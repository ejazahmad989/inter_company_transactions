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

	# 1. Reset fetch_if_empty = 0 and default = 0 / NULL on all ICT Custom Fields
	try:
		if frappe.db.table_exists("Custom Field"):
			if frappe.db.has_column("Custom Field", "fetch_if_empty"):
				frappe.db.sql("""
					UPDATE `tabCustom Field`
					SET `fetch_if_empty` = 0
					WHERE `fieldname` = 'intercompany_target_company'
				""")
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
			frappe.db.commit()
	except Exception as e:
		frappe.logger().warning(f"[ICT Patch v1.4] Warning updating Custom Field defaults: {e}")

	# 2. Clean up draft transactions where target company erroneously matches own company
	doctypes = [
		"Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice",
		"Delivery Note", "Purchase Receipt", "Quotation", "Supplier Quotation",
		"Material Request", "Stock Entry", "Journal Entry", "Payment Entry",
		"Request for Quotation", "Landed Cost Voucher"
	]

	for dt in doctypes:
		try:
			if frappe.db.table_exists(dt) and frappe.db.has_column(dt, "intercompany_target_company") and frappe.db.has_column(dt, "company"):
				draft_docs = frappe.get_all(
					dt,
					filters={"docstatus": 0, "intercompany_target_company": ["is", "set"]},
					fields=["name", "company", "is_intercompany", "intercompany_target_company"],
					ignore_permissions=True,
				)
				for row in draft_docs or []:
					if not row.get("is_intercompany") or row.get("intercompany_target_company") == row.get("company"):
						frappe.db.set_value(dt, row.get("name"), "intercompany_target_company", "", update_modified=False)
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

	# 3. Clean up any erroneously generated draft counterpart documents from non-intercompany transactions
	try:
		if frappe.db.table_exists("Inter Company Document Reference"):
			refs = frappe.get_all(
				"Inter Company Document Reference",
				fields=["name", "source_doctype", "source_name", "target_doctype", "target_name"]
			)
			for ref in refs:
				if ref.source_doctype and ref.source_name and frappe.db.exists(ref.source_doctype, ref.source_name):
					src_is_ic = frappe.db.get_value(ref.source_doctype, ref.source_name, "is_intercompany")
					if not src_is_ic:
						# Source was not an intercompany transaction! Delete draft counterpart if still docstatus=0
						if ref.target_doctype and ref.target_name and frappe.db.exists(ref.target_doctype, ref.target_name):
							target_status = frappe.db.get_value(ref.target_doctype, ref.target_name, "docstatus")
							if target_status == 0:
								try:
									frappe.delete_doc(ref.target_doctype, ref.target_name, force=True, ignore_permissions=True)
								except Exception:
									pass
						try:
							frappe.delete_doc("Inter Company Document Reference", ref.name, force=True, ignore_permissions=True)
						except Exception:
							pass
			frappe.db.commit()
	except Exception as e:
		frappe.logger().warning(f"[ICT Patch v1.4] Warning cleaning up draft document references: {e}")

	frappe.db.commit()
	try:
		frappe.clear_cache()
	except Exception:
		pass
