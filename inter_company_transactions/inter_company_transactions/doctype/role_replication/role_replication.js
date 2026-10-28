// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on("Role Replication", {
	onload(frm) {
		frm.set_query("existing_role", () => {
			return {
				filters: {
					disabled: 0
				},
				order_by: "name asc",
				page_length: 100
			};
		});
	},
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Re-replicate Permissions"), () => {
				frappe.dom.freeze(__("Replicating role permissions..."));
				frm.call("replicate_role").then(() => {
					frappe.dom.unfreeze();
					frappe.msgprint(__("Role replication completed."));
				});
			});
		}
	},
	after_save(frm) {
		frappe.msgprint(__("Role '{0}' created and replicated in Role list.", [frm.doc.new_role]));
	}
});