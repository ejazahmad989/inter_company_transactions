import frappe

def add_custom_fields():
    """Add custom fields to standard doctypes"""
    custom_fields = {
        "Payment Entry": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Journal Entry": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Sales Order": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Sales Invoice": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Delivery Note": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Purchase Order": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Purchase invoice": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        "Purchase Receipt": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on=""
            )
        ],
        

        # You can add more doctypes here like Sales Order, Sales Invoice, etc.
    }
    
    for doctype, fields in custom_fields.items():
        for field in fields:
            # Check if the custom field already exists for the doctype
            if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
                field["dt"] = doctype  # Assign the doctype name
                # Create and insert the custom field
                frappe.get_doc({
                    "doctype": "Custom Field",
                    **field
                }).insert(ignore_permissions=True)
                
    frappe.msgprint("Custom fields added successfully.")
