# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class InterCompanyErrorLog(Document):
	@frappe.whitelist()
	def retry_sync(self):
		"""
		Retry synchronization for the failed source document.
		Handles both local document creation and remote federated REST push.
		"""
		if not frappe.db.exists(self.source_doctype, self.source_name):
			frappe.throw(_("Source document {0} {1} no longer exists.").format(self.source_doctype, self.source_name))

		source_doc = frappe.get_doc(self.source_doctype, self.source_name)

		# Check if target company belongs to a remote federated site
		from inter_company_transactions.sync import get_remote_site_for_company, push_document_to_remote_site
		remote_site = get_remote_site_for_company(self.target_company)

		try:
			if remote_site:
				res = push_document_to_remote_site(source_doc, self.target_company, remote_site)
				if not res.get("success"):
					raise Exception(res.get("error") or _("Remote push failed"))
			else:
				from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
					create_linked_documents,
				)
				create_linked_documents(source_doc)

			self.status = "Retried Successfully"
			self.resolved_by = frappe.session.user if (hasattr(frappe, "session") and frappe.session) else "Administrator"
			self.resolved_at = now_datetime()
			self.save(ignore_permissions=True)
			if hasattr(frappe, "msgprint"):
				frappe.msgprint(
					_("Successfully retried synchronization for {0} {1}").format(self.source_doctype, self.source_name),
					indicator="green",
					title=_("Retry Success"),
				)
		except Exception as e:
			self.status = "Failed"
			self.error_message = str(e)
			self.traceback = frappe.get_traceback()
			self.save(ignore_permissions=True)
			if hasattr(frappe, "throw"):
				frappe.throw(_("Retry failed: {0}").format(str(e)))


@frappe.whitelist()
def auto_retry_pending_errors():
	"""
	Scheduled task to retry pending/failed inter-company sync errors automatically.
	"""
	if not (hasattr(frappe, "db") and frappe.db):
		return
	if not frappe.db.table_exists("Inter Company Error Log"):
		return

	try:
		# Check if auto retry is enabled in settings if available
		settings = {}
		if frappe.db.exists("DocType", "Inter Company Settings"):
			settings = frappe.get_cached_doc("Inter Company Settings", "Inter Company Settings").as_dict()

		if settings and not settings.get("enabled", 1):
			return

		pending_errors = frappe.get_all(
			"Inter Company Error Log",
			filters={"status": ["in", ["Pending", "Failed", "Queued", "Pending Retry"]]},
			fields=["name"],
			limit=20
		)

		for entry in pending_errors:
			try:
				log_doc = frappe.get_doc("Inter Company Error Log", entry.name)
				log_doc.retry_sync()
			except Exception:
				# Error is updated within retry_sync
				pass
	except Exception as e:
		frappe.log_error(f"Error in auto_retry_pending_errors: {str(e)}", "Inter Company Error Log")
