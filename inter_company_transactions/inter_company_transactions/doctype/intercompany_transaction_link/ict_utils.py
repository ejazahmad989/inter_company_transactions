# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import ast
import re
import sys

import frappe
from frappe.utils import cint, flt

_FACADE_MODULE = (
	"inter_company_transactions.inter_company_transactions.doctype"
	".intercompany_transaction_link.intercompany_transaction_link"
)


def _facade_fn(name, fallback):
	"""Resolve a function via the facade module so unittest.mock.patch on intercompany_transaction_link works."""
	mod = sys.modules.get(_FACADE_MODULE)
	fn = getattr(mod, name, None) if mod is not None else None
	return fn if fn is not None else fallback


def _safe_flt(val, precision=None):
	"""
	Safe float conversion with optional precision rounding.
	Uses frappe.utils.flt(val, precision) first; if uncached System Settings inside Frappe
	causes flt()'s internal rounded() call to fall back to 0.0 on a non-zero number,
	falls back cleanly to Python round(raw, precision).
	"""
	raw = flt(val)
	if precision is None:
		return raw
	p = cint(precision)
	res = flt(raw, p)
	py_rounded = round(raw, p)
	if res == 0.0 and py_rounded != 0.0:
		return py_rounded
	return res


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


def get_default_warehouse(company):
	"""Get default warehouse for company."""
	return frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0},
		"name",
	)


def get_default_cost_center(company):
	"""Get default cost center for company."""
	return frappe.db.get_value("Company", company, "cost_center")


def get_mapped_account(account, to_company):
	"""Get corresponding account in target company."""
	account_type = frappe.db.get_value("Account", account, "account_type")
	account_name = frappe.db.get_value("Account", account, "account_name")

	mapped_account = frappe.db.get_value(
		"Account",
		{"account_name": account_name, "company": to_company},
		"name",
	)

	if not mapped_account and account_type:
		mapped_account = frappe.db.get_value(
			"Account",
			{"account_type": account_type, "company": to_company, "is_group": 0},
			"name",
		)

	if not mapped_account:
		if account_type == "Receivable":
			mapped_account = frappe.db.get_value("Company", to_company, "default_receivable_account")
		elif account_type == "Payable":
			mapped_account = frappe.db.get_value("Company", to_company, "default_payable_account")
		else:
			mapped_account = frappe.db.get_value("Company", to_company, "default_expense_account")

	return mapped_account


def get_or_create_ict_parent_group(company):
	"""
	Finds or creates a dedicated 'ICT_ACC' (Inter Company Transaction Accounts) group folder
	under Current Assets -> Asset for organizing single all-in-one Bank-typed TMP-<ABBR> accounts.
	"""
	if not company or not (hasattr(frappe, "db") and frappe.db):
		return None

	existing = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"is_group": 1,
			"root_type": "Asset",
			"account_name": ["in", ["ICT_ACC", "Inter Company Transaction Accounts"]],
		},
		"name",
	)
	if existing:
		return existing

	current_assets = (
		frappe.db.get_value(
			"Account",
			{
				"company": company,
				"is_group": 1,
				"root_type": "Asset",
				"account_name": ["in", ["Current Assets", "Current Asset"]],
			},
			"name",
		)
		or frappe.db.get_value(
			"Account",
			{
				"company": company,
				"is_group": 1,
				"root_type": "Asset",
				"account_name": ["like", "%Current Asset%"],
			},
			"name",
		)
		or frappe.db.get_value(
			"Account",
			{
				"company": company,
				"is_group": 1,
				"root_type": "Asset",
				"parent_account": ["is", "set"],
			},
			"name",
		)
	)
	if not current_assets:
		return None

	try:
		grp = frappe.get_doc({
			"doctype": "Account",
			"account_name": "ICT_ACC",
			"company": company,
			"parent_account": current_assets,
			"root_type": "Asset",
			"account_type": "",
			"is_group": 1,
		})
		grp.flags.ignore_permissions = True
		grp.flags.ignore_mandatory = True
		grp.insert()
		return grp.name
	except Exception:
		return None


def get_parent_clearing_account(company):
	"""
	Finds or provisions the dedicated 'ICT_ACC' group account under Current Assets,
	falling back to Bank Accounts / Current Assets for Intercompany Bank-typed TMP-<ABBR> accounts.
	"""
	if not company or not (hasattr(frappe, "db") and frappe.db):
		return None

	ict_group = get_or_create_ict_parent_group(company)
	if ict_group:
		return ict_group

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
	cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(company)).upper()
	return cleaned[:6] or "IC"


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

	find_fn = _facade_fn("find_existing_clearing_account", find_existing_clearing_account)
	existing_valid = find_fn(company, sister_company)
	if existing_valid:
		return existing_valid

	sister_clean = (sister_company or "").strip()
	sister_abbr = _get_company_abbr_token(sister_clean) if sister_clean else "IC"
	acc_label = f"TMP-{sister_abbr}"

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
			try:
				frappe.db.set_value("Account", existing_same_name.name, "account_type", "Bank")
				return existing_same_name.name
			except Exception:
				acc_label = f"TMP-{sister_abbr}-Bank"

	try:
		parent_fn = _facade_fn("get_parent_clearing_account", get_parent_clearing_account)
		parent_account = parent_fn(company)
		if not parent_account:
			return (
				frappe.db.get_value("Company", company, "default_bank_account")
				or frappe.db.get_value("Company", company, "default_cash_account")
			)

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
		frappe.log_error(
			f"Error auto-creating intercompany TMP Bank account in {company}: {e}",
			"Intercompany Accounting",
		)
		return (
			frappe.db.get_value("Company", company, "default_bank_account")
			or frappe.db.get_value("Company", company, "default_cash_account")
		)


def get_intercompany_warehouse(company):
	"""Get inter-company / transit warehouse for a company (v15/v16 schema safe)."""
	warehouse = None
	if hasattr(frappe, "db") and frappe.db and frappe.db.has_column("Warehouse", "is_intercompany_warehouse"):
		warehouse = frappe.db.get_value(
			"Warehouse",
			{"company": company, "is_intercompany_warehouse": 1, "is_group": 0},
			"name",
		)
	if not warehouse:
		warehouse = frappe.db.get_value(
			"Warehouse",
			{"company": company, "warehouse_name": ["like", "%inter%company%"], "is_group": 0},
			"name",
		)
	if not warehouse:
		warehouse = frappe.db.get_value(
			"Warehouse",
			{"company": company, "warehouse_name": ["like", "%transit%"], "is_group": 0},
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

	try:
		parent_wh = (
			frappe.db.get_value(
				"Warehouse",
				{"company": company, "is_group": 1, "warehouse_name": ["like", "%All Warehouses%"]},
				"name",
			)
			or frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")
		)

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
				if (
					(ps.get("property") == "default" and ps.get("field_name") == "intercompany_target_company")
					or _is_corrupted_or_invalid_eval_expr(ps.get("value"))
				):
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


def fix_legacy_custom_fields(force=False):
	"""
	Sanitizes glued operators like '1or(' and ensures field expressions
	are valid both for JavaScript and Python.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return

	try:
		_sanitize_intercompany_stock_entry_custom_fields(force=True)

		if frappe.db.table_exists("Custom Field"):
			frappe.db.sql("""
				DELETE FROM `tabCustom Field`
				WHERE `dt` IN ('Customer Group', 'Supplier Group', 'Item Group') AND `fieldname` = 'custom_company'
			""")
			obsolete_master_fields = [
				("Customer", "ic_customer_group"),
				("Supplier", "ic_supplier_group"),
				("Item", "is_intercompany_item"),
				("Item", "ic_item_group"),
				("Warehouse", "is_intercompany_warehouse"),
				("Warehouse", "ic_warehouse"),
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

		tx_doctypes = [
			"Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
			"Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation",
			"Material Request", "Stock Entry", "Journal Entry", "Payment Entry",
			"Request for Quotation", "Landed Cost Voucher",
		]
		for dt in tx_doctypes:
			try:
				if (
					frappe.db.table_exists(dt)
					and frappe.db.has_column(dt, "is_intercompany")
					and frappe.db.has_column(dt, "intercompany_target_company")
				):
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


def backfill_sister_company_names():
	"""
	Ensure all existing Intercompany Transaction Link records have their
	sister_company column populated and properly named/titled so list views
	display the Sister Company name instead of random hash IDs.
	"""
	if not frappe.db.exists("DocType", "Intercompany Transaction Link"):
		return

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
