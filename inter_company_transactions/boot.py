import frappe


def boot_session(bootinfo):
    """Add cached intercompany party map to Desk boot session when enabled."""
    try:
        user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user == "Guest":
            return

        if hasattr(frappe, "db") and frappe.db:
            user_type = frappe.db.get_value("User", user, "user_type")
            if user_type == "Website User":
                return

        cache = frappe.cache() if callable(getattr(frappe, "cache", None)) else None
        cached_map = cache.get_value("ict_intercompany_party_map") if cache else None
        if isinstance(cached_map, dict):
            bootinfo.intercompany_party_map = cached_map
            return

        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            get_intercompany_party_map,
        )
        party_map = get_intercompany_party_map()
        bootinfo.intercompany_party_map = party_map
        if cache and isinstance(party_map, dict):
            cache.set_value("ict_intercompany_party_map", party_map, expires_in_sec=300)
    except Exception as e:
        frappe.log_error(f"Error in boot session: {e!s}", "Boot Session")


def has_app_permission():
    """Allow all authenticated Desk users (non-Guest) to see Inter Company on the Apps Screen."""
    try:
        user = getattr(getattr(frappe, "session", None), "user", None)
        return bool(user and user != "Guest")
    except Exception:
        return True
