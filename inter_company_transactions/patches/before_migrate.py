import frappe


def before_migrate():
    """Execute before migration to ensure module DocTypes remain standard (custom = 0)"""
    ensure_standard_doctypes()


def execute():
    """Alias for before_migrate to ensure compatibility"""
    before_migrate()


def ensure_standard_doctypes():
    """Ensure all app DocTypes are flagged standard (custom = 0)"""
    app_doctypes = [
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

    for doctype_name in app_doctypes:
        try:
            if frappe.db.exists("DocType", doctype_name):
                frappe.db.set_value("DocType", doctype_name, "custom", 0)
        except Exception as e:
            print(f"Notice marking {doctype_name} as standard: {e}")
