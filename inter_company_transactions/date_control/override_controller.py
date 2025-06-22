import frappe
from frappe.model.document import Document

class CustomPaymentEntry(Document):
    def validate(self):
        super().validate()
        # Add custom payment entry validation if needed

def override_doctype_methods():
    """Override standard doctype methods"""
    from frappe import _dict
    
    # Example for Payment Entry
    original_payment_entry = frappe.get_meta("Payment Entry")
    original_payment_entry.validate = CustomPaymentEntry.validate