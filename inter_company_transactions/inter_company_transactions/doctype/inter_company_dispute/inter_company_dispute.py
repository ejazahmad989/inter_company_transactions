# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
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

		elif res_action == "Journal Adjustment" and self.variance_amount > 0:
			je = frappe.new_doc("Journal Entry")
			je.company = self.source_company
			je.posting_date = nowdate()
			je.user_remark = f"Dispute Adjustment for {self.name} ({self.dispute_title}): Variance of {self.variance_amount}"
			accounts = frappe.get_all("Account", filters={"company": self.source_company, "is_group": 0}, pluck="name", limit=2)
			if len(accounts) >= 2:
				je.append("accounts", {"account": accounts[0], "debit_in_account_currency": self.variance_amount, "credit_in_account_currency": 0})
				je.append("accounts", {"account": accounts[1], "debit_in_account_currency": 0, "credit_in_account_currency": self.variance_amount})
				je.flags.ignore_permissions = True
				je.insert()
				res_doc_name = je.name

		self.resolution_document = res_doc_name or _("Variance Accepted (No entry required)")
		self.status = "Resolved"
		self.save()
		frappe.msgprint(_("Dispute {0} resolved successfully: {1}").format(self.name, self.resolution_document), indicator="green")
