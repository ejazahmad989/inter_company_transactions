// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// Desk enhancements for intercompany transactions

(function() {
	const supportedDocTypes = [
		'Sales Order',
		'Purchase Order',
		'Sales Invoice',
		'Purchase Invoice',
		'Delivery Note',
		'Purchase Receipt',
		'Quotation',
		'Supplier Quotation',
		'Material Request',
		'Stock Entry',
		'Journal Entry',
		'Payment Entry',
		'Request for Quotation'
	];

	function sync_intercompany_state(frm) {
		if (!frm.fields_dict.is_intercompany || !frm.fields_dict.intercompany_target_company) {
			return;
		}

		const is_intercompany = cint(frm.doc.is_intercompany);
		const current_company = frm.doc.company || '';

		if (!is_intercompany) {
			// Normal internal transaction:
			// 1. Target company is read-only
			frm.set_df_property('intercompany_target_company', 'read_only', 1);
			frm.set_df_property('intercompany_target_company', 'reqd', 0);

			// 2. Target company reflects same company as document
			if (current_company && frm.doc.intercompany_target_company !== current_company) {
				if (frm.doc.docstatus === 0) {
					frm.set_value('intercompany_target_company', current_company);
				}
			}

			// Clear filter query so current company does not get blocked if viewed
			frm.set_query('intercompany_target_company', function() {
				return {};
			});
		} else {
			// Intercompany transaction:
			// 1. Target company is editable (if draft) and mandatory
			if (frm.doc.docstatus === 0) {
				frm.set_df_property('intercompany_target_company', 'read_only', 0);
				frm.set_df_property('intercompany_target_company', 'reqd', 1);

				// 2. If it is currently holding the source company, clear it to prompt user selection
				if (frm.doc.intercompany_target_company && frm.doc.intercompany_target_company === current_company) {
					frm.set_value('intercompany_target_company', '');
				}
			}

			// 3. Filter query so user can ONLY select other sister companies
			frm.set_query('intercompany_target_company', function() {
				return {
					filters: [
						['Company', 'name', '!=', current_company]
					]
				};
			});
		}
	}

	supportedDocTypes.forEach(function(dt) {
		frappe.ui.form.on(dt, {
			onload: function(frm) {
				sync_intercompany_state(frm);
			},
			refresh: function(frm) {
				sync_intercompany_state(frm);

				// Show navigation button to linked document if one exists
				if (frm.doc.intercompany_linked_doc_name && frm.doc.intercompany_linked_doc_doctype) {
					const targetDocType = frm.doc.intercompany_linked_doc_doctype;
					const targetDocName = frm.doc.intercompany_linked_doc_name;
					const targetCompany = frm.doc.intercompany_linked_company || '';

					frm.add_custom_button(
						__('Open Linked {0}', [__(targetDocType)]),
						function() {
							frappe.set_route('Form', targetDocType, targetDocName);
						},
						__('Inter Company')
					);

					// Raise dispute button for enterprise dispute management
					frm.add_custom_button(
						__('Raise Dispute'),
						function() {
							frappe.new_doc('Inter Company Dispute', {
								source_doctype: frm.doc.doctype,
								source_name: frm.doc.name,
								source_company: frm.doc.company,
								target_company: targetCompany,
								source_amount: frm.doc.grand_total || frm.doc.total || 0,
								dispute_title: __('Dispute for {0} {1}', [frm.doc.doctype, frm.doc.name])
							});
						},
						__('Inter Company')
					);

					// Add badge/intro banner in dashboard
					if (frm.dashboard && frm.dashboard.set_headline_alert) {
						frm.dashboard.set_headline_alert(
							__('Linked Inter-Company Document: <a href="/app/{0}/{1}"><b>{2} {3}</b></a> ({4})', [
								frappe.router.slug(targetDocType),
								targetDocName,
								__(targetDocType),
								targetDocName,
								targetCompany
							]),
							'blue'
						);
					}
				} else if (frm.doc.docstatus === 1 && cint(frm.doc.is_intercompany)) {
					// Allow manual sync trigger for submitted documents ONLY IF is_intercompany is checked
					frm.add_custom_button(
						__('Sync Mirror Now'),
						function() {
							frappe.call({
								method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.trigger_manual_intercompany_sync',
								args: {
									doctype: frm.doc.doctype,
									name: frm.doc.name
								},
								freeze: true,
								freeze_message: __('Processing Inter-Company Mirroring...'),
								callback: function(r) {
									if (r.message && r.message.success) {
										frappe.show_alert({
											message: r.message.message,
											indicator: 'green'
										});
										frm.reload_doc();
									} else if (r.message) {
										frappe.msgprint({
											title: __('Inter-Company Sync Notice'),
											indicator: 'orange',
											message: r.message.message
										});
									}
								}
							});
						},
						__('Inter Company')
					);
				}
			},
			is_intercompany: function(frm) {
				sync_intercompany_state(frm);
				if (cint(frm.doc.is_intercompany)) {
					frappe.show_alert({
						message: __('Intercompany mode enabled: Select target sister company in Intercompany Target Company.'),
						indicator: 'blue'
					});
				} else {
					frappe.show_alert({
						message: __('Standard internal transaction: Intercompany Target Company set to {0}.', [frm.doc.company || '']),
						indicator: 'gray'
					});
				}
			},
			company: function(frm) {
				if (!cint(frm.doc.is_intercompany)) {
					if (frm.doc.company) {
						frm.set_value('intercompany_target_company', frm.doc.company);
					}
				} else {
					if (frm.doc.intercompany_target_company === frm.doc.company) {
						frm.set_value('intercompany_target_company', '');
					}
				}
				sync_intercompany_state(frm);
			},
			validate: function(frm) {
				if (cint(frm.doc.is_intercompany)) {
					if (!frm.doc.intercompany_target_company) {
						frappe.msgprint({
							title: __('Intercompany Target Company Required'),
							indicator: 'red',
							message: __('Please select an Intercompany Target Company for this inter-company transaction.')
						});
						frappe.validated = false;
						return false;
					}
					if (frm.doc.company && frm.doc.intercompany_target_company === frm.doc.company) {
						frappe.msgprint({
							title: __('Invalid Intercompany Target Company'),
							indicator: 'red',
							message: __('For an inter-company transaction, Target Company cannot be the same as Source Company ({0}). Please choose another sister company.', [frm.doc.company])
						});
						frappe.validated = false;
						return false;
					}
				} else {
					if (frm.doc.company && frm.fields_dict.intercompany_target_company && frm.doc.intercompany_target_company !== frm.doc.company) {
						frm.set_value('intercompany_target_company', frm.doc.company);
					}
				}
			}
		});
	});
})();

