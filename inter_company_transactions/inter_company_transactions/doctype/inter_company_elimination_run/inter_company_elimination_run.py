# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


def _get_intercompany_invoice_names():
	"""Return sets of intercompany Sales Invoice and Purchase Invoice names from document references."""
	si_names = set()
	pi_names = set()
	if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Inter Company Document Reference")):
		return si_names, pi_names

	refs = frappe.get_all(
		"Inter Company Document Reference",
		filters={
			"source_doctype": ["in", ["Sales Invoice", "Purchase Invoice"]],
		},
		fields=["source_doctype", "source_name", "target_doctype", "target_name"],
	)
	for ref in refs:
		if ref.source_doctype == "Sales Invoice" and ref.source_name:
			si_names.add(ref.source_name)
		elif ref.source_doctype == "Purchase Invoice" and ref.source_name:
			pi_names.add(ref.source_name)
		if ref.target_doctype == "Sales Invoice" and ref.target_name:
			si_names.add(ref.target_name)
		elif ref.target_doctype == "Purchase Invoice" and ref.target_name:
			pi_names.add(ref.target_name)
	return si_names, pi_names


def _convert_to_consolidation_currency(amount, from_currency, target_currency, tx_date):
	amt = flt(amount)
	if not amt or not from_currency or not target_currency or from_currency == target_currency:
		return amt

	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency import (
		get_intercompany_exchange_rate,
	)

	rate = get_intercompany_exchange_rate(from_currency, target_currency, tx_date, raise_if_missing=True)
	return flt(amt) * flt(rate)


def _compute_eliminations(doc):
	"""Compute consolidation elimination totals on an InterCompanyEliminationRun document using posting_date."""
	consol_ccy = (
		frappe.get_cached_value("Company", doc.consolidation_company, "default_currency")
		if doc.consolidation_company and hasattr(frappe, "db") and frappe.db
		else None
	)
	fx_date = doc.posting_date or doc.to_date or nowdate()

	ref_si_names, ref_pi_names = _get_intercompany_invoice_names()

	si_filters = {
		"posting_date": ["between", [doc.from_date, doc.to_date]],
		"docstatus": 1,
	}
	si_or_filters = []
	if ref_si_names:
		si_or_filters.append(["name", "in", list(ref_si_names)])
	if frappe.db.has_column("Sales Invoice", "intercompany_linked_company"):
		si_or_filters.append(["intercompany_linked_company", "is", "set"])
	if frappe.db.has_column("Sales Invoice", "is_intercompany"):
		si_or_filters.append(["is_intercompany", "=", 1])

	sales_invoices = (
		frappe.get_all(
			"Sales Invoice",
			filters=si_filters,
			or_filters=si_or_filters if si_or_filters else None,
			fields=["name", "company", "currency", "grand_total", "outstanding_amount"],
		)
		if si_or_filters
		else []
	)

	total_sales = 0.0
	total_ar = 0.0
	seen_si = set()
	for inv in sales_invoices:
		if inv.name in seen_si:
			continue
		seen_si.add(inv.name)
		inv_ccy = inv.currency or (
			frappe.get_cached_value("Company", inv.company, "default_currency") if inv.company else consol_ccy
		)
		total_sales += _convert_to_consolidation_currency(inv.grand_total, inv_ccy, consol_ccy, fx_date)
		total_ar += _convert_to_consolidation_currency(inv.outstanding_amount, inv_ccy, consol_ccy, fx_date)

	pi_filters = {
		"posting_date": ["between", [doc.from_date, doc.to_date]],
		"docstatus": 1,
	}
	pi_or_filters = []
	if ref_pi_names:
		pi_or_filters.append(["name", "in", list(ref_pi_names)])
	if frappe.db.has_column("Purchase Invoice", "intercompany_linked_company"):
		pi_or_filters.append(["intercompany_linked_company", "is", "set"])
	if frappe.db.has_column("Purchase Invoice", "is_intercompany"):
		pi_or_filters.append(["is_intercompany", "=", 1])

	purchase_invoices = (
		frappe.get_all(
			"Purchase Invoice",
			filters=pi_filters,
			or_filters=pi_or_filters if pi_or_filters else None,
			fields=["name", "company", "currency", "outstanding_amount"],
		)
		if pi_or_filters
		else []
	)

	total_ap = 0.0
	seen_pi = set()
	for pinv in purchase_invoices:
		if pinv.name in seen_pi:
			continue
		seen_pi.add(pinv.name)
		pinv_ccy = pinv.currency or (
			frappe.get_cached_value("Company", pinv.company, "default_currency") if pinv.company else consol_ccy
		)
		total_ap += _convert_to_consolidation_currency(pinv.outstanding_amount, pinv_ccy, consol_ccy, fx_date)

	matched_ar_ap = round(min(total_ar, total_ap) if (total_ar > 0 and total_ap > 0) else 0.0, 2)

	scope = (doc.elimination_type or "All (Full Consolidation)").strip()
	if scope == "Intercompany AR / AP Elimination":
		doc.total_revenue_eliminated = 0.0
		doc.total_cogs_eliminated = 0.0
		doc.total_receivables_eliminated = matched_ar_ap
		doc.total_payables_eliminated = matched_ar_ap
		doc.unrealized_inventory_profit = 0.0
	elif scope == "Intercompany Revenue / COGS Elimination":
		doc.total_revenue_eliminated = round(total_sales, 2)
		doc.total_cogs_eliminated = round(total_sales, 2)
		doc.total_receivables_eliminated = 0.0
		doc.total_payables_eliminated = 0.0
		doc.unrealized_inventory_profit = 0.0
	elif scope == "Unrealized Inventory Profit Elimination":
		doc.total_revenue_eliminated = 0.0
		doc.total_cogs_eliminated = 0.0
		doc.total_receivables_eliminated = 0.0
		doc.total_payables_eliminated = 0.0
		# Preserve any user-calculated or zero unrealized profit instead of fabricating a percentage
		doc.unrealized_inventory_profit = round(flt(getattr(doc, "unrealized_inventory_profit", 0.0)), 2)
	else:
		doc.total_revenue_eliminated = round(total_sales, 2)
		doc.total_cogs_eliminated = round(total_sales, 2)
		doc.total_receivables_eliminated = matched_ar_ap
		doc.total_payables_eliminated = matched_ar_ap
		doc.unrealized_inventory_profit = round(flt(getattr(doc, "unrealized_inventory_profit", 0.0)), 2)

	doc.status = "Calculated"


def _resolve_non_cash_elimination_accounts(company):
	"""
	Resolve non-party, non-Bank/non-Cash Asset and Liability accounts for AR/AP consolidation elimination.
	Never uses default_bank_account or default_cash_account.
	"""
	asset_acct = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Asset",
			"is_group": 0,
			"account_type": ["not in", ["Bank", "Cash", "Receivable", "Payable"]],
			"account_name": ["like", "%Elimination%"],
		},
		"name",
	) or frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Asset",
			"is_group": 0,
			"account_type": ["not in", ["Bank", "Cash", "Receivable", "Payable"]],
		},
		"name",
	)

	liability_acct = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Liability",
			"is_group": 0,
			"account_type": ["not in", ["Bank", "Cash", "Receivable", "Payable"]],
			"account_name": ["like", "%Elimination%"],
		},
		"name",
	) or frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Liability",
			"is_group": 0,
			"account_type": ["not in", ["Bank", "Cash", "Receivable", "Payable"]],
		},
		"name",
	)

	return asset_acct, liability_acct


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
		3. Leaves unrealized inventory margin at 0.0 unless explicitly quantified.
		"""
		self.check_permission("write")
		_compute_eliminations(self)
		frappe.msgprint(_("Calculated elimination entries for consolidation period."), indicator="green")

	def on_submit(self):
		"""
		Generates the consolidation Elimination Journal Entry in the parent consolidation company
		using non-Bank/non-Cash elimination control accounts and persists totals cleanly via db_set.
		"""
		_compute_eliminations(self)
		company = self.consolidation_company
		date = self.posting_date or nowdate()

		self.db_set({
			"total_revenue_eliminated": flt(self.total_revenue_eliminated),
			"total_cogs_eliminated": flt(self.total_cogs_eliminated),
			"total_receivables_eliminated": flt(self.total_receivables_eliminated),
			"total_payables_eliminated": flt(self.total_payables_eliminated),
			"unrealized_inventory_profit": flt(self.unrealized_inventory_profit),
		}, update_modified=False)

		if not self.total_revenue_eliminated and not self.total_receivables_eliminated and not self.unrealized_inventory_profit:
			self.status = "Submitted"
			self.db_set("status", "Submitted", update_modified=False)
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
		inv_acct = (
			frappe.db.get_value("Company", company, "default_inventory_account")
			or frappe.db.get_value("Account", {"company": company, "account_type": "Stock", "is_group": 0}, "name")
		)

		elim_asset_acct, elim_liability_acct = _resolve_non_cash_elimination_accounts(company)

		# 1. Eliminate Revenue vs COGS
		if flt(self.total_revenue_eliminated) > 0:
			if not (rev_acct and cogs_acct):
				frappe.throw(
					_("Default Income and Expense/COGS accounts are required on company {0} to eliminate Revenue/COGS.").format(company)
				)
			je.append("accounts", {
				"account": rev_acct,
				"debit_in_account_currency": flt(self.total_revenue_eliminated),
				"credit_in_account_currency": 0,
			})
			je.append("accounts", {
				"account": cogs_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.total_revenue_eliminated),
			})

		# 2. Eliminate AR vs AP (via non-Bank/non-Cash Asset and Liability elimination accounts)
		if flt(self.total_receivables_eliminated) > 0:
			if not (elim_liability_acct and elim_asset_acct):
				frappe.throw(
					_("Non-cash Asset and Liability elimination accounts are required on company {0} to eliminate AR/AP balances.").format(company)
				)
			je.append("accounts", {
				"account": elim_liability_acct,
				"debit_in_account_currency": flt(self.total_receivables_eliminated),
				"credit_in_account_currency": 0,
			})
			je.append("accounts", {
				"account": elim_asset_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.total_receivables_eliminated),
			})

		# 3. Eliminate Unrealized Margin in Ending Inventory (only when explicitly quantified)
		if flt(self.unrealized_inventory_profit) > 0:
			if not (cogs_acct and inv_acct):
				frappe.throw(
					_("Default COGS/Expense and Stock Inventory accounts are required on company {0} to eliminate unrealized inventory margin.").format(company)
				)
			je.append("accounts", {
				"account": cogs_acct,
				"debit_in_account_currency": flt(self.unrealized_inventory_profit),
				"credit_in_account_currency": 0,
			})
			je.append("accounts", {
				"account": inv_acct,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": flt(self.unrealized_inventory_profit),
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
			self.db_set("elimination_journal_entry", je.name, update_modified=False)

		self.status = "Submitted"
		self.db_set("status", "Submitted", update_modified=False)
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
		self.db_set("status", "Cancelled", update_modified=False)
