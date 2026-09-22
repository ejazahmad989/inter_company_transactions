# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def after_migrate():
    """Execute after migration to restore data"""
    print("Running post-migration tasks for Inter Company Transactions...")
    
    # Sanitize custom fields and doctypes to prevent SyntaxError
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import fix_legacy_custom_fields
        fix_legacy_custom_fields(force=True)
    except Exception as e:
        print(f"Error sanitizing custom fields: {e}")

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
    
    # Ensure ICT Notification Setting exists for all users
    ensure_ict_notification_settings_for_all_users()

    # Ensure Page and Workspace exist
    ensure_page_and_workspace()
    
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

def ensure_ict_notification_settings_for_all_users():
    """Ensure every existing User has a valid ICT Notification Setting record"""
    try:
        from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import get_ict_notification_settings
        users = frappe.get_all("User", pluck="name")
        for u in users:
            if u and u not in ("Guest", "None"):
                try:
                    get_ict_notification_settings(u)
                except Exception:
                    pass
        frappe.db.commit()
        print("Ensured all users have ICT Notification Settings")
    except Exception as e:
        print(f"Error ensuring ICT Notification Settings: {str(e)}")

def ensure_page_and_workspace():
    """Ensure Page inter-company-console and Workspace Inter Company exist"""
    import os
    import json
    try:
        # Page
        if not frappe.db.exists("Page", "inter-company-console"):
            page = frappe.new_doc("Page")
            page.name = "inter-company-console"
            page.page_name = "inter-company-console"
            page.title = "Inter-Company Control Console"
            page.module = "Inter Company Transactions"
            page.standard = "Yes"
            for r in ["System Manager", "Accounts Manager", "Accounts User"]:
                page.append("roles", {"role": r})
            page.flags.ignore_permissions = True
            page.insert()
            print("Ensured Page: inter-company-console")
        else:
            page = frappe.get_doc("Page", "inter-company-console")
            roles = [r.role for r in page.roles]
            for r in ["System Manager", "Accounts Manager", "Accounts User"]:
                if r not in roles:
                    page.append("roles", {"role": r})
            page.flags.ignore_permissions = True
            page.save()

        # Workspace
        ws_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "inter_company_transactions",
            "workspace",
            "inter_company",
            "inter_company.json"
        )
        if os.path.exists(ws_file):
            with open(ws_file, "r") as f:
                ws_data = json.load(f)
            if not frappe.db.exists("Workspace", "Inter Company"):
                ws_doc = frappe.get_doc(ws_data)
                ws_doc.flags.ignore_permissions = True
                ws_doc.insert()
                print("Ensured Workspace: Inter Company")
        frappe.db.commit()
    except Exception as e:
        print(f"Error ensuring page or workspace: {str(e)}")

