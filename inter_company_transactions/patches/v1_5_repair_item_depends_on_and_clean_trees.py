# Copyright (c) 2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""
	Patch v1.5:
	1. Repairs corrupted 'depends_on' expressions across tabDocField, tabCustom Field,
	   and tabProperty Setter (specifically fixing '__islocalanddoc' -> '__islocal && doc'
	   which was crashing the Desk UI on standard ERPNext Item, Customer, and Supplier forms).
	2. Removes intrusive custom fields from Tree DocTypes (Customer Group, Supplier Group,
	   Item Group) and Master DocTypes (Customer, Supplier, Item, Warehouse) so forms
	   never get stuck in a dirty unsaved state.
	3. Removes intrusive Property Setters that hid or altered standard naming_series on Customer / Supplier.
	4. Reloads affected doctypes and clears cache so forms immediately restore their Delete, Add, and Tree actions.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return

	print("Running patch v1.5: Repairing depends_on expressions, cleaning tree doctypes and master records...")

	# 1. Permanently repair corrupted depends_on expressions in MariaDB
	tables = ["tabDocField", "tabCustom Field", "tabProperty Setter"]
	for tbl in tables:
		if not frappe.db.table_exists(tbl):
			continue

		cols = ["value"] if tbl == "tabProperty Setter" else ["depends_on", "mandatory_depends_on", "read_only_depends_on"]
		for col in cols:
			if not frappe.db.has_column(tbl, col):
				continue

			try:
				# Fix __islocalanddoc -> __islocal && doc
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, '__islocalanddoc', '__islocal && doc')
					WHERE `{col}` LIKE '%__islocalanddoc%'
				""")
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, '__islocal anddoc', '__islocal && doc')
					WHERE `{col}` LIKE '%__islocal anddoc%'
				""")
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, '__islocaland doc', '__islocal && doc')
					WHERE `{col}` LIKE '%__islocaland doc%'
				""")

				# Fix __islocaland -> __islocal &&
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, '__islocaland', '__islocal && ')
					WHERE `{col}` LIKE '%__islocaland%'
				""")

				# Fix anddoc. -> && doc.
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, 'anddoc.', ' && doc.')
					WHERE `{col}` LIKE '%anddoc.%'
				""")
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, 'and!doc.', ' && !doc.')
					WHERE `{col}` LIKE '%and!doc.%'
				""")
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(`{col}`, 'and !doc.', ' && !doc.')
					WHERE `{col}` LIKE '%and !doc.%'
				""")


				# Fix glued operators
				frappe.db.sql(f"""
					UPDATE `{tbl}`
					SET `{col}` = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(`{col}`,
						'1or(', '1 || ('),
						'0or(', '0 || ('),
						')or(', ') || ('),
						'1and(', '1 && ('),
						'0and(', '0 && (')
					WHERE `{col}` IS NOT NULL AND (
						`{col}` LIKE '%1or(%' OR
						`{col}` LIKE '%0or(%' OR
						`{col}` LIKE '%)or(%' OR
						`{col}` LIKE '%1and(%' OR
						`{col}` LIKE '%0and(%'
					)
				""")
			except Exception as e:
				frappe.logger().warning(f"[ICT Patch v1.5] Warning repairing {tbl}.{col}: {e}")

	# 2. Delete intrusive custom fields from Master and Tree DocTypes
	if frappe.db.table_exists("Custom Field"):
		try:
			# Remove tree custom fields
			frappe.db.sql("""
				DELETE FROM `tabCustom Field`
				WHERE `dt` IN ('Customer Group', 'Supplier Group', 'Item Group')
				  AND `fieldname` = 'custom_company'
			""")

			# Remove unused master custom fields that cause dirty locks or form errors
			obsolete_master_fields = [
				('Customer', 'ic_customer_group'),
				('Supplier', 'ic_supplier_group'),
				('Item', 'is_intercompany_item'),
				('Item', 'ic_item_group'),
				('Warehouse', 'is_intercompany_warehouse'),
				('Warehouse', 'ic_warehouse'),
			]
			for dt, fn in obsolete_master_fields:
				frappe.db.sql("""
					DELETE FROM `tabCustom Field`
					WHERE `dt` = %s AND `fieldname` = %s
				""", (dt, fn))

			print("Deleted obsolete master and tree custom fields.")
		except Exception as e:
			frappe.logger().warning(f"[ICT Patch v1.5] Warning cleaning custom fields: {e}")

	# 3. Clean up intrusive Property Setters affecting Customer and Supplier naming_series
	if frappe.db.table_exists("Property Setter"):
		try:
			frappe.db.sql("""
				DELETE FROM `tabProperty Setter`
				WHERE `doc_type` IN ('Customer', 'Supplier')
				  AND `field_name` = 'naming_series'
			""")
			print("Cleaned up Customer/Supplier naming_series property setters.")
		except Exception as e:
			frappe.logger().warning(f"[ICT Patch v1.5] Warning cleaning property setters: {e}")

	# 4. Reload standard DocTypes to flush metadata cache
	for dt in ["Item", "Customer", "Supplier", "Customer Group", "Supplier Group", "Item Group"]:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.reload_doctype(dt, force=True)
		except Exception as e:
			frappe.logger().warning(f"[ICT Patch v1.5] Warning reloading {dt}: {e}")

	# 5. Commit and clear cache
	frappe.db.commit()
	frappe.clear_cache()
	print("Patch v1.5 completed successfully.")
