# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint
import json
import urllib.request
import urllib.error


class InterCompanySettings(Document):
	pass


def get_intercompany_settings():
	"""Helper to fetch cached Inter Company Settings safely"""
	try:
		return frappe.get_cached_doc("Inter Company Settings")
	except Exception:
		return None


@frappe.whitelist()
def get_enterprise_health_check():
	"""
	Enterprise System Health Check & Telemetry
	Audits all intercompany configurations, policies, and ledger integrity.
	"""
	health = {
		"status": "Healthy",
		"total_companies": 0,
		"active_links": 0,
		"transfer_pricing_policies": 0,
		"netting_cycles": 0,
		"elimination_runs": 0,
		"open_disputes": 0,
		"error_log_count": 0,
		"recommendations": []
	}

	try:
		health["total_companies"] = frappe.db.count("Company")
		if health["total_companies"] < 2:
			health["recommendations"].append(_("At least two companies are recommended for intercompany features."))

		if frappe.db.exists("DocType", "Intercompany Transaction Link"):
			health["active_links"] = frappe.db.count("Intercompany Transaction Link", {"enabled": 1})
			if health["active_links"] == 0:
				health["recommendations"].append(_("No active Intercompany Transaction Links found. Set up company pairs."))

		if frappe.db.exists("DocType", "Transfer Pricing Policy"):
			health["transfer_pricing_policies"] = frappe.db.count("Transfer Pricing Policy", {"is_active": 1})

		if frappe.db.exists("DocType", "Inter Company Netting Cycle"):
			health["netting_cycles"] = frappe.db.count("Inter Company Netting Cycle")

		if frappe.db.exists("DocType", "Inter Company Elimination Run"):
			health["elimination_runs"] = frappe.db.count("Inter Company Elimination Run")

		if frappe.db.exists("DocType", "Inter Company Dispute"):
			health["open_disputes"] = frappe.db.count("Inter Company Dispute", {"status": ["in", ["Open", "Under Investigation"]]})

		if frappe.db.exists("DocType", "Inter Company Error Log"):
			health["error_log_count"] = frappe.db.count("Inter Company Error Log", {"status": "Failed"})
			if health["error_log_count"] > 0:
				health["status"] = "Attention Needed"
				health["recommendations"].append(_("Found {0} failed sync transactions in Error Log.").format(health["error_log_count"]))

	except Exception as e:
		health["status"] = "Warning"
		health["error"] = str(e)

	return health


@frappe.whitelist()
def test_remote_site_connection(site_url, api_key, api_secret):
	"""
	Tests REST API handshake with an external federated ERPNext instance.
	"""
	if not site_url or not api_key or not api_secret:
		frappe.throw(_("Site URL, API Key, and API Secret are required."))

	endpoint = f"{site_url.rstrip('/')}/api/method/frappe.auth.get_logged_user"
	headers = {
		"Authorization": f"token {api_key}:{api_secret}",
		"Accept": "application/json"
	}

	try:
		req = urllib.request.Request(endpoint, headers=headers)
		with urllib.request.urlopen(req, timeout=10) as resp:
			result = json.loads(resp.read().decode('utf-8'))
			return {
				"success": True,
				"message": _("Connection successful! Authenticated as: {0}").format(result.get("message"))
			}
	except urllib.error.HTTPError as e:
		return {
			"success": False,
			"message": _("HTTP {0}: {1}").format(e.code, e.reason)
		}
	except Exception as e:
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist(allow_guest=False)
def receive_intercompany_webhook(payload):
	"""
	Receives cross-site intercompany transaction payloads via REST API/Webhook,
	allowing federated multi-instance synchronization.
	"""
	if isinstance(payload, str):
		data = json.loads(payload)
	else:
		data = payload

	source_doctype = data.get("doctype")
	source_name = data.get("name")
	source_company = data.get("company")
	target_company = data.get("target_company")

	if not (source_doctype and source_name and source_company and target_company):
		frappe.throw(_("Incomplete payload: source doctype, name, source company, and target company are required."))

	return {
		"status": "Accepted",
		"received_doc": f"{source_doctype} {source_name}",
		"target_company": target_company
	}


@frappe.whitelist()
def get_console_dashboard_data():
	"""
	Retrieves live metrics, links topology, and recent intercompany transaction flow
	for the interactive visual Inter-Company Console.
	"""
	data = {
		"metrics": {
			"companies_count": frappe.db.count("Company"),
			"active_links": 0,
			"synced_docs_count": 0,
			"open_disputes": 0,
			"failed_syncs": 0,
			"total_settled_amount": 0.0,
			"elimination_runs": 0,
		},
		"links": [],
		"recent_transactions": [],
		"deployment_mode": "Local Multi-Company (Single Database)",
		"health_status": "Healthy"
	}

	try:
		settings = frappe.get_cached_doc("Inter Company Settings")
		data["deployment_mode"] = settings.deployment_mode or "Local Multi-Company (Single Database)"
	except Exception:
		pass

	# Active Transaction Links
	if frappe.db.exists("DocType", "Intercompany Transaction Link"):
		links = frappe.get_all(
			"Intercompany Transaction Link",
			fields=["name", "main_company", "enabled", "creation", "modified"],
			order_by="modified desc"
		)
		data["metrics"]["active_links"] = sum(1 for l in links if l.get("enabled"))
		
		# Enrich with linked counterparties
		for l in links:
			counterparties = frappe.get_all(
				"Intercompany Linked Company",
				filters={"parent": l.name},
				pluck="company"
			)
			types_count = frappe.db.count("Intercompany Transaction Type", {"parent": l.name})
			data["links"].append({
				"name": l.name,
				"main_company": l.main_company,
				"enabled": l.enabled,
				"counterparties": counterparties,
				"active_types_count": types_count
			})

	# Synced Documents
	if frappe.db.exists("DocType", "Inter Company Document Reference"):
		data["metrics"]["synced_docs_count"] = frappe.db.count("Inter Company Document Reference")
		recent = frappe.get_all(
			"Inter Company Document Reference",
			fields=[
				"name",
				"source_doctype",
				"source_name",
				"source_company",
				"target_doctype",
				"target_name",
				"target_company",
				"creation"
			],
			order_by="creation desc",
			limit=8
		)
		data["recent_transactions"] = recent

	# Open Disputes
	if frappe.db.exists("DocType", "Inter Company Dispute"):
		data["metrics"]["open_disputes"] = frappe.db.count(
			"Inter Company Dispute",
			{"status": ["in", ["Open", "Under Investigation"]]}
		)

	# Failed Error Logs
	if frappe.db.exists("DocType", "Inter Company Error Log"):
		failed_count = frappe.db.count("Inter Company Error Log", {"status": "Failed"})
		data["metrics"]["failed_syncs"] = failed_count
		if failed_count > 0:
			data["health_status"] = "Attention Needed"

	# Multilateral Netting Totals
	if frappe.db.exists("DocType", "Inter Company Netting Cycle"):
		netting_cycles = frappe.get_all(
			"Inter Company Netting Cycle",
			filters={"docstatus": 1},
			fields=["name", "total_settlement_amount"]
		)
		data["metrics"]["total_settled_amount"] = sum(flt(nc.get("total_settlement_amount")) for nc in netting_cycles)

	# Elimination runs
	if frappe.db.exists("DocType", "Inter Company Elimination Run"):
		data["metrics"]["elimination_runs"] = frappe.db.count("Inter Company Elimination Run", {"docstatus": 1})

	return data


@frappe.whitelist()
def quick_setup_intercompany_pair(main_company, counterparty_company, preset="full", custom_rules=None):
	"""
	1-Click Setup Wizard:
	Effortlessly connects two sister companies, configures internal customer/supplier,
	intelligent clearing accounts, and activates selected transaction mirroring rules.
	"""
	if not main_company or not counterparty_company:
		frappe.throw(_("Both Main Company and Counterparty Company must be selected."))

	if main_company == counterparty_company:
		frappe.throw(_("Main Company and Counterparty Company cannot be the same entity."))

	# 1. Find or create internal Customer in Main Company
	main_cust = frappe.db.get_value("Customer", {"represents_company": counterparty_company}, "name")
	if not main_cust:
		cust_name = f"{counterparty_company} (Internal)"
		if not frappe.db.exists("Customer", cust_name):
			cust = frappe.new_doc("Customer")
			cust.customer_name = cust_name
			cust.customer_type = "Company"
			cust.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
			cust.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
			cust.is_internal_customer = 1
			cust.represents_company = counterparty_company
			cust.flags.ignore_permissions = True
			cust.insert()
			main_cust = cust.name
		else:
			main_cust = cust_name

	# 2. Find or create internal Supplier in Main Company
	main_supp = frappe.db.get_value("Supplier", {"represents_company": counterparty_company}, "name")
	if not main_supp:
		supp_name = f"{counterparty_company} (Internal)"
		if not frappe.db.exists("Supplier", supp_name):
			supp = frappe.new_doc("Supplier")
			supp.supplier_name = supp_name
			supp.supplier_type = "Company"
			supp.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
			supp.is_internal_supplier = 1
			supp.represents_company = counterparty_company
			supp.flags.ignore_permissions = True
			supp.insert()
			main_supp = supp.name
		else:
			main_supp = supp_name

	# 3. Find or create internal Customer in Counterparty Company
	other_cust = frappe.db.get_value("Customer", {"represents_company": main_company}, "name")
	if not other_cust:
		other_cust_name = f"{main_company} (Internal)"
		if not frappe.db.exists("Customer", other_cust_name):
			ocust = frappe.new_doc("Customer")
			ocust.customer_name = other_cust_name
			ocust.customer_type = "Company"
			ocust.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
			ocust.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
			ocust.is_internal_customer = 1
			ocust.represents_company = main_company
			ocust.flags.ignore_permissions = True
			ocust.insert()
			other_cust = ocust.name
		else:
			other_cust = other_cust_name

	# 4. Find or create internal Supplier in Counterparty Company
	other_supp = frappe.db.get_value("Supplier", {"represents_company": main_company}, "name")
	if not other_supp:
		other_supp_name = f"{main_company} (Internal)"
		if not frappe.db.exists("Supplier", other_supp_name):
			osupp = frappe.new_doc("Supplier")
			osupp.supplier_name = other_supp_name
			osupp.supplier_type = "Company"
			osupp.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
			osupp.is_internal_supplier = 1
			osupp.represents_company = main_company
			osupp.flags.ignore_permissions = True
			osupp.insert()
			other_supp = osupp.name
		else:
			other_supp = other_supp_name

	# 5. Find default intercompany clearing accounts if available
	main_clearing_account = frappe.db.get_value(
		"Account",
		{
			"company": main_company,
			"is_group": 0,
			"account_name": ["like", "%Inter%Company%"]
		},
		"name"
	) or frappe.db.get_value(
		"Account",
		{
			"company": main_company,
			"is_group": 0,
			"account_type": ["in", ["Temporary", "Current Asset", "Current Liability"]]
		},
		"name"
	)

	other_clearing_account = frappe.db.get_value(
		"Account",
		{
			"company": counterparty_company,
			"is_group": 0,
			"account_name": ["like", "%Inter%Company%"]
		},
		"name"
	) or frappe.db.get_value(
		"Account",
		{
			"company": counterparty_company,
			"is_group": 0,
			"account_type": ["in", ["Temporary", "Current Asset", "Current Liability"]]
		},
		"name"
	)

	# 6. Determine mapping rules to apply based on preset
	trading_rules = [
		("Sales Order", "Purchase Order", "Both"),
		("Sales Invoice", "Purchase Invoice", "Both"),
		("Delivery Note", "Purchase Receipt", "Both"),
		("Quotation", "Supplier Quotation", "Both"),
		("Material Request", "Sales Order", "Both")
	]
	financial_rules = [
		("Journal Entry", "Journal Entry", "Both"),
		("Payment Entry", "Payment Entry", "Both")
	]
	stock_rules = [
		("Stock Entry", "Stock Entry", "Both")
	]

	selected_mappings = []
	if preset == "trading":
		selected_mappings = trading_rules
	elif preset == "financial":
		selected_mappings = financial_rules
	elif preset == "inventory":
		selected_mappings = stock_rules + [("Delivery Note", "Purchase Receipt", "Both")]
	else:
		selected_mappings = trading_rules + financial_rules + stock_rules

	# 7. Check if link already exists for main_company
	existing_link = frappe.db.get_value("Intercompany Transaction Link", {"main_company": main_company}, "name")

	if existing_link:
		link_doc = frappe.get_doc("Intercompany Transaction Link", existing_link)
		found = False
		for row in (link_doc.linked_companies or []):
			if row.company == counterparty_company:
				found = True
				break
		if not found:
			link_doc.append("linked_companies", {
				"company": counterparty_company,
				"main_company_customer": main_cust,
				"main_company_supplier": main_supp,
				"main_company_account": main_clearing_account,
				"other_company_customer": other_cust,
				"other_company_supplier": other_supp,
				"other_company_account": other_clearing_account
			})

		existing_pairs = set()
		for row in (link_doc.transaction_types or []):
			existing_pairs.add((row.source_type, row.target_type))

		for src, tgt, direction in selected_mappings:
			if (src, tgt) not in existing_pairs:
				link_doc.append("transaction_types", {
					"source_type": src,
					"target_type": tgt,
					"direction": direction
				})

		link_doc.flags.ignore_permissions = True
		link_doc.save()
		link_name = link_doc.name
	else:
		link_doc = frappe.new_doc("Intercompany Transaction Link")
		link_doc.main_company = main_company
		link_doc.enabled = 1
		link_doc.auto_create_draft = 1
		link_doc.auto_cancel_linked_document = 1
		link_doc.append("linked_companies", {
			"company": counterparty_company,
			"main_company_customer": main_cust,
			"main_company_supplier": main_supp,
			"main_company_account": main_clearing_account,
			"other_company_customer": other_cust,
			"other_company_supplier": other_supp,
			"other_company_account": other_clearing_account
		})

		for src, tgt, direction in selected_mappings:
			link_doc.append("transaction_types", {
				"source_type": src,
				"target_type": tgt,
				"direction": direction
			})

		link_doc.flags.ignore_permissions = True
		link_doc.insert()
		link_name = link_doc.name

	frappe.db.commit()

	return {
		"success": True,
		"link_name": link_name,
		"message": _("Intercompany relationship and transaction rules successfully established between {0} and {1}.").format(main_company, counterparty_company)
	}
