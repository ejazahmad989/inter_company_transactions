// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inter Company Elimination Run', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Calculate Eliminations'), function() {
				frappe.call({
					method: 'calculate_eliminations',
					doc: frm.doc,
					freeze: true,
					freeze_message: __('Calculating intercompany balance sheet & P&L eliminations...'),
					callback: function() {
						frm.refresh();
					}
				});
			}, __('Actions'));
		}

		if (frm.doc.elimination_journal_entry) {
			frm.add_custom_button(__('Open Elimination Journal'), function() {
				frappe.set_route('Form', 'Journal Entry', frm.doc.elimination_journal_entry);
			});
		}
	}
});
