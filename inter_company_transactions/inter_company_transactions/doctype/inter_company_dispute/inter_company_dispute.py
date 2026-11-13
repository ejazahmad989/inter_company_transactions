# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class InterCompanyDispute(Document):
	def validate(self):
		self.variance_amount = abs(flt(self.target_amount) - flt(self.source_amount))

	@frappe.whitelist()
	def execute_resolution(self):
		"""
		Executes selected resolution method:
		- Issue Credit Note (return Sales Invoice)
		- Issue Debit Note (return Purchase Invoice)
		- Journal Adjustment
		- Accept Variance
		"""
		if self.status == "Resolved":
			frappe.throw(_("Dispute is already resolved."))

		res_action = self.resolution_action
		res_doc_name = None

		if res_action == "Issue Credit Note" and self.source_doctype == "Sales Invoice":
			# Create Credit Note return
			orig_doc = frappe.get_doc("Sales Invoice", self.source_name)
			cn = frappe.new_doc("Sales Invoice")
			cn.is_return = 1
			cn.return_against = orig_doc.name
			cn.customer = orig_doc.customer
			cn.company = orig_doc.company
			cn.posting_date = nowdate()
			for item in orig_doc.items:
				cn.append("items", {
					"item_code": item.item_code,
					"qty": -1 * (item.qty or 1),
					"rate": item.rate,
					"uom": item.uom
				})
			cn.flags.ignore_permissions = True
			cn.insert()
			res_doc_name = cn.name

		elif res_action == "Issue Debit Note" and self.source_doctype == "Purchase Invoice":
			# Create Debit Note return
			orig_doc = frappe.get_doc("Purchase Invoice", self.source_name)
			dn = frappe.new_doc("Purchase Invoice")
			dn.is_return = 1
			dn.return_against = orig_doc.name
			dn.supplier = orig_doc.supplier
			dn.company = orig_doc.company
			dn.posting_date = nowdate()
			for item in orig_doc.items:
				dn.append("items", {
					"item_code": item.item_code,
					"qty": -1 * (item.qty or 1),
					"rate": item.rate,
					"uom": item.uom
				})
			dn.flags.ignore_permissions = True
			dn.insert()
			res_doc_name = dn.name

		elif res_action in ("Journal Adjustment", "Stock Adjustment") and self.variance_amount > 0:
			from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
				get_or_create_intercompany_clearing_account,
			)
			je = frappe.new_doc("Journal Entry")
			je.company = self.source_company
			je.posting_date = nowdate()
			je.user_remark = f"{res_action} for Dispute {self.name} ({self.dispute_title}): Variance of {self.variance_amount}"
			clearing_acct = get_or_create_intercompany_clearing_account(self.source_company, self.target_company)
			expense_acct = (
				frappe.db.get_value("Company", self.source_company, "default_expense_account")
				or frappe.db.get_value("Account", {"company": self.source_company, "root_type": "Expense", "is_group": 0}, "name")
			)
			if not expense_acct or expense_acct == clearing_acct:
				expense_acct = frappe.db.get_value(
					"Account",
					{"company": self.source_company, "is_group": 0, "name": ["!=", clearing_acct or ""]},
					"name",
				)
			if clearing_acct and expense_acct:
				je.append("accounts", {"account": expense_acct, "debit_in_account_currency": self.variance_amount, "credit_in_account_currency": 0})
				je.append("accounts", {"account": clearing_acct, "debit_in_account_currency": 0, "credit_in_account_currency": self.variance_amount})
				je.flags.ignore_permissions = True
				je.flags.ignore_mandatory = True
				je.insert(ignore_permissions=True)
				res_doc_name = je.name

		self.resolution_document = res_doc_name or _("Variance Accepted (No entry required)")
		self.status = "Resolved"
		self.save()
		frappe.msgprint(_("Dispute {0} resolved successfully: {1}").format(self.name, self.resolution_document), indicator="green")
