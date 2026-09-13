// Backdate Permission JavaScript

frappe.ui.form.on('Backdate Permission', {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__('Test Permission'), function() {
            test_backdate_permission(frm);
        });
        
        frm.add_custom_button(__('View Usage Log'), function() {
            view_usage_log(frm);
        });
        
        if (frm.doc.enabled && !frm.doc.approved_by) {
            frm.add_custom_button(__('Approve Permission'), function() {
                approve_permission(frm);
            });
        }
        
        // Show usage statistics
        if (frm.doc.usage_count > 0) {
            show_usage_statistics(frm);
        }
    },
    
    user: function(frm) {
        if (frm.doc.user) {
            frappe.db.get_value('User', frm.doc.user, 'full_name', function(r) {
                frm.set_value('full_name', r.full_name);
            });
        }
    },
    
    auto_expire: function(frm) {
        if (frm.doc.auto_expire && !frm.doc.expires_on) {
            // Set default expiry date to 30 days from now
            let expiry_date = frappe.datetime.add_days(frappe.datetime.get_today(), 30);
            frm.set_value('expires_on', expiry_date);
        }
    },
    
    restrict_to_date_range: function(frm) {
        if (frm.doc.restrict_to_date_range && !frm.doc.date_from) {
            frm.set_value('date_from', frappe.datetime.get_today());
        }
    },
    
    doctype: function(frm) {
        // Show/hide party type field based on document type
        let show_party_type = ['Payment Entry', 'Journal Entry', 'Sales Invoice', 'Purchase Invoice'].includes(frm.doc.doctype);
        frm.toggle_display('party_type', show_party_type);
        
        // Show/hide special permissions based on document type
        frm.toggle_display('allow_stock_accounts', frm.doc.doctype === 'Journal Entry');
        frm.toggle_display('bypass_credit_limit', ['Sales Invoice', 'Sales Order'].includes(frm.doc.doctype));
        frm.toggle_display('allow_negative_stock', ['Stock Entry', 'Delivery Note', 'Sales Invoice'].includes(frm.doc.doctype));
    }
});

function test_backdate_permission(frm) {
    if (!frm.doc.user || !frm.doc.doctype) {
        frappe.msgprint(__('Please select User and Document Type first'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('Test Backdate Permission'),
        fields: [
            {
                fieldtype: 'Date',
                fieldname: 'test_date',
                label: __('Test Date'),
                reqd: 1,
                default: frappe.datetime.get_today()
            },
            {
                fieldtype: 'Link',
                fieldname: 'test_company',
                label: __('Company'),
                options: 'Company'
            },
            {
                fieldtype: 'Select',
                fieldname: 'test_party_type',
                label: __('Party Type'),
                options: '\nCustomer\nSupplier\nEmployee'
            }
        ],
        primary_action_label: __('Test'),
        primary_action: function(values) {
            frappe.call({
                method: 'inter_company_transactions.doctype.backdate_permission.backdate_permission.check_backdate_permission',
                args: {
                    user: frm.doc.user,
                    doctype: frm.doc.doctype,
                    posting_date: values.test_date,
                    company: values.test_company,
                    party_type: values.test_party_type
                },
                callback: function(r) {
                    if (r.message) {
                        let message = r.message.allowed ? 
                            `<div style="color: green;"><strong>✓ Permission Granted</strong><br>${r.message.message}</div>` :
                            `<div style="color: red;"><strong>✗ Permission Denied</strong><br>${r.message.message}</div>`;
                        
                        frappe.msgprint(message);
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function view_usage_log(frm) {
    if (!frm.doc.name) {
        frappe.msgprint(__('Please save the document first'));
        return;
    }
    
    frappe.route_options = {
        "permission": frm.doc.name
    };
    frappe.set_route("List", "Backdate Permission Log");
}

function approve_permission(frm) {
    frappe.confirm(
        __('Are you sure you want to approve this backdate permission?'),
        function() {
            frm.set_value('approved_by', frappe.session.user);
            frm.set_value('approval_date', frappe.datetime.now_datetime());
            frm.save();
            frappe.msgprint(__('Permission approved successfully'));
        }
    );
}

function show_usage_statistics(frm) {
    let stats_html = `
        <div class="usage-statistics" style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <h5>Usage Statistics</h5>
            <div class="row">
                <div class="col-md-6">
                    <strong>Total Usage:</strong> ${frm.doc.usage_count} times
                </div>
                <div class="col-md-6">
                    <strong>Last Used:</strong> ${frm.doc.last_used ? frappe.datetime.str_to_user(frm.doc.last_used) : 'Never'}
                </div>
            </div>
        </div>
    `;
    
    frm.fields_dict.usage_count.$wrapper.after(stats_html);
}

// Document validation hooks
frappe.ui.form.on(['Sales Invoice', 'Purchase Invoice', 'Journal Entry', 'Payment Entry', 'Sales Order', 'Purchase Order'], {
    validate: function(frm) {
        if (frm.doc.posting_date && frm.doc.posting_date !== frappe.datetime.get_today()) {
            validate_backdate_permission(frm);
        }
    }
});

function validate_backdate_permission(frm) {
    frappe.call({
        method: 'inter_company_transactions.doctype.backdate_permission.backdate_permission.check_backdate_permission',
        args: {
            user: frappe.session.user,
            doctype: frm.doc.doctype,
            posting_date: frm.doc.posting_date,
            company: frm.doc.company,
            party_type: frm.doc.party_type
        },
        callback: function(r) {
            if (r.message && !r.message.allowed) {
                frappe.validated = false;
                frappe.msgprint({
                    title: __('Backdate Permission Required'),
                    message: r.message.message,
                    indicator: 'red'
                });
            } else if (r.message && r.message.require_approval) {
                frappe.msgprint({
                    title: __('Approval Required'),
                    message: __('This transaction requires approval from {0}', [r.message.approval_role]),
                    indicator: 'orange'
                });
            }
        }
    });
}

// Auto-check permissions on date change
$(document).on('change', '[data-fieldname="posting_date"]', function() {
    let posting_date = $(this).val();
    let current_date = frappe.datetime.get_today();
    
    if (posting_date && posting_date !== current_date) {
        let form = $(this).closest('.form-layout').data('frm');
        if (form && form.doc.doctype) {
            validate_backdate_permission(form);
        }
    }
});