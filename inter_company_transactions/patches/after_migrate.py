# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def after_migrate():
    """Execute after migration to restore data"""
    print("Running post-migration tasks for Inter Company Transactions...")
    
    # Restore backed up data
    restore_custom_data()
    
    # Recreate any missing doctypes
    recreate_missing_doctypes()
    
    # Ensure custom fields are in place
    ensure_custom_fields()

    # Update permissions
    update_permissions()
    
    print("Post-migration tasks completed successfully!")

def execute():
    """Alias for after_migrate to ensure compatibility"""
    after_migrate()

def ensure_custom_fields():
    """Ensure all required custom fields exist after migration"""
    from inter_company_transactions.install import create_custom_fields
    try:
        create_custom_fields()
        print("Ensured custom fields exist")
    except Exception as e:
        print(f"Error ensuring custom fields: {str(e)}")

def restore_custom_data():
    """Restore backed up custom data"""
    try:
        # Restore workflows
        workflows = frappe.cache().get_value("backup_workflows")
        if workflows:
            for workflow in workflows:
                if not frappe.db.exists("Inter Company Workflow", workflow.get("name")):
                    # Recreate workflow
                    new_workflow = frappe.get_doc({
                        "doctype": "Inter Company Workflow",
                        **workflow
                    })
                    new_workflow.insert(ignore_permissions=True)
            print("Restored workflow data")
        
        # Restore themes
        themes = frappe.cache().get_value("backup_themes")
        if themes:
            for theme in themes:
                if not frappe.db.exists("Enhanced Theme Manager", theme.get("name")):
                    # Recreate theme
                    new_theme = frappe.get_doc({
                        "doctype": "Enhanced Theme Manager",
                        **theme
                    })
                    new_theme.insert(ignore_permissions=True)
            print("Restored theme data")
            
    except Exception as e:
        print(f"Error restoring data: {str(e)}")

def recreate_missing_doctypes():
    """Recreate any missing doctypes"""
    from inter_company_transactions.install import create_doctypes
    
    try:
        create_doctypes()
        print("Recreated missing doctypes")
    except Exception as e:
        print(f"Error recreating doctypes: {str(e)}")

def update_permissions():
    """Update permissions after migration"""
    from inter_company_transactions.install import set_default_permissions
    
    try:
        set_default_permissions()
        print("Updated permissions")
    except Exception as e:
        print(f"Error updating permissions: {str(e)}")