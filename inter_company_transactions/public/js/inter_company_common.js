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
		'Payment Entry'
	];

	supportedDocTypes.forEach(function(dt) {
		frappe.ui.form.on(dt, {
			refresh: function(frm) {
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
				} else if (frm.doc.docstatus === 1) {
					// Allow manual sync trigger for submitted documents
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

				// Filter intercompany target company field so user cannot select current company
				if (frm.fields_dict.intercompany_target_company) {
					frm.set_query('intercompany_target_company', function() {
						return {
							filters: [
								['Company', 'name', '!=', frm.doc.company || '']
							]
						};
					});
				}
			}
		});
	});
})();
