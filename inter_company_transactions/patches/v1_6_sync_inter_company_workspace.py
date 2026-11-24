import frappe


def execute():
    """Force-sync Inter Company Workspace so all cards and DocTypes appear without reinstalling."""
    try:
        if frappe.db.exists("Page", "inter-company-console"):
            frappe.reload_doc("inter_company_transactions", "page", "inter_company_console", force=True)

        # Clean up broken private per-user copies that lack Card Break entries
        if frappe.db.table_exists("Workspace") and frappe.db.table_exists("Workspace Link"):
            user_workspaces = frappe.get_all(
                "Workspace",
                filters={"title": "Inter Company", "for_user": ["!=", ""]},
                pluck="name",
            )
            for ws_name in user_workspaces:
                has_cards = frappe.db.exists(
                    "Workspace Link",
                    {"parent": ws_name, "type": "Card Break"},
                )
                if not has_cards:
                    frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)

        frappe.reload_doc("inter_company_transactions", "workspace", "inter_company", force=True)
        from inter_company_transactions.patches.after_migrate import ensure_v16_desktop_icon_and_sidebar
        ensure_v16_desktop_icon_and_sidebar()
        frappe.clear_cache()
    except Exception as e:
        frappe.log_error(f"Error syncing Inter Company workspace: {e!s}", "ICT Workspace Sync")
