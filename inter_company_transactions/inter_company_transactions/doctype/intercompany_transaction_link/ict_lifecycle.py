# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import json
import urllib.request

import frappe
from frappe import _
from frappe.utils import cint

from .ict_accounting_builders import _precalculate_mirrored_doc_totals
from .ict_builders import create_corresponding_document
from .ict_currency import validate_intercompany_cross_currency_rate
from .ict_utils import (
	_FACADE_MODULE,
	_facade_fn,
	_get_intercompany_settings,
	_log_local_mirror_error,
)


def _execute_linked_documents(doc_doctype, doc_name):
	"""Background worker entrypoint for asynchronous intercompany mirroring."""
	try:
		if not frappe.db.exists(doc_doctype, doc_name):
			return
		doc = frappe.get_doc(doc_doctype, doc_name)
		frappe.flags.ict_in_background = True
		create_fn = _facade_fn("create_linked_documents", create_linked_documents)
		create_fn(doc, None)
	finally:
		frappe.flags.ict_in_background = False


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
				"target_name": target_doc.name,
			},
		)

		if not existing_ref:
			ref_doc = frappe.get_doc({
				"doctype": "Inter Company Document Reference",
				"source_doctype": source_doc.doctype,
				"source_name": source_doc.name,
				"source_company": source_doc.company,
				"target_doctype": target_doc.doctype,
				"target_name": target_doc.name,
				"target_company": target_doc.company,
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


def create_linked_documents(doc, method=None):
	"""Create corresponding documents in all linked companies (Local & Remote Federated)."""
	if not hasattr(doc, "doctype") or not doc.get("company"):
		return

	if not cint(doc.get("is_intercompany")):
		return

	if doc.get("intercompany_linked_doc_doctype") or doc.get("intercompany_linked_doc_name"):
		return

	settings_fn = _facade_fn("_get_intercompany_settings", _get_intercompany_settings)
	settings = settings_fn()
	if not cint(settings.get("enabled", 1)):
		return

	validate_intercompany_cross_currency_rate(doc)

	if (
		settings.get("execution_mode") == "Asynchronous (Background Job)"
		and not getattr(frappe.flags, "in_test", False)
		and not getattr(frappe.flags, "ict_in_background", False)
	):
		try:
			frappe.enqueue(
				f"{_FACADE_MODULE}._execute_linked_documents",
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

	for mapping in mappings:
		target_comp = mapping.get("company")
		target_dt = mapping.get("target_doctype")
		try:
			if not target_comp or target_comp == doc.company:
				continue

			if target_company_hint and target_comp != target_company_hint:
				continue

			dedup_key = (target_comp, target_dt)
			if dedup_key in created_targets:
				continue

			if frappe.db.exists("DocType", "Inter Company Document Reference"):
				existing = frappe.db.exists(
					"Inter Company Document Reference",
					{
						"source_doctype": doc.doctype,
						"source_name": doc.name,
						"target_company": target_comp,
						"target_doctype": target_dt,
					},
				)
				if existing:
					continue

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
				is_main_to_other = doc.company == mapping["mapping"].main_company
				direction = "main_to_other" if is_main_to_other else "other_to_main"

			validate_required_parties(doc, mapping)
			validate_intercompany_items(doc, mapping)

			linked_doc = create_corresponding_document(doc, mapping, direction, settings=settings)

			if linked_doc:
				linked_doc.company = target_comp
				linked_doc.is_intercompany = 1
				linked_doc.intercompany_linked_doc_doctype = doc.doctype
				linked_doc.intercompany_linked_doc_name = doc.name
				linked_doc.intercompany_linked_company = doc.company
				linked_doc.intercompany_target_company = doc.company

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
							"Inter Company Auto Submit",
						)

				frappe.msgprint(
					_("Created {0} {1} {2} in company {3}").format(
						status_label, linked_doc.doctype, linked_doc.name, linked_doc.company
					)
				)

		except Exception as e:
			frappe.log_error(
				f"Error in intercompany creation for {doc.doctype} {doc.name}: {e!s}\n{frappe.get_traceback()}",
				"Inter Company Transaction Error",
			)
			_log_local_mirror_error(doc, target_comp, target_dt, e)
			indicator = "red" if cint(settings.get("notify_on_sync_failure", 1)) else "orange"
			frappe.msgprint(
				_("Notice for linked company {0}: {1}").format(target_comp or "", str(e)),
				indicator=indicator,
				alert=bool(cint(settings.get("notify_on_sync_failure", 1))),
			)


def get_linked_counterpart_documents(doc):
	"""Fetch all linked counterpart documents (both where doc is source and where doc is target)."""
	if not hasattr(doc, "company") or not doc.company:
		return []
	if not frappe.db.exists("DocType", "Inter Company Document Reference"):
		return []

	related_docs = []

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
	"""Checks if a document has active downstream Payment/Journal/Delivery/Receipt/Invoice records."""
	blocking_records = []

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
	"""Enforces Cancellation Authority and checks counterpart documents for active downstream records."""
	if not hasattr(doc, "company") or not doc.company:
		return

	if not cint(doc.get("is_intercompany")) and not doc.get("intercompany_linked_doc_name"):
		return

	if doc.flags.get("intercompany_auto_cancel"):
		return

	settings_fn = _facade_fn("_get_intercompany_settings", _get_intercompany_settings)
	settings = settings_fn()
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

	counterparts_fn = _facade_fn("get_linked_counterpart_documents", get_linked_counterpart_documents)
	counterparts = counterparts_fn(doc)
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
				title=_("Active Transactions Exist in Linked Company"),
			)


def cancel_linked_documents(doc, method=None):
	"""Cancel corresponding documents in all linked companies - BIDIRECTIONAL with transaction integrity."""
	if not hasattr(doc, "company") or not doc.company:
		return

	if not cint(doc.get("is_intercompany")) and not doc.get("intercompany_linked_doc_name"):
		return

	if doc.flags.get("intercompany_auto_cancel"):
		return

	if not frappe.db.exists("DocType", "Inter Company Document Reference"):
		return

	validate_intercompany_cancellation(doc)

	counterparts_fn = _facade_fn("get_linked_counterpart_documents", get_linked_counterpart_documents)
	all_related_docs = counterparts_fn(doc)

	for ld in all_related_docs:
		if ld.get("is_remote") and ld.get("remote_site_url"):
			try:
				from inter_company_transactions.sync import get_remote_site_for_company

				remote_site = get_remote_site_for_company(ld.get("company"))
				if remote_site:
					endpoint = f"{remote_site['site_url']}/api/method/inter_company_transactions.sync.cancel_remote_transaction"
					c_payload = json.dumps({"source_doctype": doc.doctype, "source_name": doc.name}).encode("utf-8")
					c_headers = {
						"Content-Type": "application/json",
						"Authorization": f"token {remote_site['api_key']}:{remote_site['api_secret']}",
					}
					c_req = urllib.request.Request(endpoint, data=c_payload, headers=c_headers, method="POST")
					with urllib.request.urlopen(c_req, timeout=10):
						frappe.msgprint(
							_("Notified remote instance ({0}) to cancel mirrored transaction.").format(remote_site["site_url"])
						)
			except Exception as ex:
				frappe.logger().error(f"Failed to cancel remote document on {ld.get('remote_site_url')}: {ex!s}")

	for related_doc in all_related_docs:
		if related_doc.get("is_remote"):
			continue

		doctype = related_doc["doctype"]
		docname = related_doc["name"]
		company = related_doc.get("company")
		relationship = related_doc.get("relationship")

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

			frappe.msgprint(
				_("Cancelled {0} {1} in company {2} ({3} document)").format(
					target_doc.doctype, target_doc.name, company or getattr(target_doc, "company", ""), relationship
				)
			)
		except Exception as e:
			frappe.throw(
				_(
					"<b>Inter-Company Cancellation Failed:</b><br>"
					"Failed to cancel linked {0} <b>{1}</b> in company <b>{2}</b>.<br>"
					"Error: {3}<br><br>"
					"The cancellation of <b>{4} {5}</b> has been aborted to preserve accounting ledger consistency."
				).format(doctype, docname, company or getattr(target_doc, "company", ""), str(e), doc.doctype, doc.name),
				title=_("Inter-Company Cancellation Aborted"),
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
	"""Purge Inter Company Document Reference & Error Log rows and unlink surviving targets on trash."""
	if not hasattr(doc, "doctype") or not getattr(doc, "name", None):
		return
	if not (hasattr(frappe, "db") and frappe.db):
		return

	clear_fn = _facade_fn("_clear_mirrored_link_markers", _clear_mirrored_link_markers)
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
					clear_fn(ref.get("target_doctype"), ref.get("target_name"))
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


def resolve_target_doctype(source_doctype, trans_type, direction):
	"""Resolves the target DocType given the source DocType, mapping rule, and transaction flow direction."""
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


def find_applicable_mappings(doc):
	"""Finds unique, valid matching mapping configurations for the document."""
	if not hasattr(doc, "company") or not doc.company:
		return []

	if not cint(doc.get("is_intercompany")):
		return []

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

	if not target_company_hint or target_company_hint == source_company:
		return []

	links = frappe.get_all(
		"Intercompany Transaction Link",
		filters={"enabled": 1} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {},
		fields=["name", "main_company"],
	)

	for link_entry in links:
		link = frappe.get_doc("Intercompany Transaction Link", link_entry.name)

		is_main = source_company == link.main_company
		is_linked = any(lc.company == source_company for lc in (link.linked_companies or []))

		if not is_main and not is_linked:
			continue

		if is_main:
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
							"target_doctype": target_dt,
						})
		else:
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
						"target_doctype": target_dt,
					})

	return mappings


def validate_required_parties(doc, mapping):
	"""Validate that required parties are configured based on target transaction type."""
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
	"""Validate that all items can be resolved for the target company."""
	if getattr(doc, "doctype", "") == "Landed Cost Voucher":
		return

	if not hasattr(doc, "items") or not doc.get("items"):
		return

	auto_create = True
	try:
		if frappe.db.exists("DocType", "Inter Company Settings"):
			settings = frappe.get_single("Inter Company Settings")
			if settings.auto_create_missing_items is not None:
				auto_create = bool(cint(settings.auto_create_missing_items))
	except Exception:
		pass

	if auto_create:
		return

	target_company = mapping.get("company")
	link_doc = mapping.get("mapping")

	unresolved_items = []
	for item in doc.items:
		src_code = item.get("item_code") if isinstance(item, dict) else getattr(item, "item_code", None)
		if not src_code:
			continue

		mapped = False
		if link_doc and hasattr(link_doc, "item_mappings"):
			for row in (link_doc.get("item_mappings") or []):
				if row.source_item_code == src_code and (not row.target_company or row.target_company == target_company):
					if frappe.db.exists("Item", row.target_item_code):
						mapped = True
						break

		if not mapped and frappe.db.exists("DocType", "Intercompany Item Mapping"):
			target_sku = frappe.db.get_value(
				"Intercompany Item Mapping",
				{"source_item_code": src_code, "target_company": target_company},
				"target_item_code",
			)
			if target_sku and frappe.db.exists("Item", target_sku):
				mapped = True

		if not mapped and frappe.db.exists("Item", src_code):
			mapped = True

		if not mapped:
			unresolved_items.append(src_code)

	if unresolved_items:
		items_str = ", ".join(f"'{c}'" for c in sorted(set(unresolved_items)))
		frappe.throw(
			_(
				"Intercompany Item Error: The following item(s) do not exist for sister company '{0}': {1}. "
				"Please either map them in 'Intercompany Transaction Link' -> 'SKU / Item Code Mappings', "
				"create them in the item catalog, or enable 'Auto-Create Missing Items' in 'Inter Company Settings'."
			).format(target_company, items_str),
			title=_("Item Mapping Required"),
		)
