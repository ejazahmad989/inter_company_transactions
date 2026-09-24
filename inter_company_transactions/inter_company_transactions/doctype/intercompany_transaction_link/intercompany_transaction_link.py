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
            if linked_company.main_company_customer and not linked_company.other_company_supplier:
                frappe.throw(_("Other Company Supplier is required when Main Company Customer is set for {0}").format(linked_company.company))
            
            if linked_company.main_company_supplier and not linked_company.other_company_customer:
                frappe.throw(_("Other Company Customer is required when Main Company Supplier is set for {0}").format(linked_company.company))


def create_linked_documents(doc, method=None):
    """Create corresponding documents in all linked companies"""
    if doc.get("intercompany_linked_doc_doctype") or doc.get("intercompany_linked_doc_name"):
        return
    
    mappings = find_applicable_mappings(doc)
    if not mappings:
        return
    
    for i, mapping in enumerate(mappings):
        try:
            direction = mapping.get("direction")
            if not direction:
                is_main_to_other = (doc.company == mapping["mapping"].main_company)
                direction = "main_to_other" if is_main_to_other else "other_to_main"
            
            validate_required_parties(doc, mapping)
            
            linked_doc = create_corresponding_document(doc, mapping, direction)
            
            if linked_doc:
                linked_doc.intercompany_linked_doc_doctype = doc.doctype
                linked_doc.intercompany_linked_doc_name = doc.name
                linked_doc.intercompany_linked_company = doc.company
                linked_doc.intercompany_target_company = doc.company
                
                linked_doc.flags.ignore_permissions = True
                linked_doc.flags.ignore_mandatory = True
                linked_doc.insert(ignore_permissions=True, ignore_mandatory=True)
                
                create_document_reference(doc, linked_doc)
                
                frappe.msgprint(_("Created draft {0} {1} in company {2}").format(
                    linked_doc.doctype, linked_doc.name, linked_doc.company
                ))
            
        except Exception as e:
            frappe.log_error(f"Error in intercompany creation for {doc.doctype} {doc.name}: {str(e)}\n{frappe.get_traceback()}", "Inter Company Transaction Error")
            frappe.msgprint(_("Notice for linked company {0}: {1}").format(
                mapping.get('company', ''), str(e)
            ))


def cancel_linked_documents(doc, method=None):
    """Cancel corresponding documents in all linked companies - BIDIRECTIONAL"""
    if not hasattr(doc, 'company') or not doc.company:
        return
    
    if doc.flags.get("intercompany_auto_cancel"):
        return
    
    if not frappe.db.exists("DocType", "Inter Company Document Reference"):
        return
        
    all_related_docs = []
    
    # Documents where current doc is the SOURCE
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
        for ld in linked_docs:
            all_related_docs.append({
                "doctype": ld.target_doctype,
                "name": ld.target_name,
                "company": ld.target_company,
                "relationship": "target"
            })
    except Exception as e:
        frappe.logger().error(f"Error finding linked documents (as source): {str(e)}")
    
    # Documents where current doc is the TARGET  
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
        for rl in reverse_links:
            all_related_docs.append({
                "doctype": rl.source_doctype,
                "name": rl.source_name,
                "company": rl.source_company,
                "relationship": "source"
            })
    except Exception as e:
        frappe.logger().error(f"Error finding reverse links (as target): {str(e)}")
    
    def cancel_doc(doctype, docname, company=None, relationship=None):
        try:
            if not frappe.db.exists(doctype, docname):
                return False
                
            target_doc = frappe.get_doc(doctype, docname)
            if target_doc.docstatus != 1:
                return False
            
            target_doc.flags.ignore_permissions = True
            target_doc.flags.ignore_mandatory = True
            target_doc.flags.ignore_account_permission = True
            target_doc.flags.ignore_validate = True
            target_doc.flags.ignore_links = True
            target_doc.flags.ignore_validate_update_after_submit = True
            target_doc.flags.ignore_workflow = True
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
                f"Document: {related_doc['doctype']} {related_doc['name']}",
                "Inter Company Transaction Error"
            )


def find_applicable_mappings(doc):
    """
    Finds matching mapping configurations for the document.
    Handles bidirectional document pairs (e.g. Sales Invoice <-> Purchase Invoice,
    Sales Order <-> Purchase Order, Delivery Note <-> Purchase Receipt, Quotation <-> Supplier Quotation,
    Stock Entry <-> Stock Entry, Journal Entry <-> Journal Entry, Payment Entry <-> Payment Entry).
    """
    mappings = []
    
    links = frappe.get_all(
        "Intercompany Transaction Link",
        filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {},
        fields=["name", "main_company"]
    )
    
    for link_entry in links:
        link = frappe.get_doc("Intercompany Transaction Link", link_entry.name)
        
        is_main = (doc.company == link.main_company)
        is_linked = any(lc.company == doc.company for lc in link.linked_companies)
        
        if not is_main and not is_linked:
            continue
            
        target_company_hint = doc.get("intercompany_target_company")
        
        if is_main:
            # Document originates from Main Company -> Target is Linked Company
            candidate_linked_companies = []
            if target_company_hint:
                matched_lc = next((lc for lc in link.linked_companies if lc.company == target_company_hint), None)
                if matched_lc:
                    candidate_linked_companies = [matched_lc]
            
            if not candidate_linked_companies:
                # Try to identify target company by party in Main Company
                if hasattr(doc, "customer") and doc.customer:
                    matched_lc = next((lc for lc in link.linked_companies if lc.main_company_customer == doc.customer), None)
                    if matched_lc:
                        candidate_linked_companies = [matched_lc]
                elif hasattr(doc, "supplier") and doc.supplier:
                    matched_lc = next((lc for lc in link.linked_companies if lc.main_company_supplier == doc.supplier), None)
                    if matched_lc:
                        candidate_linked_companies = [matched_lc]
            
            if not candidate_linked_companies:
                candidate_linked_companies = list(link.linked_companies)
            
            for linked_company in candidate_linked_companies:
                for trans_type in link.transaction_types:
                    target_dt = resolve_target_doctype(doc.doctype, trans_type, direction="main_to_other")
                    if target_dt:
                        mappings.append({
                            "mapping": link,
                            "transaction_type": trans_type,
                            "company": linked_company.company,
                            "linked_company": linked_company,
                            "direction": "main_to_other",
                            "target_doctype": target_dt
                        })
                        
        else:
            # Document originates from Linked Company -> Target is Main Company
            linked_company = next((lc for lc in link.linked_companies if lc.company == doc.company), None)
            if linked_company:
                for trans_type in link.transaction_types:
                    target_dt = resolve_target_doctype(doc.doctype, trans_type, direction="other_to_main")
                    if target_dt:
                        mappings.append({
                            "mapping": link,
                            "transaction_type": trans_type,
                            "company": link.main_company,
                            "linked_company": linked_company,
                            "direction": "other_to_main",
                            "target_doctype": target_dt
                        })
                        
    return mappings


def resolve_target_doctype(source_doctype, trans_type, direction):
    """
    Resolves the target DocType given the source DocType, mapping rule, and transaction flow direction.
    Allows bidirectional pairs configured in either direction.
    """
    rule_src = trans_type.source_type
    rule_tgt = trans_type.target_type
    rule_dir = (trans_type.direction or "").strip()
    
    if direction == "main_to_other":
        if rule_src == source_doctype and rule_dir in ["Main to Other", "Both", ""]:
            return rule_tgt
        if rule_tgt == source_doctype and rule_dir in ["Other to Main", "Both"]:
            return rule_src
            
    elif direction == "other_to_main":
        if rule_src == source_doctype and rule_dir in ["Other to Main", "Both", ""]:
            return rule_tgt
        if rule_tgt == source_doctype and rule_dir in ["Main to Other", "Both"]:
            return rule_src
            
    return None


def validate_required_parties(doc, mapping):
    """Validate that required parties are configured based on target transaction type"""
    linked_company = mapping["linked_company"]
    target_doctype = mapping.get("target_doctype")
    direction = mapping.get("direction", "main_to_other")
    
    if target_doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]:
        if direction == "other_to_main":
            if not linked_company.main_company_supplier:
                frappe.throw(_("Main Company Supplier is required for linked company {0}").format(linked_company.company))
        else:
            if not linked_company.other_company_supplier:
                frappe.throw(_("Other Company Supplier is required for linked company {0}").format(linked_company.company))
                
    elif target_doctype in ["Sales Order", "Sales Invoice", "Delivery Note", "Quotation"]:
        if direction == "other_to_main":
            if not linked_company.main_company_customer:
                frappe.throw(_("Main Company Customer is required for linked company {0}").format(linked_company.company))
        else:
            if not linked_company.other_company_customer:
                frappe.throw(_("Other Company Customer is required for linked company {0}").format(linked_company.company))
                
    elif target_doctype in ["Journal Entry", "Payment Entry"]:
        if not linked_company.main_company_customer:
            frappe.throw(_("Main Company Customer is required for {0}").format(linked_company.company))
        if not linked_company.other_company_supplier:
            frappe.throw(_("Other Company Supplier is required for {0}").format(linked_company.company))


def get_intercompany_exchange_rate(from_currency, to_currency, transaction_date=None):
    """
    Safely get the exchange rate from from_currency to to_currency on transaction_date.
    Returns 1.0 if currencies are equal or cannot be resolved.
    """
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0

    rate = None
    # 1. Try ERPNext setup utility
    try:
        from erpnext.setup.utils import get_exchange_rate
        rate = get_exchange_rate(from_currency, to_currency, transaction_date or nowdate())
    except Exception:
        pass

    # 2. Try Currency Exchange DocType
    if not rate and frappe.db and hasattr(frappe.db, "exists") and frappe.db.exists("DocType", "Currency Exchange"):
        try:
            rate = frappe.db.get_value(
                "Currency Exchange",
                {"from_currency": from_currency, "to_currency": to_currency},
                "exchange_rate",
                order_by="date desc"
            )
            if not rate:
                # Inverted rate
                inv = frappe.db.get_value(
                    "Currency Exchange",
                    {"from_currency": to_currency, "to_currency": from_currency},
                    "exchange_rate",
                    order_by="date desc"
                )
                if inv and flt(inv) > 0:
                    rate = 1.0 / flt(inv)
        except Exception:
            pass

    return flt(rate or 1.0)


def resolve_intercompany_currency_and_rate(source_doc, target_company, party_type=None, party_name=None, date=None):
    """
    Resolve target document currency, conversion_rate, and item rate factor.
    - target_currency: party default currency or source document currency or target company default currency
    - conversion_rate: exchange rate from target_currency to target_company default currency
    - rate_factor: multiplier to convert unit prices from source_currency to target_currency
    """
    target_company_currency = frappe.db.get_value("Company", target_company, "default_currency")
    source_company = getattr(source_doc, "company", None)
    source_company_currency = frappe.db.get_value("Company", source_company, "default_currency") if source_company else None
    source_currency = getattr(source_doc, "currency", None) or source_company_currency or target_company_currency
    
    party_currency = None
    if party_type and party_name and frappe.db.exists(party_type, party_name):
        party_currency = frappe.db.get_value(party_type, party_name, "default_currency")
    
    # Priority: Party designated billing currency -> Source document currency -> Target company currency
    target_currency = party_currency or source_currency or target_company_currency
    
    # ERPNext conversion_rate represents: target_currency -> target_company_currency
    if target_currency == target_company_currency:
        conversion_rate = 1.0
    else:
        conversion_rate = get_intercompany_exchange_rate(target_currency, target_company_currency, date)
        if not conversion_rate or conversion_rate <= 0:
            conversion_rate = 1.0
            
    # rate_factor converts unit prices from source_currency to target_currency
    if source_currency == target_currency:
        rate_factor = 1.0
    else:
        rate_factor = get_intercompany_exchange_rate(source_currency, target_currency, date)
        if not rate_factor or rate_factor <= 0:
            rate_factor = 1.0
            
    return target_currency, conversion_rate, rate_factor


def create_corresponding_document(source_doc, mapping_info, direction):
    """Route document creation by target DocType"""
    mapping = mapping_info["mapping"]
    linked_company = mapping_info["linked_company"]
    target_doctype = mapping_info.get("target_doctype")
    
    if target_doctype == "Sales Invoice":
        return create_sales_invoice(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Purchase Invoice":
        return create_purchase_invoice(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Sales Order":
        return create_sales_order(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Purchase Order":
        return create_purchase_order(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Delivery Note":
        return create_delivery_note(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Purchase Receipt":
        return create_purchase_receipt(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Stock Entry":
        return create_stock_entry(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Journal Entry":
        return create_journal_entry(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Payment Entry":
        return create_payment_entry(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Quotation":
        return create_quotation(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Supplier Quotation":
        return create_supplier_quotation(source_doc, mapping, linked_company, direction)
        
    return None


def create_sales_invoice(source_doc, mapping, linked_company, direction):
    """Create Sales Invoice from Purchase Invoice or other source"""
    si = frappe.new_doc("Sales Invoice")
    
    if direction == "other_to_main":
        si.company = mapping.main_company
        si.customer = linked_company.main_company_customer
    else:
        si.company = linked_company.company
        si.customer = linked_company.other_company_customer

    if not si.customer:
        frappe.throw(_("Customer not mapped for company {0}").format(si.company))

    si.posting_date = getattr(source_doc, "posting_date", None) or nowdate()
    si.due_date = getattr(source_doc, "due_date", None) or si.posting_date
    si.po_no = getattr(source_doc, "bill_no", None) or source_doc.name

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        source_doc, si.company, party_type="Customer", party_name=si.customer, date=si.posting_date
    )
    si.currency = target_currency
    si.conversion_rate = conversion_rate

    warehouse = get_default_warehouse(si.company)
    if not warehouse:
        warehouse = frappe.db.get_value("Warehouse", {"company": si.company, "is_group": 0}, "name")

    debit_to = frappe.db.get_value("Company", si.company, "default_receivable_account")
    if not debit_to and si.customer:
        debit_to = frappe.db.get_value("Party Account", {"parent": si.customer, "company": si.company}, "account")
    if debit_to:
        si.debit_to = debit_to

    default_income_account = frappe.db.get_value("Company", si.company, "default_income_account")
    default_cost_center = get_default_cost_center(si.company)

    for item in getattr(source_doc, "items", []):
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        item_row = {
            "item_code": item.item_code,
            "item_name": getattr(item, "item_name", item.item_code),
            "description": getattr(item, "description", item.item_code),
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
            "cost_center": default_cost_center,
        }
        if warehouse:
            item_row["warehouse"] = warehouse
        if default_income_account:
            item_row["income_account"] = default_income_account
        si.append("items", item_row)

    si.intercompany_linked_doc_doctype = source_doc.doctype
    si.intercompany_linked_doc_name = source_doc.name
    si.intercompany_linked_company = source_doc.company
    si.intercompany_target_company = source_doc.company

    si.flags.ignore_permissions = True
    si.flags.ignore_mandatory = True
    si.flags.ignore_account_permission = True
    si.flags.ignore_validate = True
    si.flags.ignore_links = True
    si.flags.ignore_pricing_rule = True
    si.flags.ignore_party_validation = True

    try:
        si.set_missing_values(for_validate=True)
    except Exception:
        pass

    si.docstatus = 0  # Draft
    return si


def create_purchase_invoice(source_doc, mapping, linked_company, direction):
    """Create Purchase Invoice from Sales Invoice or other source"""
    pi = frappe.new_doc("Purchase Invoice")
    
    if direction == "other_to_main":
        pi.company = mapping.main_company
        pi.supplier = linked_company.main_company_supplier
    else:
        pi.company = linked_company.company
        pi.supplier = linked_company.other_company_supplier

    if not pi.supplier:
        frappe.throw(_("Supplier not mapped for company {0}").format(pi.company))

    pi.posting_date = getattr(source_doc, "posting_date", None) or nowdate()
    pi.due_date = getattr(source_doc, "due_date", None) or pi.posting_date
    pi.bill_no = source_doc.name

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        source_doc, pi.company, party_type="Supplier", party_name=pi.supplier, date=pi.posting_date
    )
    pi.currency = target_currency
    pi.conversion_rate = conversion_rate
    
    warehouse = get_default_warehouse(pi.company)
    if not warehouse:
        warehouse = frappe.db.get_value("Warehouse", {"company": pi.company, "is_group": 0}, "name")

    credit_to = frappe.db.get_value("Company", pi.company, "default_payable_account")
    if not credit_to and pi.supplier:
        credit_to = frappe.db.get_value("Party Account", {"parent": pi.supplier, "company": pi.company}, "account")
    if credit_to:
        pi.credit_to = credit_to

    default_expense_account = frappe.db.get_value("Company", pi.company, "default_expense_account")
    default_cost_center = get_default_cost_center(pi.company)

    for item in getattr(source_doc, "items", []):
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        item_row = {
            "item_code": item.item_code,
            "item_name": getattr(item, "item_name", item.item_code),
            "description": getattr(item, "description", item.item_code),
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
            "cost_center": default_cost_center,
        }
        if warehouse:
            item_row["warehouse"] = warehouse
        if default_expense_account:
            item_row["expense_account"] = default_expense_account
        pi.append("items", item_row)

    pi.intercompany_linked_doc_doctype = source_doc.doctype
    pi.intercompany_linked_doc_name = source_doc.name
    pi.intercompany_linked_company = source_doc.company
    pi.intercompany_target_company = source_doc.company

    pi.flags.ignore_permissions = True
    pi.flags.ignore_mandatory = True
    pi.flags.ignore_account_permission = True
    pi.flags.ignore_validate = True
    pi.flags.ignore_links = True
    pi.flags.ignore_pricing_rule = True
    pi.flags.ignore_party_validation = True

    try:
        pi.set_missing_values(for_validate=True)
    except Exception:
        pass

    pi.docstatus = 0  # Draft
    return pi


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
    
    po.transaction_date = sales_order.transaction_date
    po.schedule_date = getattr(sales_order, "delivery_date", None) or nowdate()
    po.intercompany_target_company = sales_order.company

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        sales_order, po.company, party_type="Supplier", party_name=po.supplier, date=po.transaction_date
    )
    po.currency = target_currency
    po.conversion_rate = conversion_rate
    
    warehouse = get_default_warehouse(po.company)
    if not warehouse:
        warehouse = frappe.db.get_value("Warehouse", {"company": po.company, "is_group": 0}, "name")
    
    for item in sales_order.items:
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        po.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
            "warehouse": warehouse,
            "schedule_date": getattr(item, "delivery_date", None) or po.schedule_date
        })
    
    po.flags.ignore_permissions = True
    po.flags.ignore_mandatory = True
    po.flags.ignore_account_permission = True
    po.flags.ignore_validate = True
    po.flags.ignore_links = True
    po.flags.ignore_pricing_rule = True
    po.flags.ignore_party_validation = True
    
    try:
        po.set_missing_values(for_validate=True)
    except Exception:
        pass
        
    po.docstatus = 0  # Draft
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
    
    so.transaction_date = purchase_order.transaction_date
    so.delivery_date = getattr(purchase_order, "schedule_date", None) or nowdate()
    so.intercompany_target_company = purchase_order.company

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        purchase_order, so.company, party_type="Customer", party_name=so.customer, date=so.transaction_date
    )
    so.currency = target_currency
    so.conversion_rate = conversion_rate
    
    warehouse = get_default_warehouse(so.company)
    if not warehouse:
        warehouse = frappe.db.get_value("Warehouse", {"company": so.company, "is_group": 0}, "name")
    
    for item in purchase_order.items:
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        so.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
            "warehouse": warehouse,
            "delivery_date": getattr(item, "schedule_date", None) or so.delivery_date
        })
    
    so.flags.ignore_permissions = True
    so.flags.ignore_mandatory = True
    so.flags.ignore_account_permission = True
    so.flags.ignore_validate = True
    so.flags.ignore_links = True
    so.flags.ignore_pricing_rule = True
    so.flags.ignore_party_validation = True
    
    try:
        so.set_missing_values(for_validate=True)
    except Exception:
        pass
        
    so.docstatus = 0  # Draft
    return so


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
    dn.posting_time = getattr(purchase_receipt, "posting_time", None)
    dn.set_posting_time = getattr(purchase_receipt, "set_posting_time", 0)

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        purchase_receipt, dn.company, party_type="Customer", party_name=dn.customer, date=dn.posting_date
    )
    dn.currency = target_currency
    dn.conversion_rate = conversion_rate
    
    target_warehouse = get_default_warehouse(dn.company)
    if not target_warehouse:
        target_warehouse = frappe.db.get_value("Warehouse", {"company": dn.company, "is_group": 0}, "name")

    for item in purchase_receipt.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        dn.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
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

    try:
        dn.set_missing_values(for_validate=True)
    except Exception:
        pass

    dn.docstatus = 0  # Draft
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
    pr.posting_time = getattr(delivery_note, "posting_time", None)
    pr.set_posting_time = getattr(delivery_note, "set_posting_time", 0)

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        delivery_note, pr.company, party_type="Supplier", party_name=pr.supplier, date=pr.posting_date
    )
    pr.currency = target_currency
    pr.conversion_rate = conversion_rate
    
    target_warehouse = get_default_warehouse(pr.company)
    if not target_warehouse:
        target_warehouse = frappe.db.get_value("Warehouse", {"company": pr.company, "is_group": 0}, "name")

    for item in delivery_note.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        pr.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate,
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

    try:
        pr.set_missing_values(for_validate=True)
    except Exception:
        pass

    pr.docstatus = 0  # Draft
    return pr


def create_quotation(supplier_quotation, mapping, linked_company, direction):
    """Create Quotation from Supplier Quotation"""
    q = frappe.new_doc("Quotation")
    if direction == "other_to_main":
        q.company = mapping.main_company
        q.party_name = linked_company.main_company_customer
    else:
        q.company = linked_company.company
        q.party_name = linked_company.other_company_customer

    q.quotation_to = "Customer"
    q.transaction_date = getattr(supplier_quotation, "transaction_date", None) or nowdate()

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        supplier_quotation, q.company, party_type="Customer", party_name=q.party_name, date=q.transaction_date
    )
    q.currency = target_currency
    q.conversion_rate = conversion_rate

    for item in supplier_quotation.items:
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        q.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate
        })

    q.intercompany_linked_doc_doctype = supplier_quotation.doctype
    q.intercompany_linked_doc_name = supplier_quotation.name
    q.intercompany_linked_company = supplier_quotation.company
    q.intercompany_target_company = supplier_quotation.company

    q.flags.ignore_permissions = True
    q.flags.ignore_mandatory = True
    try:
        q.set_missing_values(for_validate=True)
    except Exception:
        pass
    q.docstatus = 0
    return q


def create_supplier_quotation(quotation, mapping, linked_company, direction):
    """Create Supplier Quotation from Quotation"""
    sq = frappe.new_doc("Supplier Quotation")
    if direction == "other_to_main":
        sq.company = mapping.main_company
        sq.supplier = linked_company.main_company_supplier
    else:
        sq.company = linked_company.company
        sq.supplier = linked_company.other_company_supplier

    sq.transaction_date = getattr(quotation, "transaction_date", None) or nowdate()

    # Accurate multi-currency and exchange rate resolution
    target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
        quotation, sq.company, party_type="Supplier", party_name=sq.supplier, date=sq.transaction_date
    )
    sq.currency = target_currency
    sq.conversion_rate = conversion_rate

    for item in quotation.items:
        unit_rate = flt(getattr(item, "rate", 0)) * flt(rate_factor)
        sq.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "rate": unit_rate
        })

    sq.intercompany_linked_doc_doctype = quotation.doctype
    sq.intercompany_linked_doc_name = quotation.name
    sq.intercompany_linked_company = quotation.company
    sq.intercompany_target_company = quotation.company

    sq.flags.ignore_permissions = True
    sq.flags.ignore_mandatory = True
    try:
        sq.set_missing_values(for_validate=True)
    except Exception:
        pass
    sq.docstatus = 0
    return sq


def get_intercompany_warehouse(company):
    """Get inter-company / transit warehouse for a company"""
    warehouse = frappe.db.get_value(
        "Warehouse",
        {
            "company": company,
            "is_intercompany_warehouse": 1,
            "is_group": 0
        },
        "name"
    )
    if not warehouse:
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
            {
                "company": company,
                "warehouse_name": ["like", "%transit%"],
                "is_group": 0
            },
            "name"
        )
    if not warehouse:
        warehouse = get_default_warehouse(company)
    return warehouse


def sanitize_intercompany_stock_entry(doc, method=None):
    """
    Ensures that an intercompany Material Receipt Stock Entry never contains
    cross-company source warehouses which trigger ERPNext's 'Warehouse does not belong to company' error.
    """
    if doc.purpose == "Material Receipt":
        if doc.from_warehouse:
            from_wh_comp = frappe.db.get_value("Warehouse", doc.from_warehouse, "company")
            if from_wh_comp and from_wh_comp != doc.company:
                doc.from_warehouse = None
                
        for d in doc.get("items", []):
            if d.s_warehouse:
                s_wh_comp = frappe.db.get_value("Warehouse", d.s_warehouse, "company")
                if s_wh_comp and s_wh_comp != doc.company:
                    d.s_warehouse = None


def create_stock_entry(source_stock_entry, mapping, linked_company, direction):
    """
    Creates a paired Stock Entry in target company for inter-company stock transfer.
    Bridges between the two companies using intercompany/transit warehouses.
    """
    se = frappe.new_doc("Stock Entry")
    
    if direction == "other_to_main":
        se.company = mapping.main_company
        target_warehouse_company = mapping.main_company
        target_warehouse = getattr(linked_company, "main_company_warehouse", None)
    else:
        se.company = linked_company.company
        target_warehouse_company = linked_company.company
        target_warehouse = getattr(linked_company, "other_company_warehouse", None)

    # Receive into target company's transit or receiving warehouse
    se.stock_entry_type = "Material Receipt"
    se.purpose = "Material Receipt"
    
    se.posting_date = getattr(source_stock_entry, "posting_date", None) or nowdate()
    se.posting_time = getattr(source_stock_entry, "posting_time", None)
    se.set_posting_time = getattr(source_stock_entry, "set_posting_time", 0)

    # Resolve currency conversion if source and target company default currencies differ
    source_company_currency = frappe.db.get_value("Company", source_stock_entry.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", se.company, "default_currency")
    fx_rate = get_intercompany_exchange_rate(source_company_currency, target_company_currency, se.posting_date)
    
    if not target_warehouse:
        target_warehouse = get_intercompany_warehouse(target_warehouse_company)
    if not target_warehouse:
        target_warehouse = frappe.db.get_value("Warehouse", {"company": target_warehouse_company, "is_group": 0}, "name")

    # In ERPNext, a Stock Entry in target company MUST NOT have from_warehouse set to another company!
    se.from_warehouse = None
    se.to_warehouse = target_warehouse

    for item in source_stock_entry.items:
        if not frappe.db.exists("Item", item.item_code):
            continue
            
        base_rate = getattr(item, "basic_rate", 0) or getattr(item, "valuation_rate", 0) or 0
        rate = flt(base_rate) * flt(fx_rate)
        se.append("items", {
            "item_code": item.item_code,
            "qty": item.qty,
            "uom": item.uom,
            "s_warehouse": None,
            "t_warehouse": target_warehouse,
            "basic_rate": rate,
            "basic_amount": rate * item.qty,
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

    try:
        se.set_missing_values(for_validate=True)
    except Exception:
        pass

    # Re-enforce clean warehouse state after set_missing_values
    se.from_warehouse = None
    for d in se.items:
        d.s_warehouse = None
        if not d.t_warehouse:
            d.t_warehouse = target_warehouse

    se.docstatus = 0  # Draft
    return se


def create_journal_entry(source_je, mapping, linked_company, direction):
    """Create corresponding Journal Entry"""
    je = frappe.new_doc("Journal Entry")
    
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
    je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name} " + (source_je.user_remark or "")

    # Multi-currency exchange rate handling
    source_company_currency = frappe.db.get_value("Company", source_je.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", je.company, "default_currency")
    fx_rate = get_intercompany_exchange_rate(source_company_currency, target_company_currency, je.posting_date)
    
    if source_company_currency != target_company_currency:
        je.multi_currency = 1
    else:
        je.multi_currency = source_je.multi_currency

    credit_amt = flt(source_je.total_credit) * flt(fx_rate)
    debit_amt = flt(source_je.total_debit) * flt(fx_rate)
    
    source_party_type = None
    source_is_credit = False
    
    for acc in source_je.accounts:
        if acc.party_type and acc.party:
            source_party_type = acc.party_type
            source_is_credit = acc.credit_in_account_currency > 0
            break
    
    default_cost_center = get_default_cost_center(je.company)

    if source_party_type == "Supplier" and source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_receivable_account"),
            "party_type": "Customer",
            "party": customer,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": credit_amt,
            "cost_center": default_cost_center
        })
        je.append("accounts", {
            "account": tmp_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": credit_amt,
            "cost_center": default_cost_center
        })
    elif source_party_type == "Supplier" and not source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_receivable_account"),
            "party_type": "Customer",
            "party": customer,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": debit_amt,
            "cost_center": default_cost_center
        })
        je.append("accounts", {
            "account": tmp_account,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": debit_amt,
            "cost_center": default_cost_center
        })
    elif source_party_type == "Customer" and source_is_credit:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_payable_account"),
            "party_type": "Supplier",
            "party": supplier,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": credit_amt,
            "cost_center": default_cost_center
        })
        je.append("accounts", {
            "account": tmp_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": credit_amt,
            "cost_center": default_cost_center
        })
    else:
        je.append("accounts", {
            "account": frappe.db.get_value("Company", je.company, "default_payable_account"),
            "party_type": "Supplier",
            "party": supplier,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": debit_amt,
            "cost_center": default_cost_center
        })
        je.append("accounts", {
            "account": tmp_account,
            "credit_in_account_currency": 0,
            "debit_in_account_currency": debit_amt,
            "cost_center": default_cost_center
        })
    
    je.flags.ignore_permissions = True
    je.flags.ignore_mandatory = True
    je.flags.ignore_account_permission = True
    je.flags.ignore_validate = True
    je.flags.ignore_links = True
    
    je.intercompany_target_company = source_je.company
    je.docstatus = 0  # Draft
    return je


def create_payment_entry(source_pe, mapping, linked_company, direction):
    """Create corresponding Payment Entry"""
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
    
    source_company_currency = frappe.db.get_value("Company", source_pe.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", pe.company, "default_currency")

    if pe.paid_from:
        pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency") or target_company_currency
    if pe.paid_to:
        pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency") or target_company_currency
    
    source_paid_currency = getattr(source_pe, "paid_from_account_currency", None) or source_company_currency

    # Rate from source payment currency to target paid_from currency
    fx_source_to_target_from = get_intercompany_exchange_rate(source_paid_currency, pe.paid_from_account_currency, pe.posting_date)
    pe.paid_amount = flt(source_pe.paid_amount) * flt(fx_source_to_target_from)

    # Conversion between target paid_from and paid_to
    fx_from_to_to = get_intercompany_exchange_rate(pe.paid_from_account_currency, pe.paid_to_account_currency, pe.posting_date)
    pe.target_exchange_rate = fx_from_to_to
    pe.received_amount = flt(pe.paid_amount) * flt(fx_from_to_to)

    pe.source_exchange_rate = get_intercompany_exchange_rate(pe.paid_from_account_currency, target_company_currency, pe.posting_date)
    
    pe.reference_no = getattr(source_pe, "reference_no", None) or source_pe.name
    pe.reference_date = getattr(source_pe, "reference_date", None) or source_pe.posting_date
    
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
    
    pe.docstatus = 0  # Draft
    return pe


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
            ref_doc.insert(ignore_permissions=True)
            frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error creating document reference: {str(e)}", "Inter Company Transaction Error")


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
    return frappe.db.get_value("Company", company, "cost_center")


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


def fix_legacy_custom_fields(force=False):
    """
    Sanitizes glued operators like '1or(' and ensures field expressions
    are valid both for JavaScript and Python.
    """
    if not (hasattr(frappe, "db") and frappe.db):
        return

    try:
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


@frappe.whitelist()
def bulk_create_linked_documents(doc_names, doctype):
    results = []
    for doc_name in doc_names:
        try:
            doc = frappe.get_doc(doctype, doc_name)
            create_linked_documents(doc, None)
            results.append({"name": doc_name, "status": "success"})
        except Exception as e:
            results.append({"name": doc_name, "status": "error", "message": str(e)})
    return results


@frappe.whitelist()
def reconcile_intercompany_accounts():
    companies = frappe.get_all("Company", pluck="name")
    reconciliation_data = []
    for company_a in companies:
        for company_b in companies:
            if company_a != company_b:
                balance_data = get_intercompany_balance(company_a, company_b)
                if balance_data:
                    reconciliation_data.append(balance_data)
    return reconciliation_data


def get_intercompany_balance(company_a, company_b):
    transactions = frappe.db.sql("""
        SELECT 
            source_doctype, source_name, source_company,
            target_doctype, target_name, target_company,
            modified
        FROM `tabInter Company Document Reference`
        WHERE (source_company = %s AND target_company = %s)
           OR (source_company = %s AND target_company = %s)
    """, (company_a, company_b, company_b, company_a), as_dict=True)
    return {"transactions_count": len(transactions)}


@frappe.whitelist()
def get_intercompany_dashboard_data(company):
    return {
        "pending_documents": 0,
        "monthly_volume": 0,
        "outstanding_balances": 0,
        "recent_transactions": []
    }
