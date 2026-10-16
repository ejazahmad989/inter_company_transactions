# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import hashlib
import hmac
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
			"Payment Entry", "Journal Entry",
			"Stock Entry"
		]
	}


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
			if (site.company_name or "").strip() == company_name.strip() and cint(site.is_active):
				return {
					"site_url": (site.site_url or "").strip().rstrip('/'),
					"company_name": site.company_name.strip(),
					"api_key": (site.api_key or "").strip(),
					"api_secret": (site.api_secret or "").strip(),
					"hmac_secret": (site.hmac_secret or "").strip(),
					"timeout_seconds": cint(site.timeout_seconds) or 15,
					"verify_ssl": cint(site.verify_ssl) if site.get("verify_ssl") is not None else 1
				}
	except Exception as e:
		frappe.logger().error(f"Error fetching remote site for company {company_name}: {e!s}")

	return None


def prepare_remote_payload(doc, target_company):
	"""
	Serializes a local transaction into a standard cross-site payload.
	Includes header data, line items, taxes, and idempotency key.
	"""
	system_site = frappe.utils.get_url() or "local"
	idempotency_key = f"{system_site}:{doc.doctype}:{doc.name}"

	payload = {
		"idempotency_key": idempotency_key,
		"source_site_url": system_site,
		"source_doctype": doc.doctype,
		"source_name": doc.name,
		"source_company": doc.company,
		"target_company": target_company,
		"posting_date": str(doc.get("posting_date") or doc.get("transaction_date") or nowdate()),
		"transaction_date": str(doc.get("transaction_date") or doc.get("posting_date") or nowdate()),
		"currency": doc.get("currency"),
		"conversion_rate": flt(doc.get("conversion_rate") or 1.0),
		"grand_total": flt(doc.get("grand_total") or doc.get("total") or 0.0),
		"total_qty": flt(doc.get("total_qty") or 0.0),
		"remarks": doc.get("remarks") or f"Intercompany synchronized from {doc.company} ({doc.doctype} {doc.name})",
		"items": [],
		"accounts": [],
		"taxes": []
	}

	# Serialize Items
	if hasattr(doc, "items") and doc.items:
		for row in doc.items:
			payload["items"].append({
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"description": row.get("description"),
				"qty": flt(row.get("qty") or 0.0),
				"rate": flt(row.get("rate") or 0.0),
				"amount": flt(row.get("amount") or 0.0),
				"uom": row.get("uom"),
				"stock_uom": row.get("stock_uom"),
				"conversion_factor": flt(row.get("conversion_factor") or 1.0)
			})

	# Serialize Accounts (for Journal Entry or Payment Entry)
	if hasattr(doc, "accounts") and doc.accounts:
		for row in doc.accounts:
			payload["accounts"].append({
				"account": row.get("account"),
				"party_type": row.get("party_type"),
				"party": row.get("party"),
				"debit_in_account_currency": flt(row.get("debit_in_account_currency") or row.get("debit") or 0.0),
				"credit_in_account_currency": flt(row.get("credit_in_account_currency") or row.get("credit") or 0.0),
				"account_currency": row.get("account_currency")
			})

	# Payment Entry specifics
	if doc.doctype == "Payment Entry":
		payload["payment_type"] = doc.get("payment_type")
		payload["paid_amount"] = flt(doc.get("paid_amount") or 0.0)
		payload["received_amount"] = flt(doc.get("received_amount") or 0.0)
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
			frappe.db.commit()
	except Exception:
		pass


def log_remote_sync_failure(doc, target_company, site_url, payload_json, error_message):
	"""Logs failed remote sync to Inter Company Error Log for automatic background retry."""
	if not frappe.db.exists("DocType", "Inter Company Error Log"):
		return

	try:
		err_log = frappe.new_doc("Inter Company Error Log")
		err_log.source_doctype = doc.doctype
		err_log.source_document = doc.name
		err_log.source_company = doc.company
		err_log.target_company = target_company
		err_log.error_type = "Remote Sync"
		err_log.error_message = f"Failed to push to {site_url}: {error_message}"
		err_log.traceback = frappe.get_traceback()
		err_log.status = "Pending Retry"
		err_log.payload_snapshot = payload_json
		err_log.flags.ignore_permissions = True
		err_log.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.logger().error(f"Failed to log remote sync error: {e!s}")


@frappe.whitelist(allow_guest=False)
def receive_remote_transaction(payload=None):
	"""
	Inbound REST API endpoint on receiving instance.
	Validates authentication, ensures idempotency, and creates mirrored transaction.
	"""
	raw_data = payload
	if not raw_data:
		raw_data = frappe.request.get_data(as_text=True) if hasattr(frappe, "request") and frappe.request else None

	if isinstance(raw_data, (bytes, bytearray)):
		raw_data = raw_data.decode("utf-8")

	if isinstance(raw_data, str):
		try:
			data = json.loads(raw_data)
		except Exception:
			frappe.throw(_("Invalid JSON payload received."))
	elif isinstance(raw_data, dict):
		data = raw_data
	else:
		frappe.throw(_("No payload provided."))

	# Optional HMAC signature verification
	incoming_sig = frappe.get_request_header("X-Intercompany-Signature") if hasattr(frappe, "get_request_header") else None
	settings = frappe.get_cached_doc("Inter Company Settings")
	if incoming_sig and settings.get("remote_sites"):
		# Verify if any remote site has matching HMAC secret
		verified = False
		raw_bytes = json.dumps(data, default=str).encode("utf-8")
		for site in settings.remote_sites:
			if site.hmac_secret:
				expected = hmac.new(site.hmac_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
				if hmac.compare_digest(incoming_sig, expected):
					verified = True
					break
		if not verified:
			frappe.logger().warning("HMAC signature mismatch on receive_remote_transaction")

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

	# Identify Target Company
	target_company = data.get("target_company")
	if not target_company or not frappe.db.exists("Company", target_company):
		# Fall back to single company default or throw
		companies = frappe.get_all("Company", limit=1)
		if companies:
			target_company = companies[0].name
		else:
			frappe.throw(_("Target company {0} does not exist on this ERPNext instance.").format(target_company))

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
		"Payment Entry": "Payment Entry",
		"Journal Entry": "Journal Entry",
		"Stock Entry": "Stock Entry"
	}

	target_doctype = target_doctype_map.get(source_doctype)
	if not target_doctype:
		frappe.throw(_("Unsupported source DocType for intercompany sync: {0}").format(source_doctype))

	# Construct Mirrored Document
	target_doc = frappe.new_doc(target_doctype)
	target_doc.company = target_company

	# Set posting date
	if hasattr(target_doc, "posting_date"):
		target_doc.posting_date = data.get("posting_date") or nowdate()
	if hasattr(target_doc, "transaction_date"):
		target_doc.transaction_date = data.get("transaction_date") or nowdate()

	# Resolve Party (Customer or Supplier)
	party_name = resolve_counterparty_for_remote_source(source_company, target_doctype, target_company)
	if target_doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]:
		target_doc.supplier = party_name
	elif target_doctype in ["Sales Order", "Sales Invoice", "Delivery Note", "Quotation"]:
		target_doc.customer = party_name

	# Map Line Items
	if hasattr(target_doc, "items") and data.get("items"):
		for row in data["items"]:
			resolved_item_code = resolve_item_code_for_remote(row.get("item_code"), target_company)
			item_row = {
				"item_code": resolved_item_code,
				"qty": flt(row.get("qty")),
				"rate": flt(row.get("rate")),
				"uom": row.get("uom")
			}
			# Warehouse resolution
			if hasattr(target_doc, "set_warehouse") and target_doc.set_warehouse:
				item_row["warehouse"] = target_doc.set_warehouse
			target_doc.append("items", item_row)

	# Journal Entry specifics
	if target_doctype == "Journal Entry":
		target_doc.voucher_type = "Inter Company Journal Entry" if frappe.db.exists("Journal Entry Type", "Inter Company Journal Entry") else "Journal Entry"
		target_doc.user_remark = data.get("remarks")
		# Post mirrored entries
		for acc_row in data.get("accounts", []):
			# Map account or use default clearing account
			clearing_account = get_or_create_intercompany_clearing_account(target_company)
			target_doc.append("accounts", {
				"account": clearing_account,
				"debit_in_account_currency": flt(acc_row.get("credit_in_account_currency")),
				"credit_in_account_currency": flt(acc_row.get("debit_in_account_currency"))
			})

	# Payment Entry specifics
	if target_doctype == "Payment Entry":
		inv_type = "Pay" if data.get("payment_type") == "Receive" else "Receive"
		target_doc.payment_type = inv_type
		target_doc.party_type = "Supplier" if inv_type == "Pay" else "Customer"
		target_doc.party = party_name
		target_doc.paid_amount = flt(data.get("received_amount") or data.get("paid_amount") or 0.0)
		target_doc.received_amount = flt(data.get("paid_amount") or data.get("received_amount") or 0.0)

	# Set Intercompany Link Markers
	target_doc.intercompany_linked_doc_doctype = source_doctype
	target_doc.intercompany_linked_doc_name = source_name
	target_doc.intercompany_linked_company = source_company
	target_doc.intercompany_target_company = source_company

	target_doc.flags.ignore_permissions = True
	target_doc.flags.ignore_mandatory = True
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

	frappe.db.commit()

	return {
		"success": True,
		"created_doctype": target_doc.doctype,
		"created_name": target_doc.name,
		"company": target_company,
		"message": _("Created mirrored draft document {0} {1}").format(target_doc.doctype, target_doc.name)
	}


def resolve_counterparty_for_remote_source(source_company, target_doctype, target_company):
	"""Resolves or auto-provisions customer/supplier for the remote sister entity."""
	is_supplier = target_doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]
	party_doctype = "Supplier" if is_supplier else "Customer"

	# Check if party with source_company name exists
	if frappe.db.exists(party_doctype, source_company):
		return source_company

	# Search by custom intercompany field
	existing = frappe.db.get_value(
		party_doctype,
		{"is_inter_company": 1, "represents_company": source_company},
		"name"
	)
	if existing:
		return existing

	# Fall back to first available customer/supplier or create
	first_party = frappe.db.get_value(party_doctype, {}, "name")
	if first_party:
		return first_party

	# Create new party representing the sister company
	try:
		new_party = frappe.new_doc(party_doctype)
		if is_supplier:
			new_party.supplier_name = source_company
			new_party.supplier_group = "Inter Company" if frappe.db.exists("Supplier Group", "Inter Company") else "All Supplier Groups"
		else:
			new_party.customer_name = source_company
			new_party.customer_group = "Inter Company" if frappe.db.exists("Customer Group", "Inter Company") else "All Customer Groups"
			new_party.territory = "All Territories"
		new_party.is_inter_company = 1
		new_party.represents_company = source_company
		new_party.flags.ignore_permissions = True
		new_party.insert(ignore_permissions=True)
		frappe.db.commit()
		return new_party.name
	except Exception:
		return source_company


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
def cancel_remote_transaction(payload=None):
	"""
	Inbound cancellation endpoint. Cancels mirrored document on remote instance.
	"""
	raw_data = payload
	if not raw_data:
		raw_data = frappe.request.get_data(as_text=True) if hasattr(frappe, "request") and frappe.request else None

	if isinstance(raw_data, str):
		data = json.loads(raw_data)
	else:
		data = raw_data or {}

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
		target_doc.flags.ignore_permissions = True
		target_doc.flags.intercompany_auto_cancel = True
		target_doc.cancel()
		frappe.db.commit()
		return {"success": True, "cancelled": f"{ref.target_doctype} {ref.target_name}"}
	elif target_doc.docstatus == 0:
		target_doc.delete()
		frappe.db.commit()
		return {"success": True, "deleted_draft": f"{ref.target_doctype} {ref.target_name}"}

	return {"success": True, "message": "Already cancelled"}


@frappe.whitelist()
def diagnose_remote_site_connectivity(site_url, api_key=None, api_secret=None, timeout=5):
	"""
	Comprehensive Multi-Layer Network, Port & Firewall Diagnostic Engine.
	Executes 6 verification layers:
	  1. URL format & scheme validation
	  2. DNS hostname resolution
	  3. TCP socket / port reachability
	  4. SSL/TLS Handshake
	  5. Frappe API Token Authentication
	  6. Intercompany Transactions App Handshake
	Returns actionable Linux firewall commands (UFW, Firewalld, iptables, AWS SG).
	"""
	if not site_url:
		frappe.throw(_("Please provide a Site URL to diagnose."))

	site_url = site_url.strip().rstrip('/')
	timeout = cint(timeout) or 5

	diag = {
		"site_url": site_url,
		"overall_status": "Passed",
		"steps": [],
		"firewall_commands": {},
		"latency_ms": 0,
		"error": None
	}

	# Step 1: URL Parsing
	parsed = urllib.parse.urlparse(site_url)
	if not parsed.scheme or not parsed.netloc:
		diag["overall_status"] = "Failed"
		diag["error"] = _("Invalid URL format. Please include protocol, e.g. https://erp.yourdomain.com:443")
		diag["steps"].append({
			"step": "URL Format",
			"status": "Failed",
			"details": _("Missing scheme (http/https) or host domain.")
		})
		return diag

	scheme = parsed.scheme.lower()
	hostname = parsed.hostname
	port = parsed.port or (443 if scheme == "https" else 80)

	diag["steps"].append({
		"step": "URL & Protocol",
		"status": "Passed" if scheme == "https" else "Warning",
		"details": f"Scheme: {scheme.upper()}, Host: {hostname}, Port: {port}" + (" (Plain HTTP is unencrypted; HTTPS recommended)" if scheme == "http" else "")
	})

	# Step 2: DNS Resolution
	ip_address = None
	try:
		ip_address = socket.gethostbyname(hostname)
		diag["steps"].append({
			"step": "DNS Resolution",
			"status": "Passed",
			"details": f"Hostname '{hostname}' successfully resolved to IP: {ip_address}"
		})
	except socket.gaierror as e:
		diag["overall_status"] = "Failed"
		diag["steps"].append({
			"step": "DNS Resolution",
			"status": "Failed",
			"details": f"DNS Lookup failed for host '{hostname}': {e!s}. Ensure domain is configured in DNS or /etc/hosts."
		})
		_generate_firewall_remedy(diag, hostname, port)
		return diag

	# Step 3: TCP Port & Socket Reachability
	t_start = time.time()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.settimeout(timeout)
	try:
		sock.connect((hostname, port))
		sock.close()
		sock_latency = round((time.time() - t_start) * 1000, 2)
		diag["latency_ms"] = sock_latency
		diag["steps"].append({
			"step": "TCP Port & Firewall Reachability",
			"status": "Passed",
			"details": f"Port {port} on {ip_address} is OPEN and reachable. (TCP handshake: {sock_latency} ms)"
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

	# Step 4: SSL/TLS Handshake (if HTTPS)
	if scheme == "https":
		try:
			context = ssl.create_default_context()
			with socket.create_connection((hostname, port), timeout=timeout) as s:
				with context.wrap_socket(s, server_hostname=hostname) as ssock:
					cert = ssock.getpeercert()
					diag["steps"].append({
						"step": "SSL / TLS Handshake",
						"status": "Passed",
						"details": f"TLS verification valid. Certificate Subject: {dict(x[0] for x in cert.get('subject', []))}"
					})
		except ssl.SSLError as e:
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
			ssl_ctx = ssl.create_default_context()
			ssl_ctx.check_hostname = False
			ssl_ctx.verify_mode = ssl.CERT_NONE

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
		ssl_ctx = ssl.create_default_context()
		ssl_ctx.check_hostname = False
		ssl_ctx.verify_mode = ssl.CERT_NONE

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
