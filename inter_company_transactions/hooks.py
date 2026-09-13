# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Your Company"
app_description = "A custom app for handling inter-company transactions with workflow and theme management"
app_icon = "octicon octicon-git-compare"
app_color = "blue"
app_email = "your@example.com"
app_license = "MIT"



# Desk assets (backend)
app_include_css = [
    "/assets/inter_company_transactions/css/enhanced_themes.css",
    "/assets/inter_company_transactions/css/inter_company_transactions.css",
    "/assets/inter_company_transactions/css/theme_manager.css",
    "/assets/inter_company_transactions/css/quickbooks_theme.css"
]

app_include_js = [
    "/assets/inter_company_transactions/js/backdate_permission.js",
    "/assets/inter_company_transactions/js/enhanced_workflow.js",
    "/assets/inter_company_transactions/js/inter_company_transaction_map.js",
    "/assets/inter_company_transactions/js/theme_manager.js",
    "/assets/enhanced_theme_manager/js/custom_login.js"
]

# include js, css files in header of desk.html
# app_include_css = "/assets/test/css/test.css"
# app_include_js = "/assets/test/js/test.js"

# include js, css files in header of web template
# web_include_css = "/assets/test/css/test.css"
# web_include_js = "/assets/test/js/test.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "test/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}


# Fixtures - This ensures all doctypes and custom fields are preserved during migrations
fixtures = [
    # DocTypes - All custom doctypes
    {
        "doctype": "DocType",
        "filters": [
            ["name", "in", [
                "Role Replication",
                "Intercompany Transaction Link",
                "Intercompany Linked Company", 
                "Intercompany Transaction Type",
                "Inter Company Document Reference",
                "Theme Manager",
                "Theme Manager Company",
                "Theme Manager User",
                "Theme Manager Role",
                "Enhanced Theme Manager",
                "Inter Company Workflow",
                "Inter Company Workflow Approver",
                "Workflow Approval Request",
                "Workflow Approval History",
                "Notification Settings"
             
            ]]
        ]
    },
    # Custom Fields - All inter-company related fields
    {
        "doctype": "Custom Field",
        "filters": [
            ["fieldname", "in", [
                "intercompany_linked_doc_doctype",
                "intercompany_linked_doc_name",
                "intercompany_linked_company",
                "intercompany_target_company",
                "ic_customer_group",
                "ic_supplier_group",
                "Form",
                "custom_company"
            ]]
        ]
    },
    # Property Setter for custom field properties
    {
        "doctype": "Property Setter",
        "filters": [
            ["doc_type", "in", [
                "Sales Order",
                "Purchase Order", 
                "Journal Entry",
                "Payment Entry",
                "Customer",
                "Supplier",
                "Customer Group",
                "Supplier Group"
            ]]
        ]
    },
    # Email Templates for workflow notifications
    {
        "doctype": "Email Template",
        "filters": [
            ["name", "in", [
                "approval_request_email",
                "approval_approved_email", 
                "approval_rejected_email",
                "escalation_email"
            ]]
        ]
    },
    # Print Formats if any
    {
        "doctype": "Print Format",
        "filters": [
            ["doc_type", "in", [
                "Workflow Approval Request",
                "Inter Company Workflow"
            ]]
        ]
    },
    # Roles
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", [
                "Workflow Manager",
                "Approver",
                "Theme Administrator"
            ]]
        ]
    }
]

scheduler_events = {
    "hourly": [
        "inter_company_transactions.workflow.send_approval_reminders",
        "inter_company_transactions.workflow.process_escalations"
    ],
    "daily": [
        "inter_company_transactions.workflow.cleanup_old_notifications"
    ]
}

# Document Events - Enhanced with workflow integration
doc_events = {
    "Sales Order": {
        "on_submit": [
            "inter_company_transactions.workflow.create_workflow_request",
            "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
            #"inter_company_transactions.workflow.create_approval_request_if_required"
        ],
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
        "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_save": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Purchase Order": {
        "on_submit": [ 
            "inter_company_transactions.workflow.create_workflow_request",
            "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
            
            #"inter_company_transactions.workflow.create_approval_request_if_required"
        ],
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
        #"validate":  "inter_company_transactions.date_validation_hooks.validate_backdate"
        # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Journal Entry": {
        "on_submit": [
            "inter_company_transactions.workflow.create_workflow_request",
            "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",

            # "inter_company_transactions.workflow.create_approval_request_if_required"
        ],
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
       # "validate": "inter_company_transactions.date_validation_hooks.validate_backdate"
       # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
        "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"

    },
    "Payment Entry": {
        "on_submit": [
            "inter_company_transactions.workflow.create_workflow_request",
            "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",

            #"inter_company_transactions.workflow.create_approval_request_if_required"
        ],
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
        #"validate": "inter_company_transactions.date_validation_hooks.validate_backdate"
        # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Sales Invoice": {
          "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
          "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"

          # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Purchase Invoice": {
          "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
          "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"

          # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Delivery Note": {
          "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
          "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"

       # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
    "Purchase Receipt": {
          "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
          "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"

        # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    },
      "Salary Slip": {
           "before_save": "inter_company_transactionshrms.custom_fetch_fixed_allowances"
    },
    "Stock Entry": {
          "validate": "inter_company_transactions.date_validation_hooks.validate_backdate",
          "before_insert": "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_save":   "inter_company_transactions.date_control.date_validator.validate_transaction_date",
          "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
       
          # "validate": "inter_company_transactions.doctype.backdate_permission.backdate_permission.validate_posting_date"
    }
}

# Login hooks for theme application
on_login = [
    "inter_company_transactions.enhanced_theme.apply_user_theme"
]

# Scheduled tasks for workflow reminders and escalations
scheduler_events = {
    "hourly": [
        "inter_company_transactions.workflow.send_approval_reminders",
        "inter_company_transactions.workflow.process_escalations"
    ],
    "daily": [
        "inter_company_transactions.workflow.cleanup_old_notifications",
        "inter_company_transactions.enhanced_theme.cleanup_old_theme_files"
    ]
}

# Jinja Environment - Enhanced with theme and workflow methods
jenv = {
    "methods": [
        "inter_company_transactions.enhanced_theme.get_company_theme",
        "inter_company_transactions.workflow.get_pending_approvals_count",
        "inter_company_transactions.workflow.get_user_approval_requests"
    ]
}

# Website context - Enhanced branding
website_context = {
    "favicon": "/assets/inter_company_transactions/images/favicon.ico",
    "splash_image": "/assets/inter_company_transactions/images/splash.png",
    "brand_html": "Inter Company Transactions"
}

# Boot session - Add user-specific data on login
boot_session = "inter_company_transactions.boot.boot_session"

# Override whitelisted methods
#override_whitelisted_methods = {
    #"frappe.desk.form.save.savedocs": "inter_company_transactions.overrides.enhanced_save_docs"
#}

# Import whitelisted functions
#from .overrides import enhanced_save_docs, check_workflow_triggers

# Define custom whitelisted functions
whitelisted_functions = [
    'enhanced_save_docs',
    'check_workflow_triggers'
]

# Standard portal menu items
standard_portal_menu_items = [
    {
        "title": "Approval Requests",
        "route": "/approval-requests",
        "reference_doctype": "Workflow Approval Request",
        "role": "Approver"
    }
]

# Permission query methods
#permission_query_conditions = {
    #"Workflow Approval Request": "inter_company_transactions.workflow.get_permission_query_conditions_for_approval_request"
#}

# Data import/export hooks
data_import_tool = {
    "Intercompany Transaction Link": "inter_company_transactions.data_import.validate_intercompany_data"
}

# Notification hooks
notification_config = "inter_company_transactions.notifications.get_notification_config"

# Report hooks
standard_queries = {
    "Workflow Approval Request": "inter_company_transactions.queries.workflow_approval_request_query"
}

# Translation hooks
get_translated_dict = {
    "doctype": "inter_company_transactions.translations.get_doctype_translations"
}

# Desk page hooks
extend_bootinfo = "inter_company_transactions.boot.extend_bootinfo"

# Global search hooks
global_search_doctypes = {
    "Workflow Approval Request": {
        "search_fields": ["document_name", "document_type", "requested_by"],
        "title_field": "document_name"
    },
    "Inter Company Workflow": {
        "search_fields": ["workflow_name", "source_company", "target_company"],
        "title_field": "workflow_name"
    }
}

#override_whitelisted_methods = {
    #"frappe.desk.form.save.savedocs": "inter_company_transactions.inter_company_transactions.overrides.enhanced_save_docs"
#}

# Backup hooks
before_backup = "inter_company_transactions.backup.before_backup"
after_backup = "inter_company_transactions.backup.after_backup"

# Migration hooks - Fixed paths
before_migrate = "inter_company_transactions.patches.before_migrate.before_migrate"
after_migrate = "inter_company_transactions.patches.after_migrate.after_migrate"

# Installation hooks
after_install = "inter_company_transactions.install.after_install"
before_uninstall = "inter_company_transactions.install.before_uninstall"

# Startup hooks
on_session_creation = "inter_company_transactions.session.on_session_creation"

# Error handling hooks
on_error = "inter_company_transactions.error_handler.handle_error"

# Cache hooks
cache_wipe_doctypes = [
    "Intercompany Transaction Link",
    "Inter Company Workflow", 
    "Enhanced Theme Manager"
]