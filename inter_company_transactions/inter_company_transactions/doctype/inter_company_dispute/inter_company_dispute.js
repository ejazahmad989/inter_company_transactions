// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inter Company Dispute', {
	refresh: function(frm) {
		if (frm.doc.status !== 'Resolved' && frm.doc.status !== 'Rejected') {
			frm.add_custom_button(__('Execute Resolution'), function() {
				frappe.confirm(
					__('Are you sure you want to execute resolution action "{0}"?', [frm.doc.resolution_action]),
					function() {
						frappe.call({
							method: 'execute_resolution',
							doc: frm.doc,
							freeze: true,
							freeze_message: __('Executing dispute resolution...'),
							callback: function() {
								frm.refresh();
							}
						});
					}
				);
			}, __('Actions'));
		}
	},
	source_amount: function(frm) {
		frm.trigger('calc_variance');
	},
	target_amount: function(frm) {
		frm.trigger('calc_variance');
	},
	calc_variance: function(frm) {
		let v = Math.abs((frm.doc.target_amount || 0) - (frm.doc.source_amount || 0));
		frm.set_value('variance_amount', v);
	}
});
