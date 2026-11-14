// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// For license information, please see license.txt

frappe.ui.form.on('Intercompany Transaction Link', {
	setup: function(frm) {
		const PARTY_QUERY = 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.intercompany_party_query';
		const ACCOUNT_QUERY = 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.intercompany_account_query';

		// Prevent picking Main Company inside linked_companies grid
		frm.set_query('company', 'linked_companies', function(doc) {
			return {
				filters: doc.main_company ? [['Company', 'name', '!=', doc.main_company]] : []
			};
		});

		// Main Company Settings (parties representing the sister company; accounts & warehouses belonging to main company)
		frm.set_query('main_company_customer', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!doc.main_company || !row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: PARTY_QUERY,
				filters: {
					company: doc.main_company,
					represents_company: row.company
				}
			};
		});

		frm.set_query('main_company_supplier', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!doc.main_company || !row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: PARTY_QUERY,
				filters: {
					company: doc.main_company,
					represents_company: row.company
				}
			};
		});

		frm.set_query('main_company_account', 'linked_companies', function(doc) {
			if (!doc.main_company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: ACCOUNT_QUERY,
				filters: { company: doc.main_company }
			};
		});

		frm.set_query('main_company_warehouse', 'linked_companies', function(doc) {
			if (!doc.main_company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				filters: {
					company: doc.main_company,
					is_group: 0
				}
			};
		});

		// Other Company Settings (parties representing main company; accounts & warehouses belonging to sister company)
		frm.set_query('other_company_customer', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!doc.main_company || !row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: PARTY_QUERY,
				filters: {
					company: row.company,
					represents_company: doc.main_company
				}
			};
		});

		frm.set_query('other_company_supplier', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!doc.main_company || !row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: PARTY_QUERY,
				filters: {
					company: row.company,
					represents_company: doc.main_company
				}
			};
		});

		frm.set_query('other_company_account', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				query: ACCOUNT_QUERY,
				filters: { company: row.company }
			};
		});

		frm.set_query('other_company_warehouse', 'linked_companies', function(doc, cdt, cdn) {
			let row = locals[cdt] && locals[cdt][cdn];
			if (!row || !row.company) {
				return { filters: { name: ['=', ''] } };
			}
			return {
				filters: {
					company: row.company,
					is_group: 0
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

			// Button to jump to item SKU mappings table
			frm.add_custom_button(__('Item SKU Mappings'), function() {
				frm.scroll_to_field('item_mappings');
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

			// 1-Click Button to scan Chart of Accounts and auto-create Bank-typed TMP-<ABBR> Clearing Accounts
			let all_accounts_configured = (frm.doc.linked_companies || []).length > 0 &&
				(frm.doc.linked_companies || []).every(r => r.main_company_account && r.other_company_account);

			let account_btn_label = all_accounts_configured
				? __('Verify / Sync TMP Bank Accounts')
				: __('Auto-Setup TMP Bank Accounts');
			let account_btn = frm.add_custom_button(account_btn_label, function() {
				frappe.call({
					doc: frm.doc,
					method: 'auto_create_intercompany_accounts',
					freeze: true,
					freeze_message: __('Scanning Chart of Accounts & configuring Bank TMP-<ABBR> Clearing Accounts...'),
					callback: function(r) {
						if (!r.exc && r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: r.message.message || __('Intercompany Bank TMP Clearing Accounts verified and linked.'),
								indicator: 'green'
							});
						}
					}
				});
			}, __('Actions'));

			if (!all_accounts_configured) {
				account_btn.addClass('btn-primary font-weight-bold');
			}

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

		// Ensure sister company field is populated if missing
		if (!frm.doc.sister_company && frm.doc.linked_companies && frm.doc.linked_companies.length) {
			update_sister_company_field(frm);
		}

		// Render informative helper banner above transaction types grid
		render_transaction_types_guide(frm);
	}
});

// Real-time synchronization & smart CoA/party scan when linked companies table changes
frappe.ui.form.on('Intercompany Linked Company', {
	company: function(frm, cdt, cdn) {
		update_sister_company_field(frm);
		let row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.company || !frm.doc.main_company || row.company === frm.doc.main_company) {
			return;
		}
		frappe.call({
			method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.scan_linked_company_defaults',
			args: {
				main_company: frm.doc.main_company,
				other_company: row.company
			},
			callback: function(r) {
				if (!r || !r.message) return;
				let d = r.message;
				const auto_fields = [
					'main_company_customer',
					'main_company_supplier',
					'main_company_account',
					'main_company_warehouse',
					'other_company_customer',
					'other_company_supplier',
					'other_company_account',
					'other_company_warehouse'
				];
				let filled = 0;
				auto_fields.forEach(fn => {
					if (!row[fn] && d[fn]) {
						frappe.model.set_value(cdt, cdn, fn, d[fn]);
						filled++;
					}
				});

				let missing_tmp = [];
				if (!d.main_company_account && !row.main_company_account && d.main_suggested_tmp) {
					missing_tmp.push(`${d.main_suggested_tmp} (${frm.doc.main_company})`);
				}
				if (!d.other_company_account && !row.other_company_account && d.other_suggested_tmp) {
					missing_tmp.push(`${d.other_suggested_tmp} (${row.company})`);
				}

				if (missing_tmp.length > 0) {
					frappe.show_alert({
						message: __('Chart of Accounts scan complete ({0} auto-filled). Click Save then Actions -> Auto-Setup TMP Bank Accounts to create: {1}', [
							filled,
							frappe.utils.escape_html(missing_tmp.join(', '))
						]),
						indicator: 'blue'
					}, 7);
				} else if (filled > 0) {
					frappe.show_alert({
						message: __('Auto-matched {0} existing party/account/warehouse field(s) for {1}.', [
							filled,
							frappe.utils.escape_html(row.company)
						]),
						indicator: 'green'
					});
				}
			}
		});
	},
	linked_companies_remove: function(frm) {
		update_sister_company_field(frm);
	}
});

function update_sister_company_field(frm) {
	let companies = (frm.doc.linked_companies || [])
		.map(d => d.company)
		.filter(Boolean);
	let unique = [...new Set(companies)];
	let sister_str = unique.join(', ');
	if (frm.doc.sister_company !== sister_str) {
		frm.set_value('sister_company', sister_str);
	}
}

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

		if (row && row.source_type && default_targets[row.source_type]) {
			// Auto switch Target Transaction Type whenever Source changes
			frappe.model.set_value(cdt, cdn, 'target_type', default_targets[row.source_type]);
		}

		if (row && !row.direction) {
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
		{ source_type: "Request for Quotation", target_type: "Supplier Quotation", direction: "Both" },
		{ source_type: "Stock Entry", target_type: "Stock Entry", direction: "Both" },
		{ source_type: "Journal Entry", target_type: "Journal Entry", direction: "Both" },
		{ source_type: "Payment Entry", target_type: "Payment Entry", direction: "Both" },
		{ source_type: "Landed Cost Voucher", target_type: "Journal Entry", direction: "Both" }
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
				<div><strong>Procurement:</strong> Request for Quotation &rarr; Supplier Quotation</div>
				<div><strong>Requisition:</strong> Material Request &rarr; SO / PO</div>
				<div><strong>Inventory:</strong> Stock Entry (Issue) &rarr; Stock Entry (Receipt)</div>
				<div><strong>General Ledger:</strong> Journal Entry &harr; Journal Entry</div>
				<div><strong>Cash & Bank:</strong> Payment Entry &harr; Payment Entry</div>
				<div><strong>Landed Cost:</strong> Landed Cost Voucher &rarr; Journal Entry</div>
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

	if (!frm.doc.linked_companies || frm.doc.linked_companies.length === 0) {
		frappe.msgprint({
			title: __('Validation'),
			indicator: 'orange',
			message: __('No linked companies configured in the table below.')
		});
		return;
	}

	let issues = [];
	frm.doc.linked_companies.forEach((row, idx) => {
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
