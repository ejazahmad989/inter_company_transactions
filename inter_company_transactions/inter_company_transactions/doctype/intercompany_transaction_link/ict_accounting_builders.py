# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from .ict_currency import (
	extract_document_exchange_rate,
	get_intercompany_exchange_rate,
	validate_stock_entry_same_currency,
)
from .ict_pricing import resolve_intercompany_target_item
from .ict_utils import (
	_facade_fn,
	_safe_flt,
	get_default_cost_center,
	get_intercompany_warehouse,
	get_or_create_intercompany_clearing_account,
	get_or_create_intercompany_warehouse,
)


def create_stock_entry(source_stock_entry, mapping, linked_company, direction, settings=None):
	"""Creates a paired Stock Entry in target company for inter-company stock transfer."""
	se = frappe.new_doc("Stock Entry")

	if direction == "other_to_main":
		se.company = mapping.main_company
		target_warehouse_company = mapping.main_company
		target_warehouse = getattr(linked_company, "main_company_warehouse", None)
	else:
		se.company = linked_company.company
		target_warehouse_company = linked_company.company
		target_warehouse = getattr(linked_company, "other_company_warehouse", None)

	se.stock_entry_type = "Material Receipt"
	se.purpose = "Material Receipt"

	se.posting_date = getattr(source_stock_entry, "posting_date", None) or nowdate()
	se.posting_time = getattr(source_stock_entry, "posting_time", None)
	se.set_posting_time = getattr(source_stock_entry, "set_posting_time", 0)
	se.remarks = getattr(source_stock_entry, "remarks", None) or (
		f"Intercompany Material Receipt from {source_stock_entry.doctype} {source_stock_entry.name} ({source_stock_entry.company})"
	)

	source_company_currency = frappe.db.get_value("Company", source_stock_entry.company, "default_currency")
	target_company_currency = frappe.db.get_value("Company", se.company, "default_currency")
	if source_company_currency and target_company_currency and source_company_currency != target_company_currency:
		validate_stock_entry_same_currency(source_stock_entry.company, se.company)
	fx_rate = 1.0

	get_wh_fn = _facade_fn("get_intercompany_warehouse", get_intercompany_warehouse)
	get_or_create_wh_fn = _facade_fn("get_or_create_intercompany_warehouse", get_or_create_intercompany_warehouse)
	if not target_warehouse:
		target_warehouse = get_wh_fn(target_warehouse_company)
	if not target_warehouse:
		target_warehouse = get_or_create_wh_fn(target_warehouse_company)
	if not target_warehouse:
		target_warehouse = frappe.db.get_value("Warehouse", {"company": target_warehouse_company, "is_group": 0}, "name")

	se.from_warehouse = None
	se.to_warehouse = target_warehouse

	for item in (source_stock_entry.get("items") or []):
		item_code = getattr(item, "item_code", None) or (item.get("item_code") if isinstance(item, dict) else None)
		base_rate = flt(
			getattr(item, "basic_rate", 0)
			or getattr(item, "valuation_rate", 0)
			or getattr(item, "rate", 0)
		)
		if base_rate <= 0 and item_code:
			base_rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate") or 0)

		item_for_mapping = {
			"item_code": item_code,
			"item_name": getattr(item, "item_name", None) or item_code,
			"description": getattr(item, "description", None) or item_code,
			"qty": flt(getattr(item, "qty", 1)),
			"rate": base_rate,
			"uom": getattr(item, "uom", None) or "Nos",
		}
		target_item = resolve_intercompany_target_item(
			item_for_mapping,
			se.company,
			mapping=mapping,
			rate_factor=fx_rate,
			settings=settings,
			source_company=source_stock_entry.company,
			transaction_date=se.posting_date,
		)
		final_rate = flt(target_item["rate"])
		se_row = {
			"item_code": target_item["item_code"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"s_warehouse": None,
			"t_warehouse": target_warehouse,
			"basic_rate": final_rate,
			"basic_amount": flt(final_rate * target_item["qty"]),
			"conversion_factor": target_item["conversion_factor"],
		}
		if final_rate <= 0:
			se_row["allow_zero_valuation_rate"] = 1
		se.append("items", se_row)

	se.intercompany_linked_doc_doctype = source_stock_entry.doctype
	se.intercompany_linked_doc_name = source_stock_entry.name
	se.intercompany_linked_company = source_stock_entry.company
	se.intercompany_target_company = source_stock_entry.company

	se.flags.ignore_permissions = True
	se.flags.ignore_mandatory = True
	se.flags.ignore_validate = True
	se.flags.ignore_links = True

	try:
		se.set_missing_values(for_validate=True)
	except Exception:
		pass

	se.from_warehouse = None
	for d in (se.get("items") or []):
		d.s_warehouse = None
		if not d.t_warehouse:
			d.t_warehouse = target_warehouse

	se.docstatus = 0
	return se


def _build_je_row(
	account,
	side,
	target_base_amount,
	target_company_currency,
	fx_hint_map=None,
	tx_date=None,
	party_type=None,
	party=None,
	cost_center=None,
):
	"""Constructs a balanced Journal Entry Account row respecting the target account's account_currency."""
	acc_currency = (
		frappe.db.get_value("Account", account, "account_currency")
		if account and hasattr(frappe, "db") and frappe.db
		else None
	) or target_company_currency

	base_amt = _safe_flt(target_base_amount, 2)
	raw_fx = 1.0
	if acc_currency and target_company_currency and acc_currency != target_company_currency:
		hint = (fx_hint_map or {}).get((acc_currency, target_company_currency))
		raw_fx = flt(hint) if hint else flt(get_intercompany_exchange_rate(acc_currency, target_company_currency, tx_date))
		if raw_fx <= 0:
			raw_fx = 1.0
		amt_in_acc_ccy = _safe_flt(base_amt / raw_fx, 2)
		if amt_in_acc_ccy > 0 and abs(_safe_flt(amt_in_acc_ccy * raw_fx, 2) - base_amt) > 0.001:
			raw_fx = base_amt / amt_in_acc_ccy
	else:
		amt_in_acc_ccy = base_amt

	row_fx = _safe_flt(raw_fx, 9)
	row = {
		"account": account,
		"account_currency": acc_currency,
		"exchange_rate": row_fx,
		"cost_center": cost_center,
		"debit_in_account_currency": amt_in_acc_ccy if side == "debit" else 0,
		"credit_in_account_currency": amt_in_acc_ccy if side == "credit" else 0,
		"debit": base_amt if side == "debit" else 0,
		"credit": base_amt if side == "credit" else 0,
	}
	if party_type and party:
		row["party_type"] = party_type
		row["party"] = party
	return row


def create_journal_entry_from_lcv(source_lcv, mapping, linked_company, direction):
	"""Creates a balanced Intercompany Recharge Journal Entry from a Landed Cost Voucher."""
	je = frappe.new_doc("Journal Entry")

	if direction == "other_to_main":
		je.company = mapping.main_company
		supplier = getattr(linked_company, "main_company_supplier", None)
		clearing_account = getattr(linked_company, "main_company_account", None)
	else:
		je.company = linked_company.company
		supplier = getattr(linked_company, "other_company_supplier", None)
		clearing_account = getattr(linked_company, "other_company_account", None)

	if not clearing_account:
		clear_fn = _facade_fn("get_or_create_intercompany_clearing_account", get_or_create_intercompany_clearing_account)
		clearing_account = clear_fn(je.company, source_lcv.company)

	total_amt = flt(getattr(source_lcv, "total_taxes_and_charges", 0))
	if total_amt <= 0:
		for tax in (source_lcv.get("taxes") or []):
			total_amt += flt(tax.get("base_amount") if isinstance(tax, dict) else getattr(tax, "base_amount", 0)) or flt(
				tax.get("amount") if isinstance(tax, dict) else getattr(tax, "amount", 0)
			)

	if total_amt <= 0:
		frappe.throw(
			_("Landed Cost Voucher {0} has zero total taxes and charges to recharge.").format(source_lcv.name)
		)

	je.posting_date = getattr(source_lcv, "posting_date", None) or nowdate()
	je.voucher_type = "Journal Entry"

	tax_descs = []
	for tax in (source_lcv.get("taxes") or []):
		desc = tax.get("description") if isinstance(tax, dict) else getattr(tax, "description", None)
		if desc:
			tax_descs.append(str(desc))
	tax_summary = f" ({', '.join(tax_descs[:3])})" if tax_descs else ""
	je.user_remark = f"Landed Cost Recharge from {source_lcv.doctype} {source_lcv.name} ({source_lcv.company}){tax_summary}"

	source_ccy = frappe.db.get_value("Company", source_lcv.company, "default_currency")
	target_ccy = frappe.db.get_value("Company", je.company, "default_currency")
	fx_rate = get_intercompany_exchange_rate(source_ccy, target_ccy, je.posting_date)
	if source_ccy and target_ccy and source_ccy != target_ccy:
		je.multi_currency = 1

	converted_amt = _safe_flt(total_amt * flt(fx_rate), 2)
	if converted_amt <= 0:
		converted_amt = _safe_flt(total_amt, 2)

	default_cost_center = get_default_cost_center(je.company)

	debit_account = frappe.db.get_value("Company", je.company, "default_expense_account")
	if not debit_account:
		debit_account = (
			frappe.db.get_value(
				"Account",
				{"company": je.company, "root_type": "Expense", "is_group": 0, "account_name": ["like", "%Freight%"]},
				"name",
			)
			or frappe.db.get_value(
				"Account",
				{"company": je.company, "root_type": "Expense", "is_group": 0, "account_name": ["like", "%Landed%"]},
				"name",
			)
			or frappe.db.get_value(
				"Account",
				{"company": je.company, "root_type": "Expense", "is_group": 0},
				"name",
			)
			or clearing_account
		)

	payable_account = frappe.db.get_value("Company", je.company, "default_payable_account")
	debit_row = _build_je_row(
		debit_account,
		"debit",
		converted_amt,
		target_ccy,
		tx_date=je.posting_date,
		cost_center=default_cost_center,
	)
	if supplier and payable_account:
		credit_row = _build_je_row(
			payable_account,
			"credit",
			converted_amt,
			target_ccy,
			tx_date=je.posting_date,
			party_type="Supplier",
			party=supplier,
			cost_center=default_cost_center,
		)
	else:
		credit_row = _build_je_row(
			clearing_account or debit_account,
			"credit",
			converted_amt,
			target_ccy,
			tx_date=je.posting_date,
			cost_center=default_cost_center,
		)

	je.append("accounts", debit_row)
	je.append("accounts", credit_row)

	je.intercompany_linked_doc_doctype = source_lcv.doctype
	je.intercompany_linked_doc_name = source_lcv.name
	je.intercompany_linked_company = source_lcv.company
	je.intercompany_target_company = source_lcv.company

	je.flags.ignore_permissions = True
	je.flags.ignore_mandatory = True
	je.flags.ignore_account_permission = True
	je.flags.ignore_validate = True
	je.flags.ignore_links = True
	je.docstatus = 0
	return je


def create_journal_entry(source_je, mapping, linked_company, direction):
	"""Create corresponding Journal Entry with 100% multi-currency ledger parity."""
	if getattr(source_je, "doctype", "") == "Landed Cost Voucher":
		return create_journal_entry_from_lcv(source_je, mapping, linked_company, direction)

	je = frappe.new_doc("Journal Entry")

	if direction == "other_to_main":
		je.company = mapping.main_company
		supplier = linked_company.main_company_supplier
		customer = linked_company.main_company_customer
		tmp_account = getattr(linked_company, "main_company_account", None)
	else:
		je.company = linked_company.company
		supplier = linked_company.other_company_supplier
		customer = linked_company.other_company_customer
		tmp_account = getattr(linked_company, "other_company_account", None)

	if not tmp_account:
		clear_fn = _facade_fn("get_or_create_intercompany_clearing_account", get_or_create_intercompany_clearing_account)
		tmp_account = clear_fn(je.company, source_je.company)

	je.posting_date = getattr(source_je, "posting_date", None) or nowdate()
	je.voucher_type = "Journal Entry"
	je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name} " + (getattr(source_je, "user_remark", None) or "")

	source_company_currency = (
		frappe.db.get_value("Company", source_je.company, "default_currency")
		if hasattr(frappe, "db") and frappe.db else None
	) or getattr(source_je, "currency", None)
	target_company_currency = (
		frappe.db.get_value("Company", je.company, "default_currency")
		if hasattr(frappe, "db") and frappe.db else None
	) or source_company_currency

	source_party_type = None
	source_is_credit = False
	source_party_row = None
	for acc in (getattr(source_je, "accounts", None) or []):
		if getattr(acc, "party_type", None) and getattr(acc, "party", None):
			source_party_type = acc.party_type
			source_is_credit = flt(getattr(acc, "credit_in_account_currency", 0)) > 0 or flt(getattr(acc, "credit", 0)) > 0
			source_party_row = acc
			break

	src_base_total = flt(getattr(source_je, "total_credit", 0)) or flt(getattr(source_je, "total_debit", 0))
	if src_base_total <= 0:
		src_base_total = sum(
			flt(getattr(r, "credit", 0))
			or (flt(getattr(r, "credit_in_account_currency", 0)) * (flt(getattr(r, "exchange_rate", 1)) or 1.0))
			for r in (getattr(source_je, "accounts", None) or [])
		)

	fx_hint_map = {}
	for acc_row in (getattr(source_je, "accounts", None) or []):
		r_ccy = getattr(acc_row, "account_currency", None)
		r_fx = flt(getattr(acc_row, "exchange_rate", 0))
		if r_ccy and source_company_currency and r_ccy != source_company_currency and r_fx > 0:
			fx_hint_map[(r_ccy, source_company_currency)] = r_fx
			fx_hint_map[(source_company_currency, r_ccy)] = 1.0 / r_fx

	if source_company_currency == target_company_currency:
		target_base_amount = _safe_flt(src_base_total, 2)
	elif (
		source_party_row
		and getattr(source_party_row, "account_currency", None) == target_company_currency
		and (
			flt(getattr(source_party_row, "credit_in_account_currency", 0)) > 0
			or flt(getattr(source_party_row, "debit_in_account_currency", 0)) > 0
		)
	):
		target_base_amount = _safe_flt(
			flt(getattr(source_party_row, "credit_in_account_currency", 0))
			or flt(getattr(source_party_row, "debit_in_account_currency", 0)),
			2,
		)
	else:
		fx_src_to_tgt = (
			fx_hint_map.get((source_company_currency, target_company_currency))
			or extract_document_exchange_rate(source_je, source_company_currency, target_company_currency)
			or get_intercompany_exchange_rate(source_company_currency, target_company_currency, je.posting_date)
		)
		target_base_amount = _safe_flt(src_base_total * flt(fx_src_to_tgt), 2)

	if source_company_currency != target_company_currency:
		je.multi_currency = 1
	else:
		je.multi_currency = getattr(source_je, "multi_currency", 0)

	default_cost_center = get_default_cost_center(je.company)

	if source_party_type == "Supplier":
		party_acct = (
			frappe.db.get_value("Party Account", {"parenttype": "Customer", "parent": customer, "company": je.company}, "account")
			if customer else None
		) or frappe.db.get_value("Company", je.company, "default_receivable_account")
		p_side = "debit" if source_is_credit else "credit"
		t_side = "credit" if source_is_credit else "debit"
		r1 = _build_je_row(party_acct, p_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, "Customer", customer, default_cost_center)
		r2 = _build_je_row(tmp_account, t_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, None, None, default_cost_center)
	else:
		party_acct = (
			frappe.db.get_value("Party Account", {"parenttype": "Supplier", "parent": supplier, "company": je.company}, "account")
			if supplier else None
		) or frappe.db.get_value("Company", je.company, "default_payable_account")
		p_side = "debit" if source_is_credit else "credit"
		t_side = "credit" if source_is_credit else "debit"
		r1 = _build_je_row(party_acct, p_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, "Supplier", supplier, default_cost_center)
		r2 = _build_je_row(tmp_account, t_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, None, None, default_cost_center)

	if r1.get("account_currency") != target_company_currency or r2.get("account_currency") != target_company_currency:
		je.multi_currency = 1

	je.append("accounts", r1)
	je.append("accounts", r2)

	je.flags.ignore_permissions = True
	je.flags.ignore_mandatory = True
	je.flags.ignore_account_permission = True
	je.flags.ignore_validate = True
	je.flags.ignore_links = True

	je.intercompany_linked_doc_doctype = source_je.doctype
	je.intercompany_linked_doc_name = source_je.name
	je.intercompany_linked_company = source_je.company
	je.intercompany_target_company = source_je.company
	je.docstatus = 0
	return je


def create_payment_entry(source_pe, mapping, linked_company, direction):
	"""Create corresponding Payment Entry using Bank/Cash TMP clearing accounts and exact FX rates."""
	pe = frappe.new_doc("Payment Entry")

	if direction == "other_to_main":
		pe.company = mapping.main_company
		tmp_account = getattr(linked_company, "main_company_account", None)
		customer = linked_company.main_company_customer
		supplier = linked_company.main_company_supplier
	else:
		pe.company = linked_company.company
		tmp_account = getattr(linked_company, "other_company_account", None)
		customer = linked_company.other_company_customer
		supplier = linked_company.other_company_supplier

	tmp_type = (
		frappe.db.get_value("Account", tmp_account, "account_type")
		if tmp_account and hasattr(frappe, "db") and frappe.db
		else None
	)
	if not tmp_account or tmp_type not in ("Bank", "Cash"):
		clear_fn = _facade_fn("get_or_create_intercompany_clearing_account", get_or_create_intercompany_clearing_account)
		tmp_account = clear_fn(pe.company, source_pe.company)

	pe.posting_date = getattr(source_pe, "posting_date", None) or nowdate()
	pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
	pe.mode_of_payment = getattr(source_pe, "mode_of_payment", None)

	if pe.payment_type == "Pay":
		pe.paid_from = tmp_account
		pe.paid_to = (
			(frappe.db.get_value("Party Account", {"parenttype": "Supplier", "parent": supplier, "company": pe.company}, "account") if supplier else None)
			or frappe.db.get_value("Company", pe.company, "default_payable_account")
		)
		pe.party_type = "Supplier"
		pe.party = supplier
		pe.party_name = frappe.db.get_value("Supplier", supplier, "supplier_name") if supplier else ""
	else:
		pe.paid_from = (
			(frappe.db.get_value("Party Account", {"parenttype": "Customer", "parent": customer, "company": pe.company}, "account") if customer else None)
			or frappe.db.get_value("Company", pe.company, "default_receivable_account")
		)
		pe.paid_to = tmp_account
		pe.party_type = "Customer"
		pe.party = customer
		pe.party_name = frappe.db.get_value("Customer", customer, "customer_name") if customer else ""

	source_company_currency = frappe.db.get_value("Company", source_pe.company, "default_currency")
	target_company_currency = frappe.db.get_value("Company", pe.company, "default_currency")

	pe.paid_from_account_currency = (
		frappe.db.get_value("Account", pe.paid_from, "account_currency") if pe.paid_from else None
	) or target_company_currency
	pe.paid_to_account_currency = (
		frappe.db.get_value("Account", pe.paid_to, "account_currency") if pe.paid_to else None
	) or target_company_currency

	if source_pe.payment_type == "Pay":
		ref_amt = flt(getattr(source_pe, "received_amount", 0)) or flt(getattr(source_pe, "paid_amount", 0))
		ref_ccy = getattr(source_pe, "paid_to_account_currency", None) or source_company_currency
	else:
		ref_amt = flt(getattr(source_pe, "paid_amount", 0)) or flt(getattr(source_pe, "received_amount", 0))
		ref_ccy = getattr(source_pe, "paid_from_account_currency", None) or source_company_currency

	def _pe_rate(c_from, c_to):
		if not c_from or not c_to or c_from == c_to:
			return 1.0
		r = extract_document_exchange_rate(source_pe, c_from, c_to)
		if not r:
			r = get_intercompany_exchange_rate(c_from, c_to, pe.posting_date)
		return _safe_flt(r or 1.0, 9)

	pe.source_exchange_rate = _pe_rate(pe.paid_from_account_currency, target_company_currency)
	pe.target_exchange_rate = _pe_rate(pe.paid_to_account_currency, target_company_currency)

	fx_ref_to_paid_from = _pe_rate(ref_ccy, pe.paid_from_account_currency)
	pe.paid_amount = _safe_flt(ref_amt * fx_ref_to_paid_from, 2)

	base_paid_amt = _safe_flt(pe.paid_amount * flt(pe.source_exchange_rate), 2)
	if pe.paid_to_account_currency == pe.paid_from_account_currency:
		pe.received_amount = pe.paid_amount
	elif pe.paid_to_account_currency == ref_ccy:
		pe.received_amount = _safe_flt(ref_amt, 2)
	else:
		pe.received_amount = _safe_flt(base_paid_amt / (flt(pe.target_exchange_rate) or 1.0), 2)

	pe.base_paid_amount = base_paid_amt
	pe.base_received_amount = _safe_flt(pe.received_amount * flt(pe.target_exchange_rate), 2)

	pe.reference_no = getattr(source_pe, "reference_no", None) or source_pe.name
	pe.reference_date = getattr(source_pe, "reference_date", None) or pe.posting_date

	pe.intercompany_linked_doc_doctype = source_pe.doctype
	pe.intercompany_linked_doc_name = source_pe.name
	pe.intercompany_linked_company = source_pe.company
	pe.intercompany_target_company = source_pe.company

	pe.flags.ignore_permissions = True
	pe.flags.ignore_mandatory = True
	pe.flags.ignore_account_permission = True
	pe.flags.ignore_validate = True
	pe.flags.ignore_links = True
	pe.flags.ignore_party_validation = True
	pe.flags.ignore_exchange_rate = True
	pe.flags.ignore_pricing_rule = True

	pe.docstatus = 0
	return pe


def _set_row_value(row, key, value):
	if isinstance(row, dict):
		row[key] = value
	else:
		setattr(row, key, value)


def _has_row_field(row, key):
	return (isinstance(row, dict) and key in row) or hasattr(row, key)


def _precalculate_mirrored_doc_totals(doc):
	"""Pre-calculates ERPNext derived line amounts and document totals on mirrored drafts before DB insert."""
	if not doc:
		return

	dt = getattr(doc, "doctype", None)
	if dt == "Journal Entry":
		company_ccy = None
		if getattr(doc, "company", None) and hasattr(frappe, "db") and frappe.db:
			try:
				company_ccy = frappe.db.get_value("Company", doc.company, "default_currency")
			except Exception:
				company_ccy = None

		for row in (doc.get("accounts") or []):
			acct = row.get("account")
			if not row.get("account_currency"):
				acc_ccy = None
				if acct and hasattr(frappe, "db") and frappe.db:
					try:
						acc_ccy = frappe.db.get_value("Account", acct, "account_currency")
					except Exception:
						acc_ccy = None
				if acc_ccy or company_ccy:
					_set_row_value(row, "account_currency", acc_ccy or company_ccy)
			if abs(flt(row.get("exchange_rate"))) <= 0.0001:
				_set_row_value(row, "exchange_rate", 1.0)
			fx = flt(row.get("exchange_rate") or 1.0)
			if abs(flt(row.get("debit"))) <= 0.0001 and abs(flt(row.get("debit_in_account_currency"))) > 0.0001:
				_set_row_value(row, "debit", _safe_flt(flt(row.get("debit_in_account_currency")) * fx, 2))
			if abs(flt(row.get("credit"))) <= 0.0001 and abs(flt(row.get("credit_in_account_currency"))) > 0.0001:
				_set_row_value(row, "credit", _safe_flt(flt(row.get("credit_in_account_currency")) * fx, 2))

		try:
			if hasattr(doc, "set_amounts_in_company_currency"):
				doc.set_amounts_in_company_currency()
		except Exception:
			pass
		try:
			if hasattr(doc, "set_total_debit_credit"):
				doc.set_total_debit_credit()
		except Exception:
			pass

		accounts = doc.get("accounts") or []
		if accounts and abs(flt(doc.get("total_debit"))) <= 0.0001 and abs(flt(doc.get("total_credit"))) <= 0.0001:
			doc.total_debit = _safe_flt(sum(flt(r.get("debit") or r.get("debit_in_account_currency")) for r in accounts), 2)
			doc.total_credit = _safe_flt(sum(flt(r.get("credit") or r.get("credit_in_account_currency")) for r in accounts), 2)
		return

	if dt == "Stock Entry":
		try:
			if hasattr(doc, "calculate_rate_and_amount"):
				doc.calculate_rate_and_amount()
		except Exception:
			pass
		items = doc.get("items") or []
		for row in items:
			qty = flt(row.get("qty"))
			brate = flt(row.get("basic_rate"))
			if abs(flt(row.get("basic_amount"))) <= 0.0001 and qty and brate:
				_set_row_value(row, "basic_amount", _safe_flt(qty * brate, 2))
			if abs(flt(row.get("amount"))) <= 0.0001 and (flt(row.get("basic_amount")) or flt(row.get("additional_cost"))):
				_set_row_value(row, "amount", _safe_flt(flt(row.get("basic_amount")) + flt(row.get("additional_cost")), 2))
		if items and abs(flt(doc.get("total_amount"))) <= 0.0001:
			total_val = _safe_flt(sum(flt(r.get("amount") or r.get("basic_amount")) for r in items), 2)
			if _has_row_field(doc, "total_amount"):
				_set_row_value(doc, "total_amount", total_val)
			if doc.get("purpose") == "Material Receipt" and _has_row_field(doc, "total_incoming_value"):
				_set_row_value(doc, "total_incoming_value", total_val)
		return

	if dt == "Payment Entry":
		try:
			if hasattr(doc, "set_amounts"):
				doc.set_amounts()
		except Exception:
			pass
		return

	try:
		if hasattr(doc, "calculate_taxes_and_totals"):
			doc.calculate_taxes_and_totals()
	except Exception:
		pass
	items = doc.get("items") or []
	conv_rate = flt(doc.get("conversion_rate") or 1.0)
	for row in items:
		qty = flt(row.get("qty"))
		rate = flt(row.get("rate"))
		if abs(flt(row.get("amount"))) <= 0.0001 and qty and rate:
			amt = _safe_flt(qty * rate, 2)
			_set_row_value(row, "amount", amt)
			if _has_row_field(row, "base_rate"):
				_set_row_value(row, "base_rate", _safe_flt(rate * conv_rate, 2))
			if _has_row_field(row, "base_amount"):
				_set_row_value(row, "base_amount", _safe_flt(amt * conv_rate, 2))
	if items and abs(flt(doc.get("total"))) <= 0.0001:
		total_amt = _safe_flt(sum(flt(r.get("amount")) for r in items), 2)
		if _has_row_field(doc, "total"):
			_set_row_value(doc, "total", total_amt)
		if _has_row_field(doc, "net_total"):
			_set_row_value(doc, "net_total", total_amt)
		if _has_row_field(doc, "grand_total"):
			_set_row_value(doc, "grand_total", total_amt)
