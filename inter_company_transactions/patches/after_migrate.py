import frappe


def after_migrate():
    """Execute after migration to ensure custom fields, permissions, workspace, and link titles"""
    # Ensure custom fields from custom_fields.json exist
    ensure_custom_fields()

    # Ensure Page and Workspace exist without mutating disk JSONs when already configured
    ensure_page_and_workspace()

    # Ensure ICT Notification Setting exists for active users
    ensure_ict_notification_settings_for_all_users()

    # Heal any corrupted depends_on or Python condition expressions in MariaDB
    try:
        from inter_company_transactions.diagnose_and_heal import repair_database_text
        repair_database_text(lambda *args, **kwargs: None)
    except Exception as e:
        frappe.log_error(f"Error repairing database expressions: {e!s}", "ICT After Migrate")

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
