# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class InterCompanyWorkflow(Document):
    def validate(self):
        self.validate_companies()
        self.validate_approval_levels()
        self.validate_document_types()
        self.set_defaults()

    def validate_companies(self):
        if self.source_company == self.target_company:
            frappe.throw("Source and Target Company must be different")

    def validate_approval_levels(self):
        if self.approval_required and self.approval_levels < 1:
            frappe.throw("Number of Approval Levels must be at least 1")

    def validate_document_types(self):
        valid_mappings = {
            "Sales Order": ["Purchase Order"],
            "Purchase Order": ["Sales Order"],
            "Journal Entry": ["Journal Entry"],
            "Payment Entry": ["Payment Entry"],
            "Sales Invoice": ["Purchase Invoice"],
            "Purchase Invoice": ["Sales Invoice"]
        }

        if self.source_document_type not in valid_mappings:
            frappe.throw(f"Source document type {self.source_document_type} is not supported")

        if self.target_document_type not in valid_mappings.get(self.source_document_type, []):
            frappe.throw(
                f"Invalid document mapping: {self.source_document_type} cannot be mapped to {self.target_document_type}. "
                f"Valid mappings are: {valid_mappings.get(self.source_document_type, [])}"
            )

    def set_defaults(self):
        if not self.created_by_user:
            self.created_by_user = frappe.session.user
        self.last_modified_by = frappe.session.user

    def set_default_approvers(self):
        """Set default approvers for new workflows"""
        # Level 0 - Source company approvers
        self.append("approver_mappings", {
            "approval_level": 0,
            "approver_type": "User",
            "approver_user": "burhan@example.com",  # Replace with actual user
            "is_mandatory": 1
        })

        # Level 1 - Target company approvers
        self.append("approver_mappings", {
            "approval_level": 1,
            "approver_type": "User", 
            "approver_user": "shaid@example.com",  # Replace with actual user
            "is_mandatory": 1
        })

    def before_save(self):
        self.update_approver_counts()

    def update_approver_counts(self):
        """Update total and pending approval counts"""
        self.total_approvals = len(self.approver_mappings or [])
        pending = 0
        for approver in self.approver_mappings or []:
            if approver.is_mandatory and not approver.approved:
                pending += 1
        self.pending_approvals = pending

    def get_next_approval_level(self, current_level):
        """Get next approval level details"""
        return [
            a for a in self.approver_mappings or []
            if a.approval_level == current_level + 1
        ]

    def get_approvers_for_level(self, level):
        """Get all approvers for a specific level"""
        return [
            a for a in self.approver_mappings or []
            if a.approval_level == level
        ]
    
    def after_insert(self):
        """Set default approvers if not specified"""
        if not self.approver_mappings and self.approval_required:
            self.set_default_approvers()
            self.save()


@frappe.whitelist()
def get_valid_target_types(source_type):
    """Return valid target document types for a given source type"""
    valid_mappings = {
        "Sales Order": ["Purchase Order"],
        "Purchase Order": ["Sales Order"],
        "Journal Entry": ["Journal Entry"],
        "Payment Entry": ["Payment Entry"],
        "Sales Invoice": ["Purchase Invoice"],
        "Purchase Invoice": ["Sales Invoice"]
    }
    return valid_mappings.get(source_type, [])
