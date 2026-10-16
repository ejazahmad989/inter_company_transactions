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
	report_summary = get_report_summary(data)

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

	for ref in refs:
		# Determine which is Company A side vs Company B side
		if ref.source_company == company_a:
			doc_a_type, doc_a_name = ref.source_doctype, ref.source_name
			doc_b_type, doc_b_name = ref.target_doctype, ref.target_name
		else:
			doc_a_type, doc_a_name = ref.target_doctype, ref.target_name
			doc_b_type, doc_b_name = ref.source_doctype, ref.source_name

		amt_a, date_a, _status_a, cur_a = get_doc_amount_and_date(doc_a_type, doc_a_name, company_a)
		amt_b, date_b, _status_b, cur_b = get_doc_amount_and_date(doc_b_type, doc_b_name, company_b)

		posting_date = date_a or date_b or ref.creation

		# Date filtering
		if from_date and getdate(posting_date) < getdate(from_date):
			continue
		if to_date and getdate(posting_date) > getdate(to_date):
			continue

		# Cross-currency comparison
		if cur_a and cur_b and cur_a != cur_b:
			fx = get_intercompany_exchange_rate(cur_b, cur_a, posting_date)
			converted_b = flt(amt_b) * flt(fx)
			diff = flt(amt_a - converted_b, 2)
		else:
			diff = flt(amt_a - amt_b, 2)

		tolerance = 0.05

		if abs(diff) <= tolerance and amt_a > 0 and amt_b > 0:
			status = "Matched"
		elif amt_b == 0 or not doc_b_name:
			status = "Missing in Target"
		else:
			status = "Unmatched Variance"

		if filters.get("status") and filters.get("status") != "All":
			if filters.get("status") != status:
				continue

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
			}
		)

	return data


def get_doc_amount_and_date(doctype, name, company=None):
	"""Extract grand total / paid amount, posting date, and currency safely from ERPNext document"""
	if not doctype or not name or not frappe.db.exists(doctype, name):
		return 0.0, None, "Missing", None

	meta = frappe.get_meta(doctype)
	fields = ["docstatus"]

	for f in ["grand_total", "total_amount", "paid_amount", "total_debit", "total_credit"]:
		if meta.has_field(f):
			fields.append(f)
			break

	for d in ["posting_date", "transaction_date"]:
		if meta.has_field(d):
			fields.append(d)
			break

	for c in ["currency", "paid_from_account_currency"]:
		if meta.has_field(c):
			fields.append(c)
			break

	doc_data = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not doc_data:
		return 0.0, None, "Missing", None

	amount = 0.0
	for amt_field in ["grand_total", "total_amount", "paid_amount", "total_debit", "total_credit"]:
		if doc_data.get(amt_field) is not None:
			amount = flt(doc_data.get(amt_field))
			break

	post_date = doc_data.get("posting_date") or doc_data.get("transaction_date")
	status = "Submitted" if doc_data.get("docstatus") == 1 else "Draft"
	currency = doc_data.get("currency") or doc_data.get("paid_from_account_currency")
	if not currency and company:
		currency = frappe.db.get_value("Company", company, "default_currency")

	return amount, post_date, status, currency


def get_report_summary(data):
	total_a = sum(flt(d.get("amount_a")) for d in data)
	total_b = sum(flt(d.get("amount_b")) for d in data)
	variance = flt(total_a - total_b, 2)
	matched_count = sum(1 for d in data if d.get("status") == "Matched")
	unmatched_count = len(data) - matched_count

	return [
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
			"indicator": "Green" if abs(variance) < 0.1 else "Red",
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
