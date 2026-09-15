// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inter Company Error Log", {
	refresh: function(frm) {
		if (frm.doc.status === "Failed") {
			frm.add_custom_button(__("Retry Sync"), function() {
				frm.call({
					method: "retry_sync",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Retrying Intercompany Document Sync..."),
					callback: function(r) {
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
		}
	}
});
