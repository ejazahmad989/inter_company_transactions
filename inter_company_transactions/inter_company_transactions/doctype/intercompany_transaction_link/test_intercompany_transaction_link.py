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

IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Customer",
	"Supplier",
	"Account",
	"Warehouse",
	"Item",
]


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
			return_value="ICT_ACC - MC",
		), patch.object(frappe, "get_doc", side_effect=mock_new_account):
			acc = get_or_create_intercompany_clearing_account("Main Company", "John Company")
			self.assertEqual(acc, "TMP-JC - MC")
			self.assertEqual(len(created_docs), 1)
			self.assertEqual(created_docs[0].account_type, "Bank")
			self.assertEqual(created_docs[0].account_name, "TMP-JC")
			self.assertEqual(created_docs[0].parent_account, "ICT_ACC - MC")

		# Case 3: Auto-creates dedicated ICT_ACC folder under Current Assets when missing
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_parent_clearing_account,
		)
		ict_created = []

		def mock_get_value_ict_folder(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Account" and isinstance(filters, dict):
				if filters.get("account_name") == ["in", ["Current Assets", "Current Asset"]]:
					return "Current Assets - MC"
			return None

		def mock_insert_ict(data):
			doc = frappe._dict(data)
			doc.name = f"{data['account_name']} - MC"
			doc.flags = frappe._dict()
			doc.insert = MagicMock(side_effect=lambda **kw: ict_created.append(doc))
			return doc

		with patch.object(frappe.db, "get_value", side_effect=mock_get_value_ict_folder), patch.object(
			frappe, "get_doc", side_effect=mock_insert_ict
		):
			folder = get_parent_clearing_account("Main Company")
			self.assertEqual(folder, "ICT_ACC - MC")
			self.assertEqual(len(ict_created), 1)
			self.assertEqual(ict_created[0].is_group, 1)
			self.assertEqual(ict_created[0].parent_account, "Current Assets - MC")

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
		from unittest.mock import patch

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

		with patch.object(frappe.db, "exists", return_value=True):
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

		# Strict mode -> must throw on mirrored counterpart when source document is active (docstatus=1)
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
			return_value={"cancellation_authority": "Source Company Only (Strict Control)"},
		), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: (dt == "DocType" and name == "Sales Invoice") or (dt == "Sales Invoice" and name == "SINV-001")
		), patch.object(
			frappe.db, "get_value", return_value=1
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

	def test_validate_locked_mirrored_fields_non_iterable_document(self):
		"""Verify validate_locked_mirrored_fields does not raise TypeError when previous is a non-iterable Document"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_locked_mirrored_fields,
		)

		class NonIterableDoc:
			def __init__(self, data):
				for k, v in data.items():
					setattr(self, k, v)
				self.flags = frappe._dict()

			def get(self, key, default=None):
				return getattr(self, key, default)

		base_data = {
			"doctype": "Purchase Order",
			"name": "PUR-ORD-2026-00011",
			"company": "ABC Company",
			"supplier": "Main Supplier (ABC)",
			"currency": "PKR",
			"conversion_rate": 1.0,
			"is_intercompany": 1,
			"intercompany_target_company": "MAIN",
			"intercompany_linked_doc_doctype": "Sales Order",
			"intercompany_linked_doc_name": "SAL-ORD-2026-00012",
			"intercompany_linked_company": "MAIN",
			"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 1, "rate": 46000, "amount": 46000})],
		}
		prev = NonIterableDoc(base_data)
		doc = NonIterableDoc(base_data)
		with patch.object(frappe.db, "exists", return_value=True):
			# Should pass cleanly with zero TypeError even though `customer`, `party_type`, etc. are absent
			validate_locked_mirrored_fields(doc, previous=prev)

			# Modifying supplier must still trigger locked-field ValidationError cleanly
			bad_doc = NonIterableDoc({**base_data, "supplier": "Another Supplier"})
			with self.assertRaises(frappe.ValidationError):
				validate_locked_mirrored_fields(bad_doc, previous=prev)

	def test_submit_uncalculated_mirrored_drafts_all_transaction_types(self):
		"""Verify mirrored drafts with uncalculated 0 totals/amounts submit cleanly while tampering still throws"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			_precalculate_mirrored_doc_totals,
			validate_locked_mirrored_fields,
		)

		# 1. Journal Entry (e.g. ACC-JV-2026-00036 with total_debit=0, total_credit=0 in DB before Submit)
		je_prev = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-2026-00036",
			"company": "Sister Co",
			"is_intercompany": 1,
			"intercompany_target_company": "MAIN",
			"intercompany_linked_doc_doctype": "Journal Entry",
			"intercompany_linked_doc_name": "ACC-JV-2026-00035",
			"intercompany_linked_company": "MAIN",
			"total_debit": 0.0,
			"total_credit": 0.0,
			"flags": frappe._dict(),
			"accounts": [
				frappe._dict({
					"account": "Debtors - SC",
					"account_currency": "PKR",
					"exchange_rate": 1.0,
					"party_type": "Customer",
					"party": "MAIN (Internal)",
					"debit_in_account_currency": 50000.0,
					"credit_in_account_currency": 0.0,
					"debit": 50000.0,
					"credit": 0.0,
				}),
				frappe._dict({
					"account": "TMP-MAIN - SC",
					"account_currency": "PKR",
					"exchange_rate": 1.0,
					"party_type": None,
					"party": None,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": 50000.0,
					"debit": 0.0,
					"credit": 50000.0,
				}),
			],
		})
		je_submit = frappe._dict({
			**je_prev,
			"total_debit": 50000.0,
			"total_credit": 50000.0,
			"flags": frappe._dict(),
			"accounts": [frappe._dict(r) for r in je_prev["accounts"]],
		})
		with patch.object(frappe.db, "exists", return_value=True):
			validate_locked_mirrored_fields(je_submit, previous=je_prev)

			# Legacy LCV/remote JE where account_currency/exchange_rate/base debit were uncalculated
			je_lcv_prev = frappe._dict({
				**je_prev,
				"accounts": [
					frappe._dict({
						"account": "Expenses - SC",
						"account_currency": None,
						"exchange_rate": 0.0,
						"party_type": None,
						"party": None,
						"debit_in_account_currency": 450.0,
						"credit_in_account_currency": 0.0,
						"debit": 0.0,
						"credit": 0.0,
					}),
					frappe._dict({
						"account": "Creditors - SC",
						"account_currency": None,
						"exchange_rate": 0.0,
						"party_type": "Supplier",
						"party": "MAIN Supplier",
						"debit_in_account_currency": 0.0,
						"credit_in_account_currency": 450.0,
						"debit": 0.0,
						"credit": 0.0,
					}),
				],
			})
			je_lcv_submit = frappe._dict({
				**je_lcv_prev,
				"total_debit": 450.0,
				"total_credit": 450.0,
				"flags": frappe._dict(),
				"accounts": [
					frappe._dict({**je_lcv_prev["accounts"][0], "account_currency": "USD", "exchange_rate": 1.0, "debit": 450.0}),
					frappe._dict({**je_lcv_prev["accounts"][1], "account_currency": "USD", "exchange_rate": 1.0, "credit": 450.0}),
				],
			})
			validate_locked_mirrored_fields(je_lcv_submit, previous=je_lcv_prev)

			# Tampering row debit must still block JE
			je_bad = frappe._dict({
				**je_submit,
				"flags": frappe._dict(),
				"accounts": [
					frappe._dict({**je_submit["accounts"][0], "debit_in_account_currency": 60000.0, "debit": 60000.0}),
					frappe._dict(je_submit["accounts"][1]),
				],
			})
			with self.assertRaises(frappe.ValidationError):
				validate_locked_mirrored_fields(je_bad, previous=je_prev)

			# 2. Item-based vouchers (PO/SO/SI/PI/DN/PR/SQ/Quotation) with DB amount=0
			for dt in ("Purchase Order", "Sales Order", "Purchase Invoice", "Sales Invoice", "Delivery Note", "Purchase Receipt", "Supplier Quotation"):
				prev_item_doc = frappe._dict({
					"doctype": dt,
					"name": f"{dt[:3].upper()}-0001",
					"company": "Sister Co",
					"currency": "PKR",
					"conversion_rate": 1.0,
					"is_intercompany": 1,
					"intercompany_target_company": "MAIN",
					"intercompany_linked_doc_doctype": "Sales Order",
					"intercompany_linked_doc_name": "SRC-0001",
					"intercompany_linked_company": "MAIN",
					"flags": frappe._dict(),
					"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 1.0, "rate": 46000.0, "amount": 0.0})],
				})
				sub_item_doc = frappe._dict({
					**prev_item_doc,
					"flags": frappe._dict(),
					"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 1.0, "rate": 46000.0, "amount": 46000.0})],
				})
				validate_locked_mirrored_fields(sub_item_doc, previous=prev_item_doc)

				# Rate tampering still blocked
				bad_item_doc = frappe._dict({
					**sub_item_doc,
					"flags": frappe._dict(),
					"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 1.0, "rate": 50000.0, "amount": 50000.0})],
				})
				with self.assertRaises(frappe.ValidationError):
					validate_locked_mirrored_fields(bad_item_doc, previous=prev_item_doc)

			# Quotation checks party_name and quotation_to
			q_prev = frappe._dict({
				"doctype": "Quotation",
				"name": "QTN-0001",
				"company": "MAIN",
				"quotation_to": "Customer",
				"party_name": "Sister Co Customer",
				"currency": "PKR",
				"conversion_rate": 1.0,
				"is_intercompany": 1,
				"intercompany_target_company": "Sister Co",
				"intercompany_linked_doc_doctype": "Supplier Quotation",
				"intercompany_linked_doc_name": "SQTN-0001",
				"intercompany_linked_company": "Sister Co",
				"flags": frappe._dict(),
				"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 2.0, "rate": 100.0, "amount": 0.0})],
			})
			q_sub = frappe._dict({
				**q_prev,
				"flags": frappe._dict(),
				"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 2.0, "rate": 100.0, "amount": 200.0})],
			})
			validate_locked_mirrored_fields(q_sub, previous=q_prev)
			with self.assertRaises(frappe.ValidationError):
				validate_locked_mirrored_fields(frappe._dict({**q_sub, "party_name": "Other Customer"}), previous=q_prev)

			# 3. Stock Entry where basic_amount=500 and amount=0 in DB -> amount=500 on submit
			se_prev = frappe._dict({
				"doctype": "Stock Entry",
				"name": "MAT-STE-0002",
				"company": "Sister Co",
				"is_intercompany": 1,
				"intercompany_target_company": "MAIN",
				"intercompany_linked_doc_doctype": "Stock Entry",
				"intercompany_linked_doc_name": "MAT-STE-0001",
				"intercompany_linked_company": "MAIN",
				"flags": frappe._dict(),
				"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 5.0, "basic_rate": 100.0, "basic_amount": 500.0, "amount": 0.0})],
			})
			se_sub = frappe._dict({
				**se_prev,
				"flags": frappe._dict(),
				"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 5.0, "basic_rate": 100.0, "basic_amount": 500.0, "amount": 500.0})],
			})
			validate_locked_mirrored_fields(se_sub, previous=se_prev)
			with self.assertRaises(frappe.ValidationError):
				validate_locked_mirrored_fields(
					frappe._dict({**se_sub, "items": [frappe._dict({**se_sub["items"][0], "basic_rate": 120.0})]}),
					previous=se_prev,
				)

			# 4. Payment Entry with uninitialized source_exchange_rate=0 -> 1.0 on submit
			pe_prev = frappe._dict({
				"doctype": "Payment Entry",
				"name": "ACC-PAY-0002",
				"company": "Sister Co",
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": "MAIN Customer",
				"paid_amount": 1000.0,
				"received_amount": 1000.0,
				"source_exchange_rate": 0.0,
				"target_exchange_rate": 0.0,
				"is_intercompany": 1,
				"intercompany_target_company": "MAIN",
				"intercompany_linked_doc_doctype": "Payment Entry",
				"intercompany_linked_doc_name": "ACC-PAY-0001",
				"intercompany_linked_company": "MAIN",
				"flags": frappe._dict(),
			})
			pe_sub = frappe._dict({**pe_prev, "source_exchange_rate": 1.0, "target_exchange_rate": 1.0, "flags": frappe._dict()})
			validate_locked_mirrored_fields(pe_sub, previous=pe_prev)
			with self.assertRaises(frappe.ValidationError):
				validate_locked_mirrored_fields(frappe._dict({**pe_sub, "paid_amount": 900.0}), previous=pe_prev)

		# 5. Precalculation helper populates totals & amounts cleanly before initial DB insert
		_precalculate_mirrored_doc_totals(je_prev)
		self.assertEqual(je_prev.total_debit, 50000.0)
		self.assertEqual(je_prev.total_credit, 50000.0)

		po_draft = frappe._dict({
			"doctype": "Purchase Order",
			"conversion_rate": 1.0,
			"items": [frappe._dict({"qty": 2.0, "rate": 46000.0, "amount": 0.0, "base_rate": 0.0, "base_amount": 0.0})],
		})
		_precalculate_mirrored_doc_totals(po_draft)
		self.assertEqual(po_draft["items"][0].amount, 92000.0)
		self.assertEqual(po_draft.total, 92000.0)

	def test_orphan_cancellation_allowed_when_source_deleted_or_cancelled(self):
		"""Verify mirrored counterpart can cancel freely when local source doc is deleted or cancelled, while active/remote still block"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			validate_intercompany_cancellation,
		)

		mirrored_je = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-2026-00039",
			"company": "ABC Company",
			"is_intercompany": 1,
			"intercompany_target_company": "MAIN",
			"intercompany_linked_doc_doctype": "Journal Entry",
			"intercompany_linked_doc_name": "ACC-JV-2026-00038",
			"intercompany_linked_company": "MAIN",
			"flags": frappe._dict(),
		})

		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
			return_value={"cancellation_authority": "Source Company Only (Strict Control)"},
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_linked_counterpart_documents",
			return_value=[],
		):
			# 1. Source was deleted -> must NOT raise Source Company Cancellation Authority
			def mock_exists_deleted(dt, name=None, **kwargs):
				if dt == "DocType" and name == "Journal Entry":
					return True
				if dt == "Journal Entry" and name == "ACC-JV-2026-00038":
					return False
				return False

			with patch.object(frappe.db, "exists", side_effect=mock_exists_deleted):
				validate_intercompany_cancellation(mirrored_je)

			# 2. Source exists and is Cancelled (docstatus=2) -> must NOT raise
			def mock_exists_present(dt, name=None, **kwargs):
				if dt == "DocType" and name == "Journal Entry":
					return True
				if dt == "Journal Entry" and name == "ACC-JV-2026-00038":
					return True
				return False

			with patch.object(frappe.db, "exists", side_effect=mock_exists_present), patch.object(
				frappe.db, "get_value", return_value=2
			):
				validate_intercompany_cancellation(mirrored_je)

			# 3. Source exists and is Submitted (docstatus=1) -> MUST throw
			with patch.object(frappe.db, "exists", side_effect=mock_exists_present), patch.object(
				frappe.db, "get_value", return_value=1
			):
				with self.assertRaises(Exception):
					validate_intercompany_cancellation(mirrored_je)

			# 4. Remote reference -> MUST still throw under Strict mode even though local doc doesn't exist
			def mock_exists_remote(dt, name=None, **kwargs):
				if dt == "DocType" and name in ("Journal Entry", "Inter Company Document Reference"):
					return True
				return False

			with patch.object(frappe.db, "exists", side_effect=mock_exists_remote), patch.object(
				frappe.db, "has_column", return_value=True
			), patch.object(frappe.db, "get_value", return_value="ICDR-REM-1"):
				with self.assertRaises(Exception):
					validate_intercompany_cancellation(mirrored_je)

	def test_trash_and_doc_ref_on_trash_unlink_target_markers(self):
		"""Verify deleting source or manually deleting Inter Company Document Reference unlinks target intercompany_linked_doc_* fields"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_document_reference.inter_company_document_reference import (
			InterCompanyDocumentReference,
		)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			cleanup_intercompany_links_on_trash,
		)

		# 1. Source cleanup_intercompany_links_on_trash clears markers on surviving target doc
		src_doc = frappe._dict({"doctype": "Journal Entry", "name": "ACC-JV-2026-00038"})
		set_calls = []

		def mock_sql_dict(query, params=None, pluck=False, as_dict=False, **kwargs):
			if "Inter Company Document Reference" in query:
				return [{
					"name": "ICDR-0099",
					"source_doctype": "Journal Entry",
					"source_name": "ACC-JV-2026-00038",
					"target_doctype": "Journal Entry",
					"target_name": "ACC-JV-2026-00039",
				}]
			return []

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(
			frappe.db, "get_value", return_value="ACC-JV-2026-00038"
		), patch.object(
			frappe.db, "set_value", side_effect=lambda dt, name, vals, **kw: set_calls.append((dt, name, vals))
		), patch.object(
			frappe.db, "sql", side_effect=mock_sql_dict
		), patch.object(frappe, "delete_doc"):
			cleanup_intercompany_links_on_trash(src_doc)
			self.assertEqual(len(set_calls), 1)
			self.assertEqual(set_calls[0][0], "Journal Entry")
			self.assertEqual(set_calls[0][1], "ACC-JV-2026-00039")
			self.assertEqual(set_calls[0][2]["intercompany_linked_doc_name"], "")

		# 2. Manual deletion of Inter Company Document Reference clears markers via on_trash
		ref_doc = InterCompanyDocumentReference.__new__(InterCompanyDocumentReference)
		ref_doc.target_doctype = "Journal Entry"
		ref_doc.target_name = "ACC-JV-2026-00039"
		manual_set_calls = []

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(
			frappe.db, "get_value", return_value="ACC-JV-2026-00038"
		), patch.object(
			frappe.db, "set_value", side_effect=lambda dt, name, vals, **kw: manual_set_calls.append((dt, name, vals))
		):
			ref_doc.on_trash()
			self.assertEqual(len(manual_set_calls), 1)
			self.assertEqual(manual_set_calls[0][1], "ACC-JV-2026-00039")
			self.assertEqual(manual_set_calls[0][2]["intercompany_linked_doc_doctype"], "")

	def test_delete_mirrored_draft_and_unlink_mirrored_document_endpoints(self):
		"""Verify delete_mirrored_draft enforces docstatus=0 + permission and unlink_mirrored_document works on submitted orphans"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			delete_mirrored_draft,
			unlink_mirrored_document,
		)

		draft_je = frappe._dict({"doctype": "Journal Entry", "name": "ACC-JV-DRAFT-1", "docstatus": 0})
		sub_je = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-2026-00039",
			"docstatus": 1,
			"intercompany_linked_doc_doctype": "Journal Entry",
			"intercompany_linked_doc_name": "ACC-JV-2026-00038",
		})

		# 1. delete_mirrored_draft deletes Draft when permitted
		deleted = []
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "has_permission", return_value=True
		), patch.object(frappe, "get_doc", return_value=draft_je), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cleanup_intercompany_links_on_trash"
		), patch.object(
			frappe, "delete_doc", side_effect=lambda dt, name, **kw: deleted.append((dt, name))
		):
			res = delete_mirrored_draft("Journal Entry", "ACC-JV-DRAFT-1")
			self.assertTrue(res["deleted"])
			self.assertIn(("Journal Entry", "ACC-JV-DRAFT-1"), deleted)

		# 2. delete_mirrored_draft rejects Submitted doc
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "has_permission", return_value=True
		), patch.object(frappe, "get_doc", return_value=sub_je):
			with self.assertRaises(Exception):
				delete_mirrored_draft("Journal Entry", "ACC-JV-2026-00039")

		# 3. unlink_mirrored_document unlinks Submitted orphan via cancel permission
		cleared = []

		def mock_unlink_exists(dt, name=None, **kwargs):
			if dt == "Journal Entry" and name == "ACC-JV-2026-00039":
				return True
			if dt == "Journal Entry" and name == "ACC-JV-2026-00038":
				return False
			if dt == "DocType":
				return False
			return False

		def mock_has_perm(dt, ptype="read", doc=None, **kwargs):
			return ptype == "cancel"

		with patch.object(frappe.db, "exists", side_effect=mock_unlink_exists), patch.object(
			frappe, "get_doc", return_value=sub_je
		), patch.object(frappe, "has_permission", side_effect=mock_has_perm), patch.object(
			frappe, "get_roles", return_value=["Accounts User"]
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._clear_mirrored_link_markers",
			side_effect=lambda dt, n: cleared.append((dt, n)),
		):
			res = unlink_mirrored_document("Journal Entry", "ACC-JV-2026-00039")
			self.assertTrue(res["unlinked"])
			self.assertEqual(cleared, [("Journal Entry", "ACC-JV-2026-00039")])

	def test_static_semgrep_and_frappe_api_hygiene(self):
		"""Verify zero SQL format injections, zero subprocess usage, clean repair_site.py, and clean README metadata"""
		import ast
		import re
		from pathlib import Path

		repo_root = Path(__file__).resolve().parents[4]
		py_files = [
			p for p in repo_root.rglob("*.py")
			if ".git" not in p.parts and "node_modules" not in p.parts
		]
		self.assertGreater(len(py_files), 5)

		for py_file in py_files:
			src = py_file.read_text(encoding="utf-8")
			tree = ast.parse(src, filename=str(py_file))

			for node in ast.walk(tree):
				# Forbid subprocess imports anywhere in repository Python files
				if isinstance(node, ast.Import):
					for alias in node.names:
						self.assertNotEqual(
							alias.name,
							"subprocess",
							f"Forbidden subprocess import in {py_file.name}:{node.lineno}",
						)
				elif isinstance(node, ast.ImportFrom):
					self.assertNotEqual(
						node.module,
						"subprocess",
						f"Forbidden subprocess import in {py_file.name}:{node.lineno}",
					)

				if isinstance(node, ast.Call):
					if isinstance(node.func, ast.Name) and node.func.id in ("eval", "compile", "exec"):
						self.fail(f"Forbidden dynamic code evaluation call '{node.func.id}()' in {py_file.name}:{node.lineno}")

				if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
					# 1. Forbid ignore_permissions in frappe.get_all / frappe.db.get_all
					if node.func.attr == "get_all":
						kw_names = [kw.arg for kw in node.keywords]
						self.assertNotIn(
							"ignore_permissions",
							kw_names,
							f"Forbidden ignore_permissions in {py_file.name}:{node.lineno}",
						)

					# 2. Forbid f-string / .format / % formatting in frappe.db.sql
					if node.func.attr == "sql" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "db":
						if node.args:
							q_arg = node.args[0]
							self.assertNotIsInstance(
								q_arg, ast.JoinedStr,
								f"SQL f-string injection risk in {py_file.name}:{node.lineno}",
							)
							if isinstance(q_arg, ast.Call) and isinstance(q_arg.func, ast.Attribute):
								self.assertNotEqual(
									q_arg.func.attr, "format",
									f"SQL .format() injection risk in {py_file.name}:{node.lineno}",
								)
							if isinstance(q_arg, ast.BinOp) and isinstance(q_arg.op, ast.Mod):
								self.fail(f"SQL % formatting injection risk in {py_file.name}:{node.lineno}")

					# 3. Forbid manual frappe.db.commit() in repair_site.py and unannotated commits elsewhere
					if node.func.attr == "commit" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "db":
						if py_file.name == "repair_site.py":
							self.fail(f"Forbidden manual frappe.db.commit() in repair_site.py:{node.lineno}")
						line_text = src.splitlines()[node.lineno - 1]
						self.assertIn(
							"# nosemgrep",
							line_text,
							f"Unannotated frappe.db.commit() in {py_file.name}:{node.lineno}",
						)

		# 4. Ensure README long description has no Marketplace-prohibited bench install/migrate commands
		for readme_path in (repo_root / "README.md", repo_root / "inter_company_transactions" / "README.md"):
			if readme_path.exists():
				readme_text = readme_path.read_text(encoding="utf-8")
				for pattern in (r"bench\s+get-app", r"bench\s+--site\s+\S+\s+install-app", r"bench\s+migrate"):
					self.assertIsNone(
						re.search(pattern, readme_text),
						f"Prohibited install instruction pattern {pattern!r} found in {readme_path}",
					)

	def test_frappe_get_all_real_signature_for_fx_and_links(self):
		"""Enforce real Frappe get_all signature (no ignore_permissions) across Currency Exchange and link queries"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			check_active_downstream_transactions,
			check_intercompany_exchange_rate,
			check_stock_entry_same_currency,
			get_linked_counterpart_documents,
			get_linked_counterpart_for_form,
			lookup_intercompany_exchange_rate,
			validate_intercompany_cross_currency_rate,
			validate_intercompany_document,
		)

		def strict_get_all(doctype, *args, **kwargs):
			if "ignore_permissions" in kwargs:
				raise TypeError("get_list() got multiple values for keyword argument 'ignore_permissions'")
			if doctype == "Currency Exchange":
				flt_dict = kwargs.get("filters") or {}
				if flt_dict.get("from_currency") == "USD" and flt_dict.get("to_currency") == "PKR":
					return [{"exchange_rate": 275.0}]
				return []
			if doctype == "Inter Company Document Reference":
				return []
			if doctype == "Payment Entry Reference":
				return []
			if doctype == "Journal Entry Account":
				return []
			return []

		def mock_get_value(dt, name=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				if name in ("Main PKR Co", "ABC PKR Co"):
					return "PKR"
				return "USD"
			return None

		sales_inv = frappe._dict({
			"doctype": "Sales Invoice",
			"name": "SINV-2026-0009",
			"company": "Main PKR Co",
			"posting_date": "14-11-2026",
			"is_intercompany": 1,
			"intercompany_target_company": "John USD Co",
			"docstatus": 1,
			"flags": frappe._dict(),
		})
		stock_entry = frappe._dict({
			"doctype": "Stock Entry",
			"name": "MAT-STE-2026-0009",
			"company": "Main PKR Co",
			"stock_entry_type": "Material Issue",
			"posting_date": "14-11-2026",
			"is_intercompany": 1,
			"intercompany_target_company": "John USD Co",
			"docstatus": 0,
			"flags": frappe._dict(),
		})

		with patch.object(frappe, "get_all", side_effect=strict_get_all), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt == "DocType" and name in ("Currency Exchange", "Inter Company Document Reference", "Payment Entry Reference", "Journal Entry Account")
		), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			rate = lookup_intercompany_exchange_rate("pkr", "usd", "14-11-2026")
			self.assertAlmostEqual(rate, 1.0 / 275.0, places=7)

			validate_intercompany_cross_currency_rate(sales_inv)

			fx_info = check_intercompany_exchange_rate("Main PKR Co", "John USD Co", "14-11-2026")
			self.assertTrue(fx_info["required"])
			self.assertTrue(fx_info["has_rate"])
			self.assertEqual(fx_info["transaction_date"], "2026-11-14")

			self.assertTrue(check_stock_entry_same_currency("Main PKR Co", "ABC PKR Co")["allowed"])
			se_mismatch = check_stock_entry_same_currency("Main PKR Co", "John USD Co")
			self.assertFalse(se_mismatch["allowed"])
			with self.assertRaises(Exception) as ctx:
				validate_intercompany_document(stock_entry)
			self.assertIn("Same-Currency", str(ctx.exception))

			self.assertEqual(get_linked_counterpart_documents(stock_entry), [])
			self.assertEqual(check_active_downstream_transactions("Sales Invoice", "SINV-1", "Main PKR Co"), [])
			self.assertEqual(get_linked_counterpart_for_form("Stock Entry", "MAT-STE-2026-0009")["counterparts"], [])

	def test_all_14_doctypes_same_and_cross_currency_mirroring(self):
		"""Verify all 14 supported DocTypes mirror accurately under both same-currency (PKR->PKR) and cross-currency (PKR->USD)"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_corresponding_document,
		)

		class FakeTargetDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.items = []
				self.accounts = []
				self.flags = frappe._dict()
				self.company = None
				self.currency = None
				self.conversion_rate = None
				self.price_list_currency = "PKR"
				self.plc_conversion_rate = 1.0

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def get(self, key, default=None):
				return getattr(self, key, default)

			def set_missing_values(self, **kwargs):
				# Simulate ERPNext resetting currency back unless preserved afterwards
				self.currency = "USD" if self.company == "USD Co" else "PKR"
				self.conversion_rate = 1.0

		mapping = frappe._dict({"main_company": "PKR Main Co", "item_mappings": []})
		settings = frappe._dict({"auto_create_missing_items": 1, "default_transfer_pricing_rule": "Source Document Rate"})

		all_pairs = [
			("Sales Order", "Purchase Order"),
			("Purchase Order", "Sales Order"),
			("Sales Invoice", "Purchase Invoice"),
			("Purchase Invoice", "Sales Invoice"),
			("Delivery Note", "Purchase Receipt"),
			("Purchase Receipt", "Delivery Note"),
			("Quotation", "Supplier Quotation"),
			("Supplier Quotation", "Quotation"),
			("Material Request", "Purchase Order"),
			("Material Request", "Sales Order"),
			("Request for Quotation", "Supplier Quotation"),
			("Stock Entry", "Stock Entry"),
			("Journal Entry", "Journal Entry"),
			("Payment Entry", "Payment Entry"),
			("Landed Cost Voucher", "Journal Entry"),
		]

		for mode in ("same_currency", "cross_currency"):
			tgt_company = "PKR Sister Co" if mode == "same_currency" else "USD Co"
			tgt_ccy = "PKR" if mode == "same_currency" else "USD"
			linked_co = frappe._dict({
				"company": tgt_company,
				"main_company_customer": "Sister Cust",
				"main_company_supplier": "Sister Supp",
				"other_company_customer": "Main Cust",
				"other_company_supplier": "Main Supp",
				"other_company_warehouse": "Transit - TGT",
				"other_company_account": "TMP-MAIN - TGT",
			})

			def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
				if dt == "Company" and fieldname == "default_currency":
					return "PKR" if filters == "PKR Main Co" else tgt_ccy
				if dt == "Company" and fieldname == "default_receivable_account":
					return "Debtors - TGT"
				if dt == "Company" and fieldname == "default_payable_account":
					return "Creditors - TGT"
				if dt == "Company" and fieldname == "default_income_account":
					return "Sales - TGT"
				if dt == "Company" and fieldname == "default_expense_account":
					return "Expenses - TGT"
				if dt == "Company" and fieldname == "cost_center":
					return "Main - TGT"
				if dt == "Account" and fieldname == "account_currency":
					return tgt_ccy
				if dt == "Account" and fieldname == "account_type":
					return "Bank"
				if dt == "Warehouse" and fieldname == "name":
					return "Transit - TGT"
				if dt == "Item" and fieldname == ["item_name", "stock_uom", "description"]:
					return frappe._dict({"item_name": "Widget", "stock_uom": "Nos", "description": "Widget"})
				return None

			def mock_get_all(dt, filters=None, **kwargs):
				if dt == "Currency Exchange":
					flt_d = filters or {}
					if flt_d.get("from_currency") == "USD" and flt_d.get("to_currency") == "PKR":
						return [{"exchange_rate": 275.0}]
				return []

			class FakeSourceDoc:
				def __init__(self, data):
					for k, v in data.items():
						setattr(self, k, v)

				def get(self, key, default=None):
					return getattr(self, key, default)

			for src_dt, tgt_dt in all_pairs:
				src_doc = FakeSourceDoc({
					"doctype": src_dt,
					"name": f"SRC-{src_dt[:3].upper()}-001",
					"company": "PKR Main Co",
					"posting_date": "2026-11-15",
					"transaction_date": "2026-11-15",
					"schedule_date": "2026-11-20",
					"delivery_date": "2026-11-20",
					"stock_entry_type": "Material Issue",
					"payment_type": "Pay",
					"paid_amount": 2750.0,
					"received_amount": 2750.0,
					"paid_from_account_currency": "PKR",
					"paid_to_account_currency": "PKR",
					"total_credit": 2750.0,
					"total_debit": 2750.0,
					"total_taxes_and_charges": 2750.0,
					"currency": None if src_dt in ("Material Request", "Request for Quotation", "Stock Entry", "Landed Cost Voucher") else "PKR",
					"conversion_rate": 1.0,
					"items": [
						frappe._dict({
							"item_code": "ITEM-1",
							"item_name": "Widget",
							"qty": 1.0,
							"uom": "Nos",
							"rate": 0.0 if src_dt == "Request for Quotation" else 2750.0,
							"basic_rate": 2750.0,
						})
					],
					"accounts": [
						frappe._dict({
							"party_type": "Supplier",
							"party": "Sister Supp",
							"account_currency": "PKR",
							"exchange_rate": 1.0,
							"debit_in_account_currency": 2750.0,
							"debit": 2750.0,
							"credit_in_account_currency": 0.0,
							"credit": 0.0,
						})
					],
					"taxes": [frappe._dict({"description": "Freight", "amount": 2750.0, "base_amount": 2750.0})],
				})

				mapping_info = {
					"mapping": mapping,
					"linked_company": linked_co,
					"target_doctype": tgt_dt,
				}

				with patch.object(frappe, "new_doc", side_effect=lambda dt: FakeTargetDoc(dt)), patch.object(
					frappe, "get_all", side_effect=mock_get_all
				), patch.object(
					frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Item", "DocType", "Journal Entry Type")
				), patch.object(
					frappe.db, "has_column", return_value=False
				), patch.object(
					frappe.db, "get_value", side_effect=mock_get_value
				):
					if tgt_dt == "Stock Entry" and mode == "cross_currency":
						with self.assertRaises(Exception) as se_ctx:
							create_corresponding_document(src_doc, mapping_info, "main_to_other", settings=settings)
						self.assertIn("Same-Currency", str(se_ctx.exception))
						continue

					res = create_corresponding_document(src_doc, mapping_info, "main_to_other", settings=settings)
					self.assertIsNotNone(res, f"Failed creating counterpart for {src_dt} -> {tgt_dt} ({mode})")
					self.assertEqual(res.company, tgt_company)

					if tgt_dt == "Stock Entry":
						self.assertAlmostEqual(res.items[0].basic_rate, 2750.0, places=2)
					elif tgt_dt == "Journal Entry":
						expected_je_amt = 2750.0 if mode == "same_currency" else 10.0
						total_dr = sum(flt(a.get("debit") if hasattr(a, "get") else getattr(a, "debit", 0)) for a in res.accounts)
						total_cr = sum(flt(a.get("credit") if hasattr(a, "get") else getattr(a, "credit", 0)) for a in res.accounts)
						if total_dr == 0.0:
							total_dr = sum(flt(a.get("debit_in_account_currency") if hasattr(a, "get") else getattr(a, "debit_in_account_currency", 0)) for a in res.accounts)
						if total_cr == 0.0:
							total_cr = sum(flt(a.get("credit_in_account_currency") if hasattr(a, "get") else getattr(a, "credit_in_account_currency", 0)) for a in res.accounts)
						self.assertAlmostEqual(total_dr, expected_je_amt, places=2)
						self.assertAlmostEqual(total_cr, expected_je_amt, places=2)

					elif tgt_dt == "Payment Entry":
						expected_pe_amt = 2750.0 if mode == "same_currency" else 10.0
						self.assertAlmostEqual(res.paid_amount, expected_pe_amt, places=2)
						self.assertAlmostEqual(res.received_amount, expected_pe_amt, places=2)
					elif tgt_dt in ("Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice", "Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation"):
						if mode == "cross_currency":
							# Target doc keeps PKR billing currency with exact 1/275 conversion_rate (0.003636364)
							self.assertEqual(res.currency, "PKR")
							self.assertAlmostEqual(res.conversion_rate, 1.0 / 275.0, places=6)
						else:
							self.assertEqual(res.currency, "PKR")
							self.assertEqual(res.conversion_rate, 1.0)

	def test_remote_sync_all_doctypes_cross_currency(self):
		"""Verify prepare_remote_payload and receive_remote_transaction convert cross-currency amounts across Stock/LCV/JE/PE"""
		from unittest.mock import patch

		from inter_company_transactions.sync import prepare_remote_payload, receive_remote_transaction

		class FakeRemoteDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.name = f"REM-{dt[:3].upper()}-001"
				self.items = []
				self.accounts = []
				self.flags = frappe._dict()
				self.docstatus = 0
				self.company = None
				self.currency = None
				self.conversion_rate = None

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def get(self, key, default=None):
				return getattr(self, key, default)

			def set_missing_values(self, **kwargs):
				pass

			def insert(self, **kwargs):
				return self

		se_src = frappe._dict({
			"doctype": "Stock Entry",
			"name": "MAT-STE-REM-1",
			"company": "Main PKR Co",
			"posting_date": "2026-11-15",
			"stock_entry_type": "Material Issue",
			"items": [frappe._dict({"item_code": "ITEM-1", "qty": 2.0, "basic_rate": 2750.0, "uom": "Nos"})],
		})

		with patch.object(frappe.db, "get_value", return_value="PKR"):
			payload = prepare_remote_payload(se_src, "Remote USD Co")
			self.assertEqual(payload["source_company_currency"], "PKR")
			self.assertEqual(payload["currency"], "PKR")

		created = []

		def make_doc(dt):
			d = FakeRemoteDoc(dt)
			created.append(d)
			return d

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "USD"
			if dt == "Company" and fieldname == "default_expense_account":
				return "Expenses - RUSD"
			if dt == "Company" and fieldname == "default_payable_account":
				return "Creditors - RUSD"
			if dt == "Customer" and fieldname == "name":
				return "Main PKR Co (Internal)"
			if dt == "Account" and fieldname == "name":
				return "TMP-MAIN - RUSD"
			return None

		def mock_get_all(dt, filters=None, **kwargs):
			if dt == "Currency Exchange":
				flt_d = filters or {}
				if flt_d.get("from_currency") == "USD" and flt_d.get("to_currency") == "PKR":
					return [{"exchange_rate": 275.0}]
			return []

		def mock_get_value_same_ccy(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR"
			return mock_get_value(dt, filters=filters, fieldname=fieldname, **kwargs)

		class UnboundProxy:
			def __bool__(self):
				return True

			def __getattr__(self, _name):
				raise RuntimeError("object is not bound")

		with patch.object(frappe, "new_doc", side_effect=make_doc), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		), patch.object(
			frappe, "has_permission", return_value=True
		), patch.object(
			frappe, "get_cached_doc", return_value=frappe._dict({"auto_submit_target_doc": 0})
		), patch.object(
			frappe, "request", UnboundProxy(), create=True
		), patch.object(
			frappe, "get_request_header", side_effect=RuntimeError("object is not bound"), create=True
		), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Company", "Item", "Journal Entry Type", "Warehouse") or (dt == "DocType" and name == "Currency Exchange")
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch(
			"inter_company_transactions.sync.create_remote_document_reference"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_warehouse",
			return_value="Transit - RUSD",
		):
			# 1. Cross-currency remote Stock Entry must be blocked clearly
			with self.assertRaises(Exception) as rem_se_ctx:
				receive_remote_transaction(payload)
			self.assertIn("Same-Currency", str(rem_se_ctx.exception))

			# 2. Cross-currency Landed Cost Voucher -> Journal Entry converts PKR -> USD cleanly
			lcv_payload = {
				"source_doctype": "Landed Cost Voucher",
				"source_name": "LCV-REM-1",
				"source_company": "Main PKR Co",
				"target_company": "Remote USD Co",
				"target_doctype": "Journal Entry",
				"posting_date": "2026-11-15",
				"source_company_currency": "PKR",
				"currency": "PKR",
				"total_taxes_and_charges": 2750.0,
				"taxes": [{"description": "Freight", "amount": 2750.0, "base_amount": 2750.0}],
			}
			lcv_resp = receive_remote_transaction(lcv_payload)
			self.assertTrue(lcv_resp["success"])
			je_created = created[-1]
			self.assertAlmostEqual(sum(flt(a.debit) for a in je_created.accounts), 10.0, places=2)
			self.assertAlmostEqual(sum(flt(a.credit) for a in je_created.accounts), 10.0, places=2)

		# 3. Same-currency remote Stock Entry succeeds cleanly
		with patch.object(frappe, "new_doc", side_effect=make_doc), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		), patch.object(
			frappe, "has_permission", return_value=True
		), patch.object(
			frappe, "get_cached_doc", return_value=frappe._dict({"auto_submit_target_doc": 0})
		), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Company", "Item", "Journal Entry Type", "Warehouse") or (dt == "DocType" and name == "Currency Exchange")
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value_same_ccy
		), patch(
			"inter_company_transactions.sync.create_remote_document_reference"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_warehouse",
			return_value="Transit - RPKR",
		):
			resp = receive_remote_transaction(payload)
			self.assertTrue(resp["success"])
			se_created = created[-1]
			self.assertAlmostEqual(se_created.items[0].basic_rate, 2750.0, places=2)
			self.assertAlmostEqual(se_created.items[0].basic_amount, 5500.0, places=2)

	def test_diagnose_and_heal_workflow_and_safe_eval_conditions(self):
		"""Verify Workflow Transition and Notification Python conditions are auto-healed or flagged clearly"""
		from unittest.mock import patch

		from inter_company_transactions.diagnose_and_heal import (
			find_invalid_safe_eval_expressions,
			repair_database_text,
		)

		store = {
			"Workflow Transition": {
				"WT-1": {"name": "WT-1", "condition": "eval: doc.is_intercompany && !doc.amended_from && true"},
				"WT-BAD": {"name": "WT-BAD", "condition": "show true"},
			},
			"Notification": {
				"NOTIF-1": {"name": "NOTIF-1", "condition": "doc.docstatus == 1 && doc.is_intercompany == true"},
			},
		}

		# Core Frappe/HRMS DocField JS expressions with trailing ';' must NOT emit false-positive warnings
		store["DocField"] = {
			"1tnlldgotp": {"name": "1tnlldgotp", "mandatory_depends_on": "eval:doc.status=='Scheduled';"},
			"t0jj04vopg": {"name": "t0jj04vopg", "mandatory_depends_on": "eval:(doc.report == 'Accounts Receivable');"},
		}

		def mock_get_all(dt, filters=None, or_filters=None, fields=None):
			if dt not in store:
				return []
			rows = []
			for rec in store[dt].values():
				if filters:
					matched = True
					for fk, fv in filters.items():
						val = rec.get(fk) or ""
						if isinstance(fv, list):
							op = fv[0]
							if op == "is" and not val:
								matched = False
								break
							if op == "like" and fv[1].strip("%") not in val:
								matched = False
								break
						elif val != fv:
							matched = False
							break
					if not matched:
						continue
				elif or_filters:
					cond = rec.get("condition") or rec.get("mandatory_depends_on") or ""
					if not any(f[2].strip("%") in cond for f in or_filters):
						continue
				rows.append(frappe._dict(rec))
			return rows

		def mock_set_value(dt, name, col, val, **kwargs):
			store[dt][name][col] = val

		logs = []
		with patch.object(frappe.db, "table_exists", side_effect=lambda dt: dt in store), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(frappe, "get_all", side_effect=mock_get_all), patch.object(
			frappe.db, "set_value", side_effect=mock_set_value
		):
			updates = repair_database_text(logs.append)
			self.assertGreaterEqual(updates, 2)
			self.assertEqual(
				store["Workflow Transition"]["WT-1"]["condition"],
				"doc.is_intercompany and not doc.amended_from and True",
			)
			self.assertEqual(
				store["Notification"]["NOTIF-1"]["condition"],
				"doc.docstatus == 1 and doc.is_intercompany == True",
			)

			invalid = find_invalid_safe_eval_expressions()
			self.assertEqual(len(invalid), 1)
			self.assertEqual(invalid[0]["doctype"], "Workflow Transition")
			self.assertEqual(invalid[0]["name"], "WT-BAD")
			self.assertEqual(invalid[0]["expression"], "show true")
			self.assertTrue(any("WT-BAD" in msg for msg in logs))
			self.assertFalse(any("1tnlldgotp" in msg for msg in logs))
			self.assertFalse(any("t0jj04vopg" in msg for msg in logs))

	def test_sanitize_stock_entry_custom_fields_self_heals(self):
		"""Verify sanitize_intercompany_stock_entry self-heals broken Custom Field & Property Setter eval expressions"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			sanitize_intercompany_stock_entry,
		)

		cf_store = {
			"Stock Entry-intercompany_target_company": {
				"name": "Stock Entry-intercompany_target_company",
				"dt": "Stock Entry",
				"fieldname": "intercompany_target_company",
				"depends_on": "eval:1or(doc.is_intercompany)",
				"mandatory_depends_on": "eval:",
				"read_only_depends_on": "",
				"default": "eval:frappe.db.get_value('Company', doc.company, 'name')",
				"fetch_if_empty": 1,
			}
		}
		ps_store = {
			"Stock Entry-is_intercompany-depends_on": {
				"name": "Stock Entry-is_intercompany-depends_on",
				"doc_type": "Stock Entry",
				"field_name": "is_intercompany",
				"property": "depends_on",
				"value": "eval:doc.purpose ===",
			}
		}

		def mock_get_all(dt, filters=None, fields=None):
			if dt == "Custom Field":
				return [frappe._dict(r) for r in cf_store.values()]
			if dt == "Property Setter":
				return [frappe._dict(r) for r in ps_store.values()]
			return []

		def mock_set_value(dt, name, field_or_dict, val=None, **kwargs):
			if dt == "Custom Field" and name in cf_store:
				if isinstance(field_or_dict, dict):
					cf_store[name].update(field_or_dict)
				else:
					cf_store[name][field_or_dict] = val

		def mock_delete(dt, filters=None, **kwargs):
			if dt == "Property Setter" and isinstance(filters, dict) and filters.get("name") in ps_store:
				ps_store.pop(filters["name"], None)

		frappe.flags.ict_se_cf_sanitized = False
		se_doc = frappe._dict({"doctype": "Stock Entry", "purpose": "Material Issue", "company": "Company A", "items": []})
		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		), patch.object(frappe.db, "set_value", side_effect=mock_set_value), patch.object(
			frappe.db, "delete", side_effect=mock_delete
		):
			sanitize_intercompany_stock_entry(se_doc)
			repaired_cf = cf_store["Stock Entry-intercompany_target_company"]
			self.assertEqual(repaired_cf["depends_on"], "")
			self.assertEqual(repaired_cf["mandatory_depends_on"], "")
			self.assertIsNone(repaired_cf["default"])
			self.assertEqual(repaired_cf["fetch_if_empty"], 0)
			self.assertEqual(ps_store, {})

	def test_precalculate_mirrored_doc_totals_real_document_rows(self):
		"""Verify _precalculate_mirrored_doc_totals works on Frappe Document child rows (no __setitem__)"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			_precalculate_mirrored_doc_totals,
		)

		class NonDictDoc:
			def __init__(self, **kw):
				for k, v in kw.items():
					setattr(self, k, v)

			def get(self, key, default=None):
				return getattr(self, key, default)

		# 1. Stock Entry Detail (non-dict Document object)
		se = NonDictDoc(
			doctype="Stock Entry",
			purpose="Material Receipt",
			total_amount=0.0,
			total_incoming_value=0.0,
			items=[NonDictDoc(qty=3.0, basic_rate=100.0, basic_amount=0.0, amount=0.0, additional_cost=0.0)],
		)
		_precalculate_mirrored_doc_totals(se)
		self.assertEqual(se.items[0].basic_amount, 300.0)
		self.assertEqual(se.items[0].amount, 300.0)
		self.assertEqual(se.total_amount, 300.0)
		self.assertEqual(se.total_incoming_value, 300.0)

		# 2. Journal Entry Account (non-dict Document object)
		je = NonDictDoc(
			doctype="Journal Entry",
			company="ABC Co",
			total_debit=0.0,
			total_credit=0.0,
			accounts=[
				NonDictDoc(
					account="TMP - ABC",
					account_currency="PKR",
					exchange_rate=0.0,
					debit_in_account_currency=500.0,
					credit_in_account_currency=0.0,
					debit=0.0,
					credit=0.0,
				),
				NonDictDoc(
					account="Creditors - ABC",
					account_currency="PKR",
					exchange_rate=0.0,
					debit_in_account_currency=0.0,
					credit_in_account_currency=500.0,
					debit=0.0,
					credit=0.0,
				),
			],
		)
		_precalculate_mirrored_doc_totals(je)
		self.assertEqual(je.accounts[0].debit, 500.0)
		self.assertEqual(je.accounts[1].credit, 500.0)
		self.assertEqual(je.total_debit, 500.0)
		self.assertEqual(je.total_credit, 500.0)

		# 3. Trading DocType Item (non-dict Document object)
		po = NonDictDoc(
			doctype="Purchase Order",
			conversion_rate=2.0,
			total=0.0,
			net_total=0.0,
			grand_total=0.0,
			items=[NonDictDoc(qty=4.0, rate=50.0, amount=0.0, base_rate=0.0, base_amount=0.0)],
		)
		_precalculate_mirrored_doc_totals(po)
		self.assertEqual(po.items[0].amount, 200.0)
		self.assertEqual(po.items[0].base_rate, 100.0)
		self.assertEqual(po.items[0].base_amount, 400.0)
		self.assertEqual(po.grand_total, 200.0)

