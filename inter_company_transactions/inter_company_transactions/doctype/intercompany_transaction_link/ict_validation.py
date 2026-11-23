# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from .ict_currency import validate_intercompany_cross_currency_rate, validate_stock_entry_same_currency
from .ict_utils import _facade_fn, sanitize_intercompany_stock_entry


def get_intercompany_party_map_impl(company=None):
	"""Returns comprehensive mapping of Customer and Supplier parties to their linked target companies."""
	party_map = {
		"party_to_company": {},
		"by_company": {},
		"universal": {
			"customer": {},
			"supplier": {},
		},
	}

	if not (hasattr(frappe, "db") and frappe.db):
		return party_map

	try:
		if frappe.db.table_exists("Intercompany Transaction Link"):
			link_filters = {"enabled": ["!=", 0]} if frappe.db.has_column("Intercompany Transaction Link", "enabled") else {}
			links = frappe.get_all(
				"Intercompany Transaction Link",
				filters=link_filters,
				fields=["name", "main_company"],
			)

			for link in links:
				main_co = link.main_company
				if not main_co:
					continue

				if main_co not in party_map["by_company"]:
					party_map["by_company"][main_co] = {
						"customer": {},
						"supplier": {},
						"all": {},
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
							"other_company_supplier",
						],
					)

					for row in linked_rows:
						other_co = row.company
						if not other_co:
							continue

						if other_co not in party_map["by_company"]:
							party_map["by_company"][other_co] = {
								"customer": {},
								"supplier": {},
								"all": {},
							}

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

		if frappe.db.table_exists("Customer") and frappe.db.has_column("Customer", "represents_company"):
			cust_rows = frappe.get_all(
				"Customer",
				filters={"represents_company": ["is", "set"]},
				fields=["name", "customer_name", "represents_company"],
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

		if frappe.db.table_exists("Supplier") and frappe.db.has_column("Supplier", "represents_company"):
			supp_rows = frappe.get_all(
				"Supplier",
				filters={"represents_company": ["is", "set"]},
				fields=["name", "supplier_name", "represents_company"],
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
	"""Determine target sister company for a given party without returning current_company."""
	if not party_name:
		return None

	party_name_clean = str(party_name).strip()
	party_type_clean = (party_type or "").lower().strip()

	if not party_map:
		party_map_fn = _facade_fn("get_intercompany_party_map", get_intercompany_party_map_impl)
		party_map = party_map_fn(current_company)

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

	if party_type_clean and party_type_clean in party_map.get("universal", {}):
		tgt = party_map["universal"][party_type_clean].get(party_name_clean)
		if tgt and tgt != current_company:
			return tgt

	tgt = party_map.get("party_to_company", {}).get(party_name_clean)
	if tgt and tgt != current_company:
		return tgt

	try:
		if (not party_type_clean or party_type_clean == "customer") and frappe.db.table_exists("Customer"):
			rep_co = frappe.db.get_value("Customer", party_name_clean, "represents_company")
			if not rep_co and frappe.db.has_column("Customer", "customer_name"):
				rep_co = frappe.db.get_value("Customer", {"customer_name": party_name_clean}, "represents_company")
			if rep_co and rep_co != current_company:
				return rep_co
	except Exception:
		pass

	try:
		if (not party_type_clean or party_type_clean == "supplier") and frappe.db.table_exists("Supplier"):
			rep_co = frappe.db.get_value("Supplier", party_name_clean, "represents_company")
			if not rep_co and frappe.db.has_column("Supplier", "supplier_name"):
				rep_co = frappe.db.get_value("Supplier", {"supplier_name": party_name_clean}, "represents_company")
			if rep_co and rep_co != current_company:
				return rep_co
	except Exception:
		pass

	try:
		if frappe.db.table_exists("Intercompany Linked Company"):
			rows = frappe.db.sql(
				"""
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
				""",
				(party_name_clean, party_name_clean, party_name_clean, party_name_clean),
				as_dict=True,
			)

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
					if party_name_clean in [r.main_company_customer, r.main_company_supplier]:
						if r.company and r.company != current_company:
							return r.company
					elif party_name_clean in [r.other_company_customer, r.other_company_supplier]:
						if r.main_company and r.main_company != current_company:
							return r.main_company
	except Exception:
		pass

	return None


def validate_locked_mirrored_fields(doc, previous=None):
	"""Enforces strict read-only locks on mirrored intercompany financial/party/currency fields."""
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
		get_before_save = getattr(doc, "get_doc_before_save", None)
		if callable(get_before_save):
			previous = get_before_save()
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

	expected_target_company = previous.get("intercompany_target_company") or doc.get("intercompany_linked_company")
	if expected_target_company and doc.get("intercompany_target_company") != expected_target_company:
		doc.intercompany_target_company = expected_target_company

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
		("paid_from_account_currency", _("Paid From Account Currency")),
		("paid_to_account_currency", _("Paid To Account Currency")),
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
			if fname in ("currency", "paid_from_account_currency", "paid_to_account_currency") and not previous.get(fname):
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
					if fname in ("amount", "basic_amount") and abs(flt(o_val)) <= 0.0001:
						continue
					if _differs(n_val, o_val, is_num=True):
						changed_fields.append(_("Row #{0} {1}").format(idx, _(label)))

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
	"""Unified validate doc_event across all 14 supported intercompany DocTypes."""
	if getattr(doc, "doctype", None) == "Stock Entry":
		sanitize_intercompany_stock_entry(doc, method)

	if doc.flags.get("ict_system_sync"):
		return

	if doc.get("intercompany_linked_doc_name") or doc.get("intercompany_linked_doc_doctype"):
		validate_locked_mirrored_fields(doc)
		return

	detect_fn = _facade_fn("auto_detect_intercompany_party", auto_detect_intercompany_party)
	detect_fn(doc, method)

	if cint(doc.get("is_intercompany")) and doc.get("intercompany_target_company"):
		if doc.get("intercompany_target_company") == doc.get("company"):
			frappe.throw(_("Intercompany Target Company cannot be the same as Source Company ({0}).").format(doc.get("company")))
		if getattr(doc, "doctype", None) == "Stock Entry":
			validate_stock_entry_same_currency(doc.get("company"), doc.get("intercompany_target_company"))
		elif cint(doc.get("docstatus")) == 1:
			validate_intercompany_cross_currency_rate(doc)


def auto_detect_intercompany_party(doc, method=None):
	"""Auto-detect intercompany parties and enforce intercompany_target_company cleanly on validate."""
	if not hasattr(doc, "doctype") or not doc.get("company"):
		return

	if doc.get("intercompany_linked_doc_name") or doc.get("intercompany_linked_doc_doctype"):
		return

	company = doc.company
	party_map_fn = _facade_fn("get_intercompany_party_map", get_intercompany_party_map_impl)
	party_map = party_map_fn(company)
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
	else:
		existing_target = (doc.get("intercompany_target_company") or "").strip()
		if not existing_target or existing_target == company:
			doc.is_intercompany = 0
			doc.intercompany_target_company = ""
			if doc.doctype == "Journal Entry":
				for row in doc.get("accounts") or []:
					if hasattr(row, "intercompany_target_company") or "intercompany_target_company" in row.as_dict():
						row.intercompany_target_company = ""
