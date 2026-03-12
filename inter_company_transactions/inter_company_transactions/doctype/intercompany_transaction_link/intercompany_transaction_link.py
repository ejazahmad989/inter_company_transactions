import frappe
from frappe.model.document import Document

class IntercompanyTransactionLink(Document):
    def validate(self):
        self.validate_companies()
        self.validate_transaction_types()
        self.validate_parties()
    
    def validate_companies(self):
        """Ensure main company and linked companies are different"""
        linked_companies = [d.company for d in self.linked_companies]
        if self.main_company in linked_companies:
            frappe.throw("Main Company cannot be in Linked Companies")
        
        if len(linked_companies) != len(set(linked_companies)):
            frappe.throw("Duplicate companies found in Linked Companies")

    def get_document_creator(source_doc, target_type):
        """Return the appropriate document creation function based on target type"""
        creators = {
            "Purchase Order": create_purchase_order,
            "Sales Order": create_sales_order,
            "Journal Entry": create_journal_entry,
            "Payment Entry": create_payment_entry
    }

        if target_type not in creators:
            frappe.throw(f"No creator available for target type {target_type}")

        return creators[target_type]

    def validate_document_mapping(source_type, target_type):
        """Validate that the document types can be mapped"""
        valid_mappings = {
            "Sales Order": ["Purchase Order"],
            "Purchase Order": ["Sales Order"],
            "Journal Entry": ["Journal Entry"],
            "Payment Entry": ["Payment Entry"]
        }

        if source_type not in valid_mappings:
            frappe.throw(f"Source document type {source_type} is not supported")

        if target_type not in valid_mappings.get(source_type, []):
            frappe.throw(
                f"Cannot map {source_type} to {target_type}. "
                f"Valid targets are: {', '.join(valid_mappings.get(source_type, []))}"
            )

    
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
    
    def validate_parties(self):
        """Validate that customers and suppliers are properly mapped between companies"""
        for linked_company in self.linked_companies:
            # Only validate required parties based on what's configured
            if linked_company.main_company_customer and not linked_company.other_company_supplier:
                frappe.throw(f"Other Company Supplier is required when Main Company Customer is set for {linked_company.company}")
            
            if linked_company.main_company_supplier and not linked_company.other_company_customer:
                frappe.throw(f"Other Company Customer is required when Main Company Supplier is set for {linked_company.company}")

def create_linked_documents(doc, method):
    """Robust document creation with complete error handling"""
    try:
        if doc.get("intercompany_linked_doc_doctype"):
            return

        mappings = find_applicable_mappings(doc)
        if not mappings:
            return

        for mapping in mappings:
            try:
                # Validate mapping structure
                if not all(key in mapping for key in ["mapping", "transaction_type", "linked_company", "direction"]):
                    continue

                direction = mapping["direction"]
                linked_company = mapping["linked_company"]
                
                # Validate required parties
                validate_required_parties(doc, mapping)
                
                # Create document
                linked_doc = create_corresponding_document(doc, mapping, direction)
                if not linked_doc:
                    continue

                # Set references
                linked_doc.update({
                    "intercompany_linked_doc_doctype": doc.doctype,
                    "intercompany_linked_doc_name": doc.name,
                    "intercompany_linked_company": doc.company
                })

                linked_doc.flags.ignore_permissions = True
                linked_doc.insert()
                
                create_document_reference(doc, linked_doc)
                frappe.msgprint(f"Created draft {linked_doc.doctype} {linked_doc.name} in company {linked_doc.company}")

            except Exception as e:
                error_msg = f"Failed to create linked document: {str(e)}"
                frappe.log_error(error_msg, "Inter Company Transaction Error")
                frappe.msgprint(error_msg)

    except Exception as e:
        frappe.log_error(
            f"Critical error in create_linked_documents: {str(e)}",
            "Inter Company Transaction Error"
        )


def cancel_linked_documents(doc, method):
    """Cancel corresponding documents in all linked companies"""
    if doc.get("intercompany_linked_doc_doctype"):
        return  # Skip if this is already a linked document
        
    # First find all directly linked documents
    linked_docs = frappe.get_all(
        "Inter Company Document Reference",
        filters=[
            ["source_doctype", "=", doc.doctype],
            ["source_name", "=", doc.name],
            ["source_company", "=", doc.company]
        ],
        fields=["target_doctype", "target_name", "target_company"]
    )
    
    # Also check if this document is a target and find its source
    reverse_links = frappe.get_all(
        "Inter Company Document Reference",
        filters=[
            ["target_doctype", "=", doc.doctype],
            ["target_name", "=", doc.name],
            ["target_company", "=", doc.company]
        ],
        fields=["source_doctype", "source_name", "source_company"]
    )
    
    def cancel_doc(doctype, docname):
        if frappe.db.exists(doctype, docname):
            target_doc = frappe.get_doc(doctype, docname)
            
            # Set all permission flags
            target_doc.flags.ignore_permissions = True
            target_doc.flags.ignore_mandatory = True
            target_doc.flags.ignore_account_permission = True
            target_doc.flags.ignore_validate = True
            target_doc.flags.ignore_links = True
            
            if target_doc.docstatus == 1:  # If submitted
                target_doc.cancel()
                frappe.db.commit()
                frappe.msgprint(f"Cancelled {target_doc.doctype} {target_doc.name}")
    
    try:
        # Cancel all linked documents
        for linked_doc in linked_docs:
            try:
                cancel_doc(linked_doc.target_doctype, linked_doc.target_name)
            except Exception as e:
                frappe.log_error(
                    f"Error cancelling linked document: {str(e)}\n"
                    f"Document: {linked_doc.target_doctype} {linked_doc.target_name}",
                    "Inter Company Transaction Error"
                )
        
        # Cancel source document if this is a target
        for reverse_link in reverse_links:
            try:
                cancel_doc(reverse_link.source_doctype, reverse_link.source_name)
            except Exception as e:
                frappe.log_error(
                    f"Error cancelling source document: {str(e)}\n"
                    f"Document: {reverse_link.source_doctype} {reverse_link.source_name}",
                    "Inter Company Transaction Error"
                )
                
    except Exception as e:
        frappe.log_error(
            f"Error in cancel_linked_documents: {str(e)}\n"
            f"Document: {doc.doctype} {doc.name}\n"
            f"Traceback: {frappe.get_traceback()}",
            "Inter Company Transaction Error"
        )
        raise

def validate_required_parties(doc, mapping):
    """Validate that required parties are configured based on transaction type"""
    linked_company = mapping["linked_company"]
    trans_type = mapping["transaction_type"]
    
    if doc.doctype == "Sales Order" and trans_type.target_type == "Purchase Order":
        if not linked_company.main_company_supplier:
            frappe.throw(f"Main Company Supplier is required for company {linked_company.company}")
    
    elif doc.doctype == "Purchase Order" and trans_type.target_type == "Sales Order":
        if not linked_company.main_company_customer:
            frappe.throw(f"Main Company Customer is required for company {linked_company.company}")
    
    elif doc.doctype in ["Journal Entry", "Payment Entry"]:
        # For financial transactions, we need both customer and supplier
        if not linked_company.main_company_customer:
            frappe.throw(f"Main Company Customer is required for company {linked_company.company}")
        if not linked_company.main_company_supplier:
            frappe.throw(f"Main Company Supplier is required for company {linked_company.company}")

def create_journal_entry(source_je, mapping_info, direction):
    """Create corresponding Journal Entry with robust error handling"""
    try:
        mapping = mapping_info["mapping"]
        linked_company = mapping_info["linked_company"]
        
        je = frappe.new_doc("Journal Entry")
        
        # Set intercompany_target_company
        je.intercompany_target_company = source_je.company
        
        
        # Set company and accounts based on direction
        if direction == "other_to_main":
            je.company = mapping.main_company
            supplier = linked_company.main_company_supplier
            customer = linked_company.main_company_customer
            tmp_account = linked_company.main_company_account
        else:
            je.company = linked_company.company
            supplier = linked_company.other_company_supplier
            customer = linked_company.other_company_customer
            tmp_account = linked_company.other_company_account
        
        # Validate all required accounts and parties exist
        if not tmp_account:
            frappe.throw(f"Temporary account not configured for company {je.company}")
        
        if not all([supplier, customer]):
            frappe.throw(f"Supplier/Customer not configured for company {je.company}")

        default_receivable = frappe.db.get_value("Company", je.company, "default_receivable_account")
        default_payable = frappe.db.get_value("Company", je.company, "default_payable_account")
        
        if not all([default_receivable, default_payable]):
            frappe.throw(f"Default accounts not configured for company {je.company}")

        je.posting_date = source_je.posting_date
        je.multi_currency = source_je.multi_currency
        je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name}"
        
        # Find the first party account in source JE
        source_party_type = None
        source_party = None
        source_is_credit = False
        
        for acc in source_je.accounts:
            if acc.party_type and acc.party:
                source_party_type = acc.party_type
                source_party = acc.party
                source_is_credit = acc.credit_in_account_currency > 0
                break
        
        # Create accounting entries
        if source_party_type == "Supplier":
            if source_is_credit:
                # Source credited supplier ? target debits customer
                je.append("accounts", {
                    "account": default_receivable,
                    "party_type": "Customer",
                    "party": customer,
                    "debit_in_account_currency": source_je.total_credit,
                    "cost_center": get_default_cost_center(je.company)
                })
                je.append("accounts", {
                    "account": tmp_account,
                    "credit_in_account_currency": source_je.total_credit,
                    "cost_center": get_default_cost_center(je.company)
                })
            else:
                # Source debited supplier ? target credits customer
                je.append("accounts", {
                    "account": default_receivable,
                    "party_type": "Customer",
                    "party": customer,
                    "credit_in_account_currency": source_je.total_debit,
                    "cost_center": get_default_cost_center(je.company)
                })
                je.append("accounts", {
                    "account": tmp_account,
                    "debit_in_account_currency": source_je.total_debit,
                    "cost_center": get_default_cost_center(je.company)
                })
        elif source_party_type == "Customer":
            if source_is_credit:
                # Source credited customer ? target debits supplier
                je.append("accounts", {
                    "account": default_payable,
                    "party_type": "Supplier",
                    "party": supplier,
                    "debit_in_account_currency": source_je.total_credit,
                    "cost_center": get_default_cost_center(je.company)
                })
                je.append("accounts", {
                    "account": tmp_account,
                    "credit_in_account_currency": source_je.total_credit,
                    "cost_center": get_default_cost_center(je.company)
                })
            else:
                # Source debited customer ? target credits supplier
                je.append("accounts", {
                    "account": default_payable,
                    "party_type": "Supplier",
                    "party": supplier,
                    "credit_in_account_currency": source_je.total_debit,
                    "cost_center": get_default_cost_center(je.company)
                })
                je.append("accounts", {
                    "account": tmp_account,
                    "debit_in_account_currency": source_je.total_debit,
                    "cost_center": get_default_cost_center(je.company)
                })
        
        # Set permission flags
        je.flags.ignore_permissions = True
        je.flags.ignore_mandatory = True
        je.flags.ignore_account_permission = True
        je.flags.ignore_validate = True
        je.flags.ignore_links = True
        
        je.intercompany_target_company = source_je.company
        je.docstatus = 0
        return je
        
    except Exception as e:
        frappe.log_error(
            f"Journal Entry creation failed for {source_je.doctype} {source_je.name}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise

import frappe
def create_payment_entry(source_pe, mapping_info, direction):
    """Create Payment Entry with proper error handling"""
    try:
        mapping = mapping_info["mapping"]
        linked_company = mapping_info["linked_company"]
        
        pe = frappe.new_doc("Payment Entry")
        # Set intercompany_target_company
        pe.intercompany_target_company = source_pe.company
        
        # Set company and accounts based on direction
        if direction == "other_to_main":
            pe.company = mapping.main_company
            tmp_account = linked_company.main_company_account
            customer = linked_company.main_company_customer
            supplier = linked_company.main_company_supplier
        else:
            pe.company = linked_company.company
            tmp_account = linked_company.other_company_account
            customer = linked_company.other_company_customer
            supplier = linked_company.other_company_supplier
        
        # Validate required accounts and parties
        if not tmp_account:
            frappe.throw(f"Temporary account not configured for company {pe.company}")
        
        if not all([customer, supplier]):
            frappe.throw(f"Customer/Supplier not configured for company {pe.company}")

        # Set basic fields
        pe.posting_date = source_pe.posting_date
        pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
        pe.mode_of_payment = source_pe.mode_of_payment
        
        # Set accounts and party based on payment type
        if pe.payment_type == "Pay":
            pe.paid_from = tmp_account
            pe.paid_to = frappe.db.get_value("Company", pe.company, "default_payable_account")
            pe.party_type = "Supplier"
            pe.party = supplier
        else:
            pe.paid_from = frappe.db.get_value("Company", pe.company, "default_receivable_account")
            pe.paid_to = tmp_account
            pe.party_type = "Customer"
            pe.party = customer
        
        # Set amounts and currencies
        pe.paid_amount = source_pe.paid_amount
        pe.received_amount = source_pe.received_amount
        pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency")
        pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")
        
        # Set permission flags
        pe.flags.ignore_permissions = True
        pe.flags.ignore_mandatory = True
        pe.docstatus = 0
        return pe
        
    except Exception as e:
        frappe.log_error(
            f"Payment Entry creation failed for {source_pe.doctype} {source_pe.name}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise

def create_purchase_order(sales_order, mapping_info, direction):
    """Create Purchase Order from Sales Order with proper error handling"""
    try:
        mapping = mapping_info["mapping"]
        linked_company = mapping_info["linked_company"]
        
        po = frappe.new_doc("Purchase Order")

        # Set intercompany_target_company
        po.intercompany_target_company = sales_order.company
        
        # Set company and supplier based on direction
        if direction == "other_to_main":
            po.company = mapping.main_company
            po.supplier = linked_company.main_company_supplier
        else:
            po.company = linked_company.company
            po.supplier = linked_company.other_company_supplier
        
        if not po.supplier:
            frappe.throw(f"Supplier not found for company {po.company}")
        
        # Copy basic fields
        po.currency = sales_order.currency
        po.conversion_rate = sales_order.conversion_rate
        po.transaction_date = sales_order.transaction_date
        po.schedule_date = sales_order.delivery_date
        
        # Set warehouse
        warehouse = get_default_warehouse(po.company)
        if not warehouse:
            frappe.throw(f"Default warehouse not found for company {po.company}")
        
        # Copy items
        for item in sales_order.items:
            po.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "warehouse": warehouse,
                "schedule_date": item.delivery_date
            })
        
        # Set permission flags
        po.flags.ignore_permissions = True
        po.flags.ignore_mandatory = True
        po.docstatus = 0
        return po
        
    except Exception as e:
        frappe.log_error(
            f"Purchase Order creation failed for {sales_order.doctype} {sales_order.name}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise


def create_sales_order(purchase_order, mapping_info, direction):
    """Create Sales Order from Purchase Order with proper error handling"""
    try:
        mapping = mapping_info["mapping"]
        linked_company = mapping_info["linked_company"]
        
        so = frappe.new_doc("Sales Order")
        # Set intercompany_target_company
        so.intercompany_target_company = purchase_order.company
        
        # Set company and customer based on direction
        if direction == "other_to_main":
            so.company = mapping.main_company
            so.customer = linked_company.main_company_customer
        else:
            so.company = linked_company.company
            so.customer = linked_company.other_company_customer
        
        if not so.customer:
            frappe.throw(f"Customer not found for company {so.company}")
        
        # Copy basic fields
        so.currency = purchase_order.currency
        so.conversion_rate = purchase_order.conversion_rate
        so.transaction_date = purchase_order.transaction_date
        so.delivery_date = purchase_order.schedule_date
        
        # Set warehouse
        warehouse = get_default_warehouse(so.company)
        if not warehouse:
            frappe.throw(f"Default warehouse not found for company {so.company}")
        
        # Copy items
        for item in purchase_order.items:
            so.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "warehouse": warehouse,
                "delivery_date": item.schedule_date
            })
        
        # Set permission flags
        so.flags.ignore_permissions = True
        so.flags.ignore_mandatory = True
        so.docstatus = 0
        return so
        
    except Exception as e:
        frappe.log_error(
            f"Sales Order creation failed for {purchase_order.doctype} {purchase_order.name}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise

def get_default_warehouse(company):
    """Get default warehouse for company with error handling"""
    try:
        warehouse = frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 0},
            "name"
        )
        
        if not warehouse:
            frappe.throw(f"Default warehouse not found for company {company}")
        
        return warehouse
        
    except Exception as e:
        frappe.log_error(
            f"Error getting default warehouse for {company}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise


def get_default_cost_center(company):
    """Get default cost center for company with error handling"""
    try:
        cost_center = frappe.db.get_value("Company", company, "cost_center")
        
        if not cost_center:
            frappe.throw(f"Default cost center not found for company {company}")
        
        return cost_center
        
    except Exception as e:
        frappe.log_error(
            f"Error getting default cost center for {company}: {str(e)}",
            "Inter Company Transaction Error"
        )
        raise

def get_mapped_account(account, to_company):
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
    
    if not mapped_account:
        frappe.throw(f"Could not find corresponding account in company {to_company}")
    
    return mapped_account

def find_matching_mapping_and_direction(doc, link):
    """
    Given a document and IntercompanyTransactionLink, find the matching mapping row and direction
    """
    for row in link.intercompany_transaction_type_mappings:
        dir = row.direction.lower().strip()
        main = link.main_company
        other = link.other_company

        if dir == "both":
            if doc.company == main and doc.doctype == row.main_company_doctype:
                return row, "main_to_other"
            elif doc.company == other and doc.doctype == row.other_company_doctype:
                return row, "other_to_main"
        elif dir == "main to other":
            if doc.company == main and doc.doctype == row.main_company_doctype:
                return row, "main_to_other"
        elif dir == "other to main":
            if doc.company == other and doc.doctype == row.other_company_doctype:
                return row, "other_to_main"

    return None, None
def handle_after_insert(doc, method=None):
    try:
        links = frappe.get_all("Intercompany Transaction Link", filters={"disabled": 0})
        for link_name in [l.name for l in links]:
            link = frappe.get_doc("Intercompany Transaction Link", link_name)
            mapping_row, direction = find_matching_mapping_and_direction(doc, link)

            if not mapping_row or not direction:
                continue

            mapping_info = {
                "mapping": mapping_row,
                "transaction_type": mapping_row,
                "linked_company": link
            }

            # Avoid infinite loop
            if doc.intercompany_linked_doc_name:
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
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Intercompany Insert Handler Failed")


def create_document_reference(source_doc, target_doc):
    """Create inter-company document reference"""
    try:
        # Validate companies are different
        if source_doc.company == target_doc.company:
            frappe.log_error(
                f"Cannot create reference between same company:\n"
                f"Source: {source_doc.doctype} {source_doc.name} ({source_doc.company})\n"
                f"Target: {target_doc.doctype} {target_doc.name} ({target_doc.company})",
                "Inter Company Transaction Error"
            )
            return
            
        # Check if reference already exists
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
    """Find valid mappings with proper type checking for all document types"""
    try:
        # Skip if no target or already linked
        target_company = doc.get('intercompany_target_company')
        if not target_company or doc.get("intercompany_linked_doc_doctype"):
            return []

        # Skip if target matches source
        if target_company == doc.company:
            return []

        # Skip if target is user's default company
        user_default_company = frappe.get_cached_value("User", frappe.session.user, "company") or \
                             frappe.defaults.get_defaults().company
        if target_company == user_default_company:
            return []

        mappings = []
        links = frappe.get_all(
            "Intercompany Transaction Link",
            filters={"enabled": 1},
            fields=["name", "main_company"]
        )

        for link in links:
            try:
                mapping = frappe.get_cached_doc("Intercompany Transaction Link", link.name)
                
                # Validate mapping structure
                if not hasattr(mapping, 'linked_companies') or not hasattr(mapping, 'transaction_types'):
                    continue
                
                # Main ? Linked Company
                if doc.company == mapping.main_company:
                    for lc in mapping.linked_companies:
                        if lc.company == target_company:
                            for trans_type in mapping.transaction_types:
                                if trans_type.source_type == doc.doctype and trans_type.direction in ["Main to Other", "Both"]:
                                    mappings.append({
                                        "mapping": mapping,
                                        "transaction_type": trans_type,
                                        "company": target_company,
                                        "linked_company": lc,
                                        "direction": "main_to_other"
                                    })
                
                # Linked Company ? Main
                elif target_company == mapping.main_company:
                    for lc in mapping.linked_companies:
                        if lc.company == doc.company:
                            for trans_type in mapping.transaction_types:
                                if trans_type.source_type == doc.doctype and trans_type.direction in ["Other to Main", "Both"]:
                                    mappings.append({
                                        "mapping": mapping,
                                        "transaction_type": trans_type,
                                        "company": target_company,
                                        "linked_company": lc,
                                        "direction": "other_to_main"
                                    })
            
            except Exception as e:
                frappe.log_error(
                    f"Error processing link {link.name}: {str(e)}",
                    "Inter Company Transaction Error"
                )
                continue

        return mappings

    except Exception as e:
        frappe.log_error(
            f"Error in find_applicable_mappings: {str(e)}",
            "Inter Company Transaction Error"
        )
        return []




def create_corresponding_document(source_doc, mapping_info, direction):
    """Create the corresponding document with proper error handling"""
    try:
        if not isinstance(mapping_info, dict) or 'mapping' not in mapping_info:
            frappe.throw("Invalid mapping information provided")
            
        mapping = mapping_info["mapping"]
        trans_type = mapping_info["transaction_type"]
        linked_company = mapping_info["linked_company"]
        
        if source_doc.doctype == "Sales Order" and trans_type.target_type == "Purchase Order":
            return create_purchase_order(source_doc, mapping_info, direction)
        elif source_doc.doctype == "Purchase Order" and trans_type.target_type == "Sales Order":
            return create_sales_order(source_doc, mapping_info, direction)
        elif source_doc.doctype == "Journal Entry" and trans_type.target_type == "Journal Entry":
            return create_journal_entry(source_doc, mapping_info, direction)
        elif source_doc.doctype == "Payment Entry" and trans_type.target_type == "Payment Entry":
            return create_payment_entry(source_doc, mapping_info, direction)
        
        return None
        
    except Exception as e:
        frappe.log_error(
            f"Error in create_corresponding_document: {str(e)}\n"
            f"Source Doc: {source_doc.doctype} {source_doc.name}",
            "Inter Company Transaction Error"
        )
        raise

def cancel_child_documents(doc):
    """Cancel any child documents linked to this document"""
    # Get all linked documents where this doc is the source
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
                
                # Set all permission flags
                target.flags.ignore_permissions = True
                target.flags.ignore_mandatory = True
                target.flags.ignore_account_permission = True
                target.flags.ignore_validate = True
                target.flags.ignore_links = True
                
                if target.docstatus == 1:
                    target.cancel()
                    frappe.msgprint(f"Cancelled child document {target.doctype} {target.name}")
        except Exception as e:
            frappe.log_error(
                f"Error cancelling child document: {str(e)}\n"
                f"Document: {child_doc.target_doctype} {child_doc.target_name}",
                "Inter Company Transaction Error"
            )











