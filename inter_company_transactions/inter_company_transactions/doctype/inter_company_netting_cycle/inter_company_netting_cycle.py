# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


def _get_cycle_currency(doc):
	"""Resolve a single common reporting/settlement currency for the netting cycle."""
	for row in (getattr(doc, "participating_companies", None) or []):
		comp = row.get("company") if isinstance(row, dict) else getattr(row, "company", None)
		if comp and hasattr(frappe, "db") and frappe.db:
			ccy = frappe.get_cached_value("Company", comp, "default_currency")
			if ccy:
				return ccy
	for inv in (getattr(doc, "invoices", None) or []):
		ccy = inv.get("currency") if isinstance(inv, dict) else getattr(inv, "currency", None)
		if ccy:
			return ccy
	return None


def _get_mirrored_invoice_link_set(invoices):
	"""Return set of (invoice_type, invoice_name) rows that are already represented by a counterpart in invoices."""
	skip_keys = set()
	if not invoices or not (hasattr(frappe, "db") and frappe.db):
		return skip_keys

	si_names = {
		inv.get("invoice_name")
		for inv in invoices
		if inv.get("invoice_type") == "Sales Invoice" and inv.get("invoice_name")
	}
	pi_names = {
		inv.get("invoice_name")
		for inv in invoices
		if inv.get("invoice_type") == "Purchase Invoice" and inv.get("invoice_name")
	}
	if not (si_names and pi_names):
		return skip_keys

	if frappe.db.table_exists("Inter Company Document Reference"):
		refs = frappe.get_all(
			"Inter Company Document Reference",
			filters={
				"source_doctype": ["in", ["Sales Invoice", "Purchase Invoice"]],
				"target_doctype": ["in", ["Sales Invoice", "Purchase Invoice"]],
			},
			fields=["source_doctype", "source_name", "target_doctype", "target_name"],
		)
		for ref in refs:
			if (
				ref.source_doctype == "Sales Invoice"
				and ref.target_doctype == "Purchase Invoice"
				and ref.source_name in si_names
				and ref.target_name in pi_names
			):
				skip_keys.add(("Purchase Invoice", ref.target_name))
			elif (
				ref.source_doctype == "Purchase Invoice"
				and ref.target_doctype == "Sales Invoice"
				and ref.source_name in pi_names
				and ref.target_name in si_names
			):
				skip_keys.add(("Purchase Invoice", ref.source_name))

	if frappe.db.has_column("Purchase Invoice", "intercompany_linked_doc_name"):
		pi_links = frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", list(pi_names)]},
			fields=["name", "intercompany_linked_doc_doctype", "intercompany_linked_doc_name"],
		)
		for pi in pi_links:
			if pi.get("intercompany_linked_doc_doctype") == "Sales Invoice" and pi.get("intercompany_linked_doc_name") in si_names:
				skip_keys.add(("Purchase Invoice", pi.name))

	if frappe.db.has_column("Sales Invoice", "intercompany_linked_doc_name"):
		si_links = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", list(si_names)]},
			fields=["name", "intercompany_linked_doc_doctype", "intercompany_linked_doc_name"],
		)
		for si in si_links:
			if si.get("intercompany_linked_doc_doctype") == "Purchase Invoice" and si.get("intercompany_linked_doc_name") in pi_names:
				skip_keys.add(("Purchase Invoice", si.get("intercompany_linked_doc_name")))

	return skip_keys


def _convert_cycle_amount(amount, from_currency, to_currency, tx_date):
	"""Convert invoice amount into cycle currency cleanly, requiring FX rate if currencies differ."""
	amt = flt(amount)
	if not amt or not from_currency or not to_currency or from_currency == to_currency:
		return amt

	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency import (
		get_intercompany_exchange_rate,
	)

	rate = get_intercompany_exchange_rate(from_currency, to_currency, tx_date, raise_if_missing=True)
	return round(amt * flt(rate), 2)


def _compute_netting(doc):
	"""Compute multilateral netting positions and settlements for an InterCompanyNettingCycle document."""
	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_currency import (
		get_intercompany_exchange_rate,
	)

	company_stats = {}
	for row in doc.participating_companies:
		company_stats[row.company] = {
			"gross_payables": 0.0,
			"gross_receivables": 0.0,
			"net_balance": 0.0,
		}

	cycle_currency = _get_cycle_currency(doc)
	settlement_date = getattr(doc, "settlement_date", None) or nowdate()

	has_invoices = bool(doc.invoices)
	if has_invoices:
		mirrored_skip_keys = _get_mirrored_invoice_link_set(doc.invoices)
		seen_invoices = set()
		for inv in (doc.invoices or []):
			inv_key = (inv.invoice_type, inv.invoice_name)
			if inv.invoice_name:
				if inv_key in seen_invoices or inv_key in mirrored_skip_keys:
					continue
				seen_invoices.add(inv_key)

			raw_amt = flt(getattr(inv, "settled_amount", None) or getattr(inv, "outstanding_amount", None) or (inv.get("settled_amount") if isinstance(inv, dict) else 0) or (inv.get("outstanding_amount") if isinstance(inv, dict) else 0))
			inv_currency = getattr(inv, "currency", None) or (inv.get("currency") if isinstance(inv, dict) else None)
			if not inv_currency and inv.company and hasattr(frappe, "db") and frappe.db:
				inv_currency = frappe.get_cached_value("Company", inv.company, "default_currency")
			if inv_currency and cycle_currency and inv_currency != cycle_currency:
				rate = get_intercompany_exchange_rate(inv_currency, cycle_currency, settlement_date, raise_if_missing=True)
				amt = round(raw_amt * flt(rate), 2)
			else:
				amt = raw_amt

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
		row.gross_payables = round(stats.get("gross_payables", 0.0), 2)
		row.gross_receivables = round(stats.get("gross_receivables", 0.0), 2)
		row.net_balance = round(row.gross_receivables - row.gross_payables, 2)
		total_payables += row.gross_payables
		total_receivables += row.gross_receivables

		if row.net_balance > 0.01:
			row.settlement_position = "Net Creditor"
		elif row.net_balance < -0.01:
			row.settlement_position = "Net Debtor"
		else:
			row.settlement_position = "Balanced"

	doc.total_gross_payables = round(total_payables, 2)
	doc.total_gross_receivables = round(total_receivables, 2)

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
			settle_currency = cycle_currency or (
				frappe.get_cached_value("Company", debtor["company"], "default_currency")
				if hasattr(frappe, "db") and frappe.db
				else None
			)
			doc.append("net_settlements", {
				"paying_company": debtor["company"],
				"receiving_company": creditor["company"],
				"amount": round(settle_amt, 2),
				"currency": settle_currency,
				"status": "Pending",
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


def _resolve_netting_clearing_and_supplier(doc, payer, receiver):
	"""Symmetrically resolve payer's clearing account and supplier representing receiver."""
	clearing_account_payer = None
	receiver_supplier = None

	for row in (getattr(doc, "participating_companies", None) or []):
		if getattr(row, "company", None) == payer and getattr(row, "clearing_account", None):
			clearing_account_payer = row.clearing_account
			break

	if hasattr(frappe, "db") and frappe.db:
		parent_link = frappe.get_value("Intercompany Transaction Link", {"main_company": payer}, "name")
		if parent_link:
			row_data = frappe.get_value(
				"Intercompany Linked Company",
				{"parent": parent_link, "company": receiver},
				["main_company_account", "main_company_supplier"],
				as_dict=True,
			)
			if row_data:
				clearing_account_payer = clearing_account_payer or row_data.get("main_company_account")
				receiver_supplier = row_data.get("main_company_supplier")

		if not receiver_supplier or not clearing_account_payer:
			rev_parent = frappe.get_value("Intercompany Transaction Link", {"main_company": receiver}, "name")
			if rev_parent:
				rev_row = frappe.get_value(
					"Intercompany Linked Company",
					{"parent": rev_parent, "company": payer},
					["other_company_account", "other_company_supplier"],
					as_dict=True,
				)
				if rev_row:
					clearing_account_payer = clearing_account_payer or rev_row.get("other_company_account")
					receiver_supplier = receiver_supplier or rev_row.get("other_company_supplier")

	return clearing_account_payer, receiver_supplier


def _resolve_netting_clearing_and_customer(doc, receiver, payer):
	"""Symmetrically resolve receiver's clearing account and customer representing payer."""
	clearing_account_receiver = None
	payer_customer = None

	for row in (getattr(doc, "participating_companies", None) or []):
		if getattr(row, "company", None) == receiver and getattr(row, "clearing_account", None):
			clearing_account_receiver = row.clearing_account
			break

	if hasattr(frappe, "db") and frappe.db:
		parent_link = frappe.get_value("Intercompany Transaction Link", {"main_company": receiver}, "name")
		if parent_link:
			row_data = frappe.get_value(
				"Intercompany Linked Company",
				{"parent": parent_link, "company": payer},
				["main_company_account", "main_company_customer"],
				as_dict=True,
			)
			if row_data:
				clearing_account_receiver = clearing_account_receiver or row_data.get("main_company_account")
				payer_customer = row_data.get("main_company_customer")

		if not payer_customer or not clearing_account_receiver:
			rev_parent = frappe.get_value("Intercompany Transaction Link", {"main_company": payer}, "name")
			if rev_parent:
				rev_row = frappe.get_value(
					"Intercompany Linked Company",
					{"parent": rev_parent, "company": receiver},
					["other_company_account", "other_company_customer"],
					as_dict=True,
				)
				if rev_row:
					clearing_account_receiver = clearing_account_receiver or rev_row.get("other_company_account")
					payer_customer = payer_customer or rev_row.get("other_company_customer")

	return clearing_account_receiver, payer_customer


def _collect_pair_open_invoices_for_settlement(doc, company, partner_company, invoice_type, target_currency, tx_date):
	"""Collect open invoices for a (company, partner_company) side to reference on the netting Journal Entry."""
	refs = []
	seen = set()
	for inv in (getattr(doc, "invoices", None) or []):
		inv_dt = getattr(inv, "invoice_type", None) or (inv.get("invoice_type") if isinstance(inv, dict) else None)
		inv_name = getattr(inv, "invoice_name", None) or (inv.get("invoice_name") if isinstance(inv, dict) else None)
		inv_co = getattr(inv, "company", None) or (inv.get("company") if isinstance(inv, dict) else None)
		inv_partner = getattr(inv, "partner_company", None) or (inv.get("partner_company") if isinstance(inv, dict) else None)
		if not inv_name:
			continue

		matched_name = None
		matched_ccy = getattr(inv, "currency", None) or (inv.get("currency") if isinstance(inv, dict) else None)
		raw_amt = flt(
			getattr(inv, "settled_amount", None)
			or getattr(inv, "outstanding_amount", None)
			or (inv.get("settled_amount") if isinstance(inv, dict) else 0)
			or (inv.get("outstanding_amount") if isinstance(inv, dict) else 0)
		)

		if inv_dt == invoice_type and inv_co == company and inv_partner == partner_company:
			matched_name = inv_name
		elif (
			inv_co == partner_company
			and inv_partner == company
			and inv_dt in ("Sales Invoice", "Purchase Invoice")
			and inv_dt != invoice_type
			and hasattr(frappe, "db")
			and frappe.db
			and frappe.db.table_exists("Inter Company Document Reference")
		):
			cp_name = (
				frappe.db.get_value(
					"Inter Company Document Reference",
					{"source_doctype": inv_dt, "source_name": inv_name, "target_doctype": invoice_type, "target_company": company},
					"target_name",
				)
				or frappe.db.get_value(
					"Inter Company Document Reference",
					{"target_doctype": inv_dt, "target_name": inv_name, "source_doctype": invoice_type, "source_company": company},
					"source_name",
				)
			)
			if cp_name:
				cp_info = frappe.db.get_value(invoice_type, cp_name, ["docstatus", "outstanding_amount", "currency"], as_dict=True)
				if isinstance(cp_info, dict) and cp_info.get("docstatus") == 1 and flt(cp_info.get("outstanding_amount")) > 0:
					matched_name = cp_name
					raw_amt = flt(cp_info.get("outstanding_amount"))
					matched_ccy = cp_info.get("currency") or matched_ccy

		if matched_name and matched_name not in seen and raw_amt > 0.01:
			seen.add(matched_name)
			amt = _convert_cycle_amount(raw_amt, matched_ccy, target_currency, tx_date)
			if amt > 0.01:
				refs.append({"doctype": invoice_type, "name": matched_name, "amount": amt})

	return refs


def _append_allocated_party_rows(je, account, side, total_amount, company_currency, tx_date, party_type, party, invoice_refs):
	"""Append party JE rows linked against open invoices up to total_amount, with remainder unallocated."""
	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_accounting_builders import (
		_build_je_row,
	)

	remaining = flt(total_amount, 2)
	for ref in (invoice_refs or []):
		if remaining <= 0.01:
			break
		alloc = min(remaining, flt(ref["amount"], 2))
		if alloc <= 0.01:
			continue
		row = _build_je_row(
			account,
			side,
			alloc,
			company_currency,
			tx_date=tx_date,
			party_type=party_type,
			party=party,
		)
		row["reference_type"] = ref["doctype"]
		row["reference_name"] = ref["name"]
		je.append("accounts", row)
		remaining = flt(remaining - alloc, 2)

	if remaining > 0.01:
		je.append(
			"accounts",
			_build_je_row(
				account,
				side,
				remaining,
				company_currency,
				tx_date=tx_date,
				party_type=party_type,
				party=party,
			),
		)


class InterCompanyNettingCycle(Document):
	def validate(self):
		if not self.participating_companies:
			frappe.throw(_("Please add at least two participating companies for multilateral netting."))

	@frappe.whitelist()
	def fetch_open_invoices(self):
		"""
		Fetches all outstanding unique intercompany obligations between participating entities,
		deduplicating mirrored Sales Invoice / Purchase Invoice pairs so liabilities are never double-counted.
		"""
		self.check_permission("write")
		companies = [row.company for row in self.participating_companies if row.company]
		if len(companies) < 2:
			frappe.throw(_("At least two participating companies are required."))

		self.invoices = []

		links = frappe.get_all(
			"Intercompany Linked Company",
			filters={"company": ["in", companies]},
			fields=[
				"parent",
				"company",
				"main_company_customer",
				"main_company_supplier",
				"other_company_customer",
				"other_company_supplier",
			],
		)

		company_pairs = {}
		for link in links:
			parent_link = frappe.get_value("Intercompany Transaction Link", link.parent, "main_company")
			if parent_link in companies and link.company in companies:
				company_pairs[(parent_link, link.company)] = {
					"customer_in_other": link.other_company_customer,
					"supplier_in_other": link.other_company_supplier,
					"customer_in_main": link.main_company_customer,
					"supplier_in_main": link.main_company_supplier,
				}

		si_fields = ["name", "company", "customer", "outstanding_amount", "currency"]
		if frappe.db.has_column("Sales Invoice", "intercompany_linked_doc_doctype"):
			si_fields.extend(["intercompany_linked_doc_doctype", "intercompany_linked_doc_name"])

		sales_invoices = frappe.get_all(
			"Sales Invoice",
			filters={
				"company": ["in", companies],
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			fields=si_fields,
		)

		fetched_si_names = set()
		mirrored_pi_names = set()
		matched_pairs = set()

		for inv in sales_invoices:
			for (main_co, other_co), mapping in company_pairs.items():
				partner = None
				if inv.company == main_co and inv.customer == mapping["customer_in_main"]:
					partner = other_co
				elif inv.company == other_co and inv.customer == mapping["customer_in_other"]:
					partner = main_co

				if partner and partner in companies:
					pair_key = ("Sales Invoice", inv.name, partner)
					if pair_key in matched_pairs:
						continue
					matched_pairs.add(pair_key)
					fetched_si_names.add(inv.name)
					if (
						inv.get("intercompany_linked_doc_doctype") == "Purchase Invoice"
						and inv.get("intercompany_linked_doc_name")
					):
						mirrored_pi_names.add(inv.get("intercompany_linked_doc_name"))
					self.append("invoices", {
						"company": inv.company,
						"partner_company": partner,
						"invoice_type": "Sales Invoice",
						"invoice_name": inv.name,
						"outstanding_amount": inv.outstanding_amount,
						"currency": inv.currency,
						"settled_amount": inv.outstanding_amount,
					})

		if fetched_si_names and frappe.db.table_exists("Inter Company Document Reference"):
			doc_refs = frappe.get_all(
				"Inter Company Document Reference",
				filters={
					"source_doctype": ["in", ["Sales Invoice", "Purchase Invoice"]],
					"target_doctype": ["in", ["Sales Invoice", "Purchase Invoice"]],
				},
				fields=["source_doctype", "source_name", "target_doctype", "target_name"],
			)
			for ref in doc_refs:
				if ref.source_doctype == "Sales Invoice" and ref.source_name in fetched_si_names and ref.target_doctype == "Purchase Invoice":
					mirrored_pi_names.add(ref.target_name)
				elif ref.target_doctype == "Sales Invoice" and ref.target_name in fetched_si_names and ref.source_doctype == "Purchase Invoice":
					mirrored_pi_names.add(ref.source_name)

		pi_fields = ["name", "company", "supplier", "outstanding_amount", "currency"]
		if frappe.db.has_column("Purchase Invoice", "intercompany_linked_doc_doctype"):
			pi_fields.extend(["intercompany_linked_doc_doctype", "intercompany_linked_doc_name"])

		purchase_invoices = frappe.get_all(
			"Purchase Invoice",
			filters={
				"company": ["in", companies],
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			fields=pi_fields,
		)

		for inv in purchase_invoices:
			if inv.name in mirrored_pi_names:
				continue
			if (
				inv.get("intercompany_linked_doc_doctype") == "Sales Invoice"
				and inv.get("intercompany_linked_doc_name") in fetched_si_names
			):
				continue

			for (main_co, other_co), mapping in company_pairs.items():
				partner = None
				if inv.company == main_co and inv.supplier == mapping["supplier_in_main"]:
					partner = other_co
				elif inv.company == other_co and inv.supplier == mapping["supplier_in_other"]:
					partner = main_co

				if partner and partner in companies:
					pair_key = ("Purchase Invoice", inv.name, partner)
					if pair_key in matched_pairs:
						continue
					matched_pairs.add(pair_key)
					self.append("invoices", {
						"company": inv.company,
						"partner_company": partner,
						"invoice_type": "Purchase Invoice",
						"invoice_name": inv.name,
						"outstanding_amount": inv.outstanding_amount,
						"currency": inv.currency,
						"settled_amount": inv.outstanding_amount,
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
		and persists child net_settlements rows, settlement_entry links, and status cleanly to DB.
		"""
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.ict_accounting_builders import (
			_build_je_row,
		)
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

		for pc in (self.participating_companies or []):
			if pc.get("name") and hasattr(pc, "db_set"):
				pc.db_set({
					"gross_payables": flt(pc.gross_payables),
					"gross_receivables": flt(pc.gross_receivables),
					"net_balance": flt(pc.net_balance),
					"settlement_position": pc.settlement_position,
				}, update_modified=False)

		is_real_doc = (
			not isinstance(self, dict)
			and getattr(self, "name", None)
			and hasattr(frappe, "db")
			and frappe.db
			and frappe.db.table_exists("Inter Company Netting Summary")
		)
		if is_real_doc:
			frappe.db.delete(
				"Inter Company Netting Summary",
				{"parent": self.name, "parenttype": self.doctype, "parentfield": "net_settlements"},
			)

		for idx, settlement in enumerate(self.net_settlements, start=1):
			payer = settlement.paying_company
			receiver = settlement.receiving_company
			raw_amt = flt(settlement.amount)

			if is_real_doc and not settlement.get("name") and hasattr(settlement, "insert"):
				settlement.parent = self.name
				settlement.parenttype = self.doctype
				settlement.parentfield = "net_settlements"
				settlement.idx = idx
				settlement.docstatus = self.docstatus
				settlement.insert(ignore_permissions=True)

			if raw_amt <= 0.01:
				continue

			payer_currency = (
				frappe.get_cached_value("Company", payer, "default_currency")
				if hasattr(frappe, "db") and frappe.db
				else None
			)
			settlement_ccy = getattr(settlement, "currency", None) or payer_currency
			base_amt = _convert_cycle_amount(raw_amt, settlement_ccy, payer_currency, date)

			# Create intercompany clearing entry
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Journal Entry"
			je.company = payer
			je.posting_date = date
			je.user_remark = f"Multilateral Netting Settlement for Cycle {self.name}: Paid to {receiver}"

			clearing_account_payer, receiver_supplier = _resolve_netting_clearing_and_supplier(self, payer, receiver)
			if not clearing_account_payer:
				clearing_account_payer = get_or_create_intercompany_clearing_account(payer, receiver)

			payable_acct = frappe.get_value("Company", payer, "default_payable_account")
			bank_or_cash_acct = (
				frappe.get_value("Company", payer, "default_bank_account")
				or frappe.get_value("Company", payer, "default_cash_account")
			)

			if payable_acct and receiver_supplier:
				pi_refs = _collect_pair_open_invoices_for_settlement(self, payer, receiver, "Purchase Invoice", payer_currency, date)
				_append_allocated_party_rows(
					je,
					payable_acct,
					"debit",
					base_amt,
					payer_currency,
					date,
					"Supplier",
					receiver_supplier,
					pi_refs,
				)
			elif bank_or_cash_acct:
				je.append("accounts", _build_je_row(bank_or_cash_acct, "debit", base_amt, payer_currency, tx_date=date))
			else:
				je.append("accounts", _build_je_row(payable_acct or clearing_account_payer, "debit", base_amt, payer_currency, tx_date=date))

			if clearing_account_payer and je.accounts:
				credit_row = _build_je_row(clearing_account_payer, "credit", base_amt, payer_currency, tx_date=date)
				if (
					payer_currency
					and any(r.get("account_currency") != payer_currency for r in je.accounts)
				) or (payer_currency and credit_row.get("account_currency") != payer_currency):
					je.multi_currency = 1

				je.append("accounts", credit_row)
				je.flags.ignore_permissions = True
				je.flags.ignore_mandatory = True
				je.flags.ict_system_sync = True
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

				# Create mirrored receiver-side AR settlement JE so both ledgers tally
				clearing_account_receiver, payer_customer = _resolve_netting_clearing_and_customer(self, receiver, payer)
				receivable_acct = (
					frappe.get_value("Company", receiver, "default_receivable_account")
					if hasattr(frappe, "db") and frappe.db
					else None
				)
				if not clearing_account_receiver and receivable_acct and payer_customer:
					clearing_account_receiver = get_or_create_intercompany_clearing_account(receiver, payer)

				if clearing_account_receiver and receivable_acct and payer_customer:
					receiver_currency = (
						frappe.get_cached_value("Company", receiver, "default_currency")
						if hasattr(frappe, "db") and frappe.db
						else payer_currency
					)
					recv_base_amt = _convert_cycle_amount(raw_amt, settlement_ccy, receiver_currency, date)
					si_refs = _collect_pair_open_invoices_for_settlement(self, receiver, payer, "Sales Invoice", receiver_currency, date)

					recv_je = frappe.new_doc("Journal Entry")
					recv_je.voucher_type = "Journal Entry"
					recv_je.company = receiver
					recv_je.posting_date = date
					recv_je.user_remark = f"Mirrored Netting Settlement for Cycle {self.name}: Received from {payer}"
					recv_je.is_intercompany = 1
					recv_je.intercompany_linked_doc_doctype = "Journal Entry"
					recv_je.intercompany_linked_doc_name = je.name
					recv_je.intercompany_linked_company = payer

					recv_debit_row = _build_je_row(clearing_account_receiver, "debit", recv_base_amt, receiver_currency, tx_date=date)
					recv_je.append("accounts", recv_debit_row)
					_append_allocated_party_rows(
						recv_je,
						receivable_acct,
						"credit",
						recv_base_amt,
						receiver_currency,
						date,
						"Customer",
						payer_customer,
						si_refs,
					)
					if receiver_currency and any(r.get("account_currency") != receiver_currency for r in recv_je.accounts):
						recv_je.multi_currency = 1
					recv_je.flags.ignore_permissions = True
					recv_je.flags.ignore_mandatory = True
					recv_je.flags.ict_system_sync = True
					recv_je.insert(ignore_permissions=True)
					try:
						if hasattr(frappe.db, "savepoint"):
							frappe.db.savepoint("ict_netting_recv_submit")
						recv_je.submit()
					except Exception as e:
						if hasattr(frappe.db, "rollback"):
							try:
								frappe.db.rollback(save_point="ict_netting_recv_submit")
							except Exception:
								pass
						frappe.log_error(f"Receiver netting JE {recv_je.name} kept as draft: {e!s}", "Inter Company Netting")
						settlement.status = "Pending"
					settlement.receiver_settlement_entry = recv_je.name
					if frappe.db.table_exists("Inter Company Document Reference"):
						try:
							ref_doc = frappe.get_doc({
								"doctype": "Inter Company Document Reference",
								"source_doctype": "Journal Entry",
								"source_name": je.name,
								"source_company": payer,
								"target_doctype": "Journal Entry",
								"target_name": recv_je.name,
								"target_company": receiver,
							})
							ref_doc.flags.ignore_permissions = True
							ref_doc.flags.ignore_links = True
							ref_doc.flags.ignore_mandatory = True
							ref_doc.insert(ignore_permissions=True)
						except Exception:
							pass

				if hasattr(settlement, "db_set"):
					update_vals = {
						"status": settlement.status,
						"settlement_entry": je.name,
					}
					if getattr(settlement, "receiver_settlement_entry", None):
						update_vals["receiver_settlement_entry"] = settlement.receiver_settlement_entry
					settlement.db_set(update_vals, update_modified=False)

		self.status = "Settled"
		self.db_set("status", "Settled", update_modified=False)
		frappe.msgprint(_("Multilateral Netting Cycle {0} submitted. Two-sided settlement entries generated.").format(self.name), indicator="green")

	def on_cancel(self):
		"""Cancel associated payer and receiver settlement Journal Entries."""
		for settlement in (self.net_settlements or []):
			je_names = []
			if getattr(settlement, "settlement_entry", None):
				je_names.append(settlement.settlement_entry)
			if getattr(settlement, "receiver_settlement_entry", None):
				je_names.append(settlement.receiver_settlement_entry)
			for je_name in je_names:
				if frappe.db.exists("Journal Entry", je_name):
					try:
						doc = frappe.get_doc("Journal Entry", je_name)
						if doc.docstatus == 1:
							doc.flags.ignore_permissions = True
							doc.flags.ict_system_sync = True
							doc.cancel()
					except Exception as e:
						frappe.log_error(f"Error cancelling netting settlement entry {je_name}: {e}")
		self.status = "Cancelled"
		self.db_set("status", "Cancelled", update_modified=False)
