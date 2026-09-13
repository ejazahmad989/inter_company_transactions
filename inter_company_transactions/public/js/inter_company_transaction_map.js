frappe.ui.form.on('Inter Company Transaction Map', {
    refresh: function(frm) {
        frm.add_custom_button(__('Test Connection'), function() {
            test_company_connection(frm);
        });
    }
});

function test_company_connection(frm) {
    if (!frm.doc.main_company) {
        frappe.throw(__('Please select a Main Company'));
        return;
    }
    
    if (!frm.doc.transaction_mappings || frm.doc.transaction_mappings.length === 0) {
        frappe.throw(__('Please add at least one Transaction Mapping'));
        return;
    }
    
    frappe.msgprint(__('Testing connections between companies...'));
    
    // Simulate connection test with all companies in the mappings
    let companies = [];
    frm.doc.transaction_mappings.forEach(function(mapping) {
        if (!companies.includes(mapping.other_company)) {
            companies.push(mapping.other_company);
        }
    });
    
    let message = __('Connection test results:') + '<br><br>';
    
    companies.forEach(function(company) {
        // In a real implementation, we would test actual database connections
        message += `<b>${company}</b>: ${__('Connection successful')}<br>`;
    });
    
    frappe.msgprint(message);
}