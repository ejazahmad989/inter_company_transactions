# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import os
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from .ict_lifecycle import (
	_clear_mirrored_link_markers,
	cleanup_intercompany_links_on_trash,
	create_linked_documents,
	find_applicable_mappings,
)
from .ict_utils import (
	_facade_fn,
	_get_company_abbr_token,
	find_existing_clearing_account,
	get_intercompany_warehouse,
)
from .ict_validation import resolve_party_target_company

_SUPPORTED_INTERCOMPANY_DOCTYPES = {
	"Sales Order",
	"Purchase Order",
	"Sales Invoice",
	"Purchase Invoice",
	"Delivery Note",
	"Purchase Receipt",
	"Stock Entry",
	"Journal Entry",
	"Payment Entry",
	"Quotation",
	"Supplier Quotation",
	"Material Request",
	"Request for Quotation",
	"Landed Cost Voucher",
}


def scan_linked_company_defaults_impl(main_company, other_company):
	"""
	Read-only CoA & warehouse scanner for Intercompany Linked Company rows.
	Finds existing Bank/Cash TMP-<ABBR> clearing accounts and transit warehouses
	(only when both companies share the same base currency).
	Customer and Supplier fields remain unset so users choose them explicitly.
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
		"main_currency": None,
		"other_currency": None,
		"same_currency": True,
		"main_suggested_tmp": f"TMP-{_get_company_abbr_token(other_company)}" if other_company else None,
		"other_suggested_tmp": f"TMP-{_get_company_abbr_token(main_company)}" if main_company else None,
	}
	if not main_company or not other_company or not (hasattr(frappe, "db") and frappe.db):
		return result

	main_currency = frappe.db.get_value("Company", main_company, "default_currency")
	other_currency = frappe.db.get_value("Company", other_company, "default_currency")
	same_currency = not (main_currency and other_currency and main_currency != other_currency)
	result["main_currency"] = main_currency
	result["other_currency"] = other_currency
	result["same_currency"] = bool(same_currency)

	find_acct_fn = _facade_fn("find_existing_clearing_account", find_existing_clearing_account)
	get_wh_fn = _facade_fn("get_intercompany_warehouse", get_intercompany_warehouse)

	result["main_company_account"] = find_acct_fn(main_company, other_company)
	result["other_company_account"] = find_acct_fn(other_company, main_company)
	if same_currency:
		result["main_company_warehouse"] = get_wh_fn(main_company)
		result["other_company_warehouse"] = get_wh_fn(other_company)

	return result


def get_company_currencies_impl(companies=None):
	"""Return {company_name: default_currency} for the requested list of companies."""
	if isinstance(companies, str):
		companies = frappe.parse_json(companies) or []
	if not isinstance(companies, (list, tuple, set)):
		return {}
	currencies = {}
	if not (hasattr(frappe, "db") and frappe.db):
		return currencies
	for comp in companies:
		name = (comp or "").strip() if isinstance(comp, str) else ""
		if name and name not in currencies:
			currencies[name] = frappe.db.get_value("Company", name, "default_currency")
	return currencies


def intercompany_party_query_impl(doctype, txt, searchfield, start, page_len, filters):
	"""Filter Customer/Supplier dropdowns to active parties belonging to/allowed in selected company."""
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

	has_company_col = bool(hasattr(frappe, "db") and frappe.db and frappe.db.has_column(doctype, "company"))
	has_party_account = bool(hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Party Account"))
	has_att = bool(hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Allowed To Transact With"))

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


def intercompany_account_query_impl(doctype, txt, searchfield, start, page_len, filters):
	"""Filter Account dropdowns strictly to active non-group accounts belonging to selected company."""
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


def trigger_manual_intercompany_sync_impl(doctype, name):
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

	create_fn = _facade_fn("create_linked_documents", create_linked_documents)
	create_fn(doc, None)

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


def get_linked_counterpart_for_form_impl(doctype, name):
	"""Lightweight lookup used by Desk JS on Source or Target forms."""
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


def delete_mirrored_draft_impl(doctype, name):
	"""Safely deletes a mirrored draft (docstatus=0) and cleans up its Document Reference rows."""
	if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES or not name:
		frappe.throw(_("Invalid document specified for deletion."))
	if not frappe.db.exists(doctype, name):
		return {"success": True, "deleted": True}

	frappe.has_permission(doctype, "delete", name, throw=True)
	doc = frappe.get_doc(doctype, name)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only Draft documents can be deleted directly. Please Cancel the document first."))

	cleanup_fn = _facade_fn("cleanup_intercompany_links_on_trash", cleanup_intercompany_links_on_trash)
	cleanup_fn(doc)
	frappe.delete_doc(doctype, name)
	return {"success": True, "deleted": True}


def unlink_mirrored_document_impl(doctype, name):
	"""Unlinks a mirrored counterpart whose source document was deleted/cancelled (or by Admin override)."""
	if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES or not name:
		frappe.throw(_("Invalid document specified."))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} was not found.").format(doctype, name))

	doc = frappe.get_doc(doctype, name)
	docstatus = cint(doc.docstatus)
	has_write = False
	if frappe.has_permission(doctype, "write", doc):
		has_write = True
	has_cancel = False
	if docstatus == 1:
		if frappe.has_permission(doctype, "cancel", doc):
			has_cancel = True
	has_delete = False
	if docstatus in (0, 2):
		if frappe.has_permission(doctype, "delete", doc):
			has_delete = True
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

	clear_fn = _facade_fn("_clear_mirrored_link_markers", _clear_mirrored_link_markers)
	clear_fn(doctype, name)
	return {"success": True, "unlinked": True}


def bulk_create_linked_documents_impl(doc_names, doctype):
	if doctype not in _SUPPORTED_INTERCOMPANY_DOCTYPES:
		frappe.throw(_("DocType {0} is not supported for inter-company mirroring.").format(doctype))

	if isinstance(doc_names, str):
		doc_names = frappe.parse_json(doc_names) or []

	create_fn = _facade_fn("create_linked_documents", create_linked_documents)
	results = []
	for doc_name in doc_names:
		try:
			frappe.has_permission(doctype, "write", doc_name, throw=True)
			doc = frappe.get_doc(doctype, doc_name)
			create_fn(doc, None)
			results.append({"name": doc_name, "status": "success"})
		except Exception as e:
			results.append({"name": doc_name, "status": "error", "message": str(e)})
	return results


def _get_pair_ledger_accounts_and_parties(company_a, company_b):
	"""Return configured clearing accounts and intercompany parties for (company_a, company_b)."""
	accounts_a, accounts_b = set(), set()
	parties_a, parties_b = set(), set()

	if not (
		hasattr(frappe, "db")
		and frappe.db
		and frappe.db.table_exists("Intercompany Transaction Link")
		and frappe.db.table_exists("Intercompany Linked Company")
	):
		return accounts_a, accounts_b, parties_a, parties_b

	rows = frappe.db.sql(
		"""
		SELECT
			ilt.main_company,
			lc.company,
			lc.main_company_account,
			lc.other_company_account,
			lc.main_company_customer,
			lc.main_company_supplier,
			lc.other_company_customer,
			lc.other_company_supplier
		FROM `tabIntercompany Linked Company` lc
		JOIN `tabIntercompany Transaction Link` ilt ON ilt.name = lc.parent
		WHERE (ilt.enabled IS NULL OR ilt.enabled != 0)
		  AND (
		      (ilt.main_company = %s AND lc.company = %s)
		      OR (ilt.main_company = %s AND lc.company = %s)
		  )
		""",
		(company_a, company_b, company_b, company_a),
		as_dict=True,
	)
	for r in rows or []:
		if r.main_company == company_a:
			if r.main_company_account:
				accounts_a.add(r.main_company_account)
			if r.other_company_account:
				accounts_b.add(r.other_company_account)
			for p in (r.main_company_customer, r.main_company_supplier):
				if p:
					parties_a.add(p)
			for p in (r.other_company_customer, r.other_company_supplier):
				if p:
					parties_b.add(p)
		else:
			if r.other_company_account:
				accounts_a.add(r.other_company_account)
			if r.main_company_account:
				accounts_b.add(r.main_company_account)
			for p in (r.other_company_customer, r.other_company_supplier):
				if p:
					parties_a.add(p)
			for p in (r.main_company_customer, r.main_company_supplier):
				if p:
					parties_b.add(p)

	return accounts_a, accounts_b, parties_a, parties_b


def _query_company_intercompany_gl_balance(company, accounts, parties):
	"""Compute net GL balance (debit - credit) across a company's intercompany accounts and parties."""
	if not (hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("GL Entry")):
		return 0.0
	if not accounts and not parties:
		return 0.0

	if accounts and parties:
		res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(debit - credit), 0)
			FROM `tabGL Entry`
			WHERE company = %(company)s
			  AND is_cancelled = 0
			  AND (account IN %(accounts)s OR party IN %(parties)s)
			""",
			{"company": company, "accounts": tuple(accounts), "parties": tuple(parties)},
		)
	elif accounts:
		res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(debit - credit), 0)
			FROM `tabGL Entry`
			WHERE company = %(company)s
			  AND is_cancelled = 0
			  AND account IN %(accounts)s
			""",
			{"company": company, "accounts": tuple(accounts)},
		)
	else:
		res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(debit - credit), 0)
			FROM `tabGL Entry`
			WHERE company = %(company)s
			  AND is_cancelled = 0
			  AND party IN %(parties)s
			""",
			{"company": company, "parties": tuple(parties)},
		)
	return flt(res[0][0] if res and res[0] else 0.0, 2)


def get_intercompany_balance(company_a, company_b):
	"""Calculate intercompany document count and net GL ledger balance between two companies."""
	tx_count = 0
	if hasattr(frappe, "db") and frappe.db and frappe.db.table_exists("Inter Company Document Reference"):
		res = frappe.db.sql(
			"""
			SELECT COUNT(*)
			FROM `tabInter Company Document Reference`
			WHERE (source_company = %s AND target_company = %s)
			   OR (source_company = %s AND target_company = %s)
			""",
			(company_a, company_b, company_b, company_a),
		)
		tx_count = cint(res[0][0] if res and res[0] else 0)

	accounts_a, accounts_b, parties_a, parties_b = _get_pair_ledger_accounts_and_parties(company_a, company_b)
	bal_a = _query_company_intercompany_gl_balance(company_a, accounts_a, parties_a)
	bal_b = _query_company_intercompany_gl_balance(company_b, accounts_b, parties_b)
	net_variance = flt(bal_a + bal_b, 2)

	return {
		"company_a": company_a,
		"company_b": company_b,
		"transactions_count": tx_count,
		"company_a_balance": bal_a,
		"company_b_balance": bal_b,
		"net_variance": net_variance,
		"is_reconciled": abs(net_variance) < 0.01,
	}


def reconcile_intercompany_accounts_impl():
	"""Reconcile intercompany clearing and party GL balances across linked company pairs."""
	seen_pairs = set()
	ordered_pairs = []

	if (
		hasattr(frappe, "db")
		and frappe.db
		and frappe.db.table_exists("Intercompany Transaction Link")
		and frappe.db.table_exists("Intercompany Linked Company")
	):
		rows = frappe.db.sql(
			"""
			SELECT ilt.main_company, lc.company
			FROM `tabIntercompany Linked Company` lc
			JOIN `tabIntercompany Transaction Link` ilt ON ilt.name = lc.parent
			WHERE (ilt.enabled IS NULL OR ilt.enabled != 0)
			  AND ilt.main_company IS NOT NULL AND ilt.main_company != ''
			  AND lc.company IS NOT NULL AND lc.company != ''
			""",
			as_dict=True,
		)
		for r in rows or []:
			if r.main_company != r.company:
				pair_key = tuple(sorted((r.main_company, r.company)))
				if pair_key not in seen_pairs:
					seen_pairs.add(pair_key)
					ordered_pairs.append(pair_key)

	if not ordered_pairs and hasattr(frappe, "get_all"):
		companies = frappe.get_all("Company", pluck="name") or []
		for idx, company_a in enumerate(companies):
			for company_b in companies[idx + 1:]:
				if company_a != company_b:
					pair_key = tuple(sorted((company_a, company_b)))
					if pair_key not in seen_pairs:
						seen_pairs.add(pair_key)
						ordered_pairs.append(pair_key)

	return [get_intercompany_balance(company_a, company_b) for company_a, company_b in ordered_pairs]


def get_intercompany_dashboard_data_impl(company):
	"""Return live intercompany metrics and recent synced documents for the requested company."""
	result = {
		"company": company,
		"pending_documents": 0,
		"monthly_volume": 0.0,
		"outstanding_balances": 0.0,
		"recent_transactions": [],
	}
	if not company or not (hasattr(frappe, "db") and frappe.db):
		return result

	if frappe.db.table_exists("Inter Company Error Log"):
		err_res = frappe.db.sql(
			"""
			SELECT COUNT(*)
			FROM `tabInter Company Error Log`
			WHERE status IN ('Failed', 'Pending Retry')
			  AND (source_company = %s OR target_company = %s)
			""",
			(company, company),
		)
		result["pending_documents"] += cint(err_res[0][0] if err_res and err_res[0] else 0)

	if frappe.db.table_exists("Inter Company Document Reference"):
		pending_ref_res = frappe.db.sql(
			"""
			SELECT COUNT(*)
			FROM `tabInter Company Document Reference`
			WHERE (source_company = %s OR target_company = %s)
			  AND (target_name IS NULL OR target_name = '')
			""",
			(company, company),
		)
		result["pending_documents"] += cint(pending_ref_res[0][0] if pending_ref_res and pending_ref_res[0] else 0)

		result["recent_transactions"] = frappe.db.sql(
			"""
			SELECT
				name, source_doctype, source_name, source_company,
				target_doctype, target_name, target_company, modified
			FROM `tabInter Company Document Reference`
			WHERE source_company = %s OR target_company = %s
			ORDER BY modified DESC
			LIMIT 10
			""",
			(company, company),
			as_dict=True,
		) or []

	since_date = add_days(nowdate(), -30)
	volume_queries = (
		(
			"Sales Invoice",
			"grand_total",
			"posting_date",
			"SELECT COALESCE(SUM(`grand_total`), 0) FROM `tabSales Invoice` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `posting_date` >= %s",
		),
		(
			"Purchase Invoice",
			"grand_total",
			"posting_date",
			"SELECT COALESCE(SUM(`grand_total`), 0) FROM `tabPurchase Invoice` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `posting_date` >= %s",
		),
		(
			"Sales Order",
			"grand_total",
			"transaction_date",
			"SELECT COALESCE(SUM(`grand_total`), 0) FROM `tabSales Order` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `transaction_date` >= %s",
		),
		(
			"Purchase Order",
			"grand_total",
			"transaction_date",
			"SELECT COALESCE(SUM(`grand_total`), 0) FROM `tabPurchase Order` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `transaction_date` >= %s",
		),
		(
			"Payment Entry",
			"paid_amount",
			"posting_date",
			"SELECT COALESCE(SUM(`paid_amount`), 0) FROM `tabPayment Entry` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `posting_date` >= %s",
		),
		(
			"Journal Entry",
			"total_debit",
			"posting_date",
			"SELECT COALESCE(SUM(`total_debit`), 0) FROM `tabJournal Entry` WHERE company = %s AND docstatus = 1 AND is_intercompany = 1 AND `posting_date` >= %s",
		),
	)
	monthly_volume = 0.0
	for dt, amount_col, date_col, query_sql in volume_queries:
		if (
			frappe.db.table_exists(dt)
			and frappe.db.has_column(dt, "is_intercompany")
			and frappe.db.has_column(dt, amount_col)
			and frappe.db.has_column(dt, date_col)
		):
			vol_res = frappe.db.sql(query_sql, (company, since_date))
			monthly_volume += flt(vol_res[0][0] if vol_res and vol_res[0] else 0.0)
	result["monthly_volume"] = flt(monthly_volume, 2)

	if frappe.db.table_exists("Intercompany Transaction Link") and frappe.db.table_exists("Intercompany Linked Company"):
		all_accts, all_parties = set(), set()
		link_rows = frappe.db.sql(
			"""
			SELECT ilt.main_company, lc.company,
				lc.main_company_account, lc.other_company_account,
				lc.main_company_customer, lc.main_company_supplier,
				lc.other_company_customer, lc.other_company_supplier
			FROM `tabIntercompany Linked Company` lc
			JOIN `tabIntercompany Transaction Link` ilt ON ilt.name = lc.parent
			WHERE (ilt.enabled IS NULL OR ilt.enabled != 0)
			  AND (ilt.main_company = %s OR lc.company = %s)
			""",
			(company, company),
			as_dict=True,
		)
		for lr in link_rows or []:
			if lr.main_company == company:
				if lr.main_company_account:
					all_accts.add(lr.main_company_account)
				for p in (lr.main_company_customer, lr.main_company_supplier):
					if p:
						all_parties.add(p)
			if lr.company == company:
				if lr.other_company_account:
					all_accts.add(lr.other_company_account)
				for p in (lr.other_company_customer, lr.other_company_supplier):
					if p:
						all_parties.add(p)
		result["outstanding_balances"] = _query_company_intercompany_gl_balance(company, all_accts, all_parties)

	return result


def download_user_guide_pdf_impl():
	"""Download the comprehensive PDF User Guide directly from ERPNext Desk."""
	app_path = frappe.get_app_path("inter_company_transactions")
	pdf_path = os.path.join(app_path, "public", "Inter_Company_Transactions_User_Guide.pdf")
	if not os.path.exists(pdf_path):
		try:
			from inter_company_transactions.generate_pdf_guide import create_pdf

			pdf_path = create_pdf()
		except Exception:
			pass

	if os.path.exists(pdf_path):
		filecontent = Path(pdf_path).read_bytes()
		frappe.response["filename"] = "Inter_Company_Transactions_User_Guide.pdf"
		frappe.response["filecontent"] = filecontent
		frappe.response["type"] = "download"
	else:
		frappe.throw(_("User guide PDF file could not be found."))


def get_party_target_company_impl(party_name, party_type=None, current_company=None):
	"""Resolve whether a selected party (Customer/Supplier) belongs to a sister company."""
	target = resolve_party_target_company(party_name, party_type, current_company)
	return {"target_company": target}
