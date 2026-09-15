// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inter Company Netting Cycle', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Fetch Open Invoices'), function() {
				frappe.call({
					method: 'fetch_open_invoices',
					doc: frm.doc,
					freeze: true,
					freeze_message: __('Fetching open intercompany invoices...'),
					callback: function() {
						frm.refresh();
					}
				});
			}, __('Actions'));

			frm.add_custom_button(__('Recalculate Netting'), function() {
				frappe.call({
					method: 'calculate_netting',
					doc: frm.doc,
					freeze: true,
					freeze_message: __('Running multilateral netting algorithm...'),
					callback: function() {
						frm.refresh();
					}
				});
			}, __('Actions'));
		}

		if (frm.doc.total_gross_payables > 0 && frm.doc.total_net_settled >= 0) {
			let saved = frm.doc.total_gross_payables - frm.doc.total_net_settled;
			let pct = frm.doc.total_gross_payables > 0 ? ((saved / frm.doc.total_gross_payables) * 100).toFixed(1) : 0;
			if (frm.dashboard && frm.dashboard.set_headline_alert) {
				frm.dashboard.set_headline_alert(
					__('Multilateral Netting Savings: <b>{0}% liquidity efficiency</b> ({1} gross reduced to {2} net cash flow).', [
						pct,
						format_currency(frm.doc.total_gross_payables),
						format_currency(frm.doc.total_net_settled)
					]),
					'green'
				);
			}
		}
	}
});
