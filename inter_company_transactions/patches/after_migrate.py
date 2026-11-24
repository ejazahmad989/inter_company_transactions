import frappe


def after_migrate():
    """Execute after migration to ensure custom fields, permissions, workspace, and link titles"""
    # Ensure custom fields from custom_fields.json exist
    ensure_custom_fields()

    # Ensure Page and Workspace exist without mutating disk JSONs when already configured
    ensure_page_and_workspace()

    # Ensure ICT Notification Setting exists for active users
    ensure_ict_notification_settings_for_all_users()

    # Sanitize strictly Inter Company Transactions custom fields on Stock Entry
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            _sanitize_intercompany_stock_entry_custom_fields,
        )
        _sanitize_intercompany_stock_entry_custom_fields(force=True)
    except Exception as e:
        frappe.log_error(f"Error sanitizing ICT custom fields: {e!s}", "ICT After Migrate")

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
    """Ensure Page inter-company-console, Workspace Inter Company, and v16 Desktop Icon/Sidebar exist."""
    changed = False
    try:
        if not frappe.db.exists("Page", "inter-company-console"):
            frappe.reload_doc("inter_company_transactions", "page", "inter_company_console")
            changed = True

        if frappe.db.table_exists("Workspace") and frappe.db.table_exists("Workspace Link"):
            stale_private = frappe.get_all(
                "Workspace",
                filters={"title": "Inter Company", "for_user": ["!=", ""]},
                pluck="name",
            )
            for ws_name in stale_private:
                if not frappe.db.exists("Workspace Link", {"parent": ws_name, "type": "Card Break"}):
                    frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)
                    changed = True

        needs_workspace_sync = not frappe.db.exists("Workspace", "Inter Company")
        if not needs_workspace_sync and frappe.db.table_exists("Workspace Link"):
            has_card_breaks = frappe.db.exists(
                "Workspace Link",
                {"parent": "Inter Company", "type": "Card Break"},
            )
            if not has_card_breaks:
                needs_workspace_sync = True

        if needs_workspace_sync:
            frappe.reload_doc("inter_company_transactions", "workspace", "inter_company", force=True)
            changed = True

        # On Frappe v16, ensure Workspace links to this app and is visible
        if frappe.db.exists("Workspace", "Inter Company"):
            ws_meta = frappe.get_meta("Workspace")
            ws_updates = {}
            if ws_meta and ws_meta.has_field("app"):
                cur_app = frappe.db.get_value("Workspace", "Inter Company", "app")
                if cur_app != "inter_company_transactions":
                    ws_updates["app"] = "inter_company_transactions"
            if frappe.db.get_value("Workspace", "Inter Company", "is_hidden"):
                ws_updates["is_hidden"] = 0
            if not frappe.db.get_value("Workspace", "Inter Company", "public"):
                ws_updates["public"] = 1
            if ws_updates:
                frappe.db.set_value("Workspace", "Inter Company", ws_updates, update_modified=False)
                changed = True

        if ensure_v16_desktop_icon_and_sidebar():
            changed = True

        if changed:
            frappe.clear_cache()
    except Exception as e:
        frappe.log_error(f"Error ensuring page or workspace: {e!s}", "ICT After Migrate")


def ensure_v16_desktop_icon_and_sidebar():
    """Create or sync Frappe v16 Workspace Sidebar and Desktop Icon for Inter Company cleanly (no-op on v15)."""
    changed = False
    sidebar_exists = False

    if frappe.db.exists("DocType", "Workspace Sidebar") and frappe.db.exists("DocType", "Workspace Sidebar Item"):
        ws_sidebar_meta = frappe.get_meta("Workspace Sidebar")
        ws_item_meta = frappe.get_meta("Workspace Sidebar Item")

        sidebar_name = "Inter Company" if frappe.db.exists("Workspace Sidebar", "Inter Company") else None
        if not sidebar_name and ws_sidebar_meta and ws_sidebar_meta.has_field("app"):
            matches = frappe.get_all(
                "Workspace Sidebar",
                filters={"app": "inter_company_transactions"},
                pluck="name",
                limit=1,
            )
            if matches:
                sidebar_name = matches[0]

        sidebar_items = [
            ("Inter Company", "Workspace", "Inter Company", "home"),
            ("Control Console", "Page", "inter-company-console", "dashboard"),
            ("Transaction Links", "DocType", "Intercompany Transaction Link", "link"),
            ("Global Settings", "DocType", "Inter Company Settings", "setting"),
            ("Transfer Pricing", "DocType", "Transfer Pricing Policy", "tag"),
            ("Netting Cycles", "DocType", "Inter Company Netting Cycle", "refresh"),
            ("Elimination Runs", "DocType", "Inter Company Elimination Run", "filter"),
            ("Dispute Center", "DocType", "Inter Company Dispute", "alert"),
            ("Document References", "DocType", "Inter Company Document Reference", "file"),
            ("Sync Error Log", "DocType", "Inter Company Error Log", "warning"),
            ("Notification Settings", "DocType", "ICT Notification Setting", "bell"),
            ("Balance Reconciliation", "Report", "Inter Company Balance Reconciliation", "chart"),
            ("Transaction Matrix", "Report", "Inter Company Transaction Matrix", "table"),
        ]

        sidebar_link_type_field = ws_item_meta.get_field("link_type") if (ws_item_meta and hasattr(ws_item_meta, "get_field")) else None
        allowed_sidebar_link_types = {
            opt.strip()
            for opt in str(getattr(sidebar_link_type_field, "options", "") or "").splitlines()
            if opt.strip()
        }

        has_existing_items = bool(
            sidebar_name
            and frappe.db.exists("Workspace Sidebar Item", {"parent": sidebar_name})
        )
        if not sidebar_name or not has_existing_items:
            doc = (
                frappe.get_doc("Workspace Sidebar", sidebar_name)
                if sidebar_name
                else frappe.new_doc("Workspace Sidebar")
            )
            doc.title = "Inter Company"
            if not doc.get("name"):
                doc.name = "Inter Company"
            if ws_sidebar_meta:
                if ws_sidebar_meta.has_field("app"):
                    doc.app = "inter_company_transactions"
                if ws_sidebar_meta.has_field("header_icon"):
                    doc.header_icon = "git-compare"
                if ws_sidebar_meta.has_field("module"):
                    doc.module = "Inter Company Transactions"
                if ws_sidebar_meta.has_field("standard"):
                    doc.standard = 1
                if ws_sidebar_meta.has_field("is_standard"):
                    doc.is_standard = 1
            if hasattr(doc, "set"):
                doc.set("items", [])
            else:
                doc.items = []
            for label, ltype, lto, icon_name in sidebar_items:
                if allowed_sidebar_link_types and ltype not in allowed_sidebar_link_types:
                    continue
                if ltype in ("Workspace", "Page", "DocType", "Report") and not frappe.db.exists(ltype, lto):
                    continue
                row = {
                    "label": label,
                    "link_type": ltype,
                    "link_to": lto,
                }
                if ws_item_meta:
                    if ws_item_meta.has_field("type"):
                        row["type"] = "Link"
                    if ws_item_meta.has_field("icon"):
                        row["icon"] = icon_name
                doc.append("items", row)
            doc.flags.ignore_permissions = True
            if doc.is_new():
                doc.insert(ignore_permissions=True)
            else:
                doc.save(ignore_permissions=True)
            sidebar_name = doc.name
            changed = True

        sidebar_exists = bool(sidebar_name and frappe.db.exists("Workspace Sidebar", sidebar_name))

    if frappe.db.exists("DocType", "Desktop Icon"):
        di_meta = frappe.get_meta("Desktop Icon")
        # Only manage Desktop Icon on Frappe v16+ where link_type & link_to exist
        if di_meta and di_meta.has_field("link_type") and di_meta.has_field("link_to"):
            existing_di = None
            if frappe.db.exists("Desktop Icon", "Inter Company"):
                existing_di = "Inter Company"
            elif di_meta.has_field("app"):
                matches = frappe.get_all(
                    "Desktop Icon",
                    filters={"app": "inter_company_transactions"},
                    pluck="name",
                    limit=1,
                )
                if matches:
                    existing_di = matches[0]
            if not existing_di:
                matches = frappe.get_all(
                    "Desktop Icon",
                    filters={"label": "Inter Company"},
                    pluck="name",
                    limit=1,
                )
                if matches:
                    existing_di = matches[0]

            link_type_field = di_meta.get_field("link_type") if hasattr(di_meta, "get_field") else None
            allowed_di_link_types = [
                opt.strip()
                for opt in str(getattr(link_type_field, "options", "") or "").splitlines()
                if opt.strip()
            ]
            if sidebar_exists and (not allowed_di_link_types or "Workspace Sidebar" in allowed_di_link_types):
                target_link_type = "Workspace Sidebar"
                target_link_to = "Inter Company"
            elif not allowed_di_link_types or "Workspace" in allowed_di_link_types:
                target_link_type = "Workspace"
                target_link_to = "Inter Company"
            elif "Page" in allowed_di_link_types:
                target_link_type = "Page"
                target_link_to = "inter-company-console"
            else:
                target_link_type = allowed_di_link_types[0]
                target_link_to = "Inter Company"

            icon_type_field = di_meta.get_field("icon_type") if hasattr(di_meta, "get_field") else None
            allowed_icon_types = [
                opt.strip()
                for opt in str(getattr(icon_type_field, "options", "") or "").splitlines()
                if opt.strip()
            ]
            target_icon_type = (
                "Link"
                if (not allowed_icon_types or "Link" in allowed_icon_types)
                else allowed_icon_types[0]
            )

            if not existing_di:
                di_doc = frappe.new_doc("Desktop Icon")
                di_doc.label = "Inter Company"
                di_doc.link_type = target_link_type
                di_doc.link_to = target_link_to
                if di_meta.has_field("app"):
                    di_doc.app = "inter_company_transactions"
                if di_meta.has_field("icon_type"):
                    di_doc.icon_type = target_icon_type
                if di_meta.has_field("sidebar") and sidebar_exists:
                    di_doc.sidebar = "Inter Company"
                if di_meta.has_field("logo_url"):
                    di_doc.logo_url = "/assets/inter_company_transactions/images/inter_company_icon_512.png"
                if di_meta.has_field("icon"):
                    di_doc.icon = "git-compare"
                if di_meta.has_field("standard"):
                    di_doc.standard = 1
                if di_meta.has_field("hidden"):
                    di_doc.hidden = 0
                di_doc.flags.ignore_permissions = True
                di_doc.insert(ignore_permissions=True)
                changed = True
            else:
                di_doc = frappe.get_doc("Desktop Icon", existing_di)
                di_dirty = False
                if di_doc.get("link_type") != target_link_type:
                    di_doc.link_type = target_link_type
                    di_dirty = True
                if di_doc.get("link_to") != target_link_to:
                    di_doc.link_to = target_link_to
                    di_dirty = True
                if di_meta.has_field("app") and di_doc.get("app") != "inter_company_transactions":
                    di_doc.app = "inter_company_transactions"
                    di_dirty = True
                if di_meta.has_field("sidebar") and sidebar_exists and di_doc.get("sidebar") != "Inter Company":
                    di_doc.sidebar = "Inter Company"
                    di_dirty = True
                if di_meta.has_field("hidden") and di_doc.get("hidden"):
                    di_doc.hidden = 0
                    di_dirty = True
                if di_dirty:
                    di_doc.save(ignore_permissions=True)
                    changed = True

    return changed
