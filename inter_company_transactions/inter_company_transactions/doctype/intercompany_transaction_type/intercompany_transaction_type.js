// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// For license information, please see license.txt

(function() {
	const ICT_TARGET_MAPPING = {
		'Sales Order': 'Purchase Order',
		'Purchase Order': 'Sales Order',
		'Sales Invoice': 'Purchase Invoice',
		'Purchase Invoice': 'Sales Invoice',
		'Delivery Note': 'Purchase Receipt',
		'Purchase Receipt': 'Delivery Note',
		'Stock Entry': 'Stock Entry',
		'Journal Entry': 'Journal Entry',
		'Payment Entry': 'Payment Entry',
		'Quotation': 'Supplier Quotation',
		'Supplier Quotation': 'Quotation',
		'Material Request': 'Purchase Order',
		'Request for Quotation': 'Supplier Quotation',
		'Subcontracting Order': 'Purchase Order',
		'Landed Cost Voucher': 'Journal Entry'
	};

	frappe.ui.form.on('Intercompany Transaction Type', {
		source_type: function(frm, cdt, cdn) {
			let row = locals[cdt][cdn];
			if (!row || !row.source_type) return;

			let target = ICT_TARGET_MAPPING[row.source_type];
			if (target) {
				frappe.model.set_value(cdt, cdn, 'target_type', target);
			}

			if (!row.direction) {
				frappe.model.set_value(cdt, cdn, 'direction', 'Both');
			}
		}
	});
})();
