// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.query_reports["Inter Company Transaction Matrix"] = {
	filters: [
		{
			fieldname: "source_company",
			label: __("Source Company"),
			fieldtype: "Link",
			options: "Company"
		},
		{
			fieldname: "target_company",
			label: __("Target Company"),
			fieldtype: "Link",
			options: "Company"
		},
		{
			fieldname: "doctype",
			label: __("Document Type"),
			fieldtype: "Link",
			options: "DocType"
		},
		{
			fieldname: "status",
			label: __("Sync Status"),
			fieldtype: "Select",
			options: "All\nSynchronized\nVariance\nPending Mirror",
			default: "All"
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date"
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date"
		}
	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status") {
			if (data.status === "Synchronized") {
				value = `<span class="indicator-pill green">${value}</span>`;
			} else if (data.status === "Variance") {
				value = `<span class="indicator-pill red">${value}</span>`;
			} else if (data.status === "Pending Mirror") {
				value = `<span class="indicator-pill orange">${value}</span>`;
			}
		} else if (column.fieldname === "variance" && Math.abs(data.variance) > 0.05) {
			value = `<span style="color: red; font-weight: bold;">${value}</span>`;
		}
		return value;
	}
};
