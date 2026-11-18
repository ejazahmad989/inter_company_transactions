import json
import os
from pathlib import Path

import frappe


def after_install():
    """Run after app installation"""
    print("Starting Inter Company Transactions app installation...")

    try:
        # Run repair patch to fix any corrupted depends_on expressions and clean up trees/masters
        from inter_company_transactions.patches.v1_5_repair_item_depends_on_and_clean_trees import execute as repair_patch
        repair_patch()
    except Exception as e:
        print(f"Notice during repair patch execution: {e}")

    try:
        # Create custom roles first
        create_custom_roles()
    except Exception as e:
        print(f"Notice during role creation: {e}")
        frappe.log_error(f"Error in create_custom_roles: {e}", "App Installation")

    try:
        # Create custom fields
        create_custom_fields()
    except Exception as e:
        print(f"Notice during custom fields creation: {e}")
        frappe.log_error(f"Error in create_custom_fields: {e}", "App Installation")

    try:
        # Verify default permissions without mutating standard DocType documents
        set_default_permissions()
    except Exception as e:
        print(f"Notice during permissions setup: {e}")
        frappe.log_error(f"Error in set_default_permissions: {e}", "App Installation")

    try:
        # Initialize Inter Company Settings defaults
        create_sample_data()
    except Exception as e:
        print(f"Notice during sample data creation: {e}")
        frappe.log_error(f"Error in create_sample_data: {e}", "App Installation")

    try:
        # Ensure page and workspace are synced from module JSONs
        create_page_and_workspace()
    except Exception as e:
        print(f"Notice during page/workspace creation: {e}")
        frappe.log_error(f"Error in create_page_and_workspace: {e}", "App Installation")

    print("Inter Company Transactions app installation completed successfully!")

def create_custom_roles():
    """Create custom roles required by the app"""
    roles = [
        {
            "role_name": "Inter Company User",
            "description": "Can view and process inter-company transactions"
        }
    ]

    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": role_data["role_name"],
                "description": role_data["description"]
            })
            role.insert(ignore_permissions=True)
            print(f"Created role: {role_data['role_name']}")

def create_doctypes():
    """Ensure standard module DocTypes are synced via JSON without requiring developer_mode."""
    core_doctypes = [
        ("Intercompany Linked Company", "intercompany_linked_company"),
        ("Intercompany Transaction Type", "intercompany_transaction_type"),
        ("Intercompany Transaction Link", "intercompany_transaction_link"),
        ("Inter Company Document Reference", "inter_company_document_reference"),
        ("ICT Notification Setting", "ict_notification_setting"),
    ]
    for doctype_name, folder_name in core_doctypes:
        if not frappe.db.exists("DocType", doctype_name):
            frappe.reload_doc("inter_company_transactions", "doctype", folder_name)

def create_custom_fields():
    """Create custom fields for inter-company transactions"""
    try:
        # Load custom fields from JSON file
        custom_fields_file = os.path.join(os.path.dirname(__file__), "custom_fields.json")

        if os.path.exists(custom_fields_file):
            custom_fields = json.loads(Path(custom_fields_file).read_text(encoding="utf-8"))
        else:
            # Fallback custom fields definition
            tx_doctypes = [
                "Sales Order", "Purchase Order", "Journal Entry", "Payment Entry",
                "Sales Invoice", "Purchase Invoice", "Delivery Note", "Purchase Receipt",
                "Stock Entry", "Quotation", "Supplier Quotation", "Material Request",
                "Request for Quotation", "Landed Cost Voucher"
            ]

            def _get_fallback_tx_fields():
                return [
                    {
                        "fieldname": "is_intercompany",
                        "label": "Is Intercompany",
                        "fieldtype": "Check",
                        "default": "0",
                        "insert_after": "company",
                        "description": "Check if this transaction is with a sister company",
                        "in_list_view": 1,
                        "in_standard_filter": 1
                    },
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Intercompany Target Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "is_intercompany",
                        "description": "Target company for inter-company transaction (editable only when Is Intercompany is checked)",
                        "in_list_view": 1,
                        "in_standard_filter": 1,
                        "ignore_user_permissions": 1
                    },
                    {
                        "fieldname": "intercompany_linked_doc_doctype",
                        "label": "Linked Document Type",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_target_company",
                        "read_only": 1,
                        "hidden": 1,
                        "no_copy": 1
                    },
                    {
                        "fieldname": "intercompany_linked_doc_name",
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1,
                        "no_copy": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1,
                        "no_copy": 1,
                        "ignore_user_permissions": 1
                    }
                ]

            custom_fields = {}
            for dt in tx_doctypes:
                custom_fields[dt] = _get_fallback_tx_fields()


        for doctype, fields in custom_fields.items():
            for field in fields:
                try:
                    field_name = f"{doctype}-{field['fieldname']}"
                    existing_cf = None
                    if frappe.db.exists("Custom Field", field_name):
                        existing_cf = field_name
                    elif frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
                        existing_cf = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}, "name")

                    if not existing_cf:
                        custom_field = frappe.get_doc({
                            "doctype": "Custom Field",
                            "name": field_name,
                            "dt": doctype,
                            "module": "Inter Company Transactions",
                            "fieldname": field["fieldname"],
                            "label": field["label"],
                            "fieldtype": field["fieldtype"],
                            "options": field.get("options"),
                            "default": field.get("default"),
                            "insert_after": field.get("insert_after", "amended_from"),
                            "description": field.get("description", ""),
                            "read_only": field.get("read_only", 0),
                            "hidden": field.get("hidden", 0),
                            "no_copy": field.get("no_copy", 0),
                            "depends_on": field.get("depends_on", ""),
                            "mandatory_depends_on": field.get("mandatory_depends_on", ""),
                            "read_only_depends_on": field.get("read_only_depends_on", ""),
                            "in_list_view": field.get("in_list_view", 0),
                            "columns": field.get("columns", 0),
                            "in_standard_filter": field.get("in_standard_filter", 0),
                            "fetch_if_empty": field.get("fetch_if_empty", 0),
                            "ignore_user_permissions": field.get("ignore_user_permissions", 1 if field["fieldname"] in ("intercompany_target_company", "intercompany_linked_company") else 0)
                        })
                        custom_field.flags.ignore_permissions = True
                        custom_field.insert()
                    else:
                        # Sync only missing or core structural attributes quietly
                        sync_props = [
                            "label", "fieldtype", "options", "default", "description",
                            "read_only", "hidden", "no_copy", "depends_on", "mandatory_depends_on",
                            "read_only_depends_on", "in_list_view", "columns",
                            "in_standard_filter", "fetch_if_empty", "ignore_user_permissions"
                        ]
                        cf_doc = frappe.get_doc("Custom Field", existing_cf)
                        updated = False
                        for prop in sync_props:
                            if prop in field:
                                target_val = field[prop]
                            elif prop in ("depends_on", "mandatory_depends_on", "read_only_depends_on"):
                                target_val = ""
                            elif prop == "default" and field["fieldname"] == "intercompany_target_company":
                                target_val = None
                            elif prop == "fetch_if_empty" and field["fieldname"] == "intercompany_target_company":
                                target_val = 0
                            else:
                                continue
                            current_val = getattr(cf_doc, prop, None)
                            if str(target_val or "") != str(current_val or ""):
                                setattr(cf_doc, prop, target_val)
                                updated = True
                        if updated:
                            cf_doc.flags.ignore_permissions = True
                            cf_doc.save(ignore_permissions=True)

                except Exception as e:
                    frappe.log_error(
                        f"Custom Field Creation Error: {e!s}\nField: {field['fieldname']}\nDocType: {doctype}",
                        "Inter Company Transaction Setup"
                    )

    except Exception as e:
        print(f"Error creating custom fields: {e!s}")
        frappe.log_error(f"Custom Fields Creation Error: {e!s}", "Inter Company Transaction Setup")

def set_default_permissions():
    """Set default permissions for custom doctypes"""
    permissions = [
        # System Manager - Full access to all
        {
            "doctype": "Intercompany Transaction Link",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Document Reference",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Settings",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Error Log",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Netting Cycle",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 1, "cancel": 1, "amend": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Transfer Pricing Policy",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Elimination Run",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 1, "cancel": 1, "amend": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Dispute",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 1, "cancel": 1, "amend": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "ICT Notification Setting",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "ICT Notification Setting",
            "role": "Accounts Manager",
            "read": 1, "write": 1, "create": 1, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "ICT Notification Setting",
            "role": "Inter Company User",
            "read": 1, "write": 1, "create": 1, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 1, "email": 1, "share": 0
        },
        {
            "doctype": "ICT Notification Setting",
            "role": "Accounts User",
            "read": 1, "write": 1, "create": 1, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "Inter Company User",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "Accounts User",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "Sales User",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "Purchase User",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "Stock User",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        }
    ]

    for perm in permissions:
        try:
            dt = perm["doctype"]
            role = perm["role"]
            if not frappe.db.exists("DocType", dt):
                continue

            has_perm = frappe.db.exists("DocPerm", {"parent": dt, "role": role}) or frappe.db.exists(
                "Custom DocPerm", {"parent": dt, "role": role}
            )
            if has_perm:
                continue

            if frappe.db.get_value("DocType", dt, "istable"):
                continue

            # Use frappe.permissions (Custom DocPerm) so non-developer production sites never fail
            from frappe.permissions import add_permission, update_permission_property

            add_permission(dt, role, 0)
            for ptype in ("read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "print", "email", "share"):
                update_permission_property(dt, role, 0, ptype, perm.get(ptype, 0), validate=False)

        except Exception as e:
            frappe.log_error(f"Error setting permissions for {perm['doctype']}: {e!s}", "ICT Install")

def create_sample_data():
    """Ensure Inter Company Settings single doctype is initialized with default values"""
    try:
        if frappe.db.exists("DocType", "Inter Company Settings"):
            settings = frappe.get_single("Inter Company Settings")
            if not settings.execution_mode:
                settings.execution_mode = "Synchronous"
            if settings.enabled is None:
                settings.enabled = 1
            if settings.auto_create_missing_items is None:
                settings.auto_create_missing_items = 1
            if not settings.tax_handling_strategy:
                settings.tax_handling_strategy = "Mirror Net Rate Exactly"
            if not settings.default_transfer_pricing_rule:
                settings.default_transfer_pricing_rule = "Source Document Rate"
            if settings.tolerance_amount is None:
                settings.tolerance_amount = 0.05
            if settings.notify_on_sync_failure is None:
                settings.notify_on_sync_failure = 1
            if hasattr(settings, "cancellation_authority") and not settings.cancellation_authority:
                settings.cancellation_authority = "Source Company Only (Strict Control)"
            settings.save(ignore_permissions=True)
            print("Initialized Inter Company Settings default values")
    except Exception as e:
        print(f"Notice during sample data initialization: {e!s}")

def create_page_and_workspace():
    """Ensure Inter-Company Control Console page and Inter Company workspace exist via JSON reload."""
    try:
        if not frappe.db.exists("Page", "inter-company-console"):
            frappe.reload_doc("inter_company_transactions", "page", "inter_company_console")
            print("Synced Page: inter-company-console")

        if not frappe.db.exists("Workspace", "Inter Company"):
            frappe.reload_doc("inter_company_transactions", "workspace", "inter_company")
            print("Synced Workspace: Inter Company")

    except Exception as e:
        print(f"Notice syncing page or workspace: {e!s}")

