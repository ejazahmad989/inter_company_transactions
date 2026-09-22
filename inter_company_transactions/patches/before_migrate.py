# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def before_migrate():
    """Execute before migration to preserve doctypes"""
    print("Running pre-migration tasks for Inter Company Transactions...")

    # Sanitize custom fields and doctypes before migration begins
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import fix_legacy_custom_fields
        fix_legacy_custom_fields(force=True)
    except Exception as e:
        print(f"Error sanitizing custom fields before migration: {e}")

    # Backup important data before migration
    backup_custom_data()
    
    # Ensure all doctypes are properly flagged as custom
    ensure_custom_doctypes()
    
    print("Pre-migration tasks completed successfully!")

def execute():
    """Alias for before_migrate to ensure compatibility"""
    before_migrate()

def backup_custom_data():
    """Backup custom data that might be affected by migration"""
    try:
        # Backup workflow data
        workflows = frappe.get_all("Inter Company Workflow", fields=["*"])
        if workflows:
            frappe.cache().set_value("backup_workflows", workflows)
            print(f"Backed up {len(workflows)} workflows")
        
        # Backup theme data
        themes = frappe.get_all("Enhanced Theme Manager", fields=["*"])
        if themes:
            frappe.cache().set_value("backup_themes", themes)
            print(f"Backed up {len(themes)} themes")
            
    except Exception as e:
        print(f"Error backing up data: {str(e)}")

def ensure_custom_doctypes():
    """Ensure all our doctypes are marked as custom"""
    custom_doctypes = [
        "Intercompany Transaction Link",
        "Intercompany Linked Company", 
        "Intercompany Transaction Type",
        "Inter Company Document Reference",
        "Backdate Permission",
        "Backdate Permission Company",
        "Theme Manager",
        "Theme Manager Company",
        "Theme Manager User",
        "Theme Manager Role",
        "Enhanced Theme Manager",
        "Inter Company Workflow",
        "Inter Company Workflow Approver",
        "Workflow Approval Request",
        "Workflow Approval History",
        "Intercompany Item Mapping",
        "Inter Company Error Log",
        "Inter Company Settings",
        "Inter Company Netting Cycle",
        "Inter Company Netting Company",
        "Inter Company Netting Invoice",
        "Inter Company Netting Summary",
        "Transfer Pricing Policy",
        "Inter Company Elimination Run",
        "Inter Company Dispute",
        "Inter Company Remote Site"
    ]
    
    for doctype_name in custom_doctypes:
        try:
            if frappe.db.exists("DocType", doctype_name):
                frappe.db.set_value("DocType", doctype_name, "custom", 1)
                print(f"Marked {doctype_name} as custom")
        except Exception as e:
            print(f"Error marking {doctype_name} as custom: {str(e)}")