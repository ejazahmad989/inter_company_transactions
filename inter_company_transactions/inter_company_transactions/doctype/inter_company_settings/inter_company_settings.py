# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
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
