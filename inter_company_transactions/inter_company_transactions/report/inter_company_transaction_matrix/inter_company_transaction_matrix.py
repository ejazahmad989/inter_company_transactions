# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
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
		limit=500
	)

	for r in refs:
		created_date = getdate(r.creation)
		if filters.get("from_date") and created_date < getdate(filters.from_date):
			continue
		if filters.get("to_date") and created_date > getdate(filters.to_date):
			continue

		source_amount = 0.0
		posting_date = created_date
		target_amount = 0.0

		if frappe.db.exists(r.source_doctype, r.source_name):
			doc = frappe.get_value(
				r.source_doctype,
				r.source_name,
				["grand_total", "total", "posting_date", "transaction_date"],
				as_dict=1
			)
			if doc:
				source_amount = flt(doc.get("grand_total") or doc.get("total"))
				posting_date = doc.get("posting_date") or doc.get("transaction_date") or created_date

		if r.target_doctype and r.target_name and frappe.db.exists(r.target_doctype, r.target_name):
			tdoc = frappe.get_value(
				r.target_doctype,
				r.target_name,
				["grand_total", "total"],
				as_dict=1
			)
			if tdoc:
				target_amount = flt(tdoc.get("grand_total") or tdoc.get("total"))

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
