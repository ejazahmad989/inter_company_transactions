import frappe


def boot_session(bootinfo):
    """Add custom data to boot session for Inter Company Transactions"""
    try:
        try:
            from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
                get_intercompany_party_map,
            )
            bootinfo.intercompany_party_map = get_intercompany_party_map()
        except Exception:
            pass
    except Exception as e:
        frappe.log_error(f"Error in boot session: {e!s}", "Boot Session")


def has_app_permission():
    """Allow all authenticated Desk users (non-Guest) to see Inter Company on the Apps Screen."""
    try:
        user = getattr(getattr(frappe, "session", None), "user", None)
        return bool(user and user != "Guest")
    except Exception:
        return True
