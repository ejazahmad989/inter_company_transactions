import frappe


def after_migrate():
    """Execute after migration to restore data and verify setup"""
    print("Running post-migration tasks for Inter Company Transactions...")

    # Sanitize custom fields, repair depends_on expressions, and clean tree doctypes
    try:
        from inter_company_transactions.patches.v1_5_repair_item_depends_on_and_clean_trees import execute as repair_patch
        repair_patch()
    except Exception as e:
        print(f"Error running repair patch: {e}")


    # Recreate any missing doctypes
    recreate_missing_doctypes()

    # Ensure custom fields are in place
    ensure_custom_fields()

    # Re-sanitize immediately after custom fields creation
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            fix_legacy_custom_fields,
        )
        fix_legacy_custom_fields(force=True)
    except Exception as e:
        print(f"Error re-sanitizing custom fields: {e}")

    # Update permissions
    update_permissions()

    # Ensure all users have valid Notification Settings
    ensure_notification_settings_for_all_users()

    # Ensure ICT Notification Setting exists for all users
    ensure_ict_notification_settings_for_all_users()

    # Ensure Page and Workspace exist
    ensure_page_and_workspace()

    # Ensure sister company names and titles are populated for all links
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            backfill_sister_company_names,
        )
        backfill_sister_company_names()
    except Exception as e:
        print(f"Error backfilling sister company names: {e}")

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
        print(f"Error ensuring custom fields: {e!s}")

def recreate_missing_doctypes():
    """Recreate any missing doctypes"""
    from inter_company_transactions.install import create_doctypes
    try:
        create_doctypes()
        print("Recreated missing doctypes")
    except Exception as e:
        print(f"Error recreating doctypes: {e!s}")

def update_permissions():
    """Update permissions after migration"""
    from inter_company_transactions.install import set_default_permissions
    try:
        set_default_permissions()
        print("Updated permissions")
    except Exception as e:
        print(f"Error updating permissions: {e!s}")

def ensure_notification_settings_for_all_users():
    """Ensure every existing User has a valid Notification Settings record"""
    try:
        if frappe.db.exists("DocType", "Notification Settings"):
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
        print(f"Error ensuring Notification Settings: {e!s}")

def ensure_ict_notification_settings_for_all_users():
    """Ensure every existing User has a valid ICT Notification Setting record"""
    try:
        from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import (
            get_ict_notification_settings,
        )
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
        print(f"Error ensuring ICT Notification Settings: {e!s}")

def ensure_page_and_workspace():
    """Ensure Page inter-company-console and Workspace Inter Company exist"""
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
            with open(ws_file) as f:
                ws_data = json.load(f)
            if not frappe.db.exists("Workspace", "Inter Company"):
                ws_doc = frappe.get_doc(ws_data)
                ws_doc.flags.ignore_permissions = True
                ws_doc.insert()
                print("Ensured Workspace: Inter Company")
        frappe.db.commit()
    except Exception as e:
        print(f"Error ensuring page or workspace: {e!s}")
