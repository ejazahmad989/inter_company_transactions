# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class InterCompanyRemoteSite(Document):
	@frappe.whitelist()
	def test_connection(self):
		"""
		Executes connection verification and updates sync status.
		"""
		self.check_permission("write")
		from inter_company_transactions.sync import diagnose_remote_site_connectivity
		diag = diagnose_remote_site_connectivity(
			site_url=self.site_url,
			api_key=self.api_key,
			api_secret=self.get_password("api_secret") if hasattr(self, "get_password") else self.api_secret,
			timeout=self.timeout_seconds or 5
		)

		if diag.get("overall_status") in ["Passed", "Warning"]:
			self.sync_status = "Connected"
			self.last_sync_time = now_datetime()
			self.last_error = ""
		else:
			self.sync_status = "Error"
			self.last_error = diag.get("error") or "Connection failed"

		return diag
