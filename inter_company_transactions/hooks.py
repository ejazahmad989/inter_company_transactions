# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "inter_company_transactions"
app_title = "Inter Company Transactions"
app_publisher = "Your Company"
app_description = "A custom app for handling inter-company transactions with dynamic theming"
app_icon = "octicon octicon-git-compare"
app_color = "blue"
app_email = "your@example.com"
app_license = "MIT"

# ============================================================================
# THEME SYSTEM - WORKING CONFIGURATION
# ============================================================================

# CSS and JS includes
app_include_css = "inter_company_transactions.inter_company_transactions.theme_loader.get_company_css"
app_include_js = [
    "/assets/inter_company_transactions/js/theme_auto_loader.js",
    "/assets/inter_company_transactions/js/inter_company_common.js"
]

# DocType specific JS
doctype_js = {"Company Theme": "public/js/theme_auto_loader.js"}

# Website theme for login
website_theme = "inter_company_transactions.inter_company_transactions.theme_loader.get_website_theme"

# ============================================================================
# EXISTING INTER-COMPANY FUNCTIONALITY
# ============================================================================

# Custom Fields
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                "Sales Order-intercompany_linked_doc_doctype",
                "Sales Order-intercompany_linked_doc_name",
                "Sales Order-intercompany_linked_company",
                "Sales Order-intercompany_target_company",
                "Sales Order-backdate_reason",
                "Sales Order-futuredate_reason",

                "Purchase Order-intercompany_linked_doc_doctype",
                "Purchase Order-intercompany_linked_doc_name",
                "Purchase Order-intercompany_linked_company",
                "Purchase Order-intercompany_target_company",
                "Purchase Order-backdate_reason",
                "Purchase Order-futuredate_reason",

                "Sales Invoice-intercompany_linked_doc_doctype",
                "Sales Invoice-intercompany_linked_doc_name",
                "Sales Invoice-intercompany_linked_company",
                "Sales Invoice-intercompany_target_company",
                "Sales Invoice-inter_company_reference",
                "Sales Invoice-backdate_reason",
                "Sales Invoice-futuredate_reason",

                "Purchase Invoice-intercompany_linked_doc_doctype",
                "Purchase Invoice-intercompany_linked_doc_name",
                "Purchase Invoice-intercompany_linked_company",
                "Purchase Invoice-intercompany_target_company",
                "Purchase Invoice-inter_company_reference",
                "Purchase Invoice-backdate_reason",
                "Purchase Invoice-futuredate_reason",

                "Journal Entry-intercompany_linked_doc_doctype",
                "Journal Entry-intercompany_linked_doc_name",
                "Journal Entry-intercompany_linked_company",
                "Journal Entry-intercompany_target_company",
                "Journal Entry-backdate_reason",
                "Journal Entry-futuredate_reason",

                "Payment Entry-intercompany_linked_doc_doctype",
                "Payment Entry-intercompany_linked_doc_name",
                "Payment Entry-intercompany_linked_company",
                "Payment Entry-intercompany_target_company",
                "Payment Entry-backdate_reason",
                "Payment Entry-futuredate_reason",

                "Delivery Note-intercompany_linked_doc_doctype",
                "Delivery Note-intercompany_linked_doc_name",
                "Delivery Note-intercompany_linked_company",
                "Delivery Note-intercompany_target_company",
                "Delivery Note-backdate_reason",
                "Delivery Note-futuredate_reason",

                "Purchase Receipt-intercompany_linked_doc_doctype",
                "Purchase Receipt-intercompany_linked_doc_name",
                "Purchase Receipt-intercompany_linked_company",
                "Purchase Receipt-intercompany_target_company",
                "Purchase Receipt-backdate_reason",
                "Purchase Receipt-futuredate_reason",

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
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Purchase Order": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Sales Invoice": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Purchase Invoice": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Delivery Note": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Purchase Receipt": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Material Request": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Stock Entry": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents"
    },
    "Journal Entry": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
    },
    "Payment Entry": {
        "on_submit": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.create_linked_documents",
        "on_cancel": "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.cancel_linked_documents",
        "before_submit": "inter_company_transactions.date_control.date_validator.validate_transaction_date"
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

# Boot session for theme data
def boot_session(bootinfo):
    """Add theme information to boot session"""
    try:
        import frappe
        from inter_company_transactions.inter_company_transactions.theme_loader import get_active_theme_for_company
        
        if frappe.session.user != "Guest":
            company = frappe.get_value("User", frappe.session.user, "company")
            if not company:
                company = frappe.db.get_single_value("Global Defaults", "default_company")
            
            if company:
                theme_data = get_active_theme_for_company(company)
                if theme_data:
                    bootinfo.company_theme = {
                        "company": company,
                        "theme_name": theme_data.get("name", "Default"),
                        "colors": theme_data.get("colors", {}),
                        "font": theme_data.get("font", "inherit")
                    }
    except Exception as e:
        import frappe
        frappe.logger().error(f"Error in boot_session for theme: {str(e)}")
