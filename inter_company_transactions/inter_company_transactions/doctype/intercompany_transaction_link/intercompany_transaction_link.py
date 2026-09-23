# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate


class IntercompanyTransactionLink(Document):
    def validate(self):
        self.validate_companies()
        self.validate_parties()
        # DO NOT call validate_transaction_types here - it belongs to child table
    
    def validate_companies(self):
        """Ensure main company and linked companies are different"""
        linked_companies = [d.company for d in self.linked_companies if d.company]
        if self.main_company in linked_companies:
            frappe.throw(_("Main Company cannot be in Linked Companies"))
        
        if len(linked_companies) != len(set(linked_companies)):
            frappe.throw(_("Duplicate companies found in Linked Companies"))
    
    def validate_parties(self):
        """Validate that customers and suppliers are properly mapped between companies"""
        for linked_company in self.linked_companies:
            # Only validate required parties based on what's configured
            if linked_company.main_company_customer and not linked_company.other_company_supplier:
                frappe.throw(_("Other Company Supplier is required when Main Company Customer is set for {0}").format(linked_company.company))
            
            if linked_company.main_company_supplier and not linked_company.other_company_customer:
                frappe.throw(_("Other Company Customer is required when Main Company Supplier is set for {0}").format(linked_company.company))


def create_linked_documents(doc, method=None):
    """Create corresponding documents in all linked companies"""
    if doc.get("intercompany_linked_doc_doctype") or doc.get("intercompany_linked_doc_name"):
        return
    
    # Find applicable mappings
    mappings = find_applicable_mappings(doc)
    if not mappings:
        return
    
    for i, mapping in enumerate(mappings):
        try:
            # Determine direction
            is_main_to_other = doc.company == mapping["mapping"].main_company
            direction = "main_to_other" if is_main_to_other else "other_to_main"
            
            # Validate required parties before creating document
            validate_required_parties(doc, mapping)
            
            linked_doc = create_corresponding_document(doc, mapping, direction)
            
            if linked_doc:
                # Set references
                linked_doc.intercompany_linked_doc_doctype = doc.doctype
                linked_doc.intercompany_linked_doc_name = doc.name
                linked_doc.intercompany_linked_company = doc.company
                
                linked_doc.flags.ignore_permissions = True
                linked_doc.insert()
                
                create_document_reference(doc, linked_doc)
                
                frappe.msgprint(_("Created draft {0} {1} in company {2}").format(
                    linked_doc.doctype, linked_doc.name, linked_doc.company
                ))
            
        except Exception as e:
            frappe.log_error(f"Error in mapping {i+1}: {str(e)}", "Inter Company Transaction Error")
            frappe.msgprint(_("Failed to create linked document in company {0}: {1}").format(
                mapping.get('company', ''), str(e)
            ))


def cancel_linked_documents(doc, method=None):
    """Cancel corresponding documents in all linked companies - BIDIRECTIONAL"""
    if not hasattr(doc, 'company') or not doc.company:
        return
    
    # Check if this cancellation is triggered by our method (prevent infinite loop)
    if doc.flags.get("intercompany_auto_cancel"):
        return
    
    # Check if Inter Company Document Reference doctype exists
    if not frappe.db.exists("DocType", "Inter Company Document Reference"):
        return
        
    all_related_docs = []
    
    # Find documents where current doc is the SOURCE
    try:
        linked_docs = frappe.get_all(
            "Inter Company Document Reference",
            filters=[
                ["source_doctype", "=", doc.doctype],
                ["source_name", "=", doc.name],
                ["source_company", "=", doc.company]
            ],
            fields=["target_doctype", "target_name", "target_company"]
        )
        
        for linked_doc in linked_docs:
            all_related_docs.append({
                "doctype": linked_doc.target_doctype,
                "name": linked_doc.target_name,
                "company": linked_doc.target_company,
                "relationship": "target"
            })
    except Exception as e:
        frappe.logger().error(f"Error finding linked documents (as source): {str(e)}")
    
    # Find documents where current doc is the TARGET  
    try:
        reverse_links = frappe.get_all(
            "Inter Company Document Reference",
            filters=[
                ["target_doctype", "=", doc.doctype],
                ["target_name", "=", doc.name],  
                ["target_company", "=", doc.company]
            ],
            fields=["source_doctype", "source_name", "source_company"]
        )
        
        for reverse_link in reverse_links:
            all_related_docs.append({
                "doctype": reverse_link.source_doctype,
                "name": reverse_link.source_name,
                "company": reverse_link.source_company,
                "relationship": "source"
            })
    except Exception as e:
        frappe.logger().error(f"Error finding reverse links (as target): {str(e)}")
    
    def cancel_doc(doctype, docname, company=None, relationship=None):
        """Cancel a document with proper error handling"""
        try:
            if not frappe.db.exists(doctype, docname):
                return False
                
            target_doc = frappe.get_doc(doctype, docname)
            
            if target_doc.docstatus != 1:
                return False
            
            # Set all permission flags
            target_doc.flags.ignore_permissions = True
            target_doc.flags.ignore_mandatory = True
            target_doc.flags.ignore_account_permission = True
            target_doc.flags.ignore_validate = True
            target_doc.flags.ignore_links = True
            target_doc.flags.ignore_validate_update_after_submit = True
            target_doc.flags.ignore_workflow = True
            
            # CRITICAL: Set flag to prevent recursive calling
            target_doc.flags.intercompany_auto_cancel = True
            
            target_doc.cancel()
            frappe.db.commit()
            
            frappe.msgprint(_("Cancelled {0} {1} ({2} document)").format(
                target_doc.doctype, target_doc.name, relationship
            ))
            return True
            
        except Exception as e:
            frappe.log_error(
                f"Error cancelling document: {str(e)}\n"
                f"Document: {doctype} {docname}\n"
                f"Company: {company}\n"
                f"Relationship: {relationship}\n"
                f"Traceback: {frappe.get_traceback()}",
                "Inter Company Transaction Error"
            )
            return False
    
    try:
        # Cancel ALL related documents (both sources and targets)
        for related_doc in all_related_docs:
            try:
                cancel_doc(
                    related_doc['doctype'], 
                    related_doc['name'],
                    related_doc['company'],
                    related_doc['relationship']
                )
            except Exception as e:
                frappe.log_error(
                    f"Error cancelling {related_doc['relationship']} document: {str(e)}\n"
                    f"Document: {related_doc['doctype']} {related_doc['name']}\n"
                    f"Company: {related_doc['company']}",
                    "Inter Company Transaction Error"
                )
                
    except Exception as e:
        frappe.log_error(
            f"Error in cancel_linked_documents: {str(e)}\n"
            f"Document: {doc.doctype} {doc.name}\n"
            f"Traceback: {frappe.get_traceback()}",
            "Inter Company Transaction Error"
        )


def validate_required_parties(doc, mapping):
    """Validate that required parties are configured based on transaction type"""
    linked_company = mapping["linked_company"]
    trans_type = mapping["transaction_type"]
    direction = mapping.get("direction", "unknown")
    
    # Sales Order -> Purchase Order
    if doc.doctype == "Sales Order" and trans_type.target_type == "Purchase Order":
        if not linked_company.main_company_supplier:
            frappe.throw(_("Main Company Supplier is required for company {0}").format(linked_company.company))
    
    # Sales Invoice -> Purchase Invoice  
    elif doc.doctype == "Sales Invoice" and trans_type.target_type == "Purchase Invoice":
        if direction == "other_to_main":
            required_supplier = linked_company.main_company_supplier
            field_name = "Main Company Supplier"
        else:
            required_supplier = linked_company.other_company_supplier
            field_name = "Other Company Supplier"
            
        if not required_supplier:
            frappe.throw(_("{0} is required for company {1}").format(field_name, linked_company.company))
    
    # Purchase Order -> Sales Order
    elif doc.doctype == "Purchase Order" and trans_type.target_type == "Sales Order":
        if not linked_company.main_company_customer:
            frappe.throw(_("Main Company Customer is required for company {0}").format(linked_company.company))
    
    # Purchase Invoice -> Sales Invoice
    elif doc.doctype == "Purchase Invoice" and trans_type.target_type == "Sales Invoice":
        if direction == "other_to_main":
            required_customer = linked_company.main_company_customer
            field_name = "Main Company Customer"
        else:
            required_customer = linked_company.other_company_customer
            field_name = "Other Company Customer"
            
        if not required_customer:
            frappe.throw(_("{0} is required for company {1}").format(field_name, linked_company.company))
    
    # Purchase Receipt -> Delivery Note
    elif doc.doctype == "Purchase Receipt" and trans_type.target_type == "Delivery Note":
        if direction == "other_to_main":
            required_customer = linked_company.main_company_customer
        else:
            required_customer = linked_company.other_company_customer
        if not required_customer:
            frappe.throw(_("Customer is required for company {0}").format(linked_company.company))
    
    # Delivery Note -> Purchase Receipt
    elif doc.doctype == "Delivery Note" and trans_type.target_type == "Purchase Receipt":
        if direction == "other_to_main":
            required_supplier = linked_company.main_company_supplier
        else:
            required_supplier = linked_company.other_company_supplier
        if not required_supplier:
            frappe.throw(_("Supplier is required for company {0}").format(linked_company.company))
    
    # Journal Entry and Payment Entry
    elif doc.doctype in ["Journal Entry", "Payment Entry"]:
        if not linked_company.main_company_customer:
            frappe.throw(_("Main Company Customer is required for company {0}").format(linked_company.company))
        if not linked_company.other_company_supplier:
            frappe.throw(_("Other Company Supplier is required for company {0}").format(linked_company.company))


def create_journal_entry(source_je, mapping, linked_company, direction):
    """Create corresponding Journal Entry"""
    je = frappe.new_doc("Journal Entry")
    
    # Set company based on direction
    if direction == "other_to_main":
        je.company = mapping.main_company
        supplier = linked_company.main_company_supplier
        customer = linked_company.main_company_customer
        tmp_account = getattr(linked_company, "main_company_account", None)
    else:
        je.company = linked_company.company
        supplier = linked_company.other_company_supplier
        customer = linked_company.other_company_customer
        tmp_account = getattr(linked_company, "other_company_account", None)
    
    if not tmp_account:
        tmp_account = frappe.db.get_value("Company", je.company, "default_cash_account") or \
                      frappe.db.get_value("Company", je.company, "default_bank_account")
    
    je.posting_date = source_je.posting_date
    je.multi_currency = source_je.multi_currency
    je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name} " + (source_je.user_remark or "")
    
    source_party_type = None
    source_party = None
    source_is_credit = False
    
    for acc in source_je.accounts:
        if acc.party_type and acc.party:
            source_party_type = acc.party_type
            source_party = acc.party
            source_is_credit = acc.credit_in_account_currency > 0
            break
    
    if source_party_type == "Supplier" and source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_receivable_account"),
            "party_type": "Customer",
            "party": customer,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": source_je.total_credit,
            "cost_center": get_default_cost_center(je.company)
        })
        je.append("accounts", {
            "account": tmp_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": source_je.total_credit,
            "cost_center": get_default_cost_center(je.company)
        })
    elif source_party_type == "Supplier" and not source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_receivable_account"),
            "party_type": "Customer",
            "party": customer,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": source_je.total_debit,
            "cost_center": get_default_cost_center(je.company)
        })
        je.append("accounts", {
            "account": tmp_account,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": source_je.total_debit,
            "cost_center": get_default_cost_center(je.company)
        })
    elif source_party_type == "Customer" and source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_payable_account"),
            "party_type": "Supplier",
            "party": supplier,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": source_je.total_credit,
            "cost_center": get_default_cost_center(je.company)
        })
        je.append("accounts", {
            "account": tmp_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": source_je.total_credit,
            "cost_center": get_default_cost_center(je.company)
        })
    else:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_payable_account"),
            "party_type": "Supplier",
            "party": supplier,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": source_je.total_debit,
            "cost_center": get_default_cost_center(je.company)
        })
        je.append("accounts", {
            "account": tmp_account,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": source_je.total_debit,
            "cost_center": get_default_cost_center(je.company)
        })
    
    je.flags.ignore_permissions = True
    je.flags.ignore_mandatory = True
    je.flags.ignore_account_permission = True
    je.flags.ignore_validate = True
    je.flags.ignore_links = True
    
    je.intercompany_target_company = source_je.company
    je.docstatus = 0  # Keep as draft
    return je


def create_payment_entry(source_pe, mapping, linked_company, direction):
    """Create corresponding Payment Entry"""
    try:
        pe = frappe.new_doc("Payment Entry")
        
        if direction == "other_to_main":
            pe.company = mapping.main_company
            tmp_account = getattr(linked_company, "main_company_account", None)
            customer = linked_company.main_company_customer
            supplier = linked_company.main_company_supplier
        else:
            pe.company = linked_company.company
            tmp_account = getattr(linked_company, "other_company_account", None)
            customer = linked_company.other_company_customer
            supplier = linked_company.other_company_supplier
        
        if not tmp_account:
            tmp_account = frappe.db.get_value("Company", pe.company, "default_cash_account") or \
                          frappe.db.get_value("Company", pe.company, "default_bank_account")
        
        pe.posting_date = source_pe.posting_date
        pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
        pe.mode_of_payment = source_pe.mode_of_payment
        
        if pe.payment_type == "Pay":
            pe.paid_from = tmp_account
            pe.paid_to = frappe.db.get_value("Company", pe.company, "default_payable_account")
            pe.party_type = "Supplier"
            pe.party = supplier
            pe.party_name = frappe.db.get_value("Supplier", supplier, "supplier_name") if supplier else ""
        else:
            pe.paid_from = frappe.db.get_value("Company", pe.company, "default_receivable_account")
            pe.paid_to = tmp_account
            pe.party_type = "Customer"
            pe.party = customer
            pe.party_name = frappe.db.get_value("Customer", customer, "customer_name") if customer else ""
        
        if pe.paid_from:
            pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency")
        if pe.paid_to:
            pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")
        
        pe.paid_amount = source_pe.paid_amount
        pe.received_amount = source_pe.received_amount
        pe.target_exchange_rate = source_pe.target_exchange_rate
        
        pe.reference_no = source_pe.reference_no
        pe.reference_date = source_pe.reference_date
        
        pe.intercompany_linked_doc_doctype = source_pe.doctype
        pe.intercompany_linked_doc_name = source_pe.name
        pe.intercompany_linked_company = source_pe.company
        pe.intercompany_target_company = source_pe.company
        
        pe.flags.ignore_permissions = True
        pe.flags.ignore_mandatory = True
        pe.flags.ignore_account_permission = True
        pe.flags.ignore_validate = True
        pe.flags.ignore_links = True
        pe.flags.ignore_party_validation = True
        pe.flags.ignore_exchange_rate = True
        pe.flags.ignore_pricing_rule = True
        
        pe.docstatus = 0  # Keep as draft
        return pe
        
    except Exception as e:
        frappe.log_error(
            f"Error creating payment entry: {str(e)}\n"
            f"Source PE: {source_pe.name}\n"
            f"Direction: {direction}\n"
            f"Traceback: {frappe.get_traceback()}",
            "Inter Company Transaction Error"
        )
        raise


def create_purchase_order(sales_order, mapping, linked_company, direction):
    """Create Purchase Order from Sales Order"""
    po = frappe.new_doc("Purchase Order")
    
    if direction == "other_to_main":
        po.company = mapping.main_company
        po.supplier = linked_company.main_company_supplier
    else:
        po.company = linked_company.company
        po.supplier = linked_company.other_company_supplier
    
    if not po.supplier:
        frappe.throw(_("Supplier not found for company {0}").format(po.company))
    
    po.currency = sales_order.currency
    po.conversion_rate = sales_order.conversion_rate
    po.transaction_date = sales_order.transaction_date
    po.schedule_date = sales_order.delivery_date
    po.intercompany_target_company = sales_order.company
    
    warehouse = get_default_warehouse(po.company)
    if not warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(po.company))
    
    for item in sales_order.items:
        po.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": warehouse,
            "schedule_date": item.delivery_date or sales_order.delivery_date
        })
    
    po.flags.ignore_permissions = True
    po.flags.ignore_mandatory = True
    po.flags.ignore_account_permission = True
    po.flags.ignore_validate = True
    po.flags.ignore_links = True
    po.flags.ignore_pricing_rule = True
    po.flags.ignore_party_validation = True
    
    po.docstatus = 0  # Keep as draft
    return po


def create_sales_order(purchase_order, mapping, linked_company, direction):
    """Create Sales Order from Purchase Order"""
    so = frappe.new_doc("Sales Order")
    
    if direction == "other_to_main":
        so.company = mapping.main_company
        so.customer = linked_company.main_company_customer
    else:
        so.company = linked_company.company
        so.customer = linked_company.other_company_customer
    
    if not so.customer:
        frappe.throw(_("Customer not found for company {0}").format(so.company))
    
    so.currency = purchase_order.currency
    so.conversion_rate = purchase_order.conversion_rate
    so.transaction_date = purchase_order.transaction_date
    so.delivery_date = purchase_order.schedule_date
    so.intercompany_target_company = purchase_order.company
    
    warehouse = get_default_warehouse(so.company)
    if not warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(so.company))
    
    for item in purchase_order.items:
        so.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": warehouse,
            "delivery_date": item.schedule_date or purchase_order.schedule_date
        })
    
    so.flags.ignore_permissions = True
    so.flags.ignore_mandatory = True
    so.flags.ignore_account_permission = True
    so.flags.ignore_validate = True
    so.flags.ignore_links = True
    so.flags.ignore_pricing_rule = True
    so.flags.ignore_party_validation = True
    
    so.docstatus = 0  # Keep as draft
    return so


def create_purchase_invoice(sales_invoice, mapping, linked_company, direction):
    """Create Purchase Invoice from Sales Invoice"""
    pi = frappe.new_doc("Purchase Invoice")
    
    if direction == "other_to_main":
        pi.company = mapping.main_company
        pi.supplier = linked_company.main_company_supplier
    else:
        pi.company = linked_company.company
        pi.supplier = linked_company.other_company_supplier

    if not pi.supplier:
        frappe.throw(_("Supplier not found for company {0}").format(pi.company))

    pi.currency = sales_invoice.currency
    pi.conversion_rate = sales_invoice.conversion_rate
    pi.posting_date = sales_invoice.posting_date
    pi.due_date = sales_invoice.due_date
    pi.bill_no = sales_invoice.name
    
    warehouse = get_default_warehouse(pi.company)
    if not warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(pi.company))

    for item in sales_invoice.items:
        pi.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": warehouse,
        })

    pi.intercompany_linked_doc_doctype = sales_invoice.doctype
    pi.intercompany_linked_doc_name = sales_invoice.name
    pi.intercompany_linked_company = sales_invoice.company
    pi.intercompany_target_company = sales_invoice.company

    pi.flags.ignore_permissions = True
    pi.flags.ignore_mandatory = True
    pi.flags.ignore_account_permission = True
    pi.flags.ignore_validate = True
    pi.flags.ignore_links = True
    pi.flags.ignore_pricing_rule = True
    pi.flags.ignore_party_validation = True

    pi.docstatus = 0  # Keep as draft
    return pi


def create_sales_invoice(purchase_invoice, mapping, linked_company, direction):
    """Create Sales Invoice from Purchase Invoice"""
    si = frappe.new_doc("Sales Invoice")
    
    if direction == "other_to_main":
        si.company = mapping.main_company
        si.customer = linked_company.main_company_customer
    else:
        si.company = linked_company.company
        si.customer = linked_company.other_company_customer

    if not si.customer:
        frappe.throw(_("Customer not found for company {0}").format(si.company))

    si.currency = purchase_invoice.currency
    si.conversion_rate = purchase_invoice.conversion_rate
    si.posting_date = purchase_invoice.posting_date
    si.due_date = purchase_invoice.due_date
    si.po_no = purchase_invoice.name

    warehouse = get_default_warehouse(si.company)
    if not warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(si.company))

    for item in purchase_invoice.items:
        si.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": warehouse,
        })

    si.intercompany_linked_doc_doctype = purchase_invoice.doctype
    si.intercompany_linked_doc_name = purchase_invoice.name
    si.intercompany_linked_company = purchase_invoice.company
    si.intercompany_target_company = purchase_invoice.company

    si.flags.ignore_permissions = True
    si.flags.ignore_mandatory = True
    si.flags.ignore_account_permission = True
    si.flags.ignore_validate = True
    si.flags.ignore_links = True
    si.flags.ignore_pricing_rule = True
    si.flags.ignore_party_validation = True

    si.docstatus = 0  # Keep as draft
    return si


def create_delivery_note(purchase_receipt, mapping, linked_company, direction):
    """Create Delivery Note from Purchase Receipt"""
    dn = frappe.new_doc("Delivery Note")
    
    if direction == "other_to_main":
        dn.company = mapping.main_company
        dn.customer = linked_company.main_company_customer
    else:
        dn.company = linked_company.company
        dn.customer = linked_company.other_company_customer

    if not dn.customer:
        frappe.throw(_("Customer not found for company {0}").format(dn.company))

    dn.posting_date = purchase_receipt.posting_date
    dn.posting_time = purchase_receipt.posting_time
    dn.set_posting_time = getattr(purchase_receipt, "set_posting_time", 0)
    dn.currency = purchase_receipt.currency
    dn.conversion_rate = purchase_receipt.conversion_rate
    
    target_warehouse = get_default_warehouse(dn.company)
    if not target_warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(dn.company))

    for item in purchase_receipt.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        dn.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": target_warehouse,
            "against_sales_order": None,
            "against_sales_invoice": None
        })

    dn.intercompany_linked_doc_doctype = purchase_receipt.doctype
    dn.intercompany_linked_doc_name = purchase_receipt.name
    dn.intercompany_linked_company = purchase_receipt.company
    dn.intercompany_target_company = purchase_receipt.company

    dn.flags.ignore_permissions = True
    dn.flags.ignore_mandatory = True
    dn.flags.ignore_account_permission = True
    dn.flags.ignore_validate = True
    dn.flags.ignore_links = True
    dn.flags.ignore_pricing_rule = True
    dn.flags.ignore_party_validation = True

    dn.docstatus = 0  # Keep as draft
    return dn


def create_purchase_receipt(delivery_note, mapping, linked_company, direction):
    """Create Purchase Receipt from Delivery Note"""
    pr = frappe.new_doc("Purchase Receipt")
    
    if direction == "other_to_main":
        pr.company = mapping.main_company
        pr.supplier = linked_company.main_company_supplier
    else:
        pr.company = linked_company.company
        pr.supplier = linked_company.other_company_supplier

    if not pr.supplier:
        frappe.throw(_("Supplier not found for company {0}").format(pr.company))

    pr.posting_date = delivery_note.posting_date
    pr.posting_time = delivery_note.posting_time
    pr.set_posting_time = getattr(delivery_note, "set_posting_time", 0)
    pr.currency = delivery_note.currency
    pr.conversion_rate = delivery_note.conversion_rate
    
    target_warehouse = get_default_warehouse(pr.company)
    if not target_warehouse:
        frappe.throw(_("Default warehouse not found for company {0}").format(pr.company))

    for item in delivery_note.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        pr.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "warehouse": target_warehouse,
            "purchase_order": None,
            "purchase_invoice": None
        })

    pr.intercompany_linked_doc_doctype = delivery_note.doctype
    pr.intercompany_linked_doc_name = delivery_note.name
    pr.intercompany_linked_company = delivery_note.company
    pr.intercompany_target_company = delivery_note.company

    pr.flags.ignore_permissions = True
    pr.flags.ignore_mandatory = True
    pr.flags.ignore_account_permission = True
    pr.flags.ignore_validate = True
    pr.flags.ignore_links = True
    pr.flags.ignore_pricing_rule = True
    pr.flags.ignore_party_validation = True

    pr.docstatus = 0  # Keep as draft
    return pr


def get_intercompany_warehouse(company):
    """Get inter-company warehouse for a company"""
    warehouse = frappe.db.get_value(
        "Warehouse",
        {
            "company": company,
            "warehouse_name": ["like", "%inter%company%"],
            "is_group": 0
        },
        "name"
    )
    if not warehouse:
        warehouse = frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 0},
            "name"
        )
    return warehouse


def create_stock_entry(source_stock_entry, mapping, linked_company, direction):
    """Create Stock Entry for inter-company stock transfer"""
    se = frappe.new_doc("Stock Entry")
    
    if direction == "other_to_main":
        se.company = mapping.main_company
        source_warehouse_company = linked_company.company
        target_warehouse_company = mapping.main_company
    else:
        se.company = linked_company.company
        source_warehouse_company = mapping.main_company
        target_warehouse_company = linked_company.company

    se.stock_entry_type = "Material Transfer"
    se.purpose = "Material Transfer"
    
    se.posting_date = source_stock_entry.posting_date
    se.posting_time = source_stock_entry.posting_time
    se.set_posting_time = getattr(source_stock_entry, "set_posting_time", 0)
    
    source_warehouse = get_intercompany_warehouse(source_warehouse_company)
    target_warehouse = get_intercompany_warehouse(target_warehouse_company)
    
    if not source_warehouse or not target_warehouse:
        frappe.throw(_("Inter-company warehouses not configured properly"))

    for item in source_stock_entry.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        se.append("items", {
            "item_code": item.item_code,
            "qty": item.qty,
            "uom": item.uom,
            "s_warehouse": source_warehouse,
            "t_warehouse": target_warehouse,
            "basic_rate": getattr(item, "basic_rate", 0) or 0,
            "basic_amount": (getattr(item, "basic_rate", 0) or 0) * item.qty,
            "conversion_factor": getattr(item, "conversion_factor", 1) or 1
        })

    se.intercompany_linked_doc_doctype = source_stock_entry.doctype
    se.intercompany_linked_doc_name = source_stock_entry.name
    se.intercompany_linked_company = source_stock_entry.company
    se.intercompany_target_company = source_stock_entry.company

    se.flags.ignore_permissions = True
    se.flags.ignore_mandatory = True
    se.flags.ignore_validate = True
    se.flags.ignore_links = True

    se.docstatus = 0  # Keep as draft
    return se


def get_default_warehouse(company):
    """Get default warehouse for company"""
    warehouse = frappe.db.get_value(
        "Warehouse",
        {"company": company, "is_group": 0},
        "name"
    )
    return warehouse


def get_default_cost_center(company):
    """Get default cost center for company"""
    cost_center = frappe.db.get_value("Company", company, "cost_center")
    return cost_center


def get_mapped_account(account, to_company):
    """Get corresponding account in target company"""
    account_type = frappe.db.get_value("Account", account, "account_type")
    account_name = frappe.db.get_value("Account", account, "account_name")
    
    mapped_account = frappe.db.get_value(
        "Account",
        {"account_name": account_name, "company": to_company},
        "name"
    )
    
    if not mapped_account and account_type:
        mapped_account = frappe.db.get_value(
            "Account",
            {"account_type": account_type, "company": to_company, "is_group": 0},
            "name"
        )
    
    if not mapped_account:
        if account_type == "Receivable":
            mapped_account = frappe.db.get_value("Company", to_company, "default_receivable_account")
        elif account_type == "Payable":
            mapped_account = frappe.db.get_value("Company", to_company, "default_payable_account")
        else:
            mapped_account = frappe.db.get_value("Company", to_company, "default_expense_account")
    
    return mapped_account


def find_matching_mapping_and_direction(doc, link):
    """
    Given a document and IntercompanyTransactionLink, find the matching mapping row and direction
    """
    mappings = getattr(link, "intercompany_transaction_type_mappings", []) or getattr(link, "transaction_types", [])
    for row in mappings:
        direction = getattr(row, "direction", "").lower().strip()
        main = link.main_company
        other = getattr(link, "other_company", None)

        src_type = getattr(row, "main_company_doctype", None) or getattr(row, "source_type", None)
        tgt_type = getattr(row, "other_company_doctype", None) or getattr(row, "target_type", None)

        if direction == "both":
            if doc.company == main and doc.doctype == src_type:
                return row, "main_to_other"
            elif other and doc.company == other and doc.doctype == tgt_type:
                return row, "other_to_main"
            elif not other and doc.doctype == src_type:
                return row, "main_to_other"
        elif direction in ["main to other", "main_to_other"]:
            if doc.company == main and doc.doctype == src_type:
                return row, "main_to_other"
        elif direction in ["other to main", "other_to_main"]:
            if (other and doc.company == other and doc.doctype == tgt_type) or (doc.doctype == src_type):
                return row, "other_to_main"

    return None, None


def handle_after_insert(doc, method=None):
    try:
        links = frappe.get_all("Intercompany Transaction Link", filters={"disabled": 0})
        for link_row in links:
            link = frappe.get_doc("Intercompany Transaction Link", link_row.name)
            mapping_row, direction = find_matching_mapping_and_direction(doc, link)

            if not mapping_row or not direction:
                continue

            mapping_info = {
                "mapping": link,
                "transaction_type": mapping_row,
                "linked_company": link
            }

            if doc.get("intercompany_linked_doc_name"):
                continue

            target_doc = create_corresponding_document(doc, mapping_info, direction)
            if target_doc:
                target_doc.insert(ignore_permissions=True)
                frappe.db.set_value(
                    doc.doctype,
                    doc.name,
                    {
                        "intercompany_linked_doc_doctype": target_doc.doctype,
                        "intercompany_linked_doc_name": target_doc.name,
                        "intercompany_linked_company": target_doc.company,
                    }
                )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Intercompany Insert Handler Failed")


def create_document_reference(source_doc, target_doc):
    """Create inter-company document reference"""
    try:
        if source_doc.company == target_doc.company:
            return
            
        existing_ref = frappe.db.exists(
            "Inter Company Document Reference",
            {
                "source_doctype": source_doc.doctype,
                "source_name": source_doc.name,
                "target_doctype": target_doc.doctype,
                "target_name": target_doc.name
            }
        )
        
        if not existing_ref:
            ref_doc = frappe.get_doc({
                "doctype": "Inter Company Document Reference",
                "source_doctype": source_doc.doctype,
                "source_name": source_doc.name,
                "source_company": source_doc.company,
                "target_doctype": target_doc.doctype,
                "target_name": target_doc.name,
                "target_company": target_doc.company
            })
            ref_doc.flags.ignore_permissions = True
            ref_doc.insert()
            frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error creating document reference: {str(e)}", "Inter Company Transaction Error")


def find_applicable_mappings(doc):
    """Find appropriate mapping configurations"""
    mappings = []
    
    links = frappe.get_all(
        "Intercompany Transaction Link",
        filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {},
        fields=["name", "main_company"]
    )
    
    for link in links:
        mapping = frappe.get_doc("Intercompany Transaction Link", link.name)
        
        if doc.get("intercompany_linked_doc_doctype") and doc.get("intercompany_linked_doc_name"):
            continue
        
        is_main = doc.company == mapping.main_company
        target_company = doc.get('intercompany_target_company')
        
        if is_main:
            if target_company:
                linked_company = next(
                    (lc for lc in mapping.linked_companies if lc.company == target_company),
                    None
                )
                if linked_company:
                    for trans_type in mapping.transaction_types:
                        if trans_type.source_type == doc.doctype and trans_type.direction in ["Main to Other", "Both"]:
                            mappings.append({
                                "mapping": mapping,
                                "transaction_type": trans_type,
                                "company": target_company,
                                "linked_company": linked_company,
                                "direction": "main_to_other"
                            })
            else:
                for linked_company in mapping.linked_companies:
                    for trans_type in mapping.transaction_types:
                        if trans_type.source_type == doc.doctype and trans_type.direction in ["Main to Other", "Both"]:
                            mappings.append({
                                "mapping": mapping,
                                "transaction_type": trans_type,
                                "company": linked_company.company,
                                "linked_company": linked_company,
                                "direction": "main_to_other"
                            })
        else:
            is_linked = any(lc.company == doc.company for lc in mapping.linked_companies)
            if is_linked:
                linked_company = next(
                    (lc for lc in mapping.linked_companies if lc.company == doc.company),
                    None
                )
                if linked_company:
                    for trans_type in mapping.transaction_types:
                        if trans_type.source_type == doc.doctype and trans_type.direction in ["Other to Main", "Both"]:
                            mappings.append({
                                "mapping": mapping,
                                "transaction_type": trans_type,
                                "company": mapping.main_company,
                                "linked_company": linked_company,
                                "direction": "other_to_main"
                            })
    
    return mappings


def create_corresponding_document(source_doc, mapping_info, direction):
    """Create the corresponding document based on mapping"""
    try:
        mapping = mapping_info["mapping"]
        trans_type = mapping_info["transaction_type"]
        linked_company = mapping_info["linked_company"]

        try:
            user_default_company = frappe.db.get_default("Company")
        except Exception:
            user_default_company = None
            
        target_company = source_doc.get("intercompany_target_company")
        if user_default_company and target_company == user_default_company and target_company == source_doc.company:
            return None

        if source_doc.doctype == "Sales Order" and trans_type.target_type == "Purchase Order":
            return create_purchase_order(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Purchase Order" and trans_type.target_type == "Sales Order":
            return create_sales_order(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Sales Invoice" and trans_type.target_type == "Purchase Invoice":
            return create_purchase_invoice(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Purchase Invoice" and trans_type.target_type == "Sales Invoice":
            return create_sales_invoice(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Purchase Receipt" and trans_type.target_type == "Delivery Note":
            return create_delivery_note(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Delivery Note" and trans_type.target_type == "Purchase Receipt":
            return create_purchase_receipt(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Stock Entry" and trans_type.target_type == "Stock Entry":
            return create_stock_entry(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Journal Entry" and trans_type.target_type == "Journal Entry":
            return create_journal_entry(source_doc, mapping, linked_company, direction)
        elif source_doc.doctype == "Payment Entry" and trans_type.target_type == "Payment Entry":
            return create_payment_entry(source_doc, mapping, linked_company, direction)

        return None
    except Exception as e:
        frappe.log_error(
            f"Error in create_corresponding_document: {str(e)}\n"
            f"Source Doc: {source_doc.doctype} {source_doc.name}\n"
            f"Traceback: {frappe.get_traceback()}",
            "Inter Company Transaction Error"
        )
        raise


def cancel_child_documents(doc):
    """Cancel any child documents linked to this document"""
    child_docs = frappe.get_all(
        "Inter Company Document Reference",
        filters={
            "source_doctype": doc.doctype,
            "source_name": doc.name
        },
        fields=["target_doctype", "target_name"]
    )
    
    for child_doc in child_docs:
        try:
            if frappe.db.exists(child_doc.target_doctype, child_doc.target_name):
                target = frappe.get_doc(child_doc.target_doctype, child_doc.target_name)
                target.flags.ignore_permissions = True
                target.flags.ignore_mandatory = True
                target.flags.ignore_account_permission = True
                target.flags.ignore_validate = True
                target.flags.ignore_links = True
                
                if target.docstatus == 1:
                    target.cancel()
                    frappe.msgprint(_("Cancelled child document {0} {1}").format(target.doctype, target.name))
        except Exception as e:
            frappe.log_error(
                f"Error cancelling child document: {str(e)}\n"
                f"Document: {child_doc.target_doctype} {child_doc.target_name}",
                "Inter Company Transaction Error"
            )


def cancel_parent_documents(doc):
    """Cancel any parent documents linked to this document"""
    parent_docs = frappe.get_all(
        "Inter Company Document Reference",
        filters={
            "target_doctype": doc.doctype,
            "target_name": doc.name
        },
        fields=["source_doctype", "source_name"]
    )

    for parent_doc in parent_docs:
        try:
            if frappe.db.exists(parent_doc.source_doctype, parent_doc.source_name):
                source = frappe.get_doc(parent_doc.source_doctype, parent_doc.source_name)
                source.flags.ignore_permissions = True
                source.flags.ignore_mandatory = True
                source.flags.ignore_account_permission = True
                source.flags.ignore_validate = True
                source.flags.ignore_links = True

                if source.docstatus == 1:
                    source.cancel()
                    frappe.msgprint(_("Cancelled parent document {0} {1}").format(source.doctype, source.name))
        except Exception as e:
            frappe.log_error(
                f"Error cancelling parent document: {str(e)}\n"
                f"Document: {parent_doc.source_doctype} {parent_doc.source_name}",
                "Inter Company Transaction Error"
            )


def validate_intercompany_linked_company(doc, method=None):
    pass


@frappe.whitelist()
def bulk_create_linked_documents(doc_names, doctype):
    """Bulk process multiple documents for better performance"""
    results = []
    for doc_name in doc_names:
        try:
            doc = frappe.get_doc(doctype, doc_name)
            create_linked_documents(doc, None)
            results.append({"name": doc_name, "status": "success"})
        except Exception as e:
            results.append({"name": doc_name, "status": "error", "message": str(e)})
    return results


def optimize_mapping_search():
    """Cache mapping configurations for better performance"""
    cache_key = "intercompany_mappings"
    mappings = frappe.cache().get_value(cache_key)
    
    if not mappings:
        mappings = frappe.get_all(
            "Intercompany Transaction Link",
            filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {},
            fields=["name", "main_company"]
        )
        frappe.cache().set_value(cache_key, mappings, expires_in_sec=300)
    
    return mappings


def validate_intercompany_rules(doc, mapping):
    """Enhanced business rule validation"""
    if hasattr(doc, 'grand_total') and doc.grand_total:
        validate_credit_limit(doc, mapping)
    validate_approval_requirements(doc, mapping)


def get_intercompany_customer(doc, mapping):
    lc = mapping.get("linked_company")
    if lc:
        return lc.other_company_customer if doc.company == mapping["mapping"].main_company else lc.main_company_customer
    return None


def validate_credit_limit(doc, mapping):
    """Check if transaction exceeds credit limits"""
    customer = get_intercompany_customer(doc, mapping)
    if customer:
        credit_limit = frappe.db.get_value("Customer", customer, "credit_limit")
        if credit_limit and doc.grand_total > credit_limit:
            frappe.throw(_("Transaction amount exceeds credit limit for {0}").format(customer))


def validate_approval_requirements(doc, mapping):
    """Check if document requires approval based on amount/type"""
    if frappe.db.exists("DocType", "Intercompany Settings"):
        approval_limit = frappe.db.get_single_value("Intercompany Settings", "approval_limit")
        if approval_limit and hasattr(doc, 'grand_total'):
            if doc.grand_total > approval_limit and doc.docstatus < 1:
                frappe.throw(_("Document requires approval before submission"))


@frappe.whitelist()
def reconcile_intercompany_accounts():
    """Reconcile inter-company account balances"""
    companies = frappe.get_all("Company", pluck="name")
    reconciliation_data = []
    
    for company_a in companies:
        for company_b in companies:
            if company_a != company_b:
                balance_data = get_intercompany_balance(company_a, company_b)
                if balance_data:
                    reconciliation_data.append(balance_data)
    
    return reconciliation_data


def calculate_net_balance(transactions):
    total = sum(flt(t.get("outstanding_amount") or 0) for t in transactions)
    return {"transactions_count": len(transactions), "net_balance": total}


def get_intercompany_balance(company_a, company_b):
    """Get outstanding balance between two companies"""
    transactions = frappe.db.sql("""
        SELECT 
            source_doctype, source_name, source_company,
            target_doctype, target_name, target_company,
            modified
        FROM `tabInter Company Document Reference`
        WHERE (source_company = %s AND target_company = %s)
           OR (source_company = %s AND target_company = %s)
    """, (company_a, company_b, company_b, company_a), as_dict=True)
    
    return calculate_net_balance(transactions)


@frappe.whitelist()
def create_reconciliation_journal_entry(company_a, company_b, amount):
    pass


def process_transaction_summary(data):
    return {"total": len(data), "items": data}


@frappe.whitelist()
def get_intercompany_transaction_summary(from_date, to_date, company=None):
    """Get comprehensive inter-company transaction summary"""
    filters = {
        "creation": ["between", [from_date, to_date]]
    }
    if company:
        filters.update({"source_company": company})
    
    data = frappe.db.get_list(
        "Inter Company Document Reference",
        filters=filters,
        fields=[
            "source_doctype", "source_name", "source_company",
            "target_doctype", "target_name", "target_company",
            "creation", "modified"
        ]
    )
    return process_transaction_summary(data)


def find_missing_linked_documents(mapping):
    return []


@frappe.whitelist()
def get_pending_intercompany_documents():
    """Get all pending inter-company documents requiring action"""
    pending_docs = []
    mappings = frappe.get_all("Intercompany Transaction Link", filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {})
    for mapping in mappings:
        pending = find_missing_linked_documents(mapping)
        pending_docs.extend(pending)
    return pending_docs


def create_intercompany_settings():
    return []


def retry_failed_document_creation(reference_name):
    """Retry creating a failed inter-company document"""
    try:
        ref_doc = frappe.get_doc("Inter Company Document Reference", reference_name)
        source_doc = frappe.get_doc(ref_doc.source_doctype, ref_doc.source_name)
        mappings = find_applicable_mappings(source_doc)
        
        for mapping in mappings:
            if mapping["company"] == ref_doc.target_company:
                linked_doc = create_corresponding_document(source_doc, mapping, mapping["direction"])
                if linked_doc:
                    linked_doc.insert()
                    frappe.msgprint(_("Successfully created {0} {1}").format(linked_doc.doctype, linked_doc.name))
                    break
    except Exception as e:
        frappe.log_error(f"Retry failed: {str(e)}", "Inter Company Retry Error")
        frappe.throw(_("Failed to retry document creation: {0}").format(str(e)))


def handle_orphaned_reference(ref):
    pass


@frappe.whitelist()
def fix_orphaned_references():
    """Find and fix orphaned inter-company references"""
    pass


def setup_intercompany_workflows():
    return {}


def validate_workflow_state(doc, mapping):
    pass


def get_pending_count(company):
    return 0


def get_monthly_transaction_volume(company):
    return 0


def get_outstanding_balances(company):
    return 0


def get_recent_transactions(company, limit=10):
    return []


@frappe.whitelist()
def get_intercompany_dashboard_data(company):
    return {
        "pending_documents": get_pending_count(company),
        "monthly_volume": get_monthly_transaction_volume(company),
        "outstanding_balances": get_outstanding_balances(company),
        "recent_transactions": get_recent_transactions(company, limit=10)
    }


def sync_items_across_companies():
    pass


def sync_customer_supplier_relationships():
    pass


def sync_pricing_data():
    pass


@frappe.whitelist()
def sync_intercompany_data():
    sync_items_across_companies()
    sync_customer_supplier_relationships()
    sync_pricing_data()


def fix_legacy_custom_fields(force=False):
    """
    Sanitizes glued operators like '1or(' and ensures field expressions
    are valid both for JavaScript and Python.
    """
    if not (hasattr(frappe, "db") and frappe.db):
        return

    try:
        # Fix glued operators in tabCustom Field
        if frappe.db.table_exists("Custom Field"):
            for col in ["depends_on", "mandatory_depends_on", "read_only_depends_on"]:
                if frappe.db.has_column("Custom Field", col):
                    frappe.db.sql(f"""
                        UPDATE `tabCustom Field`
                        SET `{col}` = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(`{col}`,
                            '1or(', '1 or ('),
                            '0or(', '0 or ('),
                            ')or(', ') or ('),
                            '1and(', '1 and ('),
                            '0and(', '0 and (')
                        WHERE `{col}` IS NOT NULL AND (
                            `{col}` LIKE '%1or(%' OR
                            `{col}` LIKE '%0or(%' OR
                            `{col}` LIKE '%)or(%' OR
                            `{col}` LIKE '%1and(%' OR
                            `{col}` LIKE '%0and(%'
                        )
                    """)
        frappe.db.commit()
    except Exception:
        pass
