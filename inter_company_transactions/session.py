import frappe


def ensure_user_ict_notification_settings(user=None):
	"""Ensure that the given user has an ICT Notification Setting document via standard ORM."""
	if not user:
		user = getattr(getattr(frappe, "session", None), "user", None)
	if not user or user in ("Guest", "None"):
		return

	from inter_company_transactions.inter_company_transactions.doctype.ict_notification_setting.ict_notification_setting import (
		get_ict_notification_settings,
	)

	get_ict_notification_settings(user)


def on_session_creation(login_manager):
	"""Initialize ICT notification preferences cleanly upon interactive user login."""
	try:
		if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
			return
		user = getattr(getattr(frappe, "session", None), "user", None)
		if user and user not in ("Guest", "None"):
			ensure_user_ict_notification_settings(user)
	except Exception as e:
		frappe.log_error(
			f"Could not initialize ICT notification settings on login: {e!s}",
			"ICT Session Initialization",
		)
