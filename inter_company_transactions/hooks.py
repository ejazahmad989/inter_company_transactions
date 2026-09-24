# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Your Company"
app_description = "A custom app for handling inter-company transactions"
app_icon = "octicon octicon-git-compare"
app_color = "blue"
app_email = "your@example.com"
app_license = "MIT"

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

# Fixtures for Inter-Company Custom Fields
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                "Sales Order-intercompany_linked_doc_doctype",
                "Sales Order-intercompany_linked_doc_name",
                "Sales Order-intercompany_linked_company",
                "Sales Order-intercompany_target_company",

                "Purchase Order-intercompany_linked_doc_doctype",
                "Purchase Order-intercompany_linked_doc_name",
                "Purchase Order-intercompany_linked_company",
                "Purchase Order-intercompany_target_company",

                "Sales Invoice-intercompany_linked_doc_doctype",
                "Sales Invoice-intercompany_linked_doc_name",
                "Sales Invoice-intercompany_linked_company",
                "Sales Invoice-intercompany_target_company",
                "Sales Invoice-inter_company_reference",

                "Purchase Invoice-intercompany_linked_doc_doctype",
                "Purchase Invoice-intercompany_linked_doc_name",
                "Purchase Invoice-intercompany_linked_company",
                "Purchase Invoice-intercompany_target_company",
                "Purchase Invoice-inter_company_reference",

                "Journal Entry-intercompany_linked_doc_doctype",
                "Journal Entry-intercompany_linked_doc_name",
                "Journal Entry-intercompany_linked_company",
                "Journal Entry-intercompany_target_company",

                "Payment Entry-intercompany_linked_doc_doctype",
                "Payment Entry-intercompany_linked_doc_name",
                "Payment Entry-intercompany_linked_company",
                "Payment Entry-intercompany_target_company",

                "Delivery Note-intercompany_linked_doc_doctype",
                "Delivery Note-intercompany_linked_doc_name",
                "Delivery Note-intercompany_linked_company",
                "Delivery Note-intercompany_target_company",

                "Purchase Receipt-intercompany_linked_doc_doctype",
                "Purchase Receipt-intercompany_linked_doc_name",
                "Purchase Receipt-intercompany_linked_company",
                "Purchase Receipt-intercompany_target_company",

                "Material Request-intercompany_linked_doc_doctype",
                "Material Request-intercompany_linked_doc_name",
                "Material Request-intercompany_linked_company",
                "Material Request-intercompany_target_company",

                "Stock Entry-intercompany_linked_doc_doctype",
                "Stock Entry-intercompany_linked_doc_name",
                "Stock Entry-intercompany_linked_company",
                "Stock Entry-intercompany_target_company",

                "Quotation-intercompany_linked_doc_doctype",
                "Quotation-intercompany_linked_doc_name",
                "Quotation-intercompany_linked_company",
                "Quotation-intercompany_target_company",

                "Supplier Quotation-intercompany_linked_doc_doctype",
                "Supplier Quotation-intercompany_linked_doc_name",
                "Supplier Quotation-intercompany_linked_company",
                "Supplier Quotation-intercompany_target_company",

                "Item-is_intercompany_item",
                "Item-ic_item_group",
                "Warehouse-is_intercompany_warehouse",
                "Warehouse-ic_warehouse",

                "Customer-ic_customer_group",
                "Customer-custom_company",
                "Supplier-ic_supplier_group",
                "Supplier-custom_company",
                "Customer Group-custom_company",
                "Supplier Group-custom_company"
            ]]
        ]
    }
]

# Install Hooks
after_install = "inter_company_transactions.install.after_install"

# Document Events for Inter-Company Transactions
doc_events = {
    "Sales Order": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Order": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Sales Invoice": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Invoice": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Delivery Note": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Receipt": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Material Request": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Stock Entry": {
        "validate": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.sanitize_intercompany_stock_entry",
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Journal Entry": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Payment Entry": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Quotation": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Supplier Quotation": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    }
}
