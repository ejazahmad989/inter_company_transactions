# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe


def before_uninstall():
    """
    Executes before the app is uninstalled:
    1. Removes all Custom Fields added to standard ERPNext DocTypes (Customer, Supplier,
       Customer Group, Supplier Group, Item, Warehouse, and transaction doctypes).
    2. Removes any Property Setters created by the app.
    3. Repairs any corrupted depends_on expressions in tabDocField (e.g. restoring
       'doc.__islocal && doc.is_stock_item' if damaged).
    4. Ensures the site database is left in a pristine, clean state so ERPNext master
       forms (Customer, Supplier, Item, Customer Group, etc.) never experience dirty form
       locks or JavaScript depends_on evaluation crashes after uninstall.
    """
    print("Running before_uninstall for Inter Company Transactions...")

    # 1. Repair any corrupted depends_on in tabDocField, tabCustom Field, tabProperty Setter
    repair_all_depends_on_expressions()

    # 2. Delete all Custom Fields created by or belonging to this app
    cleanup_custom_fields()

    # 3. Delete any Property Setters created by the app
    cleanup_property_setters()

    # 4. Remove any ICT Custom DocPerms
    cleanup_custom_docperms()

    frappe.db.commit()
    frappe.clear_cache()
    print("Pre-uninstall cleanup for Inter Company Transactions completed successfully.")


def after_uninstall():
    """
    Executes after the app is uninstalled:
    Final cache clearing and schema validation.
    """
    print("Running after_uninstall for Inter Company Transactions...")
    repair_all_depends_on_expressions()
    frappe.db.commit()
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
        "custom_company"
    ]

    try:
        # Delete by module
        frappe.db.sql("""
            DELETE FROM `tabCustom Field`
            WHERE `module` = 'Inter Company Transactions'
        """)

        # Delete by fieldname on affected DocTypes to ensure no orphan fields remain
        placeholders = ", ".join(["%s"] * len(ict_fields))
        frappe.db.sql(f"""
            DELETE FROM `tabCustom Field`
            WHERE `fieldname` IN ({placeholders})
        """, tuple(ict_fields))

        print("Cleaned up all Inter Company Transactions Custom Fields.")
    except Exception as e:
        print(f"Notice during custom fields cleanup: {e}")


def cleanup_property_setters():
    """Delete any Property Setter records introduced by the app"""
    if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Property Setter")):
        return

    try:
        frappe.db.sql("""
            DELETE FROM `tabProperty Setter`
            WHERE `module` = 'Inter Company Transactions'
               OR `property` LIKE '%intercompany%'
        """)
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
        "Role Replication"
    ]

    try:
        placeholders = ", ".join(["%s"] * len(ict_doctypes))
        frappe.db.sql(f"""
            DELETE FROM `tabCustom DocPerm`
            WHERE `parent` IN ({placeholders})
        """, tuple(ict_doctypes))
    except Exception as e:
        print(f"Notice during custom docperms cleanup: {e}")


def repair_all_depends_on_expressions():
    """
    Scans and permanently repairs any damaged depends_on expressions in MariaDB.
    Specifically fixes '__islocalanddoc' -> '__islocal && doc' so ERPNext Item,
    Customer, and Supplier forms never crash with 'Invalid depends_on expression'.
    """
    if not (hasattr(frappe, "db") and frappe.db):
        return

    tables = ["tabDocField", "tabCustom Field", "tabProperty Setter"]
    for tbl in tables:
        if not frappe.db.table_exists(tbl):
            continue

        cols_to_check = []
        if tbl == "tabProperty Setter":
            if frappe.db.has_column(tbl, "value"):
                cols_to_check.append("value")
        else:
            for c in ["depends_on", "mandatory_depends_on", "read_only_depends_on"]:
                if frappe.db.has_column(tbl, c):
                    cols_to_check.append(c)

        for col in cols_to_check:
            try:
                # 1. Fix __islocalanddoc -> __islocal && doc
                frappe.db.sql(f"""
                    UPDATE `{tbl}`
                    SET `{col}` = REPLACE(`{col}`, '__islocalanddoc', '__islocal && doc')
                    WHERE `{col}` LIKE '%__islocalanddoc%'
                """)

                # 2. Fix __islocaland -> __islocal &&
                frappe.db.sql(f"""
                    UPDATE `{tbl}`
                    SET `{col}` = REPLACE(`{col}`, '__islocaland', '__islocal && ')
                    WHERE `{col}` LIKE '%__islocaland%'
                """)

                # 3. Fix anddoc. -> && doc.
                frappe.db.sql(f"""
                    UPDATE `{tbl}`
                    SET `{col}` = REPLACE(`{col}`, 'anddoc.', ' && doc.')
                    WHERE `{col}` LIKE '%anddoc.%'
                """)

                # 4. Fix glued or / and operators
                frappe.db.sql(f"""
                    UPDATE `{tbl}`
                    SET `{col}` = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(`{col}`,
                        '1or(', '1 || ('),
                        '0or(', '0 || ('),
                        ')or(', ') || ('),
                        '1and(', '1 && ('),
                        '0and(', '0 && (')
                    WHERE `{col}` IS NOT NULL AND (
                        `{col}` LIKE '%1or(%' OR
                        `{col}` LIKE '%0or(%' OR
                        `{col}` LIKE '%)or(%' OR
                        `{col}` LIKE '%1and(%' OR
                        `{col}` LIKE '%0and(%'
                    )
                """)
            except Exception:
                pass

    frappe.db.commit()
