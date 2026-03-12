# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, get_datetime, time_diff_in_hours
import json

@frappe.whitelist()
def create_workflow_request(doc, method=None):
    """Create workflow request when document is submitted"""
    if doc.flags.ignore_workflow:
        return
        
    # Check if this is already a linked document
    if doc.get("intercompany_linked_doc_doctype"):
        return
        
    # Find applicable workflow
    workflow = get_applicable_workflow(doc)
    if not workflow:
        return
        
    # Create workflow approval request
    request = frappe.new_doc("Workflow Approval Request")
    request.update({
        "workflow": workflow.name,
        "document_type": doc.doctype,
        "document_name": doc.name,
        "source_company": doc.company,
        "target_company": workflow.target_company,
        "requested_by": frappe.session.user,
        "required_approvals": workflow.approval_levels,
        "status": "Pending",
        "priority": "Medium"
    })
    
    if workflow.escalation_enabled:
        request.due_date = frappe.utils.add_days(
            frappe.utils.now_datetime(), 
            workflow.escalation_hours/24
        )
    
    request.insert(ignore_permissions=True)
    request.notify_next_approvers()
    frappe.db.commit()

def get_applicable_workflow(doc):
    """Find workflow matching this document"""
    workflows = frappe.get_all("Inter Company Workflow",
        filters={
            "source_document_type": doc.doctype,
            "source_company": doc.company,
            "enabled": 1
        },
        fields=["name"])
        
    if workflows:
        return frappe.get_doc("Inter Company Workflow", workflows[0].name)
    return None

@frappe.whitelist()
def approve_request(request, comments=""):
    """Approve an approval request"""
    try:
        approval_request = frappe.get_doc("Workflow Approval Request", request)
        workflow = frappe.get_doc("Inter Company Workflow", approval_request.workflow)
        
        # Add to approval history
        approval_request.append("approval_history", {
            "approval_level": approval_request.current_approval_level,
            "approver": frappe.session.user,
            "action": "Approved",
            "action_date": now_datetime(),
            "comments": comments,
            "processing_time": calculate_processing_time(approval_request.created_date)
        })
        
        approval_request.completed_approvals += 1
        
        # Check if all approvals are complete
        if approval_request.completed_approvals >= approval_request.required_approvals:
            approval_request.status = "Approved"
            approval_request.completed_date = now_datetime()
            
            # Process the inter-company transaction
            process_approved_transaction(approval_request)
            
        else:
            # Move to next approval level
            approval_request.current_approval_level += 1
            
            # Send notifications to next level approvers
            send_approval_notifications(approval_request)
        
        approval_request.save()
        
        # Send status update notifications
        send_status_update_notification(approval_request, "approved")
        
        return {
            "success": True,
            "message": "Request approved successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error approving request: {str(e)}", "Workflow Error")
        return {
            "success": False,
            "message": f"Failed to approve request: {str(e)}"
        }

@frappe.whitelist()
def reject_request(request, reason=""):
    """Reject an approval request"""
    try:
        approval_request = frappe.get_doc("Workflow Approval Request", request)
        
        # Add to approval history
        approval_request.append("approval_history", {
            "approval_level": approval_request.current_approval_level,
            "approver": frappe.session.user,
            "action": "Rejected",
            "action_date": now_datetime(),
            "comments": reason,
            "processing_time": calculate_processing_time(approval_request.created_date)
        })
        
        approval_request.status = "Rejected"
        approval_request.completed_date = now_datetime()
        approval_request.save()
        
        # Send rejection notifications
        send_status_update_notification(approval_request, "rejected")
        
        return {
            "success": True,
            "message": "Request rejected"
        }
        
    except Exception as e:
        frappe.log_error(f"Error rejecting request: {str(e)}", "Workflow Error")
        return {
            "success": False,
            "message": f"Failed to reject request: {str(e)}"
        }

@frappe.whitelist()
def delegate_request(request, delegate_to, reason=""):
    """Delegate an approval request"""
    try:
        approval_request = frappe.get_doc("Workflow Approval Request", request)
        
        # Add to approval history
        approval_request.append("approval_history", {
            "approval_level": approval_request.current_approval_level,
            "approver": frappe.session.user,
            "action": "Delegated",
            "action_date": now_datetime(),
            "comments": f"Delegated to {delegate_to}. Reason: {reason}",
            "processing_time": calculate_processing_time(approval_request.created_date)
        })
        
        approval_request.save()
        
        # Send delegation notifications
        send_delegation_notification(approval_request, delegate_to, reason)
        
        return {
            "success": True,
            "message": "Request delegated successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error delegating request: {str(e)}", "Workflow Error")
        return {
            "success": False,
            "message": f"Failed to delegate request: {str(e)}"
        }

def send_approval_notifications(approval_request):
    """Send notifications to approvers"""
    try:
        workflow = frappe.get_doc("Inter Company Workflow", approval_request.workflow)
        
        # Get current level approvers
        current_level_approvers = [
            approver for approver in workflow.approver_mappings 
            if approver.approval_level == approval_request.current_approval_level
        ]
        
        for approver_mapping in current_level_approvers:
            approvers = get_approvers_for_mapping(approver_mapping, approval_request.document_amount)
            
            for approver in approvers:
                # Get notification settings
                notification_settings = get_notification_settings(approver)
                
                if notification_settings and notification_settings.enabled:
                    # Send email notification
                    if notification_settings.email_notifications:
                        send_email_notification(approver, approval_request, "approval_request")
                    
                    # Send in-app notification
                    if notification_settings.in_app_notifications:
                        send_in_app_notification(approver, approval_request, "approval_request")
        
    except Exception as e:
        frappe.log_error(f"Error sending approval notifications: {str(e)}", "Workflow Error")

def get_approvers_for_mapping(approver_mapping, amount):
    """Get list of approvers based on mapping configuration"""
    approvers = []
    
    # Check amount threshold
    if approver_mapping.amount_threshold and amount < approver_mapping.amount_threshold:
        return approvers
    
    if approver_mapping.approver_type == "User":
        if approver_mapping.approver_user:
            approvers.append(approver_mapping.approver_user)
    
    elif approver_mapping.approver_type == "Role":
        if approver_mapping.approver_role:
            role_users = frappe.get_all(
                "Has Role",
                filters={"role": approver_mapping.approver_role},
                fields=["parent"]
            )
            approvers.extend([user.parent for user in role_users])
    
    return approvers

def get_notification_settings(user):
    """Get notification settings for a user without forcing creation"""
    if not user:
        return None

    try:
        return frappe.get_doc("Notification Settings", user)
    except frappe.DoesNotExistError:
        return None  # or return {} if preferred

def send_email_notification(user, approval_request, notification_type):
    """Send email notification"""
    try:
        user_email = frappe.db.get_value("User", user, "email")
        if not user_email:
            return
        
        subject = f"Approval Required: {approval_request.document_type} {approval_request.document_name}"
        message = f"""
        Dear {frappe.db.get_value("User", user, "full_name")},
        
        You have a new approval request:
        
        Document: {approval_request.document_type} {approval_request.document_name}
        Amount: {approval_request.document_amount}
        Requested by: {approval_request.requested_by}
        
        Please log in to the system to review and approve.
        
        Best regards,
        System Administrator
        """
        
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            reference_doctype="Workflow Approval Request",
            reference_name=approval_request.name
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending email notification: {str(e)}", "Workflow Error")

def send_in_app_notification(user, approval_request, notification_type):
    """Send in-app notification"""
    try:
        notification_doc = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Approval Required: {approval_request.document_type} {approval_request.document_name}",
            "for_user": user,
            "type": "Alert",
            "document_type": "Workflow Approval Request",
            "document_name": approval_request.name,
            "from_user": approval_request.requested_by
        })
        notification_doc.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error sending in-app notification: {str(e)}", "Workflow Error")

def calculate_processing_time(start_time):
    """Calculate processing time"""
    try:
        start = get_datetime(start_time)
        end = get_datetime(now_datetime())
        hours = time_diff_in_hours(end, start)
        
        if hours < 1:
            return f"{int(hours * 60)} minutes"
        elif hours < 24:
            return f"{int(hours)} hours"
        else:
            days = int(hours / 24)
            remaining_hours = int(hours % 24)
            return f"{days} days, {remaining_hours} hours"
            
    except:
        return "Unknown"

def process_approved_transaction(approval_request):
    """Process the approved inter-company transaction"""
    try:
        # Get the original document
        doc = frappe.get_doc(approval_request.document_type, approval_request.document_name)
        
        # Create the inter-company transaction
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import create_linked_documents
        
        create_linked_documents(doc, "on_submit")
        
    except Exception as e:
        frappe.log_error(f"Error processing approved transaction: {str(e)}", "Workflow Error")
def process_approved_request(approval_request):
    """Process approved workflow request"""
    try:
        # Get the source document
        source_doc = frappe.get_doc(
            approval_request.document_type, 
            approval_request.document_name
        )
        
        # Create the target document
        from intercompany_transaction_link import create_linked_documents
        create_linked_documents(source_doc, "on_submit")
        
        # Update approval request with target document info
        if source_doc.get("intercompany_linked_doc_name"):
            approval_request.db_set({
                "target_document_type": source_doc.intercompany_linked_doc_doctype,
                "target_document_name": source_doc.intercompany_linked_doc_name
            })
            
    except Exception as e:
        frappe.log_error(
            f"Failed to process approved request {approval_request.name}: {str(e)}",
            "Workflow Error"
        )
        approval_request.db_set({
            "status": "Failed",
            "approval_notes": f"Failed to create target document: {str(e)}"
        })


@frappe.whitelist()
def get_dashboard_data():
    """Get workflow dashboard data"""
    try:
        data = {
            "total_workflows": frappe.db.count("Inter Company Workflow"),
            "active_workflows": frappe.db.count("Inter Company Workflow", {"enabled": 1}),
            "pending_approvals": frappe.db.count("Workflow Approval Request", {"status": "Pending"}),
            "overdue_approvals": frappe.db.count("Workflow Approval Request", {
                "status": "Pending",
                "due_date": ["<", now_datetime()]
            })
        }
        
        return data
        
    except Exception as e:
        frappe.log_error(f"Error getting dashboard data: {str(e)}", "Workflow Error")
        return {}

def send_approval_reminders():
    """Send reminders for pending approvals"""
    try:
        # Get pending approvals that need reminders
        pending_requests = frappe.get_all(
            "Workflow Approval Request",
            filters={
                "status": "Pending",
                "reminder_count": ["<", 3]  # Max 3 reminders
            },
            fields=["name", "workflow", "created_date", "reminder_count", "last_notification_sent"]
        )
        
        for request in pending_requests:
            # Check if reminder is due
            last_notification = request.get("last_notification_sent")
            if last_notification:
                hours_since_last = time_diff_in_hours(get_datetime(now_datetime()), get_datetime(last_notification))
                if hours_since_last < 24:  # Send daily reminders
                    continue
            
            # Send reminder
            approval_request = frappe.get_doc("Workflow Approval Request", request.name)
            send_approval_notifications(approval_request)
            
            # Update reminder count
            frappe.db.set_value("Workflow Approval Request", request.name, {
                "reminder_count": request.reminder_count + 1,
                "last_notification_sent": now_datetime()
            })
            
    except Exception as e:
        frappe.log_error(f"Error sending approval reminders: {str(e)}", "Workflow Error")

def process_escalations():
    """Process escalations for overdue approvals"""
    try:
        # Get overdue approvals
        overdue_requests = frappe.get_all(
            "Workflow Approval Request",
            filters={
                "status": "Pending",
                "due_date": ["<", now_datetime()],
                "escalation_level": ["<", 3]  # Max 3 escalation levels
            },
            fields=["name", "workflow", "escalation_level"]
        )
        
        for request in overdue_requests:
            approval_request = frappe.get_doc("Workflow Approval Request", request.name)
            workflow = frappe.get_doc("Inter Company Workflow", request.workflow)
            
            if workflow.escalation_enabled:
                # Escalate to next level
                escalate_approval_request(approval_request, workflow)
                
    except Exception as e:
        frappe.log_error(f"Error processing escalations: {str(e)}", "Workflow Error")

def escalate_approval_request(approval_request, workflow):
    """Escalate an approval request"""
    try:
        approval_request.escalation_level += 1
        approval_request.escalation_date = now_datetime()
        approval_request.save()
        
    except Exception as e:
        frappe.log_error(f"Error escalating approval request: {str(e)}", "Workflow Error")

def send_status_update_notification(approval_request, status):
    """Send status update notification"""
    try:
        # Send notification to requester
        send_email_notification(approval_request.requested_by, approval_request, status)
        send_in_app_notification(approval_request.requested_by, approval_request, status)
        
    except Exception as e:
        frappe.log_error(f"Error sending status update notification: {str(e)}", "Workflow Error")

def send_delegation_notification(approval_request, delegate_to, reason):
    """Send delegation notification"""
    try:
        send_email_notification(delegate_to, approval_request, "delegation")
        send_in_app_notification(delegate_to, approval_request, "delegation")
        
    except Exception as e:
        frappe.log_error(f"Error sending delegation notification: {str(e)}", "Workflow Error")

# Scheduled task functions
def cleanup_old_notifications():
    """Clean up old notifications"""
    try:
        # Delete notifications older than 30 days
        old_notifications = frappe.get_all(
            "Notification Log",
            filters={
                "creation": ["<", frappe.utils.add_days(frappe.utils.now(), -30)]
            },
            fields=["name"]
        )
        
        for notification in old_notifications:
            frappe.delete_doc("Notification Log", notification.name, ignore_permissions=True)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error cleaning up old notifications: {str(e)}", "Cleanup Error")


import frappe

def on_submit(doc, method):
    """Trigger workflow request on submission"""
    if doc.doctype in ["Sales Order", "Purchase Order", "Journal Entry", "Payment Entry"]:
        create_workflow_request(doc)

def create_workflow_request(source_doc):
    workflows = frappe.get_all("Inter Company Workflow",
        filters={
            "source_document_type": source_doc.doctype,
            "source_company": source_doc.company,
            "enabled": 1
        })

    if not workflows:
        return  # No workflow exists for this combination

    workflow = frappe.get_doc("Inter Company Workflow", workflows[0].name)

    request = frappe.new_doc("Workflow Approval Request")
    request.update({
        "workflow": workflow.name,
        "document_type": source_doc.doctype,
        "document_name": source_doc.name,
        "source_company": source_doc.company,
        "target_company": workflow.target_company,
        "requested_by": frappe.session.user,
        "required_approvals": workflow.approval_levels,
        "status": "Pending",
        "priority": "Medium"
    })

    if workflow.escalation_enabled:
        request.due_date = frappe.utils.add_days(
            frappe.utils.now_datetime(), workflow.escalation_hours / 24
        )

    request.insert()
    request.notify_next_approvers()


import frappe
from frappe.core.doctype.communication.email import make
from frappe.utils import get_url_to_form

def send_workflow_notifications():
    """Send pending workflow notifications"""
    pending_requests = frappe.get_all("Workflow Approval Request",
        filters={"status": "Pending"},
        fields=["name", "workflow", "document_type", "document_name"])
        
    for request in pending_requests:
        doc = frappe.get_doc("Workflow Approval Request", request.name)
        doc.notify_next_approvers()

def get_notification_message(doc):
    """Generate standardized notification message"""
    return f"""
        <p>You have a pending approval request:</p>
        <p><strong>Document:</strong> {doc.document_type} {doc.document_name}</p>
        <p><strong>Priority:</strong> {doc.priority}</p>
        <p><strong>Due Date:</strong> {doc.due_date or 'Not specified'}</p>
        <p>Please review at: <a href="{get_url_to_form(doc.doctype, doc.name)}">{doc.name}</a></p>
    """
