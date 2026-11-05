# Copyright (c) 2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""
	Patch v1.5:
	1. Repairs corrupted 'depends_on' expressions across:
	   - MariaDB tables (tabDocField, tabCustom Field, tabProperty Setter, etc.)
	   - JSON schema files on disk in apps/ (e.g. apps/erpnext/erpnext/stock/doctype/item/item.json)
	2. Restores 'Create' and 'Delete' buttons on Customer, Supplier, and Item:
	   - Wipes restrictive Custom DocPerms so standard ERPNext role permissions take effect.
	   - Guarantees System Manager, Sales Manager, and Purchase Manager have full create & delete rights.
	3. Fixes Tree View dirty 'Save' button locks on Customer Group, Supplier Group, and Item Group:
	   - Purges all custom fields and intrusive property setters on Tree DocTypes.
	   - Purges obsolete custom fields from Customer, Supplier, Item, and Warehouse.
	4. Force-reloads standard DocTypes to flush metadata cache.
	5. Commits to database and clears Redis / Desk cache.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return

	try:
		from inter_company_transactions.diagnose_and_heal import run_full_healing
		run_full_healing(verbose=True)
	except Exception as e:
		print(f"Notice running full healing in patch v1.5: {e}")
