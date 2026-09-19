# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import json
import os

def after_install():
    """Run after app installation"""
    print("Starting Inter Company Transactions app installation...")
    
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
        # Create email templates
        create_email_templates()
    except Exception as e:
        print(f"Notice during email templates creation: {e}")
        frappe.log_error(f"Error in create_email_templates: {e}", "App Installation")
    
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
            "role_name": "Workflow Manager",
            "description": "Can manage inter-company workflows and approval processes"
        },
        {
            "role_name": "Approver",
            "description": "Can approve workflow requests and inter-company transactions"
        },
        {
            "role_name": "Theme Administrator", 
            "description": "Can manage themes and UI customizations"
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
        # Child Tables First (to avoid dependency issues)
        
        # 1. Backdate Permission Company (Child Table)
        {
            "doctype": "DocType",
            "name": "Backdate Permission Company",
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
                }
            ]
        },
        
        # 2. Intercompany Linked Company (Child Table)
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
                }
            ]
        },
        
        # 3. Intercompany Transaction Type (Child Table)
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
                    "options": "Journal Entry\nPayment Entry\nSales Order\nPurchase Order",
                    "reqd": 1
                },
                {
                    "fieldname": "target_type",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Target Transaction Type",
                    "options": "Journal Entry\nPayment Entry\nSales Order\nPurchase Order",
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
        
        # 4. Theme Manager Company (Child Table)
        {
            "doctype": "DocType",
            "name": "Theme Manager Company",
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
                }
            ]
        },
        
        # 5. Theme Manager User (Child Table)
        {
            "doctype": "DocType",
            "name": "Theme Manager User",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "user",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "User",
                    "options": "User",
                    "reqd": 1
                }
            ]
        },
        
        # 6. Theme Manager Role (Child Table)
        {
            "doctype": "DocType",
            "name": "Theme Manager Role",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "role",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Role",
                    "options": "Role",
                    "reqd": 1
                }
            ]
        },
        
        # 7. Inter Company Workflow Approver (Child Table)
        {
            "doctype": "DocType",
            "name": "Inter Company Workflow Approver",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "approval_level",
                    "fieldtype": "Int",
                    "in_list_view": 1,
                    "label": "Approval Level",
                    "reqd": 1
                },
                {
                    "fieldname": "approver_type",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Approver Type",
                    "options": "User\nRole\nDynamic",
                    "reqd": 1
                },
                {
                    "fieldname": "approver_user",
                    "fieldtype": "Link",
                    "label": "Approver User",
                    "options": "User",
                    "depends_on": "eval:doc.approver_type === 'User'"
                },
                {
                    "fieldname": "approver_role",
                    "fieldtype": "Link",
                    "label": "Approver Role",
                    "options": "Role",
                    "depends_on": "eval:doc.approver_type === 'Role'"
                },
                {
                    "fieldname": "amount_threshold",
                    "fieldtype": "Currency",
                    "label": "Amount Threshold"
                },
                {
                    "fieldname": "is_mandatory",
                    "fieldtype": "Check",
                    "label": "Is Mandatory",
                    "default": 1
                }
            ]
        },
        
        # 8. Workflow Approval History (Child Table)
        {
            "doctype": "DocType",
            "name": "Workflow Approval History",
            "module": "Inter Company Transactions",
            "istable": 1,
            "custom": 1,
            "fields": [
                {
                    "fieldname": "approval_level",
                    "fieldtype": "Int",
                    "in_list_view": 1,
                    "label": "Approval Level"
                },
                {
                    "fieldname": "approver",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Approver",
                    "options": "User"
                },
                {
                    "fieldname": "action",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Action",
                    "options": "Approved\nRejected\nDelegated\nEscalated\nCommented"
                },
                {
                    "fieldname": "action_date",
                    "fieldtype": "Datetime",
                    "in_list_view": 1,
                    "label": "Action Date"
                },
                {
                    "fieldname": "comments",
                    "fieldtype": "Text",
                    "label": "Comments"
                }
            ]
        },
        
        # Main DocTypes (after child tables)
        
        # 9. Backdate Permission (Main DocType) - FIXED: Changed 'doctype' to 'document_type'
        {
            "doctype": "DocType",
            "name": "Backdate Permission",
            "module": "Inter Company Transactions",
            "custom": 1,
            "autoname": "format:BDP-{user}-{document_type}-{#####}",
            "fields": [
                {
                    "fieldname": "user",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "User",
                    "options": "User",
                    "reqd": 1
                },
                {
                    "fieldname": "full_name",
                    "fieldtype": "Data",
                    "label": "Full Name",
                    "read_only": 1
                },
                {
                    "fieldname": "role",
                    "fieldtype": "Link",
                    "label": "Primary Role",
                    "options": "Role"
                },
                {
                    "fieldname": "company",
                    "fieldtype": "Link",
                    "label": "Default Company",
                    "options": "Company"
                },
                {
                    "fieldname": "enabled",
                    "fieldtype": "Check",
                    "in_list_view": 1,
                    "label": "Enabled",
                    "default": 1
                },
                {
                    "fieldname": "document_type",  # FIXED: Changed from 'doctype' to 'document_type'
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Document Type",
                    "options": "Journal Entry\nPayment Entry\nSales Invoice\nPurchase Invoice\nSales Order\nPurchase Order\nDelivery Note\nPurchase Receipt\nStock Entry\nAsset\nAll Transaction Types",
                    "reqd": 1
                },
                {
                    "fieldname": "applies_to_all_companies",
                    "fieldtype": "Check",
                    "label": "Applies to All Companies",
                    "default": 0
                },
                {
                    "fieldname": "specific_companies",
                    "fieldtype": "Table",
                    "label": "Specific Companies",
                    "options": "Backdate Permission Company",
                    "depends_on": "eval:!doc.applies_to_all_companies"
                },
                {
                    "fieldname": "allow_backdate",
                    "fieldtype": "Check",
                    "label": "Allow Backdate Transactions",
                    "default": 1
                },
                {
                    "fieldname": "backdate_days",
                    "fieldtype": "Int",
                    "label": "Backdate Days Allowed",
                    "default": 2,
                    "depends_on": "allow_backdate"
                },
                {
                    "fieldname": "allow_future_date",
                    "fieldtype": "Check",
                    "label": "Allow Future Date Transactions",
                    "default": 0
                },
                {
                    "fieldname": "future_date_days",
                    "fieldtype": "Int",
                    "label": "Future Date Days Allowed",
                    "default": 0,
                    "depends_on": "allow_future_date"
                },
                {
                    "fieldname": "expires_on",
                    "fieldtype": "Date",
                    "label": "Expires On",
                    "depends_on": "auto_expire"
                },
                {
                    "fieldname": "auto_expire",
                    "fieldtype": "Check",
                    "label": "Auto Expire",
                    "default": 0
                }
            ]
        },
        
        # 10. Intercompany Transaction Link (Main DocType)
        {
            "doctype": "DocType",
            "name": "Intercompany Transaction Link",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
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
        
        # 11. Inter Company Document Reference
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
        
        # 12. Enhanced Theme Manager
        {
            "doctype": "DocType",
            "name": "Enhanced Theme Manager",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
            "autoname": "format:ETM-{theme_name}-{#####}",
            "fields": [
                {
                    "fieldname": "theme_name",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Theme Name",
                    "options": "QuickBooks Classic\nQuickBooks Modern\nQuickBooks Pro\nSage Green\nXero Blue\nFreshBooks Orange\nZoho Purple\nWave Teal\nAccounting Professional\nManufacturing Blue\nTrading Green\nRetail Orange\nHealthcare Teal\nEducation Purple\nFintech Dark\nStartup Minimal\nCorporate Elite\nCustom Theme",
                    "reqd": 1
                },
                {
                    "fieldname": "is_active",
                    "fieldtype": "Check",
                    "in_list_view": 1,
                    "label": "Is Active",
                    "default": 0
                },
                {
                    "fieldname": "is_default",
                    "fieldtype": "Check",
                    "label": "Is Default Theme",
                    "default": 0
                },
                {
                    "fieldname": "primary_color",
                    "fieldtype": "Color",
                    "label": "Primary Color"
                },
                {
                    "fieldname": "secondary_color",
                    "fieldtype": "Color",
                    "label": "Secondary Color"
                },
                {
                    "fieldname": "background_color",
                    "fieldtype": "Color",
                    "label": "Background Color"
                },
                {
                    "fieldname": "text_color",
                    "fieldtype": "Color",
                    "label": "Text Color"
                },
                {
                    "fieldname": "custom_css",
                    "fieldtype": "Code",
                    "label": "Custom CSS",
                    "options": "CSS"
                }
            ]
        },
        
        # 13. Inter Company Workflow
        {
            "doctype": "DocType",
            "name": "Inter Company Workflow",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
            "autoname": "format:ICW-{workflow_name}-{#####}",
            "fields": [
                {
                    "fieldname": "workflow_name",
                    "fieldtype": "Data",
                    "in_list_view": 1,
                    "label": "Workflow Name",
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
                    "fieldname": "source_company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Source Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "target_company",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Target Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "source_document_type",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Source Document Type",
                    "options": "DocType",
                    "reqd": 1,
                    "description": "The document type that initiates the workflow (e.g., Sales Order)"
                },
                {
                    "fieldname": "target_document_type",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Target Document Type",
                    "options": "DocType",
                    "reqd": 1,
                    "description": "The document type that will be created upon approval (e.g., Purchase Order)"
                },
                {
                    "fieldname": "approval_required",
                    "fieldtype": "Check",
                    "label": "Approval Required",
                    "default": 1
                },
                {
                    "fieldname": "approver_mappings",
                    "fieldtype": "Table",
                    "label": "Approver Mappings",
                    "options": "Inter Company Workflow Approver"
                },
                {
                    "fieldname": "escalation_enabled",
                    "fieldtype": "Check",
                    "label": "Enable Escalation",
                    "default": 0
                },
                {
                    "fieldname": "escalation_hours",
                    "fieldtype": "Int",
                    "label": "Escalation Hours",
                    "default": 24,
                    "depends_on": "escalation_enabled"
                }
            ]
        },
        
        # 14. Workflow Approval Request
        {
            "doctype": "DocType",
            "name": "Workflow Approval Request",
            "module": "Inter Company Transactions",
            "custom": 1,
            "allow_import": 0,
            "autoname": "format:WAR-{document_type}-{#####}",
            "fields": [
                {
                    "fieldname": "workflow",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Workflow",
                    "options": "Inter Company Workflow",
                    "reqd": 1
                },
                {
                    "fieldname": "document_type",
                    "fieldtype": "Link",
                    "in_list_view": 1,
                    "label": "Document Type",
                    "options": "DocType",
                    "reqd": 1
                },
                {
                    "fieldname": "document_name",
                    "fieldtype": "Dynamic Link",
                    "in_list_view": 1,
                    "label": "Document Name",
                    "options": "document_type",
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
                    "fieldname": "target_company",
                    "fieldtype": "Link",
                    "label": "Target Company",
                    "options": "Company",
                    "reqd": 1
                },
                {
                    "fieldname": "requested_by",
                    "fieldtype": "Link",
                    "label": "Requested By",
                    "options": "User",
                    "reqd": 1
                },
                {
                    "fieldname": "status",
                    "fieldtype": "Select",
                    "in_list_view": 1,
                    "label": "Status",
                    "options": "Pending\nApproved\nRejected\nEscalated\nCancelled",
                    "default": "Pending"
                },
                {
                    "fieldname": "document_amount",
                    "fieldtype": "Currency",
                    "label": "Document Amount"
                },
                {
                    "fieldname": "approval_history",
                    "fieldtype": "Table",
                    "label": "Approval History",
                    "options": "Workflow Approval History"
                },
                {
                    "fieldname": "created_date",
                    "fieldtype": "Datetime",
                    "label": "Created Date",
                    "read_only": 1
                },
                {
                    "fieldname": "due_date",
                    "fieldtype": "Datetime",
                    "label": "Due Date"
                }
            ]
        },
        
        # 15. ICT Notification Setting
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
                    "fieldname": "approval_requests",
                    "fieldtype": "Check",
                    "label": "Approval Requests"
                },
                {
                    "default": "1",
                    "fieldname": "status_updates",
                    "fieldtype": "Check",
                    "label": "Status Updates"
                },
                {
                    "fieldname": "column_break_events",
                    "fieldtype": "Column Break"
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
            print(f"Error creating DocType {doctype['name']}: {str(e)}")
            frappe.log_error(
                f"DocType Creation Error: {str(e)}\nDocType: {doctype['name']}", 
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
            custom_fields = {
                "Sales Order": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "mandatory_depends_on": "eval:doc.docstatus===0",
                        "read_only_depends_on": "eval:doc.docstatus===1",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Purchase Order": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "mandatory_depends_on": "eval:doc.docstatus===0",
                        "read_only_depends_on": "eval:doc.docstatus===1",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Journal Entry": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "mandatory_depends_on": "eval:doc.docstatus===0",
                        "read_only_depends_on": "eval:doc.docstatus===1",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Payment Entry": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "mandatory_depends_on": "eval:doc.docstatus===0",
                        "read_only_depends_on": "eval:doc.docstatus===1",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Sales Invoice": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Purchase Invoice": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Delivery Note": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Purchase Receipt": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Quotation": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Supplier Quotation": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Material Request": [
                    {
                        "fieldname": "intercompany_target_company",
                        "label": "Inter Company Target",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "company",
                        "description": "Select the target company for inter-company transaction",
                        "depends_on": "eval:doc.docstatus===0",
                        "in_list_view": 1,
                        "in_standard_filter": 1
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
                        "label": "Linked Document",
                        "fieldtype": "Data",
                        "insert_after": "intercompany_linked_doc_doctype",
                        "read_only": 1,
                        "hidden": 1
                    },
                    {
                        "fieldname": "intercompany_linked_company",
                        "label": "Linked Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "intercompany_linked_doc_name",
                        "read_only": 1,
                        "hidden": 1
                    }
                ],
                "Customer": [
                    {
                        "fieldname": "ic_customer_group",
                        "label": "Inter Company Customer Group",
                        "fieldtype": "Link",
                        "options": "Customer Group",
                        "insert_after": "customer_group",
                        "description": "Used for mapping customers between companies"
                    }
                ],
                "Supplier": [
                    {
                        "fieldname": "ic_supplier_group",
                        "label": "Inter Company Supplier Group",
                        "fieldtype": "Link",
                        "options": "Supplier Group",
                        "insert_after": "supplier_group",
                        "description": "Used for mapping suppliers between companies"
                    }
                ],
                "Customer Group": [
                    {
                        "fieldname": "custom_company",
                        "label": "Custom Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "parent_customer_group",
                        "description": "Company this customer group belongs to"
                    }
                ],
                "Supplier Group": [
                    {
                        "fieldname": "custom_company",
                        "label": "Custom Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "insert_after": "parent_supplier_group",
                        "description": "Company this supplier group belongs to"
                    }
                ]
            }
            
        for doctype, fields in custom_fields.items():
            for field in fields:
                try:
                    field_name = f"{doctype}-{field['fieldname']}"
                    # Check if Custom Field exists by name or by (dt, fieldname)
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
                            "insert_after": field.get("insert_after", "amended_from"),
                            "description": field.get("description", ""),
                            "read_only": field.get("read_only", 0),
                            "hidden": field.get("hidden", 0),
                            "depends_on": field.get("depends_on", ""),
                            "mandatory_depends_on": field.get("mandatory_depends_on", ""),
                            "read_only_depends_on": field.get("read_only_depends_on", ""),
                            "in_list_view": field.get("in_list_view", 0),
                            "in_standard_filter": field.get("in_standard_filter", 0),
                            "fetch_if_empty": field.get("fetch_if_empty", 0)
                        })
                        custom_field.flags.ignore_permissions = True
                        custom_field.insert()
                        print(f"Created Custom Field: {doctype} - {field['fieldname']}")
                    else:
                        # Ensure module is set to Inter Company Transactions
                        frappe.db.set_value("Custom Field", existing_cf, "module", "Inter Company Transactions", update_modified=False)
                        print(f"Custom Field already exists: {doctype} - {field['fieldname']}")
                        
                except Exception as e:
                    print(f"Error creating custom field {field['fieldname']} for {doctype}: {str(e)}")
                    frappe.log_error(
                        f"Custom Field Creation Error: {str(e)}\nField: {field['fieldname']}\nDocType: {doctype}",
                        "Inter Company Transaction Setup"
                    )
                    
        frappe.db.commit()
        
    except Exception as e:
        frappe.db.rollback()
        print(f"Error creating custom fields: {str(e)}")
        frappe.log_error(f"Custom Fields Creation Error: {str(e)}", "Inter Company Transaction Setup")

def create_email_templates():
    """Create email templates for workflow notifications"""
    templates = [
        {
            "name": "approval_request_email",
            "subject": "Approval Required: {{ doc.document_type }} {{ doc.document_name }}",
            "response": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #0077C5, #005A9F); color: white; padding: 20px; text-align: center;">
                    <h2>Approval Required</h2>
                </div>
                <div style="padding: 20px; background: #f8f9fa;">
                    <p>Dear {{ frappe.db.get_value("User", user, "full_name") }},</p>
                    
                    <p>You have a new approval request:</p>
                    
                    <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p><strong>Document:</strong> {{ doc.document_type }} {{ doc.document_name }}</p>
                        <p><strong>Amount:</strong> {{ frappe.format_value(doc.document_amount, "Currency") }}</p>
                        <p><strong>Requested By:</strong> {{ frappe.db.get_value("User", doc.requested_by, "full_name") }}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{ frappe.utils.get_url() }}/app/workflow-approval-request/{{ doc.name }}" 
                           style="background: #0077C5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                            Review & Approve
                        </a>
                    </div>
                </div>
            </div>
            """
        },
        {
            "name": "approval_approved_email",
            "subject": "Request Approved: {{ doc.document_type }} {{ doc.document_name }}",
            "response": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 20px; text-align: center;">
                    <h2>Request Approved</h2>
                </div>
                <div style="padding: 20px; background: #f8f9fa;">
                    <p>Your approval request has been approved:</p>
                    
                    <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p><strong>Document:</strong> {{ doc.document_type }} {{ doc.document_name }}</p>
                        <p><strong>Amount:</strong> {{ frappe.format_value(doc.document_amount, "Currency") }}</p>
                        <p><strong>Status:</strong> Approved</p>
                    </div>
                </div>
            </div>
            """
        },
        {
            "name": "approval_rejected_email",
            "subject": "Request Rejected: {{ doc.document_type }} {{ doc.document_name }}",
            "response": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; text-align: center;">
                    <h2>Request Rejected</h2>
                </div>
                <div style="padding: 20px; background: #f8f9fa;">
                    <p>Your approval request has been rejected:</p>
                    
                    <div style="background: white; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p><strong>Document:</strong> {{ doc.document_type }} {{ doc.document_name }}</p>
                        <p><strong>Amount:</strong> {{ frappe.format_value(doc.document_amount, "Currency") }}</p>
                        <p><strong>Status:</strong> Rejected</p>
                    </div>
                </div>
            </div>
            """
        }
    ]
    
    for template in templates:
        if not frappe.db.exists("Email Template", template["name"]):
            email_template = frappe.get_doc({
                "doctype": "Email Template",
                "name": template["name"],
                "subject": template["subject"],
                "response": template["response"]
            })
            email_template.insert(ignore_permissions=True)
            print(f"Created Email Template: {template['name']}")

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
            "doctype": "Backdate Permission",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Enhanced Theme Manager",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Inter Company Workflow",
            "role": "System Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Workflow Approval Request",
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
        
        # All Role - Read access to view DocTypes
        {
            "doctype": "Intercompany Transaction Link",
            "role": "All",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Enhanced Theme Manager",
            "role": "All",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        {
            "doctype": "Workflow Approval Request",
            "role": "All",
            "read": 1, "write": 0, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        },
        
        # Accounts Manager - Can manage Backdate Permissions
        {
            "doctype": "Backdate Permission",
            "role": "Accounts Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        
        # Theme Administrator - Can manage themes
        {
            "doctype": "Enhanced Theme Manager",
            "role": "Theme Administrator",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        
        # Workflow Manager - Can manage workflows
        {
            "doctype": "Inter Company Workflow",
            "role": "Workflow Manager",
            "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        {
            "doctype": "Workflow Approval Request",
            "role": "Workflow Manager",
            "read": 1, "write": 1, "create": 1, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1
        },
        
        # Approver - Can read/write approval requests
        {
            "doctype": "Workflow Approval Request",
            "role": "Approver",
            "read": 1, "write": 1, "create": 0, "delete": 0,
            "submit": 0, "cancel": 0, "amend": 0,
            "report": 0, "export": 0, "print": 0, "email": 0, "share": 0
        }
    ]
    
    for perm in permissions:
        try:
            if frappe.db.exists("DocType", perm["doctype"]):
                # Check if permission already exists
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
            print(f"Error setting permissions for {perm['doctype']}: {str(e)}")

def create_sample_data():
    """Create sample data for demonstration"""
    try:
        # Create sample enhanced theme if none exists
        if not frappe.db.exists("Enhanced Theme Manager", {"is_default": 1}):
            sample_theme = frappe.get_doc({
                "doctype": "Enhanced Theme Manager",
                "theme_name": "QuickBooks Classic",
                "theme_description": "Classic QuickBooks-inspired theme for accounting",
                "is_default": 1,
                "is_active": 1,
                "primary_color": "#0077C5",
                "secondary_color": "#2CA01C",
                "background_color": "#F5F5F5",
                "text_color": "#333333"
            })
            sample_theme.insert(ignore_permissions=True)
            print("Created sample theme: QuickBooks Classic")
        
        print("Sample data creation completed")
            
    except Exception as e:
        print(f"Error creating sample data: {str(e)}")

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
            with open(ws_file, "r") as f:
                ws_data = json.load(f)
            if not frappe.db.exists("Workspace", "Inter Company"):
                ws_doc = frappe.get_doc(ws_data)
                ws_doc.flags.ignore_permissions = True
                ws_doc.insert()
                print("Created Workspace: Inter Company")
        frappe.db.commit()
    except Exception as e:
        print(f"Error creating page or workspace: {str(e)}")

def before_uninstall():
    """Clean up before app uninstall"""
    print("Cleaning up Inter Company Transactions app...")
    
    # Remove custom fields
    custom_fields = frappe.get_all("Custom Field", 
        filters={"module": "Inter Company Transactions"},
        fields=["name"]
    )
    
    for field in custom_fields:
        frappe.delete_doc("Custom Field", field.name, ignore_permissions=True)
    
    print("Inter Company Transactions app cleanup completed!")