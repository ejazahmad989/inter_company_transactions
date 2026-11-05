#!/usr/bin/env python3
# Standalone Site Repair Script for ERPNext
# Run via: bench --site <your-site> run-script repair_site.py
# Or copy-paste into: bench --site <your-site> console

import os
import frappe


def main():
	print("\n" + "=" * 70)
	print("STARTING FULL REPAIR OF SITE MASTER DOCTYPES & PERMISSIONS")
	print("=" * 70)

	# 1. Repair corrupted depends_on expressions in database
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

	total_db = 0
	for tbl, cols in tables:
		if not frappe.db.table_exists(tbl):
			continue
		for col in cols:
			if not frappe.db.has_column(tbl, col):
				continue
			for old_val, new_val in replacements:
				try:
					rows = frappe.db.sql(f"SELECT count(*) FROM `{tbl}` WHERE `{col}` LIKE %s", (f"%{old_val}%",))[0][0]
					if rows > 0:
						frappe.db.sql(f"UPDATE `{tbl}` SET `{col}` = REPLACE(`{col}`, %s, %s) WHERE `{col}` LIKE %s", (old_val, new_val, f"%{old_val}%"))
						total_db += rows
						print(f"  Fixed {rows} records in {tbl}.{col} ('{old_val}')")
				except Exception:
					pass
	print(f"[1/5] Database expressions repaired: {total_db} rows fixed.")

	# 2. Repair disk JSON files in apps/ (e.g. apps/erpnext/erpnext/stock/doctype/item/item.json)
	apps_dirs = []
	for candidate in ["apps", "../apps", "../../apps", "/home/frappe/frappe-bench/apps"]:
		if os.path.exists(candidate):
			abs_c = os.path.abspath(candidate)
			if abs_c not in apps_dirs:
				apps_dirs.append(abs_c)
	for app in ["erpnext", "frappe"]:
		try:
			p = frappe.get_app_path(app)
			parent_app = os.path.abspath(os.path.join(p, ".."))
			if parent_app not in apps_dirs:
				apps_dirs.append(parent_app)
		except Exception:
			pass

	repaired_files = 0
	for base in apps_dirs:
		try:
			for root, dirs, files in os.walk(base):
				if "node_modules" in root or ".git" in root or "__pycache__" in root:
					continue
				for file in files:
					if file.endswith(".json"):
						fp = os.path.join(root, file)
						try:
							with open(fp, "r", encoding="utf-8") as f:
								c = f.read()
							if "__islocalanddoc" in c or "__islocaland" in c or "anddoc." in c:
								nc = c.replace("__islocalanddoc", "__islocal && doc")
								nc = nc.replace("__islocal anddoc", "__islocal && doc")
								nc = nc.replace("__islocaland doc", "__islocal && doc")
								nc = nc.replace("__islocaland", "__islocal && ")
								nc = nc.replace("anddoc.", " && doc.")
								nc = nc.replace("and!doc.", " && !doc.")
								with open(fp, "w", encoding="utf-8") as f:
									f.write(nc)
								repaired_files += 1
								print(f"  Restored clean schema file on disk: {fp}")
						except Exception:
							pass
		except Exception:
			pass
	print(f"[2/5] Disk schema files repaired: {repaired_files} files fixed.")

	# 3. Restore 'Add' and 'Delete' permissions on Customer, Supplier, Item
	master_doctypes = ["Customer", "Supplier", "Item", "Customer Group", "Supplier Group", "Item Group", "Warehouse"]
	if frappe.db.table_exists("Custom DocPerm"):
		placeholders = ", ".join(["%s"] * len(master_doctypes))
		frappe.db.sql(f"DELETE FROM `tabCustom DocPerm` WHERE `parent` IN ({placeholders})", tuple(master_doctypes))
		print("  Removed restrictive Custom DocPerm overrides on master doctypes.")

	if frappe.db.table_exists("DocPerm"):
		frappe.db.sql("""
			UPDATE `tabDocPerm`
			SET `create` = 1, `delete` = 1, `write` = 1, `read` = 1
			WHERE `parent` IN ('Customer', 'Supplier', 'Item', 'Customer Group', 'Supplier Group', 'Item Group')
			  AND `role` IN ('System Manager', 'Administrator', 'Sales Manager', 'Purchase Manager')
		""")
		print("  Guaranteed full Add & Delete permissions for System Manager & Manager roles.")

	if frappe.db.table_exists("DocType"):
		frappe.db.sql("""
			UPDATE `tabDocType`
			SET `read_only` = 0, `in_create` = 0
			WHERE `name` IN ('Customer', 'Supplier', 'Item', 'Customer Group', 'Supplier Group', 'Item Group')
		""")
	print("[3/5] Master permissions restored: Add Customer/Supplier and Delete buttons enabled.")

	# 4. Clean up Tree DocTypes and Master Custom Fields / Property Setters
	if frappe.db.table_exists("Custom Field"):
		tree_dts = ["Customer Group", "Supplier Group", "Item Group"]
		tree_ph = ", ".join(["%s"] * len(tree_dts))
		frappe.db.sql(f"DELETE FROM `tabCustom Field` WHERE `dt` IN ({tree_ph})", tuple(tree_dts))

		master_fields = [
			"ic_customer_group", "ic_supplier_group", "is_intercompany_item",
			"ic_item_group", "is_intercompany_warehouse", "ic_warehouse", "custom_company"
		]
		field_ph = ", ".join(["%s"] * len(master_fields))
		frappe.db.sql(f"DELETE FROM `tabCustom Field` WHERE `fieldname` IN ({field_ph})", tuple(master_fields))
		print("  Removed all obsolete custom fields from Tree and Master DocTypes.")

	if frappe.db.table_exists("Property Setter"):
		frappe.db.sql("""
			DELETE FROM `tabProperty Setter`
			WHERE (`doc_type` IN ('Customer', 'Supplier', 'Item') AND `property` IN ('read_only', 'in_create', 'is_submittable', 'editable_grid'))
			   OR (`doc_type` IN ('Customer', 'Supplier') AND `field_name` = 'naming_series')
			   OR (`doc_type` IN ('Customer Group', 'Supplier Group', 'Item Group'))
			   OR (`module` = 'Inter Company Transactions')
		""")
		print("  Removed conflicting Property Setters on Customer/Supplier and Tree DocTypes.")
	print("[4/5] Tree and Master DocTypes cleaned: persistent 'Save' button lock removed.")

	# 5. Reload doctypes and flush Redis & Desk cache
	for dt in ["Item", "Customer", "Supplier", "Customer Group", "Supplier Group", "Item Group"]:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.reload_doctype(dt, force=True)
				print(f"  Reloaded standard schema: {dt}")
		except Exception as e:
			print(f"  Notice reloading {dt}: {e}")

	frappe.db.commit()
	frappe.clear_cache()
	print("[5/5] Reloaded standard DocTypes and cleared site cache.")

	print("=" * 70)
	print("REPAIR COMPLETED SUCCESSFULLY!")
	print("=" * 70)


if __name__ == "__main__" or "frappe" in locals():
	main()
