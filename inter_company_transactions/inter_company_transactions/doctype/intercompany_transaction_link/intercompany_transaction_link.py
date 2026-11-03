
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate


class IntercompanyTransactionLink(Document):
    def autoname(self):
        self.set_sister_company()
        sister = getattr(self, "sister_company", None) or self.get_sister_company_name()
        if self.main_company and sister:
            base = f"{self.main_company} - {sister}"[:130]
            name = base
            count = 1
            while frappe.db.exists("Intercompany Transaction Link", name):
                name = f"{base} ({count})"
                count += 1
            self.name = name
        else:
            from frappe.model.naming import set_new_name
            set_new_name(self)

    def before_insert(self):
        self.set_sister_company()

    def before_save(self):
        self.set_sister_company()

    def onload(self):
        if not getattr(self, "sister_company", None) and self.get("linked_companies"):
            self.set_sister_company()

    def on_update(self):
        sister = self.get_sister_company_name()
        if sister and getattr(self, "sister_company", None) != sister:
            self.db_set("sister_company", sister, update_modified=False)

    def get_sister_company_name(self):
        """Extract sister company name(s) from linked_companies child table"""
        companies = []
        for d in (self.get("linked_companies") or []):
            comp = getattr(d, "company", None) or (d.get("company") if isinstance(d, dict) else None)
            if comp and comp not in companies:
                companies.append(comp)
        return ", ".join(companies)

    def set_sister_company(self):
        """Auto-populate sister_company field from child table"""
        sister = self.get_sister_company_name()
        if sister:
            self.sister_company = sister
        elif not getattr(self, "sister_company", None):
            self.sister_company = ""

    def validate(self):
        self.set_sister_company()
        self.validate_companies()
        self.validate_parties()
        self.validate_transaction_types_child_table()

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

    def validate_transaction_types_child_table(self):
        """Auto-populate or fix target_type and direction for any child row"""
        default_targets = {
            "Sales Order": "Purchase Order",
            "Purchase Order": "Sales Order",
            "Sales Invoice": "Purchase Invoice",
            "Purchase Invoice": "Sales Invoice",
            "Delivery Note": "Purchase Receipt",
            "Purchase Receipt": "Delivery Note",
            "Stock Entry": "Stock Entry",
            "Journal Entry": "Journal Entry",
            "Payment Entry": "Payment Entry",
            "Quotation": "Supplier Quotation",
            "Supplier Quotation": "Quotation",
            "Material Request": "Purchase Order",
            "Request for Quotation": "Supplier Quotation",
            "Subcontracting Order": "Purchase Order",
            "Landed Cost Voucher": "Journal Entry"
        }
        for row in (self.get("transaction_types") or []):
            if row.source_type and not row.target_type:
                row.target_type = default_targets.get(row.source_type, row.source_type)
            if not row.direction:
                row.direction = "Both"

    @frappe.whitelist()
    def populate_default_transaction_types(self):
        """Populate standard supported intercompany transaction types"""
        default_pairs = [
            ("Sales Order", "Purchase Order", "Both"),
            ("Purchase Order", "Sales Order", "Both"),
            ("Sales Invoice", "Purchase Invoice", "Both"),
            ("Purchase Invoice", "Sales Invoice", "Both"),
            ("Delivery Note", "Purchase Receipt", "Both"),
            ("Purchase Receipt", "Delivery Note", "Both"),
            ("Quotation", "Supplier Quotation", "Both"),
            ("Supplier Quotation", "Quotation", "Both"),
            ("Material Request", "Sales Order", "Both"),
            ("Material Request", "Purchase Order", "Both"),
            ("Stock Entry", "Stock Entry", "Both"),
            ("Journal Entry", "Journal Entry", "Both"),
            ("Payment Entry", "Payment Entry", "Both"),
            ("Request for Quotation", "Supplier Quotation", "Both"),
            ("Subcontracting Order", "Purchase Order", "Both"),
            ("Landed Cost Voucher", "Journal Entry", "Both")
        ]

        existing = {
            (r.source_type, r.target_type)
            for r in (self.get("transaction_types") or [])
            if r.source_type and r.target_type
        }

        count = 0
        for src, tgt, direction in default_pairs:
            if (src, tgt) not in existing:
                self.append("transaction_types", {
                    "source_type": src,
                    "target_type": tgt,
                    "direction": direction
                })
                existing.add((src, tgt))
                count += 1

        if not self.is_new() and count > 0:
            self.save(ignore_permissions=True)

        return count

    @frappe.whitelist()
    def auto_create_intercompany_accounts(self):
        """
        Auto-provisions GAAP/IFRS-compliant Intercompany Clearing accounts in the Chart of Accounts
        for both Main Company and all Linked Companies.
        Automatically links them to main_company_account and other_company_account.
        """
        created_count = 0
        linked_count = 0

        for row in (self.get("linked_companies") or []):
            if not row.company:
                continue

            # 1. Ensure Main Company has clearing account for this sister company
            if not row.main_company_account:
                acc = get_or_create_intercompany_clearing_account(self.main_company, row.company)
                if acc:
                    row.main_company_account = acc
                    created_count += 1
            else:
                linked_count += 1

            # 2. Ensure Sister Company has clearing account for main company
            if not row.other_company_account:
                acc = get_or_create_intercompany_clearing_account(row.company, self.main_company)
                if acc:
                    row.other_company_account = acc
                    created_count += 1
            else:
                linked_count += 1

        if not self.is_new() and created_count > 0:
            self.save(ignore_permissions=True)

        return {
            "created": created_count,
            "already_configured": linked_count,
            "message": _("Configured {0} clearing account(s) ({1} verified).").format(created_count, linked_count),
        }


def create_linked_documents(doc, method=None):
    """Create corresponding documents in all linked companies (Local & Remote Federated)"""
    if not hasattr(doc, "doctype") or not doc.get("company"):
        return

    # Never process standard non-intercompany documents
    if not cint(doc.get("is_intercompany")):
        return

    # Never process a document that was itself generated as an intercompany counterpart
    if doc.get("intercompany_linked_doc_doctype") or doc.get("intercompany_linked_doc_name"):
        return

    # Check for direct target company remote push
    target_company_hint = (doc.get("intercompany_target_company") or "").strip()
    if target_company_hint:
        try:
            from inter_company_transactions.sync import (
                get_remote_site_for_company,
                push_document_to_remote_site,
            )
            remote_site = get_remote_site_for_company(target_company_hint)
            if remote_site:
                push_document_to_remote_site(doc, target_company_hint, remote_site)
                return
        except Exception as e:
            frappe.logger().error(f"Error checking remote site for target company {target_company_hint}: {e!s}")

    mappings = find_applicable_mappings(doc)
    if not mappings:
        return

    created_targets = set()

    for _i, mapping in enumerate(mappings):
        try:
            target_comp = mapping.get("company")
            target_dt = mapping.get("target_doctype")

            # 1. Absolute rule: Target company cannot be source company
            if not target_comp or target_comp == doc.company:
                continue

            # 2. If target_company_hint is specified, strictly respect it
            if target_company_hint and target_comp != target_company_hint:
                continue

            # 3. Deduplication: Only create ONE counterpart document per target company & target doctype
            dedup_key = (target_comp, target_dt)
            if dedup_key in created_targets:
                continue

            # 4. Check existing document reference in database to prevent double creation
            if frappe.db.exists("DocType", "Inter Company Document Reference"):
                existing = frappe.db.exists(
                    "Inter Company Document Reference",
                    {
                        "source_doctype": doc.doctype,
                        "source_name": doc.name,
                        "target_company": target_comp,
                        "target_doctype": target_dt
                    }
                )
                if existing:
                    continue

            # Check if this mapped company belongs to an external federated ERPNext site
            try:
                from inter_company_transactions.sync import (
                    get_remote_site_for_company,
                    push_document_to_remote_site,
                )
                remote_site = get_remote_site_for_company(target_comp)
                if remote_site:
                    push_document_to_remote_site(doc, target_comp, remote_site)
                    created_targets.add(dedup_key)
                    continue
            except Exception as e:
                frappe.logger().error(f"Error checking remote site for mapped company {target_comp}: {e!s}")

            direction = mapping.get("direction")
            if not direction:
                is_main_to_other = (doc.company == mapping["mapping"].main_company)
                direction = "main_to_other" if is_main_to_other else "other_to_main"

            validate_required_parties(doc, mapping)
            validate_intercompany_items(doc, mapping)

            linked_doc = create_corresponding_document(doc, mapping, direction)

            if linked_doc:
                # Ensure correct target company
                linked_doc.company = target_comp
                linked_doc.intercompany_linked_doc_doctype = doc.doctype
                linked_doc.intercompany_linked_doc_name = doc.name
                linked_doc.intercompany_linked_company = doc.company
                linked_doc.intercompany_target_company = doc.company

                linked_doc.flags.ignore_permissions = True
                linked_doc.flags.ignore_mandatory = True
                linked_doc.insert(ignore_permissions=True, ignore_mandatory=True)

                created_targets.add(dedup_key)
                create_document_reference(doc, linked_doc)

                frappe.msgprint(_("Created draft {0} {1} in company {2}").format(
                    linked_doc.doctype, linked_doc.name, linked_doc.company
                ))

        except Exception as e:
            frappe.log_error(f"Error in intercompany creation for {doc.doctype} {doc.name}: {e!s}\n{frappe.get_traceback()}", "Inter Company Transaction Error")
            frappe.msgprint(_("Notice for linked company {0}: {1}").format(
                mapping.get('company', ''), str(e)
            ))


def get_linked_counterpart_documents(doc):
    """
    Fetch all linked counterpart documents (both where doc is source and where doc is target).
    Uses ignore_permissions=True so server-side validation does not hit user company restrictions.
    """
    if not hasattr(doc, "company") or not doc.company:
        return []
    if not frappe.db.exists("DocType", "Inter Company Document Reference"):
        return []

    related_docs = []

    # 1. Documents where current doc is the SOURCE
    try:
        fields = ["target_doctype", "target_name", "target_company"]
        if frappe.db.has_column("Inter Company Document Reference", "is_remote"):
            fields.extend(["is_remote", "remote_site_url"])

        linked_docs = frappe.get_all(
            "Inter Company Document Reference",
            filters=[
                ["source_doctype", "=", doc.doctype],
                ["source_name", "=", doc.name],
                ["source_company", "=", doc.company],
            ],
            fields=fields,
            ignore_permissions=True,
        )
        for ld in linked_docs:
            related_docs.append({
                "doctype": ld.target_doctype,
                "name": ld.target_name,
                "company": ld.target_company,
                "relationship": "target",
                "is_remote": ld.get("is_remote"),
                "remote_site_url": ld.get("remote_site_url"),
            })
    except Exception as e:
        frappe.logger().error(f"Error finding linked documents (as source): {e!s}")

    # 2. Documents where current doc is the TARGET
    try:
        reverse_links = frappe.get_all(
            "Inter Company Document Reference",
            filters=[
                ["target_doctype", "=", doc.doctype],
                ["target_name", "=", doc.name],
                ["target_company", "=", doc.company],
            ],
            fields=["source_doctype", "source_name", "source_company"],
            ignore_permissions=True,
        )
        for rl in reverse_links:
            related_docs.append({
                "doctype": rl.source_doctype,
                "name": rl.source_name,
                "company": rl.source_company,
                "relationship": "source",
                "is_remote": False,
                "remote_site_url": None,
            })
    except Exception as e:
        frappe.logger().error(f"Error finding reverse links (as target): {e!s}")

    return related_docs


def check_active_downstream_transactions(doctype, docname, company):
    """
    Checks if a document in any company has active downstream transactions (such as
    submitted Payment Entries, Journal Entries, Delivery Notes, Purchase Receipts, or Invoices).
    Returns a list of descriptive strings for any active blocking records found.
    """
    blocking_records = []

    # 1. Active Payment Entries (Sales Invoice or Purchase Invoice)
    if doctype in ["Sales Invoice", "Purchase Invoice"]:
        try:
            if frappe.db.exists("DocType", "Payment Entry Reference"):
                pe_refs = frappe.get_all(
                    "Payment Entry Reference",
                    filters={
                        "reference_doctype": doctype,
                        "reference_name": docname,
                        "docstatus": 1,
                    },
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for pe in pe_refs:
                    if pe.parent and f"Payment Entry '{pe.parent}'" not in blocking_records:
                        blocking_records.append(f"Payment Entry '{pe.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Payment Entry Reference for {doctype} {docname}: {e!s}")

        # 2. Active Journal Entries (linked vouchers/payments)
        try:
            if frappe.db.exists("DocType", "Journal Entry Account"):
                je_refs = frappe.get_all(
                    "Journal Entry Account",
                    filters={
                        "reference_type": doctype,
                        "reference_name": docname,
                        "docstatus": 1,
                    },
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for je in je_refs:
                    if je.parent and f"Journal Entry '{je.parent}'" not in blocking_records:
                        blocking_records.append(f"Journal Entry '{je.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Journal Entry Account for {doctype} {docname}: {e!s}")

    # 3. Downstream fulfillment for Sales Order
    elif doctype == "Sales Order":
        try:
            if frappe.db.exists("DocType", "Delivery Note Item"):
                dns = frappe.get_all(
                    "Delivery Note Item",
                    filters={"against_sales_order": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for dn in dns:
                    if dn.parent and f"Delivery Note '{dn.parent}'" not in blocking_records:
                        blocking_records.append(f"Delivery Note '{dn.parent}'")

            if frappe.db.exists("DocType", "Sales Invoice Item"):
                sis = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"sales_order": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for si in sis:
                    if si.parent and f"Sales Invoice '{si.parent}'" not in blocking_records:
                        blocking_records.append(f"Sales Invoice '{si.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Sales Order downstream for {docname}: {e!s}")

    # 4. Downstream fulfillment for Purchase Order
    elif doctype == "Purchase Order":
        try:
            if frappe.db.exists("DocType", "Purchase Receipt Item"):
                prs = frappe.get_all(
                    "Purchase Receipt Item",
                    filters={"purchase_order": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for pr in prs:
                    if pr.parent and f"Purchase Receipt '{pr.parent}'" not in blocking_records:
                        blocking_records.append(f"Purchase Receipt '{pr.parent}'")

            if frappe.db.exists("DocType", "Purchase Invoice Item"):
                pis = frappe.get_all(
                    "Purchase Invoice Item",
                    filters={"purchase_order": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for pi in pis:
                    if pi.parent and f"Purchase Invoice '{pi.parent}'" not in blocking_records:
                        blocking_records.append(f"Purchase Invoice '{pi.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Purchase Order downstream for {docname}: {e!s}")

    # 5. Downstream invoice for Delivery Note
    elif doctype == "Delivery Note":
        try:
            if frappe.db.exists("DocType", "Sales Invoice Item"):
                sis = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"delivery_note": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for si in sis:
                    if si.parent and f"Sales Invoice '{si.parent}'" not in blocking_records:
                        blocking_records.append(f"Sales Invoice '{si.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Delivery Note downstream for {docname}: {e!s}")

    # 6. Downstream invoice for Purchase Receipt
    elif doctype == "Purchase Receipt":
        try:
            if frappe.db.exists("DocType", "Purchase Invoice Item"):
                pis = frappe.get_all(
                    "Purchase Invoice Item",
                    filters={"purchase_receipt": docname, "docstatus": 1},
                    fields=["parent"],
                    ignore_permissions=True,
                )
                for pi in pis:
                    if pi.parent and f"Purchase Invoice '{pi.parent}'" not in blocking_records:
                        blocking_records.append(f"Purchase Invoice '{pi.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Purchase Receipt downstream for {docname}: {e!s}")

    return blocking_records


def validate_intercompany_cancellation(doc, method=None):
    """
    Validates before cancellation that neither this document nor any linked
    intercompany counterpart documents have active payments or downstream transactions.
    If active transactions exist, cancellation is blocked with clear, actionable instructions.
    """
    if not hasattr(doc, "company") or not doc.company:
        return

    # Non-intercompany documents have no linked counterparts to validate
    if not cint(doc.get("is_intercompany")) and not doc.get("intercompany_linked_doc_name"):
        return

    if doc.flags.get("intercompany_auto_cancel"):
        return

    # Check counterpart documents
    counterparts = get_linked_counterpart_documents(doc)
    for cp in counterparts:
        if cp.get("is_remote"):
            continue

        c_doctype = cp["doctype"]
        c_name = cp["name"]
        c_company = cp.get("company") or "Linked Company"

        if not frappe.db.exists(c_doctype, c_name):
            continue

        status = frappe.db.get_value(c_doctype, c_name, "docstatus")
        if status != 1:
            # If draft or already cancelled, no active payments can block
            continue

        blocking = check_active_downstream_transactions(c_doctype, c_name, c_company)
        if blocking:
            blocking_bullets = "".join([f"<li><b>{b}</b></li>" for b in blocking])
            frappe.throw(
                _(
                    "<div style='font-size: 13px; line-height: 1.6;'>"
                    "<h4><b>Inter-Company Cancellation Blocked</b></h4>"
                    "Cannot cancel <b>{0} {1}</b> because the linked counterpart <b>{2} {3}</b> "
                    "in company <b>{4}</b> has active downstream transaction(s):"
                    "<ul style='margin: 8px 0 12px 20px;'>{5}</ul>"
                    "<b>Required Action:</b><br>"
                    "Please contact the accounting team in <b>{4}</b> (via phone or WhatsApp) to cancel "
                    "or remove the above payment/downstream transactions first, then cancel <b>{3}</b>, "
                    "after which this document can be cancelled."
                    "</div>"
                ).format(doc.doctype, doc.name, c_doctype, c_name, c_company, blocking_bullets),
                title=_("Active Transactions Exist in Linked Company")
            )


def cancel_linked_documents(doc, method=None):
    """Cancel corresponding documents in all linked companies - BIDIRECTIONAL with transaction integrity"""
    if not hasattr(doc, 'company') or not doc.company:
        return

    # Non-intercompany documents have no linked counterparts to cancel
    if not cint(doc.get("is_intercompany")) and not doc.get("intercompany_linked_doc_name"):
        return

    if doc.flags.get("intercompany_auto_cancel"):
        return

    if not frappe.db.exists("DocType", "Inter Company Document Reference"):
        return

    # Step 1: Pre-validate downstream payments and transactions
    validate_intercompany_cancellation(doc)

    all_related_docs = get_linked_counterpart_documents(doc)

    # Step 2: Handle remote instances if enabled
    for ld in all_related_docs:
        if ld.get("is_remote") and ld.get("remote_site_url"):
            try:
                from inter_company_transactions.sync import get_remote_site_for_company
                remote_site = get_remote_site_for_company(ld.get("company"))
                if remote_site:
                    import json
                    import urllib.request
                    endpoint = f"{remote_site['site_url']}/api/method/inter_company_transactions.sync.cancel_remote_transaction"
                    c_payload = json.dumps({"source_doctype": doc.doctype, "source_name": doc.name}).encode("utf-8")
                    c_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"token {remote_site['api_key']}:{remote_site['api_secret']}"
                    }
                    c_req = urllib.request.Request(endpoint, data=c_payload, headers=c_headers, method="POST")
                    with urllib.request.urlopen(c_req, timeout=10):
                        frappe.msgprint(_("Notified remote instance ({0}) to cancel mirrored transaction.").format(remote_site['site_url']))
            except Exception as ex:
                frappe.logger().error(f"Failed to cancel remote document on {ld.get('remote_site_url')}: {ex!s}")

    # Step 3: Cancel local linked counterpart documents atomically
    for related_doc in all_related_docs:
        if related_doc.get("is_remote"):
            continue

        doctype = related_doc['doctype']
        docname = related_doc['name']
        company = related_doc.get('company')
        relationship = related_doc.get('relationship')

        if not frappe.db.exists(doctype, docname):
            continue

        target_doc = frappe.get_doc(doctype, docname)
        if target_doc.docstatus != 1:
            continue

        try:
            target_doc.flags.ignore_permissions = True
            target_doc.flags.ignore_mandatory = True
            target_doc.flags.ignore_account_permission = True
            target_doc.flags.ignore_validate = True
            target_doc.flags.ignore_links = True
            target_doc.flags.ignore_validate_update_after_submit = True
            target_doc.flags.ignore_workflow = True
            target_doc.flags.intercompany_auto_cancel = True

            target_doc.cancel()

            frappe.msgprint(_("Cancelled {0} {1} in company {2} ({3} document)").format(
                target_doc.doctype, target_doc.name, company or getattr(target_doc, 'company', ''), relationship
            ))
        except Exception as e:
            frappe.throw(
                _(
                    "<b>Inter-Company Cancellation Failed:</b><br>"
                    "Failed to cancel linked {0} <b>{1}</b> in company <b>{2}</b>.<br>"
                    "Error: {3}<br><br>"
                    "The cancellation of <b>{4} {5}</b> has been aborted to preserve accounting ledger consistency."
                ).format(doctype, docname, company or getattr(target_doc, 'company', ''), str(e), doc.doctype, doc.name),
                title=_("Inter-Company Cancellation Aborted")
            )


def find_applicable_mappings(doc):
    """
    Finds unique, valid matching mapping configurations for the document.
    Ensures:
    1. Target company is NEVER the same as source doc.company.
    2. If doc has intercompany_target_company set, ONLY matches that target company.
    3. Exactly ONE mapping per (target_company, target_doctype) pair to prevent duplicate documents.
    """
    if not hasattr(doc, "company") or not doc.company:
        return []

    # Standard non-intercompany documents have NO applicable intercompany mappings
    if not cint(doc.get("is_intercompany")):
        return []

    # If this document is already a linked counterpart created by ICT, do NOT trigger counter creations
    if doc.get("intercompany_linked_doc_name") or doc.get("intercompany_linked_doc_doctype"):
        return []

    mappings = []
    seen_pairs = set()

    source_company = doc.company
    target_company_hint = (doc.get("intercompany_target_company") or "").strip()
    if not target_company_hint and doc.doctype == "Journal Entry":
        for row in (doc.get("accounts") or []):
            r_target = (row.get("intercompany_target_company") or "").strip()
            if r_target and r_target != source_company:
                target_company_hint = r_target
                break

    # An inter-company transaction MUST have an explicit designated target sister company.
    # Without a target sister company, mirroring must NEVER broadcast to arbitrary linked companies.
    if not target_company_hint or target_company_hint == source_company:
        return []

    links = frappe.get_all(
        "Intercompany Transaction Link",
        filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {},
        fields=["name", "main_company"]
    )

    for link_entry in links:
        link = frappe.get_doc("Intercompany Transaction Link", link_entry.name)

        is_main = (source_company == link.main_company)
        is_linked = any(lc.company == source_company for lc in (link.linked_companies or []))

        if not is_main and not is_linked:
            continue

        if is_main:
            # Source is Main Company -> Target is Linked Company
            candidate_linked_companies = [
                lc for lc in (link.linked_companies or [])
                if lc.company and lc.company == target_company_hint and lc.company != source_company
            ]
            if not candidate_linked_companies:
                continue

            for linked_company in candidate_linked_companies:
                target_comp = linked_company.company
                if not target_comp or target_comp == source_company:
                    continue

                for trans_type in (link.transaction_types or []):
                    target_dt = resolve_target_doctype(doc.doctype, trans_type, direction="main_to_other")
                    if target_dt:
                        pair_key = (target_comp, target_dt)
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        mappings.append({
                            "mapping": link,
                            "transaction_type": trans_type,
                            "company": target_comp,
                            "linked_company": linked_company,
                            "direction": "main_to_other",
                            "target_doctype": target_dt
                        })

        else:
            # Source is Linked Company -> Target is Main Company
            if target_company_hint != link.main_company or link.main_company == source_company:
                continue

            linked_company = next((lc for lc in (link.linked_companies or []) if lc.company == source_company), None)
            if not linked_company:
                continue

            target_comp = link.main_company
            for trans_type in (link.transaction_types or []):
                target_dt = resolve_target_doctype(doc.doctype, trans_type, direction="other_to_main")
                if target_dt:
                    pair_key = (target_comp, target_dt)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    mappings.append({
                        "mapping": link,
                        "transaction_type": trans_type,
                        "company": target_comp,
                        "linked_company": linked_company,
                        "direction": "other_to_main",
                        "target_doctype": target_dt
                    })

    return mappings


def resolve_target_doctype(source_doctype, trans_type, direction):
    """
    Resolves the target DocType given the source DocType, mapping rule, and transaction flow direction.
    Allows bidirectional pairs configured in either direction without duplicate firing.
    """
    rule_src = trans_type.source_type
    rule_tgt = trans_type.target_type
    rule_dir = (trans_type.direction or "").strip()

    if direction == "main_to_other":
        if rule_src == source_doctype and rule_dir in ["Main to Other", "Both", ""]:
            return rule_tgt
        if rule_src != rule_tgt and rule_tgt == source_doctype and rule_dir in ["Other to Main", "Both"]:
            return rule_src

    elif direction == "other_to_main":
        if rule_src == source_doctype and rule_dir in ["Other to Main", "Both", ""]:
            return rule_tgt
        if rule_src != rule_tgt and rule_tgt == source_doctype and rule_dir in ["Main to Other", "Both"]:
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


def validate_intercompany_items(doc, mapping):
    """
    Validate that all items can be resolved for the target company.
    If auto_create_missing_items is disabled in settings, ensures every item
    either exists in the catalog or has an explicit SKU cross-mapping.
    If an item cannot be resolved, raises a descriptive error to alert the user.
    """
    if not hasattr(doc, "items") or not doc.get("items"):
        return

    # Check if auto_create_missing_items is enabled (default = 1)
    auto_create = True
    try:
        if frappe.db.exists("DocType", "Inter Company Settings"):
            settings = frappe.get_single("Inter Company Settings")
            if settings.auto_create_missing_items is not None:
                auto_create = bool(cint(settings.auto_create_missing_items))
    except Exception:
        pass

    if auto_create:
        return  # Auto-creation handles missing items smoothly

    target_company = mapping.get("company")
    link_doc = mapping.get("mapping")

    unresolved_items = []
    for item in doc.items:
        src_code = item.get("item_code") if isinstance(item, dict) else getattr(item, "item_code", None)
        if not src_code:
            continue

        # Check mapping in child table
        mapped = False
        if link_doc and hasattr(link_doc, "item_mappings"):
            for row in (link_doc.get("item_mappings") or []):
                if row.source_item_code == src_code and (not row.target_company or row.target_company == target_company):
                    if frappe.db.exists("Item", row.target_item_code):
                        mapped = True
                        break

        # Check standalone mapping
        if not mapped and frappe.db.exists("DocType", "Intercompany Item Mapping"):
            target_sku = frappe.db.get_value(
                "Intercompany Item Mapping",
                {"source_item_code": src_code, "target_company": target_company},
                "target_item_code",
            )
            if target_sku and frappe.db.exists("Item", target_sku):
                mapped = True

        # Check if source item code itself exists
        if not mapped and frappe.db.exists("Item", src_code):
            mapped = True

        if not mapped:
            unresolved_items.append(src_code)

    if unresolved_items:
        items_str = ", ".join(f"'{c}'" for c in sorted(set(unresolved_items)))
        frappe.throw(
            _("Intercompany Item Error: The following item(s) do not exist for sister company '{0}': {1}. "
              "Please either map them in 'Intercompany Transaction Link' -> 'SKU / Item Code Mappings', "
              "create them in the item catalog, or enable 'Auto-Create Missing Items' in 'Inter Company Settings'."
            ).format(target_company, items_str),
            title=_("Item Mapping Required"),
        )


def get_parent_clearing_account(company):
    """
    Finds the appropriate parent account for an Intercompany Clearing account
    under Current Assets for the given company.
    """
    if not company:
        return None

    # 1. Look for 'Current Assets' group account in this company
    parent = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "is_group": 1,
            "root_type": "Asset",
            "account_name": ["in", ["Current Assets", "Current Asset"]],
        },
        "name",
    )
    if not parent:
        # Try finding any group account containing 'Current Asset'
        parent = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "is_group": 1,
                "root_type": "Asset",
                "account_name": ["like", "%Current Asset%"],
            },
            "name",
        )
    if not parent:
        # Fallback to any group Asset account that is not root
        parent = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "is_group": 1,
                "root_type": "Asset",
                "parent_account": ["is", "set"],
            },
            "name",
        )
    return parent


def get_or_create_intercompany_clearing_account(company, sister_company):
    """
    Finds or creates an IFRS/GAAP-compliant Intercompany Clearing / Bridge account
    under Current Assets for the given company.
    """
    if not company:
        return None

    sister_clean = (sister_company or "").strip()

    # 1. Search for existing account with matching sister company name in this company
    if sister_clean:
        candidate = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "is_group": 0,
                "account_name": ["like", f"%Intercompany Clearing%{sister_clean}%"],
            },
            "name",
        )
        if candidate:
            return candidate

    # 2. General intercompany clearing account in this company
    candidate = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "is_group": 0,
            "account_name": ["like", "%Intercompany Clearing%"],
        },
        "name",
    )
    if candidate:
        return candidate

    # 3. Create a compliant clearing account under Current Assets
    try:
        parent_account = get_parent_clearing_account(company)
        if not parent_account:
            return frappe.db.get_value("Company", company, "default_cash_account") or frappe.db.get_value("Company", company, "default_bank_account")

        acc_label = f"Intercompany Clearing - {sister_clean}" if sister_clean else "Intercompany Clearing"
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": acc_label,
            "company": company,
            "parent_account": parent_account,
            "root_type": "Asset",
            "account_type": "Temporary",
            "is_group": 0,
        })
        acc.flags.ignore_permissions = True
        acc.flags.ignore_mandatory = True
        acc.insert()
        return acc.name
    except Exception as e:
        frappe.log_error(f"Error auto-creating intercompany clearing account in {company}: {e}", "Intercompany Accounting")
        return frappe.db.get_value("Company", company, "default_cash_account") or frappe.db.get_value("Company", company, "default_bank_account")


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


def ensure_item_exists(item_code, item_name=None, description=None, uom="Nos", item_group=None):
    """
    Ensure an item exists in the database. If it doesn't exist, create it cleanly.
    """
    if not item_code:
        return item_code

    if frappe.db.exists("Item", item_code):
        return item_code

    # Check settings if auto creation is enabled (default enabled)
    auto_create = True
    try:
        if frappe.db.exists("DocType", "Inter Company Settings"):
            settings = frappe.get_single("Inter Company Settings")
            if settings.auto_create_missing_items is not None:
                auto_create = bool(cint(settings.auto_create_missing_items))
    except Exception:
        pass

    if not auto_create:
        return item_code

    try:
        # Determine valid item_group
        if not item_group or not frappe.db.exists("Item Group", item_group):
            item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"

        if not uom or not frappe.db.exists("UOM", uom):
            uom = frappe.db.get_value("UOM", {}, "name") or "Nos"

        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name or item_code,
            "description": description or item_name or item_code,
            "item_group": item_group,
            "stock_uom": uom,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
        })
        item_doc.flags.ignore_permissions = True
        item_doc.flags.ignore_mandatory = True
        item_doc.insert()
        return item_doc.name
    except Exception as e:
        frappe.log_error(f"Could not auto-create item {item_code}: {e}", "Intercompany Item Creation")
        return item_code


def resolve_intercompany_target_item(source_item, target_company, mapping=None, rate_factor=1.0):
    """
    Resolves item code, quantity, rate, and UOM for intercompany target document.
    Translates source SKU (e.g. 'PEN' in Company A) to target SKU (e.g. 'PEN-001' in Company B)
    using:
    1. Child table 'item_mappings' in Intercompany Transaction Link (mapping)
    2. Global 'Intercompany Item Mapping' table
    3. Fallback to same item_code, auto-creating in target company if missing
    """
    source_code = source_item.get("item_code") if isinstance(source_item, dict) else getattr(source_item, "item_code", None)
    source_name = source_item.get("item_name") if isinstance(source_item, dict) else getattr(source_item, "item_name", source_code)
    source_desc = source_item.get("description") if isinstance(source_item, dict) else getattr(source_item, "description", source_name)
    source_qty = flt(source_item.get("qty") if isinstance(source_item, dict) else getattr(source_item, "qty", 1))
    source_rate = flt(source_item.get("rate") if isinstance(source_item, dict) else getattr(source_item, "rate", 0))
    source_uom = source_item.get("uom") if isinstance(source_item, dict) else getattr(source_item, "uom", "Nos")

    target_code = None
    target_name = source_name
    target_desc = source_desc
    conversion_factor = 1.0

    # 1. Check mapping in Intercompany Transaction Link child table
    if mapping and hasattr(mapping, "item_mappings"):
        for row in (mapping.get("item_mappings") or []):
            if row.source_item_code == source_code:
                if not row.target_company or row.target_company == target_company:
                    target_code = row.target_item_code
                    conversion_factor = flt(row.conversion_factor) or 1.0
                    break

    # 2. Check standalone Intercompany Item Mapping DocType
    if not target_code and frappe.db.exists("DocType", "Intercompany Item Mapping"):
        try:
            mapping_row = frappe.db.get_value(
                "Intercompany Item Mapping",
                {"source_item_code": source_code, "target_company": target_company},
                ["target_item_code", "conversion_factor"],
                as_dict=True,
            )
            if mapping_row:
                target_code = mapping_row.target_item_code
                conversion_factor = flt(mapping_row.conversion_factor) or 1.0
        except Exception:
            pass

    # 3. If no translation rule found, default to same item code
    if not target_code:
        target_code = source_code
        conversion_factor = 1.0

    # Ensure target item exists in database (auto-creates if missing)
    if target_code:
        ensure_item_exists(target_code, item_name=target_name, description=target_desc, uom=source_uom)

    # Calculate converted qty and rate
    target_qty = source_qty * (conversion_factor if conversion_factor != 0 else 1.0)
    unit_rate = (source_rate * flt(rate_factor)) / (conversion_factor if conversion_factor != 0 else 1.0)

    # Fetch actual item_name and stock_uom from Item record if available
    item_info = frappe.db.get_value("Item", target_code, ["item_name", "stock_uom", "description"], as_dict=True) if target_code else None
    if item_info:
        target_name = item_info.item_name or target_name
        target_desc = item_info.description or target_desc
        target_uom = item_info.stock_uom if conversion_factor != 1.0 else (source_uom or item_info.stock_uom)
    else:
        target_uom = source_uom

    return {
        "item_code": target_code,
        "item_name": target_name,
        "description": target_desc,
        "qty": target_qty,
        "uom": target_uom,
        "rate": unit_rate,
        "conversion_factor": conversion_factor,
    }


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
        target_item = resolve_intercompany_target_item(item, si.company, mapping=mapping, rate_factor=rate_factor)
        item_row = {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
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
        target_item = resolve_intercompany_target_item(item, pi.company, mapping=mapping, rate_factor=rate_factor)
        item_row = {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
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
        target_item = resolve_intercompany_target_item(item, po.company, mapping=mapping, rate_factor=rate_factor)
        po.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
            "warehouse": warehouse,
            "schedule_date": getattr(item, "delivery_date", None) or po.schedule_date,
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
        target_item = resolve_intercompany_target_item(item, so.company, mapping=mapping, rate_factor=rate_factor)
        so.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
            "warehouse": warehouse,
            "delivery_date": getattr(item, "schedule_date", None) or so.delivery_date,
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
        target_item = resolve_intercompany_target_item(item, dn.company, mapping=mapping, rate_factor=rate_factor)
        dn.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
            "warehouse": target_warehouse,
            "against_sales_order": None,
            "against_sales_invoice": None,
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
        target_item = resolve_intercompany_target_item(item, pr.company, mapping=mapping, rate_factor=rate_factor)
        pr.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
            "warehouse": target_warehouse,
            "purchase_order": None,
            "purchase_invoice": None,
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
        target_item = resolve_intercompany_target_item(item, q.company, mapping=mapping, rate_factor=rate_factor)
        q.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
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
        target_item = resolve_intercompany_target_item(item, sq.company, mapping=mapping, rate_factor=rate_factor)
        sq.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
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
        target_item = resolve_intercompany_target_item(item, se.company, mapping=mapping, rate_factor=fx_rate)
        base_rate = getattr(item, "basic_rate", 0) or getattr(item, "valuation_rate", 0) or 0
        rate = flt(base_rate) * flt(fx_rate)
        final_rate = target_item["rate"] if target_item["rate"] else rate
        se.append("items", {
            "item_code": target_item["item_code"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "s_warehouse": None,
            "t_warehouse": target_warehouse,
            "basic_rate": final_rate,
            "basic_amount": final_rate * target_item["qty"],
            "conversion_factor": target_item["conversion_factor"],
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
        tmp_account = get_or_create_intercompany_clearing_account(je.company, source_je.company)

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
        tmp_account = get_or_create_intercompany_clearing_account(pe.company, source_pe.company)

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
        frappe.log_error(f"Error creating document reference: {e!s}", "Inter Company Transaction Error")


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

            if frappe.db.has_column("Custom Field", "default"):
                frappe.db.sql("""
                    UPDATE `tabCustom Field`
                    SET `default` = '0'
                    WHERE `fieldname` = 'is_intercompany'
                      AND (`default` IS NULL OR `default` = '' OR `default` = '1')
                """)
                frappe.db.sql("""
                    UPDATE `tabCustom Field`
                    SET `default` = NULL
                    WHERE `fieldname` = 'intercompany_target_company'
                      AND `default` IS NOT NULL
                """)
            if frappe.db.has_column("Custom Field", "fetch_if_empty"):
                frappe.db.sql("""
                    UPDATE `tabCustom Field`
                    SET `fetch_if_empty` = 0
                    WHERE `fieldname` = 'intercompany_target_company'
                """)

            # Directly enforce DEFAULT 0 on MariaDB transaction tables and clean stale draft values
            tx_doctypes = [
                "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
                "Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation",
                "Material Request", "Stock Entry", "Journal Entry", "Payment Entry",
                "Request for Quotation"
            ]
            for dt in tx_doctypes:
                try:
                    if frappe.db.table_exists(dt) and frappe.db.has_column(dt, "is_intercompany"):
                        frappe.db.sql(f"ALTER TABLE `tab{dt}` ALTER COLUMN `is_intercompany` SET DEFAULT 0")
                except Exception:
                    pass

                try:
                    if frappe.db.table_exists(dt) and frappe.db.has_column(dt, "is_intercompany") and frappe.db.has_column(dt, "intercompany_target_company"):
                        frappe.db.sql(f"""
                            UPDATE `tab{dt}`
                            SET `intercompany_target_company` = NULL
                            WHERE `docstatus` = 0 AND (`is_intercompany` = 0 OR `is_intercompany` IS NULL)
                              AND `intercompany_target_company` IS NOT NULL AND `intercompany_target_company` != ''
                        """)
                except Exception:
                    pass

            try:
                if frappe.db.table_exists("Journal Entry Account") and frappe.db.has_column("Journal Entry Account", "intercompany_target_company"):
                    frappe.db.sql("""
                        UPDATE `tabJournal Entry Account` jeea
                        JOIN `tabJournal Entry` je ON je.name = jeea.parent
                        SET jeea.`intercompany_target_company` = NULL
                        WHERE je.`docstatus` = 0 AND (je.`is_intercompany` = 0 OR je.`is_intercompany` IS NULL)
                          AND jeea.`intercompany_target_company` IS NOT NULL AND jeea.`intercompany_target_company` != ''
                    """)
            except Exception:
                pass
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


@frappe.whitelist()
def download_user_guide_pdf():
    """Whitelisted endpoint allowing users to download the comprehensive PDF User Guide directly from ERPNext Desk."""
    import os
    app_path = frappe.get_app_path("inter_company_transactions")
    pdf_path = os.path.join(app_path, "public", "Inter_Company_Transactions_User_Guide.pdf")
    if not os.path.exists(pdf_path):
        try:
            from inter_company_transactions.generate_pdf_guide import create_pdf
            pdf_path = create_pdf()
        except Exception:
            pass

    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            filecontent = f.read()
        frappe.response["filename"] = "Inter_Company_Transactions_User_Guide.pdf"
        frappe.response["filecontent"] = filecontent
        frappe.response["type"] = "download"
    else:
        frappe.throw(_("User guide PDF file could not be found."))


@frappe.whitelist()
def get_intercompany_party_map(company=None):
    """
    Returns dynamic mapping of Customer and Supplier parties to their linked target companies.
    Structure:
    {
        "party_to_company": { party_name: target_company },
        "by_company": {
            company_name: {
                "customer": { customer_name: target_company },
                "supplier": { supplier_name: target_company },
                "all": { party_name: target_company }
            }
        },
        "universal": {
            "customer": { customer_name: target_company },
            "supplier": { supplier_name: target_company }
        }
    }
    """
    party_map = {
        "party_to_company": {},
        "by_company": {},
        "universal": {
            "customer": {},
            "supplier": {}
        }
    }

    if not (hasattr(frappe, "db") and frappe.db):
        return party_map

    try:
        if not frappe.db.table_exists("Intercompany Transaction Link"):
            return party_map

        links = frappe.get_all(
            "Intercompany Transaction Link",
            filters={"enabled": 1},
            fields=["name", "main_company"]
        )

        for link in links:
            main_co = link.main_company
            if not main_co:
                continue

            if main_co not in party_map["by_company"]:
                party_map["by_company"][main_co] = {
                    "customer": {},
                    "supplier": {},
                    "all": {}
                }

            if frappe.db.table_exists("Intercompany Linked Company"):
                linked_rows = frappe.get_all(
                    "Intercompany Linked Company",
                    filters={"parent": link.name},
                    fields=[
                        "company",
                        "main_company_customer",
                        "main_company_supplier",
                        "other_company_customer",
                        "other_company_supplier"
                    ]
                )

                for row in linked_rows:
                    other_co = row.company
                    if not other_co:
                        continue

                    if other_co not in party_map["by_company"]:
                        party_map["by_company"][other_co] = {
                            "customer": {},
                            "supplier": {},
                            "all": {}
                        }

                    # Main company perspective (user in main company selects party)
                    if row.main_company_customer:
                        party_map["by_company"][main_co]["customer"][row.main_company_customer] = other_co
                        party_map["by_company"][main_co]["all"][row.main_company_customer] = other_co
                        party_map["universal"]["customer"][row.main_company_customer] = other_co
                        party_map["party_to_company"][row.main_company_customer] = other_co

                    if row.main_company_supplier:
                        party_map["by_company"][main_co]["supplier"][row.main_company_supplier] = other_co
                        party_map["by_company"][main_co]["all"][row.main_company_supplier] = other_co
                        party_map["universal"]["supplier"][row.main_company_supplier] = other_co
                        party_map["party_to_company"][row.main_company_supplier] = other_co

                    # Other company perspective (user in other company selects party)
                    if row.other_company_customer:
                        party_map["by_company"][other_co]["customer"][row.other_company_customer] = main_co
                        party_map["by_company"][other_co]["all"][row.other_company_customer] = main_co
                        party_map["universal"]["customer"][row.other_company_customer] = main_co
                        party_map["party_to_company"][row.other_company_customer] = main_co

                    if row.other_company_supplier:
                        party_map["by_company"][other_co]["supplier"][row.other_company_supplier] = main_co
                        party_map["by_company"][other_co]["all"][row.other_company_supplier] = main_co
                        party_map["universal"]["supplier"][row.other_company_supplier] = main_co
                        party_map["party_to_company"][row.other_company_supplier] = main_co

    except Exception as e:
        frappe.log_error(f"Error fetching intercompany party map: {e!s}", "Intercompany Party Map")

    return party_map


def resolve_party_target_company(party_name, party_type=None, current_company=None, party_map=None):
    """Helper to determine target sister company for a given party"""
    if not party_name:
        return None
    if not party_map:
        party_map = get_intercompany_party_map(current_company)

    party_type_clean = (party_type or "").lower()

    # 1. Check company specific
    if current_company and current_company in party_map.get("by_company", {}):
        comp_dict = party_map["by_company"][current_company]
        if party_type_clean and party_type_clean in comp_dict and party_name in comp_dict[party_type_clean]:
            return comp_dict[party_type_clean][party_name]
        if party_name in comp_dict.get("all", {}):
            return comp_dict["all"][party_name]

    # 2. Check universal by party_type
    if party_type_clean and party_type_clean in party_map.get("universal", {}):
        tgt = party_map["universal"][party_type_clean].get(party_name)
        if tgt and tgt != current_company:
            return tgt

    # 3. Check party_to_company
    tgt = party_map.get("party_to_company", {}).get(party_name)
    if tgt and tgt != current_company:
        return tgt

    return None


def auto_detect_intercompany_party(doc, method=None):
    """
    Hooked on document validate/before_save:
    Automatically sets is_intercompany = 1 and intercompany_target_company
    when an intercompany customer or supplier is selected.
    For Journal Entry: inspects accounts rows and populates row & parent target company.
    """
    if not hasattr(doc, "doctype") or not doc.get("company"):
        return

    # If document was already created by the intercompany engine as a linked document, don't overwrite
    if doc.get("intercompany_linked_doc_name"):
        return

    # Respect the user's explicit choice on the "Is Intercompany" checkbox.
    # If the user has NOT checked it (is_intercompany is 0 or falsy), never
    # auto-enable intercompany based on party detection alone — this prevents
    # unintended mirror drafts in sister companies for regular business transactions.
    if not cint(doc.get("is_intercompany")):
        # User has explicitly left Is Intercompany unchecked.
        # Clear any stale target-company values to be 100% safe
        if doc.get("intercompany_target_company"):
            doc.intercompany_target_company = ""
        if doc.doctype == "Journal Entry":
            for row in doc.get("accounts") or []:
                if getattr(row, "intercompany_target_company", None):
                    row.intercompany_target_company = ""
        return

    company = doc.company
    party_map = get_intercompany_party_map(company)
    target_company = None

    if doc.doctype in ["Sales Order", "Sales Invoice", "Delivery Note", "Quotation"]:
        customer = doc.get("customer")
        if customer:
            target_company = resolve_party_target_company(customer, "customer", company, party_map)

    elif doc.doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt", "Supplier Quotation"]:
        supplier = doc.get("supplier")
        if supplier:
            target_company = resolve_party_target_company(supplier, "supplier", company, party_map)

    elif doc.doctype == "Payment Entry":
        party = doc.get("party")
        party_type = (doc.get("party_type") or "").lower()
        if party:
            target_company = resolve_party_target_company(party, party_type, company, party_map)

    elif doc.doctype == "Journal Entry":
        for row in doc.get("accounts") or []:
            row_party = row.get("party")
            row_party_type = (row.get("party_type") or "").lower()
            if row_party:
                row_target = resolve_party_target_company(row_party, row_party_type, company, party_map)
                if row_target and row_target != company:
                    if hasattr(row, "intercompany_target_company") or "intercompany_target_company" in row.as_dict():
                        row.intercompany_target_company = row_target
                    if not target_company:
                        target_company = row_target

    if target_company and target_company != company:
        if not doc.get("intercompany_target_company") or doc.get("intercompany_target_company") == company:
            doc.intercompany_target_company = target_company
    elif not doc.get("intercompany_target_company") or doc.get("intercompany_target_company") == company:
        doc.is_intercompany = 0
        doc.intercompany_target_company = ""
        if doc.doctype == "Journal Entry":
            for row in doc.get("accounts") or []:
                row.intercompany_target_company = ""


def backfill_sister_company_names():
    """
    Ensure all existing Intercompany Transaction Link records have their
    sister_company column populated and properly named/titled so list views
    display the Sister Company name instead of random hash IDs (e.g. pdlbej2fjb).
    """
    if not frappe.db.exists("DocType", "Intercompany Transaction Link"):
        return

    import re

    try:
        links = frappe.get_all(
            "Intercompany Transaction Link",
            fields=["name", "main_company", "sister_company"],
        )
    except Exception:
        return

    for link in links:
        child_rows = frappe.get_all(
            "Intercompany Linked Company",
            filters={"parent": link.name},
            fields=["company"],
            order_by="idx asc",
        )
        companies = [c.company for c in child_rows if c.company]
        sister_name = ", ".join(companies) if companies else ""

        if sister_name:
            if link.sister_company != sister_name:
                frappe.db.set_value(
                    "Intercompany Transaction Link",
                    link.name,
                    "sister_company",
                    sister_name,
                    update_modified=False,
                )

            # If the name is a legacy random hash (e.g. 10 chars like pdlbej2fjb, sh6m81t121)
            # and main_company is present, safely rename to clean readable format
            is_legacy_hash = bool(re.match(r"^[a-z0-9]{10}$", link.name))
            if is_legacy_hash and link.main_company:
                target_name = f"{link.main_company} - {sister_name}"[:130]
                if not frappe.db.exists("Intercompany Transaction Link", target_name):
                    try:
                        frappe.rename_doc(
                            "Intercompany Transaction Link",
                            link.name,
                            target_name,
                            force=True,
                            show_alert=False,
                        )
                    except Exception as e:
                        frappe.log_error(
                            f"Could not rename legacy link {link.name} to {target_name}: {e}",
                            "Intercompany Transaction Link Migration",
                        )

    frappe.db.commit()


