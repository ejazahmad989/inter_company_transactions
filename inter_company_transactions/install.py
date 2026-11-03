import json
import os

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
        # Create doctypes
        create_doctypes()
    except Exception as e:
        print(f"Notice during doctype creation: {e}")
        frappe.log_error(f"Error in create_doctypes: {e}", "App Installation")

    try:
        # Create custom fields
        create_custom_fields()
    except Exception as e:
        print(f"Notice during custom fields creation: {e}")
        frappe.log_error(f"Error in create_custom_fields: {e}", "App Installation")

    try:
        # Set default permissions
        set_default_permissions()
    except Exception as e:
        print(f"Notice during permissions setup: {e}")
        frappe.log_error(f"Error in set_default_permissions: {e}", "App Installation")

    try:
        # Create sample data
        create_sample_data()
    except Exception as e:
        print(f"Notice during sample data creation: {e}")
        frappe.log_error(f"Error in create_sample_data: {e}", "App Installation")

    try:
        # Ensure page and workspace exist
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
    """Create required DocTypes"""
    doctypes = [
        # 1. Intercompany Linked Company (Child Table)
        {
            "doctype": "DocType",
            "name": "Intercompany Linked Company",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "section_break_1",
                    "fieldtype": "Section Break",
                    "label": "Main Company Settings"
                },
                {
                    "fieldname": "main_company_customer",
                    "fieldtype": "Link",
                    "label": "Main Company Customer",
                    "options": "Customer"
                },
                {
                    "fieldname": "main_company_supplier",
                    "fieldtype": "Link",
                    "label": "Main Company Supplier",
                    "options": "Supplier"
                },
                {
                    "fieldname": "main_company_account",
                    "fieldtype": "Link",
                    "label": "Main Company Account",
                    "options": "Account"
                },
                {
                    "fieldname": "main_company_warehouse",
                    "fieldtype": "Link",
                    "label": "Main Company Transit Warehouse",
                    "options": "Warehouse"
                },
                {
                    "fieldname": "section_break_2",
                    "fieldtype": "Section Break",
                    "label": "Other Company Settings"
                },
                {
                    "fieldname": "other_company_customer",
                    "fieldtype": "Link",
                    "label": "Other Company Customer",
                    "options": "Customer"
                },
                {
                    "fieldname": "other_company_supplier",
                    "fieldtype": "Link",
                    "label": "Other Company Supplier",
                    "options": "Supplier"
                },
                {
                    "fieldname": "other_company_account",
                    "fieldtype": "Link",
                    "label": "Other Company Account",
                    "options": "Account"
                },
                {
                    "fieldname": "other_company_warehouse",
                    "fieldtype": "Link",
                    "label": "Other Company Transit Warehouse",
                    "options": "Warehouse"
                }
            ]
        },

        # 2. Intercompany Transaction Type (Child Table)
        {
            "doctype": "DocType",
            "name": "Intercompany Transaction Type",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "source_type",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Source Transaction Type",
                    "options": "Sales Order\nPurchase Order\nSales Invoice\nPurchase Invoice\nDelivery Note\nPurchase Receipt\nStock Entry\nJournal Entry\nPayment Entry\nQuotation\nSupplier Quotation\nMaterial Request\nRequest for Quotation\nSubcontracting Order\nLanded Cost Voucher",
                    "reqd": 1
                },
                {
                    "fieldname": "target_type",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Target Transaction Type",
                    "options": "Sales Order\nPurchase Order\nSales Invoice\nPurchase Invoice\nDelivery Note\nPurchase Receipt\nStock Entry\nJournal Entry\nPayment Entry\nQuotation\nSupplier Quotation\nMaterial Request\nRequest for Quotation\nSubcontracting Order\nLanded Cost Voucher",
                    "reqd": 1
                },
                {
                    "fieldname": "direction",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Direction",
                    "options": "Main to Other\nOther to Main\nBoth",
                    "reqd": 1
                }
            ]
        },

        # 3. Intercompany Transaction Link (Main DocType)
        {
            "doctype": "DocType",
            "name": "Intercompany Transaction Link",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
            "title_field": "sister_company",
            "show_title_field_in_link": 1,
            "search_fields": "sister_company,main_company",
            "fields": [
                {
                    "fieldname": "main_company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Main Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "sister_company",
                    "fieldtype": "Data",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "in_global_search": 1,
                    "label": "Sister Company",
                    "read_only": 1,
                    "bold": 1,
                    "description": "Sister company name resolved from Linked Companies"
                },
                {
                    "fieldname": "linked_companies",
                    "fieldtype": "Table",
                    "label": "Linked Companies",
                    "options": "Intercompany Linked Company",
                    "reqd": 1
                },
                {
                    "fieldname": "enabled",
                    "fieldtype": "Check",
                    "in_list_view": 1,
                    "label": "Enabled",
                    "default": 1
                },
                {
                    "fieldname": "auto_create_draft",
                    "fieldtype": "Check",
                    "label": "Auto Create Linked Document as Draft",
                    "default": 1
                },
                {
                    "fieldname": "auto_cancel_linked_document",
                    "fieldtype": "Check",
                    "label": "Auto Cancel Linked Document",
                    "default": 1
                },
                {
                    "fieldname": "transaction_types",
                    "fieldtype": "Table",
                    "label": "Transaction Types",
                    "options": "Intercompany Transaction Type",
                    "reqd": 1
                }
            ]
        },

        # 4. Inter Company Document Reference
        {
            "doctype": "DocType",
            "name": "Inter Company Document Reference",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
            "fields": [
                {
                    "fieldname": "source_doctype",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Source DocType",
                    "options": "DocType",
                    "reqd": 1
                },
                {
                    "fieldname": "source_name",
                    "fieldtype": "Dynamic Link",
                    "in_list_view": 1,
                    "label": "Source Document",
                    "options": "source_doctype",
                    "reqd": 1
                },
                {
                    "fieldname": "source_company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Source Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "target_doctype",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Target DocType",
                    "options": "DocType",
                    "reqd": 1
                },
                {
                    "fieldname": "target_name",
                    "fieldtype": "Dynamic Link",
                    "in_list_view": 1,
                    "label": "Target Document",
                    "options": "target_doctype",
                    "reqd": 1
                },
                {
                    "fieldname": "target_company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Target Company",
                    "options": "Company",
                    "reqd": 1
                }
            ]
        },

        # 5. ICT Notification Setting
        {
            "doctype": "DocType",
            "name": "ICT Notification Setting",
            "module": "Inter Company Transactions",
            "custom": 0,
            "allow_import": 1,
            "autoname": "field:user",
            "fields": [
                {
                    "fieldname": "user",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "User",
                    "options": "User",
                    "reqd": 1,
                    "unique": 1
                },
                {
                    "default": "1",
                    "fieldname": "enabled",
                    "fieldtype": "Check",
                    "in_list_view": 1,
                    "label": "Enabled"
                },
                {
                    "fieldname": "section_break_channels",
                    "fieldtype": "Section Break",
                    "label": "Notification Channels"
                },
                {
                    "default": "1",
                    "fieldname": "email_notifications",
                    "fieldtype": "Check",
                    "label": "Email Notifications"
                },
                {
                    "default": "1",
                    "fieldname": "in_app_notifications",
                    "fieldtype": "Check",
                    "label": "In-App Notifications"
                },
                {
                    "fieldname": "column_break_channels",
                    "fieldtype": "Column Break"
                },
                {
                    "default": "0",
                    "fieldname": "sms_notifications",
                    "fieldtype": "Check",
                    "label": "SMS Notifications"
                },
                {
                    "default": "0",
                    "fieldname": "slack_notifications",
                    "fieldtype": "Check",
                    "label": "Slack / Webhook Notifications"
                },
                {
                    "fieldname": "section_break_events",
                    "fieldtype": "Section Break",
                    "label": "Notification Triggers & Events"
                },
                {
                    "default": "1",
                    "fieldname": "dispute_alerts",
                    "fieldtype": "Check",
                    "label": "Dispute Alerts"
                },
                {
                    "default": "1",
                    "fieldname": "netting_cycle_alerts",
                    "fieldtype": "Check",
                    "label": "Netting Cycle Alerts"
                },
                {
                    "default": "1",
                    "fieldname": "elimination_alerts",
                    "fieldtype": "Check",
                    "label": "Elimination Run Alerts"
                },
                {
                    "fieldname": "section_break_digest",
                    "fieldtype": "Section Break",
                    "label": "Frequency & Digest"
                },
                {
                    "default": "0",
                    "fieldname": "daily_summary",
                    "fieldtype": "Check",
                    "label": "Daily Summary Digest"
                },
                {
                    "default": "0",
                    "fieldname": "weekly_summary",
                    "fieldtype": "Check",
                    "label": "Weekly Summary Digest"
                }
            ]
        }
    ]

    for doctype in doctypes:
        try:
            if not frappe.db.exists("DocType", doctype["name"]):
                doc = frappe.get_doc(doctype)
                doc.flags.ignore_permissions = True
                doc.insert()
                print(f"Created DocType: {doctype['name']}")
            else:
                print(f"DocType already exists: {doctype['name']}")

            frappe.db.commit()

        except Exception as e:
            frappe.db.rollback()
            print(f"Error creating DocType {doctype['name']}: {e!s}")
            frappe.log_error(
                f"DocType Creation Error: {e!s}\nDocType: {doctype['name']}",
                "Inter Company Transaction Setup"
            )

def create_custom_fields():
    """Create custom fields for inter-company transactions"""
    try:
        # Load custom fields from JSON file
        custom_fields_file = os.path.join(os.path.dirname(__file__), "custom_fields.json")

        if os.path.exists(custom_fields_file):
            with open(custom_fields_file) as f:
                custom_fields = json.load(f)
        else:
            # Fallback custom fields definition
            tx_doctypes = [
                "Sales Order", "Purchase Order", "Journal Entry", "Payment Entry",
                "Sales Invoice", "Purchase Invoice", "Delivery Note", "Purchase Receipt",
                "Stock Entry", "Quotation", "Supplier Quotation", "Material Request",
                "Request for Quotation"
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
                        "description": "Select the target company for inter-company transaction",
                        "mandatory_depends_on": "is_intercompany",
                        "in_list_view": 1,
                        "in_standard_filter": 1,
                        "fetch_if_empty": 0
                    },
                    {
                        "fieldname": "intercompany_linked_doc_doctype",
                        "label": "Linked Document Type",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_target_company",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_doc_name",
                        "label": "Linked Document Name",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
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
                            "depends_on": field.get("depends_on", ""),
                            "mandatory_depends_on": field.get("mandatory_depends_on", ""),
                            "read_only_depends_on": field.get("read_only_depends_on", ""),
                            "in_list_view": field.get("in_list_view", 0),
                            "columns": field.get("columns", 0),
                            "in_standard_filter": field.get("in_standard_filter", 0),
                            "fetch_if_empty": field.get("fetch_if_empty", 0)
                        })
                        custom_field.flags.ignore_permissions = True
                        custom_field.insert()
                        print(f"Created Custom Field: {doctype} - {field['fieldname']}")
                    else:
                        # Custom field already exists; sync properties to ensure live DB is never stale
                        sync_props = [
                            "label", "fieldtype", "options", "default", "description",
                            "read_only", "hidden", "depends_on", "mandatory_depends_on",
                            "read_only_depends_on", "in_list_view", "columns",
                            "in_standard_filter", "fetch_if_empty"
                        ]
                        cf_doc = frappe.get_doc("Custom Field", existing_cf)
                        updated = False
                        for prop in sync_props:
                            if prop in field:
                                target_val = field[prop]
                                current_val = getattr(cf_doc, prop, None)
                                if str(target_val or "") != str(current_val or ""):
                                    setattr(cf_doc, prop, target_val)
                                    updated = True
                        if updated:
                            cf_doc.flags.ignore_permissions = True
                            cf_doc.save(ignore_permissions=True)
                            print(f"Synced Custom Field: {doctype} - {field['fieldname']}")

                except Exception as e:
                    print(f"Error creating custom field {field['fieldname']} for {doctype}: {e!s}")
                    frappe.log_error(
                        f"Custom Field Creation Error: {e!s}\nField: {field['fieldname']}\nDocType: {doctype}",
                        "Inter Company Transaction Setup"
                    )

        # Run comprehensive repair patch to delete obsolete master/tree custom fields and repair depends_on
        try:
            from inter_company_transactions.patches.v1_5_repair_item_depends_on_and_clean_trees import execute as repair_patch
            repair_patch()
        except Exception as e:
            print(f"Notice during repair patch execution: {e}")


        frappe.db.commit()

    except Exception as e:
        frappe.db.rollback()
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
            "doctype": "Intercompany Item Mapping",
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
            "role": "All",
            "read": 1, "write": 1, "create": 1, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 1, "email": 1, "share": 0
        },
        {
            "doctype": "Intercompany Transaction Link",
            "role": "All",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        }
    ]

    for perm in permissions:
        try:
            if frappe.db.exists("DocType", perm["doctype"]):
                existing_perm = frappe.db.exists("DocPerm", {
                    "parent": perm["doctype"],
                    "role": perm["role"]
                })

                if not existing_perm:
                    doctype_doc = frappe.get_doc("DocType", perm["doctype"])
                    doctype_doc.append("permissions", {
                        "role": perm["role"],
                        "read": perm.get("read", 0),
                        "write": perm.get("write", 0),
                        "create": perm.get("create", 0),
                        "delete": perm.get("delete", 0),
                        "submit": perm.get("submit", 0),
                        "cancel": perm.get("cancel", 0),
                        "amend": perm.get("amend", 0),
                        "report": perm.get("report", 0),
                        "export": perm.get("export", 0),
                        "print": perm.get("print", 0),
                        "email": perm.get("email", 0),
                        "share": perm.get("share", 0)
                    })
                    doctype_doc.save(ignore_permissions=True)
                    print(f"Added permission for {perm['role']} on {perm['doctype']}")
                else:
                    print(f"Permission already exists for {perm['role']} on {perm['doctype']}")
            else:
                print(f"DocType {perm['doctype']} does not exist, skipping permissions")

        except Exception as e:
            print(f"Error setting permissions for {perm['doctype']}: {e!s}")

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
            settings.save(ignore_permissions=True)
            print("Initialized Inter Company Settings default values")
        frappe.db.commit()
    except Exception as e:
        print(f"Notice during sample data initialization: {e!s}")

def create_page_and_workspace():
    """Ensure Inter-Company Control Console page and Inter Company workspace exist in DB"""
    try:
        # 1. Page
        if not frappe.db.exists("Page", "inter-company-console"):
            page = frappe.new_doc("Page")
            page.name = "inter-company-console"
            page.page_name = "inter-company-console"
            page.title = "Inter-Company Control Console"
            page.module = "Inter Company Transactions"
            page.standard = "Yes"
            for r in ["System Manager", "Accounts Manager", "Accounts User"]:
                page.append("roles", {"role": r})
            page.flags.ignore_permissions = True
            page.insert()
            print("Created Page: inter-company-console")
        else:
            page = frappe.get_doc("Page", "inter-company-console")
            roles = [r.role for r in page.roles]
            for r in ["System Manager", "Accounts Manager", "Accounts User"]:
                if r not in roles:
                    page.append("roles", {"role": r})
            page.flags.ignore_permissions = True
            page.save()

        # 2. Workspace
        ws_file = os.path.join(os.path.dirname(__file__), "inter_company_transactions", "workspace", "inter_company", "inter_company.json")
        if os.path.exists(ws_file):
            with open(ws_file) as f:
                ws_data = json.load(f)
            if not frappe.db.exists("Workspace", "Inter Company"):
                ws_doc = frappe.get_doc(ws_data)
                ws_doc.flags.ignore_permissions = True
                ws_doc.insert()
                print("Created Workspace: Inter Company")
        frappe.db.commit()
    except Exception as e:
        print(f"Error creating page or workspace: {e!s}")

def before_uninstall():
    """Clean up before app uninstall"""
    print("Cleaning up Inter Company Transactions app...")

    custom_fields = frappe.get_all("Custom Field",
        filters={"module": "Inter Company Transactions"},
        fields=["name"]
    )

    for field in custom_fields:
        frappe.delete_doc("Custom Field", field.name, ignore_permissions=True)

    print("Inter Company Transactions app cleanup completed!")
