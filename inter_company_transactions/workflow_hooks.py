import frappe

SUPPORTED_DOCTYPES = [
    "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
    "Delivery Note", "Purchase Receipt", "Stock Entry", "Journal Entry",
    "Payment Entry", "Quotation", "Supplier Quotation", "Material Request"
]

def on_submit(doc, method):
    """Trigger workflow request on submission"""
    if doc.doctype in SUPPORTED_DOCTYPES:
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
