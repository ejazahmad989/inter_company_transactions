import frappe


def execute():
	"""
	Sets columns=1 on Journal Entry Account-intercompany_target_company custom field.
	Ensures total grid column width is exactly 10:
	Account (2) + Party Type (1) + Party (2) + Intercompany Target Company (1) + Debit (2) + Credit (2) = 10.
	This prevents the Credit column from being pushed out of the Journal Entry accounts table.
	"""
	cf_name = "Journal Entry Account-intercompany_target_company"
	updated = False
	if frappe.db.exists("Custom Field", cf_name):
		frappe.db.set_value("Custom Field", cf_name, "columns", 1, update_modified=False)
		updated = True
	elif frappe.db.exists("Custom Field", {"dt": "Journal Entry Account", "fieldname": "intercompany_target_company"}):
		frappe.db.set_value(
			"Custom Field",
			{"dt": "Journal Entry Account", "fieldname": "intercompany_target_company"},
			"columns",
			1,
			update_modified=False,
		)
		updated = True

	if updated:
		try:
			frappe.clear_cache(doctype="Journal Entry")
			frappe.clear_cache(doctype="Journal Entry Account")
		except Exception:
			pass
		print("Successfully updated Journal Entry Account intercompany_target_company columns to 1.")
