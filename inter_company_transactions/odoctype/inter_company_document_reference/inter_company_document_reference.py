# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class InterCompanyDocumentReference(Document):
    def validate(self):
        self.validate_companies()
        self.validate_documents()
    
    def validate_companies(self):
        """Ensure source and target companies are different"""
        if self.source_company == self.target_company:
            frappe.throw("Source and Target companies cannot be the same")
    
    def validate_documents(self):
        """Validate document references"""
        if not frappe.db.exists(self.source_doctype, self.source_name):
            frappe.throw(f"Source document {self.source_doctype} {self.source_name} does not exist")
        
        if not frappe.db.exists(self.target_doctype, self.target_name):
            frappe.throw(f"Target document {self.target_doctype} {self.target_name} does not exist")