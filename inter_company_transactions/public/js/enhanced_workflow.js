// Enhanced Workflow System JavaScript

frappe.ui.form.on('Inter Company Workflow', {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__('Test Workflow'), function() {
            test_workflow(frm);
        });
        
        frm.add_custom_button(__('View Pending Approvals'), function() {
            view_pending_approvals(frm);
        });
        
        frm.add_custom_button(__('Workflow Analytics'), function() {
            show_workflow_analytics(frm);
        });
        
        // Add workflow status indicator
        if (frm.doc.enabled) {
            show_workflow_status(frm);
        }
    },
    
    source_company: function(frm) {
        if (frm.doc.source_company === frm.doc.target_company) {
            frappe.msgprint(__('Source and Target companies cannot be the same'));
            frm.set_value('target_company', '');
        }
    },
    
    target_company: function(frm) {
        if (frm.doc.source_company === frm.doc.target_company) {
            frappe.msgprint(__('Source and Target companies cannot be the same'));
            frm.set_value('target_company', '');
        }
    },
    
    escalation_enabled: function(frm) {
        if (frm.doc.escalation_enabled && !frm.doc.escalation_hours) {
            frm.set_value('escalation_hours', 24);
        }
    }
});

frappe.ui.form.on('Workflow Approval Request', {
    refresh: function(frm) {
        if (frm.doc.status === 'Pending') {
            // Add approval buttons
            frm.add_custom_button(__('Approve'), function() {
                approve_request(frm);
            }, __('Actions')).addClass('btn-primary');
            
            frm.add_custom_button(__('Reject'), function() {
                reject_request(frm);
            }, __('Actions')).addClass('btn-danger');
            
            frm.add_custom_button(__('Delegate'), function() {
                delegate_request(frm);
            }, __('Actions'));
            
            frm.add_custom_button(__('Add Comment'), function() {
                add_comment(frm);
            }, __('Actions'));
        }
        
        // Show approval timeline
        if (frm.doc.approval_history && frm.doc.approval_history.length > 0) {
            show_approval_timeline(frm);
        }
        
        // Show SLA status
        show_sla_status(frm);
    }
});

function test_workflow(frm) {
    if (!frm.doc.name) {
        frappe.msgprint(__('Please save the workflow first'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('Test Workflow'),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'test_document_type',
                label: __('Document Type'),
                options: 'DocType',
                reqd: 1
            },
            {
                fieldtype: 'Dynamic Link',
                fieldname: 'test_document',
                label: __('Test Document'),
                options: 'test_document_type',
                reqd: 1
            },
            {
                fieldtype: 'Currency',
                fieldname: 'test_amount',
                label: __('Test Amount'),
                default: 10000
            }
        ],
        primary_action_label: __('Test'),
        primary_action: function(values) {
            frappe.call({
                method: 'inter_company_transactions.workflow.test_workflow',
                args: {
                    workflow: frm.doc.name,
                    document_type: values.test_document_type,
                    document_name: values.test_document,
                    amount: values.test_amount
                },
                callback: function(r) {
                    if (r.message) {
                        show_test_results(r.message);
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function view_pending_approvals(frm) {
    frappe.route_options = {
        "workflow": frm.doc.name,
        "status": "Pending"
    };
    frappe.set_route("List", "Workflow Approval Request");
}

function show_workflow_analytics(frm) {
    frappe.call({
        method: 'inter_company_transactions.workflow.get_workflow_analytics',
        args: {
            workflow: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                show_analytics_dialog(r.message);
            }
        }
    });
}

function show_workflow_status(frm) {
    let status_html = `
        <div class="workflow-status-indicator">
            <div class="row">
                <div class="col-md-3">
                    <div class="status-card">
                        <h4>${frm.doc.total_approvals || 0}</h4>
                        <p>Total Approvals</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card pending">
                        <h4>${frm.doc.pending_approvals || 0}</h4>
                        <p>Pending Approvals</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card success">
                        <h4>${((frm.doc.total_approvals - frm.doc.pending_approvals) / Math.max(frm.doc.total_approvals, 1) * 100).toFixed(1)}%</h4>
                        <p>Approval Rate</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card ${frm.doc.workflow_status.toLowerCase()}">
                        <h4>${frm.doc.workflow_status}</h4>
                        <p>Status</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    frm.fields_dict.workflow_status.$wrapper.after(status_html);
}

function approve_request(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Approve Request'),
        fields: [
            {
                fieldtype: 'Text',
                fieldname: 'approval_comments',
                label: __('Comments'),
                reqd: 1
            }
        ],
        primary_action_label: __('Approve'),
        primary_action: function(values) {
            frappe.call({
                method: 'inter_company_transactions.workflow.approve_request',
                args: {
                    request: frm.doc.name,
                    comments: values.approval_comments
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('Request approved successfully'));
                        frm.reload_doc();
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function reject_request(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Reject Request'),
        fields: [
            {
                fieldtype: 'Text',
                fieldname: 'rejection_reason',
                label: __('Rejection Reason'),
                reqd: 1
            }
        ],
        primary_action_label: __('Reject'),
        primary_action: function(values) {
            frappe.call({
                method: 'inter_company_transactions.workflow.reject_request',
                args: {
                    request: frm.doc.name,
                    reason: values.rejection_reason
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('Request rejected'));
                        frm.reload_doc();
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function delegate_request(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Delegate Request'),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'delegate_to',
                label: __('Delegate To'),
                options: 'User',
                reqd: 1
            },
            {
                fieldtype: 'Text',
                fieldname: 'delegation_reason',
                label: __('Delegation Reason')
            }
        ],
        primary_action_label: __('Delegate'),
        primary_action: function(values) {
            frappe.call({
                method: 'inter_company_transactions.workflow.delegate_request',
                args: {
                    request: frm.doc.name,
                    delegate_to: values.delegate_to,
                    reason: values.delegation_reason
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('Request delegated successfully'));
                        frm.reload_doc();
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function show_approval_timeline(frm) {
    let timeline_html = '<div class="approval-timeline">';
    
    frm.doc.approval_history.forEach(function(history, index) {
        let icon_class = '';
        let status_class = '';
        
        switch(history.action) {
            case 'Approved':
                icon_class = 'fa-check-circle';
                status_class = 'success';
                break;
            case 'Rejected':
                icon_class = 'fa-times-circle';
                status_class = 'danger';
                break;
            case 'Delegated':
                icon_class = 'fa-share';
                status_class = 'info';
                break;
            default:
                icon_class = 'fa-comment';
                status_class = 'secondary';
        }
        
        timeline_html += `
            <div class="timeline-item ${status_class}">
                <div class="timeline-marker">
                    <i class="fa ${icon_class}"></i>
                </div>
                <div class="timeline-content">
                    <h6>${history.action} by ${history.approver}</h6>
                    <p class="text-muted">${frappe.datetime.str_to_user(history.action_date)}</p>
                    ${history.comments ? `<p>${history.comments}</p>` : ''}
                    ${history.processing_time ? `<small class="text-muted">Processing time: ${history.processing_time}</small>` : ''}
                </div>
            </div>
        `;
    });
    
    timeline_html += '</div>';
    
    frm.fields_dict.approval_history.$wrapper.html(timeline_html);
}

function show_sla_status(frm) {
    if (frm.doc.due_date) {
        let now = new Date();
        let due_date = new Date(frm.doc.due_date);
        let time_remaining = due_date - now;
        let hours_remaining = Math.floor(time_remaining / (1000 * 60 * 60));
        
        let sla_class = 'success';
        let sla_text = 'On Time';
        
        if (hours_remaining < 0) {
            sla_class = 'danger';
            sla_text = 'Overdue';
        } else if (hours_remaining < 24) {
            sla_class = 'warning';
            sla_text = 'Near Breach';
        }
        
        let sla_html = `
            <div class="sla-status ${sla_class}">
                <strong>SLA Status: ${sla_text}</strong>
                ${hours_remaining > 0 ? `<br><small>${hours_remaining} hours remaining</small>` : ''}
            </div>
        `;
        
        frm.fields_dict.approval_sla_status.$wrapper.html(sla_html);
    }
}

// Notification System
frappe.realtime.on('workflow_notification', function(data) {
    if (data.user === frappe.session.user) {
        show_notification(data);
    }
});

function show_notification(data) {
    let notification_html = `
        <div class="workflow-notification ${data.type}">
            <div class="notification-header">
                <strong>${data.title}</strong>
                <button class="close-notification">&times;</button>
            </div>
            <div class="notification-body">
                ${data.message}
            </div>
            <div class="notification-actions">
                ${data.actions ? data.actions.map(action => 
                    `<button class="btn btn-sm btn-${action.type}" onclick="${action.onclick}">${action.label}</button>`
                ).join(' ') : ''}
            </div>
        </div>
    `;
    
    $('body').append(notification_html);
    
    // Auto-hide after 10 seconds
    setTimeout(function() {
        $('.workflow-notification').fadeOut();
    }, 10000);
}

// Enhanced Theme System Integration
$(document).ready(function() {
    // Apply enhanced themes
    apply_enhanced_theme();
    
    // Initialize workflow dashboard
    if (window.location.pathname.includes('workflow')) {
        initialize_workflow_dashboard();
    }
});

function apply_enhanced_theme() {
    frappe.call({
        method: 'inter_company_transactions.enhanced_theme.get_active_theme',
        callback: function(r) {
            if (r.message) {
                let theme = r.message;
                
                // Apply theme classes
                $('body').addClass(theme.theme_class);
                
                // Load theme CSS
                if (theme.css_file) {
                    $('head').append(`<link rel="stylesheet" href="${theme.css_file}">`);
                }
                
                // Apply custom CSS
                if (theme.custom_css) {
                    $('head').append(`<style>${theme.custom_css}</style>`);
                }
                
                // Execute custom JS
                if (theme.custom_js) {
                    eval(theme.custom_js);
                }
            }
        }
    });
}

function initialize_workflow_dashboard() {
    // Create workflow dashboard
    let dashboard_html = `
        <div class="workflow-dashboard">
            <div class="dashboard-header">
                <h3>Workflow Dashboard</h3>
                <div class="dashboard-actions">
                    <button class="btn btn-primary" onclick="create_new_workflow()">New Workflow</button>
                    <button class="btn btn-secondary" onclick="refresh_dashboard()">Refresh</button>
                </div>
            </div>
            <div class="dashboard-content">
                <div class="row">
                    <div class="col-md-3">
                        <div class="dashboard-card">
                            <h4 id="total-workflows">0</h4>
                            <p>Total Workflows</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card">
                            <h4 id="active-workflows">0</h4>
                            <p>Active Workflows</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card">
                            <h4 id="pending-approvals">0</h4>
                            <p>Pending Approvals</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card">
                            <h4 id="overdue-approvals">0</h4>
                            <p>Overdue Approvals</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    $('.layout-main-section').prepend(dashboard_html);
    
    // Load dashboard data
    load_dashboard_data();
}

function load_dashboard_data() {
    frappe.call({
        method: 'inter_company_transactions.workflow.get_dashboard_data',
        callback: function(r) {
            if (r.message) {
                let data = r.message;
                $('#total-workflows').text(data.total_workflows);
                $('#active-workflows').text(data.active_workflows);
                $('#pending-approvals').text(data.pending_approvals);
                $('#overdue-approvals').text(data.overdue_approvals);
            }
        }
    });
}