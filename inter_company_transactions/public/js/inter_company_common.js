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
