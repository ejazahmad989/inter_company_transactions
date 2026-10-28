# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.core.page.permission_manager.permission_manager import get_permissions
from frappe.model.document import Document


class RoleReplication(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		existing_role: DF.Link | None
		new_role: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if not self.existing_role:
			frappe.throw(_("Please select an Existing Role to replicate from."))
		if not self.new_role:
			frappe.throw(_("Please specify a New Role name."))

	def after_insert(self):
		self.replicate_role()

	def on_update(self):
		self.replicate_role()

	@frappe.whitelist()
	def replicate_role(self):
		frappe.only_for("System Manager")

		if not self.existing_role or not self.new_role:
			return

		new_role_name = self.new_role.strip()
		# 1. Ensure the Role document exists in the Role list
		if not frappe.db.exists("Role", new_role_name):
			role_doc = frappe.get_doc({
				"doctype": "Role",
				"role_name": new_role_name,
				"desk_access": 1
			})
			role_doc.insert(ignore_permissions=True)
			new_role = role_doc.name
		else:
			new_role = new_role_name

		# 2. Handle 'Administrator' alias to 'System Manager' if needed
		source_role = self.existing_role
		if source_role == "Administrator" and not frappe.db.exists("DocPerm", {"role": source_role}):
			source_role = "System Manager"

		# 3. Copy permissions from source role to new role
		perms = get_permissions(role=source_role)
		for perm in perms:
			parent_doctype = perm.get("parent")
			if not parent_doctype or not frappe.db.exists("DocType", parent_doctype):
				continue

			perm_level = perm.get("permlevel", 0)
			existing_cdp = frappe.db.exists(
				"Custom DocPerm",
				{
					"parent": parent_doctype,
					"role": new_role,
					"permlevel": perm_level
				}
			)
			if existing_cdp:
				continue

			perm_dict = dict(perm)
			for k in ["name", "creation", "modified", "modified_by", "owner", "linked_doctypes"]:
				perm_dict.pop(k, None)

			perm_dict["role"] = new_role
			perm_dict["doctype"] = "Custom DocPerm"

			try:
				cdp = frappe.get_doc(perm_dict)
				cdp.insert(ignore_permissions=True)
			except Exception as e:
				frappe.logger().error(f"Error replicating perm for {parent_doctype} to {new_role}: {e!s}")

		frappe.clear_cache()
		frappe.msgprint(_("Role '{0}' replicated from '{1}' successfully.").format(new_role, source_role))
