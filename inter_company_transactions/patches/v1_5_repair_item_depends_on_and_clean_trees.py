# Copyright (c) 2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""
	Patch v1.5 (ICT-scoped):
	Sanitizes only Inter Company Transactions' own Stock Entry custom fields
	without scanning or rewriting core ERPNext DocField, Client Script,
	Workflow, Custom DocPerm tables, or app JSON files.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return

	try:
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_utils import (
			_sanitize_intercompany_stock_entry_custom_fields,
		)

		_sanitize_intercompany_stock_entry_custom_fields(force=True)
	except Exception as e:
		frappe.log_error(f"Notice in v1_5 ICT custom field sanitization: {e!s}", "ICT Patch v1.5")
