# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from inter_company_transactions.install import create_custom_fields, set_default_permissions

def execute():
	"""
	Post model sync migration patch for v1.1+:
	- Ensures custom fields on all supported doctypes (including Quotation, Supplier Quotation, Material Request)
	- Ensures Inter Company Settings single doctype is initialized with default values
	- Sets permissions for new DocTypes
	"""
	print("Executing patch: v1_1_update_custom_fields...")

	# 1. Ensure custom fields exist
	try:
		create_custom_fields()
		print("Successfully updated custom fields from custom_fields.json")
	except Exception as e:
		print(f"Notice: Custom field creation during patch: {e}")

	# 2. Ensure Inter Company Settings is initialized
	try:
		if frappe.db.exists("DocType", "Inter Company Settings"):
			settings = frappe.get_single("Inter Company Settings")
			if not settings.execution_mode:
				settings.execution_mode = "Synchronous"
			if settings.enabled is None:
				settings.enabled = 1
			if settings.auto_create_missing_items is None:
				settings.auto_create_missing_items = 1
			if not settings.tax_handling_strategy:
				settings.tax_handling_strategy = "Mirror Net Rate Exactly"
			if not settings.default_transfer_pricing_rule:
				settings.default_transfer_pricing_rule = "Source Document Rate"
			if settings.tolerance_amount is None:
				settings.tolerance_amount = 0.05
			if settings.notify_on_sync_failure is None:
				settings.notify_on_sync_failure = 1
			settings.save(ignore_permissions=True)
			print("Initialized Inter Company Settings default values")
	except Exception as e:
		print(f"Notice: Settings initialization during patch: {e}")

	# 3. Ensure permissions on new DocTypes
	try:
		set_default_permissions()
		print("Successfully refreshed default DocType permissions")
	except Exception as e:
		print(f"Notice: Permissions update during patch: {e}")

	frappe.db.commit()
	print("Patch v1_1_update_custom_fields executed successfully.")
