frappe.ui.form.on('Inter Company Workflow', {
    source_document_type: function(frm) {
        if (frm.doc.source_document_type) {
            frappe.call({
                method: 'inter_company_transactions.inter_company_workflow.doctype.inter_company_workflow.inter_company_workflow.get_valid_target_types',
                args: {
                    source_type: frm.doc.source_document_type
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_df_property('target_document_type', 'options', r.message);
                    }
                }
            });
        }
    }
});