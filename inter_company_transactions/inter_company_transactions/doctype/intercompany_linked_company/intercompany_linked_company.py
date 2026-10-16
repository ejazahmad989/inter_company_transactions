import frappe
from frappe.model.document import Document


class IntercompanyLinkedCompany(Document):
    def validate(self):
        self.validate_company()
        self.validate_parties()
        self.validate_accounts()

    def validate_company(self):
        """Validate company settings"""
        if not frappe.db.exists("Company", self.company):
            frappe.throw(f"Company {self.company} does not exist")

    def validate_parties(self):
        """Validate customers and suppliers"""
        # Main company parties
        if self.main_company_customer and not frappe.db.exists("Customer", self.main_company_customer):
            frappe.throw(f"Customer {self.main_company_customer} does not exist")

        if self.main_company_supplier and not frappe.db.exists("Supplier", self.main_company_supplier):
            frappe.throw(f"Supplier {self.main_company_supplier} does not exist")

        # Other company parties
        if self.other_company_customer and not frappe.db.exists("Customer", self.other_company_customer):
            frappe.throw(f"Customer {self.other_company_customer} does not exist")

        if self.other_company_supplier and not frappe.db.exists("Supplier", self.other_company_supplier):
            frappe.throw(f"Supplier {self.other_company_supplier} does not exist")

    def validate_accounts(self):
        """Validate accounts"""
        parent = frappe.get_doc("Intercompany Transaction Link", self.parent)

        # Validate main company account
        if self.main_company_account:
            account = frappe.get_doc("Account", self.main_company_account)
            if account.company != parent.main_company:
                frappe.throw(f"Account {self.main_company_account} does not belong to main company {parent.main_company}")

            if account.account_type != "Bank":
                frappe.throw(f"Account {self.main_company_account} must be of type 'Bank'")

        # Validate other company account
        if self.other_company_account:
            account = frappe.get_doc("Account", self.other_company_account)
            if account.company != self.company:
                frappe.throw(f"Account {self.other_company_account} does not belong to company {self.company}")

            if account.account_type != "Bank":
                frappe.throw(f"Account {self.other_company_account} must be of type 'Bank'")
