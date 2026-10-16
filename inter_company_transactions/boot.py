import frappe


def boot_session(bootinfo):
    """Add custom data to boot session for Inter Company Transactions"""
    try:
        try:
            from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
                fix_legacy_custom_fields,
                get_intercompany_party_map,
            )
            fix_legacy_custom_fields(force=True)
            bootinfo.intercompany_party_map = get_intercompany_party_map()
        except Exception:
            pass
    except Exception as e:
        frappe.log_error(f"Error in boot session: {e!s}", "Boot Session")
