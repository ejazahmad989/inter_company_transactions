// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.query_reports["Inter Company Balance Reconciliation"] = {
	filters: [
		{
			fieldname: "company_a",
			label: __("Company A"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company")
		},
		{
			fieldname: "company_b",
			label: __("Company B (Sister Entity)"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "All\nMatched\nUnmatched Variance\nMissing in Target",
			default: "All"
		}
	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status") {
			if (data.status === "Matched") {
				value = `<span class="indicator-pill green">${value}</span>`;
			} else if (data.status === "Unmatched Variance") {
				value = `<span class="indicator-pill red">${value}</span>`;
			} else if (data.status === "Missing in Target") {
				value = `<span class="indicator-pill orange">${value}</span>`;
			}
		} else if (column.fieldname === "difference" && Math.abs(data.difference) > 0.05) {
			value = `<span style="color: red; font-weight: bold;">${value}</span>`;
		}
		return value;
	}
};
