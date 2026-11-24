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
	"Customer Group",
	"Supplier",
	"Supplier Group",
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
		"""Verify scan_linked_company_defaults scans clearing accounts/warehouses without auto-filling Customer/Supplier"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			scan_linked_company_defaults,
		)

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "abbr":
				return "MAIN" if filters == "Main Corp" else "JC"
			if dt == "Company" and fieldname == "default_currency":
				return "USD"
			return None

		def mock_find_acc(company, sister):
			return f"TMP-{sister[:2].upper()} - {company[:2].upper()}"

		with patch.object(frappe.db, "get_value", side_effect=mock_get_value), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.find_existing_clearing_account",
			side_effect=mock_find_acc,
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_warehouse",
			side_effect=lambda c: f"Transit - {c}",
		):
			res = scan_linked_company_defaults("Main Corp", "John Co")
			self.assertIsNone(res["main_company_customer"])
			self.assertIsNone(res["main_company_supplier"])
			self.assertIsNone(res["other_company_customer"])
			self.assertIsNone(res["other_company_supplier"])
			self.assertEqual(res["main_company_account"], "TMP-JO - MA")
			self.assertEqual(res["other_company_account"], "TMP-MA - JO")
			self.assertEqual(res["main_company_warehouse"], "Transit - Main Corp")
			self.assertEqual(res["other_company_warehouse"], "Transit - John Co")
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

		# 4. Ensure README and doc files have no Marketplace-prohibited bench install/migrate commands
		for doc_path in (
			repo_root / "README.md",
			repo_root / "inter_company_transactions" / "README.md",
			repo_root / "INSTALLATION.md",
		):
			if doc_path.exists():
				doc_text = doc_path.read_text(encoding="utf-8")
				for pattern in (r"bench\s+get-app", r"bench\s+--site\s+\S+\s+install-app", r"bench\s+migrate"):
					self.assertIsNone(
						re.search(pattern, doc_text),
						f"Prohibited install instruction pattern {pattern!r} found in {doc_path}",
					)

		# 5. Keep all Python modules concise to avoid Marketplace Semgrep timeouts
		ict_pkg_dir = Path(__file__).resolve().parent
		for mod_file in ict_pkg_dir.glob("*.py"):
			if not mod_file.name.startswith("test_"):
				line_count = len(mod_file.read_text(encoding="utf-8").splitlines())
				self.assertLessEqual(
					line_count,
					1000,
					f"{mod_file.name} has {line_count} lines (> 1000); split further to avoid Semgrep timeout",
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
					frappe, "get_system_settings", side_effect=lambda k: "Banker's Rounding" if k == "rounding_method" else None
				), patch.object(
					frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Item", "DocType")
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
						total_dr = sum(flt(a.debit) for a in res.accounts)
						total_cr = sum(flt(a.credit) for a in res.accounts)
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
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Company", "Item", "Warehouse") or (dt == "DocType" and name == "Currency Exchange")
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
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Company", "Item", "Warehouse") or (dt == "DocType" and name == "Currency Exchange")
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

	def test_safe_flt_recovers_when_system_settings_uncached(self):
		"""Verify JE, PE, and FX calculations never zero out if flt(x, precision) encounters uncached System Settings (Frappe v16)"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			_safe_flt,
			create_journal_entry,
			create_payment_entry,
			resolve_intercompany_currency_and_rate,
		)

		def strict_get_system_settings(key):
			raise KeyError(f"Uncached System Settings: {key}")

		class FakeDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.items = []
				self.accounts = []
				self.flags = frappe._dict()
				self.company = None

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def get(self, key, default=None):
				return getattr(self, key, default)

		src_je = frappe._dict({
			"doctype": "Journal Entry",
			"name": "JV-V16-001",
			"company": "EUR Main Co",
			"posting_date": "2026-11-18",
			"total_debit": 2750.0,
			"total_credit": 2750.0,
			"currency": "EUR",
			"accounts": [
				frappe._dict({
					"party_type": "Supplier",
					"party": "Sister Supp",
					"account_currency": "EUR",
					"exchange_rate": 1.0,
					"debit_in_account_currency": 2750.0,
					"debit": 2750.0,
					"credit_in_account_currency": 0.0,
					"credit": 0.0,
				})
			],
		})
		src_pe = frappe._dict({
			"doctype": "Payment Entry",
			"name": "PE-V16-001",
			"company": "EUR Main Co",
			"posting_date": "2026-11-18",
			"payment_type": "Pay",
			"paid_amount": 2750.0,
			"received_amount": 2750.0,
			"paid_from_account_currency": "EUR",
			"paid_to_account_currency": "EUR",
		})
		mapping = frappe._dict({"main_company": "EUR Main Co"})
		linked_co = frappe._dict({
			"company": "EUR Sister Co",
			"other_company_customer": "Main Cust",
			"other_company_supplier": "Main Supp",
			"other_company_account": "TMP-MAIN - EURS",
		})

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "EUR"
			if dt == "Company" and fieldname in ("default_receivable_account", "default_payable_account"):
				return "Control - EURS"
			if dt == "Account" and fieldname == "account_currency":
				return "EUR"
			if dt == "Account" and fieldname == "account_type":
				return "Bank"
			if dt == "Company" and fieldname == "cost_center":
				return "Main - EURS"
			return None

		with patch.object(frappe, "get_system_settings", side_effect=strict_get_system_settings), patch.object(
			frappe, "new_doc", side_effect=lambda dt: FakeDoc(dt)
		), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			self.assertEqual(_safe_flt(2750.0, 2), 2750.0)
			self.assertAlmostEqual(_safe_flt(1.0 / 275.0, 9), 0.003636364, places=9)
			self.assertEqual(_safe_flt(0.0, 2), 0.0)

			je = create_journal_entry(src_je, mapping, linked_co, "main_to_other")
			self.assertAlmostEqual(sum(r.debit for r in je.accounts), 2750.0, places=2)
			self.assertAlmostEqual(sum(r.credit for r in je.accounts), 2750.0, places=2)

			pe = create_payment_entry(src_pe, mapping, linked_co, "main_to_other")
			self.assertAlmostEqual(pe.paid_amount, 2750.0, places=2)
			self.assertAlmostEqual(pe.received_amount, 2750.0, places=2)

			ccy, conv_rate, rate_factor = resolve_intercompany_currency_and_rate(src_je, "EUR Sister Co")
			self.assertEqual(ccy, "EUR")
			self.assertEqual(conv_rate, 1.0)
			self.assertEqual(rate_factor, 1.0)

	def test_cross_currency_warehouse_guard_and_scanner(self):
		"""Verify cross-currency pairs lock/clear transit warehouses in scanner and IntercompanyTransactionLink.validate()"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			IntercompanyTransactionLink,
			get_company_currencies,
			scan_linked_company_defaults,
		)

		currencies = {
			"Main PKR Co": "PKR",
			"Sister PKR Co": "PKR",
			"Sister USD Co": "USD",
		}

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return currencies.get(filters)
			if dt == "Company" and fieldname == "abbr":
				return "CO"
			return None

		# 1. Cross-currency scan omits transit warehouses and reports same_currency=False
		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "sql", return_value=[]
		), patch.object(frappe.db, "get_value", side_effect=mock_get_value), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.find_existing_clearing_account",
			return_value="TMP - CO",
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_warehouse",
			side_effect=lambda c: f"Transit - {c}",
		):
			cross_res = scan_linked_company_defaults("Main PKR Co", "Sister USD Co")
			self.assertFalse(cross_res["same_currency"])
			self.assertEqual(cross_res["main_currency"], "PKR")
			self.assertEqual(cross_res["other_currency"], "USD")
			self.assertIsNone(cross_res["main_company_warehouse"])
			self.assertIsNone(cross_res["other_company_warehouse"])

			same_res = scan_linked_company_defaults("Main PKR Co", "Sister PKR Co")
			self.assertTrue(same_res["same_currency"])
			self.assertEqual(same_res["main_company_warehouse"], "Transit - Main PKR Co")
			self.assertEqual(same_res["other_company_warehouse"], "Transit - Sister PKR Co")

			ccy_map = get_company_currencies(["Main PKR Co", "Sister USD Co"])
			self.assertEqual(ccy_map, {"Main PKR Co": "PKR", "Sister USD Co": "USD"})

		# 2. Server-side validate() clears warehouses on mismatched currency row while keeping same-currency row
		doc = IntercompanyTransactionLink.__new__(IntercompanyTransactionLink)
		doc.main_company = "Main PKR Co"
		doc.sister_company = ""
		doc.linked_companies = [
			frappe._dict({
				"company": "Sister PKR Co",
				"main_company_customer": "Sister PKR (C)",
				"other_company_customer": "Main PKR (C)",
				"main_company_supplier": "Sister PKR (S)",
				"other_company_supplier": "Main PKR (S)",
				"main_company_account": "TMP-SPK - MPK",
				"other_company_account": "TMP-MPK - SPK",
				"main_company_warehouse": "Transit - Main PKR",
				"other_company_warehouse": "Transit - Sister PKR",
			}),
			frappe._dict({
				"company": "Sister USD Co",
				"main_company_customer": "Sister USD (C)",
				"other_company_customer": "Main PKR (C)",
				"main_company_supplier": "Sister USD (S)",
				"other_company_supplier": "Main PKR (S)",
				"main_company_account": "TMP-SUS - MPK",
				"other_company_account": "TMP-MPK - SUS",
				"main_company_warehouse": "Transit - Main PKR",
				"other_company_warehouse": "Transit - Sister USD",
			}),
		]
		doc.transaction_types = []

		with patch.object(frappe.db, "get_value", side_effect=mock_get_value):
			doc.validate()

		self.assertEqual(doc.linked_companies[0].main_company_warehouse, "Transit - Main PKR")
		self.assertEqual(doc.linked_companies[0].other_company_warehouse, "Transit - Sister PKR")
		self.assertIsNone(doc.linked_companies[1].main_company_warehouse)
		self.assertIsNone(doc.linked_companies[1].other_company_warehouse)

	def test_workspace_central_hub_has_card_breaks_and_doctypes(self):
		"""Verify Inter-Company Central Hub workspace links include Card Breaks matching every content card"""
		import json
		from pathlib import Path

		ws_path = (
			Path(__file__).resolve().parents[2] / "workspace" / "inter_company" / "inter_company.json"
		)
		ws = json.loads(ws_path.read_text(encoding="utf-8"))
		blocks = json.loads(ws["content"])

		card_names = [b["data"]["card_name"] for b in blocks if b.get("type") == "card"]
		self.assertEqual(len(card_names), 4)

		links = ws.get("links", [])
		card_breaks = [row for row in links if row.get("type") == "Card Break"]
		self.assertEqual([cb["label"] for cb in card_breaks], card_names)

		# Verify each Card Break link_count matches the following Link rows
		idx = 0
		for cb in card_breaks:
			while idx < len(links) and links[idx] is not cb:
				idx += 1
			idx += 1
			count = 0
			while idx < len(links) and links[idx].get("type") == "Link":
				count += 1
				idx += 1
			self.assertEqual(cb["link_count"], count, f"Mismatch link_count for card {cb['label']}")

		linked_targets = {row.get("link_to") for row in links if row.get("type") == "Link"}
		self.assertIn("Intercompany Transaction Link", linked_targets)
		self.assertIn("Inter Company Settings", linked_targets)
		self.assertIn("Inter Company Document Reference", linked_targets)

	def test_transaction_matrix_report_multi_doctype_columns(self):
		"""Verify Inter Company Transaction Matrix checks actual columns per DocType (no Unknown column 'grand_total')"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.report.inter_company_transaction_matrix.inter_company_transaction_matrix import (
			execute,
		)

		schema_cols = {
			"Sales Invoice": {"name", "grand_total", "total", "posting_date"},
			"Purchase Invoice": {"name", "grand_total", "total", "posting_date"},
			"Stock Entry": {"name", "total_amount", "posting_date"},
			"Journal Entry": {"name", "total_debit", "total_credit", "posting_date"},
			"Payment Entry": {"name", "paid_amount", "posting_date"},
			"Material Request": {"name", "transaction_date"},
		}
		docs = {
			("Sales Invoice", "SINV-1"): {"name": "SINV-1", "grand_total": 1000.0, "posting_date": "2026-11-20"},
			("Purchase Invoice", "PINV-1"): {"name": "PINV-1", "grand_total": 1000.0, "posting_date": "2026-11-20"},
			("Stock Entry", "STE-1"): {"name": "STE-1", "total_amount": 500.0, "posting_date": "2026-11-20"},
			("Stock Entry", "STE-2"): {"name": "STE-2", "total_amount": 500.0, "posting_date": "2026-11-20"},
			("Journal Entry", "JV-1"): {"name": "JV-1", "total_debit": 250.0, "total_credit": 250.0, "posting_date": "2026-11-20"},
			("Journal Entry", "JV-2"): {"name": "JV-2", "total_debit": 250.0, "total_credit": 250.0, "posting_date": "2026-11-20"},
			("Payment Entry", "PE-1"): {"name": "PE-1", "paid_amount": 300.0, "posting_date": "2026-11-20"},
			("Payment Entry", "PE-2"): {"name": "PE-2", "paid_amount": 300.0, "posting_date": "2026-11-20"},
			("Material Request", "MR-1"): {"name": "MR-1", "transaction_date": "2026-11-20"},
		}
		refs = [
			frappe._dict({"name": "R1", "source_doctype": "Sales Invoice", "source_name": "SINV-1", "source_company": "A", "target_doctype": "Purchase Invoice", "target_name": "PINV-1", "target_company": "B", "creation": "2026-11-20"}),
			frappe._dict({"name": "R2", "source_doctype": "Stock Entry", "source_name": "STE-1", "source_name_id": "STE-1", "source_company": "A", "target_doctype": "Stock Entry", "target_name": "STE-2", "target_company": "B", "creation": "2026-11-20"}),
			frappe._dict({"name": "R3", "source_doctype": "Journal Entry", "source_name": "JV-1", "source_company": "A", "target_doctype": "Journal Entry", "target_name": "JV-2", "target_company": "B", "creation": "2026-11-20"}),
			frappe._dict({"name": "R4", "source_doctype": "Payment Entry", "source_name": "PE-1", "source_company": "A", "target_doctype": "Payment Entry", "target_name": "PE-2", "target_company": "B", "creation": "2026-11-20"}),
			frappe._dict({"name": "R5", "source_doctype": "Material Request", "source_name": "MR-1", "source_company": "A", "target_doctype": None, "target_name": None, "target_company": "B", "creation": "2026-11-20"}),
		]

		def strict_get_value(dt, name, fields, as_dict=False, **kwargs):
			valid_cols = schema_cols[dt]
			for f in fields:
				if f not in valid_cols:
					raise AssertionError(f"Unknown column '{f}' queried on DocType '{dt}'")
			return frappe._dict(docs[(dt, name)])

		with patch.object(frappe, "get_all", return_value=refs), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: (dt, name) in docs
		), patch.object(
			frappe.db, "has_column", side_effect=lambda dt, col: col in schema_cols.get(dt, set())
		), patch.object(
			frappe.db, "get_value", side_effect=strict_get_value
		):
			_cols, rows, _msg, _chart, summary = execute({"status": "All"})
			self.assertEqual(len(rows), 5)
			self.assertEqual([r["source_amount"] for r in rows], [1000.0, 500.0, 250.0, 300.0, 0.0])
			self.assertEqual(rows[4]["status"], "Pending Mirror")
			self.assertEqual(summary[0]["value"], 5)

	def test_quick_setup_no_auto_party_creation(self):
		"""Verify quick_setup_intercompany_pair never auto-creates Customers/Suppliers or pre-fills party fields"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings import (
			quick_setup_intercompany_pair,
		)

		created_doctypes = []
		created_links = []

		class FakeLinkDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.name = "Main Co - Sister Co"
				self.main_company = None
				self.linked_companies = []
				self.transaction_types = []
				self.flags = frappe._dict()

			def append(self, table, row):
				getattr(self, table).append(frappe._dict(row))

			def insert(self):
				created_links.append(self)
				return self

		def mock_new_doc(dt):
			created_doctypes.append(dt)
			if dt in ("Customer", "Supplier"):
				raise AssertionError(f"Unexpected auto-creation of {dt}")
			return FakeLinkDoc(dt)

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "USD"
			if dt == "Intercompany Transaction Link":
				return None
			return None

		with patch.object(frappe, "only_for"), patch.object(
			frappe, "new_doc", side_effect=mock_new_doc
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_or_create_intercompany_clearing_account",
			side_effect=lambda owner, other: f"TMP-{other[:3].upper()} - {owner[:2].upper()}",
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_or_create_intercompany_warehouse",
			side_effect=lambda c: f"Transit - {c}",
		):
			resp = quick_setup_intercompany_pair("Main Co", "Sister Co", preset="trading")
			self.assertTrue(resp["success"])
			self.assertNotIn("Customer", created_doctypes)
			self.assertNotIn("Supplier", created_doctypes)
			self.assertEqual(len(created_links), 1)
			row = created_links[0].linked_companies[0]
			self.assertIsNone(row.get("main_company_customer"))
			self.assertIsNone(row.get("main_company_supplier"))
			self.assertIsNone(row.get("other_company_customer"))
			self.assertIsNone(row.get("other_company_supplier"))

	def test_remote_sync_never_auto_creates_parties(self):
		"""Verify resolve_counterparty_for_remote_source raises cleanly when missing instead of creating Customer/Supplier"""
		from unittest.mock import patch

		from inter_company_transactions.sync import resolve_counterparty_for_remote_source

		with patch.object(frappe, "new_doc", side_effect=AssertionError("Must not auto-create party")), patch.object(
			frappe.db, "exists", return_value=False
		), patch.object(
			frappe.db, "get_value", return_value=None
		), patch.object(
			frappe.db, "has_column", return_value=True
		):
			with self.assertRaises(Exception) as ctx:
				resolve_counterparty_for_remote_source("Remote Co", "Purchase Invoice", "Local Co")
			self.assertIn("Supplier", str(ctx.exception))

		# Explicitly configured Intercompany Transaction Link party must resolve directly
		def mock_get_all(dt, filters=None, fields=None, **kwargs):
			if dt == "Intercompany Transaction Link":
				return [frappe._dict({"name": "Local Co - Remote Co", "main_company": "Local Co"})]
			if dt == "Intercompany Linked Company":
				return [frappe._dict({"company": "Remote Co", "main_company_supplier": "Manual Remote Supplier"})]
			return []

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		):
			resolved = resolve_counterparty_for_remote_source("Remote Co", "Purchase Invoice", "Local Co")
			self.assertEqual(resolved, "Manual Remote Supplier")

	def test_journal_entry_never_queries_journal_entry_type_doctype(self):
		"""Ensure v16 does not trigger 'DocType Journal Entry Type not found' across JE, LCV, Netting, and Remote Sync."""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_netting_cycle.inter_company_netting_cycle import (
			InterCompanyNettingCycle,
		)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_journal_entry,
			create_journal_entry_from_lcv,
			create_linked_documents,
		)
		from inter_company_transactions.sync import receive_remote_transaction

		queried_exists = []

		class FakeJEDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.name = "ACC-JV-2026-00001"
				self.accounts = []
				self.flags = frappe._dict()
				self.docstatus = 0
				self.company = None
				self.voucher_type = None
				self.posting_date = None

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def get(self, key, default=None):
				return getattr(self, key, default)

			def insert(self, **kwargs):
				return self

		def strict_exists(dt, name=None, **kw):
			queried_exists.append(dt)
			if dt == "Journal Entry Type":
				raise AssertionError("Must never query non-existent 'Journal Entry Type' DocType")
			if dt in ("Company", "Account"):
				return True
			return False

		def mock_get_value(dt, filters=None, fieldname=None, **kwargs):
			if dt == "Company":
				if fieldname == "default_currency":
					return "PKR"
				if fieldname == "cost_center":
					return "Main - CO"
				if fieldname == "default_payable_account":
					return "Creditors - CO"
				if fieldname == "default_receivable_account":
					return "Debtors - CO"
				if fieldname == "default_expense_account":
					return "Expenses - CO"
				if fieldname == "default_bank_account":
					return "Bank - CO"
			if dt == "Account":
				if fieldname == "account_currency":
					return "PKR"
				return "TMP-CO - CO"
			return None

		mapping = frappe._dict({"main_company": "Main Co"})
		linked_co = frappe._dict({
			"company": "Sister Co",
			"main_company_customer": "Sister Cust",
			"main_company_supplier": "Sister Supp",
			"other_company_customer": "Main Cust",
			"other_company_supplier": "Main Supp",
			"main_company_account": "TMP-SIS - MC",
			"other_company_account": "TMP-MAIN - SC",
		})
		src_je = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-SRC-001",
			"company": "Main Co",
			"posting_date": "2026-11-22",
			"is_intercompany": 1,
			"intercompany_target_company": "Sister Co",
			"total_debit": 1500.0,
			"total_credit": 1500.0,
			"accounts": [
				frappe._dict({
					"party_type": "Supplier",
					"party": "Sister Supp",
					"account_currency": "PKR",
					"exchange_rate": 1.0,
					"credit_in_account_currency": 1500.0,
					"credit": 1500.0,
					"debit_in_account_currency": 0.0,
					"debit": 0.0,
				})
			],
		})
		src_lcv = frappe._dict({
			"doctype": "Landed Cost Voucher",
			"name": "MAT-LCV-001",
			"company": "Main Co",
			"posting_date": "2026-11-22",
			"total_taxes_and_charges": 500.0,
			"taxes": [frappe._dict({"description": "Freight", "amount": 500.0, "base_amount": 500.0})],
		})

		messages = []

		with patch.object(frappe, "new_doc", side_effect=lambda dt: FakeJEDoc(dt)), patch.object(
			frappe.db, "exists", side_effect=strict_exists
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch.object(
			frappe, "has_permission", return_value=True
		), patch.object(
			frappe, "get_cached_doc", return_value=frappe._dict({"auto_submit_target_doc": 0})
		), patch.object(
			frappe, "msgprint", side_effect=lambda msg, **kw: messages.append(str(msg))
		), patch.object(
			frappe, "request", None, create=True
		):
			je = create_journal_entry(src_je, mapping, linked_co, "main_to_other")
			self.assertEqual(je.voucher_type, "Journal Entry")

			lcv_je = create_journal_entry_from_lcv(src_lcv, mapping, linked_co, "main_to_other")
			self.assertEqual(lcv_je.voucher_type, "Journal Entry")

			rem_resp = receive_remote_transaction({
				"source_doctype": "Journal Entry",
				"source_name": "REM-JV-001",
				"source_company": "Main Co",
				"target_company": "Sister Co",
				"posting_date": "2026-11-22",
				"source_company_currency": "PKR",
				"currency": "PKR",
				"accounts": [
					{
						"account_currency": "PKR",
						"exchange_rate": 1.0,
						"debit_in_account_currency": 1500.0,
						"credit_in_account_currency": 0.0,
						"debit": 1500.0,
						"credit": 0.0,
					}
				],
			})
			self.assertTrue(rem_resp["success"])

		# Verify Netting Cycle also sets voucher_type='Journal Entry' without querying Journal Entry Type
		netting = frappe._dict({
			"name": "NET-2026-001",
			"settlement_date": "2026-11-22",
			"participating_companies": [
				frappe._dict({"company": "Main Co", "gross_receivables": 0.0, "gross_payables": 100.0}),
				frappe._dict({"company": "Sister Co", "gross_receivables": 100.0, "gross_payables": 0.0}),
			],
			"invoices": [],
			"net_settlements": [],
			"append": lambda tbl, row: netting[tbl].append(frappe._dict(row)),
			"db_set": lambda *a, **kw: None,
		})
		for s_row_attr in ("total_gross_payables", "total_gross_receivables", "total_net_settled", "status"):
			netting[s_row_attr] = None

		created_netting_jes = []

		class FakeNettingJE(FakeJEDoc):
			def db_set(self, *a, **kw):
				return None

			def insert(self, **kwargs):
				created_netting_jes.append(self)
				return self

			def submit(self):
				self.docstatus = 1
				return self

		with patch.object(frappe, "new_doc", side_effect=lambda dt: FakeNettingJE(dt)), patch.object(
			frappe, "get_cached_value", return_value="PKR"
		), patch.object(
			frappe.db, "exists", side_effect=strict_exists
		), patch.object(
			frappe, "get_value", side_effect=lambda dt, flt_or_name, fieldname=None, **kw: mock_get_value(dt, flt_or_name, fieldname)
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_or_create_intercompany_clearing_account",
			return_value="TMP-SIS - MC",
		), patch.object(
			frappe, "msgprint", side_effect=lambda msg, **kw: messages.append(str(msg))
		):
			# Bind db_set on settlement row after _compute_netting populates it
			orig_append = netting["append"]

			def append_with_db_set(tbl, row):
				d = frappe._dict(row)
				d.db_set = lambda *a, **kw: None
				netting[tbl].append(d)

			netting["append"] = append_with_db_set
			InterCompanyNettingCycle.on_submit(netting)
			self.assertEqual(len(created_netting_jes), 1)
			self.assertEqual(created_netting_jes[0].voucher_type, "Journal Entry")

		# Verify create_linked_documents produces the exact clean Journal Entry creation msgprint
		messages.clear()
		lifecycle_mapping = [{
			"mapping": frappe._dict({"main_company": "Main Co", "auto_create_draft": 1}),
			"linked_company": linked_co,
			"company": "Sister Co",
			"direction": "main_to_other",
			"target_doctype": "Journal Entry",
		}]
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.find_applicable_mappings",
			return_value=lifecycle_mapping,
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_intercompany_cross_currency_rate"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_required_parties"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_intercompany_items"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.create_document_reference"
		), patch.object(
			frappe, "new_doc", side_effect=lambda dt: FakeJEDoc(dt)
		), patch.object(
			frappe.db, "exists", side_effect=strict_exists
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch.object(
			frappe, "msgprint", side_effect=lambda msg, **kw: messages.append(str(msg))
		):
			create_linked_documents(src_je)
			self.assertEqual(messages, ["Created draft Journal Entry ACC-JV-2026-00001 in company Sister Co"])

		self.assertNotIn("Journal Entry Type", queried_exists)

	def test_mirrored_journal_entry_save_tolerates_target_company_clear_and_keeps_ledger_locks(self):
		"""Verify mirrored JE & PO/PI drafts allow Save/Submit if intercompany_target_company is cleared/drifted while enforcing financial locks"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_accounting_builders import (
			_precalculate_mirrored_doc_totals,
		)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation import (
			validate_intercompany_document,
			validate_locked_mirrored_fields,
		)

		prev_je = frappe._dict({
			"doctype": "Journal Entry",
			"name": "ACC-JV-2026-00001",
			"company": "Sister Co",
			"is_intercompany": 1,
			"intercompany_target_company": "AYP GROUP",
			"intercompany_linked_doc_doctype": "Journal Entry",
			"intercompany_linked_doc_name": "ACC-JV-2026-00000",
			"intercompany_linked_company": "AYP GROUP",
			"total_debit": 1000.0,
			"total_credit": 1000.0,
			"accounts": [
				frappe._dict({
					"account": "Debtors - SC",
					"account_currency": "PKR",
					"exchange_rate": 1.0,
					"party_type": "Customer",
					"party": "AYP GROUP",
					"debit_in_account_currency": 1000.0,
					"credit_in_account_currency": 0.0,
					"debit": 1000.0,
					"credit": 0.0,
					"cost_center": "Main - SC",
				}),
				frappe._dict({
					"account": "Intercompany Clearing - SC",
					"account_currency": "PKR",
					"exchange_rate": 1.0,
					"party_type": None,
					"party": None,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": 1000.0,
					"debit": 0.0,
					"credit": 1000.0,
					"cost_center": "Main - SC",
				}),
			],
		})

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_doc", return_value=prev_je
		):
			# Case 1: intercompany_target_company cleared on client + editable account/cost_center changed -> must pass & restore
			edited_je = frappe._dict({
				**prev_je,
				"intercompany_target_company": "",
				"flags": frappe._dict(),
				"accounts": [
					frappe._dict({**prev_je.accounts[0], "cost_center": "Branch - SC"}),
					frappe._dict({**prev_je.accounts[1], "account": "Suspense - SC"}),
				],
			})
			validate_intercompany_document(edited_je)
			self.assertEqual(edited_je.intercompany_target_company, "AYP GROUP")

			# Case 2: Mirrored Purchase Invoice with cleared target company -> must pass & restore
			prev_pi = frappe._dict({
				"doctype": "Purchase Invoice",
				"name": "ACC-PINV-2026-00001",
				"company": "Sister Co",
				"currency": "PKR",
				"conversion_rate": 1.0,
				"supplier": "AYP GROUP",
				"is_intercompany": 1,
				"intercompany_target_company": "AYP GROUP",
				"intercompany_linked_doc_doctype": "Sales Invoice",
				"intercompany_linked_doc_name": "ACC-SINV-2026-00001",
				"intercompany_linked_company": "AYP GROUP",
				"items": [frappe._dict({"item_code": "ITEM-1", "uom": "Nos", "qty": 1.0, "rate": 500.0, "amount": 500.0})],
			})
			edited_pi = frappe._dict({
				**prev_pi,
				"intercompany_target_company": None,
				"flags": frappe._dict(),
				"items": [frappe._dict(prev_pi["items"][0])],
			})
			validate_locked_mirrored_fields(edited_pi, previous=prev_pi)
			self.assertEqual(edited_pi.intercompany_target_company, "AYP GROUP")

			# Case 3: Tampering with JE debit amount or party must still raise
			tampered_je = frappe._dict({
				**prev_je,
				"flags": frappe._dict(),
				"accounts": [
					frappe._dict({**prev_je.accounts[0], "debit_in_account_currency": 999.0, "debit": 999.0}),
					frappe._dict(prev_je.accounts[1]),
				],
			})
			with self.assertRaises(Exception):
				validate_locked_mirrored_fields(tampered_je, previous=prev_je)

		# Case 4: _precalculate_mirrored_doc_totals invokes derived JE helpers & sets difference
		called_helpers = []

		class DerivedHelperJE(frappe._dict):
			def set_amounts_in_company_currency(self):
				called_helpers.append("set_amounts_in_company_currency")

			def set_total_debit_credit(self):
				called_helpers.append("set_total_debit_credit")

			def set_against_account(self):
				called_helpers.append("set_against_account")

			def set_print_format_fields(self):
				called_helpers.append("set_print_format_fields")

			def set_title(self):
				called_helpers.append("set_title")

		helper_je = DerivedHelperJE({
			"doctype": "Journal Entry",
			"company": "Sister Co",
			"total_debit": 0.0,
			"total_credit": 0.0,
			"difference": None,
			"accounts": [
				frappe._dict({"account": "Debtors - SC", "account_currency": "PKR", "exchange_rate": 1.0, "debit_in_account_currency": 250.0, "credit_in_account_currency": 0.0, "debit": 250.0, "credit": 0.0}),
				frappe._dict({"account": "Clearing - SC", "account_currency": "PKR", "exchange_rate": 1.0, "debit_in_account_currency": 0.0, "credit_in_account_currency": 250.0, "debit": 0.0, "credit": 250.0}),
			],
		})
		with patch.object(frappe.db, "get_value", return_value="PKR"):
			_precalculate_mirrored_doc_totals(helper_je)
		self.assertEqual(
			called_helpers,
			[
				"set_amounts_in_company_currency",
				"set_total_debit_credit",
				"set_against_account",
				"set_print_format_fields",
				"set_title",
			],
		)
		self.assertEqual(helper_je.total_debit, 250.0)
		self.assertEqual(helper_je.total_credit, 250.0)
		self.assertEqual(helper_je.difference, 0.0)

	def test_link_symmetric_party_and_both_tmp_accounts_validation(self):
		"""Verify Link requires both TMP accounts and symmetric Customer/Supplier pairing without auto-creating parties"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			IntercompanyTransactionLink,
		)

		def make_link(row_data):
			doc = IntercompanyTransactionLink.__new__(IntercompanyTransactionLink)
			doc.main_company = "Main Co"
			doc.sister_company = "ABC Co"
			doc.linked_companies = [frappe._dict({"company": "ABC Co", **row_data})]
			doc.transaction_types = []
			return doc

		# 1. Missing either TMP clearing account -> must throw
		for bad_accounts in (
			{"main_company_account": "", "other_company_account": "TMP-MA - ABC"},
			{"main_company_account": "TMP-AB - MC", "other_company_account": ""},
			{"main_company_account": None, "other_company_account": None},
		):
			with self.assertRaises(Exception) as ctx:
				make_link(bad_accounts).validate_parties()
			self.assertIn("TMP", str(ctx.exception))

		# 2. One-sided Customer without counterpart Customer -> must throw
		with self.assertRaises(Exception) as ctx:
			make_link({
				"main_company_account": "TMP-AB - MC",
				"other_company_account": "TMP-MC - AB",
				"main_company_customer": "ABC Customer",
				"other_company_customer": None,
			}).validate_parties()
		self.assertIn("Other Company Customer", str(ctx.exception))

		with self.assertRaises(Exception) as ctx:
			make_link({
				"main_company_account": "TMP-AB - MC",
				"other_company_account": "TMP-MC - AB",
				"main_company_customer": None,
				"other_company_customer": "Main Customer",
			}).validate_parties()
		self.assertIn("Main Company Customer", str(ctx.exception))

		# 3. One-sided Supplier without counterpart Supplier -> must throw
		with self.assertRaises(Exception) as ctx:
			make_link({
				"main_company_account": "TMP-AB - MC",
				"other_company_account": "TMP-MC - AB",
				"main_company_supplier": "ABC Supplier",
				"other_company_supplier": None,
			}).validate_parties()
		self.assertIn("Other Company Supplier", str(ctx.exception))

		with self.assertRaises(Exception) as ctx:
			make_link({
				"main_company_account": "TMP-AB - MC",
				"other_company_account": "TMP-MC - AB",
				"main_company_supplier": None,
				"other_company_supplier": "Main Supplier",
			}).validate_parties()
		self.assertIn("Main Company Supplier", str(ctx.exception))

		# 4. Valid states: both TMP accounts with no parties (post-wizard), paired Customers, or all 4 parties
		make_link({"main_company_account": "TMP-AB - MC", "other_company_account": "TMP-MC - AB"}).validate_parties()
		make_link({
			"main_company_account": "TMP-AB - MC",
			"other_company_account": "TMP-MC - AB",
			"main_company_customer": "ABC Customer",
			"other_company_customer": "Main Customer",
		}).validate_parties()
		with patch.object(frappe.db, "get_value", return_value="PKR"):
			doc_full = make_link({
				"main_company_account": "TMP-AB - MC",
				"other_company_account": "TMP-MC - AB",
				"main_company_customer": "ABC Customer",
				"other_company_customer": "Main Customer",
				"main_company_supplier": "ABC Supplier",
				"other_company_supplier": "Main Supplier",
			})
			doc_full.validate()

	def test_mirrored_payment_entry_allows_bank_cash_account_change_locks_amount_fx(self):
		"""Verify mirrored Payment Entry allows changing paid_from/paid_to (TMP -> Cash/Bank) while locking amount, currency, party, and FX"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation import (
			validate_intercompany_document,
			validate_locked_mirrored_fields,
		)

		prev_pe = frappe._dict({
			"doctype": "Payment Entry",
			"name": "ACC-PAY-2026-00010",
			"company": "ABC Company",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": "Main Customer",
			"paid_from": "Debtors - ABC",
			"paid_to": "TMP-MAIN - ABC",
			"paid_from_account_currency": "PKR",
			"paid_to_account_currency": "PKR",
			"paid_amount": 1000.0,
			"received_amount": 1000.0,
			"source_exchange_rate": 1.0,
			"target_exchange_rate": 1.0,
			"is_intercompany": 1,
			"intercompany_target_company": "Main Co",
			"intercompany_linked_doc_doctype": "Payment Entry",
			"intercompany_linked_doc_name": "ACC-PAY-2026-00009",
			"intercompany_linked_company": "Main Co",
		})

		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_doc", return_value=prev_pe
		):
			# Switching TMP clearing account -> local Cash/Bank account in same currency must pass cleanly
			edited_account_pe = frappe._dict({
				**prev_pe,
				"paid_to": "Cash - ABC",
				"flags": frappe._dict(),
			})
			validate_intercompany_document(edited_account_pe)

			# Changing paid_amount must throw
			with self.assertRaises(Exception):
				validate_locked_mirrored_fields(
					frappe._dict({**prev_pe, "paid_to": "Cash - ABC", "paid_amount": 1200.0, "flags": frappe._dict()}),
					previous=prev_pe,
				)

			# Changing target_exchange_rate must throw
			with self.assertRaises(Exception):
				validate_locked_mirrored_fields(
					frappe._dict({**prev_pe, "paid_to": "Cash - ABC", "target_exchange_rate": 2.5, "flags": frappe._dict()}),
					previous=prev_pe,
				)

			# Changing paid_to_account_currency (e.g. picking USD bank for PKR payment) must throw
			with self.assertRaises(Exception):
				validate_locked_mirrored_fields(
					frappe._dict({**prev_pe, "paid_to": "USD Bank - ABC", "paid_to_account_currency": "USD", "flags": frappe._dict()}),
					previous=prev_pe,
				)

	def test_lookup_exchange_rate_v16_no_use_httpclient_field(self):
		"""Verify v16 Currency Exchange Settings without use_httpclient never throws/msgprints missing-field error and returns doc_currency_rate"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			check_intercompany_exchange_rate,
			lookup_intercompany_exchange_rate,
		)

		v16_meta = frappe._dict({
			"has_field": lambda fn: fn in ("disabled", "service_provider"),
		})

		def strict_get_single_value(dt, fieldname):
			if fieldname == "use_httpclient":
				raise AssertionError("Must not query use_httpclient when field does not exist in v16")
			if dt == "Currency Exchange Settings" and fieldname == "disabled":
				return 1
			return None

		def mock_get_all(doctype, filters=None, **kwargs):
			if doctype == "Currency Exchange" and filters == {"from_currency": "PKR", "to_currency": "USD", "date": ["<=", "2026-11-22"]}:
				return [frappe._dict({"exchange_rate": 0.003636364})]
			if doctype == "Currency Exchange" and filters == {"from_currency": "PKR", "to_currency": "USD"}:
				return [frappe._dict({"exchange_rate": 0.003636364})]
			return []

		def mock_get_value(dt, name, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if name == "Main PKR Co" else "USD"
			return None

		with patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt == "DocType" and name in ("Currency Exchange", "Currency Exchange Settings")
		), patch.object(
			frappe, "get_meta", return_value=v16_meta
		), patch.object(
			frappe.db, "get_single_value", side_effect=strict_get_single_value
		), patch.object(
			frappe, "get_all", return_value=[]
		):
			self.assertIsNone(lookup_intercompany_exchange_rate("USD", "PKR", "2026-11-22"))

		with patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt == "DocType" and name in ("Currency Exchange", "Currency Exchange Settings")
		), patch.object(
			frappe, "get_meta", return_value=v16_meta
		), patch.object(
			frappe.db, "get_single_value", side_effect=strict_get_single_value
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		):
			info = check_intercompany_exchange_rate("Main PKR Co", "Sister USD Co", "2026-11-22", doc_currency="USD")
			self.assertTrue(info["has_rate"])
			self.assertAlmostEqual(info["doc_currency_rate"], 1.0 / 0.003636364, places=3)

	def test_sales_order_foreign_currency_creates_po_with_inverse_exchange_rate(self):
		"""Verify Sales Order in USD @ 275 (PKR Main Co) mirrors Purchase Order in PKR @ 0.003636364 (USD Sister Co)"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_corresponding_document,
		)
		from inter_company_transactions.sync import receive_remote_transaction

		class FakeTradingDoc:
			def __init__(self, dt):
				self.doctype = dt
				self.items = []
				self.flags = frappe._dict()
				self.company = None
				self.currency = None
				self.conversion_rate = None
				self.buying_price_list = "Standard Buying"
				self.price_list_currency = "USD"
				self.plc_conversion_rate = 1.0

			def append(self, table, row):
				getattr(self, table).append(frappe._dict(row))

			def set_missing_values(self, for_validate=False):
				pass

			def get(self, key, default=None):
				return getattr(self, key, default)

			def insert(self, **kwargs):
				self.name = "PUR-ORD-2026-00001"
				return self

		src_so = FakeTradingDoc("Sales Order")
		src_so.name = "SAL-ORD-2026-00001"
		src_so.company = "PKR Main Co"
		src_so.transaction_date = "2026-11-22"
		src_so.delivery_date = "2026-11-25"
		src_so.currency = "USD"
		src_so.conversion_rate = 275.0
		src_so.append("items", {
			"item_code": "DAIRY-01",
			"item_name": "dairy america",
			"description": "dairy america",
			"qty": 2.0,
			"uom": "Nos",
			"rate": 10.0,
		})

		mapping = frappe._dict({"main_company": "PKR Main Co"})
		linked_co = frappe._dict({
			"company": "USD Sister Co",
			"main_company_customer": "Sister USD Cust",
			"other_company_customer": "Main PKR Cust",
			"main_company_supplier": "Sister USD Supp",
			"other_company_supplier": "Main PKR Supp",
		})
		mapping_info = {"mapping": mapping, "linked_company": linked_co, "target_doctype": "Purchase Order"}

		def mock_get_value(dt, name=None, fieldname=None, **kwargs):
			if dt == "Company" and fieldname == "default_currency":
				return "PKR" if name == "PKR Main Co" else "USD"
			if dt == "Supplier" and fieldname == "default_currency":
				return None
			if dt == "Item":
				return frappe._dict({"item_name": "dairy america", "stock_uom": "Nos", "description": "dairy america"})
			if dt == "Warehouse":
				return "Stores - USD"
			return None

		with patch.object(frappe, "new_doc", side_effect=lambda dt: FakeTradingDoc(dt)), patch.object(
			frappe, "get_all", return_value=[]
		), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Item", "Supplier")
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			po = create_corresponding_document(src_so, mapping_info, "main_to_other")
			self.assertEqual(po.currency, "PKR")
			self.assertAlmostEqual(po.conversion_rate, 1.0 / 275.0, places=6)
			self.assertAlmostEqual(po.items[0].rate, 2750.0, places=2)
			self.assertAlmostEqual(po.items[0].rate * po.conversion_rate, 10.0, places=2)

		remote_payload = {
			"source_doctype": "Sales Order",
			"source_name": "SAL-ORD-2026-00001",
			"source_company": "PKR Main Co",
			"target_company": "USD Sister Co",
			"source_company_currency": "PKR",
			"transaction_date": "2026-11-22",
			"schedule_date": "2026-11-25",
			"currency": "USD",
			"conversion_rate": 275.0,
			"items": [
				{"item_code": "DAIRY-01", "item_name": "dairy america", "qty": 2.0, "uom": "Nos", "rate": 10.0}
			],
		}
		created_docs = []

		def make_remote(dt):
			d = FakeTradingDoc(dt)
			created_docs.append(d)
			return d

		with patch.object(frappe, "new_doc", side_effect=make_remote), patch.object(
			frappe, "get_all", return_value=[]
		), patch(
			"inter_company_transactions.sync.resolve_counterparty_for_remote_source", return_value="Main PKR Supp"
		), patch(
			"inter_company_transactions.sync.resolve_item_code_for_remote", return_value="DAIRY-01"
		), patch.object(
			frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt in ("Item", "Supplier", "Company", "DocType")
		), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe.db, "get_value", side_effect=mock_get_value
		):
			res = receive_remote_transaction(remote_payload)
			self.assertTrue(res["success"])
			rem_po = created_docs[0]
			self.assertEqual(rem_po.currency, "PKR")
			self.assertAlmostEqual(rem_po.conversion_rate, 1.0 / 275.0, places=6)
			self.assertAlmostEqual(rem_po.items[0].rate, 2750.0, places=2)

	def test_v16_apps_screen_desktop_icon_and_workspace_sidebar(self):
		"""Verify add_to_apps_screen hook and v16 Desktop Icon + Workspace Sidebar creation without affecting v15"""
		from unittest.mock import patch

		import inter_company_transactions.hooks as ict_hooks
		from inter_company_transactions.boot import has_app_permission
		from inter_company_transactions.patches.after_migrate import ensure_v16_desktop_icon_and_sidebar

		apps_entry = ict_hooks.add_to_apps_screen[0]
		self.assertEqual(apps_entry["name"], "inter_company_transactions")
		self.assertEqual(apps_entry["title"], "Inter Company")
		self.assertIn("inter-company", apps_entry["route"])
		self.assertTrue(has_app_permission())

		# v15 mode: neither Workspace Sidebar nor v16 Desktop Icon fields exist -> clean no-op
		v15_di_meta = frappe._dict(has_field=lambda f: f in ("module_name", "label"), get_field=lambda f: None)
		with patch.object(frappe.db, "exists", side_effect=lambda dt, name=None, **kw: dt == "DocType" and name == "Desktop Icon"), patch.object(
			frappe, "get_meta", return_value=v15_di_meta
		):
			self.assertFalse(ensure_v16_desktop_icon_and_sidebar())

		# v16 mode: creates Workspace Sidebar + Desktop Icon linking to it
		store = {}

		class FakeNavDoc(dict):
			def __init__(self, dt):
				super().__init__(doctype=dt, items=[], flags=frappe._dict())
				self._new = True

			def __getattr__(self, k):
				return self[k] if k in self else None

			def __setattr__(self, k, v):
				self[k] = v

			def is_new(self):
				return self._new

			def append(self, table, row):
				self.setdefault(table, []).append(frappe._dict(row))

			def set(self, key, val):
				self[key] = val

			def insert(self, ignore_permissions=False):
				self._new = False
				self["name"] = self.get("name") or self.get("label") or self.get("title")
				store[(self["doctype"], self["name"])] = self
				return self

			def save(self, ignore_permissions=False):
				store[(self["doctype"], self["name"])] = self
				return self

		def fake_exists(dt, name=None, **kw):
			if dt == "DocType":
				return name in (
					"Workspace Sidebar",
					"Workspace Sidebar Item",
					"Desktop Icon",
					"Intercompany Transaction Link",
					"Inter Company Settings",
				)
			if dt == "Workspace":
				return name == "Inter Company"
			if dt == "Page":
				return name == "inter-company-console"
			if dt == "Workspace Sidebar":
				return (dt, name) in store
			if dt == "Desktop Icon":
				return (dt, name) in store
			return False

		def fake_meta(dt):
			if dt == "Workspace Sidebar":
				fields = {"app", "header_icon", "module", "standard", "is_standard"}
				return frappe._dict(has_field=lambda f: f in fields, get_field=lambda f: None)
			if dt == "Workspace Sidebar Item":
				fields = {"type", "icon", "link_type", "link_to", "label"}
				return frappe._dict(
					has_field=lambda f: f in fields,
					get_field=lambda f: frappe._dict(options="Workspace\nPage\nDocType\nReport") if f == "link_type" else None,
				)
			if dt == "Desktop Icon":
				fields = {"link_type", "link_to", "app", "icon_type", "sidebar", "logo_url", "icon", "standard", "hidden"}
				def _gf(f):
					if f == "link_type":
						return frappe._dict(options="Workspace Sidebar\nWorkspace\nPage\nExternal")
					if f == "icon_type":
						return frappe._dict(options="Link\nFolder\nApp")
					return None
				return frappe._dict(has_field=lambda f: f in fields, get_field=_gf)
			return frappe._dict(has_field=lambda f: False, get_field=lambda f: None)

		with patch.object(frappe.db, "exists", side_effect=fake_exists), patch.object(
			frappe, "get_meta", side_effect=fake_meta
		), patch.object(
			frappe, "get_all", return_value=[]
		), patch.object(
			frappe, "new_doc", side_effect=lambda dt: FakeNavDoc(dt)
		):
			changed = ensure_v16_desktop_icon_and_sidebar()
			self.assertTrue(changed)
			self.assertIn(("Workspace Sidebar", "Inter Company"), store)
			self.assertIn(("Desktop Icon", "Inter Company"), store)
			sidebar_doc = store[("Workspace Sidebar", "Inter Company")]
			self.assertGreaterEqual(len(sidebar_doc["items"]), 4)
			di_doc = store[("Desktop Icon", "Inter Company")]
			self.assertEqual(di_doc.link_type, "Workspace Sidebar")
			self.assertEqual(di_doc.link_to, "Inter Company")
			self.assertEqual(di_doc.sidebar, "Inter Company")

	def test_remote_site_password_decryption_and_mask_protection(self):
		"""Verify get_remote_site_for_company decrypts Password fields and never forwards masked '*****'"""
		from unittest.mock import patch

		from inter_company_transactions.sync import _get_decrypted_secret, get_remote_site_for_company

		class FakeRemoteRow(frappe._dict):
			def get_password(self, fieldname, raise_exception=False):
				return {"api_secret": "real-api-sec", "hmac_secret": "real-hmac-sec"}.get(fieldname)

		fake_row = FakeRemoteRow(
			company_name="Sister Co",
			site_url="https://sister.example.com/",
			api_key="key123",
			api_secret="*****",
			hmac_secret="*****",
			is_active=1,
		)
		fake_settings = frappe._dict({"remote_sites": [fake_row]})

		with patch.object(frappe, "get_cached_doc", return_value=fake_settings):
			cfg = get_remote_site_for_company("Sister Co")
			self.assertIsNotNone(cfg)
			self.assertEqual(cfg["api_secret"], "real-api-sec")
			self.assertEqual(cfg["hmac_secret"], "real-hmac-sec")

		self.assertEqual(_get_decrypted_secret({"hmac_secret": "*****"}, "hmac_secret"), "")
		self.assertEqual(_get_decrypted_secret({"hmac_secret": "plain-secret"}, "hmac_secret"), "plain-secret")

	def test_strict_hmac_signature_enforcement_and_company_validation(self):
		"""Verify missing/bad HMAC throws when secret configured and missing target_company never falls back"""
		import hashlib
		import hmac as _hmac
		import json
		from unittest.mock import patch

		from inter_company_transactions.sync import cancel_remote_transaction, receive_remote_transaction

		class SecretRow(dict):
			def get_password(self, fieldname, raise_exception=False):
				return "top-secret-hmac" if fieldname == "hmac_secret" else None

		settings_with_hmac = frappe._dict({
			"auto_submit_target_doc": 0,
			"remote_sites": [
				SecretRow(company_name="Remote Co", site_url="https://remote.example.com", is_active=1, hmac_secret="*****")
			],
		})
		payload_str = json.dumps({
			"source_doctype": "Sales Order",
			"source_name": "SO-999",
			"source_company": "Remote Co",
			"target_company": "Missing Co",
		})
		valid_sig = _hmac.new(b"top-secret-hmac", payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

		# 1. Missing X-Intercompany-Signature throws
		with patch.object(frappe, "get_cached_doc", return_value=settings_with_hmac), patch(
			"inter_company_transactions.sync._get_request_header_safe", return_value=None
		):
			with self.assertRaises(Exception):
				receive_remote_transaction(payload_str)
			with self.assertRaises(Exception):
				cancel_remote_transaction(payload_str)

		# 2. Invalid X-Intercompany-Signature throws
		with patch.object(frappe, "get_cached_doc", return_value=settings_with_hmac), patch(
			"inter_company_transactions.sync._get_request_header_safe", return_value="0" * 64
		):
			with self.assertRaises(Exception):
				receive_remote_transaction(payload_str)
			with self.assertRaises(Exception):
				cancel_remote_transaction(payload_str)

		# 3. Valid signature reaches Company check and MUST throw when target_company is invalid (no Company[0] fallback)
		with patch.object(frappe, "get_cached_doc", return_value=settings_with_hmac), patch(
			"inter_company_transactions.sync._get_request_header_safe", return_value=valid_sig
		), patch.object(
			frappe.db, "exists", return_value=False
		), patch.object(
			frappe, "get_all", return_value=[frappe._dict({"name": "Wrong First Company"})]
		):
			with self.assertRaises(Exception):
				receive_remote_transaction(payload_str)

	def test_network_diagnostics_ssrf_and_ipv6_protection(self):
		"""Verify SSRF IP blocking (IPv4 private/metadata + IPv6 ::1), scheme check, and System Manager RBAC"""
		import socket
		from unittest.mock import patch

		from inter_company_transactions.sync import _is_blocked_ssrf_ip, diagnose_remote_site_connectivity

		self.assertTrue(_is_blocked_ssrf_ip("127.0.0.1")[0])
		self.assertTrue(_is_blocked_ssrf_ip("169.254.169.254")[0])
		self.assertTrue(_is_blocked_ssrf_ip("10.10.0.1")[0])
		self.assertTrue(_is_blocked_ssrf_ip("192.168.1.50")[0])
		self.assertTrue(_is_blocked_ssrf_ip("::1")[0])
		self.assertTrue(_is_blocked_ssrf_ip("::ffff:127.0.0.1")[0])
		self.assertFalse(_is_blocked_ssrf_ip("93.184.216.34")[0])
		self.assertFalse(_is_blocked_ssrf_ip("2606:2800:220:1:248:1893:25c8:1946")[0])

		with patch.object(frappe, "only_for") as mock_only:
			ftp_diag = diagnose_remote_site_connectivity("ftp://erp.example.com")
			mock_only.assert_called_once_with("System Manager")
			self.assertEqual(ftp_diag["overall_status"], "Failed")
			self.assertIn("URL Format", [s["step"] for s in ftp_diag["steps"]])

			with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]):
				ssrf_diag = diagnose_remote_site_connectivity("http://metadata.internal")
				self.assertEqual(ssrf_diag["overall_status"], "Failed")
				self.assertIn("DNS Resolution & SSRF Safety", [s["step"] for s in ssrf_diag["steps"]])

			with patch("socket.getaddrinfo", return_value=[(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443, 0, 0))]):
				v6_local_diag = diagnose_remote_site_connectivity("https://localhost")
				self.assertEqual(v6_local_diag["overall_status"], "Failed")

	def test_whitelisted_endpoint_permission_guards(self):
		"""Verify whitelisted endpoints enforce Frappe permissions or role checks"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			check_intercompany_exchange_rate,
			check_stock_entry_same_currency,
			get_company_currencies,
			get_intercompany_dashboard_data,
			get_intercompany_party_map,
			get_party_target_company,
			reconcile_intercompany_accounts,
			scan_linked_company_defaults,
		)

		with patch.object(frappe, "only_for", side_effect=PermissionError("denied")):
			with self.assertRaises(PermissionError):
				reconcile_intercompany_accounts()
			with self.assertRaises(PermissionError):
				get_intercompany_dashboard_data("Co A")

		with patch.object(frappe, "has_permission", side_effect=PermissionError("no read")):
			with self.assertRaises(PermissionError):
				scan_linked_company_defaults("Co A", "Co B")
			with self.assertRaises(PermissionError):
				get_company_currencies(["Co A"])
			with self.assertRaises(PermissionError):
				check_intercompany_exchange_rate("Co A", "Co B")
			with self.assertRaises(PermissionError):
				check_stock_entry_same_currency("Co A", "Co B")
			with self.assertRaises(PermissionError):
				get_party_target_company("Cust A", "Customer", "Co A")

		with patch.object(frappe, "session", frappe._dict({"user": "Guest"})):
			with self.assertRaises(Exception):
				get_intercompany_party_map()

	def test_real_intercompany_balance_and_dashboard_queries(self):
		"""Verify get_intercompany_balance and get_intercompany_dashboard_data query live tables without stubs"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_api import (
			get_intercompany_balance,
			get_intercompany_dashboard_data_impl,
		)

		def mock_sql(query, params=None, as_dict=False):
			q = str(query)
			if "FROM `tabInter Company Document Reference`" in q and "COUNT(*)" in q:
				return [[2 if "target_name IS NULL" in q else 5]]
			if "FROM `tabInter Company Document Reference`" in q and "ORDER BY modified DESC" in q:
				return [{"source_doctype": "Sales Order", "source_name": "SO-1"}]
			if "FROM `tabIntercompany Linked Company`" in q:
				return [frappe._dict({
					"main_company": "Co A",
					"company": "Co B",
					"main_company_account": "TMP-B - A",
					"other_company_account": "TMP-A - B",
					"main_company_customer": "Cust B",
					"main_company_supplier": None,
					"other_company_customer": None,
					"other_company_supplier": "Supp A",
				})]
			if "FROM `tabGL Entry`" in q:
				comp = params["company"]
				return [[1000.0 if comp == "Co A" else -1000.0]]
			if "FROM `tabInter Company Error Log`" in q:
				return [[1]]
			if "FROM `tabSales Invoice`" in q:
				return [[2500.0]]
			return [[0]]

		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(frappe.db, "sql", side_effect=mock_sql):
			bal = get_intercompany_balance("Co A", "Co B")
			self.assertEqual(bal["transactions_count"], 5)
			self.assertEqual(bal["company_a_balance"], 1000.0)
			self.assertEqual(bal["company_b_balance"], -1000.0)
			self.assertEqual(bal["net_variance"], 0.0)
			self.assertTrue(bal["is_reconciled"])

			dash = get_intercompany_dashboard_data_impl("Co A")
			self.assertEqual(dash["pending_documents"], 3)
			self.assertEqual(dash["monthly_volume"], 2500.0)
			self.assertEqual(dash["outstanding_balances"], 1000.0)
			self.assertEqual(len(dash["recent_transactions"]), 1)

	def test_after_migrate_no_global_rewrite_and_validate_early_exit(self):
		"""Verify after_migrate stays ICT-scoped and non-intercompany docs skip party-map queries on validate"""
		from unittest.mock import patch

		import inter_company_transactions.diagnose_and_heal as dh
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation import (
			validate_intercompany_document,
		)
		from inter_company_transactions.patches.after_migrate import after_migrate

		with patch("inter_company_transactions.patches.after_migrate.ensure_custom_fields"), patch(
			"inter_company_transactions.patches.after_migrate.ensure_page_and_workspace"
		), patch(
			"inter_company_transactions.patches.after_migrate.ensure_ict_notification_settings_for_all_users"
		), patch.object(
			dh, "repair_database_text"
		) as mock_global_repair, patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._sanitize_intercompany_stock_entry_custom_fields"
		) as mock_ict_sanitize, patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.backfill_sister_company_names"
		):
			after_migrate()
			mock_global_repair.assert_not_called()
			mock_ict_sanitize.assert_called_once_with(force=True)

		se_non_ic = frappe._dict({
			"doctype": "Stock Entry",
			"name": "MAT-STE-LOCAL-1",
			"company": "Co A",
			"is_intercompany": 0,
			"flags": frappe._dict(),
		})
		mr_non_ic = frappe._dict({
			"doctype": "Material Request",
			"name": "MAT-MR-LOCAL-1",
			"company": "Co A",
			"is_intercompany": 0,
			"flags": frappe._dict(),
		})
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation.get_intercompany_party_map_impl"
		) as mock_pm:
			validate_intercompany_document(se_non_ic)
			validate_intercompany_document(mr_non_ic)
			mock_pm.assert_not_called()

	def test_netting_deduplication_currency_conversion_and_child_persistence(self):
		"""Verify netting skips mirrored SI+PI 2x double-count, converts FX, resolves reverse links, and persists settlements"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_netting_cycle.inter_company_netting_cycle import (
			InterCompanyNettingCycle,
			_compute_netting,
		)

		class FakeSettlementRow(frappe._dict):
			def insert(self, ignore_permissions=False):
				self.name = f"NET-SUM-{self.get('idx', 1)}"
				return self

			def db_set(self, vals, update_modified=False):
				if isinstance(vals, dict):
					self.update(vals)

		class FakeNettingDoc:
			def __init__(self):
				self.doctype = "Inter Company Netting Cycle"
				self.name = "NET-CYCLE-2026-00001"
				self.docstatus = 1
				self.settlement_date = "2026-11-23"
				self.participating_companies = [
					frappe._dict({"company": "Main Co"}),
					frappe._dict({"company": "Sub Co"}),
				]
				self.invoices = []
				self.net_settlements = []
				self.status = "Draft"
				self.total_gross_payables = 0.0
				self.total_gross_receivables = 0.0
				self.total_net_settled = 0.0

			def check_permission(self, ptype=None):
				return True

			def append(self, tbl, row):
				obj = FakeSettlementRow(row) if tbl == "net_settlements" else frappe._dict(row)
				getattr(self, tbl).append(obj)
				return obj

			def db_set(self, field, val=None, update_modified=False):
				if isinstance(field, dict):
					for k, v in field.items():
						setattr(self, k, v)
				else:
					setattr(self, field, val)

		doc = FakeNettingDoc()

		def mock_get_all(dt, filters=None, fields=None, **kw):
			if dt == "Intercompany Linked Company":
				return [frappe._dict({
					"parent": "IC-LINK-1",
					"company": "Sub Co",
					"main_company_customer": "Cust Sub",
					"main_company_supplier": "Supp Sub",
					"other_company_customer": "Cust Main",
					"other_company_supplier": "Supp Main",
				})]
			if dt == "Sales Invoice":
				return [frappe._dict({
					"name": "SINV-MAIN-001",
					"company": "Main Co",
					"customer": "Cust Sub",
					"outstanding_amount": 100.0,
					"currency": "USD",
				})]
			if dt == "Purchase Invoice":
				return [
					# Mirrored counterpart of SINV-MAIN-001 -> MUST be deduplicated!
					frappe._dict({
						"name": "PINV-SUB-001",
						"company": "Sub Co",
						"supplier": "Supp Main",
						"outstanding_amount": 28000.0,
						"currency": "PKR",
						"intercompany_linked_doc_doctype": "Sales Invoice",
						"intercompany_linked_doc_name": "SINV-MAIN-001",
					}),
				]
			if dt == "Inter Company Document Reference":
				return [frappe._dict({
					"source_doctype": "Sales Invoice",
					"source_name": "SINV-MAIN-001",
					"target_doctype": "Purchase Invoice",
					"target_name": "PINV-SUB-001",
				})]
			return []

		# Main Co is PKR, SINV-MAIN-001 is USD 100 @ 280 PKR/USD = PKR 28,000
		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		), patch.object(
			frappe, "get_value", return_value="Main Co"
		), patch.object(
			frappe, "get_cached_value", side_effect=lambda dt, name, fn=None: "PKR" if dt == "Company" else None
		), patch.object(
			frappe, "msgprint"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency.get_intercompany_exchange_rate",
			side_effect=lambda f, t, d=None, **kw: 280.0 if (f, t) == ("USD", "PKR") else 1.0,
		):
			InterCompanyNettingCycle.fetch_open_invoices(doc)

		# Mirrored Purchase Invoice excluded -> 1 unique obligation instead of 2
		self.assertEqual(len(doc.invoices), 1)
		self.assertEqual(doc.invoices[0].invoice_name, "SINV-MAIN-001")
		self.assertEqual(doc.total_gross_receivables, 28000.0)
		self.assertEqual(doc.total_gross_payables, 28000.0)
		self.assertEqual(doc.total_net_settled, 28000.0)
		self.assertEqual(doc.net_settlements[0].paying_company, "Sub Co")
		self.assertEqual(doc.net_settlements[0].receiving_company, "Main Co")

		# 1b. Direct _compute_netting with manual USD + PKR rows converts cleanly into cycle currency (PKR)
		manual_cycle = FakeNettingDoc()
		manual_cycle.invoices = [
			frappe._dict({"company": "Main Co", "partner_company": "Sub Co", "invoice_type": "Sales Invoice", "invoice_name": "SINV-MAN-1", "outstanding_amount": 10.0, "currency": "USD"}),
		]
		with patch.object(frappe.db, "table_exists", return_value=False), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe, "get_cached_value", return_value="PKR"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency.get_intercompany_exchange_rate",
			return_value=280.0,
		):
			_compute_netting(manual_cycle)
		self.assertEqual(manual_cycle.total_net_settled, 2800.0)

		# Now test on_submit persists settlement_entry via insert + db_set and resolves reverse Sub Co -> Main Co link
		created_jes = []

		class FakeJE:
			def __init__(self):
				self.doctype = "Journal Entry"
				self.name = "ACC-JV-NET-001"
				self.accounts = []
				self.flags = frappe._dict()
				self.docstatus = 0

			def append(self, tbl, row):
				self.accounts.append(frappe._dict(row))

			def insert(self, **kw):
				created_jes.append(self)
				return self

			def submit(self):
				self.docstatus = 1

			def cancel(self):
				self.docstatus = 2

		def mock_get_val(dt, flt_or_name, fieldname=None, as_dict=False):
			if dt == "Intercompany Transaction Link":
				if isinstance(flt_or_name, dict) and flt_or_name.get("main_company") == "Main Co":
					return "IC-LINK-1"
				return None
			if dt == "Intercompany Linked Company":
				return frappe._dict({
					"other_company_account": "TMP-MAIN - SUB",
					"other_company_supplier": "Supp Main",
				})
			if dt == "Company" and fieldname == "default_payable_account":
				return "Creditors - SUB"
			return None

		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "delete"
		) as mock_del, patch.object(
			frappe.db, "exists", return_value=False
		), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe, "get_value", side_effect=mock_get_val
		), patch.object(
			frappe, "get_cached_value", return_value="PKR"
		), patch.object(
			frappe.db, "get_value", return_value="PKR"
		), patch.object(
			frappe, "new_doc", return_value=FakeJE()
		), patch.object(
			frappe, "msgprint"
		), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency.get_intercompany_exchange_rate",
			side_effect=lambda f, t, d=None, **kw: 280.0 if (f, t) == ("USD", "PKR") else 1.0,
		):
			# Also pass duplicated mirrored pair directly into doc.invoices before submit -> _compute_netting skips duplicate!
			doc.append("invoices", {
				"company": "Sub Co",
				"partner_company": "Main Co",
				"invoice_type": "Purchase Invoice",
				"invoice_name": "PINV-SUB-001",
				"outstanding_amount": 28000.0,
				"currency": "PKR",
				"settled_amount": 28000.0,
			})
			with patch.object(frappe, "get_all", side_effect=mock_get_all):
				InterCompanyNettingCycle.on_submit(doc)

		mock_del.assert_called_once()
		self.assertEqual(len(created_jes), 1)
		self.assertEqual(created_jes[0].company, "Sub Co")
		self.assertEqual(created_jes[0].accounts[0].party, "Supp Main")
		self.assertEqual(created_jes[0].accounts[1].account, "TMP-MAIN - SUB")
		self.assertEqual(doc.net_settlements[0].name, "NET-SUM-1")
		self.assertEqual(doc.net_settlements[0].settlement_entry, "ACC-JV-NET-001")
		self.assertEqual(doc.net_settlements[0].status, "Settled")

		# Verify on_cancel cancels saved settlement_entry
		with patch.object(frappe.db, "exists", return_value=True), patch.object(
			frappe, "get_doc", return_value=created_jes[0]
		):
			InterCompanyNettingCycle.on_cancel(doc)
		self.assertEqual(created_jes[0].docstatus, 2)
		self.assertEqual(doc.status, "Cancelled")

	def test_elimination_run_no_bank_cash_no_fake_15pct_and_posting_date(self):
		"""Verify Elimination Run filters by posting_date, has 0 fabricated 15% margin, and never uses Bank/Cash accounts"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_elimination_run.inter_company_elimination_run import (
			InterCompanyEliminationRun,
		)

		elim_doc = frappe._dict({
			"doctype": "Inter Company Elimination Run",
			"name": "ELIM-2026-00001",
			"title": "Nov Consolidation",
			"consolidation_company": "Holding Co",
			"from_date": "2026-11-01",
			"to_date": "2026-11-30",
			"posting_date": "2026-11-30",
			"elimination_type": "All (Full Consolidation)",
			"unrealized_inventory_profit": 0.0,
			"db_set": lambda vals, **kw: elim_doc.update(vals) if isinstance(vals, dict) else elim_doc.__setitem__(vals, kw.get("val")),
		})

		def fix_db_set(k, v=None, **kw):
			if isinstance(k, dict):
				elim_doc.update(k)
			else:
				elim_doc[k] = v

		elim_doc.db_set = fix_db_set

		seen_filters = []

		def mock_get_all(dt, filters=None, or_filters=None, fields=None, **kw):
			seen_filters.append((dt, filters))
			if dt == "Inter Company Document Reference":
				return [frappe._dict({
					"source_doctype": "Sales Invoice",
					"source_name": "SINV-IC-1",
					"target_doctype": "Purchase Invoice",
					"target_name": "PINV-IC-1",
				})]
			if dt == "Sales Invoice":
				return [frappe._dict({
					"name": "SINV-IC-1",
					"company": "Sub A",
					"currency": "PKR",
					"grand_total": 10000.0,
					"outstanding_amount": 4000.0,
				})]
			if dt == "Purchase Invoice":
				return [frappe._dict({
					"name": "PINV-IC-1",
					"company": "Sub B",
					"currency": "PKR",
					"outstanding_amount": 4000.0,
				})]
			return []

		created_elim_jes = []

		class FakeElimJE:
			def __init__(self):
				self.doctype = "Journal Entry"
				self.name = "ACC-JV-ELIM-001"
				self.accounts = []
				self.flags = frappe._dict()
				self.docstatus = 0

			def append(self, tbl, row):
				self.accounts.append(frappe._dict(row))

			def get(self, k, d=None):
				return getattr(self, k, d)

			def insert(self, **kw):
				created_elim_jes.append(self)
				return self

			def submit(self):
				self.docstatus = 1

		def mock_db_get_val(dt, filters, fieldname=None, **kw):
			if dt == "Company":
				if fieldname in ("default_bank_account", "default_cash_account"):
					raise AssertionError(f"Elimination Run must NEVER query Company.{fieldname}")
				if fieldname == "default_income_account":
					return "Sales - HC"
				if fieldname == "default_expense_account":
					return "COGS - HC"
				if fieldname == "default_inventory_account":
					return "Stock - HC"
			if dt == "Account":
				if filters.get("root_type") == "Asset":
					return "Intercompany Elimination Asset - HC"
				if filters.get("root_type") == "Liability":
					return "Intercompany Elimination Liability - HC"
			return None

		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "has_column", return_value=True
		), patch.object(
			frappe, "get_all", side_effect=mock_get_all
		), patch.object(
			frappe, "get_cached_value", return_value="PKR"
		), patch.object(
			frappe.db, "get_value", side_effect=mock_db_get_val
		), patch.object(
			frappe, "new_doc", return_value=FakeElimJE()
		), patch.object(
			frappe, "msgprint"
		):
			InterCompanyEliminationRun.on_submit(elim_doc)

		# 1. Filtered by posting_date, never Inter Company Document Reference.creation
		si_filters = [f for dt, f in seen_filters if dt == "Sales Invoice"][0]
		self.assertIn("posting_date", si_filters)
		ref_filters = [f for dt, f in seen_filters if dt == "Inter Company Document Reference"][0]
		self.assertNotIn("creation", ref_filters)

		# 2. No fake 15% unrealized profit
		self.assertEqual(elim_doc.unrealized_inventory_profit, 0.0)
		self.assertEqual(elim_doc.total_revenue_eliminated, 10000.0)
		self.assertEqual(elim_doc.total_receivables_eliminated, 4000.0)

		# 3. JE lines use non-cash Elimination Asset/Liability accounts, never Bank/Cash
		je_accounts = [r.account for r in created_elim_jes[0].accounts]
		self.assertEqual(
			je_accounts,
			["Sales - HC", "COGS - HC", "Intercompany Elimination Liability - HC", "Intercompany Elimination Asset - HC"],
		)

	def test_settings_js_and_masked_api_secret_resolution(self):
		"""Verify Settings JS uses full dotted method paths and masked secrets resolve stored passwords"""
		from pathlib import Path
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings import (
			_resolve_saved_remote_api_secret,
		)

		js_path = (
			Path(__file__).resolve().parents[1]
			/ "inter_company_settings"
			/ "inter_company_settings.js"
		)
		js_src = js_path.read_text(encoding="utf-8")
		self.assertIn(
			"inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.get_enterprise_health_check",
			js_src,
		)
		self.assertIn(
			"inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.test_remote_site_connection",
			js_src,
		)
		self.assertNotIn("method: 'get_enterprise_health_check'", js_src)
		self.assertNotIn("method: 'test_remote_site_connection'", js_src)

		class SavedRow(frappe._dict):
			def get_password(self, fieldname, raise_exception=False):
				return "decrypted-real-secret" if fieldname == "api_secret" else None

		fake_settings = frappe._dict({
			"remote_sites": [SavedRow(site_url="https://remote.example.com/", api_key="k1", api_secret="*****")]
		})
		with patch.object(frappe, "get_cached_doc", return_value=fake_settings):
			self.assertEqual(
				_resolve_saved_remote_api_secret("https://remote.example.com", "k1", "*****"),
				"decrypted-real-secret",
			)
			self.assertEqual(
				_resolve_saved_remote_api_secret("https://remote.example.com", "k1", "explicit-pass"),
				"explicit-pass",
			)

	def test_async_enqueue_after_commit_prevalidation_and_core_ic_guard(self):
		"""Verify enqueue_after_commit=True, ERPNext core IC guard, and ValidationError surface on sync"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle import (
			create_linked_documents,
		)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation import (
			auto_detect_intercompany_party,
		)

		# 1. Core ERPNext inter_company_invoice_reference must skip ICT mirror & auto-detect
		core_si = frappe._dict({
			"doctype": "Sales Invoice",
			"name": "SINV-CORE-IC-1",
			"company": "Co A",
			"is_intercompany": 1,
			"intercompany_target_company": "Co B",
			"inter_company_invoice_reference": "PINV-CORE-IC-1",
		})
		with patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.find_applicable_mappings"
		) as mock_find, patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_validation.get_intercompany_party_map_impl"
		) as mock_pm:
			create_linked_documents(core_si)
			auto_detect_intercompany_party(core_si)
			mock_find.assert_not_called()
			mock_pm.assert_not_called()

		# 2. Async execution passes enqueue_after_commit=True
		src_so = frappe._dict({
			"doctype": "Sales Order",
			"name": "SO-ASYNC-1",
			"company": "Co A",
			"is_intercompany": 1,
			"intercompany_target_company": "Co B",
		})
		orig_in_test = getattr(frappe.flags, "in_test", False)
		orig_in_bg = frappe.flags.get("ict_in_background")
		try:
			frappe.flags.in_test = False
			frappe.flags.ict_in_background = False
			with patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
				return_value={"enabled": 1, "execution_mode": "Asynchronous (Background Job)"},
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_intercompany_cross_currency_rate"
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.find_applicable_mappings",
				return_value=[],
			), patch.object(
				frappe, "enqueue"
			) as mock_enqueue, patch.object(
				frappe, "msgprint"
			):
				create_linked_documents(src_so)
				mock_enqueue.assert_called_once()
				self.assertTrue(mock_enqueue.call_args.kwargs.get("enqueue_after_commit"))
		finally:
			frappe.flags.in_test = orig_in_test
			if orig_in_bg is None:
				frappe.flags.pop("ict_in_background", None)
			else:
				frappe.flags.ict_in_background = orig_in_bg

		# 3. Synchronous ValidationError propagates instead of failing silently
		sync_mappings = [{
			"mapping": frappe._dict({"main_company": "Co A"}),
			"linked_company": frappe._dict({"company": "Co B"}),
			"company": "Co B",
			"target_doctype": "Purchase Order",
			"direction": "main_to_other",
		}]
		orig_in_bg = frappe.flags.get("ict_in_background")
		try:
			frappe.flags.ict_in_background = False
			with patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._get_intercompany_settings",
				return_value={"enabled": 1, "execution_mode": "Synchronous"},
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_intercompany_cross_currency_rate"
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.find_applicable_mappings",
				return_value=sync_mappings,
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle.validate_required_parties",
				side_effect=frappe.ValidationError("Other Company Supplier is required"),
			), patch(
				"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_lifecycle._log_local_mirror_error"
			) as mock_err_log, patch.object(
				frappe, "log_error"
			):
				with self.assertRaises(frappe.ValidationError):
					create_linked_documents(src_so)
				mock_err_log.assert_called_once()
		finally:
			if orig_in_bg is None:
				frappe.flags.pop("ict_in_background", None)
			else:
				frappe.flags.ict_in_background = orig_in_bg

	def test_payment_entry_populates_references_and_matrix_filters_posting_date(self):
		"""Verify create_payment_entry maps counterpart invoices into references and matrix filters by posting_date"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_accounting_builders import (
			create_payment_entry,
		)
		from inter_company_transactions.inter_company_transactions.report.inter_company_transaction_matrix.inter_company_transaction_matrix import (
			execute as matrix_execute,
		)

		class FakePEDoc(frappe._dict):
			def append(self, tbl, row):
				self.setdefault(tbl, []).append(frappe._dict(row))

			def get(self, key, default=None):
				return super().get(key, default)

		src_pe = frappe._dict({
			"doctype": "Payment Entry",
			"name": "ACC-PAY-SRC-1",
			"company": "Co A",
			"payment_type": "Receive",
			"posting_date": "2026-11-23",
			"paid_amount": 500.0,
			"received_amount": 500.0,
			"paid_from_account_currency": "PKR",
			"paid_to_account_currency": "PKR",
			"references": [
				frappe._dict({
					"reference_doctype": "Sales Invoice",
					"reference_name": "SINV-A-1",
					"allocated_amount": 500.0,
				})
			],
		})
		mapping = frappe._dict({"main_company": "Co A"})
		linked_co = frappe._dict({
			"company": "Co B",
			"other_company_account": "TMP-A - B",
			"other_company_supplier": "Supp Co A",
			"other_company_customer": "Cust Co A",
		})

		def mock_pe_get_val(dt, flt_or_name, fieldname=None, as_dict=False):
			if dt == "Company":
				if fieldname == "default_currency":
					return "PKR"
				if fieldname == "default_payable_account":
					return "Creditors - B"
			if dt == "Account":
				return "Bank" if fieldname == "account_type" else "PKR"
			if dt == "Inter Company Document Reference":
				if isinstance(flt_or_name, dict) and flt_or_name.get("source_name") == "SINV-A-1":
					return frappe._dict({"target_doctype": "Purchase Invoice", "target_name": "PINV-B-1"})
				return None
			if dt == "Purchase Invoice":
				return frappe._dict({
					"docstatus": 1,
					"outstanding_amount": 500.0,
					"grand_total": 500.0,
					"currency": "PKR",
				})
			if dt == "Sales Invoice":
				return "PKR"
			if dt == "Supplier":
				return "Supp Co A"
			return None

		fake_pe = FakePEDoc({"doctype": "Payment Entry", "references": [], "flags": frappe._dict()})
		with patch.object(frappe, "new_doc", return_value=fake_pe), patch.object(
			frappe.db, "table_exists", return_value=True
		), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(
			frappe.db, "get_value", side_effect=mock_pe_get_val
		):
			pe = create_payment_entry(src_pe, mapping, linked_co, "main_to_other")
			self.assertEqual(len(pe.references), 1)
			self.assertEqual(pe.references[0].reference_doctype, "Purchase Invoice")
			self.assertEqual(pe.references[0].reference_name, "PINV-B-1")
			self.assertEqual(pe.references[0].allocated_amount, 500.0)

		# Matrix report must filter on document posting_date (Jan) rather than ref creation (Feb)
		schema_cols = {"Sales Invoice": {"name", "grand_total", "posting_date"}, "Purchase Invoice": {"name", "grand_total", "posting_date"}}
		refs = [
			frappe._dict({
				"name": "REF-BACKDATED",
				"source_doctype": "Sales Invoice",
				"source_name": "SINV-JAN",
				"source_company": "A",
				"target_doctype": "Purchase Invoice",
				"target_name": "PINV-JAN",
				"target_company": "B",
				"creation": "2026-02-10 10:00:00",
			})
		]
		docs = {
			("Sales Invoice", "SINV-JAN"): {"name": "SINV-JAN", "grand_total": 100.0, "posting_date": "2026-01-15"},
			("Purchase Invoice", "PINV-JAN"): {"name": "PINV-JAN", "grand_total": 100.0, "posting_date": "2026-01-15"},
		}
		with patch.object(frappe, "get_all", return_value=refs), patch.object(
			frappe.db, "exists", side_effect=lambda dt, n=None, **k: (dt, n) in docs
		), patch.object(
			frappe.db, "has_column", side_effect=lambda dt, col: col in schema_cols.get(dt, set())
		), patch.object(
			frappe.db, "get_value", side_effect=lambda dt, n, fields, as_dict=False: frappe._dict(docs[(dt, n)])
		):
			_c, jan_rows, _m, _ch, _s = matrix_execute({"from_date": "2026-01-01", "to_date": "2026-01-31"})
			_c2, feb_rows, _m2, _ch2, _s2 = matrix_execute({"from_date": "2026-02-01", "to_date": "2026-02-28"})
			self.assertEqual(len(jan_rows), 1)
			self.assertEqual(len(feb_rows), 0)

	def test_netting_two_sided_settlement_with_invoice_references_and_dual_cancel(self):
		"""Verify netting posts both payer AP and receiver AR Journal Entries with invoice references and cancels both"""
		from unittest.mock import patch

		from inter_company_transactions.inter_company_transactions.doctype.inter_company_netting_cycle.inter_company_netting_cycle import (
			InterCompanyNettingCycle,
		)

		class FakeSettlementRow(frappe._dict):
			def insert(self, ignore_permissions=False):
				self.name = f"NET-SUM-{self.get('idx', 1)}"
				return self

			def db_set(self, vals, update_modified=False):
				if isinstance(vals, dict):
					self.update(vals)

		class FakeTwoSidedDoc:
			def __init__(self):
				self.doctype = "Inter Company Netting Cycle"
				self.name = "NET-CYCLE-2SIDE-1"
				self.docstatus = 1
				self.settlement_date = "2026-11-24"
				self.participating_companies = [
					frappe._dict({"company": "Main Co"}),
					frappe._dict({"company": "Sub Co"}),
				]
				self.invoices = [
					frappe._dict({
						"company": "Main Co",
						"partner_company": "Sub Co",
						"invoice_type": "Sales Invoice",
						"invoice_name": "SINV-MAIN-99",
						"outstanding_amount": 500.0,
						"settled_amount": 500.0,
						"currency": "PKR",
					})
				]
				self.net_settlements = []
				self.status = "Draft"

			def append(self, tbl, row):
				obj = FakeSettlementRow(row) if tbl == "net_settlements" else frappe._dict(row)
				getattr(self, tbl).append(obj)
				return obj

			def db_set(self, field, val=None, update_modified=False):
				if isinstance(field, dict):
					for k, v in field.items():
						setattr(self, k, v)
				else:
					setattr(self, field, val)

		created_jes = []

		class FakeJE:
			def __init__(self):
				self.doctype = "Journal Entry"
				self.name = f"ACC-JV-2SIDE-{len(created_jes) + 1}"
				self.accounts = []
				self.flags = frappe._dict()
				self.docstatus = 0

			def append(self, tbl, row):
				self.accounts.append(frappe._dict(row))

			def insert(self, **kw):
				created_jes.append(self)
				return self

			def submit(self):
				self.docstatus = 1

			def cancel(self):
				self.docstatus = 2

		doc = FakeTwoSidedDoc()

		def mock_get_val(dt, flt_or_name, fieldname=None, as_dict=False):
			if dt == "Intercompany Transaction Link":
				if isinstance(flt_or_name, dict) and flt_or_name.get("main_company") == "Main Co":
					return "IC-LINK-2S"
				return None
			if dt == "Intercompany Linked Company":
				return frappe._dict({
					"main_company_account": "TMP-SUB - MAIN",
					"main_company_customer": "Cust Sub",
					"other_company_account": "TMP-MAIN - SUB",
					"other_company_supplier": "Supp Main",
				})
			if dt == "Company":
				if fieldname == "default_payable_account":
					return "Creditors - SUB"
				if fieldname == "default_receivable_account":
					return "Debtors - MAIN"
			return None

		def mock_db_get_val(dt, flt_or_name, fieldname=None, as_dict=False):
			if dt == "Inter Company Document Reference":
				if isinstance(flt_or_name, dict) and flt_or_name.get("source_name") == "SINV-MAIN-99":
					return "PINV-SUB-99"
				return None
			if dt == "Purchase Invoice" and flt_or_name == "PINV-SUB-99":
				return frappe._dict({"docstatus": 1, "outstanding_amount": 500.0, "currency": "PKR"})
			if dt == "Company":
				return "PKR"
			return None

		with patch.object(frappe.db, "table_exists", return_value=True), patch.object(
			frappe.db, "delete"
		), patch.object(
			frappe.db, "exists", return_value=False
		), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe, "get_value", side_effect=mock_get_val
		), patch.object(
			frappe, "get_cached_value", return_value="PKR"
		), patch.object(
			frappe.db, "get_value", side_effect=mock_db_get_val
		), patch.object(
			frappe, "new_doc", side_effect=lambda dt: FakeJE()
		), patch.object(
			frappe, "msgprint"
		):
			InterCompanyNettingCycle.on_submit(doc)

		self.assertEqual(len(created_jes), 2)
		payer_je, recv_je = created_jes[0], created_jes[1]
		self.assertEqual(payer_je.company, "Sub Co")
		self.assertEqual(payer_je.accounts[0].party, "Supp Main")
		self.assertEqual(payer_je.accounts[0].reference_type, "Purchase Invoice")
		self.assertEqual(payer_je.accounts[0].reference_name, "PINV-SUB-99")
		self.assertEqual(payer_je.accounts[1].account, "TMP-MAIN - SUB")

		self.assertEqual(recv_je.company, "Main Co")
		self.assertEqual(recv_je.accounts[0].account, "TMP-SUB - MAIN")
		self.assertEqual(recv_je.accounts[1].party, "Cust Sub")
		self.assertEqual(recv_je.accounts[1].reference_type, "Sales Invoice")
		self.assertEqual(recv_je.accounts[1].reference_name, "SINV-MAIN-99")

		self.assertEqual(doc.net_settlements[0].settlement_entry, payer_je.name)
		self.assertEqual(doc.net_settlements[0].receiver_settlement_entry, recv_je.name)
		self.assertEqual(doc.net_settlements[0].status, "Settled")

		je_map = {payer_je.name: payer_je, recv_je.name: recv_je}
		with patch.object(frappe.db, "exists", side_effect=lambda dt, n: n in je_map), patch.object(
			frappe, "get_doc", side_effect=lambda dt, n: je_map[n]
		):
			InterCompanyNettingCycle.on_cancel(doc)
		self.assertEqual(payer_je.docstatus, 2)
		self.assertEqual(recv_je.docstatus, 2)

	def test_v15_patch_and_uninstall_no_global_healing_boot_cached_and_rfq_fallback_rate(self):
		"""Verify v1_5 patch skips run_full_healing, uninstall drops dead helper, boot caches Desk only, and RFQ gets fallback rate"""
		from unittest.mock import MagicMock, patch

		from inter_company_transactions import boot, uninstall
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_builders import (
			create_supplier_quotation,
		)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_utils import (
			fix_legacy_custom_fields,
		)
		from inter_company_transactions.patches import v1_5_repair_item_depends_on_and_clean_trees as v15_patch

		# 1. Dead repair helper removed from uninstall.py
		self.assertFalse(hasattr(uninstall, "repair_all_depends_on_expressions"))

		# 2. v1_5 patch and fix_legacy_custom_fields stay ICT-scoped and never invoke run_full_healing / repair_database_text
		with patch("inter_company_transactions.diagnose_and_heal.run_full_healing") as mock_heal, patch(
			"inter_company_transactions.diagnose_and_heal.repair_database_text"
		) as mock_repair, patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_utils._sanitize_intercompany_stock_entry_custom_fields"
		) as mock_sanitize, patch.object(frappe.db, "table_exists", return_value=False):
			v15_patch.execute()
			fix_legacy_custom_fields()
			mock_heal.assert_not_called()
			mock_repair.assert_not_called()
			self.assertGreaterEqual(mock_sanitize.call_count, 2)

		# 3. boot_session skips Guest / Website User and uses cache for Desk users
		bootinfo = frappe._dict()
		with patch.object(frappe, "session", frappe._dict({"user": "Guest"})), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_party_map"
		) as mock_pm:
			boot.boot_session(bootinfo)
			mock_pm.assert_not_called()

		fake_cache = MagicMock()
		fake_cache.get_value.return_value = None
		with patch.object(frappe, "session", frappe._dict({"user": "accountant@example.com"})), patch.object(
			frappe.db, "get_value", return_value="System User"
		), patch.object(frappe, "cache", return_value=fake_cache, create=True), patch(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_party_map",
			return_value={"party_to_company": {"Cust B": "Co B"}},
		) as mock_pm:
			boot.boot_session(bootinfo)
			mock_pm.assert_called_once()
			fake_cache.set_value.assert_called_once()
			self.assertEqual(bootinfo.intercompany_party_map, {"party_to_company": {"Cust B": "Co B"}})

		# 4. RFQ -> Supplier Quotation resolves Item Price fallback rate instead of 0 under Source Document Rate
		class FakeSQ:
			def __init__(self):
				self.doctype = "Supplier Quotation"
				self.items = []
				self.flags = frappe._dict()

			def append(self, tbl, row):
				getattr(self, tbl).append(frappe._dict(row))

			def set_missing_values(self, for_validate=True):
				pass

		class FakeRFQ:
			doctype = "Request for Quotation"
			name = "PUR-RFQ-2026-00001"
			company = "Co A"
			transaction_date = "2026-11-24"
			items = [frappe._dict({"item_code": "ITEM-RFQ-1", "item_name": "Widget", "qty": 2.0, "uom": "Nos"})]

		rfq = FakeRFQ()
		mapping = frappe._dict({"main_company": "Co A"})
		linked_co = frappe._dict({"company": "Co B", "other_company_supplier": "Supp Co A"})
		settings = {"default_transfer_pricing_rule": "Source Document Rate"}

		def rfq_get_val(dt, filters, fieldname=None, as_dict=False):
			if dt == "Company":
				return "PKR"
			if dt == "Item Price":
				return frappe._dict({"price_list_rate": 450.0, "currency": "PKR"})
			if dt == "Item":
				return frappe._dict({"item_name": "Widget", "stock_uom": "Nos", "description": "Widget"})
			return None

		with patch.object(frappe, "new_doc", return_value=FakeSQ()), patch.object(
			frappe.db, "exists", return_value=True
		), patch.object(
			frappe.db, "has_column", return_value=False
		), patch.object(
			frappe.db, "get_value", side_effect=rfq_get_val
		):
			sq = create_supplier_quotation(rfq, mapping, linked_co, "main_to_other", settings=settings)
			self.assertEqual(sq.items[0].rate, 450.0)

