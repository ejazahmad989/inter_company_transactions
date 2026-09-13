frappe.ui.form.on('Inter Company Transaction Map', {
    setup: function(frm) {
        frm.set_query('other_company', 'transaction_mappings', function(doc) {
            return {
                filters: [
                    ['Company', 'name', '!=', doc.main_company]
                ]
            };
        });
    },

    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Check Counterpart Status'), function() {
                frappe.msgprint(__('Inter-Company Mapping active for ' + frm.doc.main_company));
            });
        }
    }
});
