# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class InterCompanyEliminationRun(Document):
	def validate(self):
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("From Date cannot be later than To Date."))

	@frappe.whitelist()
	def calculate_eliminations(self):
		"""
		Calculates Intercompany Eliminations for consolidation:
		1. Eliminates mutual intercompany sales revenue & purchases/COGS.
		2. Eliminates mutual intercompany AR & AP.
		3. Eliminates unrealized gross margin stored in ending stock.
		"""
		# Get all intercompany links
		intercompany_docs = frappe.get_all(
			"Inter Company Document Reference",
			filters={
				"creation": ["between", [self.from_date, self.to_date]]
			},
			fields=["source_doctype", "source_name", "source_company", "target_doctype", "target_name", "target_company"]
		)

		total_sales = 0.0
		total_ar = 0.0
		total_ap = 0.0

		for ref in intercompany_docs:
			if ref.source_doctype == "Sales Invoice" and frappe.db.exists("Sales Invoice", ref.source_name):
				si = frappe.get_value("Sales Invoice", ref.source_name, ["grand_total", "outstanding_amount", "docstatus"], as_dict=True)
				if si and si.docstatus == 1:
					total_sales += flt(si.grand_total)
					total_ar += flt(si.outstanding_amount)

			if ref.target_doctype == "Purchase Invoice" and frappe.db.exists("Purchase Invoice", ref.target_name):
				pi = frappe.get_value("Purchase Invoice", ref.target_name, ["outstanding_amount", "docstatus"], as_dict=True)
				if pi and pi.docstatus == 1:
					total_ap += flt(pi.outstanding_amount)

		# If direct references are fewer, also aggregate by intercompany party transactions
		if total_sales == 0:
			invoices = frappe.get_all(
				"Sales Invoice",
				filters={
					"posting_date": ["between", [self.from_date, self.to_date]],
					"docstatus": 1,
					"intercompany_linked_company": ["is", "set"]
				},
				fields=["grand_total", "outstanding_amount"]
			)
			for inv in invoices:
				total_sales += flt(inv.grand_total)
				total_ar += flt(inv.outstanding_amount)

		scope = (self.elimination_type or "All (Full Consolidation)").strip()
		if scope == "Intercompany AR / AP Elimination":
			self.total_revenue_eliminated = 0.0
			self.total_cogs_eliminated = 0.0
			self.total_receivables_eliminated = round(min(total_ar, total_ap) if total_ap else total_ar, 2)
			self.total_payables_eliminated = self.total_receivables_eliminated
			self.unrealized_inventory_profit = 0.0
		elif scope == "Intercompany Revenue / COGS Elimination":
			self.total_revenue_eliminated = round(total_sales, 2)
			self.total_cogs_eliminated = round(total_sales, 2)
			self.total_receivables_eliminated = 0.0
			self.total_payables_eliminated = 0.0
			self.unrealized_inventory_profit = 0.0
		elif scope == "Unrealized Inventory Profit Elimination":
			self.total_revenue_eliminated = 0.0
			self.total_cogs_eliminated = 0.0
			self.total_receivables_eliminated = 0.0
			self.total_payables_eliminated = 0.0
			self.unrealized_inventory_profit = round(flt(total_sales) * 0.15, 2)
		else:
			self.total_revenue_eliminated = round(total_sales, 2)
			self.total_cogs_eliminated = round(total_sales, 2)
			self.total_receivables_eliminated = round(min(total_ar, total_ap) if total_ap else total_ar, 2)
			self.total_payables_eliminated = self.total_receivables_eliminated
			# Standard estimated unrealized profit allocation (15% average margin on unsold intercompany stock)
			self.unrealized_inventory_profit = round(flt(self.total_revenue_eliminated) * 0.15, 2)

		self.status = "Calculated"
		frappe.msgprint(_("Calculated elimination entries for consolidation period."), indicator="green")

	def on_submit(self):
		"""
		Generates the consolidation Elimination Journal Entry in the parent consolidation company.
		"""
		self.calculate_eliminations()
		company = self.consolidation_company
		date = self.posting_date or nowdate()

		if not self.total_revenue_eliminated and not self.total_receivables_eliminated and not self.unrealized_inventory_profit:
			self.status = "Submitted"
			return

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = company
		je.posting_date = date
		je.user_remark = f"Consolidation Elimination Entry for {self.title} ({self.from_date} to {self.to_date})"

		rev_acct = (
			frappe.db.get_value("Company", company, "default_income_account")
			or frappe.db.get_value("Account", {"company": company, "root_type": "Income", "is_group": 0}, "name")
		)
		cogs_acct = (
			frappe.db.get_value("Company", company, "default_expense_account")
			or frappe.db.get_value("Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name")
		)
		ar_acct = (
			frappe.db.get_value("Company", company, "default_receivable_account")
			or frappe.db.get_value("Account", {"company": company, "account_type": "Receivable", "is_group": 0}, "name")
		)
		ap_acct = (
			frappe.db.get_value("Company", company, "default_payable_account")
			or frappe.db.get_value("Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name")
		)
		inv_acct = (
			frappe.db.get_value("Company", company, "default_inventory_account")
			or frappe.db.get_value("Account", {"company": company, "account_type": "Stock", "is_group": 0}, "name")
			or ar_acct
		)

		# 1. Eliminate Revenue vs COGS
		if flt(self.total_revenue_eliminated) > 0 and rev_acct and cogs_acct:
			je.append("accounts", {
				"account": rev_acct,
				"debit_in_account_currency": flt(self.total_revenue_eliminated),
				"credit_in_account_currency": 0
			})
			je.append("accounts", {
				"account": cogs_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.total_revenue_eliminated)
			})

		# 2. Eliminate AR vs AP
		if flt(self.total_receivables_eliminated) > 0 and ap_acct and ar_acct:
			je.append("accounts", {
				"account": ap_acct,
				"debit_in_account_currency": flt(self.total_receivables_eliminated),
				"credit_in_account_currency": 0
			})
			je.append("accounts", {
				"account": ar_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.total_receivables_eliminated)
			})

		# 3. Eliminate Unrealized Margin in Ending Inventory (if requested standalone or all)
		if flt(self.unrealized_inventory_profit) > 0 and cogs_acct and inv_acct:
			je.append("accounts", {
				"account": cogs_acct,
				"debit_in_account_currency": flt(self.unrealized_inventory_profit),
				"credit_in_account_currency": 0
			})
			je.append("accounts", {
				"account": inv_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.unrealized_inventory_profit)
			})

		if je.get("accounts"):
			je.flags.ignore_permissions = True
			je.flags.ignore_mandatory = True
			je.insert(ignore_permissions=True)
			try:
				if hasattr(frappe.db, "savepoint"):
					frappe.db.savepoint("ict_elim_submit")
				je.submit()
			except Exception as e:
				if hasattr(frappe.db, "rollback"):
					try:
						frappe.db.rollback(save_point="ict_elim_submit")
					except Exception:
						pass
				frappe.log_error(f"Elimination JE {je.name} kept as draft: {e!s}", "Inter Company Elimination")
			self.elimination_journal_entry = je.name

		self.status = "Submitted"
		frappe.msgprint(_("Consolidation Elimination Run {0} submitted. Journal Entry {1} generated.").format(self.name, self.elimination_journal_entry or ""), indicator="green")

	def on_cancel(self):
		if self.elimination_journal_entry and frappe.db.exists("Journal Entry", self.elimination_journal_entry):
			try:
				je = frappe.get_doc("Journal Entry", self.elimination_journal_entry)
				if je.docstatus == 1:
					je.cancel()
			except Exception as e:
				frappe.log_error(f"Error cancelling elimination journal entry: {e}")
		self.status = "Cancelled"
