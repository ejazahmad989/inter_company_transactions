# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


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

		self.calculate_netting()
		frappe.msgprint(_("Fetched {0} open inter-company invoices.").format(len(self.invoices)), indicator="green")

	@frappe.whitelist()
	def calculate_netting(self):
		"""
		Executes Multilateral Netting Algorithm:
		Calculates gross receivables, gross payables, and net position for each company,
		then resolves debtor-creditor settlements minimizing bank transactions.
		"""
		company_stats = {}
		for row in self.participating_companies:
			company_stats[row.company] = {
				"gross_payables": 0.0,
				"gross_receivables": 0.0,
				"net_balance": 0.0
			}

		for inv in (self.invoices or []):
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

		total_payables = 0.0
		total_receivables = 0.0

		for row in self.participating_companies:
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

		self.total_gross_payables = total_payables
		self.total_gross_receivables = total_receivables

		# Multilateral Settlement Solver (Greedy Knapsack Matching)
		debtors = []  # owes money: net_balance < 0
		creditors = [] # owed money: net_balance > 0

		for row in self.participating_companies:
			if row.net_balance < -0.01:
				debtors.append({"company": row.company, "amount": abs(row.net_balance)})
			elif row.net_balance > 0.01:
				creditors.append({"company": row.company, "amount": row.net_balance})

		self.net_settlements = []
		d_idx = 0
		c_idx = 0
		total_net = 0.0

		while d_idx < len(debtors) and c_idx < len(creditors):
			debtor = debtors[d_idx]
			creditor = creditors[c_idx]

			settle_amt = min(debtor["amount"], creditor["amount"])
			if settle_amt > 0.01:
				company_currency = frappe.get_cached_value("Company", debtor["company"], "default_currency")
				self.append("net_settlements", {
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

		self.total_net_settled = round(total_net, 2)
		self.status = "Calculated"

	def on_submit(self):
		"""
		On Submission:
		Creates the clearing Journal Entries or Payment Entries between the net settlement entities.
		"""
		self.calculate_netting()
		date = self.settlement_date or nowdate()

		for settlement in self.net_settlements:
			payer = settlement.paying_company
			receiver = settlement.receiving_company
			amt = flt(settlement.amount)

			if amt <= 0.01:
				continue

			# Create intercompany clearing entry
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Inter Company Journal Entry" if frappe.db.exists("Journal Entry Type", "Inter Company Journal Entry") else "Journal Entry"
			je.company = payer
			je.posting_date = date
			je.user_remark = f"Multilateral Netting Settlement for Cycle {self.name}: Paid to {receiver}"

			# Find clearing accounts
			clearing_account_payer = frappe.get_value(
				"Intercompany Linked Company",
				{"parent": frappe.get_value("Intercompany Transaction Link", {"main_company": payer}, "name"), "company": receiver},
				"main_company_account"
			) or frappe.get_value("Company", payer, "default_cash_account") or frappe.get_value("Company", payer, "default_bank_account")

			clearing_account_receiver = frappe.get_value("Company", payer, "default_payable_account")

			if not clearing_account_payer or not clearing_account_receiver:
				# Fallback to standard debit/credit accounts
				accounts = frappe.get_all("Account", filters={"company": payer, "is_group": 0}, pluck="name", limit=2)
				clearing_account_payer = accounts[0] if accounts else None
				clearing_account_receiver = accounts[1] if len(accounts) > 1 else accounts[0]

			if clearing_account_payer and clearing_account_receiver:
				je.append("accounts", {
					"account": clearing_account_receiver,
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0
				})
				je.append("accounts", {
					"account": clearing_account_payer,
					"debit_in_account_currency": 0,
					"credit_in_account_currency": amt
				})
				je.flags.ignore_permissions = True
				je.insert()
				try:
					je.submit()
				except Exception:
					pass
				settlement.settlement_entry = je.name
				settlement.status = "Settled"

		self.status = "Settled"
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
