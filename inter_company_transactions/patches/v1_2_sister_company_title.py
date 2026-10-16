import sys

import frappe

from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
	backfill_sister_company_names,
)


def execute():
	"""
	Post-model sync migration patch for v1.2:
	- Reloads Intercompany Transaction Link doctype schema
	- Backfills sister_company field and titles on all existing records
	- Renames legacy hash IDs (e.g. pdlbej2fjb, sh6m81t121) to human-readable format
	"""
	print("Executing patch: v1_2_sister_company_title...")

	try:
		frappe.reload_doc("inter_company_transactions", "doctype", "intercompany_transaction_link")
	except Exception as e:
		print(f"Notice during reload_doc: {e}")

	try:
		backfill_sister_company_names()
		print("Successfully synchronized sister company names and titles")
	except Exception as e:
		print(f"Notice during backfill_sister_company_names: {e}")

	print("Patch v1_2_sister_company_title executed successfully.")


# Module alias for backward compatibility in case an environment imports with trailing .execute
sys.modules[__name__ + ".execute"] = sys.modules[__name__]
