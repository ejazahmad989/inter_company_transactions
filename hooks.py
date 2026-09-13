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

# Document Events
doc_events = {
    "Sales Order": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Purchase Order": {
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
    }
}