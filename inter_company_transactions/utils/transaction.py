import frappe
from frappe import _
from frappe.utils import flt, nowdate


def create_linked_transaction(doc, method=None):
    """
    Called on_submit of mapped documents to automatically create the
    corresponding counterpart transaction in the linked sister company.
    """
    # Guard: prevent recursion and avoid re-triggering for generated documents
    if getattr(doc.flags, "from_inter_company", False):
        return

    if doc.get("inter_company_reference"):
        return

    # Find active mapping for this company
    map_names = frappe.get_all(
        "Inter Company Transaction Map",
        filters={"main_company": doc.company, "enabled": 1},
        pluck="name",
    )

    if not map_names:
        return

    mapping_rule = None
    for map_name in map_names:
        map_doc = frappe.get_doc("Inter Company Transaction Map", map_name)
        for row in map_doc.transaction_mappings:
            if row.main_company_transaction_type == doc.doctype:
                # If party is specified in mapping, check for match
                party_match = True
                if row.main_company_party:
                    party_field = get_party_field(doc.doctype)
                    if party_field and doc.get(party_field) != row.main_company_party:
                        party_match = False

                if party_match:
                    mapping_rule = row
                    break
        if mapping_rule:
            break

    if not mapping_rule:
        return

    # Generate counterpart transaction based on document type
    target_doctype = mapping_rule.other_company_transaction_type
    target_company = mapping_rule.other_company

    try:
        counterpart_doc = build_counterpart_doc(doc, target_doctype, target_company, mapping_rule)
        if not counterpart_doc:
            return

        # Mark with inter-company flags to avoid circular triggers
        counterpart_doc.flags.from_inter_company = True
        counterpart_doc.inter_company_reference = doc.name
        counterpart_doc.inter_company_transaction_type = doc.doctype
        counterpart_doc.inter_company_source_transaction = doc.name

        counterpart_doc.insert(ignore_permissions=True)

        # Record link on the source document
        doc.db_set("inter_company_reference", counterpart_doc.name)
        doc.db_set("inter_company_transaction_type", counterpart_doc.doctype)

        # Auto submit if configured
        if mapping_rule.auto_submit:
            counterpart_doc.flags.from_inter_company = True
            counterpart_doc.submit()

        frappe.msgprint(
            _("Inter-Company {0} <a href='/app/{1}/{2}'><b>{2}</b></a> automatically created in {3}").format(
                target_doctype,
                frappe.scrub(target_doctype),
                counterpart_doc.name,
                target_company,
            ),
            indicator="green",
        )

        doc.add_comment(
            "Comment",
            _("Created linked {0} {1} in company {2}").format(
                target_doctype, counterpart_doc.name, target_company
            ),
        )

    except Exception as e:
        frappe.log_error(
            title=_("Inter-Company Transaction Creation Failed"),
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            _("Could not auto-create linked {0} in {1}: {2}").format(
                target_doctype, target_company, str(e)
            ),
            indicator="orange",
        )


def cancel_linked_transaction(doc, method=None):
    """
    Called on_cancel of mapped documents to cascade cancellation to the
    counterpart transaction, maintaining ledger balance.
    """
    if getattr(doc.flags, "cancelling_inter_company", False):
        return

    linked_name = doc.get("inter_company_reference")
    linked_type = doc.get("inter_company_transaction_type")

    if not (linked_name and linked_type):
        return

    if not frappe.db.exists(linked_type, linked_name):
        return

    try:
        linked_doc = frappe.get_doc(linked_type, linked_name)
        if linked_doc.docstatus == 1:
            linked_doc.flags.cancelling_inter_company = True
            linked_doc.cancel()
            frappe.msgprint(
                _("Linked {0} {1} in {2} was automatically cancelled").format(
                    linked_type, linked_name, linked_doc.company
                ),
                indicator="blue",
            )
            doc.add_comment(
                "Comment",
                _("Cancelled linked {0} {1} in company {2}").format(
                    linked_type, linked_name, linked_doc.company
                ),
            )
    except Exception as e:
        frappe.log_error(
            title=_("Inter-Company Cancellation Failed"),
            message=frappe.get_traceback(),
        )
        frappe.throw(
            _("Failed to cancel linked document {0} ({1}): {2}").format(
                linked_name, linked_type, str(e)
            )
        )


def build_counterpart_doc(doc, target_doctype, target_company, mapping_rule):
    """
    Factory creating a new counterpart document populated with aligned data.
    """
    counterpart = frappe.new_doc(target_doctype)
    counterpart.company = target_company
    counterpart.currency = doc.currency

    # Date mapping
    counterpart.transaction_date = doc.get("transaction_date") or doc.get("posting_date") or nowdate()
    if target_doctype in ["Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"]:
        counterpart.posting_date = counterpart.transaction_date

    # Party mapping
    party_field = get_party_field(target_doctype)
    if party_field and mapping_rule.other_company_party:
        counterpart.set(party_field, mapping_rule.other_company_party)

    # Item mapping for order and invoice doctypes
    if hasattr(doc, "items") and hasattr(counterpart, "items"):
        for item in doc.items:
            counterpart_item = counterpart.append("items", {})
            counterpart_item.item_code = item.item_code
            counterpart_item.item_name = item.get("item_name") or item.item_code
            counterpart_item.description = item.description
            counterpart_item.qty = item.qty
            counterpart_item.rate = item.rate
            counterpart_item.amount = flt(item.qty) * flt(item.rate)
            counterpart_item.uom = item.get("uom") or "Nos"
            counterpart_item.conversion_factor = item.get("conversion_factor") or 1.0

            if target_doctype == "Purchase Order":
                counterpart_item.schedule_date = doc.get("delivery_date") or counterpart.transaction_date
            elif target_doctype == "Sales Order":
                counterpart_item.delivery_date = doc.get("schedule_date") or counterpart.transaction_date

    # Journal Entry mirroring
    elif target_doctype == "Journal Entry" and doc.doctype == "Journal Entry":
        counterpart.voucher_type = "Inter Company Journal Entry"
        counterpart.user_remark = f"Mirror entry for {doc.name} from {doc.company}"
        for acc in doc.accounts:
            c_acc = counterpart.append("accounts", {})
            c_acc.debit_in_account_currency = acc.credit_in_account_currency
            c_acc.credit_in_account_currency = acc.debit_in_account_currency
            c_acc.account = acc.account
            c_acc.party_type = acc.party_type
            c_acc.party = acc.party

    # Payment Entry mirroring
    elif target_doctype == "Payment Entry" and doc.doctype == "Payment Entry":
        counterpart.payment_type = "Pay" if doc.payment_type == "Receive" else "Receive"
        counterpart.paid_amount = doc.received_amount or doc.paid_amount
        counterpart.received_amount = doc.paid_amount or doc.received_amount
        counterpart.reference_no = doc.name
        counterpart.reference_date = doc.posting_date

    return counterpart


def get_party_field(doctype):
    """
    Returns the fieldname used for party (Customer or Supplier) in doctype.
    """
    if doctype in ["Sales Order", "Sales Invoice", "Delivery Note", "Quotation"]:
        return "customer"
    elif doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]:
        return "supplier"
    return None
