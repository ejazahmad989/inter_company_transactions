# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class IntercompanyTransactionType(Document):
    def validate(self):
        self.validate_transaction_types()
    
    def validate_transaction_types(self):
        """Validate appropriate transaction type mappings"""
        valid_mappings = {
            "Sales Order": ["Purchase Order"],
            "Purchase Order": ["Sales Order"],
            "Journal Entry": ["Journal Entry"],
            "Payment Entry": ["Payment Entry"]
        }
        
        if self.target_type not in valid_mappings.get(self.source_type, []):
            frappe.throw(f"Invalid mapping: {self.source_type} cannot be mapped to {self.target_type}")