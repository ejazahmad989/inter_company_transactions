# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


def _compute_netting(doc):
	"""Compute multilateral netting positions and settlements for an InterCompanyNettingCycle document."""
	company_stats = {}
	for row in doc.participating_companies:
		company_stats[row.company] = {
			"gross_payables": 0.0,
			"gross_receivables": 0.0,
			"net_balance": 0.0
		}

	has_invoices = bool(doc.invoices)
	if has_invoices:
		for inv in (doc.invoices or []):
			amt = flt(inv.settled_amount or inv.outstanding_amount)
			if inv.invoice_type == "Sales Invoice":
				if inv.company in company_stats:
					company_stats[inv.company]["gross_receivables"] += amt
				if inv.partner_company in company_stats:
					company_stats[inv.partner_company]["gross_payables"] += amt
			elif inv.invoice_type == "Purchase Invoice":
				if inv.company in company_stats:
					company_stats[inv.company]["gross_payables"] += amt
				if inv.partner_company in company_stats:
					company_stats[inv.partner_company]["gross_receivables"] += amt
	else:
		# Allow manual participating_companies net_balance / gross inputs directly
		for row in doc.participating_companies:
			net_val = flt(getattr(row, "net_balance", 0))
			gross_rec = flt(getattr(row, "gross_receivables", 0))
			gross_pay = flt(getattr(row, "gross_payables", 0))
			if gross_rec > 0 or gross_pay > 0:
				company_stats[row.company]["gross_receivables"] = gross_rec
				company_stats[row.company]["gross_payables"] = gross_pay
			elif net_val > 0:
				company_stats[row.company]["gross_receivables"] = net_val
			elif net_val < 0:
				company_stats[row.company]["gross_payables"] = abs(net_val)

	total_payables = 0.0
	total_receivables = 0.0

	for row in doc.participating_companies:
		stats = company_stats.get(row.company, {})
		row.gross_payables = stats.get("gross_payables", 0.0)
		row.gross_receivables = stats.get("gross_receivables", 0.0)
		row.net_balance = row.gross_receivables - row.gross_payables
		total_payables += row.gross_payables
		total_receivables += row.gross_receivables

		if row.net_balance > 0.01:
			row.settlement_position = "Net Creditor"
		elif row.net_balance < -0.01:
			row.settlement_position = "Net Debtor"
		else:
			row.settlement_position = "Balanced"

	doc.total_gross_payables = total_payables
	doc.total_gross_receivables = total_receivables

	# Multilateral Settlement Solver (Greedy Knapsack Matching)
	debtors = []  # owes money: net_balance < 0
	creditors = []  # owed money: net_balance > 0

	for row in doc.participating_companies:
		if row.net_balance < -0.01:
			debtors.append({"company": row.company, "amount": abs(row.net_balance)})
		elif row.net_balance > 0.01:
			creditors.append({"company": row.company, "amount": row.net_balance})

	doc.net_settlements = []
	d_idx = 0
	c_idx = 0
	total_net = 0.0

	while d_idx < len(debtors) and c_idx < len(creditors):
		debtor = debtors[d_idx]
		creditor = creditors[c_idx]

		settle_amt = min(debtor["amount"], creditor["amount"])
		if settle_amt > 0.01:
			company_currency = frappe.get_cached_value("Company", debtor["company"], "default_currency")
			doc.append("net_settlements", {
				"paying_company": debtor["company"],
				"receiving_company": creditor["company"],
				"amount": round(settle_amt, 2),
				"currency": company_currency,
				"status": "Pending"
			})
			total_net += settle_amt
			debtor["amount"] -= settle_amt
			creditor["amount"] -= settle_amt

		if debtor["amount"] <= 0.01:
			d_idx += 1
		if creditor["amount"] <= 0.01:
			c_idx += 1

	doc.total_net_settled = round(total_net, 2)
	doc.status = "Calculated"


class InterCompanyNettingCycle(Document):
	def validate(self):
		if not self.participating_companies:
			frappe.throw(_("Please add at least two participating companies for multilateral netting."))

	@frappe.whitelist()
	def fetch_open_invoices(self):
		"""
		Fetches all outstanding intercompany Sales and Purchase Invoices
		between the participating entities.
		"""
		self.check_permission("write")
		companies = [row.company for row in self.participating_companies if row.company]
		if len(companies) < 2:
			frappe.throw(_("At least two participating companies are required."))

		self.invoices = []

		# Get linked company relationships
		links = frappe.get_all(
			"Intercompany Linked Company",
			filters={"company": ["in", companies]},
			fields=["parent", "company", "main_company_customer", "main_company_supplier", "other_company_customer", "other_company_supplier"]
		)

		company_pairs = {}
		for link in links:
			parent_link = frappe.get_value("Intercompany Transaction Link", link.parent, "main_company")
			if parent_link in companies and link.company in companies:
				company_pairs[(parent_link, link.company)] = {
					"customer_in_other": link.other_company_customer,
					"supplier_in_other": link.other_company_supplier,
					"customer_in_main": link.main_company_customer,
					"supplier_in_main": link.main_company_supplier
				}

		# Fetch open Sales Invoices
		sales_invoices = frappe.get_all(
			"Sales Invoice",
			filters={
				"company": ["in", companies],
				"docstatus": 1,
				"outstanding_amount": [">", 0]
			},
			fields=["name", "company", "customer", "outstanding_amount", "currency"]
		)

		for inv in sales_invoices:
			# Check which sister company this customer represents
			for (main_co, other_co), mapping in company_pairs.items():
				partner = None
				if inv.company == main_co and inv.customer == mapping["customer_in_main"]:
					partner = other_co
				elif inv.company == other_co and inv.customer == mapping["customer_in_other"]:
					partner = main_co

				if partner and partner in companies:
					self.append("invoices", {
						"company": inv.company,
						"partner_company": partner,
						"invoice_type": "Sales Invoice",
						"invoice_name": inv.name,
						"outstanding_amount": inv.outstanding_amount,
						"currency": inv.currency,
						"settled_amount": inv.outstanding_amount
					})

		# Fetch open Purchase Invoices
		purchase_invoices = frappe.get_all(
			"Purchase Invoice",
			filters={
				"company": ["in", companies],
				"docstatus": 1,
				"outstanding_amount": [">", 0]
			},
			fields=["name", "company", "supplier", "outstanding_amount", "currency"]
		)

		for inv in purchase_invoices:
			for (main_co, other_co), mapping in company_pairs.items():
				partner = None
				if inv.company == main_co and inv.supplier == mapping["supplier_in_main"]:
					partner = other_co
				elif inv.company == other_co and inv.supplier == mapping["supplier_in_other"]:
					partner = main_co

				if partner and partner in companies:
					self.append("invoices", {
						"company": inv.company,
						"partner_company": partner,
						"invoice_type": "Purchase Invoice",
						"invoice_name": inv.name,
						"outstanding_amount": inv.outstanding_amount,
						"currency": inv.currency,
						"settled_amount": inv.outstanding_amount
					})

		_compute_netting(self)
		frappe.msgprint(_("Fetched {0} open inter-company invoices.").format(len(self.invoices)), indicator="green")

	@frappe.whitelist()
	def calculate_netting(self):
		"""
		Executes Multilateral Netting Algorithm:
		Calculates gross receivables, gross payables, and net position for each company,
		then resolves debtor-creditor settlements minimizing bank transactions.
		"""
		self.check_permission("write")
		_compute_netting(self)

	def on_submit(self):
		"""
		On Submission:
		Creates the clearing Journal Entries between the net settlement entities
		and persists status and settlement_entry references cleanly to DB.
		"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			get_or_create_intercompany_clearing_account,
		)

		_compute_netting(self)
		date = self.settlement_date or nowdate()

		self.db_set({
			"total_gross_payables": flt(self.total_gross_payables),
			"total_gross_receivables": flt(self.total_gross_receivables),
			"total_net_settled": flt(self.total_net_settled),
		}, update_modified=False)

		for settlement in self.net_settlements:
			payer = settlement.paying_company
			receiver = settlement.receiving_company
			amt = flt(settlement.amount)

			if amt <= 0.01:
				continue

			# Create intercompany clearing entry
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Journal Entry"
			je.company = payer
			je.posting_date = date
			je.user_remark = f"Multilateral Netting Settlement for Cycle {self.name}: Paid to {receiver}"

			clearing_account_payer = None
			receiver_supplier = None
			parent_link = frappe.get_value("Intercompany Transaction Link", {"main_company": payer}, "name")
			if parent_link:
				row_data = frappe.get_value(
					"Intercompany Linked Company",
					{"parent": parent_link, "company": receiver},
					["main_company_account", "main_company_supplier"],
					as_dict=True,
				)
				if row_data:
					clearing_account_payer = row_data.get("main_company_account")
					receiver_supplier = row_data.get("main_company_supplier")

			if not clearing_account_payer:
				clearing_account_payer = get_or_create_intercompany_clearing_account(payer, receiver)

			payable_acct = frappe.get_value("Company", payer, "default_payable_account")
			bank_or_cash_acct = (
				frappe.get_value("Company", payer, "default_bank_account")
				or frappe.get_value("Company", payer, "default_cash_account")
			)

			if payable_acct and receiver_supplier:
				debit_row = {
					"account": payable_acct,
					"party_type": "Supplier",
					"party": receiver_supplier,
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
				}
			elif bank_or_cash_acct:
				debit_row = {
					"account": bank_or_cash_acct,
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
				}
			else:
				debit_row = {
					"account": payable_acct or clearing_account_payer,
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
				}

			if clearing_account_payer and debit_row.get("account"):
				je.append("accounts", debit_row)
				je.append("accounts", {
					"account": clearing_account_payer,
					"debit_in_account_currency": 0,
					"credit_in_account_currency": amt,
				})
				je.flags.ignore_permissions = True
				je.flags.ignore_mandatory = True
				je.insert(ignore_permissions=True)
				try:
					if hasattr(frappe.db, "savepoint"):
						frappe.db.savepoint("ict_netting_submit")
					je.submit()
					settlement.status = "Settled"
				except Exception as e:
					if hasattr(frappe.db, "rollback"):
						try:
							frappe.db.rollback(save_point="ict_netting_submit")
						except Exception:
							pass
					frappe.log_error(f"Netting settlement JE {je.name} kept as draft: {e!s}", "Inter Company Netting")
					settlement.status = "Pending"
				settlement.settlement_entry = je.name
				settlement.db_set({
					"status": settlement.status,
					"settlement_entry": je.name,
				}, update_modified=False)

		self.status = "Settled"
		self.db_set("status", "Settled", update_modified=False)
		frappe.msgprint(_("Multilateral Netting Cycle {0} submitted. Settlement entries generated.").format(self.name), indicator="green")

	def on_cancel(self):
		"""Cancel associated settlement vouchers"""
		for settlement in self.net_settlements:
			if settlement.settlement_entry and frappe.db.exists("Journal Entry", settlement.settlement_entry):
				try:
					doc = frappe.get_doc("Journal Entry", settlement.settlement_entry)
					if doc.docstatus == 1:
						doc.cancel()
				except Exception as e:
					frappe.log_error(f"Error cancelling netting settlement entry {settlement.settlement_entry}: {e}")
		self.status = "Cancelled"
		self.db_set("status", "Cancelled", update_modified=False)
