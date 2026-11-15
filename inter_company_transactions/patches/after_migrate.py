import frappe


def after_migrate():
    """Execute after migration to ensure custom fields, permissions, workspace, and link titles"""
    # Ensure custom fields from custom_fields.json exist
    ensure_custom_fields()

    # Ensure Page and Workspace exist without mutating disk JSONs when already configured
    ensure_page_and_workspace()

    # Ensure ICT Notification Setting exists for active users
    ensure_ict_notification_settings_for_all_users()

    # Ensure sister company names and titles are populated for all links
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            backfill_sister_company_names,
        )
        backfill_sister_company_names()
    except Exception as e:
        frappe.log_error(f"Error backfilling sister company names: {e!s}", "ICT After Migrate")


def execute():
    """Alias for after_migrate to ensure compatibility"""
    after_migrate()


def ensure_custom_fields():
    """Ensure all required custom fields exist after migration"""
    from inter_company_transactions.install import create_custom_fields
    try:
        create_custom_fields()
    except Exception as e:
        frappe.log_error(f"Error ensuring custom fields: {e!s}", "ICT After Migrate")


def ensure_notification_settings_for_all_users():
    """Safely backfill missing Notification Settings rows for active users without altering core DocType metadata"""
    try:
        if not (frappe.db and frappe.db.table_exists("Notification Settings")):
            return

        users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
        for u in users:
            if u and u not in ("Guest", "None") and not frappe.db.exists("Notification Settings", u):
                try:
                    frappe.db.sql("""
                        INSERT IGNORE INTO `tabNotification Settings`
                        (name, user, creation, modified, modified_by, owner, docstatus)
                        VALUES (%s, %s, NOW(), NOW(), %s, %s, 0)
                    """, (u, u, u, u))
                except Exception:
                    pass
    except Exception as e:
        frappe.log_error(f"Error ensuring Notification Settings: {e!s}", "ICT After Migrate")


def ensure_ict_notification_settings_for_all_users():
    """Ensure every existing active User has a valid ICT Notification Setting record"""
    try:
        if not (frappe.db and frappe.db.exists("DocType", "ICT Notification Setting")):
            return
        from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import (
            get_ict_notification_settings,
        )
        users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
        for u in users:
            if u and u not in ("Guest", "None"):
                try:
                    get_ict_notification_settings(u)
                except Exception:
                    pass
    except Exception as e:
        frappe.log_error(f"Error ensuring ICT Notification Settings: {e!s}", "ICT After Migrate")


def ensure_page_and_workspace():
    """Ensure Page inter-company-console and Workspace Inter Company exist without unnecessary saves"""
    import json
    import os
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
        else:
            page = frappe.get_doc("Page", "inter-company-console")
            existing_roles = {r.role for r in (page.roles or [])}
            roles_added = False
            for r in ["System Manager", "Accounts Manager", "Accounts User"]:
                if r not in existing_roles:
                    page.append("roles", {"role": r})
                    roles_added = True
            if roles_added:
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
        if os.path.exists(ws_file) and not frappe.db.exists("Workspace", "Inter Company"):
            with open(ws_file) as f:
                ws_data = json.load(f)
            ws_doc = frappe.get_doc(ws_data)
            ws_doc.flags.ignore_permissions = True
            ws_doc.insert()
    except Exception as e:
        frappe.log_error(f"Error ensuring page or workspace: {e!s}", "ICT After Migrate")
import frappe


def after_migrate():
    """Execute after migration to ensure custom fields, permissions, workspace, and link titles"""
    # Ensure custom fields from custom_fields.json exist
    ensure_custom_fields()

    # Ensure Page and Workspace exist without mutating disk JSONs when already configured
    ensure_page_and_workspace()

    # Ensure ICT Notification Setting exists for active users
    ensure_ict_notification_settings_for_all_users()

    # Ensure sister company names and titles are populated for all links
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            backfill_sister_company_names,
        )
        backfill_sister_company_names()
    except Exception as e:
        frappe.log_error(f"Error backfilling sister company names: {e!s}", "ICT After Migrate")


def execute():
    """Alias for after_migrate to ensure compatibility"""
    after_migrate()


def ensure_custom_fields():
    """Ensure all required custom fields exist after migration"""
    from inter_company_transactions.install import create_custom_fields
    try:
        create_custom_fields()
    except Exception as e:
        frappe.log_error(f"Error ensuring custom fields: {e!s}", "ICT After Migrate")


def ensure_ict_notification_settings_for_all_users():
    """Ensure every existing active User has a valid ICT Notification Setting record"""
    try:
        if not (frappe.db and frappe.db.exists("DocType", "ICT Notification Setting")):
            return
        from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import (
            get_ict_notification_settings,
        )
        users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
        for u in users:
            if u and u not in ("Guest", "None"):
                try:
                    get_ict_notification_settings(u)
                except Exception:
                    pass
    except Exception as e:
        frappe.log_error(f"Error ensuring ICT Notification Settings: {e!s}", "ICT After Migrate")


def ensure_page_and_workspace():
    """Ensure Page inter-company-console and Workspace Inter Company exist via JSON reload."""
    try:
        if not frappe.db.exists("Page", "inter-company-console"):
            frappe.reload_doc("inter_company_transactions", "page", "inter_company_console")

        if not frappe.db.exists("Workspace", "Inter Company"):
            frappe.reload_doc("inter_company_transactions", "workspace", "inter_company")
    except Exception as e:
        frappe.log_error(f"Error ensuring page or workspace: {e!s}", "ICT After Migrate")
