# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InterCompanySettings(Document):
	pass


def get_intercompany_settings():
	"""Helper to fetch cached Inter Company Settings safely"""
	try:
		return frappe.get_cached_doc("Inter Company Settings")
	except Exception:
		return None
