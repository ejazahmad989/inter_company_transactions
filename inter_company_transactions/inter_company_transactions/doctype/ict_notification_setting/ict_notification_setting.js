// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('ICT Notification Setting', {
	refresh: function(frm) {
		if (frm.is_new() && !frm.doc.user) {
			frm.set_value('user', frappe.session.user);
		}
	}
});
