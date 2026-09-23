// Client-side script for Workflow Approval Request
frappe.ui.form.on('Workflow Approval Request', {
    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.status === 'Pending') {
            frm.add_custom_button(__('Approve'), function() {
                frappe.prompt([
                    {
                        fieldname: 'comments',
                        fieldtype: 'Small Text',
                        label: __('Comments')
                    }
                ], function(values) {
                    frm.call('approve', { comments: values.comments || '' }).then(() => {
                        frm.reload_doc();
                    });
                }, __('Approve Request'), __('Approve'));
            }, __('Actions')).addClass('btn-primary');

            frm.add_custom_button(__('Reject'), function() {
                frappe.prompt([
                    {
                        fieldname: 'comments',
                        fieldtype: 'Small Text',
                        label: __('Reason for Rejection'),
                        reqd: 1
                    }
                ], function(values) {
                    frm.call('reject', { comments: values.comments || '' }).then(() => {
                        frm.reload_doc();
                    });
                }, __('Reject Request'), __('Reject'));
            }, __('Actions')).addClass('btn-danger');

            frm.add_custom_button(__('Delegate'), function() {
                frappe.prompt([
                    {
                        fieldname: 'delegate_to',
                        fieldtype: 'Link',
                        options: 'User',
                        label: __('Delegate To'),
                        reqd: 1
                    },
                    {
                        fieldname: 'comments',
                        fieldtype: 'Small Text',
                        label: __('Comments')
                    }
                ], function(values) {
                    frm.call('delegate', {
                        delegate_to: values.delegate_to,
                        comments: values.comments || ''
                    }).then(() => {
                        frm.reload_doc();
                    });
                }, __('Delegate Request'), __('Delegate'));
            }, __('Actions'));
        }
    }
});
