# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import hashlib
import hmac
import ipaddress
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate


@frappe.whitelist()
def get_app_version_and_capabilities():
	"""
	Handshake endpoint responding to remote federated instances
	with version and supported intercompany capabilities.
	"""
	return {
		"app": "inter_company_transactions",
		"version": "1.0.0",
		"status": "ready",
		"capabilities": [
			"federated_multi_site_sync",
			"bidirectional_document_mirroring",
			"idempotent_inbound_receiver",
			"remote_cancellation_webhook",
			"network_firewall_diagnostics",
			"item_mapping_translation",
			"multi_currency_exchange"
		],
		"supported_doctypes": [
			"Sales Order", "Purchase Order",
			"Sales Invoice", "Purchase Invoice",
			"Delivery Note", "Purchase Receipt",
			"Quotation", "Supplier Quotation",
			"Material Request", "Request for Quotation",
			"Payment Entry", "Journal Entry",
			"Stock Entry", "Landed Cost Voucher"
		]
	}


def _get_decrypted_secret(row, fieldname):
	"""Safely retrieve decrypted Password field from an Inter Company Remote Site row."""
	if not row:
		return ""
	get_pw = getattr(row, "get_password", None)
	if callable(get_pw):
		try:
			pw = get_pw(fieldname, raise_exception=False)
			if pw is not None:
				return str(pw).strip()
		except Exception:
			pass
	row_name = row.get("name") if hasattr(row, "get") else getattr(row, "name", None)
	if row_name and hasattr(frappe, "db") and frappe.db:
		try:
			from frappe.utils.password import get_decrypted_password

			pw = get_decrypted_password(
				"Inter Company Remote Site",
				row_name,
				fieldname,
				raise_exception=False,
			)
			if pw is not None:
				return str(pw).strip()
		except Exception:
			pass
	raw_val = row.get(fieldname) if hasattr(row, "get") else getattr(row, fieldname, None)
	if not raw_val:
		return ""
	raw_str = str(raw_val).strip()
	if raw_str and set(raw_str) == {"*"}:
		return ""
	return raw_str


def get_remote_site_for_company(company_name):
	"""
	Finds configured remote ERPNext site for the specified company.
	Checks Inter Company Settings > remote_sites table.
	"""
	if not company_name:
		return None

	try:
		settings = frappe.get_cached_doc("Inter Company Settings")
		if not settings.get("remote_sites"):
			return None

		for site in settings.remote_sites:
			site_co = (site.get("company_name") if hasattr(site, "get") else getattr(site, "company_name", None) or "").strip()
			site_active = site.get("is_active") if hasattr(site, "get") else getattr(site, "is_active", 0)
			if site_co == company_name.strip() and cint(site_active):
				site_url = (site.get("site_url") if hasattr(site, "get") else getattr(site, "site_url", "") or "").strip().rstrip('/')
				api_key = (site.get("api_key") if hasattr(site, "get") else getattr(site, "api_key", "") or "").strip()
				timeout_val = site.get("timeout_seconds") if hasattr(site, "get") else getattr(site, "timeout_seconds", 0)
				verify_val = site.get("verify_ssl") if hasattr(site, "get") else getattr(site, "verify_ssl", None)
				return {
					"site_url": site_url,
					"company_name": site_co,
					"api_key": api_key,
					"api_secret": _get_decrypted_secret(site, "api_secret"),
					"hmac_secret": _get_decrypted_secret(site, "hmac_secret"),
					"timeout_seconds": cint(timeout_val) or 15,
					"verify_ssl": cint(verify_val) if verify_val is not None else 1
				}
	except Exception as e:
		frappe.logger().error(f"Error fetching remote site for company {company_name}: {e!s}")

	return None


def prepare_remote_payload(doc, target_company):
	"""
	Serializes a local transaction into a standard cross-site payload.
	Includes header data, source company currency, line items, taxes, and idempotency key.
	"""
	system_site = frappe.utils.get_url() or "local"
	idempotency_key = f"{system_site}:{doc.doctype}:{doc.name}"

	source_company_currency = None
	if doc.get("company") and hasattr(frappe, "db") and frappe.db:
		try:
			source_company_currency = frappe.db.get_value("Company", doc.get("company"), "default_currency")
		except Exception:
			source_company_currency = None

	payload = {
		"idempotency_key": idempotency_key,
		"source_site_url": system_site,
		"source_doctype": doc.doctype,
		"source_name": doc.name,
		"source_company": doc.company,
		"source_company_currency": source_company_currency,
		"target_company": target_company,
		"posting_date": str(doc.get("posting_date") or doc.get("transaction_date") or nowdate()),
		"transaction_date": str(doc.get("transaction_date") or doc.get("posting_date") or nowdate()),
		"schedule_date": str(doc.get("schedule_date") or doc.get("delivery_date") or ""),
		"currency": doc.get("currency") or source_company_currency,
		"conversion_rate": flt(doc.get("conversion_rate") or 1.0),
		"grand_total": flt(doc.get("grand_total") or doc.get("total") or 0.0),
		"total_qty": flt(doc.get("total_qty") or 0.0),
		"total_taxes_and_charges": flt(doc.get("total_taxes_and_charges") or 0.0),
		"stock_entry_type": doc.get("stock_entry_type"),
		"purpose": doc.get("purpose"),
		"remarks": doc.get("remarks") or f"Intercompany synchronized from {doc.company} ({doc.doctype} {doc.name})",
		"items": [],
		"accounts": [],
		"taxes": []
	}

	# Serialize Items
	if doc.get("items"):
		for row in (doc.get("items") or []):
			payload["items"].append({
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"description": row.get("description"),
				"qty": flt(row.get("qty") or 0.0),
				"rate": flt(row.get("rate") or row.get("basic_rate") or row.get("valuation_rate") or 0.0),
				"basic_rate": flt(row.get("basic_rate") or row.get("valuation_rate") or row.get("rate") or 0.0),
				"valuation_rate": flt(row.get("valuation_rate") or 0.0),
				"amount": flt(row.get("amount") or row.get("basic_amount") or 0.0),
				"uom": row.get("uom"),
				"stock_uom": row.get("stock_uom"),
				"conversion_factor": flt(row.get("conversion_factor") or 1.0),
				"schedule_date": str(row.get("schedule_date") or ""),
				"s_warehouse": row.get("s_warehouse"),
				"t_warehouse": row.get("t_warehouse"),
			})

	# Serialize Accounts (for Journal Entry)
	if hasattr(doc, "accounts") and doc.accounts:
		for row in doc.accounts:
			payload["accounts"].append({
				"account": row.get("account"),
				"party_type": row.get("party_type"),
				"party": row.get("party"),
				"debit_in_account_currency": flt(row.get("debit_in_account_currency") or row.get("debit") or 0.0),
				"credit_in_account_currency": flt(row.get("credit_in_account_currency") or row.get("credit") or 0.0),
				"debit": flt(row.get("debit") or 0.0),
				"credit": flt(row.get("credit") or 0.0),
				"exchange_rate": flt(row.get("exchange_rate") or 1.0),
				"account_currency": row.get("account_currency"),
			})

	# Serialize Taxes / Landed Cost charges
	if hasattr(doc, "taxes") and doc.taxes:
		for row in doc.taxes:
			payload["taxes"].append({
				"expense_account": row.get("expense_account") or row.get("account_head"),
				"description": row.get("description"),
				"amount": flt(row.get("amount") or row.get("tax_amount") or 0.0),
				"base_amount": flt(row.get("base_amount") or row.get("base_tax_amount") or row.get("amount") or 0.0),
			})

	# Payment Entry specifics
	if doc.doctype == "Payment Entry":
		payload["payment_type"] = doc.get("payment_type")
		payload["paid_amount"] = flt(doc.get("paid_amount") or 0.0)
		payload["received_amount"] = flt(doc.get("received_amount") or 0.0)
		payload["paid_from_account_currency"] = doc.get("paid_from_account_currency")
		payload["paid_to_account_currency"] = doc.get("paid_to_account_currency")
		payload["source_exchange_rate"] = flt(doc.get("source_exchange_rate") or 1.0)
		payload["target_exchange_rate"] = flt(doc.get("target_exchange_rate") or 1.0)
		payload["party_type"] = doc.get("party_type")
		payload["party"] = doc.get("party")

	return payload


def push_document_to_remote_site(doc, target_company, remote_site):
	"""
	Dispatches transaction payload via REST API to a remote ERPNext instance.
	Records transaction reference or queues for automated background retry if offline.
	"""
	site_url = remote_site["site_url"]
	endpoint = f"{site_url}/api/method/inter_company_transactions.sync.receive_remote_transaction"
	payload_data = prepare_remote_payload(doc, target_company)
	payload_json = json.dumps(payload_data, default=str)
	payload_bytes = payload_json.encode("utf-8")

	headers = {
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Authorization": f"token {remote_site['api_key']}:{remote_site['api_secret']}"
	}

	# Generate HMAC signature if secret configured
	if remote_site.get("hmac_secret"):
		sig = hmac.new(
			remote_site["hmac_secret"].encode("utf-8"),
			payload_bytes,
			hashlib.sha256
		).hexdigest()
		headers["X-Intercompany-Signature"] = sig

	# Create SSL context
	ssl_context = ssl.create_default_context()
	if not remote_site.get("verify_ssl", 1):
		ssl_context.check_hostname = False
		ssl_context.verify_mode = ssl.CERT_NONE

	timeout = remote_site.get("timeout_seconds", 15)

	try:
		req = urllib.request.Request(endpoint, data=payload_bytes, headers=headers, method="POST")
		with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
			resp_body = resp.read().decode("utf-8")
			resp_json = json.loads(resp_body)
			data = resp_json.get("message") if "message" in resp_json else resp_json

			if data and data.get("success"):
				created_dt = data.get("created_doctype")
				created_name = data.get("created_name")

				# Create local Inter Company Document Reference
				create_remote_document_reference(
					source_doc=doc,
					target_doctype=created_dt,
					target_name=created_name,
					target_company=target_company,
					remote_site_url=site_url,
					idempotency_key=payload_data["idempotency_key"]
				)

				# Update remote site health
				update_remote_site_status(remote_site["company_name"], "Connected", None)

				frappe.msgprint(_("Successfully synchronized to remote instance ({0}): Created draft {1} {2} in {3}").format(
					site_url, created_dt, created_name, target_company
				), alert=True)

				return {
					"success": True,
					"created_doctype": created_dt,
					"created_name": created_name,
					"remote_site": site_url
				}
			else:
				err_msg = data.get("message") if isinstance(data, dict) else str(data)
				raise Exception(_("Remote instance returned error: {0}").format(err_msg))

	except Exception as e:
		err_text = str(e)
		frappe.logger().error(f"Remote sync failed for {doc.doctype} {doc.name} to {site_url}: {err_text}")
		update_remote_site_status(remote_site["company_name"], "Error", err_text)

		# Log into Inter Company Error Log with payload for automatic background retry
		log_remote_sync_failure(doc, target_company, site_url, payload_json, err_text)

		frappe.msgprint(_("Notice: Remote instance at {0} is currently unreachable ({1}). Transaction saved locally and queued for automatic background sync retry.").format(
			site_url, err_text
		), indicator="orange")

		return {
			"success": False,
			"queued_for_retry": True,
			"error": err_text
		}


def push_cancellation_to_remote_site(doc, remote_site):
	"""Send signed cancellation notification to a configured remote federated ERPNext site."""
	if not remote_site or not doc:
		return False
	site_url = remote_site["site_url"]
	endpoint = f"{site_url}/api/method/inter_company_transactions.sync.cancel_remote_transaction"
	payload_bytes = json.dumps(
		{
			"source_doctype": doc.doctype,
			"source_name": doc.name,
			"source_company": doc.get("company"),
		},
		default=str,
	).encode("utf-8")
	headers = {
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Authorization": f"token {remote_site['api_key']}:{remote_site['api_secret']}",
	}
	if remote_site.get("hmac_secret"):
		headers["X-Intercompany-Signature"] = hmac.new(
			remote_site["hmac_secret"].encode("utf-8"),
			payload_bytes,
			hashlib.sha256,
		).hexdigest()

	ssl_context = ssl.create_default_context()
	if not cint(remote_site.get("verify_ssl", 1)):
		ssl_context.check_hostname = False
		ssl_context.verify_mode = ssl.CERT_NONE

	timeout = cint(remote_site.get("timeout_seconds")) or 10
	req = urllib.request.Request(endpoint, data=payload_bytes, headers=headers, method="POST")
	with urllib.request.urlopen(req, timeout=timeout, context=ssl_context):
		return True


def create_remote_document_reference(source_doc, target_doctype, target_name, target_company, remote_site_url, idempotency_key):
	"""Records cross-site reference linking source document to remote target document."""
	if not frappe.db.exists("DocType", "Inter Company Document Reference"):
		return

	try:
		ref = frappe.new_doc("Inter Company Document Reference")
		ref.source_doctype = source_doc.doctype
		ref.source_name = source_doc.name
		ref.source_company = source_doc.company
		ref.target_doctype = target_doctype
		ref.target_name = target_name
		ref.target_company = target_company
		ref.is_remote = 1
		ref.remote_site_url = remote_site_url
		ref.idempotency_key = idempotency_key
		ref.flags.ignore_permissions = True
		ref.flags.ignore_links = True
		ref.insert(ignore_permissions=True, ignore_links=True)
	except Exception as e:
		frappe.logger().error(f"Error creating remote document reference: {e!s}")


def update_remote_site_status(company_name, status, error_message=None):
	"""Updates last_sync_time and status in Inter Company Settings child table."""
	try:
		settings = frappe.get_doc("Inter Company Settings")
		updated = False
		for row in (settings.remote_sites or []):
			if (row.company_name or "").strip() == company_name.strip():
				row.sync_status = status
				row.last_sync_time = now_datetime()
				if error_message:
					row.last_error = error_message[:140]
				elif status == "Connected":
					row.last_error = ""
				updated = True
		if updated:
			settings.flags.ignore_permissions = True
			settings.save(ignore_permissions=True)
	except Exception:
		pass


def log_remote_sync_failure(doc, target_company, site_url, payload_json, error_message):
	"""Logs failed remote sync to Inter Company Error Log for automatic background retry."""
	if not frappe.db.exists("DocType", "Inter Company Error Log"):
		return

	try:
		target_map = {
			"Sales Order": "Purchase Order",
			"Purchase Order": "Sales Order",
			"Sales Invoice": "Purchase Invoice",
			"Purchase Invoice": "Sales Invoice",
			"Delivery Note": "Purchase Receipt",
			"Purchase Receipt": "Delivery Note",
			"Quotation": "Supplier Quotation",
			"Supplier Quotation": "Quotation",
			"Material Request": "Purchase Order",
			"Request for Quotation": "Supplier Quotation",
			"Payment Entry": "Payment Entry",
			"Journal Entry": "Journal Entry",
			"Stock Entry": "Stock Entry",
			"Landed Cost Voucher": "Journal Entry",
		}
		err_log = frappe.new_doc("Inter Company Error Log")
		err_log.source_doctype = doc.doctype
		err_log.source_name = doc.name
		err_log.source_company = doc.company
		err_log.target_company = target_company
		err_log.target_doctype = target_map.get(doc.doctype, doc.doctype)
		err_log.error_type = "Remote Sync"
		err_log.error_message = f"Failed to push to {site_url}: {error_message}"
		err_log.traceback = frappe.get_traceback()
		err_log.status = "Pending Retry"
		err_log.payload_snapshot = payload_json
		err_log.flags.ignore_permissions = True
		err_log.insert(ignore_permissions=True)
	except Exception as e:
		frappe.logger().error(f"Failed to log remote sync error: {e!s}")


def _get_request_raw_data_safe():
	try:
		if getattr(frappe, "request", None):
			return frappe.request.get_data(as_text=True)
	except RuntimeError:
		pass
	return None


def _get_request_header_safe(header_name):
	try:
		if getattr(frappe, "request", None) and hasattr(frappe, "get_request_header"):
			return frappe.get_request_header(header_name)
	except RuntimeError:
		pass
	return None


def _verify_remote_hmac_signature(data, raw_text_for_hmac):
	"""Strictly verify X-Intercompany-Signature when any active remote site defines an HMAC secret."""
	settings = frappe.get_cached_doc("Inter Company Settings")
	remote_sites = (settings.get("remote_sites") or []) if settings else []
	active_sites = [
		s for s in remote_sites
		if cint(s.get("is_active") if (isinstance(s, dict) and "is_active" in s) or hasattr(s, "is_active") else 1) != 0
	]
	if not active_sites:
		return

	source_company = ((data or {}).get("source_company") or "").strip()
	source_site_url = ((data or {}).get("source_site_url") or "").strip().rstrip("/")

	matched_secrets = []
	all_secrets = []
	for site in active_sites:
		secret = _get_decrypted_secret(site, "hmac_secret")
		if not secret:
			continue
		all_secrets.append(secret)
		site_co = (site.get("company_name") if hasattr(site, "get") else getattr(site, "company_name", "") or "").strip()
		site_url = (site.get("site_url") if hasattr(site, "get") else getattr(site, "site_url", "") or "").strip().rstrip("/")
		if (source_company and site_co == source_company) or (source_site_url and site_url == source_site_url):
			matched_secrets.append(secret)

	secrets_to_check = matched_secrets or all_secrets
	if not secrets_to_check:
		return

	incoming_sig = (_get_request_header_safe("X-Intercompany-Signature") or "").strip()
	auth_exc = getattr(frappe, "AuthenticationError", getattr(frappe, "PermissionError", Exception))
	if not incoming_sig:
		frappe.throw(_("Missing X-Intercompany-Signature HMAC header."), exc=auth_exc)

	raw_bytes = (
		raw_text_for_hmac.encode("utf-8")
		if raw_text_for_hmac is not None
		else json.dumps(data, default=str).encode("utf-8")
	)
	verified = any(
		hmac.compare_digest(
			incoming_sig,
			hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest(),
		)
		for secret in secrets_to_check
	)
	if not verified:
		frappe.throw(_("Invalid HMAC signature on remote inter-company request."), exc=auth_exc)


@frappe.whitelist(allow_guest=False)
def receive_remote_transaction(payload: dict | str | bytes | None = None):
	"""
	Inbound REST API endpoint on receiving instance.
	Validates authentication, ensures idempotency, and creates mirrored transaction.
	"""
	raw_data = payload
	if not raw_data:
		raw_data = _get_request_raw_data_safe()

	if isinstance(raw_data, (bytes, bytearray)):
		raw_data = raw_data.decode("utf-8")

	raw_text_for_hmac = raw_data if isinstance(raw_data, str) else None

	if isinstance(raw_data, str):
		try:
			data = json.loads(raw_data)
		except Exception:
			frappe.throw(_("Invalid JSON payload received."))
	elif isinstance(raw_data, dict):
		data = raw_data
	else:
		frappe.throw(_("No payload provided."))

	# Strict HMAC signature verification whenever remote sites configure an HMAC secret
	_verify_remote_hmac_signature(data, raw_text_for_hmac)

	# Idempotency Check
	idempotency_key = data.get("idempotency_key")
	if idempotency_key and frappe.db.exists("DocType", "Inter Company Document Reference"):
		existing_ref = frappe.db.get_value(
			"Inter Company Document Reference",
			{"idempotency_key": idempotency_key},
			["target_doctype", "target_name", "target_company"],
			as_dict=True
		)
		if existing_ref and frappe.db.exists(existing_ref.target_doctype, existing_ref.target_name):
			return {
				"success": True,
				"already_processed": True,
				"created_doctype": existing_ref.target_doctype,
				"created_name": existing_ref.target_name,
				"company": existing_ref.target_company,
				"message": _("Transaction already processed (Idempotent)")
			}

	# Identify Target Company strictly — never fall back to an arbitrary database Company
	target_company = (data.get("target_company") or "").strip()
	if not target_company or not frappe.db.exists("Company", target_company):
		frappe.throw(
			_("Target company {0} does not exist on this ERPNext instance.").format(target_company or _("(missing)"))
		)

	source_doctype = data.get("source_doctype")
	source_name = data.get("source_name")
	source_company = data.get("source_company")

	# Resolve Target DocType mapping
	target_doctype_map = {
		"Sales Order": "Purchase Order",
		"Purchase Order": "Sales Order",
		"Sales Invoice": "Purchase Invoice",
		"Purchase Invoice": "Sales Invoice",
		"Delivery Note": "Purchase Receipt",
		"Purchase Receipt": "Delivery Note",
		"Quotation": "Supplier Quotation",
		"Supplier Quotation": "Quotation",
		"Material Request": "Purchase Order",
		"Request for Quotation": "Supplier Quotation",
		"Payment Entry": "Payment Entry",
		"Journal Entry": "Journal Entry",
		"Stock Entry": "Stock Entry",
		"Landed Cost Voucher": "Journal Entry"
	}

	target_doctype = target_doctype_map.get(source_doctype)
	if not target_doctype:
		frappe.throw(_("Unsupported source DocType for intercompany sync: {0}").format(source_doctype))

	# Verify the authenticated API user has create permission on the target DocType
	frappe.has_permission(target_doctype, "create", throw=True)

	# Construct Mirrored Document
	target_doc = frappe.new_doc(target_doctype)
	target_doc.company = target_company

	# Set posting / transaction / schedule dates
	if hasattr(target_doc, "posting_date"):
		target_doc.posting_date = data.get("posting_date") or nowdate()
	if hasattr(target_doc, "transaction_date"):
		target_doc.transaction_date = data.get("transaction_date") or nowdate()
	if hasattr(target_doc, "schedule_date") and not getattr(target_doc, "schedule_date", None):
		target_doc.schedule_date = data.get("schedule_date") or data.get("transaction_date") or nowdate()

	if hasattr(target_doc, "delivery_date") and not getattr(target_doc, "delivery_date", None):
		target_doc.delivery_date = data.get("schedule_date") or data.get("transaction_date") or nowdate()

	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
		_precalculate_mirrored_doc_totals,
		_preserve_intercompany_currency_after_defaults,
		get_intercompany_warehouse,
		get_or_create_intercompany_warehouse,
		lookup_intercompany_exchange_rate,
	)

	tx_date = data.get("posting_date") or data.get("transaction_date") or nowdate()
	source_company_ccy = data.get("source_company_currency") or data.get("currency")
	target_company_ccy = frappe.db.get_value("Company", target_company, "default_currency")

	def _remote_fx(from_ccy, to_ccy):
		if not from_ccy or not to_ccy or from_ccy == to_ccy:
			return 1.0
		src_doc_ccy = data.get("currency")
		src_conv = flt(data.get("conversion_rate") or 0.0)
		if src_doc_ccy and source_company_ccy and src_doc_ccy != source_company_ccy and src_conv > 0:
			if from_ccy == src_doc_ccy and to_ccy == source_company_ccy:
				return flt(src_conv, 9)
			if from_ccy == source_company_ccy and to_ccy == src_doc_ccy:
				return flt(1.0 / src_conv, 9)
		return flt(lookup_intercompany_exchange_rate(from_ccy, to_ccy, tx_date) or 1.0, 9)

	# Resolve Party (Customer or Supplier) only for voucher types that require one
	party_name = None
	party_dt = None
	if target_doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]:
		party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override="Supplier")
		target_doc.supplier = party_name
		party_dt = "Supplier"
	elif target_doctype == "Quotation":
		party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override="Customer")
		target_doc.quotation_to = "Customer"
		target_doc.party_name = party_name
		party_dt = "Customer"
	elif target_doctype in ["Sales Order", "Sales Invoice", "Delivery Note"]:
		party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override="Customer")
		target_doc.customer = party_name
		party_dt = "Customer"
	elif target_doctype == "Payment Entry":
		pe_inv_type = "Pay" if data.get("payment_type") == "Receive" else "Receive"
		pe_party_dt = "Supplier" if pe_inv_type == "Pay" else "Customer"
		party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override=pe_party_dt)
		party_dt = pe_party_dt
	elif target_doctype == "Journal Entry" and source_doctype == "Landed Cost Voucher":
		try:
			party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override="Supplier")
			party_dt = "Supplier"
		except Exception:
			party_name = None

	# Resolve currency, conversion_rate, and item rate_factor cleanly for trading vouchers
	src_voucher_ccy = data.get("currency") or source_company_ccy or target_company_ccy
	party_ccy = None
	if party_dt and party_name and frappe.db.exists(party_dt, party_name):
		party_ccy = frappe.db.get_value(party_dt, party_name, "default_currency")
	if party_ccy:
		target_currency = party_ccy
	elif (
		source_company_ccy
		and target_company_ccy
		and source_company_ccy != target_company_ccy
		and src_voucher_ccy == target_company_ccy
	):
		target_currency = source_company_ccy
	else:
		target_currency = src_voucher_ccy or target_company_ccy
	target_conv_rate = 1.0 if (not target_currency or not target_company_ccy or target_currency == target_company_ccy) else _remote_fx(target_currency, target_company_ccy)
	item_rate_factor = 1.0 if (not src_voucher_ccy or not target_currency or src_voucher_ccy == target_currency) else _remote_fx(src_voucher_ccy, target_currency)

	if target_currency and hasattr(target_doc, "currency"):
		target_doc.currency = target_currency
	if hasattr(target_doc, "conversion_rate"):
		target_doc.conversion_rate = target_conv_rate

	# Map Stock Entry (Company 1 Material Issue -> Company 2 Material Receipt, Same-Currency Only)
	if target_doctype == "Stock Entry":
		if source_company_ccy and target_company_ccy and source_company_ccy != target_company_ccy:
			frappe.throw(
				_(
					"Inter-Company Stock Entry works for Same-Currency companies only ({0} uses {1}, {2} uses {3}). "
					"Please use Delivery Note or Sales Invoice for different currencies."
				).format(source_company, source_company_ccy, target_company, target_company_ccy)
			)
		target_doc.stock_entry_type = "Material Receipt"
		target_doc.purpose = "Material Receipt"
		target_warehouse = get_intercompany_warehouse(target_company) or get_or_create_intercompany_warehouse(target_company)
		target_doc.from_warehouse = None
		target_doc.to_warehouse = target_warehouse
		target_doc.remarks = data.get("remarks") or f"Intercompany Material Receipt synchronized from {source_company} ({source_doctype} {source_name})"

		for row in data.get("items", []):
			resolved_item_code = resolve_item_code_for_remote(row.get("item_code"), target_company)
			basic_rate = flt(row.get("basic_rate") or row.get("valuation_rate") or row.get("rate") or 0.0, 4)
			qty = flt(row.get("qty") or 1.0)
			se_row = {
				"item_code": resolved_item_code,
				"qty": qty,
				"uom": row.get("uom") or "Nos",
				"conversion_factor": flt(row.get("conversion_factor") or 1.0),
				"s_warehouse": None,
				"t_warehouse": target_warehouse,
				"basic_rate": basic_rate,
				"basic_amount": flt(basic_rate * qty, 2),
				"amount": flt(basic_rate * qty, 2),
			}
			if basic_rate <= 0:
				se_row["allow_zero_valuation_rate"] = 1
			target_doc.append("items", se_row)

	# Map Standard Order / Invoice / Receipt / Quotation Line Items
	elif hasattr(target_doc, "items") and data.get("items"):
		for row in data["items"]:
			resolved_item_code = resolve_item_code_for_remote(row.get("item_code"), target_company)
			item_row = {
				"item_code": resolved_item_code,
				"qty": flt(row.get("qty")),
				"rate": flt(flt(row.get("rate")) * item_rate_factor, 4),
				"uom": row.get("uom")
			}
			sched = row.get("schedule_date") or getattr(target_doc, "schedule_date", None) or getattr(target_doc, "delivery_date", None)
			if sched:
				if target_doctype == "Sales Order":
					item_row["delivery_date"] = sched
				else:
					item_row["schedule_date"] = sched
			# Warehouse resolution
			if hasattr(target_doc, "set_warehouse") and target_doc.set_warehouse:
				item_row["warehouse"] = target_doc.set_warehouse
			target_doc.append("items", item_row)

	# Journal Entry specifics (including remote Landed Cost Voucher -> Journal Entry)
	if target_doctype == "Journal Entry":
		target_doc.voucher_type = "Journal Entry"
		target_doc.user_remark = data.get("remarks")
		je_fx = _remote_fx(source_company_ccy, target_company_ccy)
		if source_company_ccy and target_company_ccy and source_company_ccy != target_company_ccy:
			target_doc.multi_currency = 1
		clearing_account = get_or_create_intercompany_clearing_account(target_company)
		if source_doctype == "Landed Cost Voucher":
			total_amt = flt(data.get("total_taxes_and_charges") or 0.0)
			if total_amt <= 0:
				total_amt = sum(flt(t.get("base_amount") or t.get("amount") or 0.0) for t in (data.get("taxes") or []))
			converted_amt = flt(total_amt * je_fx, 2)
			if converted_amt > 0:
				expense_acct = (
					frappe.db.get_value("Company", target_company, "default_expense_account")
					or frappe.db.get_value("Account", {"company": target_company, "root_type": "Expense", "is_group": 0}, "name")
					or clearing_account
				)
				payable_acct = frappe.db.get_value("Company", target_company, "default_payable_account")
				target_doc.append("accounts", {
					"account": expense_acct,
					"account_currency": target_company_ccy,
					"exchange_rate": 1.0,
					"debit_in_account_currency": converted_amt,
					"credit_in_account_currency": 0,
					"debit": converted_amt,
					"credit": 0,
				})
				if party_name and payable_acct:
					target_doc.append("accounts", {
						"account": payable_acct,
						"account_currency": target_company_ccy,
						"exchange_rate": 1.0,
						"party_type": "Supplier",
						"party": party_name,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": converted_amt,
						"debit": 0,
						"credit": converted_amt,
					})
				else:
					target_doc.append("accounts", {
						"account": clearing_account or expense_acct,
						"account_currency": target_company_ccy,
						"exchange_rate": 1.0,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": converted_amt,
						"debit": 0,
						"credit": converted_amt,
					})
		else:
			# Post mirrored entries in target company base currency
			for acc_row in data.get("accounts", []):
				row_fx = flt(acc_row.get("exchange_rate") or 1.0)
				src_base_dr = flt(acc_row.get("credit") or (flt(acc_row.get("credit_in_account_currency")) * row_fx))
				src_base_cr = flt(acc_row.get("debit") or (flt(acc_row.get("debit_in_account_currency")) * row_fx))
				if target_company_ccy and acc_row.get("account_currency") == target_company_ccy:
					dr = flt(acc_row.get("credit_in_account_currency"), 2)
					cr = flt(acc_row.get("debit_in_account_currency"), 2)
				else:
					dr = flt(src_base_dr * je_fx, 2)
					cr = flt(src_base_cr * je_fx, 2)
				target_doc.append("accounts", {
					"account": clearing_account,
					"account_currency": target_company_ccy,
					"exchange_rate": 1.0,
					"debit_in_account_currency": dr,
					"credit_in_account_currency": cr,
					"debit": dr,
					"credit": cr,
				})

	# Payment Entry specifics
	if target_doctype == "Payment Entry":
		inv_type = "Pay" if data.get("payment_type") == "Receive" else "Receive"
		target_doc.payment_type = inv_type
		target_doc.party_type = "Supplier" if inv_type == "Pay" else "Customer"
		target_doc.party = party_name
		pe_fx = _remote_fx(source_company_ccy, target_company_ccy)
		if data.get("payment_type") == "Pay":
			ref_amt = flt(data.get("received_amount") or data.get("paid_amount") or 0.0)
			ref_ccy = data.get("paid_to_account_currency") or source_company_ccy
		else:
			ref_amt = flt(data.get("paid_amount") or data.get("received_amount") or 0.0)
			ref_ccy = data.get("paid_from_account_currency") or source_company_ccy
		conv_factor = 1.0 if (not ref_ccy or not target_company_ccy or ref_ccy == target_company_ccy) else (_remote_fx(ref_ccy, target_company_ccy) if ref_ccy != source_company_ccy else pe_fx)
		settled_tgt_amt = flt(ref_amt * conv_factor, 2)
		target_doc.paid_amount = settled_tgt_amt
		target_doc.received_amount = settled_tgt_amt
		if not flt(getattr(target_doc, "source_exchange_rate", 0)):
			target_doc.source_exchange_rate = 1.0
		if not flt(getattr(target_doc, "target_exchange_rate", 0)):
			target_doc.target_exchange_rate = 1.0

	# Set Intercompany Link Markers
	target_doc.is_intercompany = 1
	target_doc.intercompany_linked_doc_doctype = source_doctype
	target_doc.intercompany_linked_doc_name = source_name
	target_doc.intercompany_linked_company = source_company
	target_doc.intercompany_target_company = source_company

	# Cross-company mirror drafts allow target company completion (warehouses/cost centers)
	# before final submission; create permission was verified above.
	target_doc.flags.ignore_permissions = True
	target_doc.flags.ignore_mandatory = True
	target_doc.flags.ict_system_sync = True

	try:
		if hasattr(target_doc, "set_missing_values"):
			target_doc.set_missing_values(for_validate=True)
	except Exception:
		pass

	if hasattr(target_doc, "currency") and target_currency:
		_preserve_intercompany_currency_after_defaults(target_doc, target_currency, target_conv_rate, tx_date)

	_precalculate_mirrored_doc_totals(target_doc)

	target_doc.insert(ignore_permissions=True, ignore_mandatory=True)

	# Record Inbound Document Reference
	create_remote_document_reference(
		source_doc=frappe._dict({"doctype": source_doctype, "name": source_name, "company": source_company}),
		target_doctype=target_doc.doctype,
		target_name=target_doc.name,
		target_company=target_company,
		remote_site_url=data.get("source_site_url"),
		idempotency_key=idempotency_key
	)

	try:
		settings = frappe.get_cached_doc("Inter Company Settings") or frappe._dict()
	except Exception:
		settings = frappe._dict()

	if cint(settings.get("auto_submit_target_doc")) and hasattr(target_doc, "submit") and target_doc.docstatus == 0:
		try:
			if hasattr(frappe.db, "savepoint"):
				frappe.db.savepoint("ict_remote_submit")
			target_doc.flags.ignore_permissions = True
			target_doc.flags.ict_system_sync = True
			target_doc.submit()
		except Exception:
			if hasattr(frappe.db, "rollback"):
				try:
					frappe.db.rollback(save_point="ict_remote_submit")
				except Exception:
					pass

	return {
		"success": True,
		"created_doctype": target_doc.doctype,
		"created_name": target_doc.name,
		"company": target_company,
		"message": _("Created mirrored draft document {0} {1}").format(target_doc.doctype, target_doc.name)
	}


def resolve_counterparty_for_remote_source(source_company, target_doctype, target_company, party_doctype_override=None):
	"""
	Resolves an existing Customer/Supplier for the remote sister entity without
	auto-creating parties or falling back to unrelated parties.
	Checks Intercompany Transaction Link first, then standard ERPNext fields
	(`is_internal_customer`/`is_internal_supplier`, `represents_company`),
	then exact company name match. Compatible with ERPNext v15 and v16.
	"""
	is_supplier = (
		party_doctype_override == "Supplier"
		if party_doctype_override in ("Customer", "Supplier")
		else target_doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]
	)
	party_doctype = "Supplier" if is_supplier else "Customer"
	internal_flag = "is_internal_supplier" if is_supplier else "is_internal_customer"

	# 1. Check explicitly configured Intercompany Transaction Link mapping first
	try:
		if frappe.db.exists("DocType", "Intercompany Transaction Link") and target_company:
			links = frappe.get_all(
				"Intercompany Transaction Link",
				filters={"enabled": 1},
				fields=["name", "main_company"],
			)
			for link in (links or []):
				rows = frappe.get_all(
					"Intercompany Linked Company",
					filters={"parent": link.name},
					fields=[
						"company",
						"main_company_customer",
						"main_company_supplier",
						"other_company_customer",
						"other_company_supplier",
					],
				)
				for row in (rows or []):
					party = None
					if link.main_company == target_company and row.company == source_company:
						party = row.main_company_supplier if is_supplier else row.main_company_customer
					elif link.main_company == source_company and row.company == target_company:
						party = row.other_company_supplier if is_supplier else row.other_company_customer
					if party:
						return party
	except Exception:
		pass

	# 2. Search by standard ERPNext represents_company + internal flag
	try:
		filters = {"represents_company": source_company}
		if frappe.db.has_column(party_doctype, internal_flag):
			filters[internal_flag] = 1
		existing = frappe.db.get_value(party_doctype, filters, "name")
		if existing:
			return existing

		# Also check represents_company alone
		existing_rep = frappe.db.get_value(party_doctype, {"represents_company": source_company}, "name")
		if existing_rep:
			return existing_rep
	except Exception:
		pass

	# 3. Check if party with exact source_company name exists
	if frappe.db.exists(party_doctype, source_company):
		return source_company

	internal_named = f"{source_company} (Internal)"
	if frappe.db.exists(party_doctype, internal_named):
		return internal_named

	frappe.throw(
		_(
			"No existing {0} found for remote company {1} in {2}. "
			"Please create the {0} manually in ERPNext and select it in Intercompany Transaction Link."
		).format(party_doctype, source_company, target_company or "")
	)


def resolve_item_code_for_remote(source_item_code, target_company):
	"""Maps source item code to local equivalent via Intercompany Item Mapping or fallback."""
	if not source_item_code:
		return frappe.db.get_value("Item", {"is_stock_item": 1}, "name") or "Service"

	# 1. Direct Item Code Match
	if frappe.db.exists("Item", source_item_code):
		return source_item_code

	# 2. Intercompany Item Mapping DocType
	if frappe.db.exists("DocType", "Intercompany Item Mapping"):
		mapped = frappe.db.get_value(
			"Intercompany Item Mapping",
			{"source_item_code": source_item_code},
			"target_item_code"
		)
		if mapped and frappe.db.exists("Item", mapped):
			return mapped

	# 3. Fallback to first active Item
	fallback = frappe.db.get_value("Item", {"disabled": 0}, "name")
	return fallback or source_item_code


def get_or_create_intercompany_clearing_account(company):
	"""Returns intercompany clearing account for the company."""
	acct = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%Inter%Company%"], "is_group": 0},
		"name"
	)
	if acct:
		return acct

	# Fall back to debtors/creditors or bank
	default_bank = frappe.db.get_value("Company", company, "default_bank_account")
	if default_bank:
		return default_bank

	return frappe.db.get_value("Account", {"company": company, "is_group": 0}, "name")


@frappe.whitelist(allow_guest=False)
def cancel_remote_transaction(payload: dict | str | bytes | None = None):
	"""
	Inbound cancellation endpoint. Cancels mirrored document on remote instance.
	"""
	raw_data = payload
	if not raw_data:
		raw_data = _get_request_raw_data_safe()

	if isinstance(raw_data, (bytes, bytearray)):
		raw_data = raw_data.decode("utf-8")

	raw_text_for_hmac = raw_data if isinstance(raw_data, str) else None

	if isinstance(raw_data, str):
		data = json.loads(raw_data)
	else:
		data = raw_data or {}

	_verify_remote_hmac_signature(data, raw_text_for_hmac)

	source_doctype = data.get("source_doctype")
	source_name = data.get("source_name")

	if not (source_doctype and source_name):
		frappe.throw(_("Source DocType and Name are required for cancellation."))

	ref = frappe.db.get_value(
		"Inter Company Document Reference",
		{"source_doctype": source_doctype, "source_name": source_name},
		["target_doctype", "target_name"],
		as_dict=True
	)

	if not ref or not frappe.db.exists(ref.target_doctype, ref.target_name):
		return {"success": True, "message": _("No corresponding document found to cancel.")}

	target_doc = frappe.get_doc(ref.target_doctype, ref.target_name)
	if target_doc.docstatus == 1:
		frappe.has_permission(ref.target_doctype, "cancel", ref.target_name, throw=True)
		target_doc.flags.ignore_permissions = True
		target_doc.flags.intercompany_auto_cancel = True
		target_doc.cancel()
		return {"success": True, "cancelled": f"{ref.target_doctype} {ref.target_name}"}
	elif target_doc.docstatus == 0:
		frappe.has_permission(ref.target_doctype, "delete", ref.target_name, throw=True)
		target_doc.delete()
		return {"success": True, "deleted_draft": f"{ref.target_doctype} {ref.target_name}"}

	return {"success": True, "message": "Already cancelled"}


def _is_blocked_ssrf_ip(ip_str):
	"""Return (blocked: bool, normalized_ip: str) blocking loopback, private, link-local, metadata & reserved ranges."""
	raw_ip = (ip_str or "").split("%", 1)[0].strip()
	ip_obj = ipaddress.ip_address(raw_ip)
	if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
		ip_obj = ip_obj.ipv4_mapped
	blocked = (
		ip_obj.is_private
		or ip_obj.is_loopback
		or ip_obj.is_link_local
		or ip_obj.is_multicast
		or ip_obj.is_reserved
		or ip_obj.is_unspecified
		or not ip_obj.is_global
	)
	return blocked, str(ip_obj)


@frappe.whitelist()
def diagnose_remote_site_connectivity(
	site_url: str,
	api_key: str | None = None,
	api_secret: str | None = None,
	timeout: int | float = 5,
	verify_ssl: int | bool = 1,
):
	"""
	Comprehensive Multi-Layer Network, Port & Firewall Diagnostic Engine.
	Executes 6 verification layers with SSRF & IPv6 safety checks:
	  1. URL format & http/https scheme validation
	  2. DNS hostname resolution (IPv4 & IPv6) & private/metadata IP blocking
	  3. TCP socket / port reachability
	  4. SSL/TLS Handshake
	  5. Frappe API Token Authentication
	  6. Intercompany Transactions App Handshake
	Returns actionable Linux firewall commands (UFW, Firewalld, iptables, AWS SG).
	"""
	frappe.only_for("System Manager")

	if not site_url:
		frappe.throw(_("Please provide a Site URL to diagnose."))

	site_url = site_url.strip().rstrip('/')
	timeout = max(1, min(cint(timeout) or 5, 30))

	diag = {
		"site_url": site_url,
		"overall_status": "Passed",
		"steps": [],
		"firewall_commands": {},
		"latency_ms": 0,
		"error": None
	}

	# Step 1: URL Parsing & Strict HTTP/HTTPS Scheme Validation
	parsed = urllib.parse.urlparse(site_url)
	scheme = (parsed.scheme or "").lower()
	hostname = parsed.hostname
	if not scheme or not parsed.netloc or not hostname or scheme not in ("http", "https"):
		diag["overall_status"] = "Failed"
		diag["error"] = _("Invalid URL format. Please include an http:// or https:// URL, e.g. https://erp.yourdomain.com:443")
		diag["steps"].append({
			"step": "URL Format",
			"status": "Failed",
			"details": _("Missing or unsupported URL scheme (only http/https supported) or missing host domain.")
		})
		return diag

	port = parsed.port or (443 if scheme == "https" else 80)

	diag["steps"].append({
		"step": "URL & Protocol",
		"status": "Passed" if scheme == "https" else "Warning",
		"details": f"Scheme: {scheme.upper()}, Host: {hostname}, Port: {port}" + (" (Plain HTTP is unencrypted; HTTPS recommended)" if scheme == "http" else "")
	})

	# Step 2: DNS Resolution (IPv4 + IPv6) & SSRF Validation
	addr_infos = []
	resolved_ips = []
	try:
		addr_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
		if not addr_infos:
			raise socket.gaierror(f"No address records returned for {hostname}")

		blocked_ips = []
		for _fam, _stype, _proto, _canon, sockaddr in addr_infos:
			ip_candidate = sockaddr[0]
			is_blocked, norm_ip = _is_blocked_ssrf_ip(ip_candidate)
			if norm_ip not in resolved_ips:
				resolved_ips.append(norm_ip)
			if is_blocked and norm_ip not in blocked_ips:
				blocked_ips.append(norm_ip)

		if blocked_ips:
			diag["overall_status"] = "Failed"
			diag["error"] = _("Blocked connection to non-public or internal IP address(es): {0}").format(", ".join(blocked_ips))
			diag["steps"].append({
				"step": "DNS Resolution & SSRF Safety",
				"status": "Failed",
				"details": diag["error"],
			})
			return diag

		ip_display = ", ".join(resolved_ips)
		diag["steps"].append({
			"step": "DNS Resolution",
			"status": "Passed",
			"details": f"Hostname '{hostname}' resolved to public IP(s): {ip_display}"
		})
	except (socket.gaierror, ValueError) as e:
		diag["overall_status"] = "Failed"
		diag["error"] = f"DNS Lookup failed for host '{hostname}': {e!s}"
		diag["steps"].append({
			"step": "DNS Resolution",
			"status": "Failed",
			"details": f"DNS Lookup failed for host '{hostname}': {e!s}. Ensure domain is configured in DNS."
		})
		_generate_firewall_remedy(diag, hostname, port)
		return diag

	# Step 3: TCP Port & Socket Reachability (supports both IPv4 and IPv6)
	t_start = time.time()
	primary_family, primary_socktype, primary_proto, _canon, primary_sockaddr = addr_infos[0]
	primary_ip = resolved_ips[0] if resolved_ips else hostname
	try:
		with socket.socket(primary_family, primary_socktype, primary_proto) as sock:
			sock.settimeout(timeout)
			sock.connect(primary_sockaddr)
		sock_latency = round((time.time() - t_start) * 1000, 2)
		diag["latency_ms"] = sock_latency
		diag["steps"].append({
			"step": "TCP Port & Firewall Reachability",
			"status": "Passed",
			"details": f"Port {port} on {primary_ip} is OPEN and reachable. (TCP handshake: {sock_latency} ms)"
		})
	except TimeoutError:
		diag["overall_status"] = "Failed"
		diag["steps"].append({
			"step": "TCP Port & Firewall Reachability",
			"status": "Failed",
			"details": f"Connection TIMED OUT after {timeout}s on port {port}. Traffic is being blocked by a firewall or security group on the remote server!"
		})
		_generate_firewall_remedy(diag, hostname, port)
		return diag
	except ConnectionRefusedError:
		diag["overall_status"] = "Failed"
		diag["steps"].append({
			"step": "TCP Port & Firewall Reachability",
			"status": "Failed",
			"details": f"Connection REFUSED on port {port}. The server is reachable, but no service (NGINX/Bench) is listening on port {port}."
		})
		_generate_firewall_remedy(diag, hostname, port)
		return diag
	except Exception as e:
		diag["overall_status"] = "Failed"
		diag["steps"].append({
			"step": "TCP Port & Firewall Reachability",
			"status": "Failed",
			"details": f"Network error reaching port {port}: {e!s}"
		})
		_generate_firewall_remedy(diag, hostname, port)
		return diag

	# Build TLS context respecting verify_ssl
	ssl_ctx = ssl.create_default_context()
	if not cint(verify_ssl):
		ssl_ctx.check_hostname = False
		ssl_ctx.verify_mode = ssl.CERT_NONE

	# Step 4: SSL/TLS Handshake (if HTTPS)
	if scheme == "https":
		try:
			verify_context = ssl.create_default_context()
			with socket.socket(primary_family, primary_socktype, primary_proto) as s:
				s.settimeout(timeout)
				s.connect(primary_sockaddr)
				with verify_context.wrap_socket(s, server_hostname=hostname) as ssock:
					cert = ssock.getpeercert()
					diag["steps"].append({
						"step": "SSL / TLS Handshake",
						"status": "Passed",
						"details": f"TLS verification valid. Certificate Subject: {dict(x[0] for x in cert.get('subject', []))}"
					})
		except ssl.SSLError as e:
			if cint(verify_ssl):
				diag["overall_status"] = "Warning"
			diag["steps"].append({
				"step": "SSL / TLS Handshake",
				"status": "Warning",
				"details": f"SSL Warning: {e!s}. If using self-signed certificate, uncheck 'Verify SSL' in Remote Site configuration."
			})
		except Exception as e:
			diag["steps"].append({
				"step": "SSL / TLS Handshake",
				"status": "Warning",
				"details": f"SSL handshake note: {e!s}"
			})

	# Step 5: Frappe REST API Token Authentication
	if api_key and api_secret:
		try:
			auth_url = f"{site_url}/api/method/frappe.auth.get_logged_user"
			req = urllib.request.Request(
				auth_url,
				headers={
					"Authorization": f"token {api_key}:{api_secret}",
					"Accept": "application/json"
				}
			)

			t_auth_start = time.time()
			with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
				auth_latency = round((time.time() - t_auth_start) * 1000, 2)
				res_data = json.loads(resp.read().decode('utf-8'))
				auth_user = res_data.get("message")
				diag["steps"].append({
					"step": "Frappe REST API Authentication",
					"status": "Passed",
					"details": f"Authenticated successfully as user '{auth_user}' (Response time: {auth_latency} ms)"
				})
		except urllib.error.HTTPError as e:
			diag["overall_status"] = "Warning"
			diag["steps"].append({
				"step": "Frappe REST API Authentication",
				"status": "Failed",
				"details": f"HTTP {e.code} ({e.reason}): Invalid API Key/Secret token or user permissions."
			})
		except Exception as e:
			diag["overall_status"] = "Warning"
			diag["steps"].append({
				"step": "Frappe REST API Authentication",
				"status": "Warning",
				"details": f"Auth check error: {e!s}"
			})
	else:
		diag["steps"].append({
			"step": "Frappe REST API Authentication",
			"status": "Skipped",
			"details": "API Key / Secret not supplied for token verification."
		})

	# Step 6: Intercompany App Handshake
	try:
		handshake_url = f"{site_url}/api/method/inter_company_transactions.sync.get_app_version_and_capabilities"
		req = urllib.request.Request(handshake_url, headers={"Accept": "application/json"})

		with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
			h_data = json.loads(resp.read().decode('utf-8'))
			app_info = h_data.get("message") if "message" in h_data else h_data
			diag["steps"].append({
				"step": "Inter Company App Handshake",
				"status": "Passed",
				"details": f"Remote instance has '{app_info.get('app')}' v{app_info.get('version')} installed with federated sync capability active!"
			})
	except Exception:
		diag["steps"].append({
			"step": "Inter Company App Handshake",
			"status": "Warning",
			"details": "Remote site does not have the public handshake responder or requires token authorization. Standard push will use API Token."
		})

	_generate_firewall_remedy(diag, hostname, port)
	return diag


def _generate_firewall_remedy(diag, hostname, port):
	"""Generates copy-pasteable firewall rules and NGINX configs for network setup."""
	diag["firewall_commands"] = {
		"port": port,
		"ubuntu_ufw": f"sudo ufw allow {port}/tcp comment 'ERPNext Intercompany Sync'",
		"centos_firewalld": f"sudo firewall-cmd --permanent --add-port={port}/tcp && sudo firewall-cmd --reload",
		"iptables": f"sudo iptables -A INPUT -p tcp --dport {port} -j ACCEPT",
		"aws_security_group": f"Inbound Rule: Type=Custom TCP, Port Range={port}, Source=0.0.0.0/0 (or IP of sending server)",
		"nginx_check": "sudo systemctl status nginx && sudo nginx -t"
	}
