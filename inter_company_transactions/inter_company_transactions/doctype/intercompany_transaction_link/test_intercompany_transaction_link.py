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
		self.assertTrue(meta.has_field("source_item_code"))
		self.assertTrue(meta.has_field("target_company"))
		self.assertTrue(meta.has_field("target_item_code"))
		self.assertTrue(meta.has_field("conversion_factor"))

	def test_error_log_doctype_exists(self):
		"""Verify Inter Company Error Log doctype metadata exists"""
		meta = frappe.get_meta("Inter Company Error Log")
		self.assertTrue(meta.has_field("source_doctype"))
		self.assertTrue(meta.has_field("source_name"))
		self.assertTrue(meta.has_field("error_message"))
		self.assertTrue(meta.has_field("status"))
		self.assertTrue(meta.has_field("resolved_by"))

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

	def test_netting_settlement_calculation(self):
		"""Verify multilateral netting algorithm balances debts and credits"""
		cycle = frappe.new_doc("Inter Company Netting Cycle")
		cycle.cycle_name = "Q1 Test Settlement"
		# Set up 3 companies with known balances:
		# Company A: owes B 100, owes C 50 -> Net -150
		# Company B: owed 100 from A, owes C 20 -> Net +80
		# Company C: owed 50 from A, owed 20 from B -> Net +70
		# Netting should reduce 3 transactions into just 2 minimal settlements
		cycle.append("participating_companies", {"company": "Company A", "net_balance": -150})
		cycle.append("participating_companies", {"company": "Company B", "net_balance": 80})
		cycle.append("participating_companies", {"company": "Company C", "net_balance": 70})

		cycle.calculate_netting()
		self.assertGreater(len(cycle.net_settlements), 0)
		total_settled = sum(flt(s.amount) for s in cycle.net_settlements)
		self.assertEqual(total_settled, 150.0)

	def test_dispute_variance_calculation(self):
		"""Verify dispute document automatically calculates variance"""
		from inter_company_transactions.inter_company_transactions.doctype.inter_company_dispute.inter_company_dispute import (
			InterCompanyDispute,
		)
		dispute = frappe.new_doc("Inter Company Dispute")
		dispute.dispute_title = "Pricing discrepancy on Item A"
		dispute.source_amount = 1200.0
		dispute.target_amount = 1500.0
		dispute.validate()
		self.assertEqual(dispute.variance_amount, 300.0)

	def test_enterprise_health_check(self):
		"""Verify enterprise health check telemetry returns valid status"""
		from inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings import (
			get_enterprise_health_check,
		)
		health = get_enterprise_health_check()
		self.assertIn("status", health)
		self.assertIn("recommendations", health)

	def test_multi_currency_resolution_same_currency(self):
		"""Verify currency resolver handles identical currencies seamlessly"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_intercompany_exchange_rate,
			resolve_intercompany_currency_and_rate,
		)
		self.assertEqual(get_intercompany_exchange_rate("USD", "USD"), 1.0)
		self.assertEqual(get_intercompany_exchange_rate("EUR", "EUR"), 1.0)
		self.assertEqual(get_intercompany_exchange_rate(None, "USD"), 1.0)

	def test_multi_currency_rate_factor_safe_fallback(self):
		"""Verify exchange rate resolver provides safe fallbacks when rates are not in DB"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_intercompany_exchange_rate,
		)
		rate = get_intercompany_exchange_rate("USD", "PKR", nowdate())
		self.assertIsInstance(rate, float)
		self.assertGreater(rate, 0)

	def test_party_target_company_resolution(self):
		"""Verify party-to-target-company mapping lookup across multiple sister companies"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			resolve_party_target_company,
		)
		mock_map = {
			"by_company": {
				"Main Holding Corp": {
					"customer": {"Akram Shezad": "Sister Co B", "Rahil Ali": "Sister Co B"},
					"supplier": {"Sister Supplier": "Sister Co B"},
					"all": {"Akram Shezad": "Sister Co B", "Rahil Ali": "Sister Co B"}
				}
			},
			"universal": {
				"customer": {"Akram Shezad": "Sister Co B", "Rahil Ali": "Sister Co B"},
				"supplier": {"Sister Supplier": "Sister Co B"}
			},
			"party_to_company": {
				"Akram Shezad": "Sister Co B",
				"Rahil Ali": "Sister Co B"
			}
		}
		target1 = resolve_party_target_company("Akram Shezad", "customer", "Main Holding Corp", mock_map)
		self.assertEqual(target1, "Sister Co B")

		target2 = resolve_party_target_company("Rahil Ali", "customer", "Main Holding Corp", mock_map)
		self.assertEqual(target2, "Sister Co B")

		# Non-intercompany third party should resolve to None
		target3 = resolve_party_target_company("External Third Party Ltd", "customer", "Main Holding Corp", mock_map)
		self.assertIsNone(target3)

	def test_transaction_type_bidirectional_pairing(self):
		"""Verify transaction type dictionary maps all ERPNext transactions to counterparts"""
		from inter_company_transactions.transaction_mapping import get_reverse_mapping
		reverse_map = get_reverse_mapping()
		self.assertEqual(reverse_map.get("Sales Order"), "Purchase Order")
		self.assertEqual(reverse_map.get("Purchase Order"), "Sales Order")
		self.assertEqual(reverse_map.get("Sales Invoice"), "Purchase Invoice")
		self.assertEqual(reverse_map.get("Purchase Invoice"), "Sales Invoice")
		self.assertEqual(reverse_map.get("Delivery Note"), "Purchase Receipt")
		self.assertEqual(reverse_map.get("Purchase Receipt"), "Delivery Note")
		self.assertEqual(reverse_map.get("Stock Entry"), "Stock Entry")
		self.assertEqual(reverse_map.get("Journal Entry"), "Journal Entry")
		self.assertEqual(reverse_map.get("Payment Entry"), "Payment Entry")
		self.assertEqual(reverse_map.get("Quotation"), "Supplier Quotation")
		self.assertEqual(reverse_map.get("Supplier Quotation"), "Quotation")

	def test_remote_payload_serialization(self):
		"""Verify serialization of local transaction into cross-site federated payload"""
		from inter_company_transactions.sync import prepare_remote_payload
		mock_doc = frappe._dict({
			"doctype": "Sales Invoice",
			"name": "ACC-SINV-2026-00001",
			"company": "Company A",
			"posting_date": "2026-10-13",
			"currency": "USD",
			"conversion_rate": 1.0,
			"grand_total": 5000.0,
			"items": [
				frappe._dict({
					"item_code": "ITEM-101",
					"item_name": "Industrial Valve",
					"qty": 10,
					"rate": 500.0,
					"amount": 5000.0,
					"uom": "Nos"
				})
			]
		})
		payload = prepare_remote_payload(mock_doc, "Company B")
		self.assertEqual(payload["source_doctype"], "Sales Invoice")
		self.assertEqual(payload["source_name"], "ACC-SINV-2026-00001")
		self.assertEqual(payload["target_company"], "Company B")
		self.assertEqual(payload["grand_total"], 5000.0)
		self.assertEqual(len(payload["items"]), 1)
		self.assertEqual(payload["items"][0]["item_code"], "ITEM-101")
		self.assertIn("idempotency_key", payload)

	def test_app_version_and_capabilities_handshake(self):
		"""Verify app handshake endpoint returns version and supported capabilities"""
		from inter_company_transactions.sync import get_app_version_and_capabilities
		resp = get_app_version_and_capabilities()
		self.assertEqual(resp["app"], "inter_company_transactions")
		self.assertIn("federated_multi_site_sync", resp["capabilities"])
		self.assertIn("Sales Invoice", resp["supported_doctypes"])
		self.assertIn("Purchase Invoice", resp["supported_doctypes"])

	def test_network_diagnostics_url_validation(self):
		"""Verify network diagnostic engine detects invalid URLs and formats remedies"""
		from inter_company_transactions.sync import diagnose_remote_site_connectivity
		diag = diagnose_remote_site_connectivity("invalid-domain-without-protocol")
		self.assertEqual(diag["overall_status"], "Failed")
		self.assertIn("URL Format", [s["step"] for s in diag["steps"]])

	def test_sister_company_auto_population(self):
		"""Verify set_sister_company populates sister_company field from child table"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			IntercompanyTransactionLink,
		)
		doc = IntercompanyTransactionLink.__new__(IntercompanyTransactionLink)
		doc.main_company = "AYP MAIN"
		doc.linked_companies = [
			frappe._dict({"company": "AYP SISTER 1"}),
			frappe._dict({"company": "AYP SISTER 2"}),
		]
		doc.set_sister_company()
		self.assertEqual(doc.sister_company, "AYP SISTER 1, AYP SISTER 2")

	def test_sister_company_single_auto_population(self):
		"""Verify single sister company populates exact company name"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			IntercompanyTransactionLink,
		)
		doc = IntercompanyTransactionLink.__new__(IntercompanyTransactionLink)
		doc.main_company = "AYP MAIN"
		doc.linked_companies = [
			frappe._dict({"company": "AYP SISTER"}),
		]
		doc.set_sister_company()
		self.assertEqual(doc.sister_company, "AYP SISTER")

	def test_resolve_intercompany_target_item_mapping(self):
		"""Verify cross-company SKU translation (PEN -> PEN-001) with conversion factor"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			resolve_intercompany_target_item,
		)
		mock_mapping = frappe._dict({
			"item_mappings": [
				frappe._dict({
					"source_item_code": "PEN",
					"target_company": "Company B",
					"target_item_code": "PEN-001",
					"conversion_factor": 10.0,
				})
			]
		})
		source_item = {"item_code": "PEN", "item_name": "Pen Box", "qty": 2, "rate": 50.0, "uom": "Box"}
		res = resolve_intercompany_target_item(source_item, "Company B", mapping=mock_mapping)
		self.assertEqual(res["item_code"], "PEN-001")
		self.assertEqual(res["qty"], 20.0)
		self.assertEqual(res["rate"], 5.0)
		self.assertEqual(res["conversion_factor"], 10.0)

	def test_resolve_intercompany_target_item_fallback(self):
		"""Verify unchanged item code when no custom SKU translation exists"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			resolve_intercompany_target_item,
		)
		source_item = {"item_code": "LAPTOP-01", "item_name": "Laptop", "qty": 1, "rate": 1000.0, "uom": "Nos"}
		res = resolve_intercompany_target_item(source_item, "Company B", mapping=None)
		self.assertEqual(res["item_code"], "LAPTOP-01")
		self.assertEqual(res["qty"], 1.0)
		self.assertEqual(res["rate"], 1000.0)

	def test_validate_intercompany_items_auto_create_disabled(self):
		"""Verify validation throws error when item is unmapped and auto-create is disabled"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_intercompany_items,
		)
		doc = frappe._dict({
			"doctype": "Sales Invoice",
			"items": [frappe._dict({"item_code": "NON-EXISTENT-SKU-999"})],
		})
		mapping = {
			"company": "Company B",
			"mapping": frappe._dict({"item_mappings": []}),
		}
		mock_settings = frappe._dict({"auto_create_missing_items": 0})
		with patch.object(frappe, "get_single", return_value=mock_settings):
			with patch.object(frappe.db, "exists", side_effect=lambda dt, name=None: dt == "DocType" and name == "Inter Company Settings"):
				with self.assertRaises(Exception):
					validate_intercompany_items(doc, mapping)

	def test_clearing_account_helper_exists(self):
		"""Verify get_or_create_intercompany_clearing_account handles none/empty safely"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_or_create_intercompany_clearing_account,
			get_parent_clearing_account,
		)
		# Safe execution with none
		self.assertIsNone(get_parent_clearing_account(None))
		self.assertIsNone(get_or_create_intercompany_clearing_account(None, None))

	def test_resolve_target_doctype_rules(self):
		"""Verify resolve_target_doctype accurately resolves bidirectional rules"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			resolve_target_doctype,
		)
		trans_type = frappe._dict({
			"source_type": "Sales Order",
			"target_type": "Purchase Order",
			"direction": "Both",
		})
		res = resolve_target_doctype("Sales Order", trans_type, "main_to_other")
		self.assertEqual(res, "Purchase Order")

	def test_target_company_cannot_be_source_company(self):
		"""Verify target company cannot be source company in mapping resolution"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			find_applicable_mappings,
		)
		doc = frappe._dict({
			"doctype": "Sales Order",
			"company": "GMP FOODS",
			"intercompany_target_company": "GMP FOODS",
		})
		mappings = find_applicable_mappings(doc)
		for m in mappings:
			self.assertNotEqual(m["company"], "GMP FOODS")

	def test_stock_entry_material_issue_to_receipt_with_zero_rate(self):
		"""Verify Stock Entry Material Issue mirrors to Material Receipt cleanly even without is_intercompany_warehouse column"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_stock_entry,
		)

		source_se = frappe._dict({
			"doctype": "Stock Entry",
			"name": "MAT-STE-2026-0001",
			"company": "Company A",
			"stock_entry_type": "Material Issue",
			"posting_date": "2026-10-13",
			"items": [
				frappe._dict({
					"item_code": "ITEM-ZERO",
					"item_name": "Zero Rate Item",
					"qty": 5,
					"uom": "Nos",
					"basic_rate": 0,
					"valuation_rate": 0,
				}),
				frappe._dict({
					"item_code": "ITEM-VAL",
					"item_name": "Valued Item",
					"qty": 2,
					"uom": "Nos",
					"basic_rate": 75.0,
				}),
			],
		})
		mapping = frappe._dict({"main_company": "Company A", "item_mappings": []})
		linked_company = frappe._dict({
			"company": "Company B",
			"other_company_warehouse": "Transit B - CB",
		})

		class FakeStockEntry:
			def __init__(self):
				self.doctype = "Stock Entry"
				self.items = []
				self.flags = frappe._dict()
				self.from_warehouse = None
				self.to_warehouse = None

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def get(self, key, default=None):
				return getattr(self, key, default)

			def set_missing_values(self, **kwargs):
				pass

		fake_se = FakeStockEntry()

		def mock_get_value(dt=None, filters=None, fieldname=None, doctype=None, **kwargs):
			target_dt = dt or doctype
			if target_dt == "Company" and fieldname == "default_currency":
				return "USD"
			if target_dt == "Item" and fieldname == "valuation_rate":
				return 0
			return None

		def mock_exists(dt, name=None, **kwargs):
			if dt == "Item":
				return True
			return False

		with patch.object(frappe, "new_doc", return_value=fake_se), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe.db, "exists", side_effect=mock_exists
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			res = create_stock_entry(source_se, mapping, linked_company, "main_to_other")
			self.assertEqual(res.stock_entry_type, "Material Receipt")
			self.assertEqual(res.purpose, "Material Receipt")
			self.assertEqual(res.company, "Company B")
			self.assertIsNone(res.from_warehouse)
			self.assertEqual(res.to_warehouse, "Transit B - CB")
			self.assertEqual(len(res.items), 2)
			self.assertEqual(res.items[0].allow_zero_valuation_rate, 1)
			self.assertEqual(res.items[1].basic_rate, 75.0)

	def test_landed_cost_voucher_to_journal_entry(self):
		"""Verify Landed Cost Voucher recharges into a balanced Journal Entry in target company"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_journal_entry_from_lcv,
		)

		source_lcv = frappe._dict({
			"doctype": "Landed Cost Voucher",
			"name": "MAT-LCV-2026-0001",
			"company": "Company A",
			"posting_date": "2026-10-13",
			"total_taxes_and_charges": 450.0,
			"taxes": [frappe._dict({"description": "Ocean Freight", "amount": 450.0})],
		})
		mapping = frappe._dict({"main_company": "Company A"})
		linked_company = frappe._dict({
			"company": "Company B",
			"other_company_supplier": "Company A (Internal)",
			"other_company_account": "IC Clearing B - CB",
		})

		fake_je = frappe._dict({"accounts": []})
		fake_je.doctype = "Journal Entry"
		fake_je.append = lambda tbl, row: fake_je["accounts"].append(frappe._dict(row))
		fake_je.flags = frappe._dict()

		def mock_get_value(doctype, filters=None, fieldname=None, **kwargs):
			if doctype == "Company" and fieldname == "default_currency":
				return "USD"
			if doctype == "Company" and fieldname == "default_expense_account":
				return "Freight Expense - CB"
			if doctype == "Company" and fieldname == "default_payable_account":
				return "Creditors - CB"
			if doctype == "Company" and fieldname == "cost_center":
				return "Main - CB"
			return None

		with patch.object(frappe, "new_doc", return_value=fake_je), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(frappe.db, "get_value", side_effect=mock_get_value):
			res = create_journal_entry_from_lcv(source_lcv, mapping, linked_company, "main_to_other")
			self.assertEqual(res.company, "Company B")
			total_debit = sum(flt(a.debit_in_account_currency) for a in res.accounts)
			total_credit = sum(flt(a.credit_in_account_currency) for a in res.accounts)
			self.assertEqual(total_debit, 450.0)
			self.assertEqual(total_credit, 450.0)
			self.assertIn("MAT-LCV-2026-0001", res.user_remark)

	def test_transfer_pricing_policy_markup(self):
		"""Verify Transfer Pricing Policy Cost-Plus Markup % and Settings Cost + Markup % calculation"""
		from unittest.mock import patch

		mock_policy = frappe._dict({
			"name": "TPP-2026-00001",
			"from_company": "Company A",
			"to_company": "Company B",
			"item_code": "WIDGET-01",
			"methodology": "Cost-Plus Markup %",
			"markup_percentage": 15.0,
			"effective_from": "2020-01-01",
			"effective_to": "2099-12-31",
		})
		item_doc = {"item_code": "WIDGET-01", "item_group": "Products"}

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(frappe, "get_all", return_value=[mock_policy]), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_item_valuation_rate",
			return_value=200.0,
		):
			rate = calculate_transfer_rate(
				item_doc, 200.0, "Company B", None, source_company="Company A", transaction_date="2026-10-13"
			)
			self.assertEqual(rate, 230.0)

		with patch.object(frappe.db, "exists", return_value=False), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_item_valuation_rate",
			return_value=100.0,
		):
			settings = {"default_transfer_pricing_rule": "Cost + Markup %", "markup_percentage": 20.0}
			rate2 = calculate_transfer_rate(item_doc, 100.0, "Company B", settings, source_company="Company A")
			self.assertEqual(rate2, 120.0)

	def test_remote_sync_counterparty_resolution_no_custom_field(self):
		"""Verify remote sync uses standard ERPNext internal party fields and never queries is_inter_company"""
		from unittest.mock import patch

		from inter_company_transactions.sync import resolve_counterparty_for_remote_source

		queried_filters = []

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if isinstance(filters, dict):
				queried_filters.append((dt, dict(filters)))
				if filters.get("represents_company") == "Remote Co A" and filters.get("is_internal_customer") == 1:
					return "Remote Co A (Internal)"
			return None

		with patch.object(frappe.db, "has_column", return_value=True), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			party = resolve_counterparty_for_remote_source("Remote Co A", "Sales Invoice", "Local Co B")
			self.assertEqual(party, "Remote Co A (Internal)")
			for _dt, flt_dict in queried_filters:
				self.assertNotIn("is_inter_company", flt_dict)

	def test_tmp_bank_account_scan_create_and_upgrade(self):
		"""Verify TMP-<ABBR> clearing accounts prefer Bank type and upgrade legacy Temporary accounts"""
		from unittest.mock import MagicMock, patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_or_create_intercompany_clearing_account,
		)

		# Case 1: Legacy Temporary account gets upgraded to Bank
		def mock_get_value_upgrade(dt, filters=None, fieldname=None, as_dict=False, **kwargs):
			if dt == "Company" and fieldname == "abbr":
				return "JC" if filters == "John Company" else "MC"
			if dt == "Account" and isinstance(filters, dict):
				if filters.get("account_type") == ["in", ["Bank", "Cash"]]:
					return None
				if filters.get("account_name") == "TMP-JC":
					return frappe._dict({"name": "TMP-JC - MC", "account_type": "Temporary"})
			return None

		with patch.object(frappe.db, "get_value", side_effect=mock_get_value_upgrade), patch.object(
			frappe.db, "set_value"
		) as mock_set_value:
			acc = get_or_create_intercompany_clearing_account("Main Company", "John Company")
			self.assertEqual(acc, "TMP-JC - MC")
			mock_set_value.assert_called_once_with("Account", "TMP-JC - MC", "account_type", "Bank")

		# Case 2: No existing account -> auto-creates Bank account named TMP-JC
		created_docs = []

		def mock_new_account(data):
			doc = frappe._dict(data)
			doc.name = f"{data['account_name']} - MC"
			doc.flags = frappe._dict()
			doc.insert = MagicMock(side_effect=lambda **kw: created_docs.append(doc))
			return doc

		def mock_get_value_create(dt, filters=None, fieldname=None, as_dict=False, **kwargs):
			if dt == "Company" and fieldname == "abbr":
				return "JC" if filters == "John Company" else "MC"
			return None

		with patch.object(frappe.db, "get_value", side_effect=mock_get_value_create), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_parent_clearing_account",
			return_value="Bank Accounts - MC",
		), patch.object(frappe, "get_doc", side_effect=mock_new_account):
			acc = get_or_create_intercompany_clearing_account("Main Company", "John Company")
			self.assertEqual(acc, "TMP-JC - MC")
			self.assertEqual(len(created_docs), 1)
			self.assertEqual(created_docs[0].account_type, "Bank")
			self.assertEqual(created_docs[0].account_name, "TMP-JC")

	def test_scan_linked_company_defaults_pair_matching(self):
		"""Verify scan_linked_company_defaults auto-populates internal parties and TMP-<ABBR> clearing accounts"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			scan_linked_company_defaults,
		)

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "abbr":
				return "MAIN" if filters == "Main Corp" else "JC"
			return None

		def mock_find_acc(company, sister):
			return f"TMP-{sister[:2].upper()} - {company[:2].upper()}"

		def mock_sql(query, params=None, as_dict=False, **kwargs):
			counterparty, party_dt, _owner = params
			return [frappe._dict({"name": f"{counterparty} ({party_dt})"})]

		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "sql", side_effect=mock_sql
		), patch.object(frappe.db, "get_value", side_effect=mock_get_value), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.find_existing_clearing_account",
			side_effect=mock_find_acc,
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_warehouse",
			side_effect=lambda c: f"Transit - {c}",
		):
			res = scan_linked_company_defaults("Main Corp", "John Co")
			self.assertEqual(res["main_company_customer"], "John Co (Customer)")
			self.assertEqual(res["main_company_supplier"], "John Co (Supplier)")
			self.assertEqual(res["other_company_customer"], "Main Corp (Customer)")
			self.assertEqual(res["other_company_supplier"], "Main Corp (Supplier)")
			self.assertEqual(res["main_suggested_tmp"], "TMP-JC")
			self.assertEqual(res["other_suggested_tmp"], "TMP-MAIN")

	def test_bidirectional_exchange_rate_lookup_and_strict_validation(self):
		"""Verify inverse 1/275 lookup works cleanly and missing cross-currency rate raises error instead of 1.0 fallback"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			lookup_intercompany_exchange_rate,
			validate_intercompany_cross_currency_rate,
		)

		# 1. Inverse rate lookup: only USD -> PKR = 275 exists; PKR -> USD must return ~0.003636364
		def mock_get_all(dt, filters=None, fields=None, **kwargs):
			if dt == "Currency Exchange" and filters.get("from_currency") == "USD" and filters.get("to_currency") == "PKR":
				return [{"exchange_rate": 275.0}]
			return []

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		):
			inv_rate = lookup_intercompany_exchange_rate("PKR", "USD", "2026-11-14")
			self.assertAlmostEqual(inv_rate, 1.0 / 275.0, places=7)

		# 2. Validation throws when PKR company transacts with USD company with no Currency Exchange and no doc rate
		src_doc = frappe._dict({
			"doctype": "Sales Order",
			"name": "SO-001",
			"company": "Main PKR Co",
			"is_intercompany": 1,
			"intercompany_target_company": "John USD Co",
			"currency": "PKR",
			"conversion_rate": 1.0,
			"transaction_date": "2026-11-14",
		})

		def mock_ccy(dt, name, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if name == "Main PKR Co" else "USD"
			return None

		with patch.object(frappe.db, "get_value", side_effect=mock_ccy), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.lookup_intercompany_exchange_rate",
			return_value=None,
		):
			with self.assertRaises(Exception):
				validate_intercompany_cross_currency_rate(src_doc)

		# 3. Validation passes when source document itself specifies conversion_rate = 275 for USD
		src_doc_with_rate = frappe._dict({
			"doctype": "Sales Order",
			"name": "SO-002",
			"company": "Main PKR Co",
			"is_intercompany": 1,
			"intercompany_target_company": "John USD Co",
			"currency": "USD",
			"conversion_rate": 275.0,
			"transaction_date": "2026-11-14",
		})
		with patch.object(frappe.db, "get_value", side_effect=mock_ccy), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.lookup_intercompany_exchange_rate",
			return_value=None,
		):
			validate_intercompany_cross_currency_rate(src_doc_with_rate)

	def test_multi_currency_journal_entry_pkr_usd_parity(self):
		"""Verify 500 USD @ 275 (137,500 PKR) mirrors cleanly into balanced USD and PKR ledgers"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_journal_entry,
		)

		# Case A: Main Co (PKR) debits Supplier 500 USD @ 275 (= 137,500 PKR) -> John Co (USD) gets 500 USD JE
		src_je_pkr = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-2026-0001",
			"company": "Main PKR Co",
			"posting_date": "2026-11-14",
			"total_debit": 137500.0,
			"total_credit": 137500.0,
			"accounts": [
				frappe._dict({
					"party_type": "Supplier",
					"party": "John Co (Internal)",
					"account_currency": "USD",
					"exchange_rate": 275.0,
					"debit_in_account_currency": 500.0,
					"debit": 137500.0,
					"credit_in_account_currency": 0.0,
					"credit": 0.0,
				}),
			],
		})

		mapping = frappe._dict({"main_company": "Main PKR Co"})
		linked_company = frappe._dict({
			"company": "John USD Co",
			"other_company_customer": "Main Co (Internal)",
			"other_company_supplier": "Main Supplier (Internal)",
			"other_company_account": "TMP-MAIN - JC",
		})

		fake_je = frappe._dict({"accounts": []})
		fake_je.doctype = "Journal Entry"
		fake_je.append = lambda tbl, row: fake_je["accounts"].append(frappe._dict(row))
		fake_je.flags = frappe._dict()

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if filters == "Main PKR Co" else "USD"
			if dt == "Company" and fieldname == "default_receivable_account":
				return "Debtors - JC"
			if dt == "Company" and fieldname == "cost_center":
				return "Main - JC"
			if dt == "Account" and fieldname == "account_currency":
				return "USD"
			return None

		with patch.object(frappe, "new_doc", return_value=fake_je), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(frappe.db, "get_value", side_effect=mock_get_value):
			res = create_journal_entry(src_je_pkr, mapping, linked_company, "main_to_other")
			self.assertEqual(res.company, "John USD Co")
			self.assertEqual(len(res.accounts), 2)
			total_debit = sum(flt(r.debit) for r in res.accounts)
			total_credit = sum(flt(r.credit) for r in res.accounts)
			self.assertEqual(total_debit, 500.0)
			self.assertEqual(total_credit, 500.0)
			self.assertEqual(res.accounts[0].party_type, "Customer")
			self.assertEqual(res.accounts[0].credit, 500.0)
			self.assertEqual(res.accounts[1].account, "TMP-MAIN - JC")
			self.assertEqual(res.accounts[1].debit, 500.0)

		# Case B: Same 500 USD @ 275 source JE when Customer MAIN receivable account in John USD Co is PKR-denominated
		fake_je_b = frappe._dict({"accounts": []})
		fake_je_b.doctype = "Journal Entry"
		fake_je_b.append = lambda tbl, row: fake_je_b["accounts"].append(frappe._dict(row))
		fake_je_b.flags = frappe._dict()

		def mock_get_value_pkr_party(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if filters == "Main PKR Co" else "USD"
			if dt == "Company" and fieldname == "default_receivable_account":
				return "Debtors PKR - JC"
			if dt == "Company" and fieldname == "cost_center":
				return "Main - JC"
			if dt == "Account" and fieldname == "account_currency":
				return "PKR" if filters == "Debtors PKR - JC" else "USD"
			return None

		with patch.object(frappe, "new_doc", return_value=fake_je_b), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(frappe.db, "get_value", side_effect=mock_get_value_pkr_party):
			res_b = create_journal_entry(src_je_pkr, mapping, linked_company, "main_to_other")
			self.assertEqual(res_b.accounts[0].account_currency, "PKR")
			self.assertAlmostEqual(res_b.accounts[0].exchange_rate, 1.0 / 275.0, places=7)
			self.assertEqual(res_b.accounts[0].credit_in_account_currency, 137500.0)
			self.assertEqual(res_b.accounts[0].credit, 500.0)
			self.assertEqual(res_b.accounts[1].debit, 500.0)

	def test_draft_save_unblocked_while_submit_guards_missing_fx_rate(self):
		"""Verify Draft save uses native ERPNext UI without blocking, while Submit guards missing cross-currency rate"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_intercompany_document,
		)

		draft_doc = frappe._dict({
			"doctype": "Sales Order",
			"name": "SO-DRAFT-1",
			"company": "Main PKR Co",
			"docstatus": 0,
			"is_intercompany": 1,
			"intercompany_target_company": "John USD Co",
			"currency": "PKR",
			"conversion_rate": 1.0,
			"flags": frappe._dict(),
		})

		def mock_ccy(dt, name, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if name == "Main PKR Co" else "USD"
			return None

		with patch.object(frappe.db, "get_value", side_effect=mock_ccy), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.lookup_intercompany_exchange_rate",
			return_value=None,
		):
			# Draft save must succeed without blocking
			validate_intercompany_document(draft_doc)

			# Submit with missing FX rate must block
			submit_doc = frappe._dict({**draft_doc, "docstatus": 1, "flags": frappe._dict()})
			with self.assertRaises(Exception):
				validate_intercompany_document(submit_doc)

	def test_multi_currency_payment_entry_enforces_bank_tmp_and_parity(self):
		"""Verify Payment Entry replaces invalid Temporary account with Bank TMP account and sets exact FX rates"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_payment_entry,
		)

		src_pe = frappe._dict({
			"doctype": "Payment Entry",
			"name": "ACC-PAY-2026-0001",
			"company": "Main PKR Co",
			"posting_date": "2026-11-14",
			"payment_type": "Pay",
			"paid_amount": 137500.0,
			"received_amount": 500.0,
			"paid_from_account_currency": "PKR",
			"paid_to_account_currency": "USD",
			"source_exchange_rate": 1.0,
			"target_exchange_rate": 275.0,
		})
		mapping = frappe._dict({"main_company": "Main PKR Co"})
		linked_company = frappe._dict({
			"company": "John USD Co",
			"other_company_customer": "Main Co (Internal)",
			"other_company_account": "Legacy Temp - JC",
		})

		fake_pe = frappe._dict({})
		fake_pe.doctype = "Payment Entry"
		fake_pe.flags = frappe._dict()

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Account" and filters == "Legacy Temp - JC" and fieldname == "account_type":
				return "Temporary"
			if dt == "Account" and fieldname == "account_currency":
				return "USD"
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if filters == "Main PKR Co" else "USD"
			if dt == "Company" and fieldname == "default_receivable_account":
				return "Debtors - JC"
			if dt == "Customer" and fieldname == "customer_name":
				return "Main Co (Internal)"
			return None

		with patch.object(frappe, "new_doc", return_value=fake_pe), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_or_create_intercompany_clearing_account",
			return_value="TMP-MAIN - JC",
		):
			res = create_payment_entry(src_pe, mapping, linked_company, "main_to_other")
			self.assertEqual(res.company, "John USD Co")
			self.assertEqual(res.payment_type, "Receive")
			self.assertEqual(res.paid_to, "TMP-MAIN - JC")
			self.assertEqual(res.paid_amount, 500.0)
			self.assertEqual(res.received_amount, 500.0)
			self.assertEqual(res.source_exchange_rate, 1.0)
			self.assertEqual(res.target_exchange_rate, 1.0)

	def test_locked_mirrored_fields_enforced_allows_local_warehouse(self):
		"""Verify mirrored counterpart blocks currency/FX/rate/amount edits but permits local warehouse updates"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_locked_mirrored_fields,
		)

		prev_doc = frappe._dict({
			"doctype": "Purchase Invoice",
			"name": "PINV-001",
			"company": "John USD Co",
			"currency": "USD",
			"conversion_rate": 1.0,
			"supplier": "Main Supplier",
			"is_intercompany": 1,
			"intercompany_target_company": "Main PKR Co",
			"intercompany_linked_doc_doctype": "Sales Invoice",
			"intercompany_linked_doc_name": "SINV-001",
			"intercompany_linked_company": "Main PKR Co",
			"items": [
				frappe._dict({
					"item_code": "WIDGET-01",
					"uom": "Nos",
					"qty": 5.0,
					"rate": 100.0,
					"amount": 500.0,
					"warehouse": "Stores - JC",
					"cost_center": "Main - JC",
				})
			],
		})

		# Safe edit: only warehouse changed -> must pass without exception
		safe_doc = frappe._dict({
			**prev_doc,
			"flags": frappe._dict(),
			"items": [
				frappe._dict({
					"item_code": "WIDGET-01",
					"uom": "Nos",
					"qty": 5.0,
					"rate": 100.0,
					"amount": 500.0,
					"warehouse": "Finished Goods - JC",
					"cost_center": "Sales - JC",
				})
			],
		})
		validate_locked_mirrored_fields(safe_doc, previous=prev_doc)

		# Illegal edit: conversion_rate or item rate tampered -> must throw
		tampered_doc = frappe._dict({
			**prev_doc,
			"conversion_rate": 2.5,
			"flags": frappe._dict(),
			"items": [frappe._dict(prev_doc["items"][0])],
		})
		with self.assertRaises(Exception):
			validate_locked_mirrored_fields(tampered_doc, previous=prev_doc)

	def test_cancellation_authority_strict_vs_bidirectional(self):
		"""Verify Target-side cancellation is blocked under Source Company Only and permitted under Bidirectional"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_intercompany_cancellation,
		)

		target_doc = frappe._dict({
			"doctype": "Purchase Invoice",
			"name": "PINV-001",
			"company": "John USD Co",
			"is_intercompany": 1,
			"intercompany_target_company": "Main PKR Co",
			"intercompany_linked_doc_doctype": "Sales Invoice",
			"intercompany_linked_doc_name": "SINV-001",
			"intercompany_linked_company": "Main PKR Co",
			"flags": frappe._dict(),
		})

		# Strict mode -> must throw on mirrored counterpart
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
			return_value={"cancellation_authority": "Source Company Only (Strict Control)"},
		):
			with self.assertRaises(Exception):
				validate_intercompany_cancellation(target_doc)

		# Bidirectional mode -> allowed to proceed when no downstream blockers exist
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
			return_value={"cancellation_authority": "Bidirectional (Either Side Cancels Both)"},
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_linked_counterpart_documents",
			return_value=[],
		):
			validate_intercompany_cancellation(target_doc)

	def test_cleanup_intercompany_links_on_trash(self):
		"""Verify deleting a voucher purges orphan Inter Company Document Reference & Error Log rows"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			cleanup_intercompany_links_on_trash,
		)

		doc = frappe._dict({"doctype": "Sales Order", "name": "SO-DEL-001"})
		deleted = []

		def mock_sql(query, params=None, pluck=False, **kwargs):
			if "Inter Company Document Reference" in query:
				return ["ICDR-0001"]
			if "Inter Company Error Log" in query:
				return ["ICEL-0001"]
			return []

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "sql", side_effect=mock_sql
		), patch.object(
			frappe, "delete_doc", side_effect=lambda dt, name, **kw: deleted.append((dt, name))
		):
			cleanup_intercompany_links_on_trash(doc)
			self.assertIn(("Inter Company Document Reference", "ICDR-0001"), deleted)
			self.assertIn(("Inter Company Error Log", "ICEL-0001"), deleted)

	def test_glued_depends_on_repair_and_inclusive_company_queries(self):
		"""Verify reference_typeand!in_list sanitizes cleanly and party/account queries do not hide valid company records"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			intercompany_account_query,
			intercompany_party_query,
		)
		from inter_company_transactions.safe_eval_patch import sanitize_for_python

		cleaned = sanitize_for_python(
			"eval:doc.reference_typeand!in_list(doc.reference_type, ['Expense Claim', 'Asset'])"
		)
		self.assertEqual(
			cleaned,
			"doc.reference_type and not in_list(doc.reference_type, ['Expense Claim', 'Asset'])",
		)

		captured_queries = []

		def mock_sql(sql, params=None, **kwargs):
			captured_queries.append(sql)
			return [("Sample Result",)]

		with patch.object(frappe.db, "has_column", return_value=True), patch.object(
			frappe.db, "table_exists", return_value=True
		), patch.object(frappe.db, "sql", side_effect=mock_sql):
			party_rows = intercompany_party_query(
				"Supplier", "", "name", 0, 20, {"company": "John Company", "represents_company": "MAIN"}
			)
			self.assertEqual(party_rows, [("Sample Result",)])
			# Must NOT hard-filter is_internal_supplier = 1 so standard suppliers also appear
			self.assertNotIn("is_internal_supplier` = 1", captured_queries[-1])

			acct_rows = intercompany_account_query(
				"Account", "", "name", 0, 20, {"company": "MAIN"}
			)
			self.assertEqual(acct_rows, [("Sample Result",)])
			# Must show ALL active leaf accounts of the selected company (not only Bank/Cash)
			self.assertNotIn("a.account_type IN ('Bank', 'Cash') AND", captured_queries[-1])


