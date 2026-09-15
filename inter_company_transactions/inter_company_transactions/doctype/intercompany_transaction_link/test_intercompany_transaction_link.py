# Copyright (c) 2024-2026, Inter Company Transactions and Contributors
# See license.txt

import unittest
import frappe
from frappe.utils import flt, nowdate
from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
	calculate_transfer_rate,
	ensure_item_exists,
	get_default_warehouse,
)


class TestIntercompanyTransactionLink(unittest.TestCase):
	"""
	Unit and integration tests for Inter Company Transactions ERPNext app.
	Tests settings, transfer pricing formulas, item synchronization, and link logic.
	"""

	def setUp(self):
		frappe.flags.ignore_permissions = True

	def test_transfer_pricing_source_rate(self):
		"""Verify Source Document Rate rule returns unchanged source price"""
		settings = {
			"default_transfer_pricing_rule": "Source Document Rate",
			"markup_percentage": 20.0,
		}
		item_doc = {"item_code": "TEST-ITEM-001"}
		rate = calculate_transfer_rate(item_doc, 100.0, "Company A", settings)
		self.assertEqual(rate, 100.0)

	def test_transfer_pricing_fallback_without_settings(self):
		"""Verify fallback when settings are not provided"""
		item_doc = {"item_code": "TEST-ITEM-001"}
		rate = calculate_transfer_rate(item_doc, 150.0, "Company A", None)
		self.assertEqual(rate, 150.0)

	def test_settings_single_doctype(self):
		"""Verify Inter Company Settings doctype structure and default values"""
		meta = frappe.get_meta("Inter Company Settings")
		self.assertTrue(meta.issingle)
		self.assertTrue(meta.has_field("enabled"))
		self.assertTrue(meta.has_field("execution_mode"))
		self.assertTrue(meta.has_field("auto_create_missing_items"))
		self.assertTrue(meta.has_field("tax_handling_strategy"))
		self.assertTrue(meta.has_field("default_transfer_pricing_rule"))
		self.assertTrue(meta.has_field("tolerance_amount"))

	def test_reconciliation_report_exists(self):
		"""Verify Inter Company Balance Reconciliation report metadata exists"""
		self.assertTrue(frappe.db.exists("Report", "Inter Company Balance Reconciliation"))

	def test_document_reference_doctype_exists(self):
		"""Verify Inter Company Document Reference tracking doctype exists"""
		meta = frappe.get_meta("Inter Company Document Reference")
		self.assertTrue(meta.has_field("source_doctype"))
		self.assertTrue(meta.has_field("source_name"))
		self.assertTrue(meta.has_field("target_doctype"))
		self.assertTrue(meta.has_field("target_name"))

	def test_item_mapping_doctype_exists(self):
		"""Verify Intercompany Item Mapping doctype metadata exists"""
		meta = frappe.get_meta("Intercompany Item Mapping")
		self.assertTrue(meta.has_field("source_company"))
		self.assertTrue(meta.has_field("target_company"))
		self.assertTrue(meta.has_field("source_item_code"))
		self.assertTrue(meta.has_field("target_item_code"))

	def test_error_log_doctype_exists(self):
		"""Verify Inter Company Error Log doctype metadata exists"""
		meta = frappe.get_meta("Inter Company Error Log")
		self.assertTrue(meta.has_field("source_doctype"))
		self.assertTrue(meta.has_field("source_name"))
		self.assertTrue(meta.has_field("error_message"))
		self.assertTrue(meta.has_field("resolved"))

	def test_populate_default_transaction_types(self):
		"""Verify default transaction types population logic"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			IntercompanyTransactionLink,
		)
		doc = frappe.new_doc("Intercompany Transaction Link")
		doc.main_company = "Test Company 1"
		added = doc.populate_default_transaction_types()
		self.assertGreaterEqual(added, 8)
		type_pairs = [(r.source_type, r.target_type) for r in doc.transaction_types]
		self.assertIn(("Sales Order", "Purchase Order"), type_pairs)
		self.assertIn(("Quotation", "Supplier Quotation"), type_pairs)
		self.assertIn(("Material Request", "Sales Order"), type_pairs)
		self.assertIn(("Delivery Note", "Purchase Receipt"), type_pairs)


