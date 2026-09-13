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
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Journal Entry": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Sales Order": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Sales Invoice": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Delivery Note": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Purchase Order": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Purchase invoice": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
            )
        ],
        "Purchase Receipt": [
            dict(
                fieldname="backdate_reason",
                label="Backdate Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date < frappe.utils.nowdate()"
            ),
            dict(
                fieldname="futuredate_reason",
                label="Future Date Reason",
                fieldtype="Small Text",
                insert_after="posting_date",
                depends_on="eval:doc.posting_date > frappe.utils.nowdate()"
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
