import frappe


def validate_intercompany_data(doc, method):
    """Validate inter-company data during import"""
    try:
        if doc.doctype == "Intercompany Transaction Link":
            # Validate companies exist
            if not frappe.db.exists("Company", doc.main_company):
                frappe.throw(f"Main Company {doc.main_company} does not exist")

            # Validate linked companies
            for linked_company in doc.linked_companies:
                if not frappe.db.exists("Company", linked_company.company):
                    frappe.throw(f"Linked Company {linked_company.company} does not exist")

            # Validate transaction types
            for trans_type in doc.transaction_types:
                valid_mappings = {
                    "Sales Order": ["Purchase Order"],
                    "Purchase Order": ["Sales Order"],
                    "Journal Entry": ["Journal Entry"],
                    "Payment Entry": ["Payment Entry"]
                }

                if trans_type.target_type not in valid_mappings.get(trans_type.source_type, []):
                    frappe.throw(f"Invalid mapping: {trans_type.source_type} to {trans_type.target_type}")

    except Exception as e:
        frappe.log_error(f"Error validating inter-company data: {e!s}", "Data Import Validation")
        frappe.throw(f"Validation failed: {e!s}")
