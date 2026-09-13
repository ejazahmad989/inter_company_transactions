# inter_company_workflow_approver.py

import frappe
from frappe.model.document import Document

class InterCompanyWorkflowApprover(Document):
    def validate(self):
        self.validate_approver()
        
    def validate_approver(self):
        """Validate that approver is properly set based on type"""
        if self.approver_type == "User" and not self.approver_user:
            frappe.throw("Approver User is required when Approver Type is User")
        elif self.approver_type == "Role" and not self.approver_role:
            frappe.throw("Approver Role is required when Approver Type is Role")
            
    def get_approver_users(self):
        """Get list of users who can approve based on settings"""
        if self.approver_type == "User":
            return [self.approver_user]
        elif self.approver_type == "Role":
            return frappe.get_all("User", 
                filters={"role_profile_name": self.approver_role},
                pluck="name")
        return []
        
    def process_delegation(self, delegator):
        """Process delegation request"""
        if not self.can_delegate:
            frappe.throw("Delegation is not allowed for this approval level")
            
        if not self.delegate_to:
            frappe.throw("Please select a user to delegate to")
            
        # Add to approval history
        parent = frappe.get_doc("Inter Company Workflow", self.parent)
        parent.add_approval_history({
            "approval_level": self.approval_level,
            "approver": delegator,
            "action": "Delegated",
            "delegated_to": self.delegate_to,
            "action_date": frappe.utils.now_datetime()
        })
        
        # Update approver
        self.approver_user = self.delegate_to
        self.save()