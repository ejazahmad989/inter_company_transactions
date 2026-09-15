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
		"""
		if not frappe.db.exists(self.source_doctype, self.source_name):
			frappe.throw(_("Source document {0} {1} no longer exists.").format(self.source_doctype, self.source_name))

		source_doc = frappe.get_doc(self.source_doctype, self.source_name)
		from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
			create_linked_documents,
		)

		try:
			create_linked_documents(source_doc)
			self.status = "Retried Successfully"
			self.resolved_by = frappe.session.user
			self.resolved_at = now_datetime()
			self.save(ignore_permissions=True)
			frappe.msgprint(
				_("Successfully retried synchronization for {0} {1}").format(self.source_doctype, self.source_name),
				indicator="green",
				title=_("Retry Success"),
			)
		except Exception as e:
			self.error_message = str(e)
			self.traceback = frappe.get_traceback()
			self.save(ignore_permissions=True)
			frappe.throw(_("Retry failed: {0}").format(str(e)))
