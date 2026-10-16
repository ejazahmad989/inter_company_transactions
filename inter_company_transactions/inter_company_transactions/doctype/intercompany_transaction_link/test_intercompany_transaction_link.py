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

	def test_netting_settlement_calculation(self):
		"""Verify multilateral netting algorithm balances debts and credits"""
		from inter_company_transactions.inter_company_transactions.doctype.inter_company_netting_cycle.inter_company_netting_cycle import (
			InterCompanyNettingCycle,
		)
		cycle = frappe.new_doc("InterCompany Netting Cycle")
		cycle.cycle_name = "Q1 Test Settlement"
		cycle.netting_currency = "USD"
		# Set up 3 companies with known balances
		# Company A: owes B 100, owes C 50 -> Net -150
		# Company B: owed 100 from A, owes C 20 -> Net +80
		# Company C: owed 50 from A, owed 20 from B -> Net +70
		# Netting should reduce 3 transactions into just 2 minimal settlements
		cycle.append("companies", {"company": "Company A", "initial_balance": -150})
		cycle.append("companies", {"company": "Company B", "initial_balance": 80})
		cycle.append("companies", {"company": "Company C", "initial_balance": 70})

		cycle.calculate_netting()
		self.assertGreater(len(cycle.net_settlements), 0)
		total_settled = sum(flt(s.settlement_amount) for s in cycle.net_settlements)
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




