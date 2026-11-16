
app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Ejaz Tech"
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
    "/assets/inter_company_transactions/js/inter_company_common.js"
]

# Session Hooks
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
before_uninstall = "inter_company_transactions.uninstall.before_uninstall"
after_uninstall = "inter_company_transactions.uninstall.after_uninstall"
before_tests = "inter_company_transactions.tests_bootstrap.before_tests"


# Ignore audit/log references when deleting cancelled or draft vouchers
ignore_links_on_delete = [
    "Inter Company Document Reference",
    "Inter Company Error Log",
]

# Document Events for Inter-Company Transactions
_ICT_BASE = "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link"

doc_events = {
    "Sales Order": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Purchase Order": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Sales Invoice": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Purchase Invoice": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Delivery Note": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Purchase Receipt": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Material Request": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Stock Entry": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Journal Entry": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Payment Entry": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Quotation": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Supplier Quotation": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Request for Quotation": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    },
    "Landed Cost Voucher": {
        "validate": f"{_ICT_BASE}.validate_intercompany_document",
        "on_submit": f"{_ICT_BASE}.create_linked_documents",
        "before_cancel": f"{_ICT_BASE}.validate_intercompany_cancellation",
        "on_cancel": f"{_ICT_BASE}.cancel_linked_documents",
        "on_trash": f"{_ICT_BASE}.cleanup_intercompany_links_on_trash",
    }
}

