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
			frm.add_custom_button(__('Populate All Transaction Types'), function() {
				frappe.call({
					doc: frm.doc,
					method: 'populate_default_transaction_types',
					callback: function(r) {
						if (!r.exc) {
							frm.refresh_field('transaction_types');
							frappe.show_alert({
								message: __('All standard inter-company transaction mappings populated.'),
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
		} else {
			// For new documents, offer a 1-click button to preload all transaction types
			frm.add_custom_button(__('Preload Transaction Types'), function() {
				preload_standard_transaction_types(frm);
			});
		}

		// Render informative helper banner above transaction types grid
		render_transaction_types_guide(frm);
	}
});

// Auto-fill Target Type intelligently when Source Type is selected in child table
frappe.ui.form.on('Intercompany Transaction Type', {
	source_type: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let default_targets = {
			'Sales Order': 'Purchase Order',
			'Purchase Order': 'Sales Order',
			'Sales Invoice': 'Purchase Invoice',
			'Purchase Invoice': 'Sales Invoice',
			'Delivery Note': 'Purchase Receipt',
			'Purchase Receipt': 'Delivery Note',
			'Quotation': 'Supplier Quotation',
			'Supplier Quotation': 'Quotation',
			'Material Request': 'Sales Order',
			'Stock Entry': 'Stock Entry',
			'Journal Entry': 'Journal Entry',
			'Payment Entry': 'Payment Entry'
		};

		if (row.source_type && default_targets[row.source_type]) {
			// If target_type is blank or invalid, auto-fill standard target
			if (!row.target_type || (row.target_type === row.source_type && !['Stock Entry', 'Journal Entry', 'Payment Entry'].includes(row.source_type))) {
				frappe.model.set_value(cdt, cdn, 'target_type', default_targets[row.source_type]);
			}
		}

		if (!row.direction) {
			frappe.model.set_value(cdt, cdn, 'direction', 'Both');
		}
	}
});

function preload_standard_transaction_types(frm) {
	let mappings = [
		{ source_type: "Sales Order", target_type: "Purchase Order", direction: "Both" },
		{ source_type: "Purchase Order", target_type: "Sales Order", direction: "Both" },
		{ source_type: "Sales Invoice", target_type: "Purchase Invoice", direction: "Both" },
		{ source_type: "Purchase Invoice", target_type: "Sales Invoice", direction: "Both" },
		{ source_type: "Delivery Note", target_type: "Purchase Receipt", direction: "Both" },
		{ source_type: "Purchase Receipt", target_type: "Delivery Note", direction: "Both" },
		{ source_type: "Quotation", target_type: "Supplier Quotation", direction: "Both" },
		{ source_type: "Supplier Quotation", target_type: "Quotation", direction: "Both" },
		{ source_type: "Material Request", target_type: "Sales Order", direction: "Both" },
		{ source_type: "Material Request", target_type: "Purchase Order", direction: "Both" },
		{ source_type: "Stock Entry", target_type: "Stock Entry", direction: "Both" },
		{ source_type: "Journal Entry", target_type: "Journal Entry", direction: "Both" },
		{ source_type: "Payment Entry", target_type: "Payment Entry", direction: "Both" }
	];

	let existing = new Set((frm.doc.transaction_types || []).map(r => `${r.source_type}->${r.target_type}`));
	let count = 0;

	mappings.forEach(m => {
		if (!existing.has(`${m.source_type}->${m.target_type}`)) {
			let child = frm.add_child('transaction_types');
			child.source_type = m.source_type;
			child.target_type = m.target_type;
			child.direction = m.direction;
			count++;
		}
	});

	frm.refresh_field('transaction_types');
	frappe.show_alert({
		message: __(`Loaded ${count} standard transaction types.`),
		indicator: 'green'
	});
}

function render_transaction_types_guide(frm) {
	let grid = frm.fields_dict.transaction_types;
	if (!grid || !grid.$wrapper) return;

	grid.$wrapper.find('.ict-tx-guide-banner').remove();

	let html = `
		<div class="ict-tx-guide-banner alert alert-info" style="margin-bottom: 12px; font-size: 12px; line-height: 1.5; border-left: 4px solid #17a2b8; background: #f4fbfd; color: #0c5460; padding: 10px 14px; border-radius: 4px;">
			<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
				<strong><i class="fa fa-exchange"></i> Supported Inter-Company Transaction Types & Pairings:</strong>
				<button type="button" class="btn btn-xs btn-default ict-btn-preload-tx" style="padding: 2px 8px; font-weight: 600;">
					<i class="fa fa-plus"></i> Populate All Supported Types
				</button>
			</div>
			<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px;">
				<div><strong>Commercial:</strong> Sales Order &harr; Purchase Order</div>
				<div><strong>Invoicing:</strong> Sales Invoice &harr; Purchase Invoice</div>
				<div><strong>Fulfillment:</strong> Delivery Note &harr; Purchase Receipt</div>
				<div><strong>Pre-Sales:</strong> Quotation &harr; Supplier Quotation</div>
				<div><strong>Requisition:</strong> Material Request &rarr; SO / PO</div>
				<div><strong>Inventory:</strong> Stock Entry &harr; Stock Entry</div>
				<div><strong>General Ledger:</strong> Journal Entry &harr; Journal Entry</div>
				<div><strong>Cash & Bank:</strong> Payment Entry &harr; Payment Entry</div>
			</div>
		</div>
	`;

	grid.$wrapper.prepend(html);

	grid.$wrapper.find('.ict-btn-preload-tx').on('click', function(e) {
		e.preventDefault();
		preload_standard_transaction_types(frm);
	});
}

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
