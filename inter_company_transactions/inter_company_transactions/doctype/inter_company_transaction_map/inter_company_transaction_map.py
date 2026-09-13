import frappe
from frappe import _
from frappe.model.document import Document


class InterCompanyTransactionMap(Document):
    def validate(self):
        self.validate_companies()
        self.validate_duplicate_mappings()

    def validate_companies(self):
        for row in self.transaction_mappings:
            if row.other_company == self.main_company:
                frappe.throw(
                    _("Row #{0}: Other Company cannot be the same as Main Company ({1})").format(
                        row.idx, self.main_company
                    )
                )

    def validate_duplicate_mappings(self):
        seen = set()
        for row in self.transaction_mappings:
            key = (
                row.main_company_transaction_type,
                row.other_company,
                row.other_company_transaction_type,
            )
            if key in seen:
                frappe.msgprint(
                    _("Row #{0}: Duplicate mapping defined for {1} to {2} ({3})").format(
                        row.idx,
                        row.main_company_transaction_type,
                        row.other_company,
                        row.other_company_transaction_type,
                    ),
                    indicator="orange",
                )
            seen.add(key)
