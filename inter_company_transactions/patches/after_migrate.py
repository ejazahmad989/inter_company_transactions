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
    
    # Ensure all users have valid Notification Settings
    ensure_notification_settings_for_all_users()
    
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

def ensure_notification_settings_for_all_users():
    """Ensure every existing User has a valid Notification Settings record"""
    try:
        if frappe.db.exists("DocType", "Notification Settings"):
            # Ensure module is Desk and not custom
            frappe.db.set_value("DocType", "Notification Settings", "module", "Desk")
            frappe.db.set_value("DocType", "Notification Settings", "custom", 0)
            try:
                frappe.reload_doctype("Notification Settings", force=True)
            except Exception:
                pass
            
        users = frappe.get_all("User", pluck="name")
        for u in users:
            if u and u not in ("Guest", "None"):
                if not frappe.db.exists("Notification Settings", u):
                    created = False
                    try:
                        doc = frappe.new_doc("Notification Settings")
                        doc.name = u
                        doc.user = u
                        doc.flags.ignore_permissions = True
                        doc.flags.ignore_mandatory = True
                        doc.insert(ignore_permissions=True)
                        created = True
                    except Exception:
                        pass
                    
                    if not created:
                        try:
                            frappe.db.sql("""
                                INSERT IGNORE INTO `tabNotification Settings`
                                (name, user, creation, modified, modified_by, owner, docstatus)
                                VALUES (%s, %s, NOW(), NOW(), %s, %s, 0)
                            """, (u, u, u, u))
                        except Exception:
                            pass
                
                try:
                    frappe.clear_document_cache("Notification Settings", u)
                except Exception:
                    pass
                    
        frappe.db.commit()
        print("Ensured all users have Notification Settings")
    except Exception as e:
        print(f"Error ensuring Notification Settings: {str(e)}")
