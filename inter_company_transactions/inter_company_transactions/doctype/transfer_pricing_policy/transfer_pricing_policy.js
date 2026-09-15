// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Transfer Pricing Policy', {
	refresh: function(frm) {
		frm.set_query('to_company', function() {
			return {
				filters: [
					['Company', 'name', '!=', frm.doc.from_company || '']
				]
			};
		});
	},
	from_company: function(frm) {
		if (frm.doc.from_company && frm.doc.to_company === frm.doc.from_company) {
			frm.set_value('to_company', '');
		}
	}
});
