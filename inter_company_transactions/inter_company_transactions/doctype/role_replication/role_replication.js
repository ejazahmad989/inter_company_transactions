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
		frm.disable_save();
		frm.page.set_primary_action(__("Replicate"), ($btn) => {
			if (!frm.doc.existing_role) {
				frappe.msgprint(__("Please select an Existing Role."));
				return;
			}
			if (!frm.doc.new_role) {
				frappe.msgprint(__("Please enter a New Role name."));
				return;
			}

			$btn.text(__("Replicating..."));
			frappe.run_serially([
				() => frappe.dom.freeze(__("Replicating...")),
				() => frm.call({
					method: "replicate_role",
					doc: frm.doc,
					callback: function(r) {
						if (r && r.message) {
							frappe.show_alert({
								message: __("Role '{0}' created and copied successfully!", [r.message.new_role || frm.doc.new_role]),
								indicator: "green"
							}, 5);
						}
					}
				}),
				() => frappe.dom.unfreeze(),
				() => frappe.msgprint(__("Role replication completed. New role is now available in Role List.")),
				() => $btn.text(__("Replicate")),
			]);
		});
	}
});