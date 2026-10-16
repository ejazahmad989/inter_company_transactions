import frappe


def before_migrate():
    """Execute before migration to preserve doctypes and sanitize custom fields"""
    print("Running pre-migration tasks for Inter Company Transactions...")

    # Sanitize custom fields and doctypes before migration begins
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            fix_legacy_custom_fields,
        )
        fix_legacy_custom_fields(force=True)
    except Exception as e:
        print(f"Notice during pre-migration custom fields check: {e}")

    # Ensure all doctypes are properly flagged as custom
    ensure_custom_doctypes()

    print("Pre-migration tasks completed successfully!")

def execute():
    """Alias for before_migrate to ensure compatibility"""
    before_migrate()

def ensure_custom_doctypes():
    """Ensure all our doctypes are marked as custom"""
    custom_doctypes = [
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

    for doctype_name in custom_doctypes:
        try:
            if frappe.db.exists("DocType", doctype_name):
                frappe.db.set_value("DocType", doctype_name, "custom", 1)
        except Exception as e:
            print(f"Notice marking {doctype_name} as custom: {e}")
