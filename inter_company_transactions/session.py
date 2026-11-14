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
    """Ensure user has valid notification settings without triggering DDL or unnecessary DB writes"""
    try:
        if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
            return

        user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user in ("Guest", "None"):
            return

        cache = frappe.cache() if hasattr(frappe, "cache") else None
        cache_key = f"ict_notif_init:{user}"
        if cache and cache.get_value(cache_key):
            return

        # Avoid DB writes on read-only GET requests unless strictly creating once cleanly
        ensure_user_notification_settings(user)
        ensure_user_ict_notification_settings(user)
        if cache:
            cache.set_value(cache_key, 1, expires_in_sec=3600)
    except Exception:
        pass


def ensure_user_ict_notification_settings(user=None):
    """Ensure that the given user has an ICT Notification Setting document"""
    try:
        if not user:
            user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user in ("Guest", "None"):
            return

        from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import (
            get_ict_notification_settings,
        )
        get_ict_notification_settings(user)
    except Exception:
        pass


def on_session_creation(login_manager):
    """Handle session creation"""
    try:
        if frappe.session.user != "Guest":
            ensure_user_notification_settings(frappe.session.user)
            ensure_user_ict_notification_settings(frappe.session.user)
    except Exception as e:
        frappe.log_error(f"Error in session creation: {e!s}", "Session Management")
