
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
        self.check_permission("write")
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
        Scans Chart of Accounts and auto-provisions Bank-typed TMP-<ABBR>
        Intercompany Clearing accounts for both Main Company and all Linked Companies.
        Also upgrades/replaces any legacy Temporary clearing account with a Bank account
        so Payment Entry and Journal Entry both work cleanly.
        """
        self.check_permission("write")
        created_count = 0
        linked_count = 0

        for row in (self.get("linked_companies") or []):
            if not row.company:
                continue

            # 1. Ensure Main Company has Bank/Cash TMP clearing account for this sister company
            main_acc = row.main_company_account
            main_acc_type = (
                frappe.db.get_value("Account", main_acc, "account_type")
                if main_acc and hasattr(frappe, "db") and frappe.db
                else None
            )
            if not main_acc or main_acc_type not in ("Bank", "Cash"):
                acc = get_or_create_intercompany_clearing_account(self.main_company, row.company)
                if acc and acc != main_acc:
                    row.main_company_account = acc
                    created_count += 1
                elif acc:
                    linked_count += 1
            else:
                linked_count += 1

            # 2. Ensure Sister Company has Bank/Cash TMP clearing account for main company
            other_acc = row.other_company_account
            other_acc_type = (
                frappe.db.get_value("Account", other_acc, "account_type")
                if other_acc and hasattr(frappe, "db") and frappe.db
                else None
            )
            if not other_acc or other_acc_type not in ("Bank", "Cash"):
                acc = get_or_create_intercompany_clearing_account(row.company, self.main_company)
                if acc and acc != other_acc:
                    row.other_company_account = acc
                    created_count += 1
                elif acc:
                    linked_count += 1
            else:
                linked_count += 1

        if not self.is_new() and created_count > 0:
            self.save(ignore_permissions=True)

        return {
            "created": created_count,
            "already_configured": linked_count,
            "message": _("Configured {0} Bank TMP clearing account(s) ({1} verified).").format(created_count, linked_count),
        }


def _get_intercompany_settings():
    """Safely load Inter Company Settings as a dict-like object with sensible defaults."""
    defaults = {
        "enabled": 1,
        "execution_mode": "Synchronous",
        "auto_submit_target_doc": 0,
        "auto_create_missing_items": 1,
        "tax_handling_strategy": "Mirror Net Rate Exactly",
        "default_transfer_pricing_rule": "Source Document Rate",
        "markup_percentage": 0.0,
        "notify_on_sync_failure": 1,
        "cancellation_authority": "Source Company Only (Strict Control)",
    }
    try:
        if hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Inter Company Settings"):
            settings = frappe.get_single("Inter Company Settings")
            if settings:
                return settings
    except Exception:
        pass
    return frappe._dict(defaults)


def _log_local_mirror_error(doc, target_company, target_doctype, error_message):
    """Record local intercompany mirroring failures into Inter Company Error Log."""
    try:
        if not (hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Inter Company Error Log")):
            return
        err_log = frappe.new_doc("Inter Company Error Log")
        err_log.source_doctype = getattr(doc, "doctype", "")
        err_log.source_name = getattr(doc, "name", "")
        err_log.source_company = getattr(doc, "company", "")
        err_log.target_company = target_company or getattr(doc, "intercompany_target_company", "")
        err_log.target_doctype = target_doctype or ""
        err_log.error_type = "Local Mirror"
        err_log.status = "Failed"
        err_log.error_message = str(error_message)[:1000]
        err_log.traceback = frappe.get_traceback()
        err_log.flags.ignore_permissions = True
        err_log.insert(ignore_permissions=True)
    except Exception:
        pass


def _execute_linked_documents(doc_doctype, doc_name):
    """Background worker entrypoint for asynchronous intercompany mirroring."""
    try:
        if not frappe.db.exists(doc_doctype, doc_name):
            return
        doc = frappe.get_doc(doc_doctype, doc_name)
        frappe.flags.ict_in_background = True
        create_linked_documents(doc, None)
    finally:
        frappe.flags.ict_in_background = False


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

    settings = _get_intercompany_settings()
    if not cint(settings.get("enabled", 1)):
        return

    # Prevent silent 1.0 fallback when submitting cross-currency vouchers
    validate_intercompany_cross_currency_rate(doc)

    if (
        settings.get("execution_mode") == "Asynchronous (Background Job)"
        and not getattr(frappe.flags, "in_test", False)
        and not getattr(frappe.flags, "ict_in_background", False)
    ):
        try:
            frappe.enqueue(
                "inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._execute_linked_documents",
                doc_doctype=doc.doctype,
                doc_name=doc.name,
                queue="default",
                now=False,
            )
            frappe.msgprint(
                _("Queued inter-company mirroring for {0} {1} in background.").format(doc.doctype, doc.name),
                alert=True,
            )
            return
        except Exception:
            pass

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
        target_comp = mapping.get("company")
        target_dt = mapping.get("target_doctype")
        try:
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

            linked_doc = create_corresponding_document(doc, mapping, direction, settings=settings)

            if linked_doc:
                # Ensure correct target company and immutable counterpart markers
                linked_doc.company = target_comp
                linked_doc.is_intercompany = 1
                linked_doc.intercompany_linked_doc_doctype = doc.doctype
                linked_doc.intercompany_linked_doc_name = doc.name
                linked_doc.intercompany_linked_company = doc.company
                linked_doc.intercompany_target_company = doc.company

                # Apply tax handling strategy cleanly and pre-calculate derived totals
                # so mirrored drafts are stored with valid amounts/totals and submit cleanly.
                if (
                    linked_doc.doctype in ("Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice")
                    and settings.get("tax_handling_strategy") == "Apply Target Company Tax Templates"
                ):
                    try:
                        if hasattr(linked_doc, "set_taxes"):
                            linked_doc.set_taxes()
                    except Exception:
                        pass

                _precalculate_mirrored_doc_totals(linked_doc)

                # Cross-company mirror creation: source submission is already authorized by an enabled
                # Intercompany Transaction Link, while target accountants may restrict direct User Permissions
                # across sister companies and complete local warehouse/cost-center fields in Draft first.
                linked_doc.flags.ignore_permissions = True
                linked_doc.flags.ignore_mandatory = True
                linked_doc.flags.ict_system_sync = True
                linked_doc.insert(ignore_permissions=True, ignore_mandatory=True)

                created_targets.add(dedup_key)
                create_document_reference(doc, linked_doc)

                should_auto_submit = bool(cint(settings.get("auto_submit_target_doc"))) or not bool(
                    cint(mapping["mapping"].get("auto_create_draft", 1))
                )
                status_label = "draft"
                if should_auto_submit and hasattr(linked_doc, "submit") and linked_doc.docstatus == 0:
                    try:
                        if hasattr(frappe.db, "savepoint"):
                            frappe.db.savepoint("ict_auto_submit")
                        linked_doc.flags.ignore_permissions = True
                        linked_doc.flags.ict_system_sync = True
                        linked_doc.submit()
                        status_label = "submitted"
                    except Exception as sub_err:
                        if hasattr(frappe.db, "rollback"):
                            try:
                                frappe.db.rollback(save_point="ict_auto_submit")
                            except Exception:
                                pass
                        frappe.log_error(
                            f"Auto-submit kept {linked_doc.doctype} {linked_doc.name} as draft: {sub_err!s}",
                            "Inter Company Auto Submit"
                        )

                frappe.msgprint(_("Created {0} {1} {2} in company {3}").format(
                    status_label, linked_doc.doctype, linked_doc.name, linked_doc.company
                ))

        except Exception as e:
            frappe.log_error(f"Error in intercompany creation for {doc.doctype} {doc.name}: {e!s}\n{frappe.get_traceback()}", "Inter Company Transaction Error")
            _log_local_mirror_error(doc, target_comp, target_dt, e)
            indicator = "red" if cint(settings.get("notify_on_sync_failure", 1)) else "orange"
            frappe.msgprint(
                _("Notice for linked company {0}: {1}").format(target_comp or "", str(e)),
                indicator=indicator,
                alert=bool(cint(settings.get("notify_on_sync_failure", 1))),
            )


def get_linked_counterpart_documents(doc):
    """
    Fetch all linked counterpart documents (both where doc is source and where doc is target).
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
                )
                for dn in dns:
                    if dn.parent and f"Delivery Note '{dn.parent}'" not in blocking_records:
                        blocking_records.append(f"Delivery Note '{dn.parent}'")

            if frappe.db.exists("DocType", "Sales Invoice Item"):
                sis = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"sales_order": docname, "docstatus": 1},
                    fields=["parent"],
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
                )
                for pr in prs:
                    if pr.parent and f"Purchase Receipt '{pr.parent}'" not in blocking_records:
                        blocking_records.append(f"Purchase Receipt '{pr.parent}'")

            if frappe.db.exists("DocType", "Purchase Invoice Item"):
                pis = frappe.get_all(
                    "Purchase Invoice Item",
                    filters={"purchase_order": docname, "docstatus": 1},
                    fields=["parent"],
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
                )
                for pi in pis:
                    if pi.parent and f"Purchase Invoice '{pi.parent}'" not in blocking_records:
                        blocking_records.append(f"Purchase Invoice '{pi.parent}'")
        except Exception as e:
            frappe.logger().error(f"Error checking Purchase Receipt downstream for {docname}: {e!s}")

    return blocking_records


def validate_intercompany_cancellation(doc, method=None):
    """
    Validates before cancellation:
    1. Enforces Cancellation Authority (Source Company Only vs Bidirectional).
    2. Ensures neither this document nor linked counterpart documents have active downstream
       payments, deliveries, receipts, or invoices.
    """
    if not hasattr(doc, "company") or not doc.company:
        return

    # Non-intercompany documents have no linked counterparts to validate
    if not cint(doc.get("is_intercompany")) and not doc.get("intercompany_linked_doc_name"):
        return

    if doc.flags.get("intercompany_auto_cancel"):
        return

    # Enforce configurable Cancellation Authority
    settings = _get_intercompany_settings()
    authority = (settings.get("cancellation_authority") or "Source Company Only (Strict Control)").strip()
    if authority.startswith("Source Company Only"):
        is_target_counterpart = bool(doc.get("intercompany_linked_doc_name"))
        source_info = None
        if is_target_counterpart:
            source_info = {
                "doctype": doc.get("intercompany_linked_doc_doctype") or "",
                "name": doc.get("intercompany_linked_doc_name") or "",
                "company": doc.get("intercompany_linked_company") or doc.get("intercompany_target_company") or "",
            }
        elif hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Inter Company Document Reference"):
            ref = frappe.db.get_value(
                "Inter Company Document Reference",
                {"target_doctype": doc.doctype, "target_name": doc.name, "target_company": doc.company},
                ["source_doctype", "source_name", "source_company"],
                as_dict=True,
            )
            if ref:
                is_target_counterpart = True
                source_info = {
                    "doctype": ref.source_doctype,
                    "name": ref.source_name,
                    "company": ref.source_company,
                }

        if is_target_counterpart and source_info:
            src_dt = source_info.get("doctype") or ""
            src_name = source_info.get("name") or ""
            is_remote_ref = False
            if hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Inter Company Document Reference"):
                if frappe.db.has_column("Inter Company Document Reference", "is_remote"):
                    is_remote_ref = bool(
                        frappe.db.get_value(
                            "Inter Company Document Reference",
                            {"target_doctype": doc.doctype, "target_name": doc.name, "is_remote": 1},
                            "name",
                        )
                    )

            source_still_active = True
            if (
                not is_remote_ref
                and src_dt
                and src_name
                and hasattr(frappe, "db")
                and frappe.db
                and frappe.db.exists("DocType", src_dt)
            ):
                if not frappe.db.exists(src_dt, src_name):
                    source_still_active = False
                else:
                    src_docstatus = frappe.db.get_value(src_dt, src_name, "docstatus")
                    if cint(src_docstatus) == 2:
                        source_still_active = False

            if source_still_active:
                esc = frappe.utils.escape_html
                frappe.throw(
                    _(
                        "<div style='font-size: 13px; line-height: 1.6;'>"
                        "<h4><b>Cancellation Restricted to Source Company</b></h4>"
                        "<b>{0} {1}</b> in company <b>{2}</b> is a mirrored inter-company entry "
                        "generated from <b>{3} {4}</b> in company <b>{5}</b>.<br><br>"
                        "Under current <b>Inter Company Settings</b> (<i>Source Company Only</i>), "
                        "only the originating company (<b>{5}</b>) can cancel or amend this transaction pair "
                        "so both ledgers remain 100% tallied.<br><br>"
                        "<b>Required Action:</b> Contact the accounting team in <b>{5}</b> "
                        "to cancel <b>{3} {4}</b> (which automatically cancels this entry), "
                        "or ask your Administrator to delete its link in <b>Inter Company Document Reference</b> "
                        "to manage it independently."
                        "</div>"
                    ).format(
                        esc(doc.doctype),
                        esc(doc.name),
                        esc(doc.company),
                        esc(src_dt),
                        esc(src_name),
                        esc(source_info.get("company") or _("Source Company")),
                    ),
                    title=_("Source Company Cancellation Authority"),
                )

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
            esc = frappe.utils.escape_html
            blocking_bullets = "".join([f"<li><b>{esc(b)}</b></li>" for b in blocking])
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
                ).format(
                    esc(doc.doctype),
                    esc(doc.name),
                    esc(c_doctype),
                    esc(c_name),
                    esc(c_company),
                    blocking_bullets,
                ),
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


def _clear_mirrored_link_markers(doctype, docname):
    """Clear intercompany_linked_doc_* markers on a document so it is no longer locked to a deleted counterpart."""
    if not doctype or not docname or not (hasattr(frappe, "db") and frappe.db):
        return
    if not frappe.db.exists(doctype, docname):
        return
    updates = {}
    for fn in ("intercompany_linked_doc_doctype", "intercompany_linked_doc_name", "intercompany_linked_company"):
        if frappe.db.has_column(doctype, fn):
            if frappe.db.get_value(doctype, docname, fn):
                updates[fn] = ""
    if updates:
        frappe.db.set_value(doctype, docname, updates, update_modified=False)


def cleanup_intercompany_links_on_trash(doc, method=None):
    """
    Hooked on on_trash across supported transaction DocTypes.
    1. Prevents LinkExistsError ('Cannot delete or cancel because ... is linked with Inter Company Document Reference')
       by purging audit tracking rows when a cancelled or draft voucher is permanently deleted.
    2. Unlinks any surviving target counterpart when the source document is permanently deleted so the
       counterpart is never trapped with a dead reference.
    """
    if not hasattr(doc, "doctype") or not getattr(doc, "name", None):
        return
    if not (hasattr(frappe, "db") and frappe.db):
        return

    try:
        if frappe.db.exists("DocType", "Inter Company Document Reference"):
            ref_rows = frappe.db.sql(
                """
                SELECT name, source_doctype, source_name, target_doctype, target_name
                FROM `tabInter Company Document Reference`
                WHERE (source_doctype = %s AND source_name = %s)
                   OR (target_doctype = %s AND target_name = %s)
                """,
                (doc.doctype, doc.name, doc.doctype, doc.name),
                as_dict=True,
            )
            for ref in (ref_rows or []):
                ref_name = ref.get("name") if isinstance(ref, dict) else ref
                if isinstance(ref, dict) and ref.get("source_doctype") == doc.doctype and ref.get("source_name") == doc.name:
                    _clear_mirrored_link_markers(ref.get("target_doctype"), ref.get("target_name"))
                if ref_name:
                    frappe.delete_doc(
                        "Inter Company Document Reference",
                        ref_name,
                        ignore_permissions=True,
                        force=True,
                    )

        if frappe.db.exists("DocType", "Inter Company Error Log"):
            err_names = frappe.db.sql(
                """
                SELECT name FROM `tabInter Company Error Log`
                WHERE (source_doctype = %s AND source_name = %s)
                   OR (target_doctype = %s AND target_name = %s)
                """,
                (doc.doctype, doc.name, doc.doctype, doc.name),
                pluck=True,
            )
            for err_name in (err_names or []):
                frappe.delete_doc(
                    "Inter Company Error Log",
                    err_name,
                    ignore_permissions=True,
                    force=True,
                )
    except Exception as e:
        frappe.logger().warning(f"Non-fatal cleanup warning on trash for {doc.doctype} {doc.name}: {e!s}")


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
        if doc.doctype == "Landed Cost Voucher" and target_doctype == "Journal Entry":
            return
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
    if getattr(doc, "doctype", "") == "Landed Cost Voucher":
        return

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
    Finds the appropriate parent group account for an Intercompany TMP Clearing account
    under Bank Accounts -> Current Assets -> Asset for the given company.
    """
    if not company or not (hasattr(frappe, "db") and frappe.db):
        return None

    # 1. Prefer 'Bank Accounts' group under Asset so child Bank accounts align with ERPNext CoA
    parent = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "is_group": 1,
            "root_type": "Asset",
            "account_name": ["in", ["Bank Accounts", "Bank Account"]],
        },
        "name",
    )
    if not parent:
        parent = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "is_group": 1,
                "root_type": "Asset",
                "account_name": ["like", "%Bank%"],
            },
            "name",
        )

    # 2. Fallback to 'Current Assets' group
    if not parent:
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

    # 3. Final fallback to any non-root Asset group account
    if not parent:
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


def _get_company_abbr_token(company):
    """Return company abbr (preferred) or sanitized uppercase token for TMP-<ABBR> naming."""
    if not company:
        return "IC"
    abbr = None
    if hasattr(frappe, "db") and frappe.db:
        try:
            abbr = frappe.db.get_value("Company", company, "abbr")
        except Exception:
            abbr = None
    if abbr and str(abbr).strip():
        return str(abbr).strip()
    import re
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(company)).upper()
    return (cleaned[:6] or "IC")


def find_existing_clearing_account(company, sister_company=None):
    """
    Scans the Chart of Accounts of `company` for an existing Bank/Cash intercompany
    clearing account mapped to `sister_company` (preferring TMP-<ABBR> naming).
    Only returns Bank or Cash accounts so Payment Entry and Journal Entry both succeed.
    """
    if not company or not (hasattr(frappe, "db") and frappe.db):
        return None

    sister_clean = (sister_company or "").strip()
    sister_abbr = _get_company_abbr_token(sister_clean) if sister_clean else None

    search_patterns = []
    if sister_abbr:
        search_patterns.extend([
            f"TMP-{sister_abbr}",
            f"TMP-{sister_abbr}%",
            f"TMP {sister_abbr}%",
            f"TMP - {sister_abbr}%",
        ])
    if sister_clean:
        search_patterns.extend([
            f"%TMP%{sister_clean}%",
            f"%Intercompany%{sister_clean}%",
        ])

    for pat in search_patterns:
        op = "=" if "%" not in pat else "like"
        candidate = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "is_group": 0,
                "account_type": ["in", ["Bank", "Cash"]],
                "account_name": [op, pat] if op == "like" else pat,
            },
            "name",
        )
        if candidate:
            return candidate

    return None


def get_or_create_intercompany_clearing_account(company, sister_company):
    """
    Scans Chart of Accounts for an existing Bank/Cash TMP clearing account for `sister_company`,
    or creates a Bank-typed `TMP-<COUNTERPARTY ABBR>` clearing account under Bank Accounts / Current Assets.
    Bank-typed accounts allow BOTH Payment Entry and Journal Entry without validation errors.
    """
    if not company:
        return None

    # 1. Scan Chart of Accounts for an already-valid Bank/Cash TMP clearing account
    existing_valid = find_existing_clearing_account(company, sister_company)
    if existing_valid:
        return existing_valid

    sister_clean = (sister_company or "").strip()
    sister_abbr = _get_company_abbr_token(sister_clean) if sister_clean else "IC"
    acc_label = f"TMP-{sister_abbr}"

    # 2. Check if an account named TMP-<ABBR> already exists (e.g. legacy Temporary type)
    if hasattr(frappe, "db") and frappe.db:
        existing_same_name = frappe.db.get_value(
            "Account",
            {"company": company, "is_group": 0, "account_name": acc_label},
            ["name", "account_type"],
            as_dict=True,
        )
        if existing_same_name:
            if existing_same_name.account_type in ("Bank", "Cash"):
                return existing_same_name.name
            # Attempt safe upgrade of legacy Temporary account to Bank if allowed
            try:
                frappe.db.set_value("Account", existing_same_name.name, "account_type", "Bank")
                return existing_same_name.name
            except Exception:
                acc_label = f"TMP-{sister_abbr}-Bank"

    # 3. Auto-create Bank-typed TMP-<ABBR> account in Chart of Accounts
    try:
        parent_account = get_parent_clearing_account(company)
        if not parent_account:
            return frappe.db.get_value("Company", company, "default_bank_account") or frappe.db.get_value("Company", company, "default_cash_account")

        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": acc_label,
            "company": company,
            "parent_account": parent_account,
            "root_type": "Asset",
            "account_type": "Bank",
            "is_group": 0,
        })
        acc.flags.ignore_permissions = True
        acc.flags.ignore_mandatory = True
        acc.insert()
        return acc.name
    except Exception as e:
        frappe.log_error(f"Error auto-creating intercompany TMP Bank account in {company}: {e}", "Intercompany Accounting")
        return frappe.db.get_value("Company", company, "default_bank_account") or frappe.db.get_value("Company", company, "default_cash_account")


@frappe.whitelist()
def scan_linked_company_defaults(main_company, other_company):
    """
    Read-only CoA & Party scanner for Intercompany Linked Company rows.
    Finds matching internal Customers/Suppliers, existing Bank/Cash TMP-<ABBR> clearing accounts,
    and transit warehouses for the exact (main_company, other_company) pair.
    """
    result = {
        "main_company_customer": None,
        "main_company_supplier": None,
        "main_company_account": None,
        "main_company_warehouse": None,
        "other_company_customer": None,
        "other_company_supplier": None,
        "other_company_account": None,
        "other_company_warehouse": None,
        "main_suggested_tmp": f"TMP-{_get_company_abbr_token(other_company)}" if other_company else None,
        "other_suggested_tmp": f"TMP-{_get_company_abbr_token(main_company)}" if main_company else None,
    }
    if not main_company or not other_company or not (hasattr(frappe, "db") and frappe.db):
        return result

    def _find_internal_party(owner_co, counterparty_co, party_dt):
        if not frappe.db.table_exists(party_dt):
            return None
        if party_dt == "Customer":
            rows = frappe.db.sql(
                """
                SELECT p.name
                FROM `tabCustomer` p
                WHERE (p.disabled IS NULL OR p.disabled = 0)
                  AND p.`is_internal_customer` = 1
                  AND p.represents_company = %s
                ORDER BY
                  EXISTS (
                    SELECT 1 FROM `tabAllowed To Transact With` att
                    WHERE att.parent = p.name AND att.parenttype = %s AND att.company = %s
                  ) DESC,
                  p.modified DESC
                LIMIT 1
                """,
                (counterparty_co, party_dt, owner_co),
                as_dict=True,
            )
        elif party_dt == "Supplier":
            rows = frappe.db.sql(
                """
                SELECT p.name
                FROM `tabSupplier` p
                WHERE (p.disabled IS NULL OR p.disabled = 0)
                  AND p.`is_internal_supplier` = 1
                  AND p.represents_company = %s
                ORDER BY
                  EXISTS (
                    SELECT 1 FROM `tabAllowed To Transact With` att
                    WHERE att.parent = p.name AND att.parenttype = %s AND att.company = %s
                  ) DESC,
                  p.modified DESC
                LIMIT 1
                """,
                (counterparty_co, party_dt, owner_co),
                as_dict=True,
            )
        else:
            return None
        return rows[0].name if rows else None

    result["main_company_customer"] = _find_internal_party(main_company, other_company, "Customer")
    result["main_company_supplier"] = _find_internal_party(main_company, other_company, "Supplier")
    result["other_company_customer"] = _find_internal_party(other_company, main_company, "Customer")
    result["other_company_supplier"] = _find_internal_party(other_company, main_company, "Supplier")

    result["main_company_account"] = find_existing_clearing_account(main_company, other_company)
    result["other_company_account"] = find_existing_clearing_account(other_company, main_company)
    result["main_company_warehouse"] = get_intercompany_warehouse(main_company)
    result["other_company_warehouse"] = get_intercompany_warehouse(other_company)

    return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def intercompany_party_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Filters Customer or Supplier link dropdowns inside Intercompany Linked Company
    to active parties belonging to / allowed in the selected company (`Main Company` or row `Company`).
    Prioritizes internal parties linked to the counterparty company without hiding standard parties.
    """
    if doctype not in ("Customer", "Supplier"):
        return []

    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    owner_company = (filters.get("company") or "").strip()
    rep_company = (filters.get("represents_company") or "").strip()

    params = {
        "txt": f"%{txt or ''}%",
        "start": cint(start),
        "page_len": cint(page_len) or 20,
        "dt": doctype,
        "owner_company": owner_company,
        "rep_company": rep_company,
        "rep_like": f"%{rep_company}%" if rep_company else "",
    }

    has_company_col = bool(
        hasattr(frappe, "db") and frappe.db and frappe.db.has_column(doctype, "company")
    )
    has_party_account = bool(
        hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Party Account")
    )
    has_att = bool(
        hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Allowed To Transact With")
    )

    if not owner_company:
        if doctype == "Customer":
            return frappe.db.sql(
                """
                SELECT p.name, p.`customer_name`, p.represents_company
                FROM `tabCustomer` p
                WHERE (p.disabled IS NULL OR p.disabled = 0)
                  AND (p.name LIKE %(txt)s OR p.`customer_name` LIKE %(txt)s)
                ORDER BY
                    (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                    (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`customer_name` LIKE %(rep_like)s)) DESC,
                    p.modified DESC,
                    p.name ASC
                LIMIT %(start)s, %(page_len)s
                """,
                params,
            )
        return frappe.db.sql(
            """
            SELECT p.name, p.`supplier_name`, p.represents_company
            FROM `tabSupplier` p
            WHERE (p.disabled IS NULL OR p.disabled = 0)
              AND (p.name LIKE %(txt)s OR p.`supplier_name` LIKE %(txt)s)
            ORDER BY
                (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`supplier_name` LIKE %(rep_like)s)) DESC,
                p.modified DESC,
                p.name ASC
            LIMIT %(start)s, %(page_len)s
            """,
            params,
        )

    if has_att and has_party_account:
        if doctype == "Customer":
            if has_company_col:
                return frappe.db.sql(
                    """
                    SELECT p.name, p.`customer_name`, p.represents_company
                    FROM `tabCustomer` p
                    WHERE (p.disabled IS NULL OR p.disabled = 0)
                      AND (p.represents_company IS NULL OR p.represents_company = '' OR p.represents_company != %(owner_company)s)
                      AND (
                        p.company = %(owner_company)s
                        OR EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att WHERE att.parent = p.name AND att.parenttype = %(dt)s AND att.company = %(owner_company)s)
                        OR EXISTS (SELECT 1 FROM `tabParty Account` pa WHERE pa.parent = p.name AND pa.parenttype = %(dt)s AND pa.company = %(owner_company)s)
                        OR ((p.company IS NULL OR p.company = '') AND NOT EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att_other WHERE att_other.parent = p.name AND att_other.parenttype = %(dt)s))
                      )
                      AND (p.name LIKE %(txt)s OR p.`customer_name` LIKE %(txt)s)
                    ORDER BY
                        (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                        (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`customer_name` LIKE %(rep_like)s)) DESC,
                        (p.company = %(owner_company)s) DESC,
                        EXISTS (SELECT 1 FROM `tabParty Account` pa2 WHERE pa2.parent = p.name AND pa2.parenttype = %(dt)s AND pa2.company = %(owner_company)s) DESC,
                        p.modified DESC,
                        p.name ASC
                    LIMIT %(start)s, %(page_len)s
                    """,
                    params,
                )
            return frappe.db.sql(
                """
                SELECT p.name, p.`customer_name`, p.represents_company
                FROM `tabCustomer` p
                WHERE (p.disabled IS NULL OR p.disabled = 0)
                  AND (p.represents_company IS NULL OR p.represents_company = '' OR p.represents_company != %(owner_company)s)
                  AND (
                    EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att WHERE att.parent = p.name AND att.parenttype = %(dt)s AND att.company = %(owner_company)s)
                    OR EXISTS (SELECT 1 FROM `tabParty Account` pa WHERE pa.parent = p.name AND pa.parenttype = %(dt)s AND pa.company = %(owner_company)s)
                    OR NOT EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att_other WHERE att_other.parent = p.name AND att_other.parenttype = %(dt)s)
                  )
                  AND (p.name LIKE %(txt)s OR p.`customer_name` LIKE %(txt)s)
                ORDER BY
                    (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                    (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`customer_name` LIKE %(rep_like)s)) DESC,
                    EXISTS (SELECT 1 FROM `tabParty Account` pa2 WHERE pa2.parent = p.name AND pa2.parenttype = %(dt)s AND pa2.company = %(owner_company)s) DESC,
                    p.modified DESC,
                    p.name ASC
                LIMIT %(start)s, %(page_len)s
                """,
                params,
            )

        if has_company_col:
            return frappe.db.sql(
                """
                SELECT p.name, p.`supplier_name`, p.represents_company
                FROM `tabSupplier` p
                WHERE (p.disabled IS NULL OR p.disabled = 0)
                  AND (p.represents_company IS NULL OR p.represents_company = '' OR p.represents_company != %(owner_company)s)
                  AND (
                    p.company = %(owner_company)s
                    OR EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att WHERE att.parent = p.name AND att.parenttype = %(dt)s AND att.company = %(owner_company)s)
                    OR EXISTS (SELECT 1 FROM `tabParty Account` pa WHERE pa.parent = p.name AND pa.parenttype = %(dt)s AND pa.company = %(owner_company)s)
                    OR ((p.company IS NULL OR p.company = '') AND NOT EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att_other WHERE att_other.parent = p.name AND att_other.parenttype = %(dt)s))
                  )
                  AND (p.name LIKE %(txt)s OR p.`supplier_name` LIKE %(txt)s)
                ORDER BY
                    (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                    (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`supplier_name` LIKE %(rep_like)s)) DESC,
                    (p.company = %(owner_company)s) DESC,
                    EXISTS (SELECT 1 FROM `tabParty Account` pa2 WHERE pa2.parent = p.name AND pa2.parenttype = %(dt)s AND pa2.company = %(owner_company)s) DESC,
                    p.modified DESC,
                    p.name ASC
                LIMIT %(start)s, %(page_len)s
                """,
                params,
            )
        return frappe.db.sql(
            """
            SELECT p.name, p.`supplier_name`, p.represents_company
            FROM `tabSupplier` p
            WHERE (p.disabled IS NULL OR p.disabled = 0)
              AND (p.represents_company IS NULL OR p.represents_company = '' OR p.represents_company != %(owner_company)s)
              AND (
                EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att WHERE att.parent = p.name AND att.parenttype = %(dt)s AND att.company = %(owner_company)s)
                OR EXISTS (SELECT 1 FROM `tabParty Account` pa WHERE pa.parent = p.name AND pa.parenttype = %(dt)s AND pa.company = %(owner_company)s)
                OR NOT EXISTS (SELECT 1 FROM `tabAllowed To Transact With` att_other WHERE att_other.parent = p.name AND att_other.parenttype = %(dt)s)
              )
              AND (p.name LIKE %(txt)s OR p.`supplier_name` LIKE %(txt)s)
            ORDER BY
                (%(rep_company)s != '' AND p.represents_company = %(rep_company)s) DESC,
                (%(rep_company)s != '' AND (p.name LIKE %(rep_like)s OR p.`supplier_name` LIKE %(rep_like)s)) DESC,
                EXISTS (SELECT 1 FROM `tabParty Account` pa2 WHERE pa2.parent = p.name AND pa2.parenttype = %(dt)s AND pa2.company = %(owner_company)s) DESC,
                p.modified DESC,
                p.name ASC
            LIMIT %(start)s, %(page_len)s
            """,
            params,
        )

    # Fallback when optional ERPNext tables (Allowed To Transact With / Party Account) are absent
    name_col = "customer_name" if doctype == "Customer" else "supplier_name"
    rows = frappe.get_all(
        doctype,
        filters={"disabled": ["in", [0, None]]},
        or_filters=[[doctype, "name", "like", params["txt"]], [doctype, name_col, "like", params["txt"]]],
        fields=["name", name_col, "represents_company"],
        order_by="modified desc, name asc",
        start=params["start"],
        page_length=params["page_len"],
    )
    return [
        (r.get("name"), r.get(name_col), r.get("represents_company"))
        for r in (rows or [])
        if (r.get("represents_company") or "") != owner_company
    ]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def intercompany_account_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Filters Account dropdowns inside Intercompany Linked Company strictly to
    active non-group accounts belonging to the selected company, prioritizing TMP / Bank accounts.
    """
    if doctype != "Account":
        return []

    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    company = (filters.get("company") or "").strip()

    params = {
        "txt": f"%{txt or ''}%",
        "start": cint(start),
        "page_len": cint(page_len) or 20,
    }
    if company:
        params["company"] = company
        return frappe.db.sql(
            """
            SELECT a.name, a.account_type, a.account_currency
            FROM `tabAccount` a
            WHERE a.is_group = 0
              AND (a.disabled IS NULL OR a.disabled = 0)
              AND a.company = %(company)s
              AND (a.name LIKE %(txt)s OR a.account_name LIKE %(txt)s)
            ORDER BY
                (a.account_name LIKE 'TMP%%') DESC,
                (a.account_name LIKE '%%Intercompany%%') DESC,
                (a.account_type IN ('Bank', 'Cash')) DESC,
                a.name ASC
            LIMIT %(start)s, %(page_len)s
            """,
            params,
        )

    return frappe.db.sql(
        """
        SELECT a.name, a.account_type, a.account_currency
        FROM `tabAccount` a
        WHERE a.is_group = 0
          AND (a.disabled IS NULL OR a.disabled = 0)
          AND (a.name LIKE %(txt)s OR a.account_name LIKE %(txt)s)
        ORDER BY
            (a.account_name LIKE 'TMP%%') DESC,
            (a.account_name LIKE '%%Intercompany%%') DESC,
            (a.account_type IN ('Bank', 'Cash')) DESC,
            a.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        params,
    )


def _normalize_tx_date(transaction_date=None):
    """Safely convert date/datetime/ISO/DD-MM-YYYY strings to YYYY-MM-DD."""
    if not transaction_date:
        return str(nowdate())
    try:
        return str(getdate(transaction_date))
    except Exception:
        from datetime import datetime
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(transaction_date).strip()[:10], fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        return str(nowdate())


def lookup_intercompany_exchange_rate(from_currency, to_currency, transaction_date=None):
    """
    Silently queries Currency Exchange in both forward and inverse (1 / rate) directions
    without triggering erpnext.setup.utils.get_exchange_rate msgprint popups.
    Returns float (9 decimals) or None if no Currency Exchange record exists.
    """
    from_ccy = (str(from_currency).strip().upper() if from_currency else "")
    to_ccy = (str(to_currency).strip().upper() if to_currency else "")
    if not from_ccy or not to_ccy or from_ccy == to_ccy:
        return 1.0

    if not (hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Currency Exchange")):
        return None

    tx_date = _normalize_tx_date(transaction_date)

    try:
        # 1. Exact forward match on or before transaction_date
        fwd = frappe.get_all(
            "Currency Exchange",
            filters={
                "from_currency": from_ccy,
                "to_currency": to_ccy,
                "date": ["<=", tx_date],
            },
            fields=["exchange_rate"],
            order_by="date desc",
            limit=1,
        )
        if fwd and flt(fwd[0].get("exchange_rate")) > 0:
            return flt(fwd[0].get("exchange_rate"), 9)

        # 2. Inverse match on or before transaction_date (e.g. USD->PKR when PKR->USD requested)
        inv = frappe.get_all(
            "Currency Exchange",
            filters={
                "from_currency": to_ccy,
                "to_currency": from_ccy,
                "date": ["<=", tx_date],
            },
            fields=["exchange_rate"],
            order_by="date desc",
            limit=1,
        )
        if inv and flt(inv[0].get("exchange_rate")) > 0:
            return flt(1.0 / flt(inv[0].get("exchange_rate")), 9)

        # 3. Fallback to latest available record regardless of date
        fwd_any = frappe.get_all(
            "Currency Exchange",
            filters={"from_currency": from_ccy, "to_currency": to_ccy},
            fields=["exchange_rate"],
            order_by="date desc",
            limit=1,
        )
        if fwd_any and flt(fwd_any[0].get("exchange_rate")) > 0:
            return flt(fwd_any[0].get("exchange_rate"), 9)

        inv_any = frappe.get_all(
            "Currency Exchange",
            filters={"from_currency": to_ccy, "to_currency": from_ccy},
            fields=["exchange_rate"],
            order_by="date desc",
            limit=1,
        )
        if inv_any and flt(inv_any[0].get("exchange_rate")) > 0:
            return flt(1.0 / flt(inv_any[0].get("exchange_rate")), 9)
    except Exception as e:
        frappe.logger().warning(f"Currency Exchange lookup error ({from_ccy}->{to_ccy} on {tx_date}): {e!s}")

    # 4. Optional fallback to ERPNext HTTP Currency Exchange Settings if explicitly enabled
    try:
        if frappe.db.exists("DocType", "Currency Exchange Settings"):
            use_http = frappe.db.get_single_value("Currency Exchange Settings", "use_httpclient")
            if cint(use_http):
                from erpnext.setup.utils import get_exchange_rate
                prev_mute = getattr(frappe.flags, "mute_messages", False)
                frappe.flags.mute_messages = True
                try:
                    ext_rate = flt(get_exchange_rate(from_ccy, to_ccy, tx_date), 9)
                    if ext_rate > 0 and ext_rate != 1.0:
                        return ext_rate
                finally:
                    frappe.flags.mute_messages = prev_mute
    except Exception:
        pass

    return None


def extract_document_exchange_rate(doc, from_currency, to_currency):
    """
    Extracts an explicit exchange rate already specified on the source voucher itself
    (e.g., Journal Entry row exchange_rate=275 for USD row in PKR company, or SO/PO conversion_rate=275).
    Returns flt(rate, 9) if found, else None.
    """
    if not doc or not from_currency or not to_currency:
        return None
    if from_currency == to_currency:
        return 1.0

    src_company = getattr(doc, "company", None) or (doc.get("company") if isinstance(doc, dict) else None)
    src_company_ccy = (
        frappe.db.get_value("Company", src_company, "default_currency")
        if src_company and hasattr(frappe, "db") and frappe.db
        else None
    )

    # 1. Sales / Purchase Orders, Invoices, Quotations, DN, PR
    doc_ccy = getattr(doc, "currency", None) or (doc.get("currency") if isinstance(doc, dict) else None)
    conv_rate = flt(getattr(doc, "conversion_rate", 0) or (doc.get("conversion_rate", 0) if isinstance(doc, dict) else 0))
    if doc_ccy and src_company_ccy and doc_ccy != src_company_ccy and conv_rate > 0:
        # ERPNext conversion_rate represents 1 doc_ccy = conv_rate src_company_ccy
        if from_currency == doc_ccy and to_currency == src_company_ccy:
            return flt(conv_rate, 9)
        if from_currency == src_company_ccy and to_currency == doc_ccy:
            return flt(1.0 / conv_rate, 9)

    # 2. Payment Entry (source_exchange_rate: paid_from -> company_ccy, target_exchange_rate: paid_to -> company_ccy)
    if (getattr(doc, "doctype", None) or (doc.get("doctype") if isinstance(doc, dict) else None)) == "Payment Entry":
        p_from_ccy = getattr(doc, "paid_from_account_currency", None)
        p_to_ccy = getattr(doc, "paid_to_account_currency", None)
        src_fx = flt(getattr(doc, "source_exchange_rate", 0))
        tgt_fx = flt(getattr(doc, "target_exchange_rate", 0))
        if p_from_ccy and src_company_ccy and p_from_ccy != src_company_ccy and src_fx > 0:
            if from_currency == p_from_ccy and to_currency == src_company_ccy:
                return flt(src_fx, 9)
            if from_currency == src_company_ccy and to_currency == p_from_ccy:
                return flt(1.0 / src_fx, 9)
        if p_to_ccy and src_company_ccy and p_to_ccy != src_company_ccy and tgt_fx > 0:
            if from_currency == p_to_ccy and to_currency == src_company_ccy:
                return flt(tgt_fx, 9)
            if from_currency == src_company_ccy and to_currency == p_to_ccy:
                return flt(1.0 / tgt_fx, 9)

    # 3. Journal Entry Account rows (row.account_currency + row.exchange_rate)
    rows = getattr(doc, "accounts", None) or (doc.get("accounts") if isinstance(doc, dict) else None) or []
    for row in rows:
        r_ccy = getattr(row, "account_currency", None) or (row.get("account_currency") if isinstance(row, dict) else None)
        r_fx = flt(getattr(row, "exchange_rate", 0) or (row.get("exchange_rate", 0) if isinstance(row, dict) else 0))
        if r_ccy and src_company_ccy and r_ccy != src_company_ccy and r_fx > 0:
            if from_currency == r_ccy and to_currency == src_company_ccy:
                return flt(r_fx, 9)
            if from_currency == src_company_ccy and to_currency == r_ccy:
                return flt(1.0 / r_fx, 9)

    return None


def get_intercompany_exchange_rate(from_currency, to_currency, transaction_date=None, raise_if_missing=False):
    """
    Safely resolve the exchange rate from `from_currency` to `to_currency`.
    Queries Currency Exchange in both directions cleanly without trigger msgprint spam.
    """
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0

    rate = lookup_intercompany_exchange_rate(from_currency, to_currency, transaction_date)
    if rate and flt(rate) > 0:
        return flt(rate, 9)

    if raise_if_missing:
        frappe.throw(
            _(
                "Currency Exchange rate between <b>{0}</b> and <b>{1}</b> for date <b>{2}</b> is required "
                "so both intercompany ledgers stay 100% tallied. Please add the exchange rate first."
            ).format(from_currency, to_currency, transaction_date or nowdate()),
            title=_("Exchange Rate Required"),
        )

    return 1.0


@frappe.whitelist()
def check_intercompany_exchange_rate(
    source_company,
    target_company,
    transaction_date=None,
    doc_currency=None,
    conversion_rate=None,
):
    """
    Used by Desk JS before saving a cross-currency intercompany voucher.
    Returns whether an exchange rate is required and whether a valid rate exists.
    """
    if not source_company or not target_company or source_company == target_company:
        return {"required": False, "has_rate": True}

    if not (hasattr(frappe, "db") and frappe.db):
        return {"required": False, "has_rate": True}

    src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
    tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
    if not src_ccy or not tgt_ccy or src_ccy == tgt_ccy:
        return {
            "required": False,
            "has_rate": True,
            "from_currency": src_ccy,
            "to_currency": tgt_ccy,
        }

    tx_date = _normalize_tx_date(transaction_date)
    rate = None
    if doc_currency == tgt_ccy and flt(conversion_rate) > 0:
        rate = flt(1.0 / flt(conversion_rate), 9)
    else:
        rate = lookup_intercompany_exchange_rate(src_ccy, tgt_ccy, tx_date)

    return {
        "required": True,
        "has_rate": bool(rate and flt(rate) > 0),
        "from_currency": src_ccy,
        "to_currency": tgt_ccy,
        "exchange_rate": flt(rate, 9) if rate else None,
        "inverse_rate": flt(1.0 / flt(rate), 9) if rate else None,
        "transaction_date": tx_date,
    }


def validate_stock_entry_same_currency(source_company, target_company):
    """
    Restricts intercompany Stock Entry strictly to companies sharing the same default currency.
    """
    if not source_company or not target_company or source_company == target_company:
        return
    if not (hasattr(frappe, "db") and frappe.db):
        return

    src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
    tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
    if src_ccy and tgt_ccy and src_ccy != tgt_ccy:
        frappe.throw(
            _(
                "Inter-Company <b>Stock Entry</b> works for <b>Same-Currency companies only</b>.<br><br>"
                "<b>{0}</b> uses <b>{1}</b> while <b>{2}</b> uses <b>{3}</b>.<br><br>"
                "Because ERPNext Stock Entry has no currency or exchange rate field, please use "
                "<b>Delivery Note &rarr; Purchase Receipt</b> or <b>Sales Invoice &rarr; Purchase Invoice</b> "
                "for transfers between companies with different currencies."
            ).format(source_company, src_ccy, target_company, tgt_ccy),
            title=_("Same-Currency Only for Stock Entry"),
        )


@frappe.whitelist()
def check_stock_entry_same_currency(source_company, target_company):
    """
    Client-callable check confirming both companies share the same currency for Stock Entry.
    """
    if not source_company or not target_company or source_company == target_company:
        return {"allowed": True}
    if not (hasattr(frappe, "db") and frappe.db):
        return {"allowed": True}

    src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
    tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
    allowed = not (src_ccy and tgt_ccy and src_ccy != tgt_ccy)
    return {
        "allowed": allowed,
        "source_currency": src_ccy,
        "target_currency": tgt_ccy,
    }


@frappe.whitelist()
def save_intercompany_currency_exchange(from_currency, to_currency, exchange_rate, date=None):
    """
    Saves a Currency Exchange record from the guided Exchange Rate modal dialog.
    """
    frappe.has_permission("Currency Exchange", "create", throw=True)
    rate = flt(exchange_rate)
    if rate <= 0:
        frappe.throw(_("Exchange rate must be greater than zero."))
    if not from_currency or not to_currency or from_currency == to_currency:
        frappe.throw(_("From Currency and To Currency must be different."))

    tx_date = _normalize_tx_date(date)
    existing = frappe.db.get_value(
        "Currency Exchange",
        {"date": tx_date, "from_currency": from_currency, "to_currency": to_currency},
        "name",
    )
    if existing:
        frappe.db.set_value("Currency Exchange", existing, "exchange_rate", flt(rate, 9))
        name = existing
    else:
        ce = frappe.get_doc({
            "doctype": "Currency Exchange",
            "date": tx_date,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange_rate": flt(rate, 9),
            "for_buying": 1,
            "for_selling": 1,
        })
        ce.insert(ignore_permissions=True)
        name = ce.name

    return {
        "success": True,
        "name": name,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "exchange_rate": flt(rate, 9),
        "inverse_rate": flt(1.0 / rate, 9),
        "date": tx_date,
    }


def validate_intercompany_cross_currency_rate(doc):
    """
    Blocks saving/submitting a source intercompany document across companies with different
    default currencies unless a valid exchange rate exists on the document OR in Currency Exchange.
    Guarantees Company A and Company B ledgers never silently fall back to 1.0.
    """
    if not doc or not cint(doc.get("is_intercompany")):
        return
    if doc.get("intercompany_linked_doc_name"):
        return

    source_company = doc.get("company")
    target_company = doc.get("intercompany_target_company")
    if not source_company or not target_company or source_company == target_company:
        return
    if not (hasattr(frappe, "db") and frappe.db):
        return

    src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
    tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
    if not src_ccy or not tgt_ccy or src_ccy == tgt_ccy:
        return

    tx_date = getattr(doc, "posting_date", None) or getattr(doc, "transaction_date", None) or nowdate()
    doc_rate = extract_document_exchange_rate(doc, src_ccy, tgt_ccy)
    if doc_rate and flt(doc_rate) > 0:
        return

    db_rate = lookup_intercompany_exchange_rate(src_ccy, tgt_ccy, tx_date)
    if db_rate and flt(db_rate) > 0:
        return

    frappe.throw(
        _(
            "Multi-Currency Exchange Rate Required: <b>{0}</b> ({1}) and <b>{2}</b> ({3}) use different currencies.<br><br>"
            "No exchange rate was found between <b>{1}</b> and <b>{3}</b> for <b>{4}</b>. "
            "Please enter the exchange rate on this voucher or "
            "<a href='/app/currency-exchange/new'><b>create a Currency Exchange record</b></a> "
            "so both company ledgers stay 100% tallied."
        ).format(source_company, src_ccy, target_company, tgt_ccy, tx_date),
        title=_("Exchange Rate Required"),
    )


def resolve_intercompany_currency_and_rate(source_doc, target_company, party_type=None, party_name=None, date=None):
    """
    Resolve target document currency, conversion_rate, and item rate factor.
    Honors any explicit exchange rate entered on `source_doc` first, then Currency Exchange (bidirectional).
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

    # ERPNext conversion_rate represents: 1 target_currency = conversion_rate target_company_currency
    if target_currency == target_company_currency:
        conversion_rate = 1.0
    else:
        conversion_rate = (
            extract_document_exchange_rate(source_doc, target_currency, target_company_currency)
            or get_intercompany_exchange_rate(target_currency, target_company_currency, date)
        )
        if not conversion_rate or conversion_rate <= 0:
            conversion_rate = 1.0

    # rate_factor converts unit prices from source_currency to target_currency
    if source_currency == target_currency:
        rate_factor = 1.0
    else:
        rate_factor = (
            extract_document_exchange_rate(source_doc, source_currency, target_currency)
            or get_intercompany_exchange_rate(source_currency, target_currency, date)
        )
        if not rate_factor or rate_factor <= 0:
            rate_factor = 1.0

    return target_currency, flt(conversion_rate, 9), flt(rate_factor, 9)


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
            item_group = (
                frappe.db.get_value("Item Group", {"is_group": 0}, "name")
                or frappe.db.get_value("Item Group", {}, "name")
                or "All Item Groups"
            )

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
        # Auto-provisioning shared Item master during authorized intercompany mirror sync
        item_doc.flags.ignore_permissions = True
        item_doc.flags.ignore_mandatory = True
        item_doc.insert()
        return item_doc.name
    except Exception as e:
        try:
            frappe.log_error(f"Could not auto-create item {item_code}: {e}", "Intercompany Item Creation")
        except Exception:
            pass
        return item_code


def _get_item_valuation_rate(item_code, company=None):
    """Fetch item valuation rate safely from Bin (company-filtered) or Item master."""
    if not item_code or not (hasattr(frappe, "db") and frappe.db):
        return 0.0
    try:
        if company and frappe.db.exists("DocType", "Bin"):
            bin_rate = frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate")
            if flt(bin_rate) > 0:
                return flt(bin_rate)
        item_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
        if flt(item_rate) > 0:
            return flt(item_rate)
    except Exception:
        pass
    return 0.0


def calculate_transfer_rate(
    item_doc,
    base_rate,
    target_company=None,
    settings=None,
    source_company=None,
    transaction_date=None,
):
    """
    Compute the arm's-length intercompany transfer rate using:
    1. Active Transfer Pricing Policy (matching target_company, source_company, item_code/item_group, date range)
    2. Global Inter Company Settings (default_transfer_pricing_rule + markup_percentage)
    3. Fallback to base_rate
    """
    rate = flt(base_rate or 0.0)
    item_code = item_doc.get("item_code") if isinstance(item_doc, dict) else getattr(item_doc, "item_code", None)
    item_group = item_doc.get("item_group") if isinstance(item_doc, dict) else getattr(item_doc, "item_group", None)
    if not item_group and item_code and hasattr(frappe, "db") and frappe.db:
        try:
            item_group = frappe.db.get_value("Item", item_code, "item_group")
        except Exception:
            item_group = None

    tx_date = getdate(transaction_date or nowdate())

    # 1. Check active Transfer Pricing Policy records if target_company is supplied
    if target_company and hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Transfer Pricing Policy"):
        try:
            active_field = "is_active" if frappe.db.has_column("Transfer Pricing Policy", "is_active") else "enabled"
            policies = frappe.get_all(
                "Transfer Pricing Policy",
                filters={active_field: 1, "to_company": target_company},
                fields=[
                    "name", "from_company", "to_company", "item_code", "item_group",
                    "methodology", "markup_percentage", "fixed_rate",
                    "effective_from", "effective_to",
                ],
            )
            best_policy = None
            best_score = -1
            for pol in policies:
                if source_company and pol.get("from_company") and pol.get("from_company") != source_company:
                    continue
                if pol.get("item_code") and pol.get("item_code") != item_code:
                    continue
                if pol.get("item_group") and pol.get("item_group") != item_group:
                    continue
                eff_from = pol.get("effective_from") or pol.get("valid_from")
                eff_to = pol.get("effective_to") or pol.get("valid_to")
                if eff_from and tx_date < getdate(eff_from):
                    continue
                if eff_to and tx_date > getdate(eff_to):
                    continue

                score = (4 if pol.get("item_code") else 0) + (2 if pol.get("item_group") else 0) + (1 if pol.get("from_company") else 0)
                if score > best_score:
                    best_score = score
                    best_policy = pol

            if best_policy:
                method = (best_policy.get("methodology") or best_policy.get("pricing_method") or "").strip()
                markup = flt(best_policy.get("markup_percentage") or 0.0)
                if method == "Fixed Transfer Rate":
                    return flt(best_policy.get("fixed_rate") or rate)
                elif method == "Cost-Plus Markup %":
                    cost_base = _get_item_valuation_rate(item_code, source_company) or rate
                    return flt(cost_base * (1.0 + (markup / 100.0)), 4)
                elif method == "Resale Price Method":
                    return flt(rate * (1.0 - (markup / 100.0)), 4)
                elif method == "Comparable Uncontrolled Price (CUP)":
                    return flt(rate, 4)
        except Exception:
            pass

    # 2. Check Inter Company Settings default rule
    if settings is not None:
        rule = (settings.get("default_transfer_pricing_rule") if isinstance(settings, dict) else getattr(settings, "default_transfer_pricing_rule", None)) or "Source Document Rate"
        markup = flt(settings.get("markup_percentage") if isinstance(settings, dict) else getattr(settings, "markup_percentage", 0.0))
        if rule == "Source Document Rate":
            return flt(rate)
        elif rule == "Cost / Valuation Rate":
            val_rate = _get_item_valuation_rate(item_code, source_company)
            return flt(val_rate if val_rate > 0 else rate)
        elif rule == "Cost + Markup %":
            cost_base = _get_item_valuation_rate(item_code, source_company) or rate
            return flt(cost_base * (1.0 + (markup / 100.0)), 4)

    return flt(rate)


def resolve_intercompany_target_item(
    source_item,
    target_company,
    mapping=None,
    rate_factor=1.0,
    settings=None,
    source_company=None,
    transaction_date=None,
):
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

    # Apply transfer pricing rules/settings cleanly before FX + UOM conversion
    effective_source_rate = calculate_transfer_rate(
        source_item,
        source_rate,
        target_company=target_company,
        settings=settings,
        source_company=source_company,
        transaction_date=transaction_date,
    )

    # Calculate converted qty and rate
    target_qty = source_qty * (conversion_factor if conversion_factor != 0 else 1.0)
    unit_rate = (effective_source_rate * flt(rate_factor)) / (conversion_factor if conversion_factor != 0 else 1.0)

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


def create_corresponding_document(source_doc, mapping_info, direction, settings=None):
    """Route document creation by target DocType"""
    mapping = mapping_info["mapping"]
    linked_company = mapping_info["linked_company"]
    target_doctype = mapping_info.get("target_doctype")

    if target_doctype == "Sales Invoice":
        return create_sales_invoice(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Purchase Invoice":
        return create_purchase_invoice(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Sales Order":
        return create_sales_order(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Purchase Order":
        return create_purchase_order(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Delivery Note":
        return create_delivery_note(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Purchase Receipt":
        return create_purchase_receipt(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Stock Entry":
        return create_stock_entry(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Journal Entry":
        if getattr(source_doc, "doctype", "") == "Landed Cost Voucher":
            return create_journal_entry_from_lcv(source_doc, mapping, linked_company, direction)
        return create_journal_entry(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Payment Entry":
        return create_payment_entry(source_doc, mapping, linked_company, direction)
    elif target_doctype == "Quotation":
        return create_quotation(source_doc, mapping, linked_company, direction, settings=settings)
    elif target_doctype == "Supplier Quotation":
        return create_supplier_quotation(source_doc, mapping, linked_company, direction, settings=settings)

    return None


def _resolve_party_control_account(party_type, party, company, target_currency, default_fieldname):
    """Resolve Party Account matching target_currency first, then any Party Account, then Company default."""
    if party and company and hasattr(frappe, "db") and frappe.db:
        pa_rows = frappe.get_all(
            "Party Account",
            filters={"parenttype": party_type, "parent": party, "company": company},
            fields=["account"],
        )
        for row in pa_rows or []:
            acct = row.get("account")
            if acct and target_currency:
                acc_ccy = frappe.db.get_value("Account", acct, "account_currency")
                if acc_ccy == target_currency:
                    return acct
        if pa_rows and pa_rows[0].get("account"):
            return pa_rows[0].get("account")
    return frappe.db.get_value("Company", company, default_fieldname) if company else None


def _preserve_intercompany_currency_after_defaults(target_doc, target_currency, conversion_rate, date=None):
    """Re-apply exact intercompany currency and conversion_rate after ERPNext set_missing_values."""
    if not target_doc:
        return
    if hasattr(target_doc, "currency") or isinstance(target_doc, dict):
        target_doc.currency = target_currency
    if hasattr(target_doc, "conversion_rate") or isinstance(target_doc, dict):
        target_doc.conversion_rate = conversion_rate
    if hasattr(target_doc, "price_list_currency") and target_doc.company:
        tgt_comp_ccy = frappe.db.get_value("Company", target_doc.company, "default_currency")
        plc = getattr(target_doc, "price_list_currency", None)
        if not plc or plc == target_currency:
            target_doc.price_list_currency = target_currency
            target_doc.plc_conversion_rate = conversion_rate
        elif tgt_comp_ccy and plc != tgt_comp_ccy:
            if abs(flt(getattr(target_doc, "plc_conversion_rate", 0))) <= 0:
                target_doc.plc_conversion_rate = get_intercompany_exchange_rate(plc, tgt_comp_ccy, date)
        else:
            target_doc.plc_conversion_rate = 1.0


def create_sales_invoice(source_doc, mapping, linked_company, direction, settings=None):
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

    debit_to = _resolve_party_control_account(
        "Customer", si.customer, si.company, target_currency, "default_receivable_account"
    )
    if debit_to:
        si.debit_to = debit_to

    default_income_account = frappe.db.get_value("Company", si.company, "default_income_account")
    default_cost_center = get_default_cost_center(si.company)

    for item in getattr(source_doc, "items", []):
        target_item = resolve_intercompany_target_item(
            item,
            si.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=source_doc.company,
            transaction_date=si.posting_date,
        )
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
    _preserve_intercompany_currency_after_defaults(si, target_currency, conversion_rate, si.posting_date)

    si.docstatus = 0  # Draft
    return si


def create_purchase_invoice(source_doc, mapping, linked_company, direction, settings=None):
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

    credit_to = _resolve_party_control_account(
        "Supplier", pi.supplier, pi.company, target_currency, "default_payable_account"
    )
    if credit_to:
        pi.credit_to = credit_to

    default_expense_account = frappe.db.get_value("Company", pi.company, "default_expense_account")
    default_cost_center = get_default_cost_center(pi.company)

    for item in getattr(source_doc, "items", []):
        target_item = resolve_intercompany_target_item(
            item,
            pi.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=source_doc.company,
            transaction_date=pi.posting_date,
        )
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
    _preserve_intercompany_currency_after_defaults(pi, target_currency, conversion_rate, pi.posting_date)

    pi.docstatus = 0  # Draft
    return pi


def create_purchase_order(sales_order, mapping, linked_company, direction, settings=None):
    """Create Purchase Order from Sales Order or Material Request"""
    po = frappe.new_doc("Purchase Order")

    if direction == "other_to_main":
        po.company = mapping.main_company
        po.supplier = linked_company.main_company_supplier
    else:
        po.company = linked_company.company
        po.supplier = linked_company.other_company_supplier

    if not po.supplier:
        frappe.throw(_("Supplier not found for company {0}").format(po.company))

    po.transaction_date = getattr(sales_order, "transaction_date", None) or nowdate()
    po.schedule_date = getattr(sales_order, "delivery_date", None) or getattr(sales_order, "schedule_date", None) or nowdate()
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
        target_item = resolve_intercompany_target_item(
            item,
            po.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=sales_order.company,
            transaction_date=po.transaction_date,
        )
        po.append("items", {
            "item_code": target_item["item_code"],
            "item_name": target_item["item_name"],
            "description": target_item["description"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "rate": target_item["rate"],
            "warehouse": warehouse,
            "schedule_date": getattr(item, "delivery_date", None) or getattr(item, "schedule_date", None) or po.schedule_date,
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
    _preserve_intercompany_currency_after_defaults(po, target_currency, conversion_rate, po.transaction_date)

    po.docstatus = 0  # Draft
    return po


def create_sales_order(purchase_order, mapping, linked_company, direction, settings=None):
    """Create Sales Order from Purchase Order or Material Request"""
    so = frappe.new_doc("Sales Order")

    if direction == "other_to_main":
        so.company = mapping.main_company
        so.customer = linked_company.main_company_customer
    else:
        so.company = linked_company.company
        so.customer = linked_company.other_company_customer

    if not so.customer:
        frappe.throw(_("Customer not found for company {0}").format(so.company))

    so.transaction_date = getattr(purchase_order, "transaction_date", None) or nowdate()
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
        target_item = resolve_intercompany_target_item(
            item,
            so.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=purchase_order.company,
            transaction_date=so.transaction_date,
        )
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
    _preserve_intercompany_currency_after_defaults(so, target_currency, conversion_rate, so.transaction_date)

    so.docstatus = 0  # Draft
    return so


def create_delivery_note(purchase_receipt, mapping, linked_company, direction, settings=None):
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
        target_item = resolve_intercompany_target_item(
            item,
            dn.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=purchase_receipt.company,
            transaction_date=dn.posting_date,
        )
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
    _preserve_intercompany_currency_after_defaults(dn, target_currency, conversion_rate, dn.posting_date)

    dn.docstatus = 0  # Draft
    return dn


def create_purchase_receipt(delivery_note, mapping, linked_company, direction, settings=None):
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
        target_item = resolve_intercompany_target_item(
            item,
            pr.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=delivery_note.company,
            transaction_date=pr.posting_date,
        )
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
    _preserve_intercompany_currency_after_defaults(pr, target_currency, conversion_rate, pr.posting_date)

    pr.docstatus = 0  # Draft
    return pr


def create_quotation(supplier_quotation, mapping, linked_company, direction, settings=None):
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
        target_item = resolve_intercompany_target_item(
            item,
            q.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=supplier_quotation.company,
            transaction_date=q.transaction_date,
        )
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
    q.flags.ignore_account_permission = True
    q.flags.ignore_validate = True
    q.flags.ignore_links = True
    q.flags.ignore_pricing_rule = True
    q.flags.ignore_party_validation = True

    try:
        q.set_missing_values(for_validate=True)
    except Exception:
        pass
    _preserve_intercompany_currency_after_defaults(q, target_currency, conversion_rate, q.transaction_date)

    q.docstatus = 0
    return q


def create_supplier_quotation(quotation, mapping, linked_company, direction, settings=None):
    """Create Supplier Quotation from Quotation or Request for Quotation"""
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
        target_item = resolve_intercompany_target_item(
            item,
            sq.company,
            mapping=mapping,
            rate_factor=rate_factor,
            settings=settings,
            source_company=quotation.company,
            transaction_date=sq.transaction_date,
        )
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
    sq.flags.ignore_account_permission = True
    sq.flags.ignore_validate = True
    sq.flags.ignore_links = True
    sq.flags.ignore_pricing_rule = True
    sq.flags.ignore_party_validation = True

    try:
        sq.set_missing_values(for_validate=True)
    except Exception:
        pass
    _preserve_intercompany_currency_after_defaults(sq, target_currency, conversion_rate, sq.transaction_date)

    sq.docstatus = 0
    return sq


def get_intercompany_warehouse(company):
    """Get inter-company / transit warehouse for a company (v15/v16 schema safe)."""
    warehouse = None
    if hasattr(frappe, "db") and frappe.db and frappe.db.has_column("Warehouse", "is_intercompany_warehouse"):
        warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "company": company,
                "is_intercompany_warehouse": 1,
                "is_group": 0,
            },
            "name",
        )
    if not warehouse:
        warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "company": company,
                "warehouse_name": ["like", "%inter%company%"],
                "is_group": 0,
            },
            "name",
        )
    if not warehouse:
        warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "company": company,
                "warehouse_name": ["like", "%transit%"],
                "is_group": 0,
            },
            "name",
        )
    if not warehouse:
        warehouse = get_default_warehouse(company)
    return warehouse


def get_or_create_intercompany_warehouse(company):
    """
    Finds an existing receiving/transit warehouse for the company,
    or provisions a clean leaf 'Intercompany Transit Warehouse' under All Warehouses
    so Stock Entry (Material Receipt) never fails with missing target warehouse.
    """
    if not company:
        return None

    # 1. Existing intercompany/transit warehouse (exact preference)
    existing = None
    if hasattr(frappe, "db") and frappe.db and frappe.db.has_column("Warehouse", "is_intercompany_warehouse"):
        existing = frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_intercompany_warehouse": 1, "is_group": 0},
            "name",
        )
    if not existing:
        existing = frappe.db.get_value(
            "Warehouse",
            {"company": company, "warehouse_name": ["like", "%inter%company%"], "is_group": 0},
            "name",
        )
    if not existing:
        existing = frappe.db.get_value(
            "Warehouse",
            {"company": company, "warehouse_name": ["like", "%transit%"], "is_group": 0},
            "name",
        )
    if existing:
        return existing

    # 2. Try creating a dedicated leaf transit warehouse under company's parent warehouse group
    try:
        parent_wh = frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 1, "warehouse_name": ["like", "%All Warehouses%"]},
            "name",
        ) or frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")

        wh_payload = {
            "doctype": "Warehouse",
            "warehouse_name": "Intercompany Transit Warehouse",
            "company": company,
            "is_group": 0,
        }
        if parent_wh:
            wh_payload["parent_warehouse"] = parent_wh

        wh = frappe.get_doc(wh_payload)
        wh.flags.ignore_permissions = True
        wh.flags.ignore_mandatory = True
        wh.insert()
        return wh.name
    except Exception:
        return get_default_warehouse(company)


def _is_corrupted_or_invalid_eval_expr(raw_val):
    """Return True if a field expression contains glued operators or an invalid Python eval: body."""
    val = (raw_val or "").strip()
    if not val:
        return False
    compact = val.replace(" ", "").lower()
    if any(tok in compact for tok in ("__islocaland", "anddoc.", "and!", "or!", "1or(", "0or(", ")or(", "1and(", "0and(")):
        return True
    if val.lower().startswith("eval:"):
        expr = val[5:].strip().rstrip(";").strip()
        if not expr:
            return True
        try:
            import ast
            ast.parse(expr, mode="eval")
        except SyntaxError:
            return True
    return False


def _sanitize_intercompany_stock_entry_custom_fields(force=False):
    """Idempotent self-healing repair of corrupted depends_on/default expressions on Stock Entry ICT fields."""
    if not force and getattr(frappe.flags, "ict_se_cf_sanitized", False):
        return 0
    if not (hasattr(frappe, "db") and frappe.db):
        return 0

    ict_fields = (
        "is_intercompany",
        "intercompany_target_company",
        "intercompany_linked_doc_doctype",
        "intercompany_linked_doc_name",
        "intercompany_linked_company",
    )
    repaired = 0
    try:
        if frappe.db.table_exists("Custom Field"):
            cf_rows = frappe.get_all(
                "Custom Field",
                filters={"dt": ["in", ["Stock Entry", "Stock Entry Detail"]], "fieldname": ["in", list(ict_fields)]},
                fields=["name", "fieldname", "depends_on", "mandatory_depends_on", "read_only_depends_on", "default", "fetch_if_empty"],
            )
            for row in cf_rows or []:
                updates = {}
                for col in ("depends_on", "mandatory_depends_on", "read_only_depends_on"):
                    if _is_corrupted_or_invalid_eval_expr(row.get(col)):
                        updates[col] = ""
                if row.get("fieldname") == "intercompany_target_company":
                    if row.get("default") not in (None, ""):
                        updates["default"] = None
                    if cint(row.get("fetch_if_empty")):
                        updates["fetch_if_empty"] = 0
                elif _is_corrupted_or_invalid_eval_expr(row.get("default")):
                    updates["default"] = None
                if updates:
                    frappe.db.set_value("Custom Field", row["name"], updates, update_modified=False)
                    repaired += 1

        if frappe.db.table_exists("Property Setter"):
            ps_rows = frappe.get_all(
                "Property Setter",
                filters={
                    "doc_type": ["in", ["Stock Entry", "Stock Entry Detail"]],
                    "field_name": ["in", list(ict_fields)],
                    "property": ["in", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "default"]],
                },
                fields=["name", "field_name", "property", "value"],
            )
            for ps in ps_rows or []:
                if (ps.get("property") == "default" and ps.get("field_name") == "intercompany_target_company") or _is_corrupted_or_invalid_eval_expr(ps.get("value")):
                    frappe.db.delete("Property Setter", {"name": ps["name"]})
                    repaired += 1

        frappe.flags.ict_se_cf_sanitized = True
        if repaired and hasattr(frappe, "clear_cache"):
            frappe.clear_cache(doctype="Stock Entry")
    except Exception:
        pass
    return repaired


def sanitize_intercompany_stock_entry(doc, method=None):
    """
    Ensures that an intercompany Material Receipt Stock Entry never contains
    cross-company source warehouses which trigger ERPNext's 'Warehouse does not belong to company' error.
    Also self-heals corrupted eval/depends_on expressions on Stock Entry ICT custom fields.
    """
    _sanitize_intercompany_stock_entry_custom_fields()

    if (doc.get("purpose") or doc.get("stock_entry_type")) == "Material Receipt":
        if doc.get("from_warehouse"):
            from_wh_comp = frappe.db.get_value("Warehouse", doc.get("from_warehouse"), "company")
            if from_wh_comp and from_wh_comp != doc.get("company"):
                doc.from_warehouse = None

        for d in doc.get("items", []):
            if d.get("s_warehouse"):
                s_wh_comp = frappe.db.get_value("Warehouse", d.get("s_warehouse"), "company")
                if s_wh_comp and s_wh_comp != doc.get("company"):
                    d.s_warehouse = None


def create_stock_entry(source_stock_entry, mapping, linked_company, direction, settings=None):
    """
    Creates a paired Stock Entry in target company for inter-company stock transfer.
    Supports Company 1 Material Issue -> Company 2 Material Receipt cleanly.
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
    se.remarks = getattr(source_stock_entry, "remarks", None) or (
        f"Intercompany Material Receipt from {source_stock_entry.doctype} {source_stock_entry.name} ({source_stock_entry.company})"
    )

    # Inter-Company Stock Entry is restricted strictly to Same-Currency companies
    source_company_currency = frappe.db.get_value("Company", source_stock_entry.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", se.company, "default_currency")
    if source_company_currency and target_company_currency and source_company_currency != target_company_currency:
        validate_stock_entry_same_currency(source_stock_entry.company, se.company)
    fx_rate = 1.0

    if not target_warehouse:
        target_warehouse = get_intercompany_warehouse(target_warehouse_company)
    if not target_warehouse:
        target_warehouse = get_or_create_intercompany_warehouse(target_warehouse_company)
    if not target_warehouse:
        target_warehouse = frappe.db.get_value("Warehouse", {"company": target_warehouse_company, "is_group": 0}, "name")

    # In ERPNext, a Stock Entry in target company MUST NOT have from_warehouse set to another company!
    se.from_warehouse = None
    se.to_warehouse = target_warehouse

    for item in (source_stock_entry.get("items") or []):
        item_code = getattr(item, "item_code", None) or (item.get("item_code") if isinstance(item, dict) else None)
        base_rate = flt(
            getattr(item, "basic_rate", 0)
            or getattr(item, "valuation_rate", 0)
            or getattr(item, "rate", 0)
        )
        if base_rate <= 0 and item_code:
            base_rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate") or 0)

        item_for_mapping = {
            "item_code": item_code,
            "item_name": getattr(item, "item_name", None) or item_code,
            "description": getattr(item, "description", None) or item_code,
            "qty": flt(getattr(item, "qty", 1)),
            "rate": base_rate,
            "uom": getattr(item, "uom", None) or "Nos",
        }
        target_item = resolve_intercompany_target_item(
            item_for_mapping,
            se.company,
            mapping=mapping,
            rate_factor=fx_rate,
            settings=settings,
            source_company=source_stock_entry.company,
            transaction_date=se.posting_date,
        )
        final_rate = flt(target_item["rate"])
        se_row = {
            "item_code": target_item["item_code"],
            "qty": target_item["qty"],
            "uom": target_item["uom"],
            "s_warehouse": None,
            "t_warehouse": target_warehouse,
            "basic_rate": final_rate,
            "basic_amount": flt(final_rate * target_item["qty"]),
            "conversion_factor": target_item["conversion_factor"],
        }
        if final_rate <= 0:
            se_row["allow_zero_valuation_rate"] = 1
        se.append("items", se_row)

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
    for d in (se.get("items") or []):
        d.s_warehouse = None
        if not d.t_warehouse:
            d.t_warehouse = target_warehouse

    se.docstatus = 0  # Draft
    return se


def create_journal_entry_from_lcv(source_lcv, mapping, linked_company, direction):
    """
    Creates a balanced Intercompany Recharge Journal Entry in the sister company
    from a Landed Cost Voucher (freight/duty/handling allocation recharge).
    """
    je = frappe.new_doc("Journal Entry")

    if direction == "other_to_main":
        je.company = mapping.main_company
        supplier = getattr(linked_company, "main_company_supplier", None)
        clearing_account = getattr(linked_company, "main_company_account", None)
    else:
        je.company = linked_company.company
        supplier = getattr(linked_company, "other_company_supplier", None)
        clearing_account = getattr(linked_company, "other_company_account", None)

    if not clearing_account:
        clearing_account = get_or_create_intercompany_clearing_account(je.company, source_lcv.company)

    total_amt = flt(getattr(source_lcv, "total_taxes_and_charges", 0))
    if total_amt <= 0:
        for tax in (source_lcv.get("taxes") or []):
            total_amt += flt(tax.get("base_amount") if isinstance(tax, dict) else getattr(tax, "base_amount", 0)) or flt(
                tax.get("amount") if isinstance(tax, dict) else getattr(tax, "amount", 0)
            )

    if total_amt <= 0:
        frappe.throw(
            _("Landed Cost Voucher {0} has zero total taxes and charges to recharge.").format(source_lcv.name)
        )

    je.posting_date = getattr(source_lcv, "posting_date", None) or nowdate()
    je.voucher_type = (
        "Inter Company Journal Entry"
        if frappe.db.exists("Journal Entry Type", "Inter Company Journal Entry")
        else "Journal Entry"
    )

    tax_descs = []
    for tax in (source_lcv.get("taxes") or []):
        desc = tax.get("description") if isinstance(tax, dict) else getattr(tax, "description", None)
        if desc:
            tax_descs.append(str(desc))
    tax_summary = f" ({', '.join(tax_descs[:3])})" if tax_descs else ""
    je.user_remark = f"Landed Cost Recharge from {source_lcv.doctype} {source_lcv.name} ({source_lcv.company}){tax_summary}"

    source_ccy = frappe.db.get_value("Company", source_lcv.company, "default_currency")
    target_ccy = frappe.db.get_value("Company", je.company, "default_currency")
    fx_rate = get_intercompany_exchange_rate(source_ccy, target_ccy, je.posting_date)
    if source_ccy and target_ccy and source_ccy != target_ccy:
        je.multi_currency = 1

    converted_amt = flt(total_amt * flt(fx_rate), 2)
    if converted_amt <= 0:
        converted_amt = flt(total_amt, 2)

    default_cost_center = get_default_cost_center(je.company)

    # Debit Expense/Landed Cost Account in sister company
    debit_account = frappe.db.get_value("Company", je.company, "default_expense_account")
    if not debit_account:
        debit_account = (
            frappe.db.get_value(
                "Account",
                {"company": je.company, "root_type": "Expense", "is_group": 0, "account_name": ["like", "%Freight%"]},
                "name",
            )
            or frappe.db.get_value(
                "Account",
                {"company": je.company, "root_type": "Expense", "is_group": 0, "account_name": ["like", "%Landed%"]},
                "name",
            )
            or frappe.db.get_value(
                "Account",
                {"company": je.company, "root_type": "Expense", "is_group": 0},
                "name",
            )
            or clearing_account
        )

    # Credit Payable (to Sister Supplier) or Intercompany Clearing Account
    payable_account = frappe.db.get_value("Company", je.company, "default_payable_account")
    debit_row = _build_je_row(
        debit_account,
        "debit",
        converted_amt,
        target_ccy,
        tx_date=je.posting_date,
        cost_center=default_cost_center,
    )
    if supplier and payable_account:
        credit_row = _build_je_row(
            payable_account,
            "credit",
            converted_amt,
            target_ccy,
            tx_date=je.posting_date,
            party_type="Supplier",
            party=supplier,
            cost_center=default_cost_center,
        )
    else:
        credit_row = _build_je_row(
            clearing_account or debit_account,
            "credit",
            converted_amt,
            target_ccy,
            tx_date=je.posting_date,
            cost_center=default_cost_center,
        )

    je.append("accounts", debit_row)
    je.append("accounts", credit_row)

    je.intercompany_linked_doc_doctype = source_lcv.doctype
    je.intercompany_linked_doc_name = source_lcv.name
    je.intercompany_linked_company = source_lcv.company
    je.intercompany_target_company = source_lcv.company

    je.flags.ignore_permissions = True
    je.flags.ignore_mandatory = True
    je.flags.ignore_account_permission = True
    je.flags.ignore_validate = True
    je.flags.ignore_links = True
    je.docstatus = 0
    return je


def _build_je_row(account, side, target_base_amount, target_company_currency, fx_hint_map=None, tx_date=None, party_type=None, party=None, cost_center=None):
    """
    Constructs a balanced Journal Entry Account row respecting the target account's account_currency.
    Guarantees debit/credit (company base currency) == target_base_amount while computing
    debit_in_account_currency / credit_in_account_currency & exchange_rate accurately.
    """
    acc_currency = (
        frappe.db.get_value("Account", account, "account_currency")
        if account and hasattr(frappe, "db") and frappe.db
        else None
    ) or target_company_currency

    base_amt = flt(target_base_amount, 2)
    raw_fx = 1.0
    if acc_currency and target_company_currency and acc_currency != target_company_currency:
        hint = (fx_hint_map or {}).get((acc_currency, target_company_currency))
        raw_fx = flt(hint) if hint else flt(get_intercompany_exchange_rate(acc_currency, target_company_currency, tx_date))
        if raw_fx <= 0:
            raw_fx = 1.0
        amt_in_acc_ccy = flt(base_amt / raw_fx, 2)
        if amt_in_acc_ccy > 0 and abs(flt(amt_in_acc_ccy * raw_fx, 2) - base_amt) > 0.001:
            raw_fx = base_amt / amt_in_acc_ccy
    else:
        amt_in_acc_ccy = base_amt

    row_fx = flt(raw_fx, 9)
    row = {
        "account": account,
        "account_currency": acc_currency,
        "exchange_rate": row_fx,
        "cost_center": cost_center,
        "debit_in_account_currency": amt_in_acc_ccy if side == "debit" else 0,
        "credit_in_account_currency": amt_in_acc_ccy if side == "credit" else 0,
        "debit": base_amt if side == "debit" else 0,
        "credit": base_amt if side == "credit" else 0,
    }
    if party_type and party:
        row["party_type"] = party_type
        row["party"] = party
    return row


def create_journal_entry(source_je, mapping, linked_company, direction):
    """
    Create corresponding Journal Entry (including Landed Cost Voucher recharge JEs)
    with 100% multi-currency ledger parity (e.g. 500 USD @ 275 <-> 137,500 PKR).
    """
    if getattr(source_je, "doctype", "") == "Landed Cost Voucher":
        return create_journal_entry_from_lcv(source_je, mapping, linked_company, direction)

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

    je.posting_date = getattr(source_je, "posting_date", None) or nowdate()
    je.voucher_type = (
        "Inter Company Journal Entry"
        if hasattr(frappe, "db") and frappe.db and frappe.db.exists("Journal Entry Type", "Inter Company Journal Entry")
        else "Journal Entry"
    )
    je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name} " + (getattr(source_je, "user_remark", None) or "")

    source_company_currency = frappe.db.get_value("Company", source_je.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", je.company, "default_currency")

    # Inspect source accounts for party direction + exact multi-currency hints
    source_party_type = None
    source_is_credit = False
    source_party_row = None
    for acc in (getattr(source_je, "accounts", None) or []):
        if getattr(acc, "party_type", None) and getattr(acc, "party", None):
            source_party_type = acc.party_type
            source_is_credit = flt(getattr(acc, "credit_in_account_currency", 0)) > 0 or flt(getattr(acc, "credit", 0)) > 0
            source_party_row = acc
            break

    # Compute exact base amount in target company's default currency
    src_base_total = flt(getattr(source_je, "total_credit", 0)) or flt(getattr(source_je, "total_debit", 0))
    if src_base_total <= 0:
        src_base_total = sum(
            flt(getattr(r, "credit", 0)) or (flt(getattr(r, "credit_in_account_currency", 0)) * (flt(getattr(r, "exchange_rate", 1)) or 1.0))
            for r in (getattr(source_je, "accounts", None) or [])
        )

    fx_hint_map = {}
    for acc_row in (getattr(source_je, "accounts", None) or []):
        r_ccy = getattr(acc_row, "account_currency", None)
        r_fx = flt(getattr(acc_row, "exchange_rate", 0))
        if r_ccy and source_company_currency and r_ccy != source_company_currency and r_fx > 0:
            fx_hint_map[(r_ccy, source_company_currency)] = r_fx
            fx_hint_map[(source_company_currency, r_ccy)] = 1.0 / r_fx

    if source_company_currency == target_company_currency:
        target_base_amount = flt(src_base_total, 2)
    elif (
        source_party_row
        and getattr(source_party_row, "account_currency", None) == target_company_currency
        and (
            flt(getattr(source_party_row, "credit_in_account_currency", 0)) > 0
            or flt(getattr(source_party_row, "debit_in_account_currency", 0)) > 0
        )
    ):
        # Source already entered in target company's currency (e.g. 500 USD @ 275 in PKR Co -> exact 500 USD in USD Co)
        target_base_amount = flt(
            flt(getattr(source_party_row, "credit_in_account_currency", 0))
            or flt(getattr(source_party_row, "debit_in_account_currency", 0)),
            2,
        )
    else:
        fx_src_to_tgt = (
            fx_hint_map.get((source_company_currency, target_company_currency))
            or extract_document_exchange_rate(source_je, source_company_currency, target_company_currency)
            or get_intercompany_exchange_rate(source_company_currency, target_company_currency, je.posting_date)
        )
        target_base_amount = flt(src_base_total * flt(fx_src_to_tgt), 2)

    if source_company_currency != target_company_currency:
        je.multi_currency = 1
    else:
        je.multi_currency = getattr(source_je, "multi_currency", 0)

    default_cost_center = get_default_cost_center(je.company)

    if source_party_type == "Supplier":
        party_acct = (
            frappe.db.get_value("Party Account", {"parenttype": "Customer", "parent": customer, "company": je.company}, "account")
            if customer else None
        ) or frappe.db.get_value("Company", je.company, "default_receivable_account")
        p_side = "debit" if source_is_credit else "credit"
        t_side = "credit" if source_is_credit else "debit"
        r1 = _build_je_row(party_acct, p_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, "Customer", customer, default_cost_center)
        r2 = _build_je_row(tmp_account, t_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, None, None, default_cost_center)
    else:
        party_acct = (
            frappe.db.get_value("Party Account", {"parenttype": "Supplier", "parent": supplier, "company": je.company}, "account")
            if supplier else None
        ) or frappe.db.get_value("Company", je.company, "default_payable_account")
        p_side = "debit" if source_is_credit else "credit"
        t_side = "credit" if source_is_credit else "debit"
        r1 = _build_je_row(party_acct, p_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, "Supplier", supplier, default_cost_center)
        r2 = _build_je_row(tmp_account, t_side, target_base_amount, target_company_currency, fx_hint_map, je.posting_date, None, None, default_cost_center)

    if r1.get("account_currency") != target_company_currency or r2.get("account_currency") != target_company_currency:
        je.multi_currency = 1

    je.append("accounts", r1)
    je.append("accounts", r2)

    je.flags.ignore_permissions = True
    je.flags.ignore_mandatory = True
    je.flags.ignore_account_permission = True
    je.flags.ignore_validate = True
    je.flags.ignore_links = True

    je.intercompany_linked_doc_doctype = source_je.doctype
    je.intercompany_linked_doc_name = source_je.name
    je.intercompany_linked_company = source_je.company
    je.intercompany_target_company = source_je.company
    je.docstatus = 0  # Draft
    return je


def create_payment_entry(source_pe, mapping, linked_company, direction):
    """
    Create corresponding Payment Entry using Bank/Cash TMP clearing accounts
    and exact multi-currency exchange rates (100% ledger parity).
    """
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

    # Guarantee TMP clearing account is Bank or Cash so Payment Entry never rejects Temporary accounts
    tmp_type = (
        frappe.db.get_value("Account", tmp_account, "account_type")
        if tmp_account and hasattr(frappe, "db") and frappe.db
        else None
    )
    if not tmp_account or tmp_type not in ("Bank", "Cash"):
        tmp_account = get_or_create_intercompany_clearing_account(pe.company, source_pe.company)

    pe.posting_date = getattr(source_pe, "posting_date", None) or nowdate()
    pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
    pe.mode_of_payment = getattr(source_pe, "mode_of_payment", None)

    if pe.payment_type == "Pay":
        pe.paid_from = tmp_account
        pe.paid_to = (
            (frappe.db.get_value("Party Account", {"parenttype": "Supplier", "parent": supplier, "company": pe.company}, "account") if supplier else None)
            or frappe.db.get_value("Company", pe.company, "default_payable_account")
        )
        pe.party_type = "Supplier"
        pe.party = supplier
        pe.party_name = frappe.db.get_value("Supplier", supplier, "supplier_name") if supplier else ""
    else:
        pe.paid_from = (
            (frappe.db.get_value("Party Account", {"parenttype": "Customer", "parent": customer, "company": pe.company}, "account") if customer else None)
            or frappe.db.get_value("Company", pe.company, "default_receivable_account")
        )
        pe.paid_to = tmp_account
        pe.party_type = "Customer"
        pe.party = customer
        pe.party_name = frappe.db.get_value("Customer", customer, "customer_name") if customer else ""

    source_company_currency = frappe.db.get_value("Company", source_pe.company, "default_currency")
    target_company_currency = frappe.db.get_value("Company", pe.company, "default_currency")

    pe.paid_from_account_currency = (
        frappe.db.get_value("Account", pe.paid_from, "account_currency") if pe.paid_from else None
    ) or target_company_currency
    pe.paid_to_account_currency = (
        frappe.db.get_value("Account", pe.paid_to, "account_currency") if pe.paid_to else None
    ) or target_company_currency

    # Determine economic amount settled in source voucher:
    # When source was "Pay" to intercompany supplier, paid_to is the supplier's payable account;
    # when source was "Receive" from intercompany customer, paid_from is the customer's receivable account.
    if source_pe.payment_type == "Pay":
        ref_amt = flt(getattr(source_pe, "received_amount", 0)) or flt(getattr(source_pe, "paid_amount", 0))
        ref_ccy = getattr(source_pe, "paid_to_account_currency", None) or source_company_currency
    else:
        ref_amt = flt(getattr(source_pe, "paid_amount", 0)) or flt(getattr(source_pe, "received_amount", 0))
        ref_ccy = getattr(source_pe, "paid_from_account_currency", None) or source_company_currency

    def _pe_rate(c_from, c_to):
        if not c_from or not c_to or c_from == c_to:
            return 1.0
        r = extract_document_exchange_rate(source_pe, c_from, c_to)
        if not r:
            r = get_intercompany_exchange_rate(c_from, c_to, pe.posting_date)
        return flt(r or 1.0, 9)

    pe.source_exchange_rate = _pe_rate(pe.paid_from_account_currency, target_company_currency)
    pe.target_exchange_rate = _pe_rate(pe.paid_to_account_currency, target_company_currency)

    fx_ref_to_paid_from = _pe_rate(ref_ccy, pe.paid_from_account_currency)
    pe.paid_amount = flt(ref_amt * fx_ref_to_paid_from, 2)

    base_paid_amt = flt(pe.paid_amount * flt(pe.source_exchange_rate), 2)
    if pe.paid_to_account_currency == pe.paid_from_account_currency:
        pe.received_amount = pe.paid_amount
    elif pe.paid_to_account_currency == ref_ccy:
        pe.received_amount = flt(ref_amt, 2)
    else:
        pe.received_amount = flt(base_paid_amt / (flt(pe.target_exchange_rate) or 1.0), 2)

    pe.base_paid_amount = base_paid_amt
    pe.base_received_amount = flt(pe.received_amount * flt(pe.target_exchange_rate), 2)

    pe.reference_no = getattr(source_pe, "reference_no", None) or source_pe.name
    pe.reference_date = getattr(source_pe, "reference_date", None) or pe.posting_date

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
    """Create inter-company document reference using savepoint safety."""
    try:
        if source_doc.company == target_doc.company:
            return

        if hasattr(frappe.db, "savepoint"):
            frappe.db.savepoint("ict_doc_ref")

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
            ref_doc.flags.ignore_links = True
            ref_doc.flags.ignore_mandatory = True
            ref_doc.insert(ignore_permissions=True)
    except Exception as e:
        if hasattr(frappe.db, "rollback"):
            try:
                frappe.db.rollback(save_point="ict_doc_ref")
            except Exception:
                pass
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
        # 1. Permanently repair corrupted depends_on expressions across DocField, Custom Field, and Property Setter
        from inter_company_transactions.diagnose_and_heal import repair_database_text
        repair_database_text(lambda *args, **kwargs: None)
        _sanitize_intercompany_stock_entry_custom_fields(force=True)

        # 2. Remove intrusive custom fields on Tree DocTypes and Master DocTypes
        if frappe.db.table_exists("Custom Field"):
            frappe.db.sql("""
                DELETE FROM `tabCustom Field`
                WHERE `dt` IN ('Customer Group', 'Supplier Group', 'Item Group') AND `fieldname` = 'custom_company'
            """)
            obsolete_master_fields = [
                ('Customer', 'ic_customer_group'),
                ('Supplier', 'ic_supplier_group'),
                ('Item', 'is_intercompany_item'),
                ('Item', 'ic_item_group'),
                ('Warehouse', 'is_intercompany_warehouse'),
                ('Warehouse', 'ic_warehouse'),
            ]
            for m_dt, m_fn in obsolete_master_fields:
                frappe.db.sql("""
                    DELETE FROM `tabCustom Field`
                    WHERE `dt` = %s AND `fieldname` = %s
                """, (m_dt, m_fn))

        if frappe.db.table_exists("Property Setter"):
            try:
                frappe.db.sql("""
                    DELETE FROM `tabProperty Setter`
                    WHERE `module` = 'Inter Company Transactions'
                      AND `doc_type` IN ('Customer', 'Supplier')
                      AND `field_name` = 'naming_series'
                """)
            except Exception:
                pass

        if frappe.db.table_exists("Custom Field"):
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

        # Clean stale draft intercompany_target_company values via Frappe ORM
        tx_doctypes = [
            "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
            "Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation",
            "Material Request", "Stock Entry", "Journal Entry", "Payment Entry",
            "Request for Quotation", "Landed Cost Voucher"
        ]
        for dt in tx_doctypes:
            try:
                if frappe.db.table_exists(dt) and frappe.db.has_column(dt, "is_intercompany") and frappe.db.has_column(dt, "intercompany_target_company"):
                    stale_rows = frappe.get_all(
                        dt,
                        filters={"docstatus": 0, "intercompany_target_company": ["is", "set"]},
                        fields=["name", "is_intercompany"],
                    )
                    for row in stale_rows or []:
                        if not cint(row.get("is_intercompany")):
                            frappe.db.set_value(dt, row.get("name"), "intercompany_target_company", None, update_modified=False)
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
    except Exception:
        pass


_SUPPORTED_INTERCOMPANY_DOCTYPES = {
    "Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
    "Delivery Note", "Purchase Receipt", "Stock Entry", "Journal Entry",
    "Payment Entry", "Quotation", "Supplier Quotation", "Material Request",
    "Request for Quotation", "Landed Cost Voucher",
}


@frappe.whitelist()
def trigger_manual_intercompany_sync(doctype, name):
    """Manually trigger intercompany mirroring for a submitted transaction document."""
    if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES:
        frappe.throw(_("DocType {0} is not configured for inter-company mirroring.").format(doctype))

    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} was not found.").format(doctype, name))

    frappe.has_permission(doctype, "write", name, throw=True)
    doc = frappe.get_doc(doctype, name)

    if doc.docstatus != 1:
        return {"success": False, "message": _("Only submitted documents can be mirrored.")}

    if not cint(doc.get("is_intercompany")):
        return {"success": False, "message": _("Is Intercompany is not enabled on this document.")}

    if doc.get("intercompany_linked_doc_name"):
        return {
            "success": True,
            "message": _("Document is already linked to {0} {1}.").format(
                doc.get("intercompany_linked_doc_doctype") or "",
                doc.get("intercompany_linked_doc_name"),
            ),
        }

    existing_ref = None
    if frappe.db.exists("DocType", "Inter Company Document Reference"):
        existing_ref = frappe.db.get_value(
            "Inter Company Document Reference",
            {"source_doctype": doctype, "source_name": name},
            ["target_doctype", "target_name"],
            as_dict=True,
        )
    if existing_ref:
        return {
            "success": True,
            "message": _("Mirrored counterpart already exists: {0} {1}.").format(
                existing_ref.target_doctype, existing_ref.target_name
            ),
        }

    mappings = find_applicable_mappings(doc)
    if not mappings and not (doc.get("intercompany_target_company") or "").strip():
        return {
            "success": False,
            "message": _("No active Intercompany Transaction Link mapping matched this document."),
        }

    create_linked_documents(doc, None)

    new_ref = None
    if frappe.db.exists("DocType", "Inter Company Document Reference"):
        new_ref = frappe.db.get_value(
            "Inter Company Document Reference",
            {"source_doctype": doctype, "source_name": name},
            ["target_doctype", "target_name"],
            as_dict=True,
        )

    if new_ref:
        return {
            "success": True,
            "message": _("Mirrored {0} {1} created successfully.").format(
                new_ref.target_doctype, new_ref.target_name
            ),
        }

    return {
        "success": False,
        "message": _("No linked document was created. Check Intercompany Transaction Link rules or Error Log."),
    }


@frappe.whitelist()
def get_linked_counterpart_for_form(doctype, name):
    """
    Lightweight lookup used by Desk JS on Source or Target forms to display
    'Open Linked ...', 'Raise Dispute', and orphan-unlink / draft-delete controls
    without modifying source records.
    """
    if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES or not name:
        return {"counterparts": []}
    if not (hasattr(frappe, "db") and frappe.db and frappe.db.exists(doctype, name)):
        return {"counterparts": []}

    frappe.has_permission(doctype, "read", name, throw=True)
    counterparts = []

    if frappe.db.exists("DocType", "Inter Company Document Reference"):
        src_refs = frappe.get_all(
            "Inter Company Document Reference",
            filters={"source_doctype": doctype, "source_name": name},
            fields=["target_doctype", "target_name", "target_company"],
        )
        for r in src_refs:
            counterparts.append({
                "doctype": r.target_doctype,
                "name": r.target_name,
                "company": r.target_company,
                "relationship": "target",
                "exists": bool(frappe.db.exists(r.target_doctype, r.target_name)),
            })

        if not counterparts:
            ref_fields = ["source_doctype", "source_name", "source_company"]
            has_is_remote = frappe.db.has_column("Inter Company Document Reference", "is_remote")
            if has_is_remote:
                ref_fields.append("is_remote")
            tgt_refs = frappe.get_all(
                "Inter Company Document Reference",
                filters={"target_doctype": doctype, "target_name": name},
                fields=ref_fields,
            )
            for r in tgt_refs:
                is_remote = cint(r.get("is_remote")) if has_is_remote else 0
                src_exists = True if is_remote else bool(frappe.db.exists(r.source_doctype, r.source_name))
                src_status = frappe.db.get_value(r.source_doctype, r.source_name, "docstatus") if (not is_remote and src_exists) else None
                counterparts.append({
                    "doctype": r.source_doctype,
                    "name": r.source_name,
                    "company": r.source_company,
                    "relationship": "source",
                    "exists": src_exists,
                    "docstatus": src_status,
                    "is_remote": is_remote,
                })

    if not counterparts:
        linked_dt = frappe.db.get_value(doctype, name, "intercompany_linked_doc_doctype") if frappe.db.has_column(doctype, "intercompany_linked_doc_doctype") else None
        linked_name = frappe.db.get_value(doctype, name, "intercompany_linked_doc_name") if frappe.db.has_column(doctype, "intercompany_linked_doc_name") else None
        linked_co = frappe.db.get_value(doctype, name, "intercompany_linked_company") if frappe.db.has_column(doctype, "intercompany_linked_company") else None
        if linked_dt and linked_name:
            src_exists = bool(frappe.db.exists(linked_dt, linked_name))
            src_status = frappe.db.get_value(linked_dt, linked_name, "docstatus") if src_exists else None
            counterparts.append({
                "doctype": linked_dt,
                "name": linked_name,
                "company": linked_co or "",
                "relationship": "source",
                "exists": src_exists,
                "docstatus": src_status,
                "is_remote": 0,
            })

    return {"counterparts": counterparts}


@frappe.whitelist()
def delete_mirrored_draft(doctype, name):
    """Safely deletes a mirrored draft (docstatus=0) and cleans up its Inter Company Document Reference rows."""
    if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES or not name:
        frappe.throw(_("Invalid document specified for deletion."))
    if not frappe.db.exists(doctype, name):
        return {"success": True, "deleted": True}

    frappe.has_permission(doctype, "delete", name, throw=True)
    doc = frappe.get_doc(doctype, name)
    if cint(doc.docstatus) != 0:
        frappe.throw(_("Only Draft documents can be deleted directly. Please Cancel the document first."))

    cleanup_intercompany_links_on_trash(doc)
    frappe.delete_doc(doctype, name)
    return {"success": True, "deleted": True}


@frappe.whitelist()
def unlink_mirrored_document(doctype, name):
    """
    Unlinks a mirrored counterpart whose source document was deleted/cancelled (or by Admin override),
    clearing intercompany_linked_doc_* fields and any stale Inter Company Document Reference rows.
    """
    if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES or not name:
        frappe.throw(_("Invalid document specified."))
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} was not found.").format(doctype, name))

    doc = frappe.get_doc(doctype, name)
    docstatus = cint(doc.docstatus)
    has_write = frappe.has_permission(doctype, "write", doc)
    has_cancel = docstatus == 1 and frappe.has_permission(doctype, "cancel", doc)
    has_delete = docstatus in (0, 2) and frappe.has_permission(doctype, "delete", doc)
    if not (has_write or has_cancel or has_delete):
        frappe.has_permission(doctype, "cancel" if docstatus == 1 else "write", doc, throw=True)

    src_dt = doc.get("intercompany_linked_doc_doctype")
    src_name = doc.get("intercompany_linked_doc_name")
    is_admin = "System Manager" in frappe.get_roles() or "Accounts Manager" in frappe.get_roles()
    src_missing_or_cancelled = (
        not src_dt
        or not src_name
        or not frappe.db.exists(src_dt, src_name)
        or cint(frappe.db.get_value(src_dt, src_name, "docstatus")) == 2
    )

    if not src_missing_or_cancelled and not is_admin:
        frappe.throw(_("Only orphaned/cancelled links can be unlinked directly, or ask System Manager / Accounts Manager."))

    if frappe.db.exists("DocType", "Inter Company Document Reference"):
        ref_names = frappe.db.sql(
            """
            SELECT name FROM `tabInter Company Document Reference`
            WHERE target_doctype = %s AND target_name = %s
            """,
            (doctype, name),
            pluck=True,
        )
        for rn in (ref_names or []):
            frappe.delete_doc("Inter Company Document Reference", rn, ignore_permissions=True, force=True)

    _clear_mirrored_link_markers(doctype, name)
    return {"success": True, "unlinked": True}


@frappe.whitelist()
def bulk_create_linked_documents(doc_names, doctype):
    if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES:
        frappe.throw(_("DocType {0} is not supported for inter-company mirroring.").format(doctype))

    if isinstance(doc_names, str):
        doc_names = frappe.parse_json(doc_names) or []

    results = []
    for doc_name in doc_names:
        try:
            frappe.has_permission(doctype, "write", doc_name, throw=True)
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
        from pathlib import Path
        filecontent = Path(pdf_path).read_bytes()
        frappe.response["filename"] = "Inter_Company_Transactions_User_Guide.pdf"
        frappe.response["filecontent"] = filecontent
        frappe.response["type"] = "download"
    else:
        frappe.throw(_("User guide PDF file could not be found."))


@frappe.whitelist()
def get_party_target_company(party_name, party_type=None, current_company=None):
    """
    Whitelisted endpoint for client-side Desk JavaScript to dynamically resolve
    whether a selected party (Customer/Supplier) belongs to a sister company.
    """
    target = resolve_party_target_company(party_name, party_type, current_company)
    return {"target_company": target}


@frappe.whitelist()
def get_intercompany_party_map(company=None):
    """
    Returns comprehensive mapping of Customer and Supplier parties to their linked target companies.
    Sources:
    1. Intercompany Transaction Link (main_company_customer, main_company_supplier, etc.)
    2. Customer records with represents_company set
    3. Supplier records with represents_company set
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
        if frappe.db.table_exists("Intercompany Transaction Link"):
            link_filters = {"enabled": ["!=", 0]} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {}
            links = frappe.get_all(
                "Intercompany Transaction Link",
                filters=link_filters,
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

        # Also load standard ERPNext internal Customers (represents_company)
        if frappe.db.table_exists("Customer") and frappe.db.has_column("Customer", "represents_company"):
            cust_rows = frappe.get_all(
                "Customer",
                filters={"represents_company": ["is", "set"]},
                fields=["name", "customer_name", "represents_company"]
            )
            for c in cust_rows:
                rep_co = c.get("represents_company")
                if rep_co:
                    for key in [c.name, c.customer_name]:
                        if key:
                            party_map["party_to_company"][key] = rep_co
                            party_map["universal"]["customer"][key] = rep_co
                            for co in party_map["by_company"]:
                                if co != rep_co:
                                    party_map["by_company"][co]["customer"][key] = rep_co
                                    party_map["by_company"][co]["all"][key] = rep_co

        # Also load standard ERPNext internal Suppliers (represents_company)
        if frappe.db.table_exists("Supplier") and frappe.db.has_column("Supplier", "represents_company"):
            supp_rows = frappe.get_all(
                "Supplier",
                filters={"represents_company": ["is", "set"]},
                fields=["name", "supplier_name", "represents_company"]
            )
            for s in supp_rows:
                rep_co = s.get("represents_company")
                if rep_co:
                    for key in [s.name, s.supplier_name]:
                        if key:
                            party_map["party_to_company"][key] = rep_co
                            party_map["universal"]["supplier"][key] = rep_co
                            for co in party_map["by_company"]:
                                if co != rep_co:
                                    party_map["by_company"][co]["supplier"][key] = rep_co
                                    party_map["by_company"][co]["all"][key] = rep_co

    except Exception as e:
        frappe.log_error(f"Error fetching intercompany party map: {e!s}", "Intercompany Party Map")

    return party_map


def resolve_party_target_company(party_name, party_type=None, current_company=None, party_map=None):
    """
    Robust helper to determine target sister company for a given party.
    Checks:
    1. Active party_map (company-specific -> universal -> global party_to_company)
    2. Direct database queries on Customer and Supplier represents_company
    3. Direct database queries on Intercompany Linked Company records
    Guarantees that target company is NEVER the current source company.
    """
    if not party_name:
        return None

    party_name_clean = str(party_name).strip()
    party_type_clean = (party_type or "").lower().strip()

    if not party_map:
        party_map = get_intercompany_party_map(current_company)

    # 1. Check company specific mapping
    if current_company and current_company in party_map.get("by_company", {}):
        comp_dict = party_map["by_company"][current_company]
        if party_type_clean and party_type_clean in comp_dict and party_name_clean in comp_dict[party_type_clean]:
            tgt = comp_dict[party_type_clean][party_name_clean]
            if tgt and tgt != current_company:
                return tgt
        if party_name_clean in comp_dict.get("all", {}):
            tgt = comp_dict["all"][party_name_clean]
            if tgt and tgt != current_company:
                return tgt

    # 2. Check universal by party_type
    if party_type_clean and party_type_clean in party_map.get("universal", {}):
        tgt = party_map["universal"][party_type_clean].get(party_name_clean)
        if tgt and tgt != current_company:
            return tgt

    # 3. Check global party_to_company
    tgt = party_map.get("party_to_company", {}).get(party_name_clean)
    if tgt and tgt != current_company:
        return tgt

    # 4. Direct Database Fallback: Customer represents_company
    try:
        if (not party_type_clean or party_type_clean == "customer") and frappe.db.table_exists("Customer"):
            rep_co = frappe.db.get_value("Customer", party_name_clean, "represents_company")
            if not rep_co and frappe.db.has_column("Customer", "customer_name"):
                rep_co = frappe.db.get_value("Customer", {"customer_name": party_name_clean}, "represents_company")
            if rep_co and rep_co != current_company:
                return rep_co
    except Exception:
        pass

    # 5. Direct Database Fallback: Supplier represents_company
    try:
        if (not party_type_clean or party_type_clean == "supplier") and frappe.db.table_exists("Supplier"):
            rep_co = frappe.db.get_value("Supplier", party_name_clean, "represents_company")
            if not rep_co and frappe.db.has_column("Supplier", "supplier_name"):
                rep_co = frappe.db.get_value("Supplier", {"supplier_name": party_name_clean}, "represents_company")
            if rep_co and rep_co != current_company:
                return rep_co
    except Exception:
        pass

    # 6. Direct Database Fallback: Intercompany Linked Company table
    try:
        if frappe.db.table_exists("Intercompany Linked Company"):
            rows = frappe.db.sql("""
                SELECT lc.company, lc.parent, ilt.main_company,
                       lc.main_company_customer, lc.main_company_supplier,
                       lc.other_company_customer, lc.other_company_supplier
                FROM `tabIntercompany Linked Company` lc
                JOIN `tabIntercompany Transaction Link` ilt ON ilt.name = lc.parent
                WHERE (ilt.enabled IS NULL OR ilt.enabled != 0)
                  AND (
                      lc.main_company_customer = %s OR lc.main_company_supplier = %s OR
                      lc.other_company_customer = %s OR lc.other_company_supplier = %s
                  )
            """, (party_name_clean, party_name_clean, party_name_clean, party_name_clean), as_dict=True)

            for r in rows:
                if current_company == r.main_company:
                    if party_name_clean in [r.main_company_customer, r.main_company_supplier]:
                        if r.company and r.company != current_company:
                            return r.company
                elif current_company == r.company:
                    if party_name_clean in [r.other_company_customer, r.other_company_supplier]:
                        if r.main_company and r.main_company != current_company:
                            return r.main_company
                else:
                    # Generic match when current_company is not set or matches neither
                    if party_name_clean in [r.main_company_customer, r.main_company_supplier]:
                        if r.company and r.company != current_company:
                            return r.company
                    elif party_name_clean in [r.other_company_customer, r.other_company_supplier]:
                        if r.main_company and r.main_company != current_company:
                            return r.main_company
    except Exception:
        pass

    return None


def _set_row_value(row, key, value):
    if isinstance(row, dict):
        row[key] = value
    else:
        setattr(row, key, value)


def _has_row_field(row, key):
    return (isinstance(row, dict) and key in row) or hasattr(row, key)


def _precalculate_mirrored_doc_totals(doc):
    """
    Pre-calculates ERPNext derived line amounts and document totals on mirrored drafts
    before initial DB insert (since create_* builders set flags.ignore_validate = True).
    Works uniformly across all 14 supported intercompany DocTypes.
    """
    if not doc:
        return

    dt = getattr(doc, "doctype", None)
    if dt == "Journal Entry":
        company_ccy = None
        if getattr(doc, "company", None) and hasattr(frappe, "db") and frappe.db:
            try:
                company_ccy = frappe.db.get_value("Company", doc.company, "default_currency")
            except Exception:
                company_ccy = None

        for row in (doc.get("accounts") or []):
            acct = row.get("account")
            if not row.get("account_currency"):
                acc_ccy = None
                if acct and hasattr(frappe, "db") and frappe.db:
                    try:
                        acc_ccy = frappe.db.get_value("Account", acct, "account_currency")
                    except Exception:
                        acc_ccy = None
                if acc_ccy or company_ccy:
                    _set_row_value(row, "account_currency", acc_ccy or company_ccy)
            if abs(flt(row.get("exchange_rate"))) <= 0.0001:
                _set_row_value(row, "exchange_rate", 1.0)
            fx = flt(row.get("exchange_rate") or 1.0)
            if abs(flt(row.get("debit"))) <= 0.0001 and abs(flt(row.get("debit_in_account_currency"))) > 0.0001:
                _set_row_value(row, "debit", flt(flt(row.get("debit_in_account_currency")) * fx, 2))
            if abs(flt(row.get("credit"))) <= 0.0001 and abs(flt(row.get("credit_in_account_currency"))) > 0.0001:
                _set_row_value(row, "credit", flt(flt(row.get("credit_in_account_currency")) * fx, 2))

        try:
            if hasattr(doc, "set_amounts_in_company_currency"):
                doc.set_amounts_in_company_currency()
        except Exception:
            pass
        try:
            if hasattr(doc, "set_total_debit_credit"):
                doc.set_total_debit_credit()
        except Exception:
            pass

        accounts = doc.get("accounts") or []
        if accounts and abs(flt(doc.get("total_debit"))) <= 0.0001 and abs(flt(doc.get("total_credit"))) <= 0.0001:
            doc.total_debit = flt(sum(flt(r.get("debit") or r.get("debit_in_account_currency")) for r in accounts), 2)
            doc.total_credit = flt(sum(flt(r.get("credit") or r.get("credit_in_account_currency")) for r in accounts), 2)
        return

    if dt == "Stock Entry":
        try:
            if hasattr(doc, "calculate_rate_and_amount"):
                doc.calculate_rate_and_amount()
        except Exception:
            pass
        items = doc.get("items") or []
        for row in items:
            qty = flt(row.get("qty"))
            brate = flt(row.get("basic_rate"))
            if abs(flt(row.get("basic_amount"))) <= 0.0001 and qty and brate:
                _set_row_value(row, "basic_amount", flt(qty * brate, 2))
            if abs(flt(row.get("amount"))) <= 0.0001 and (flt(row.get("basic_amount")) or flt(row.get("additional_cost"))):
                _set_row_value(row, "amount", flt(flt(row.get("basic_amount")) + flt(row.get("additional_cost")), 2))
        if items and abs(flt(doc.get("total_amount"))) <= 0.0001:
            total_val = flt(sum(flt(r.get("amount") or r.get("basic_amount")) for r in items), 2)
            if _has_row_field(doc, "total_amount"):
                _set_row_value(doc, "total_amount", total_val)
            if doc.get("purpose") == "Material Receipt" and _has_row_field(doc, "total_incoming_value"):
                _set_row_value(doc, "total_incoming_value", total_val)
        return

    if dt == "Payment Entry":
        try:
            if hasattr(doc, "set_amounts"):
                doc.set_amounts()
        except Exception:
            pass
        return

    # Trading transactions (SO, PO, SI, PI, DN, PR, Quotation, Supplier Quotation)
    try:
        if hasattr(doc, "calculate_taxes_and_totals"):
            doc.calculate_taxes_and_totals()
    except Exception:
        pass
    items = doc.get("items") or []
    conv_rate = flt(doc.get("conversion_rate") or 1.0)
    for row in items:
        qty = flt(row.get("qty"))
        rate = flt(row.get("rate"))
        if abs(flt(row.get("amount"))) <= 0.0001 and qty and rate:
            amt = flt(qty * rate, 2)
            _set_row_value(row, "amount", amt)
            if _has_row_field(row, "base_rate"):
                _set_row_value(row, "base_rate", flt(rate * conv_rate, 2))
            if _has_row_field(row, "base_amount"):
                _set_row_value(row, "base_amount", flt(amt * conv_rate, 2))
    if items and abs(flt(doc.get("total"))) <= 0.0001:
        total_amt = flt(sum(flt(r.get("amount")) for r in items), 2)
        if _has_row_field(doc, "total"):
            _set_row_value(doc, "total", total_amt)
        if _has_row_field(doc, "net_total"):
            _set_row_value(doc, "net_total", total_amt)
        if _has_row_field(doc, "grand_total"):
            _set_row_value(doc, "grand_total", total_amt)


def validate_locked_mirrored_fields(doc, previous=None):
    """
    Strictly prevents modifying currency, exchange rates, parties, or financial amounts/quantities
    on mirrored intercompany counterparts created by ICT (where intercompany_linked_doc_name is set).
    Allows ERPNext to compute and populate derived 0/uninitialized totals/amounts on Submit
    when underlying quantities, unit rates, and account debit/credit inputs remain untouched.
    Local operational classification fields (Warehouse, Cost Center, Expense/Income Account) remain editable.
    """
    if not doc or not doc.get("intercompany_linked_doc_name"):
        return
    if doc.flags.get("ict_system_sync"):
        return

    src_dt = doc.get("intercompany_linked_doc_doctype")
    src_name = doc.get("intercompany_linked_doc_name")
    if (
        src_dt
        and src_name
        and hasattr(frappe, "db")
        and frappe.db
        and frappe.db.exists("DocType", src_dt)
        and not frappe.db.exists(src_dt, src_name)
    ):
        is_remote_ref = False
        if frappe.db.exists("DocType", "Inter Company Document Reference") and frappe.db.has_column("Inter Company Document Reference", "is_remote"):
            is_remote_ref = bool(
                frappe.db.get_value(
                    "Inter Company Document Reference",
                    {"target_doctype": doc.doctype, "target_name": doc.name, "is_remote": 1},
                    "name",
                )
            )
        if not is_remote_ref:
            return

    if previous is None:
        if hasattr(doc, "get_doc_before_save"):
            previous = doc.get_doc_before_save()
        if not previous and getattr(doc, "name", None) and hasattr(frappe, "db") and frappe.db and frappe.db.exists(doc.doctype, doc.name):
            try:
                previous = frappe.get_doc(doc.doctype, doc.name)
            except Exception:
                previous = None

    if not previous:
        return

    source_company = (
        doc.get("intercompany_linked_company")
        or previous.get("intercompany_linked_company")
        or doc.get("intercompany_target_company")
        or _("Source Company")
    )
    source_ref = f"{doc.get('intercompany_linked_doc_doctype') or ''} {doc.get('intercompany_linked_doc_name') or ''}".strip()

    def _differs(v_new, v_old, is_num=False):
        if is_num:
            return abs(flt(v_new) - flt(v_old)) > 0.0001
        return (v_new or "") != (v_old or "")

    changed_fields = []

    str_locked = [
        ("company", _("Company")),
        ("currency", _("Currency")),
        ("customer", _("Customer")),
        ("supplier", _("Supplier")),
        ("party_type", _("Party Type")),
        ("party", _("Party")),
        ("payment_type", _("Payment Type")),
        ("intercompany_target_company", _("Intercompany Target Company")),
    ]
    if getattr(doc, "doctype", None) == "Quotation":
        str_locked.extend([
            ("quotation_to", _("Quotation To")),
            ("party_name", _("Party Name")),
        ])

    num_locked = [
        ("paid_amount", _("Paid Amount")),
        ("received_amount", _("Received Amount")),
    ]
    # Lock exchange rates & JE aggregate totals whenever initialized (> 0) so uncalculated
    # mirrored drafts saved with ignore_validate=True (total_debit=0 / total_credit=0)
    # still submit cleanly while row-level amounts remain strictly guarded below.
    num_locked_if_nonzero = [
        ("conversion_rate", _("Exchange Rate")),
        ("source_exchange_rate", _("Source Exchange Rate")),
        ("target_exchange_rate", _("Target Exchange Rate")),
        ("total_debit", _("Total Debit")),
        ("total_credit", _("Total Credit")),
    ]

    def _has_field(obj, fieldname):
        return (isinstance(obj, dict) and fieldname in obj) or hasattr(obj, fieldname)

    for fname, label in str_locked:
        if _has_field(previous, fname):
            if fname == "currency" and not previous.get(fname):
                continue
            if _differs(doc.get(fname), previous.get(fname), is_num=False):
                changed_fields.append(label)

    for fname, label in num_locked:
        if _has_field(previous, fname):
            if _differs(doc.get(fname), previous.get(fname), is_num=True):
                changed_fields.append(label)

    for fname, label in num_locked_if_nonzero:
        if _has_field(previous, fname) and abs(flt(previous.get(fname))) > 0.0001:
            if _differs(doc.get(fname), previous.get(fname), is_num=True):
                changed_fields.append(label)

    if cint(doc.get("is_intercompany")) != cint(previous.get("is_intercompany")):
        changed_fields.append(_("Is Intercompany"))

    # Item child table locked fields (preserve item_code, qty, uom, rate/basic_rate, amount/basic_amount)
    old_items = previous.get("items") or []
    new_items = doc.get("items") or []
    if old_items:
        if len(new_items) != len(old_items):
            changed_fields.append(_("Items (Row Count)"))
        else:
            for idx, (n_row, o_row) in enumerate(zip(new_items, old_items), start=1):
                for fname, label in [("item_code", "Item Code"), ("uom", "UOM")]:
                    if _differs(n_row.get(fname), o_row.get(fname), is_num=False):
                        changed_fields.append(_("Row #{0} {1}").format(idx, _(label)))
                for fname, label in [
                    ("qty", "Qty"),
                    ("rate", "Rate"),
                    ("basic_rate", "Basic Rate"),
                    ("amount", "Amount"),
                    ("basic_amount", "Basic Amount"),
                ]:
                    o_val = o_row.get(fname)
                    n_val = n_row.get(fname)
                    if o_val is None and n_val is None:
                        continue
                    # Uncalculated derived amounts (amount=0 / basic_amount=0 from ignore_validate insert)
                    # are recomputed by ERPNext on Submit while qty, rate & basic_rate remain locked.
                    if fname in ("amount", "basic_amount") and abs(flt(o_val)) <= 0.0001:
                        continue
                    if _differs(n_val, o_val, is_num=True):
                        changed_fields.append(_("Row #{0} {1}").format(idx, _(label)))

    # Journal Entry Account child table locked fields
    old_accts = previous.get("accounts") or []
    new_accts = doc.get("accounts") or []
    if old_accts:
        if len(new_accts) != len(old_accts):
            changed_fields.append(_("Accounting Entries (Row Count)"))
        else:
            for idx, (n_row, o_row) in enumerate(zip(new_accts, old_accts), start=1):
                for fname, label in [("account_currency", "Account Currency"), ("party_type", "Party Type"), ("party", "Party")]:
                    o_val = o_row.get(fname)
                    n_val = n_row.get(fname)
                    if fname == "account_currency" and not o_val:
                        continue
                    if _differs(n_val, o_val, is_num=False):
                        changed_fields.append(_("Account Row #{0} {1}").format(idx, _(label)))
                for fname, label in [
                    ("exchange_rate", "Exchange Rate"),
                    ("debit_in_account_currency", "Debit"),
                    ("credit_in_account_currency", "Credit"),
                    ("debit", "Base Debit"),
                    ("credit", "Base Credit"),
                ]:
                    o_val = o_row.get(fname)
                    n_val = n_row.get(fname)
                    if o_val is None and n_val is None:
                        continue
                    if fname == "exchange_rate" and abs(flt(o_val)) <= 0.0001:
                        continue
                    if fname == "debit" and abs(flt(o_val)) <= 0.0001 and abs(flt(o_row.get("debit_in_account_currency"))) > 0.0001:
                        continue
                    if fname == "credit" and abs(flt(o_val)) <= 0.0001 and abs(flt(o_row.get("credit_in_account_currency"))) > 0.0001:
                        continue
                    if _differs(n_val, o_val, is_num=True):
                        changed_fields.append(_("Account Row #{0} {1}").format(idx, _(label)))

    if changed_fields:
        esc = frappe.utils.escape_html
        unique_labels = ", ".join(dict.fromkeys(changed_fields))
        frappe.throw(
            _(
                "<div style='font-size: 13px; line-height: 1.6;'>"
                "<h4><b>Mirrored Inter-Company Entry Locked</b></h4>"
                "Cannot change <b>{0}</b> because this document is linked with source entry "
                "<b>{1}</b> in company <b>{2}</b>.<br><br>"
                "To keep both companies' ledgers 100% tallied, currency, exchange rates, parties, "
                "and financial amounts are strictly read-only on mirrored drafts.<br><br>"
                "<b>Required Action:</b> Contact the accounting team in <b>{2}</b> to cancel or amend "
                "the source entry <b>{1}</b>."
                "</div>"
            ).format(esc(unique_labels), esc(source_ref), esc(source_company)),
            title=_("Inter-Company Field Locked"),
        )


def validate_intercompany_document(doc, method=None):
    """
    Unified validate doc_event across all 14 supported intercompany DocTypes:
    1. Sanitizes cross-company warehouses on Material Receipt Stock Entries.
    2. Enforces strict read-only locks on existing mirrored counterparts.
    3. Auto-detects intercompany parties & locks target company cleanly.
    4. Blocks saving/submitting cross-currency source vouchers without a valid exchange rate.
    """
    if getattr(doc, "doctype", None) == "Stock Entry":
        sanitize_intercompany_stock_entry(doc, method)

    if doc.flags.get("ict_system_sync"):
        return

    if doc.get("intercompany_linked_doc_name") or doc.get("intercompany_linked_doc_doctype"):
        validate_locked_mirrored_fields(doc)
        return

    auto_detect_intercompany_party(doc, method)

    if cint(doc.get("is_intercompany")) and doc.get("intercompany_target_company"):
        if doc.get("intercompany_target_company") == doc.get("company"):
            frappe.throw(_("Intercompany Target Company cannot be the same as Source Company ({0}).").format(doc.get("company")))
        if getattr(doc, "doctype", None) == "Stock Entry":
            validate_stock_entry_same_currency(doc.get("company"), doc.get("intercompany_target_company"))
        elif cint(doc.get("docstatus")) == 1:
            validate_intercompany_cross_currency_rate(doc)


def auto_detect_intercompany_party(doc, method=None):
    """
    Hooked on document validate:
    1. Checks if customer, supplier, Payment Entry party, or Journal Entry row party belongs to a sister company.
    2. If an intercompany party IS detected:
       - Auto-sets is_intercompany = 1
       - Strictly enforces intercompany_target_company = <Target Sister Company>
       - For Journal Entry: Auto-populates row.intercompany_target_company on applicable rows.
    3. If NO intercompany party is detected:
       - If user did not manually specify a valid target company != company:
         Enforces clean non-intercompany state (is_intercompany = 0).
    """
    if not hasattr(doc, "doctype") or not doc.get("company"):
        return

    # If document was already created by the intercompany engine as a linked document, don't overwrite
    if doc.get("intercompany_linked_doc_name") or doc.get("intercompany_linked_doc_doctype"):
        return

    company = doc.company
    party_map = get_intercompany_party_map(company)
    target_company = None

    if doc.doctype == "Quotation":
        customer = (doc.get("party_name") if doc.get("quotation_to") == "Customer" else None) or doc.get("customer")
        if customer:
            target_company = resolve_party_target_company(customer, "customer", company, party_map)

    elif doc.doctype in ["Sales Order", "Sales Invoice", "Delivery Note"]:
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
                else:
                    if hasattr(row, "intercompany_target_company") or "intercompany_target_company" in row.as_dict():
                        row.intercompany_target_company = ""

    # Case A: Intercompany party detected!
    if target_company and target_company != company:
        doc.is_intercompany = 1
        doc.intercompany_target_company = target_company
        if doc.doctype == "Journal Entry":
            for row in doc.get("accounts") or []:
                row_party = row.get("party")
                if row_party:
                    rt = resolve_party_target_company(row_party, row.get("party_type"), company, party_map)
                    if rt and rt != company:
                        row.intercompany_target_company = rt

    # Case B: No intercompany party detected
    else:
        existing_target = (doc.get("intercompany_target_company") or "").strip()
        if not existing_target or existing_target == company:
            doc.is_intercompany = 0
            doc.intercompany_target_company = ""
            if doc.doctype == "Journal Entry":
                for row in doc.get("accounts") or []:
                    if hasattr(row, "intercompany_target_company") or "intercompany_target_company" in row.as_dict():
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


