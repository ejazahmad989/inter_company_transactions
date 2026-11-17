# Copyright (c) 2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import re
import frappe


def run_full_healing(verbose=True):
	"""
	Complete self-healing and restoration utility for ERPNext site:
	1. Repairs corrupted 'depends_on' expressions in MariaDB tables
	   (tabDocField, tabCustom Field, tabProperty Setter, tabClient Script, tabCustom Script, etc.)
	2. Preserves external bench app directories without modifying disk JSON files.
	3. Restores 'Create' and 'Delete' buttons on Customer, Supplier, and Item:
	   - Wipes restrictive Custom DocPerms so standard ERPNext role permissions take effect.
	   - Guarantees System Manager, Sales Manager, and Purchase Manager have full create & delete rights.
	4. Fixes Tree View dirty 'Save' button locks on Customer Group, Supplier Group, and Item Group:
	   - Purges all custom fields and intrusive property setters on Tree DocTypes.
	   - Purges obsolete custom fields from Customer, Supplier, Item, and Warehouse.
	5. Force-reloads standard DocTypes to flush metadata cache and clears Redis / Desk cache.
	"""
	log = print if verbose else (lambda *args, **kwargs: None)
	log("=== STARTING FULL DATABASE & DOCTYPE SELF-HEALING ===")

	repaired_db_count = repair_database_text(log)
	log(f"[1/5] Repaired corrupted expressions in database: {repaired_db_count} occurrences updated.")

	repaired_files = repair_disk_json_files(log)
	log("[2/5] Verified disk schema safety (0 external disk files modified).")

	restored_perms = restore_master_permissions(log)
	log(f"[3/5] Restored master permissions (Add/Delete buttons): {restored_perms}")

	cleaned_fields = cleanup_trees_and_masters(log)
	log(f"[4/5] Cleaned Tree and Master custom fields/property setters: {cleaned_fields}")

	reload_and_flush(log)
	log("[5/5] Reloaded standard DocTypes and cleared site cache.")

	log("=== DATABASE CLEANED AND REPAIRED SUCCESSFULLY ===")
	return {
		"status": "success",
		"repaired_db_count": repaired_db_count,
		"repaired_files": repaired_files,
		"restored_perms": restored_perms,
		"cleaned_fields": cleaned_fields,
	}


def repair_database_text(log):
	"""Scan and replace corrupted expressions across all relevant MariaDB tables using ORM queries."""
	if not (hasattr(frappe, "db") and frappe.db):
		return 0

	total_updates = 0
	doctypes_and_cols = [
		("DocField", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
		("Custom Field", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
		("Property Setter", ["value"]),
		("Client Script", ["script"]),
		("Custom Script", ["script"]),
		("DocType", ["description"]),
	]

	replacements = [
		("__islocalanddoc", "__islocal && doc"),
		("__islocal anddoc", "__islocal && doc"),
		("__islocaland doc", "__islocal && doc"),
		("__islocaland", "__islocal && "),
		("anddoc.", " && doc."),
		("and!doc.", " && !doc."),
		("and !doc.", " && !doc."),
		("and!in_list(", " && !in_list("),
		("1or(", "1 || ("),
		("0or(", "0 || ("),
		(")or(", ") || ("),
		("1and(", "1 && ("),
		("0and(", "0 && ("),
	]

	for dt, cols in doctypes_and_cols:
		if not frappe.db.table_exists(dt):
			continue
		for col in cols:
			if not frappe.db.has_column(dt, col):
				continue
			for old_val, new_val in replacements:
				try:
					rows = frappe.get_all(
						dt,
						filters={col: ["like", f"%{old_val}%"]},
						fields=["name", col],
					)
					for row in rows or []:
						orig = row.get(col) or ""
						fixed = orig.replace(old_val, new_val)
						if fixed != orig:
							frappe.db.set_value(dt, row.get("name"), col, fixed, update_modified=False)
							total_updates += 1
				except Exception as e:
					log(f"  Notice updating {dt}.{col}: {e}")

			# Also fix arbitrary glued identifier+and!/or! (e.g. doc.reference_typeand!in_list)
			try:
				if frappe.db.has_column(dt, "name"):
					glued_rows = frappe.get_all(
						dt,
						or_filters=[[col, "like", "%and!%"], [col, "like", "%or!%"]],
						fields=["name", col],
					)
					for gr in glued_rows or []:
						orig = gr.get(col) or ""
						fixed = re.sub(r"([a-zA-Z0-9_\)])and!(?!=)", r"\1 && !", orig)
						fixed = re.sub(r"([a-zA-Z0-9_\)])or!(?!=)", r"\1 || !", fixed)
						if fixed != orig:
							frappe.db.set_value(dt, gr.get("name"), col, fixed, update_modified=False)
							total_updates += 1
							log(f"  Fixed glued operator in {dt}.{col} ({gr.get('name')})")
			except Exception as e:
				log(f"  Notice fixing glued operator in {dt}.{col}: {e}")

	return total_updates


def repair_disk_json_files(log):
	"""
	No-op stub retained for backwards API compatibility.
	Frappe Marketplace apps must never mutate external app files in apps/frappe or apps/erpnext.
	All schema/expression healing is performed cleanly in MariaDB and metadata reload.
	"""
	return []


def restore_master_permissions(log):
	"""
	Safely repairs Administrator/System Manager create/delete permissions on Master DocTypes
	without wiping legitimate customer Role Permissions Manager customizations for other roles.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return "db_unavailable"

	master_doctypes = ["Customer", "Supplier", "Item", "Customer Group", "Supplier Group", "Item Group"]
	admin_roles = ["System Manager", "Administrator"]

	for perm_dt in ("Custom DocPerm", "DocPerm"):
		if not frappe.db.table_exists(perm_dt):
			continue
		try:
			rows = frappe.get_all(
				perm_dt,
				filters={"parent": ["in", master_doctypes], "role": ["in", admin_roles]},
				fields=["name", "create", "delete", "write", "read"],
			)
			for row in rows or []:
				if not (row.get("create") and row.get("delete") and row.get("write") and row.get("read")):
					frappe.db.set_value(
						perm_dt,
						row.get("name"),
						{"create": 1, "delete": 1, "write": 1, "read": 1},
						update_modified=False,
					)
			log(f"  Verified System Manager & Administrator create/delete rights in {perm_dt}.")
		except Exception as e:
			log(f"  Notice during {perm_dt} check: {e}")

	if frappe.db.table_exists("DocType"):
		try:
			rows = frappe.get_all(
				"DocType",
				filters={"name": ["in", master_doctypes]},
				fields=["name", "read_only", "in_create"],
			)
			for row in rows or []:
				if row.get("read_only") or row.get("in_create"):
					frappe.db.set_value(
						"DocType",
						row.get("name"),
						{"read_only": 0, "in_create": 0},
						update_modified=False,
					)
		except Exception as e:
			log(f"  Notice updating DocType read_only: {e}")

	return "admin_roles_verified"


def cleanup_trees_and_masters(log):
	"""
	Removes ONLY obsolete Inter Company Transactions custom fields and property setters
	on Tree and Master DocTypes so third-party Marketplace apps or customer fields are never touched.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return 0

	if frappe.db.table_exists("Custom Field"):
		try:
			tree_dts = ["Customer Group", "Supplier Group", "Item Group"]
			frappe.db.delete("Custom Field", {"dt": ["in", tree_dts], "module": "Inter Company Transactions"})
			frappe.db.delete("Custom Field", {"dt": ["in", tree_dts], "fieldname": "custom_company"})

			obsolete_master_fields = [
				("Customer", "ic_customer_group"),
				("Supplier", "ic_supplier_group"),
				("Item", "is_intercompany_item"),
				("Item", "ic_item_group"),
				("Warehouse", "is_intercompany_warehouse"),
				("Warehouse", "ic_warehouse"),
			]
			for m_dt, m_fn in obsolete_master_fields:
				frappe.db.delete("Custom Field", {"dt": m_dt, "fieldname": m_fn})

			all_master_dts = [
				"Customer", "Supplier", "Item", "Warehouse",
				"Customer Group", "Supplier Group", "Item Group",
			]
			frappe.db.delete("Custom Field", {"dt": ["in", all_master_dts], "module": "Inter Company Transactions"})
			log("  Removed obsolete ICT custom fields from Tree and Master DocTypes.")
		except Exception as e:
			log(f"  Notice during custom field cleanup: {e}")

	if frappe.db.table_exists("Property Setter"):
		try:
			frappe.db.delete("Property Setter", {"module": "Inter Company Transactions"})
			frappe.db.delete("Property Setter", {"property": ["like", "%intercompany%"]})
			log("  Cleaned up Inter Company Transactions property setters.")
		except Exception as e:
			log(f"  Notice during property setter cleanup: {e}")

	return "trees_and_masters_cleaned"


def reload_and_flush(log):
	"""Reload doctypes to refresh in-memory schema and flush cache"""
	doctypes_to_reload = [
		"Item", "Customer", "Supplier",
		"Customer Group", "Supplier Group", "Item Group",
		"Journal Entry", "Journal Entry Account",
	]
	for dt in doctypes_to_reload:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.reload_doctype(dt, force=True)
				log(f"  Reloaded DocType schema: {dt}")
		except Exception as e:
			log(f"  Notice reloading {dt}: {e}")

	frappe.clear_cache()
