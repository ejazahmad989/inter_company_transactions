// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// For license information, please see license.txt

frappe.listview_settings['Intercompany Transaction Link'] = {
	add_fields: ['sister_company', 'main_company', 'enabled'],
	hide_name_column: false,
	get_indicator: function(doc) {
		if (doc.enabled) {
			return [__('Enabled'), 'green', 'enabled,=,1'];
		} else {
			return [__('Disabled'), 'gray', 'enabled,=,0'];
		}
	},
	formatters: {
		name: function(val, df, doc) {
			// Ensure list view displays sister company name instead of random hash ID
			return doc.sister_company || val;
		},
		sister_company: function(val, df, doc) {
			return val || doc.name;
		}
	}
};
