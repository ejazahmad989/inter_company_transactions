# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ICTNotificationSetting(Document):
	def validate(self):
		if not self.user:
			self.user = frappe.session.user
		if not self.name or self.name != self.user:
			self.name = self.user


def get_ict_notification_settings(user=None):
	"""
	Returns ICTNotificationSetting document for given user or creates one with defaults.
	Safe fallback if user is None or Guest.
	"""
	if not user:
		user = frappe.session.user

	if not user or user in ("Guest", "None"):
		return None

	if not frappe.db.table_exists("ICT Notification Setting"):
		return None

	try:
		if frappe.db.exists("ICT Notification Setting", user):
			return frappe.get_doc("ICT Notification Setting", user)

		# Auto create default settings
		doc = frappe.new_doc("ICT Notification Setting")
		doc.name = user
		doc.user = user
		doc.enabled = 1
		doc.email_notifications = 1
		doc.in_app_notifications = 1
		doc.approval_requests = 1
		doc.status_updates = 1
		doc.dispute_alerts = 1
		doc.netting_cycle_alerts = 1
		doc.elimination_alerts = 1
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc
	except Exception as e:
		frappe.logger("inter_company_transactions").debug(f"Error getting ICT Notification Setting: {e}")
		return None
