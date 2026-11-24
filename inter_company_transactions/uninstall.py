# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe


def before_uninstall():
    """
    Executes before the app is uninstalled:
    Runs full self-healing to repair expressions, restore Customer/Supplier/Item Add & Delete buttons,
    wipe Tree custom fields, and leave the site in a pristine, standard ERPNext state.
    """
    print("Running before_uninstall for Inter Company Transactions...")
    try:
        from inter_company_transactions.diagnose_and_heal import run_full_healing
        run_full_healing(verbose=True)
    except Exception:
        pass

    cleanup_custom_fields()
    cleanup_property_setters()
    cleanup_custom_docperms()
    cleanup_v16_navigation()

    frappe.clear_cache()
    print("Pre-uninstall cleanup for Inter Company Transactions completed successfully.")


def after_uninstall():
    """
    Executes after the app is uninstalled:
    Final cache clearing, expression repair and schema validation.
    """
    print("Running after_uninstall for Inter Company Transactions...")
    try:
        from inter_company_transactions.diagnose_and_heal import run_full_healing
        run_full_healing(verbose=True)
    except Exception:
        pass
    frappe.clear_cache()
    print("Post-uninstall tasks completed. ERPNext site is clean.")


def cleanup_custom_fields():
    """Safely delete all Custom Field records introduced by the app"""
    if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Custom Field")):
        return

    ict_fields = [
        "is_intercompany",
        "intercompany_target_company",
        "intercompany_linked_doc_doctype",
        "intercompany_linked_doc_name",
        "intercompany_linked_company",
        "is_intercompany_item",
        "ic_item_group",
        "is_intercompany_warehouse",
        "ic_warehouse",
        "ic_customer_group",
        "ic_supplier_group",
    ]

    try:
        frappe.db.delete("Custom Field", {"module": "Inter Company Transactions"})
        frappe.db.delete("Custom Field", {"fieldname": ["in", ict_fields]})
        frappe.db.delete(
            "Custom Field",
            {"dt": ["in", ["Customer Group", "Supplier Group", "Item Group"]], "fieldname": "custom_company"},
        )
        print("Cleaned up all Inter Company Transactions Custom Fields.")
    except Exception as e:
        print(f"Notice during custom fields cleanup: {e}")


def cleanup_property_setters():
    """Delete any Property Setter records introduced by the app"""
    if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Property Setter")):
        return

    ict_fieldnames = [
        "is_intercompany",
        "intercompany_target_company",
        "intercompany_linked_doc_doctype",
        "intercompany_linked_doc_name",
        "intercompany_linked_company",
    ]

    try:
        frappe.db.delete("Property Setter", {"module": "Inter Company Transactions"})
        frappe.db.delete("Property Setter", {"property": ["like", "%intercompany%"]})
        frappe.db.delete("Property Setter", {"field_name": ["in", ict_fieldnames]})
        print("Cleaned up Inter Company Transactions Property Setters.")
    except Exception as e:
        print(f"Notice during property setters cleanup: {e}")


def cleanup_custom_docperms():
    """Delete any Custom DocPerms created for ICT DocTypes"""
    if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Custom DocPerm")):
        return

    ict_doctypes = [
        "Intercompany Transaction Link",
        "Intercompany Linked Company",
        "Intercompany Transaction Type",
        "Inter Company Document Reference",
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
        "Inter Company Remote Site",
        "ICT Notification Setting",
        "Role Replication",
        "SMS Template",
    ]

    try:
        frappe.db.delete("Custom DocPerm", {"parent": ["in", ict_doctypes]})
    except Exception as e:
        print(f"Notice during custom docperms cleanup: {e}")


def cleanup_v16_navigation():
    """Remove v16 Desktop Icon and Workspace Sidebar records owned by inter_company_transactions."""
    if not (hasattr(frappe, "db") and frappe.db):
        return
    try:
        if frappe.db.table_exists("Desktop Icon"):
            meta = frappe.get_meta("Desktop Icon")
            if meta and meta.has_field("app"):
                frappe.db.delete("Desktop Icon", {"app": "inter_company_transactions"})
            if frappe.db.exists("Desktop Icon", "Inter Company"):
                frappe.db.delete("Desktop Icon", {"name": "Inter Company"})
        if frappe.db.table_exists("Workspace Sidebar"):
            meta = frappe.get_meta("Workspace Sidebar")
            if meta and meta.has_field("app"):
                frappe.db.delete("Workspace Sidebar", {"app": "inter_company_transactions"})
            if frappe.db.exists("Workspace Sidebar", "Inter Company"):
                frappe.db.delete("Workspace Sidebar", {"name": "Inter Company"})
    except Exception as e:
        print(f"Notice during v16 navigation cleanup: {e}")


def repair_all_depends_on_expressions():
    """
    Scans and permanently repairs any damaged depends_on expressions in MariaDB.
    """
    from inter_company_transactions.diagnose_and_heal import repair_database_text
    repair_database_text(lambda *args, **kwargs: None)
