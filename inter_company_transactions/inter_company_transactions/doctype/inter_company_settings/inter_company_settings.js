// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inter Company Settings', {
	refresh: function(frm) {
		// Quick link to visual control console
		frm.add_custom_button(__('Open Control Console'), function() {
			frappe.set_route('inter-company-console');
		}, __('Actions'));

		// Run Health Check
		frm.add_custom_button(__('Run Health Audit'), function() {
			frappe.call({
				method: 'get_enterprise_health_check',
				doc: frm.doc,
				freeze: true,
				freeze_message: __('Auditing intercompany configuration and health...'),
				callback: function(r) {
					if (r.message) {
						let h = r.message;
						let msg = `
							<div style="font-size: 13px;">
								<p><b>Status:</b> <span class="badge ${h.status === 'Healthy' ? 'badge-success' : 'badge-warning'}">${h.status}</span></p>
								<p><b>Total Companies:</b> ${h.total_companies} | <b>Active Links:</b> ${h.active_links}</p>
								<p><b>Transfer Pricing Policies:</b> ${h.transfer_pricing_policies} | <b>Netting Cycles:</b> ${h.netting_cycles}</p>
								<p><b>Elimination Runs:</b> ${h.elimination_runs} | <b>Open Disputes:</b> ${h.open_disputes}</p>
								<p><b>Failed Errors:</b> ${h.error_log_count}</p>
								${h.recommendations.length > 0 ? `<hr><b>Recommendations:</b><ul>${h.recommendations.map(x => `<li>${x}</li>`).join('')}</ul>` : ''}
							</div>
						`;
						frappe.msgprint({
							title: __('Inter-Company Health Audit'),
							indicator: h.status === 'Healthy' ? 'green' : 'orange',
							message: msg
						});
					}
				}
			});
		}, __('Actions'));

		// Test remote site connection if in federated mode
		if (frm.doc.deployment_mode === 'Federated Cross-Site (REST API)') {
			frm.add_custom_button(__('Test Federation Handshake'), function() {
				if (!frm.doc.remote_sites || frm.doc.remote_sites.length === 0) {
					frappe.msgprint(__('Please add at least one Remote Site in the table below.'));
					return;
				}
				let site = frm.doc.remote_sites[0];
				frappe.call({
					method: 'test_remote_site_connection',
					args: {
						site_url: site.site_url,
						api_key: site.api_key,
						api_secret: site.api_secret
					},
					freeze: true,
					freeze_message: __('Testing REST API connection to remote ERPNext site...'),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.msgprint({
								title: __('Federation Handshake Successful'),
								indicator: 'green',
								message: r.message.message
							});
						} else {
							frappe.msgprint({
								title: __('Federation Handshake Failed'),
								indicator: 'red',
								message: r.message ? r.message.message : __('Unknown error')
							});
						}
					}
				});
			}, __('Actions'));
		}
	}
});
