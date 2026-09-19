# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def ensure_user_notification_settings(user=None):
    """Ensure that the given user has a Notification Settings document in the database"""
    try:
        if not user:
            user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user in ("Guest", "None"):
            return
        
        if frappe.db and hasattr(frappe.db, "table_exists") and frappe.db.table_exists("Notification Settings"):
            if not frappe.db.exists("Notification Settings", user):
                created = False
                try:
                    doc = frappe.new_doc("Notification Settings")
                    doc.name = user
                    doc.user = user
                    doc.flags.ignore_permissions = True
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                    created = True
                except Exception:
                    pass
                
                if not created:
                    try:
                        frappe.db.sql("""
                            INSERT IGNORE INTO `tabNotification Settings`
                            (name, user, creation, modified, modified_by, owner, docstatus)
                            VALUES (%s, %s, NOW(), NOW(), %s, %s, 0)
                        """, (user, user, user, user))
                        frappe.db.commit()
                    except Exception:
                        pass
                
                try:
                    frappe.clear_document_cache("Notification Settings", user)
                except Exception:
                    pass
    except Exception:
        pass

def before_request():
    """Ensure current session user has valid notification settings before desk renders"""
    try:
        user = getattr(getattr(frappe, "session", None), "user", None)
        if user and user not in ("Guest", "None"):
            ensure_user_notification_settings(user)
    except Exception:
        pass

def on_session_creation(login_manager):
    """Handle session creation"""
    try:
        if frappe.session.user != "Guest":
            ensure_user_notification_settings(frappe.session.user)
            # Apply user theme
            from inter_company_transactions.enhanced_theme import apply_user_theme
            apply_user_theme()
            
            # Log session creation
            frappe.log_error(f"Session created for user: {frappe.session.user}", "Session Management")
            
    except Exception as e:
        frappe.log_error(f"Error in session creation: {str(e)}", "Session Management")