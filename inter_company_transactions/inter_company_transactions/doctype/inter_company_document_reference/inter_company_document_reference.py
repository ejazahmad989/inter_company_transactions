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

        if not self.get("is_remote") and not frappe.db.exists(self.target_doctype, self.target_name):
            frappe.throw(f"Target document {self.target_doctype} {self.target_name} does not exist")

    def on_trash(self):
        """When an Inter Company Document Reference is deleted, unlink mirrored fields on the target document
        so users are never locked out of editing, cancelling, or deleting it."""
        if (
            self.target_doctype
            and self.target_name
            and hasattr(frappe, "db")
            and frappe.db
            and frappe.db.exists(self.target_doctype, self.target_name)
        ):
            updates = {}
            for fn in ("intercompany_linked_doc_doctype", "intercompany_linked_doc_name", "intercompany_linked_company"):
                if frappe.db.has_column(self.target_doctype, fn):
                    cur = frappe.db.get_value(self.target_doctype, self.target_name, fn)
                    if cur:
                        updates[fn] = ""
            if updates:
                frappe.db.set_value(self.target_doctype, self.target_name, updates, update_modified=False)

