
app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Ejaz Ahmed"
app_description = "Enterprise Inter-Company Transactions, Transfer Pricing, Elimination and Netting for ERPNext"
app_version = "1.0.0"
app_icon = "octicon octicon-git-compare"
app_color = "blue"
app_email = "ejazahmad989@gmail.com"
app_license = "MIT"
app_logo_url = "/assets/inter_company_transactions/images/inter_company_logo.svg"
app_home = "inter_company_transactions"

required_apps = ["erpnext"]

# Assets includes
app_include_css = "/assets/inter_company_transactions/css/inter_company_transactions.css"
app_include_js = [
    "/assets/inter_company_transactions/js/inter_company_common.js",
    "/assets/inter_company_transactions/js/inter_company_transaction_map.js"
]

# Session Hooks
before_request = "inter_company_transactions.session.before_request"
on_session_creation = "inter_company_transactions.session.on_session_creation"

# Boot Session
boot_session = "inter_company_transactions.boot.boot_session"

# Notification Configuration
notification_config = "inter_company_transactions.notifications.get_notification_config"

# Scheduled Background Tasks
scheduler_events = {
    "hourly": [
        "inter_company_transactions.inter_company_transactions.doctype.inter_company_error_log.inter_company_error_log.auto_retry_pending_errors"
    ]
}

# Migration & Install Hooks
# Custom fields are safely created in the backend only if not already existing,
# ensuring bench migrate never overwrites user customizations or triggers fixture conflicts.
fixtures = []
after_install = "inter_company_transactions.install.after_install"
before_migrate = "inter_company_transactions.patches.before_migrate.before_migrate"
after_migrate = "inter_company_transactions.patches.after_migrate.after_migrate"


# Document Events for Inter-Company Transactions
doc_events = {
    "Sales Order": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Order": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Sales Invoice": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Invoice": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Delivery Note": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Receipt": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Material Request": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Stock Entry": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.sanitize_intercompany_stock_entry",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Journal Entry": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Payment Entry": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Quotation": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Supplier Quotation": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.auto_detect_intercompany_party",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "before_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.validate_intercompany_cancellation",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    }
}
