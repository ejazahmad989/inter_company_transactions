# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class IntercompanyTransactionLink(Document):
    def validate(self):
        self.validate_companies()
        self.validate_transaction_types()
        self.create_temporary_accounts()
    
    def validate_companies(self):
        """Ensure main company and linked companies are different"""
        linked_companies = [d.company for d in self.linked_companies]
        if self.main_company in linked_companies:
            frappe.throw("Main Company cannot be in Linked Companies")
        
        if len(linked_companies) != len(set(linked_companies)):
            frappe.throw("Duplicate companies found in Linked Companies")
    
    def validate_transaction_types(self):
        """Validate transaction type mappings"""
        valid_mappings = {
            "Sales Order": ["Purchase Order"],
            "Purchase Order": ["Sales Order"],
            "Journal Entry": ["Journal Entry"],
            "Payment Entry": ["Payment Entry"]
        }
        
        for trans_type in self.transaction_types:
            if trans_type.target_type not in valid_mappings.get(trans_type.source_type, []):
                frappe.throw(f"Invalid mapping: {trans_type.source_type} cannot be mapped to {trans_type.target_type}")
    
    def create_temporary_accounts(self):
        """Create temporary accounts for inter-company transactions"""
        def get_bank_account(company):
            """Get the root Bank account for the company"""
            bank = frappe.db.get_value("Account", 
                {"account_name": "Bank Accounts", "company": company, "is_group": 1}, "name")
            if not bank:
                bank = frappe.db.get_value("Account", 
                    {"account_type": "Bank", "company": company, "is_group": 1}, "name")
            return bank

        def ensure_group_exists(company, group_name, parent):
            """Create or get the Inter Company account group"""
            if not parent:
                frappe.throw(f"Could not find Bank account for company {company}")
                
            existing_group = frappe.db.get_value("Account", 
                {"account_name": group_name, "company": company, "is_group": 1}, "name")
                
            if not existing_group:
                group_doc = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": group_name,
                    "parent_account": parent,
                    "is_group": 1,
                    "company": company,
                    "account_type": "Bank",
                    "root_type": "Asset"
                })
                group_doc.insert(ignore_permissions=True)
                return group_doc.name
            return existing_group

        def create_temp_account(company, account_name, parent_group):
            """Create temporary account if it doesn't exist"""
            if not parent_group:
                frappe.throw(f"Parent group not found for company {company}")
                
            existing_account = frappe.db.get_value("Account", 
                {"account_name": account_name, "company": company}, "name")
                
            if not existing_account:
                account_doc = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": account_name,
                    "parent_account": parent_group,
                    "is_group": 0,
                    "company": company,
                    "account_type": "Bank",
                    "root_type": "Asset"
                })
                account_doc.insert(ignore_permissions=True)
                return account_doc.name
            return existing_account

        try:
            # For main company
            bank_main = get_bank_account(self.main_company)
            if not bank_main:
                frappe.throw(f"Could not find Bank account for company {self.main_company}")
            
            interco_group_main = ensure_group_exists(self.main_company, "Inter Company", bank_main)
            
            # Create temporary accounts for each linked company
            for linked_company in self.linked_companies:
                # Create account in main company
                main_temp_account = create_temp_account(
                    self.main_company,
                    f"TMP-{linked_company.company}",
                    interco_group_main
                )
                
                # Create account in linked company
                bank_linked = get_bank_account(linked_company.company)
                if not bank_linked:
                    frappe.throw(f"Could not find Bank account for company {linked_company.company}")
                
                interco_group_linked = ensure_group_exists(linked_company.company, "Inter Company", bank_linked)
                linked_temp_account = create_temp_account(
                    linked_company.company,
                    f"TMP-{self.main_company}",
                    interco_group_linked
                )
                
                # Update temporary accounts in linked company record
                linked_company.temporary_account = linked_temp_account
                
        except Exception as e:
            frappe.log_error(f"Error creating temporary accounts: {str(e)}", 
                "Inter Company Transaction Setup")
            frappe.throw(f"Failed to create temporary accounts: {str(e)}")

def create_linked_documents(doc, method):
    """Create corresponding documents in all linked companies"""
    if doc.get("intercompany_linked_doc_doctype"):
        return  # Skip if this is already a linked document
    
    # Find applicable mappings
    mappings = find_applicable_mappings(doc)
    if not mappings:
        return
    
    for mapping in mappings:
        try:
            linked_doc = create_corresponding_document(doc, mapping)
            if linked_doc:
                update_document_references(doc, linked_doc)
                linked_doc.insert()
                frappe.msgprint(f"Created draft {linked_doc.doctype} {linked_doc.name} in company {linked_doc.company}")
        except Exception as e:
            frappe.log_error(f"Error creating linked document: {str(e)}", "Inter Company Transaction Error")
            frappe.msgprint(f"Failed to create linked document in company {mapping.company}: {str(e)}")

def cancel_linked_documents(doc, method):
    """Cancel corresponding documents in all linked companies"""
    linked_docs = frappe.get_all(
        "Inter Company Document Reference",
        filters={
            "source_doctype": doc.doctype,
            "source_name": doc.name
        },
        fields=["target_doctype", "target_name"]
    )
    
    for linked_doc in linked_docs:
        try:
            if frappe.db.exists(linked_doc.target_doctype, linked_doc.target_name):
                target_doc = frappe.get_doc(linked_doc.target_doctype, linked_doc.target_name)
                if target_doc.docstatus == 1:  # If submitted
                    target_doc.cancel()
                    frappe.msgprint(f"Cancelled linked {target_doc.doctype} {target_doc.name}")
        except Exception as e:
            frappe.log_error(f"Error cancelling linked document: {str(e)}", "Inter Company Transaction Error")
            frappe.msgprint(f"Failed to cancel {linked_doc.target_doctype} {linked_doc.target_name}: {str(e)}")

def find_applicable_mappings(doc):
    """Find appropriate mapping configurations"""
    mappings = []
    
    # Get all enabled transaction links
    links = frappe.get_all(
        "Intercompany Transaction Link",
        filters={"enabled": 1},
        fields=["name"]
    )
    
    for link in links:
        mapping = frappe.get_doc("Intercompany Transaction Link", link.name)
        
        # Check if doc's company is main company or in linked companies
        is_main = doc.company == mapping.main_company
        is_linked = any(lc.company == doc.company for lc in mapping.linked_companies)
        
        if not (is_main or is_linked):
            continue
        
        # Check transaction types
        for trans_type in mapping.transaction_types:
            matches = False
            
            # From main company
            if is_main and trans_type.source_type == doc.doctype:
                if trans_type.direction in ["Main to Other", "Both"]:
                    matches = True
            # From linked company
            elif is_linked and trans_type.source_type == doc.doctype:
                if trans_type.direction in ["Other to Main", "Both"]:
                    matches = True
            
            if matches:
                # Add each applicable linked company
                for linked_company in mapping.linked_companies:
                    if doc.company != linked_company.company:
                        mappings.append({
                            "mapping": mapping,
                            "transaction_type": trans_type,
                            "company": linked_company.company,
                            "linked_company": linked_company
                        })
    
    return mappings

def create_corresponding_document(source_doc, mapping_info):
    """Create the corresponding document based on mapping"""
    mapping = mapping_info["mapping"]
    trans_type = mapping_info["transaction_type"]
    target_company = mapping_info["company"]
    linked_company = mapping_info["linked_company"]
    
    if source_doc.doctype == "Sales Order" and trans_type.target_type == "Purchase Order":
        return create_purchase_order(source_doc, mapping, linked_company)
    elif source_doc.doctype == "Purchase Order" and trans_type.target_type == "Sales Order":
        return create_sales_order(source_doc, mapping, linked_company)
    elif source_doc.doctype == "Journal Entry" and trans_type.target_type == "Journal Entry":
        return create_journal_entry(source_doc, mapping, linked_company)
    elif source_doc.doctype == "Payment Entry" and trans_type.target_type == "Payment Entry":
        return create_payment_entry(source_doc, mapping, linked_company)
    return None

def update_document_references(source_doc, target_doc):
    """Create inter-company document reference"""
    try:
        ref_doc = frappe.get_doc({
            "doctype": "Inter Company Document Reference",
            "source_doctype": source_doc.doctype,
            "source_name": source_doc.name,
            "source_company": source_doc.company,
            "target_doctype": target_doc.doctype,
            "target_name": target_doc.name,
            "target_company": target_doc.company
        })
        ref_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error creating document reference: {str(e)}", "Inter Company Transaction Error")
        frappe.throw(f"Failed to create document reference: {str(e)}")

def create_journal_entry(source_je, mapping, linked_company):
    """Create corresponding Journal Entry"""
    je = frappe.new_doc("Journal Entry")
    je.company = linked_company.company
    je.posting_date = source_je.posting_date
    je.multi_currency = source_je.multi_currency
    je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name}" + (source_je.user_remark or "")
    
    # Get temporary account
    tmp_account = linked_company.temporary_account
    
    # Reverse debit/credit for inter-company entries
    for entry in source_je.accounts:
        je.append("accounts", {
            "account": tmp_account or get_mapped_account(entry.account, source_je.company, linked_company.company),
            "debit_in_account_currency": entry.credit_in_account_currency,
            "credit_in_account_currency": entry.debit_in_account_currency,
            "cost_center": get_default_cost_center(linked_company.company)
        })
    
    je.docstatus = 0  # Keep as draft
    return je

def create_payment_entry(source_pe, mapping, linked_company):
    """Create corresponding Payment Entry"""
    pe = frappe.new_doc("Payment Entry")
    pe.company = linked_company.company
    pe.posting_date = source_pe.posting_date
    pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
    pe.mode_of_payment = source_pe.mode_of_payment
    
    # Copy reference details
    pe.reference_no = source_pe.reference_no
    pe.reference_date = source_pe.reference_date
    
    # Get temporary account
    tmp_account = linked_company.temporary_account
    
    # Set paid from/to accounts
    if pe.payment_type == "Receive":
        pe.paid_from = tmp_account
        pe.paid_to = frappe.db.get_value("Company", linked_company.company, "default_bank_account")
    else:
        pe.paid_from = frappe.db.get_value("Company", linked_company.company, "default_bank_account")
        pe.paid_to = tmp_account
    
    # Set amounts
    pe.paid_amount = source_pe.paid_amount
    pe.received_amount = source_pe.received_amount
    pe.target_exchange_rate = source_pe.target_exchange_rate
    
    # Copy project reference if any
    if hasattr(source_pe, 'project'):
        pe.project = source_pe.project
    
    pe.docstatus = 0  # Keep as draft
    return pe

def create_purchase_order(sales_order, mapping, linked_company):
    """Create Purchase Order from Sales Order"""
    po = frappe.new_doc("Purchase Order")
    po.company = linked_company.company
    po.supplier = linked_company.default_supplier
    po.currency = sales_order.currency
    po.conversion_rate = sales_order.conversion_rate
    po.transaction_date = sales_order.transaction_date
    po.schedule_date = sales_order.delivery_date
    
    for item in sales_order.items:
        po.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": get_default_warehouse(linked_company.company),
            "schedule_date": item.delivery_date
        })
    
    po.docstatus = 0  # Keep as draft
    return po

def create_sales_order(purchase_order, mapping, linked_company):
    """Create Sales Order from Purchase Order"""
    so = frappe.new_doc("Sales Order")
    so.company = linked_company.company
    so.customer = linked_company.default_customer
    so.currency = purchase_order.currency
    so.conversion_rate = purchase_order.conversion_rate
    so.transaction_date = purchase_order.transaction_date
    so.delivery_date = purchase_order.schedule_date
    
    for item in purchase_order.items:
        so.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": get_default_warehouse(linked_company.company),
            "delivery_date": item.schedule_date
        })
    
    so.docstatus = 0  # Keep as draft
    return so

def get_default_warehouse(company):
    """Get default warehouse for company"""
    return frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")

def get_default_cost_center(company):
    """Get default cost center for company"""
    return frappe.db.get_value("Company", company, "cost_center")

def get_mapped_account(account, from_company, to_company):
    """Get corresponding account in target company"""
    account_type = frappe.db.get_value("Account", account, "account_type")
    account_name = frappe.db.get_value("Account", account, "account_name")
    
    # Try to find account with same name
    mapped_account = frappe.db.get_value(
        "Account",
        {"account_name": account_name, "company": to_company},
        "name"
    )
    
    # If not found, try to find by account type
    if not mapped_account and account_type:
        mapped_account = frappe.db.get_value(
            "Account",
            {"account_type": account_type, "company": to_company, "is_group": 0},
            "name"
        )
    
    # Default fallback
    if not mapped_account:
        if account_type == "Receivable":
            mapped_account = frappe.db.get_value("Company", to_company, "default_receivable_account")
        elif account_type == "Payable":
            mapped_account = frappe.db.get_value("Company", to_company, "default_payable_account")
        else:
            mapped_account = frappe.db.get_value("Company", to_company, "default_expense_account")
    
    return mapped_account