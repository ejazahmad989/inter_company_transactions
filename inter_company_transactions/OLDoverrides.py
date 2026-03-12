# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def enhanced_save_docs(docs, action):
    """Enhanced save docs with workflow integration"""
    try:
        # Call original save method
        from frappe.desk.form.save import savedocs
        result = savedocs(docs, action)
        
        # Check for workflow triggers
        for doc_data in docs:
            if doc_data.get("doctype") in ["Sales Order", "Purchase Order", "Journal Entry", "Payment Entry"]:
                check_workflow_triggers(doc_data)
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Error in enhanced save docs: {str(e)}", "Enhanced Save")
        # Fallback to original method
        from frappe.desk.form.save import savedocs
        return savedocs(docs, action)

def check_workflow_triggers(doc_data):
    """Check if document triggers workflow"""
    try:
        if doc_data.get("docstatus") == 1:  # Submitted
            # Check for applicable workflows
            workflows = frappe.get_all(
                "Inter Company Workflow",
                filters={
                    "enabled": 1,
                    "document_type": doc_data.get("doctype"),
                    "source_company": doc_data.get("company")
                },
                fields=["name"]
            )
            
            for workflow in workflows:
                # Create approval request if needed
                from inter_company_transactions.workflow import create_approval_request
                create_approval_request(
                    doc_data.get("doctype"),
                    doc_data.get("name"),
                    workflow.name,
                    doc_data.get("grand_total", 0)
                )
                
    except Exception as e:
        frappe.log_error(f"Error checking workflow triggers: {str(e)}", "Workflow Trigger")