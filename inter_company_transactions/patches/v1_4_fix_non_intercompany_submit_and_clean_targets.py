import frappe


def execute():
	"""
	1. Updates all 'intercompany_target_company' Custom Fields to set fetch_if_empty = 0.
	2. Cleans up any draft transactions (docstatus = 0) where intercompany_target_company was mistakenly
	   set to the document's own company or set on a non-intercompany transaction (is_intercompany = 0),
	   allowing standard transactions to transition cleanly to the 'Submit' state.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return

	# 1. Reset fetch_if_empty = 0 on all intercompany_target_company Custom Fields
	try:
		if frappe.db.table_exists("Custom Field") and frappe.db.has_column("Custom Field", "fetch_if_empty"):
			frappe.db.sql("""
				UPDATE `tabCustom Field`
				SET `fetch_if_empty` = 0
				WHERE `fieldname` = 'intercompany_target_company'
			""")
			frappe.db.commit()
	except Exception as e:
		frappe.logger().warning(f"[ICT Patch v1.4] Warning updating fetch_if_empty on Custom Field: {e}")

	# 2. Clean up draft transactions where target company erroneously matches own company
	doctypes = [
		"Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
		"Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation",
		"Material Request", "Stock Entry", "Journal Entry", "Payment Entry",
		"Request for Quotation"
	]

	for dt in doctypes:
		try:
			if frappe.db.table_exists(dt) and frappe.db.has_column(dt, "intercompany_target_company") and frappe.db.has_column(dt, "company"):
				frappe.db.sql(f"""
					UPDATE `tab{dt}`
					SET `intercompany_target_company` = ''
					WHERE `docstatus` = 0
					  AND (`intercompany_target_company` = `company` OR `is_intercompany` = 0)
				""")
		except Exception as e:
			frappe.logger().warning(f"[ICT Patch v1.4] Warning cleaning up {dt}: {e}")

	try:
		if frappe.db.table_exists("Journal Entry Account") and frappe.db.has_column("Journal Entry Account", "intercompany_target_company"):
			frappe.db.sql("""
				UPDATE `tabJournal Entry Account` j_acc
				JOIN `tabJournal Entry` j ON j.name = j_acc.parent
				SET j_acc.`intercompany_target_company` = ''
				WHERE j.`docstatus` = 0
				  AND (j_acc.`intercompany_target_company` = j.`company` OR j.`is_intercompany` = 0)
			""")
	except Exception as e:
		frappe.logger().warning(f"[ICT Patch v1.4] Warning cleaning up Journal Entry Account: {e}")

	frappe.db.commit()
	try:
		frappe.clear_cache()
	except Exception:
		pass
