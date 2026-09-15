// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// For license information, please see license.txt

frappe.ui.form.on('Intercompany Transaction Link', {
	setup: function(frm) {
		// Filter main company customer and supplier to only show parties belonging to or representing the main company
		frm.set_query('main_company_customer', function() {
			return {
				filters: {
					disabled: 0
				}
			};
		});

		frm.set_query('main_company_supplier', function() {
			return {
				filters: {
					disabled: 0
				}
			};
		});
	},

	refresh: function(frm) {
		if (!frm.is_new()) {
			// Button to view linked document references
			frm.add_custom_button(__('Linked Documents'), function() {
				frappe.set_route('List', 'Inter Company Document Reference', {
					source_company: frm.doc.main_company
				});
			}, __('Navigate'));

			// Button to view error logs for this setup
			frm.add_custom_button(__('Sync Error Logs'), function() {
				frappe.set_route('List', 'Inter Company Error Log', {
					source_company: frm.doc.main_company
				});
			}, __('Navigate'));

			// Button to view item SKU mappings between configured companies
			frm.add_custom_button(__('Item SKU Mappings'), function() {
				frappe.set_route('List', 'Intercompany Item Mapping', {
					source_company: frm.doc.main_company
				});
			}, __('Navigate'));

			// Button to populate default transaction pairs
			frm.add_custom_button(__('Populate Default Types'), function() {
				frappe.call({
					doc: frm.doc,
					method: 'populate_default_transaction_types',
					callback: function(r) {
						if (!r.exc) {
							frm.refresh_field('transaction_types');
							frappe.show_alert({
								message: __('Default transaction mappings populated.'),
								indicator: 'green'
							});
						}
					}
				});
			}, __('Actions'));

			// Quick Validation helper
			frm.add_custom_button(__('Validate Setup'), function() {
				validate_transaction_link_setup(frm);
			});
		}
	}
});

function validate_transaction_link_setup(frm) {
	if (!frm.doc.main_company) {
		frappe.msgprint({
			title: __('Validation'),
			indicator: 'red',
			message: __('Please select a Main Company.')
		});
		return;
	}

	if (!frm.doc.companies || frm.doc.companies.length === 0) {
		frappe.msgprint({
			title: __('Validation'),
			indicator: 'orange',
			message: __('No linked companies configured in the table below.')
		});
		return;
	}

	let issues = [];
	frm.doc.companies.forEach((row, idx) => {
		if (!row.company) {
			issues.push(__('Row #{0}: Company is empty', [idx + 1]));
		}
		if (row.company === frm.doc.main_company) {
			issues.push(__('Row #{0}: Linked company cannot be the same as Main Company ({1})', [idx + 1, frm.doc.main_company]));
		}
		if (!row.other_company_customer && !row.other_company_supplier) {
			issues.push(__('Row #{0}: Both Customer and Supplier are blank for {1}', [idx + 1, row.company]));
		}
	});

	if (issues.length > 0) {
		frappe.msgprint({
			title: __('Configuration Notice'),
			indicator: 'orange',
			message: issues.join('<br>')
		});
	} else {
		frappe.msgprint({
			title: __('Configuration Valid'),
			indicator: 'green',
			message: __('All linked companies have valid customer/supplier mappings.')
		});
	}
}
