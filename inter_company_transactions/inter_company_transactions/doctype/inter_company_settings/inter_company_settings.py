# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import json
import urllib.error
import urllib.request

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


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
	frappe.only_for(["System Manager", "Accounts Manager", "Accounts User"])
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
def test_remote_site_connection(site_url: str, api_key: str, api_secret: str):
	"""
	Tests REST API handshake with an external federated ERPNext instance.
	Delegates to diagnose_remote_site_connectivity for deep diagnostic.
	"""
	frappe.only_for(["System Manager", "Accounts Manager"])
	from inter_company_transactions.sync import diagnose_remote_site_connectivity
	return diagnose_remote_site_connectivity(site_url, api_key, api_secret)


@frappe.whitelist()
def diagnose_network_and_firewall(site_url: str, api_key: str | None = None, api_secret: str | None = None):
	"""
	Runs full multi-layer socket, DNS, SSL, and firewall diagnostics.
	"""
	frappe.only_for(["System Manager", "Accounts Manager"])
	from inter_company_transactions.sync import diagnose_remote_site_connectivity
	return diagnose_remote_site_connectivity(site_url, api_key, api_secret)


@frappe.whitelist(allow_guest=False)
def receive_intercompany_webhook(payload: str | dict):
	"""
	Receives cross-site intercompany transaction payloads via REST API/Webhook,
	delegating to idempotent sync receiver.
	"""
	from inter_company_transactions.sync import receive_remote_transaction
	return receive_remote_transaction(payload)


@frappe.whitelist()
def get_console_dashboard_data():
	"""
	Retrieves live metrics, links topology, and recent intercompany transaction flow
	for the interactive visual Inter-Company Console.
	"""
	frappe.only_for(["System Manager", "Accounts Manager", "Accounts User"])
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
		try:
			field_to_sum = "total_net_settled" if frappe.db.has_column("Inter Company Netting Cycle", "total_net_settled") else None
			if field_to_sum:
				netting_cycles = frappe.get_all(
					"Inter Company Netting Cycle",
					filters={"docstatus": 1},
					fields=["name", field_to_sum]
				)
				data["metrics"]["total_settled_amount"] = sum(flt(nc.get(field_to_sum)) for nc in netting_cycles)
			else:
				data["metrics"]["total_settled_amount"] = 0.0
		except Exception:
			data["metrics"]["total_settled_amount"] = 0.0

	# Elimination runs
	if frappe.db.exists("DocType", "Inter Company Elimination Run"):
		data["metrics"]["elimination_runs"] = frappe.db.count("Inter Company Elimination Run", {"docstatus": 1})

	return data


@frappe.whitelist()
def quick_setup_intercompany_pair(
	main_company: str,
	counterparty_company: str,
	preset: str = "full",
	custom_rules: list | dict | str | None = None,
):
	"""
	1-Click Setup Wizard:
	Connects two sister companies, configures compliant clearing accounts,
	transit warehouses (for same-currency pairs), and selected transaction mirroring rules
	without auto-creating or auto-assigning Customer/Supplier records.
	"""
	frappe.only_for(["System Manager", "Accounts Manager"])
	if not main_company or not counterparty_company:
		frappe.throw(_("Both Main Company and Counterparty Company must be selected."))

	if main_company == counterparty_company:
		frappe.throw(_("Main Company and Counterparty Company cannot be the same entity."))

	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
		get_or_create_intercompany_clearing_account,
		get_or_create_intercompany_warehouse,
	)

	# 1. Provision GAAP/IFRS compliant intercompany clearing accounts & same-currency transit warehouses
	main_clearing_account = get_or_create_intercompany_clearing_account(main_company, counterparty_company)
	other_clearing_account = get_or_create_intercompany_clearing_account(counterparty_company, main_company)
	if not main_clearing_account or not other_clearing_account:
		frappe.throw(
			_("Could not configure both TMP clearing accounts for {0} and {1}. Both TMP accounts are required.").format(
				main_company, counterparty_company
			)
		)

	main_currency = frappe.db.get_value("Company", main_company, "default_currency")
	other_currency = frappe.db.get_value("Company", counterparty_company, "default_currency")
	same_currency = not (main_currency and other_currency and main_currency != other_currency)

	main_warehouse = get_or_create_intercompany_warehouse(main_company) if same_currency else None
	other_warehouse = get_or_create_intercompany_warehouse(counterparty_company) if same_currency else None

	# 2. Determine mapping rules to apply based on preset
	trading_rules = [
		("Sales Order", "Purchase Order", "Both"),
		("Purchase Order", "Sales Order", "Both"),
		("Sales Invoice", "Purchase Invoice", "Both"),
		("Purchase Invoice", "Sales Invoice", "Both"),
		("Delivery Note", "Purchase Receipt", "Both"),
		("Purchase Receipt", "Delivery Note", "Both"),
		("Quotation", "Supplier Quotation", "Both"),
		("Supplier Quotation", "Quotation", "Both"),
		("Material Request", "Sales Order", "Both"),
		("Material Request", "Purchase Order", "Both"),
		("Request for Quotation", "Supplier Quotation", "Both"),
	]
	financial_rules = [
		("Journal Entry", "Journal Entry", "Both"),
		("Payment Entry", "Payment Entry", "Both"),
		("Landed Cost Voucher", "Journal Entry", "Both"),
	]
	stock_rules = [
		("Stock Entry", "Stock Entry", "Both")
	]

	if preset == "trading":
		selected_mappings = trading_rules
	elif preset == "financial":
		selected_mappings = financial_rules
	elif preset == "inventory":
		selected_mappings = [*stock_rules, ("Delivery Note", "Purchase Receipt", "Both")]
	else:
		selected_mappings = trading_rules + financial_rules + stock_rules

	# 3. Check if link already exists for main_company
	existing_link = frappe.db.get_value("Intercompany Transaction Link", {"main_company": main_company}, "name")

	if existing_link:
		link_doc = frappe.get_doc("Intercompany Transaction Link", existing_link)
		found = False
		for row in (link_doc.linked_companies or []):
			if row.company == counterparty_company:
				if not row.main_company_account and main_clearing_account:
					row.main_company_account = main_clearing_account
				if not row.other_company_account and other_clearing_account:
					row.other_company_account = other_clearing_account
				if same_currency:
					if not getattr(row, "main_company_warehouse", None) and main_warehouse:
						row.main_company_warehouse = main_warehouse
					if not getattr(row, "other_company_warehouse", None) and other_warehouse:
						row.other_company_warehouse = other_warehouse
				found = True
				break
		if not found:
			link_doc.append("linked_companies", {
				"company": counterparty_company,
				"main_company_account": main_clearing_account,
				"main_company_warehouse": main_warehouse,
				"other_company_account": other_clearing_account,
				"other_company_warehouse": other_warehouse,
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
			"main_company_account": main_clearing_account,
			"main_company_warehouse": main_warehouse,
			"other_company_account": other_clearing_account,
			"other_company_warehouse": other_warehouse,
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

	return {
		"success": True,
		"link_name": link_name,
		"message": _(
			"Intercompany relationship and transaction rules established between {0} and {1}. "
			"Please select the Customer and Supplier manually in Intercompany Transaction Link."
		).format(main_company, counterparty_company),
	}
