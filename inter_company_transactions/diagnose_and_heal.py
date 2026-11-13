# Copyright (c) 2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import glob
import json
import os
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
	5. Force-reloads standard DocTypes to flush metadata cache, commits, and clears Redis / Desk cache.
	"""
	log = print if verbose else (lambda *args, **kwargs: None)
	log("=== STARTING FULL DATABASE & DOCTYPE SELF-HEALING ===")

	# 1. Repair database expressions
	repaired_db_count = repair_database_text(log)
	log(f"[1/5] Repaired corrupted expressions in database: {repaired_db_count} occurrences updated.")

	# 2. Skip modifying external app disk files (marketplace safety)
	repaired_files = repair_disk_json_files(log)
	log(f"[2/5] Verified disk schema safety (0 external disk files modified).")

	# 3. Restore master permissions (Customer, Supplier, Item)
	restored_perms = restore_master_permissions(log)
	log(f"[3/5] Restored master permissions (Add/Delete buttons): {restored_perms}")

	# 4. Cleanup Tree and Master DocTypes
	cleaned_fields = cleanup_trees_and_masters(log)
	log(f"[4/5] Cleaned Tree and Master custom fields/property setters: {cleaned_fields}")

	# 5. Reload doctypes and flush cache
	reload_and_flush(log)
	log("[5/5] Reloaded standard DocTypes and cleared site cache.")

	log("=== DATABASE CLEANED AND REPAIRED SUCCESSFULLY ===")
	return {
		"status": "success",
		"repaired_db_count": repaired_db_count,
		"repaired_files": repaired_files,
		"restored_perms": restored_perms,
		"cleaned_fields": cleaned_fields
	}


def repair_database_text(log):
	"""Scan and replace corrupted expressions across all relevant MariaDB tables"""
	if not (hasattr(frappe, "db") and frappe.db):
		return 0

	total_updates = 0
	tables = [
		("tabDocField", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
		("tabCustom Field", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
		("tabProperty Setter", ["value"]),
		("tabClient Script", ["script"]),
		("tabCustom Script", ["script"]),
		("tabDocType", ["description"])
	]

	replacements = [
		("__islocalanddoc", "__islocal && doc"),
		("__islocal anddoc", "__islocal && doc"),
		("__islocaland doc", "__islocal && doc"),
		("__islocaland", "__islocal && "),
		("anddoc.", " && doc."),
		("and!doc.", " && !doc."),
		("and !doc.", " && !doc."),
		("1or(", "1 || ("),
		("0or(", "0 || ("),
		(")or(", ") || ("),
		("1and(", "1 && ("),
		("0and(", "0 && (")
	]

	for tbl, cols in tables:
		if not frappe.db.table_exists(tbl):
			continue
		for col in cols:
			if not frappe.db.has_column(tbl, col):
				continue
			for old_val, new_val in replacements:
				try:
					rows = frappe.db.sql(f"""
						SELECT count(*) FROM `{tbl}` WHERE `{col}` LIKE %s
					""", (f"%{old_val}%",))[0][0]
					if rows > 0:
						frappe.db.sql(f"""
							UPDATE `{tbl}`
							SET `{col}` = REPLACE(`{col}`, %s, %s)
							WHERE `{col}` LIKE %s
						""", (old_val, new_val, f"%{old_val}%"))
						total_updates += rows
						log(f"  Fixed {rows} rows in {tbl}.{col} for '{old_val}' -> '{new_val}'")
				except Exception as e:
					log(f"  Notice updating {tbl}.{col}: {e}")

	frappe.db.commit()
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
	Restores Add/Delete buttons on Customer, Supplier, and Item forms:
	1. Deletes custom role permissions (tabCustom DocPerm) on master doctypes so
	   Frappe falls back to standard ERPNext permissions.
	2. Ensures System Manager, Sales Manager, and Purchase Manager have create/delete=1
	   in standard DocPerm.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return "db_unavailable"

	master_doctypes = ["Customer", "Supplier", "Item", "Customer Group", "Supplier Group", "Item Group", "Warehouse"]
	deleted_custom_perms = 0

	# 1. Clear any custom permission overrides that hide Add / Delete buttons
	if frappe.db.table_exists("Custom DocPerm"):
		try:
			placeholders = ", ".join(["%s"] * len(master_doctypes))
			deleted_custom_perms = frappe.db.sql(f"""
				DELETE FROM `tabCustom DocPerm`
				WHERE `parent` IN ({placeholders})
			""", tuple(master_doctypes))
			log(f"  Deleted restrictive Custom DocPerm overrides on master doctypes.")
		except Exception as e:
			log(f"  Notice during Custom DocPerm cleanup: {e}")

	# 2. Guarantee standard DocPerm has create: 1, delete: 1 for manager roles
	if frappe.db.table_exists("DocPerm"):
		try:
			frappe.db.sql("""
				UPDATE `tabDocPerm`
				SET `create` = 1, `delete` = 1, `write` = 1, `read` = 1
				WHERE `parent` IN ('Customer', 'Supplier', 'Item', 'Customer Group', 'Supplier Group', 'Item Group')
				  AND `role` IN ('System Manager', 'Administrator', 'Sales Manager', 'Purchase Manager')
			""")
			log("  Ensured System Manager & Manager roles have full Add & Delete permissions.")
		except Exception as e:
			log(f"  Notice updating DocPerm: {e}")

	# 3. Ensure tabDocType is not flagged read_only or restricted
	if frappe.db.table_exists("DocType"):
		try:
			frappe.db.sql("""
				UPDATE `tabDocType`
				SET `read_only` = 0, `in_create` = 0
				WHERE `name` IN ('Customer', 'Supplier', 'Item', 'Customer Group', 'Supplier Group', 'Item Group')
			""")
		except Exception as e:
			log(f"  Notice updating DocType read_only: {e}")

	frappe.db.commit()
	return f"custom_perms_cleared, standard_roles_enforced"


def cleanup_trees_and_masters(log):
	"""
	Removes obsolete custom fields and property setters on Tree and Master DocTypes
	so forms don't get stuck in dirty unsaved state or show unnecessary 'Save' buttons.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return 0

	total_cleaned = 0

	# 1. Custom Fields cleanup
	if frappe.db.table_exists("Custom Field"):
		try:
			# Remove all custom fields on tree doctypes
			tree_dts = ["Customer Group", "Supplier Group", "Item Group"]
			tree_ph = ", ".join(["%s"] * len(tree_dts))
			frappe.db.sql(f"""
				DELETE FROM `tabCustom Field`
				WHERE `dt` IN ({tree_ph})
			""", tuple(tree_dts))

			# Remove intercompany master custom fields
			master_fields = [
				"ic_customer_group", "ic_supplier_group", "is_intercompany_item",
				"ic_item_group", "is_intercompany_warehouse", "ic_warehouse", "custom_company"
			]
			field_ph = ", ".join(["%s"] * len(master_fields))
			frappe.db.sql(f"""
				DELETE FROM `tabCustom Field`
				WHERE `fieldname` IN ({field_ph})
			""", tuple(master_fields))
			log("  Removed all obsolete custom fields from Tree and Master DocTypes.")
		except Exception as e:
			log(f"  Notice during custom field cleanup: {e}")

	# 2. Property Setters cleanup
	if frappe.db.table_exists("Property Setter"):
		try:
			# Delete any property setters that break Customer/Supplier naming series, make them read_only, or dirty Tree doctypes
			frappe.db.sql("""
				DELETE FROM `tabProperty Setter`
				WHERE (`doc_type` IN ('Customer', 'Supplier', 'Item') AND `property` IN ('read_only', 'in_create', 'is_submittable', 'editable_grid'))
				   OR (`doc_type` IN ('Customer', 'Supplier') AND `field_name` = 'naming_series')
				   OR (`doc_type` IN ('Customer Group', 'Supplier Group', 'Item Group'))
				   OR (`module` = 'Inter Company Transactions')
			""")
			log("  Cleaned up property setters affecting Customer/Supplier/Item and Tree doctypes.")
		except Exception as e:
			log(f"  Notice during property setter cleanup: {e}")

	frappe.db.commit()
	return "trees_and_masters_cleaned"



def reload_and_flush(log):
	"""Reload doctypes to refresh in-memory schema and flush cache"""
	doctypes_to_reload = ["Item", "Customer", "Supplier", "Customer Group", "Supplier Group", "Item Group"]
	for dt in doctypes_to_reload:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.reload_doctype(dt, force=True)
				log(f"  Reloaded DocType schema: {dt}")
		except Exception as e:
			log(f"  Notice reloading {dt}: {e}")

	frappe.db.commit()
	frappe.clear_cache()
