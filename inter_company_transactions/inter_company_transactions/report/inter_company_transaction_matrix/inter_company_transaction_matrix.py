# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def get_columns():
	return [
		{
			"label": _("Source Company"),
			"fieldname": "source_company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 140,
		},
		{
			"label": _("Source Type"),
			"fieldname": "source_doctype",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 120,
		},
		{
			"label": _("Source Document"),
			"fieldname": "source_name",
			"fieldtype": "Dynamic Link",
			"options": "source_doctype",
			"width": 140,
		},
		{
			"label": _("Target Company"),
			"fieldname": "target_company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 140,
		},
		{
			"label": _("Target Type"),
			"fieldname": "target_doctype",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 120,
		},
		{
			"label": _("Target Document"),
			"fieldname": "target_name",
			"fieldtype": "Dynamic Link",
			"options": "target_doctype",
			"width": 140,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Source Amount"),
			"fieldname": "source_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Target Amount"),
			"fieldname": "target_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Variance"),
			"fieldname": "variance",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120,
		},
	]


def _get_doc_summary(doctype, name, column_cache, default_date=None):
	"""Safely fetch amount and date for any DocType without querying non-existent SQL columns."""
	if not doctype or not name or not frappe.db.exists(doctype, name):
		return 0.0, default_date

	amt_candidates = (
		"grand_total",
		"total",
		"total_amount",
		"paid_amount",
		"total_debit",
		"total_credit",
		"total_taxes_and_charges",
	)
	date_candidates = ("posting_date", "transaction_date")

	if doctype not in column_cache:
		amt_cols = [c for c in amt_candidates if frappe.db.has_column(doctype, c)]
		date_cols = [c for c in date_candidates if frappe.db.has_column(doctype, c)]
		column_cache[doctype] = (amt_cols, date_cols)

	amt_cols, date_cols = column_cache[doctype]
	fields = ["name", *amt_cols, *date_cols]
	doc = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not doc:
		return 0.0, default_date

	amount = 0.0
	for col in amt_cols:
		if doc.get(col) is not None:
			amount = flt(doc.get(col))
			break

	tx_date = default_date
	for col in date_cols:
		if doc.get(col):
			tx_date = doc.get(col)
			break

	return amount, tx_date


def get_data(filters):
	data = []
	cond = {}
	if filters.get("source_company"):
		cond["source_company"] = filters.source_company
	if filters.get("target_company"):
		cond["target_company"] = filters.target_company
	if filters.get("doctype"):
		cond["source_doctype"] = filters.doctype

	refs = frappe.get_all(
		"Inter Company Document Reference",
		filters=cond,
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
		limit=500,
	)

	column_cache = {}
	for r in refs:
		created_date = getdate(r.creation)
		if filters.get("from_date") and created_date < getdate(filters.from_date):
			continue
		if filters.get("to_date") and created_date > getdate(filters.to_date):
			continue

		source_amount, posting_date = _get_doc_summary(
			r.source_doctype, r.source_name, column_cache, default_date=created_date
		)
		target_amount, _unused = _get_doc_summary(
			r.target_doctype, r.target_name, column_cache, default_date=created_date
		)

		variance = round(abs(source_amount - target_amount), 2)
		status = "Synchronized"
		if not r.target_name:
			status = "Pending Mirror"
		elif variance > 0.05:
			status = "Variance"

		if filters.get("status") and filters.status != "All" and status != filters.status:
			continue

		data.append({
			"source_company": r.source_company,
			"source_doctype": r.source_doctype,
			"source_name": r.source_name,
			"target_company": r.target_company,
			"target_doctype": r.target_doctype or "",
			"target_name": r.target_name or "",
			"posting_date": posting_date,
			"source_amount": source_amount,
			"target_amount": target_amount,
			"variance": variance,
			"status": status,
		})

	return data


def get_chart_data(data):
	if not data:
		return None

	status_counts = {}
	for row in data:
		st = row.get("status") or "Unknown"
		status_counts[st] = status_counts.get(st, 0) + 1

	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [{"values": list(status_counts.values())}],
		},
		"type": "donut",
		"colors": ["#28a745", "#ffc107", "#dc3545"],
	}


def get_report_summary(data):
	if not data:
		return []

	total_tx = len(data)
	sync_count = sum(1 for d in data if d.get("status") == "Synchronized")
	var_count = sum(1 for d in data if d.get("status") == "Variance")
	pending_count = sum(1 for d in data if d.get("status") == "Pending Mirror")
	total_variance = sum(flt(d.get("variance")) for d in data)

	return [
		{
			"value": total_tx,
			"label": _("Total Transactions"),
			"datatype": "Int",
		},
		{
			"value": sync_count,
			"label": _("Fully Synchronized"),
			"indicator": "Green",
			"datatype": "Int",
		},
		{
			"value": var_count,
			"label": _("Transactions with Variance"),
			"indicator": "Red" if var_count > 0 else "Grey",
			"datatype": "Int",
		},
		{
			"value": pending_count,
			"label": _("Pending Mirror Creation"),
			"indicator": "Orange" if pending_count > 0 else "Grey",
			"datatype": "Int",
		},
		{
			"value": total_variance,
			"label": _("Total Absolute Variance"),
			"indicator": "Red" if total_variance > 0 else "Green",
			"datatype": "Currency",
		},
	]
