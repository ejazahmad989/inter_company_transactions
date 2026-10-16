import frappe
from frappe.model.document import Document


class IntercompanyTransactionType(Document):
    def validate(self):
        self.auto_set_target_type()
        self.validate_transaction_types()
        self.validate_direction()

    def auto_set_target_type(self):
        """Automatically switch target_type based on source_type"""
        default_targets = {
            "Sales Order": "Purchase Order",
            "Purchase Order": "Sales Order",
            "Sales Invoice": "Purchase Invoice",
            "Purchase Invoice": "Sales Invoice",
            "Delivery Note": "Purchase Receipt",
            "Purchase Receipt": "Delivery Note",
            "Stock Entry": "Stock Entry",
            "Journal Entry": "Journal Entry",
            "Payment Entry": "Payment Entry",
            "Quotation": "Supplier Quotation",
            "Supplier Quotation": "Quotation",
            "Material Request": "Purchase Order",
            "Request for Quotation": "Supplier Quotation",
            "Subcontracting Order": "Purchase Order",
            "Landed Cost Voucher": "Journal Entry"
        }
        if self.source_type and (not self.target_type or self.target_type not in self.get_valid_targets(self.source_type)):
            self.target_type = default_targets.get(self.source_type, self.source_type)

    def validate_direction(self):
        if not self.direction:
            self.direction = "Both"

    def get_valid_targets(self, source_type):
        """Get allowed target types for given source type"""
        valid_mappings = {
            "Sales Order": ["Purchase Order"],
            "Purchase Order": ["Sales Order"],
            "Sales Invoice": ["Purchase Invoice"],
            "Purchase Invoice": ["Sales Invoice"],
            "Delivery Note": ["Purchase Receipt"],
            "Purchase Receipt": ["Delivery Note"],
            "Stock Entry": ["Stock Entry"],
            "Journal Entry": ["Journal Entry"],
            "Payment Entry": ["Payment Entry"],
            "Quotation": ["Supplier Quotation"],
            "Supplier Quotation": ["Quotation"],
            "Material Request": ["Purchase Order", "Sales Order"],
            "Request for Quotation": ["Supplier Quotation"],
            "Subcontracting Order": ["Purchase Order"],
            "Landed Cost Voucher": ["Journal Entry"]
        }
        return valid_mappings.get(source_type, [source_type])

    def validate_transaction_types(self):
        """Validate appropriate transaction type mappings"""
        valid_targets = self.get_valid_targets(self.source_type)
        if self.source_type and self.target_type and self.target_type not in valid_targets:
            # Auto-align target type to standard counterpart
            self.target_type = valid_targets[0]
