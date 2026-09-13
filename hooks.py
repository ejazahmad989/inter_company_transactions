app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Your Company"
app_description = "A custom ERPNext application that enables seamless inter-company transactions between related companies"
app_email = "support@example.com"
app_license = "mit"

# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/inter_company_transactions/css/inter_company_transactions.css"
# app_include_js = "/assets/inter_company_transactions/js/inter_company_transactions.js"

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Sales Order": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
    "Purchase Order": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
    "Sales Invoice": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
    "Purchase Invoice": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
    "Journal Entry": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
    "Payment Entry": {
        "on_submit": "inter_company_transactions.utils.transaction.create_linked_transaction",
        "on_cancel": "inter_company_transactions.utils.transaction.cancel_linked_transaction",
    },
}

fixtures = [
    {"dt": "Custom Field", "filters": [["fieldname", "like", "inter_company_%"]]}
]
