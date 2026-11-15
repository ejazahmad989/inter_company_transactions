# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import frappe


def ensure_transit_warehouse_type():
	"""Ensure ERPNext's standard 'Transit' Warehouse Type exists before Company creation in tests."""
	try:
		if frappe.db.exists("DocType", "Warehouse Type") and not frappe.db.exists("Warehouse Type", "Transit"):
			doc = frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"})
			doc.flags.ignore_permissions = True
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
	except Exception:
		pass


def before_tests():
	"""Prepare ERPNext base fixtures (such as Warehouse Type: Transit) across v15 and v16 before running tests."""
	ensure_transit_warehouse_type()

	# ERPNext v15 provides erpnext.setup.utils.before_tests
	try:
		from erpnext.setup.utils import before_tests as erpnext_before_tests

		erpnext_before_tests()
		ensure_transit_warehouse_type()
		frappe.db.commit()
		return
	except ImportError:
		pass

	# ERPNext v16 uses BootStrapTestData.make_presets()
	try:
		from erpnext.tests.utils import BootStrapTestData

		bootstrap = BootStrapTestData.__new__(BootStrapTestData)
		bootstrap.make_presets()
		ensure_transit_warehouse_type()
		frappe.db.commit()
		return
	except Exception:
		pass

	ensure_transit_warehouse_type()
	if frappe.db:
		frappe.db.commit()