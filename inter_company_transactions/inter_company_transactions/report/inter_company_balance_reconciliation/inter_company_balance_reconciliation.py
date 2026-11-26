# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	report_summary = get_report_summary(data, filters=filters)

	return columns, data, None, chart, report_summary


def validate_filters(filters):
	if not filters.get("company_a") or not filters.get("company_b"):
		frappe.throw(_("Both Company A and Company B are required to reconcile balances."))
	if filters.get("company_a") == filters.get("company_b"):
		frappe.throw(_("Company A and Company B must be different companies."))


def get_columns():
	return [
		{
			"label": _("Transaction Ref"),
			"fieldname": "reference_id",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 105,
		},
		{
			"label": _("DocType A"),
			"fieldname": "doctype_a",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 130,
		},
		{
			"label": _("Document A"),
			"fieldname": "docname_a",
			"fieldtype": "Dynamic Link",
			"options": "doctype_a",
			"width": 150,
		},
		{
			"label": _("Cur A"),
			"fieldname": "currency_a",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 80,
		},
		{
			"label": _("Amount A"),
			"fieldname": "amount_a",
			"fieldtype": "Currency",
			"options": "currency_a",
			"width": 130,
		},
		{
			"label": _("DocType B"),
			"fieldname": "doctype_b",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 130,
		},
		{
			"label": _("Document B"),
			"fieldname": "docname_b",
			"fieldtype": "Dynamic Link",
			"options": "doctype_b",
			"width": 150,
		},
		{
			"label": _("Cur B"),
			"fieldname": "currency_b",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 80,
		},
		{
			"label": _("Amount B"),
			"fieldname": "amount_b",
			"fieldtype": "Currency",
			"options": "currency_b",
			"width": 130,
		},
		{
			"label": _("Variance (in Cur A)"),
			"fieldname": "difference",
			"fieldtype": "Currency",
			"options": "currency_a",
			"width": 140,
		},
		{
			"label": _("Reconciliation Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 140,
		},
	]


def _add_fx_pair(fx_map, from_ccy, to_ccy, rate):
	if from_ccy and to_ccy and from_ccy != to_ccy and flt(rate) > 0:
		fx_map.setdefault((from_ccy, to_ccy), flt(rate))
		fx_map.setdefault((to_ccy, from_ccy), 1.0 / flt(rate))


def _resolve_doc_pair_conversion(info_a, info_b, posting_date, fx_lookup):
	"""
	Convert info_b['amount'] (in cur_b) into cur_a using document-level base amounts
	and recorded exchange rates before falling back to system Currency Exchange.
	Returns (converted_b_in_cur_a, fx_used_for_tolerance).
	"""
	amt_a = flt(info_a.get("amount"))
	amt_b = flt(info_b.get("amount"))
	cur_a = info_a.get("currency")
	cur_b = info_b.get("currency")
	base_ccy_a = info_a.get("company_currency")
	base_ccy_b = info_b.get("company_currency")
	base_amt_a = flt(info_a.get("base_amount"))
	base_amt_b = flt(info_b.get("base_amount"))

	if not cur_a or not cur_b or cur_a == cur_b:
		return amt_b, 1.0

	# 1. If Document B's company currency IS cur_a, its saved base_amount is already in cur_a
	if base_ccy_b == cur_a and base_amt_b > 0:
		fx_est = (base_amt_b / amt_b) if amt_b > 0 else 1.0
		return base_amt_b, fx_est

	# 2. If Document A's company currency IS cur_b, its saved base_amount gives the exact doc rate
	if base_ccy_a == cur_b and base_amt_a > 0 and amt_a > 0:
		fx_b_to_a = amt_a / base_amt_a
		return flt(amt_b) * fx_b_to_a, fx_b_to_a

	# 3. Check explicit exchange rates saved on either document (e.g. conversion_rate, PE/JE rates)
	doc_fx = (
		(info_a.get("doc_fx_map") or {}).get((cur_b, cur_a))
		or (info_b.get("doc_fx_map") or {}).get((cur_b, cur_a))
	)
	if flt(doc_fx) > 0:
		return flt(amt_b) * flt(doc_fx), flt(doc_fx)

	# 4. Fallback to Currency Exchange lookup on posting_date
	sys_fx = flt(fx_lookup(cur_b, cur_a, posting_date))
	if sys_fx <= 0:
		sys_fx = 1.0
	return flt(amt_b) * sys_fx, sys_fx


def _convert_amount_to_reporting_ccy(amount, from_ccy, doc_info, target_ccy, posting_date, fx_lookup, other_info=None):
	"""Convert a single amount into the report summary's reporting currency (Company A's default currency)."""
	amt = flt(amount)
	if not target_ccy or not from_ccy or from_ccy == target_ccy:
		return amt

	if doc_info.get("company_currency") == target_ccy and flt(doc_info.get("base_amount")) > 0:
		return flt(doc_info.get("base_amount"))

	doc_fx = (doc_info.get("doc_fx_map") or {}).get((from_ccy, target_ccy))
	if not doc_fx and other_info:
		doc_fx = (other_info.get("doc_fx_map") or {}).get((from_ccy, target_ccy))
	if flt(doc_fx) > 0:
		return amt * flt(doc_fx)

	sys_fx = flt(fx_lookup(from_ccy, target_ccy, posting_date))
	return amt * (sys_fx if sys_fx > 0 else 1.0)


def get_data(filters):
	data = []
	company_a = filters.get("company_a")
	company_b = filters.get("company_b")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	# Query tracked document references linking both companies
	ref_filters = [
		["Inter Company Document Reference", "source_company", "in", [company_a, company_b]],
		["Inter Company Document Reference", "target_company", "in", [company_a, company_b]],
	]

	refs = frappe.get_all(
		"Inter Company Document Reference",
		filters=ref_filters,
		fields=[
			"name",
			"source_doctype",
			"source_name",
			"source_company",
			"target_doctype",
			"target_name",
			"target_company",
			"creation",
		],
		order_by="creation desc",
	)

	from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
		get_intercompany_exchange_rate,
	)

	company_a_ccy = frappe.db.get_value("Company", company_a, "default_currency") if company_a else None

	for ref in refs:
		# Determine which is Company A side vs Company B side
		if ref.source_company == company_a:
			doc_a_type, doc_a_name = ref.source_doctype, ref.source_name
			doc_b_type, doc_b_name = ref.target_doctype, ref.target_name
		else:
			doc_a_type, doc_a_name = ref.target_doctype, ref.target_name
			doc_b_type, doc_b_name = ref.source_doctype, ref.source_name

		info_a = get_doc_reconciliation_info(doc_a_type, doc_a_name, company_a)
		info_b = get_doc_reconciliation_info(doc_b_type, doc_b_name, company_b)

		amt_a, date_a, status_a, cur_a = info_a["amount"], info_a["posting_date"], info_a["status"], info_a["currency"]
		amt_b, date_b, status_b, cur_b = info_b["amount"], info_b["posting_date"], info_b["status"], info_b["currency"]

		posting_date = date_a or date_b or ref.creation

		# Date filtering
		if from_date and getdate(posting_date) < getdate(from_date):
			continue
		if to_date and getdate(posting_date) > getdate(to_date):
			continue

		# Cross-currency comparison respecting document-recorded rates and base amounts
		if cur_a and cur_b and cur_a != cur_b:
			converted_b, fx_used = _resolve_doc_pair_conversion(
				info_a, info_b, posting_date, get_intercompany_exchange_rate
			)
			diff = flt(amt_a - converted_b, 2)
			# Account for 2-decimal rounding of amt_b (<= 0.005 * fx_used) when fx_used > 1
			tolerance = max(0.05, flt(0.0055 * max(1.0, flt(fx_used)), 2))
		else:
			converted_b = amt_b
			diff = flt(amt_a - amt_b, 2)
			tolerance = 0.05

		if not doc_b_name or status_b == "Missing" or (amt_a > 0 and amt_b == 0):
			status = "Missing in Target"
		elif abs(diff) <= tolerance and (amt_a > 0 and amt_b > 0 or (amt_a == 0 and amt_b == 0 and status_a != "Missing")):
			status = "Matched"
		else:
			status = "Unmatched Variance"

		if filters.get("status") and filters.get("status") != "All":
			if filters.get("status") != status:
				continue

		# Reporting values in Company A's default currency for accurate summary aggregation
		rep_ccy = company_a_ccy or cur_a
		rep_amt_a = _convert_amount_to_reporting_ccy(
			amt_a, cur_a, info_a, rep_ccy, posting_date, get_intercompany_exchange_rate, other_info=info_b
		)
		if cur_a and cur_b and cur_a != cur_b and rep_ccy == cur_a:
			rep_amt_b = flt(converted_b, 2)
		else:
			rep_amt_b = _convert_amount_to_reporting_ccy(
				amt_b, cur_b, info_b, rep_ccy, posting_date, get_intercompany_exchange_rate, other_info=info_a
			)

		data.append(
			{
				"reference_id": ref.name,
				"posting_date": posting_date,
				"doctype_a": doc_a_type,
				"docname_a": doc_a_name,
				"currency_a": cur_a,
				"amount_a": amt_a,
				"doctype_b": doc_b_type,
				"docname_b": doc_b_name,
				"currency_b": cur_b,
				"amount_b": amt_b,
				"difference": diff,
				"status": status,
				"reporting_currency": rep_ccy,
				"reporting_amount_a": flt(rep_amt_a, 2),
				"reporting_amount_b": flt(rep_amt_b, 2),
				"tolerance": tolerance,
			}
		)

	return data


def get_doc_reconciliation_info(doctype, name, company=None):
	"""Extract transaction amount, base amount, posting date, currency, and document FX rates safely."""
	company_currency = (
		frappe.db.get_value("Company", company, "default_currency")
		if company and hasattr(frappe, "db") and frappe.db
		else None
	)
	if not doctype or not name or not frappe.db.exists(doctype, name):
		return {
			"amount": 0.0,
			"base_amount": 0.0,
			"posting_date": None,
			"status": "Missing",
			"currency": company_currency,
			"company_currency": company_currency,
			"conversion_rate": 0.0,
			"doc_fx_map": {},
		}

	meta = frappe.get_meta(doctype)
	fields = ["docstatus"]

	candidate_fields = [
		"company",
		"grand_total",
		"total_amount",
		"paid_amount",
		"received_amount",
		"total_debit",
		"total_credit",
		"total_taxes_and_charges",
		"base_grand_total",
		"base_total_amount",
		"base_paid_amount",
		"base_received_amount",
		"posting_date",
		"transaction_date",
		"currency",
		"paid_from_account_currency",
		"paid_to_account_currency",
		"conversion_rate",
		"source_exchange_rate",
		"target_exchange_rate",
	]
	for f in candidate_fields:
		if meta.has_field(f) and f not in fields:
			fields.append(f)

	doc_data = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not doc_data:
		return {
			"amount": 0.0,
			"base_amount": 0.0,
			"posting_date": None,
			"status": "Missing",
			"currency": company_currency,
			"company_currency": company_currency,
			"conversion_rate": 0.0,
			"doc_fx_map": {},
		}

	doc_company = company or doc_data.get("company")
	if not company_currency and doc_company and hasattr(frappe, "db") and frappe.db:
		company_currency = frappe.db.get_value("Company", doc_company, "default_currency")

	amount = 0.0
	for amt_field in ["grand_total", "total_amount", "paid_amount", "total_debit", "total_credit", "total_taxes_and_charges"]:
		if doc_data.get(amt_field) is not None:
			amount = flt(doc_data.get(amt_field))
			break

	base_amount = 0.0
	for base_field in ["base_grand_total", "base_total_amount", "base_paid_amount", "total_debit", "total_credit", "total_taxes_and_charges"]:
		if doc_data.get(base_field) is not None:
			base_amount = flt(doc_data.get(base_field))
			break

	post_date = doc_data.get("posting_date") or doc_data.get("transaction_date")
	status = "Submitted" if doc_data.get("docstatus") == 1 else "Draft"
	currency = doc_data.get("currency") or doc_data.get("paid_from_account_currency") or company_currency
	if base_amount <= 0 and currency == company_currency and amount > 0:
		base_amount = amount

	conv_rate = flt(doc_data.get("conversion_rate"))
	doc_fx_map = {}
	if currency and company_currency and currency != company_currency:
		if conv_rate > 0:
			_add_fx_pair(doc_fx_map, currency, company_currency, conv_rate)
		elif base_amount > 0 and amount > 0:
			_add_fx_pair(doc_fx_map, currency, company_currency, base_amount / amount)

	if doctype == "Payment Entry":
		from_ccy = doc_data.get("paid_from_account_currency")
		to_ccy = doc_data.get("paid_to_account_currency")
		src_fx = flt(doc_data.get("source_exchange_rate"))
		tgt_fx = flt(doc_data.get("target_exchange_rate"))
		if from_ccy and company_currency and src_fx > 0:
			_add_fx_pair(doc_fx_map, from_ccy, company_currency, src_fx)
		if to_ccy and company_currency and tgt_fx > 0:
			_add_fx_pair(doc_fx_map, to_ccy, company_currency, tgt_fx)
		paid_amt = flt(doc_data.get("paid_amount"))
		recv_amt = flt(doc_data.get("received_amount"))
		if from_ccy and to_ccy and from_ccy != to_ccy and paid_amt > 0 and recv_amt > 0:
			_add_fx_pair(doc_fx_map, from_ccy, to_ccy, recv_amt / paid_amt)

	if doctype == "Journal Entry" and hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Journal Entry Account"):
		try:
			je_rows = frappe.get_all(
				"Journal Entry Account",
				filters={"parent": name},
				fields=["account_currency", "exchange_rate"],
			)
			for r in (je_rows or []):
				acc_ccy = r.get("account_currency")
				r_fx = flt(r.get("exchange_rate"))
				if acc_ccy and company_currency and acc_ccy != company_currency and r_fx > 0:
					_add_fx_pair(doc_fx_map, acc_ccy, company_currency, r_fx)
		except Exception:
			pass

	return {
		"amount": amount,
		"base_amount": base_amount,
		"posting_date": post_date,
		"status": status,
		"currency": currency,
		"company_currency": company_currency,
		"conversion_rate": conv_rate,
		"doc_fx_map": doc_fx_map,
	}


def get_doc_amount_and_date(doctype, name, company=None):
	"""Extract grand total / paid amount, posting date, and currency safely from ERPNext document"""
	info = get_doc_reconciliation_info(doctype, name, company=company)
	return info["amount"], info["posting_date"], info["status"], info["currency"]


def get_report_summary(data, filters=None):
	filters = filters or {}
	reporting_ccy = None
	for d in data:
		if d.get("reporting_currency"):
			reporting_ccy = d.get("reporting_currency")
			break
	if not reporting_ccy and filters.get("company_a") and hasattr(frappe, "db") and frappe.db:
		reporting_ccy = frappe.db.get_value("Company", filters.get("company_a"), "default_currency")

	total_a = flt(sum(flt(d.get("reporting_amount_a", d.get("amount_a"))) for d in data), 2)
	total_b = flt(sum(flt(d.get("reporting_amount_b", d.get("amount_b"))) for d in data), 2)
	variance = flt(total_a - total_b, 2)
	matched_count = sum(1 for d in data if d.get("status") == "Matched")
	unmatched_count = len(data) - matched_count

	summary = [
		{
			"value": total_a,
			"indicator": "Blue",
			"label": _("Total in Company A"),
			"datatype": "Currency",
		},
		{
			"value": total_b,
			"indicator": "Purple",
			"label": _("Total in Company B"),
			"datatype": "Currency",
		},
		{
			"value": variance,
			"indicator": "Green" if unmatched_count == 0 or abs(variance) < 0.1 else "Red",
			"label": _("Net Variance"),
			"datatype": "Currency",
		},
		{
			"value": f"{matched_count} / {len(data)}",
			"indicator": "Green" if unmatched_count == 0 else "Orange",
			"label": _("Reconciled Transactions"),
			"datatype": "Data",
		},
	]
	if reporting_ccy:
		for card in summary[:3]:
			card["currency"] = reporting_ccy
	return summary


def get_chart_data(data):
	matched = sum(1 for d in data if d.get("status") == "Matched")
	variance = sum(1 for d in data if d.get("status") == "Unmatched Variance")
	missing = sum(1 for d in data if d.get("status") == "Missing in Target")

	return {
		"data": {
			"labels": [_("Matched"), _("Variance"), _("Missing in Target")],
			"datasets": [{"values": [matched, variance, missing]}],
		},
		"type": "percentage",
		"colors": ["#28a745", "#dc3545", "#ffc107"],
	}
