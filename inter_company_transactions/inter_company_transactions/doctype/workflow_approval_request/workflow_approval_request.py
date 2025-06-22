import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, time_diff_in_hours, add_days, get_datetime_str


class WorkflowApprovalRequest(Document):
    def validate(self):
        self.set_created_date_if_missing()
        self.validate_companies()
        self.update_sla_status()
        self.validate_approval_levels()

    def handle_approval(self):
        if self.status == "Approved":
            self.completed_date = now_datetime()
        # Process the approved transaction
            from intercompany_transactions.workflow import process_approved_request
            process_approved_request(self)
        elif self.status == "Rejected":
            self.cancel_linked_documents()

def notify_next_approvers(self):
    """Send notifications to all approvers at current level"""
    workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
    approvers = workflow.get_approvers_for_level(self.current_approval_level)

    for approver in approvers:
        # Get actual user emails based on approver type
        recipients = []
        if approver.approver_type == "User":
            recipients.append(approver.approver_user)
        elif approver.approver_type == "Role":
            role_users = frappe.get_all(
                "Has Role",
                filters={"role": approver.approver_role},
                fields=["parent"]
            )
            recipients.extend([u.parent for u in role_users])

        for user in recipients:
            if workflow.email_notifications:
                self.send_email_notification(user)
            if workflow.in_app_notifications:
                self.create_in_app_notification(user)

    def before_save(self):
        self.calculate_total_processing_time()
        self.update_current_approval_level()

    def on_submit(self):
        self.handle_approval()

    def on_cancel(self):
        self.status = "Cancelled"
        self.save(ignore_permissions=True)
        self.cancel_linked_documents()

    def set_created_date_if_missing(self):
        if not self.created_date:
            self.created_date = now_datetime()

    def validate_companies(self):
        if self.source_company == self.target_company:
            frappe.throw("Source and Target Company must be different")

    def validate_approval_levels(self):
        workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
        if self.required_approvals != workflow.approval_levels:
            self.required_approvals = workflow.approval_levels

    def update_current_approval_level(self):
        if self.status == "Pending":
            workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
            for i in range(1, workflow.approval_levels + 1):
                approvers = workflow.get_approvers_for_level(i)
                if not all(a.approved for a in approvers):
                    self.current_approval_level = i
                    break

    def handle_approval(self):
        if self.status == "Approved":
            self.completed_date = now_datetime()
            self.create_target_document()
        elif self.status == "Rejected":
            self.cancel_linked_documents()

    def create_target_document(self):
        from intercompany_transaction_link import (
            create_purchase_order,
            create_sales_order,
            create_journal_entry,
            create_payment_entry
        )

        source_doc = frappe.get_doc(self.document_type, self.document_name)
        workflow = frappe.get_doc("Inter Company Workflow", self.workflow)

        mapping_info = {
            'mapping': {
                'main_company': self.source_company,
                'other_company': self.target_company,
            },
            'transaction_type': {
                'source_type': workflow.source_document_type,
                'target_type': workflow.target_document_type
            },
            'linked_company': self.get_linked_company_info()
        }

        try:
            if workflow.target_document_type == "Purchase Order":
                target_doc = create_purchase_order(source_doc, mapping_info, "source_to_target")
            elif workflow.target_document_type == "Sales Order":
                target_doc = create_sales_order(source_doc, mapping_info, "source_to_target")
            elif workflow.target_document_type == "Journal Entry":
                target_doc = create_journal_entry(source_doc, mapping_info, "source_to_target")
            elif workflow.target_document_type == "Payment Entry":
                target_doc = create_payment_entry(source_doc, mapping_info, "source_to_target")
            else:
                frappe.throw(f"Unsupported target document type: {workflow.target_document_type}")

            if target_doc:
                self.finalize_target_document(target_doc)

        except Exception as e:
            self.handle_creation_error(e)

    def get_linked_company_info(self):
        return {
            'company': self.target_company,
            'main_company_customer': 'CUST-0001',
            'main_company_supplier': 'SUPP-0001',
            'other_company_customer': 'CUST-0002',
            'other_company_supplier': 'SUPP-0002',
            'main_company_account': 'Temp Account - Main',
            'other_company_account': 'Temp Account - Other'
        }

    def finalize_target_document(self, target_doc):
        target_doc.update({
            'intercompany_workflow_request': self.name,
            'intercompany_source_document': self.document_name,
            'intercompany_source_doctype': self.document_type
        })

        target_doc.flags.ignore_permissions = True
        target_doc.insert()

        self.db_set({
            'target_document_type': target_doc.doctype,
            'target_document_name': target_doc.name,
            'status': 'Completed'
        })

        frappe.msgprint(f"Created {target_doc.doctype} {target_doc.name}")

    def handle_creation_error(self, error):
        error_msg = f"Failed to create target document: {str(error)}"
        frappe.log_error(error_msg, "Workflow Approval Error")

        self.db_set({
            'status': 'Failed',
            'approval_notes': error_msg
        })

        frappe.throw(error_msg, title="Document Creation Failed")

    def cancel_linked_documents(self):
        if self.target_document_type and self.target_document_name:
            target_doc = frappe.get_doc(self.target_document_type, self.target_document_name)
            if target_doc.docstatus == 1:
                target_doc.cancel()

    def update_sla_status(self):
        if self.due_date and self.status in ["Pending", "Escalated"]:
            if now_datetime() > self.due_date:
                self.approval_sla_status = "Breached"
            elif add_days(now_datetime(), 1) >= self.due_date:
                self.approval_sla_status = "Near Breach"
            else:
                self.approval_sla_status = "On Time"

    def calculate_total_processing_time(self):
        if self.created_date and self.completed_date:
            delta = time_diff_in_hours(self.completed_date, self.created_date)
            self.total_processing_time = f"{delta:.2f} hours"

    def add_approval_history(self, approver, action, comments=""):
        self.append("approval_history", {
            "approval_level": self.current_approval_level,
            "approver": approver,
            "action": action,
            "action_date": now_datetime(),
            "comments": comments
        })
        self.save()

    def process_approval(self, approver, action, comments=""):
        if self.status != "Pending":
            frappe.throw("This request is not pending approval")

        workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
        approvers = workflow.get_approvers_for_level(self.current_approval_level)

        if approver not in [a.approver_user for a in approvers]:
            frappe.throw("You are not authorized to approve this request")

        self.add_approval_history(approver, action, comments)

        if action == "Approved":
            if all(a.approved for a in approvers):
                self.completed_approvals += 1
                if self.completed_approvals >= self.required_approvals:
                    self.status = "Approved"
                    self.submit()
                else:
                    self.current_approval_level += 1
                    self.notify_next_approvers()
        else:
            self.status = "Rejected"
            self.save()

    def notify_next_approvers(self):
        """Send notifications to all approvers at current level"""
    workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
    approvers = workflow.get_approvers_for_level(self.current_approval_level)
    
    for approver in approvers:
        if workflow.email_notifications:
            self.send_email_notification(approver)
        if workflow.in_app_notifications:
            self.create_in_app_notification(approver)

def send_email_notification(self, user):
    """Send email notification to approver"""
    try:
        user_email = frappe.db.get_value("User", user, "email")
        if not user_email:
            return

        subject = f"Approval Required: {self.document_type} {self.document_name}"
        message = f"""
        <p>You have a pending approval request:</p>
        <p><strong>Document:</strong> {self.document_type} {self.document_name}</p>
        <p><strong>Company:</strong> {self.source_company}</p>
        <p><strong>Priority:</strong> {self.priority}</p>
        <p><strong>Due Date:</strong> {self.due_date or 'Not specified'}</p>
        <p>Please review and take action.</p>
        """

        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name
        )

        self.db_set("last_notification_sent", now_datetime())

    except Exception as e:
        frappe.log_error(f"Failed to send email notification: {str(e)}")

    def send_email_notification(self, approver):
        """Send email notification to approver"""
        recipients = self.get_approver_emails(approver)
    if not recipients:
        return
        
    subject = f"Approval Required: {self.document_type} {self.document_name}"
    message = self.get_notification_message()
    
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        reference_doctype=self.doctype,
        reference_name=self.name
    )

    def get_approver_emails(self, approver):
        """Get email addresses for approver(s)"""
    if approver.approver_type == "User":
        return [frappe.db.get_value("User", approver.approver_user, "email")]
    elif approver.approver_type == "Role":
        return frappe.db.get_all("User",
            filters={"role_profile_name": approver.approver_role},
            pluck="email")
    return []

    def create_in_app_notification(self, user):
        """Create in-app notification for approver"""
    try:
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Approval Required: {self.document_type} {self.document_name}",
            "for_user": user,
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name
        }).insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Failed to create in-app notification: {str(e)}")


def create_in_app_notification(self, approver):
    """Create in-app notification for approver"""
    users = []
    
    if approver.approver_type == "User":
        users = [approver.approver_user]
    
    elif approver.approver_type == "Role":
        users = frappe.db.get_all(
            "User",
            filters={"role_profile_name": approver.approver_role},
            pluck="name"
        )

    for user in users:
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Approval Required: {self.document_type} {self.document_name}",
            "for_user": user,
            "document_type": self.doctype,
            "document_name": self.name,
            "type": "Alert"
        }).insert(ignore_permissions=True)


    def create_purchase_order(self, sales_order, mapping_info):
        from intercompany_transaction_link import create_purchase_order
        return create_purchase_order(sales_order, {
            "mapping": mapping_info,
            "transaction_type": {
                "source_type": "Sales Order",
                "target_type": "Purchase Order"
            },
            "linked_company": {
                "company": self.target_company,
                "other_company_supplier": self.get_supplier_for_company(self.target_company)
            }
        }, "source_to_target")

    def create_sales_order(self, purchase_order, mapping_info):
        from intercompany_transaction_link import create_sales_order
        return create_sales_order(purchase_order, {
            "mapping": mapping_info,
            "transaction_type": {
                "source_type": "Purchase Order",
                "target_type": "Sales Order"
            },
            "linked_company": {
                "company": self.target_company,
                "other_company_customer": self.get_customer_for_company(self.target_company)
            }
        }, "source_to_target")

    def get_supplier_for_company(self, company):
        pass  # Implement your logic to get the supplier

    def get_customer_for_company(self, company):
        pass  # Implement your logic to get the customer


@frappe.whitelist()
def approve(self, comments=None):
    self.process_approval(frappe.session.user, "Approved", comments)


@frappe.whitelist()
def reject(self, comments=None):
    self.process_approval(frappe.session.user, "Rejected", comments)


@frappe.whitelist()
def delegate(self, delegate_to, comments=None):
    workflow = frappe.get_doc("Inter Company Workflow", self.workflow)
    approvers = workflow.get_approvers_for_level(self.current_approval_level)

    for approver in approvers:
        if approver.approver_user == frappe.session.user:
            approver.process_delegation(frappe.session.user, delegate_to)
            self.add_approval_history(frappe.session.user, "Delegated",
                                      f"Delegated to {delegate_to}. Comments: {comments}")
            break
    else:
        frappe.throw("You are not authorized to delegate this request")

    self.save()
