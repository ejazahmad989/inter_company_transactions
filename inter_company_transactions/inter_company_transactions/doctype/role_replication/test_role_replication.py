# Copyright (c) 2024-2026, Inter Company Transactions and Contributors
# See license.txt

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from inter_company_transactions.inter_company_transactions.doctype.role_replication.role_replication import (
	RoleReplication,
)


class TestRoleReplication(FrappeTestCase):
	"""
	Unit tests for Role Replication DocType.
	Tests validation requirements, role creation, and permission replication logic.
	"""

	def setUp(self):
		frappe.flags.ignore_permissions = True

	def test_validate_missing_existing_role_raises(self):
		"""Verify validation throws error when existing_role is not selected"""
		doc = frappe.new_doc("Role Replication")
		doc.new_role = "Test Custom Role"
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_missing_new_role_raises(self):
		"""Verify validation throws error when new_role is blank"""
		doc = frappe.new_doc("Role Replication")
		doc.existing_role = "Accounts User"
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_valid_doc_passes(self):
		"""Verify valid configuration passes validation without error"""
		doc = frappe.new_doc("Role Replication")
		doc.existing_role = "Accounts User"
		doc.new_role = "Accounts User Junior"
		doc.validate()
		self.assertEqual(doc.existing_role, "Accounts User")
		self.assertEqual(doc.new_role, "Accounts User Junior")

	@patch("frappe.only_for")
	@patch("frappe.db.commit")
	@patch("frappe.clear_cache")
	@patch("frappe.msgprint")
	def test_replicate_role_returns_summary(self, mock_msgprint, mock_clear, mock_commit, mock_only_for):
		"""Verify replicate_role creates role and returns structured summary"""
		doc = frappe.new_doc("Role Replication")
		doc.existing_role = "Accounts User"
		doc.new_role = "Test Automated New Role"

		with patch("frappe.db.exists") as mock_exists, \
		     patch("frappe.get_doc") as mock_get_doc, \
		     patch("inter_company_transactions.inter_company_transactions.doctype.role_replication.role_replication.get_permissions") as mock_get_perms:

			# Mock role doesn't exist yet, then returns permissions
			mock_exists.return_value = False
			mock_role_doc = MagicMock()
			mock_role_doc.name = "Test Automated New Role"
			mock_get_doc.return_value = mock_role_doc
			mock_get_perms.return_value = []

			result = doc.replicate_role()
			self.assertIsNotNone(result)
			self.assertEqual(result.get("new_role"), "Test Automated New Role")
			self.assertEqual(result.get("copied_count"), 0)
			self.assertEqual(result.get("source_role"), "Accounts User")
