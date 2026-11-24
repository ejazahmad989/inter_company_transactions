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
				method: 'inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.get_enterprise_health_check',
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

		// Multi-Site Network & Firewall Diagnostic Tool
		frm.add_custom_button(__('Diagnose Network & Firewall'), function() {
			open_network_firewall_diagnostic_dialog(frm);
		}, __('Actions'));

		// Test remote site connection if in federated mode
		if (frm.doc.deployment_mode === 'Federated Cross-Site (REST API)') {
			frm.add_custom_button(__('Test Federation Handshake'), function() {
				if (!frm.doc.remote_sites || frm.doc.remote_sites.length === 0) {
					frappe.msgprint(__('Please add at least one Remote Site in the Federated Remote ERPNext Sites table below.'));
					return;
				}
				let site = frm.doc.remote_sites[0];
				frappe.call({
					method: 'inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.test_remote_site_connection',
					args: {
						site_url: site.site_url,
						api_key: site.api_key,
						api_secret: site.api_secret,
						verify_ssl: site.verify_ssl != null ? site.verify_ssl : 1
					},
					freeze: true,
					freeze_message: __('Testing multi-layer connection to remote ERPNext site...'),
					callback: function(r) {
						if (r.message) {
							render_diagnostic_results_modal(r.message);
						}
					}
				});
			}, __('Actions'));
		}
	}
});

function open_network_firewall_diagnostic_dialog(frm) {
	let site_options = [];
	if (frm.doc.remote_sites && frm.doc.remote_sites.length > 0) {
		site_options = frm.doc.remote_sites.map(s => `${s.company_name} (${s.site_url})`);
	}

	let d = new frappe.ui.Dialog({
		title: __('Remote Multi-Site Network & Firewall Diagnostic'),
		fields: [
			{
				label: __('Pre-configured Remote Site'),
				fieldname: 'preset_site',
				fieldtype: 'Select',
				options: ['-- Custom URL --'].concat(site_options),
				default: site_options.length > 0 ? site_options[0] : '-- Custom URL --',
				change: function() {
					let val = d.get_value('preset_site');
					if (val && val !== '-- Custom URL --' && frm.doc.remote_sites) {
						let matched = frm.doc.remote_sites.find(s => `${s.company_name} (${s.site_url})` === val);
						if (matched) {
							d.set_value('site_url', matched.site_url);
							d.set_value('api_key', matched.api_key);
							d.set_value('api_secret', matched.api_secret);
						}
					}
				}
			},
			{
				label: __('Remote Site URL (e.g. https://erp.sistercompany.com:443)'),
				fieldname: 'site_url',
				fieldtype: 'Data',
				reqd: 1,
				default: (frm.doc.remote_sites && frm.doc.remote_sites[0]) ? frm.doc.remote_sites[0].site_url : ''
			},
			{
				label: __('API Key (Optional for port check, required for auth)'),
				fieldname: 'api_key',
				fieldtype: 'Data',
				default: (frm.doc.remote_sites && frm.doc.remote_sites[0]) ? frm.doc.remote_sites[0].api_key : ''
			},
			{
				label: __('API Secret'),
				fieldname: 'api_secret',
				fieldtype: 'Password',
				default: (frm.doc.remote_sites && frm.doc.remote_sites[0]) ? frm.doc.remote_sites[0].api_secret : ''
			},
			{
				label: __('Socket Timeout (Seconds)'),
				fieldname: 'timeout',
				fieldtype: 'Int',
				default: 5
			}
		],
		primary_action_label: __('Run Diagnostic Test'),
		primary_action: function(values) {
			d.hide();
			frappe.call({
				method: 'inter_company_transactions.sync.diagnose_remote_site_connectivity',
				args: {
					site_url: values.site_url,
					api_key: values.api_key,
					api_secret: values.api_secret,
					timeout: values.timeout || 5
				},
				freeze: true,
				freeze_message: __('Diagnosing remote DNS, port, SSL, firewall, and token authorization...'),
				callback: function(r) {
					if (r.message) {
						render_diagnostic_results_modal(r.message);
					}
				}
			});
		}
	});

	d.show();
}

function render_diagnostic_results_modal(diag) {
	let indicator = diag.overall_status === 'Passed' ? 'green' : (diag.overall_status === 'Warning' ? 'orange' : 'red');

	let stepsHtml = (diag.steps || []).map(s => {
		let badgeClass = s.status === 'Passed' ? 'badge-success' : (s.status === 'Warning' ? 'badge-warning' : (s.status === 'Skipped' ? 'badge-secondary' : 'badge-danger'));
		return `
			<li style="margin-bottom: 8px; list-style: none; padding: 6px 10px; background: #f8fafc; border-radius: 4px; border-left: 4px solid ${s.status === 'Passed' ? '#10b981' : (s.status === 'Warning' ? '#f59e0b' : '#ef4444')};">
				<div style="display: flex; justify-content: space-between; align-items: center;">
					<b>${frappe.utils.escape_html(s.step)}</b>
					<span class="badge ${badgeClass}">${s.status}</span>
				</div>
				<div style="font-size: 12px; color: #475569; margin-top: 3px;">
					${frappe.utils.escape_html(s.details)}
				</div>
			</li>
		`;
	}).join('');

	let firewallHtml = '';
	if (diag.firewall_commands && Object.keys(diag.firewall_commands).length > 0) {
		let fw = diag.firewall_commands;
		firewallHtml = `
			<div style="margin-top: 15px; padding: 12px; background: #f1f5f9; border-radius: 6px; border: 1px solid #cbd5e1;">
				<h5 style="margin-top: 0; margin-bottom: 8px; color: #1e293b;"><b>Firewall & Port Setup Commands (Port ${fw.port}):</b></h5>
				<p style="font-size: 12px; color: #64748b; margin-bottom: 8px;">
					If connectivity timed out or was refused, execute the corresponding command on your destination server terminal:
				</p>
				<p style="font-size: 11px; margin-bottom: 2px;"><b>Ubuntu / Debian (UFW):</b></p>
				<pre style="background: #0f172a; color: #38bdf8; padding: 6px 10px; border-radius: 4px; font-size: 12px; user-select: all;">${fw.ubuntu_ufw}</pre>
				
				<p style="font-size: 11px; margin-bottom: 2px; margin-top: 8px;"><b>CentOS / RHEL / AlmaLinux (Firewalld):</b></p>
				<pre style="background: #0f172a; color: #38bdf8; padding: 6px 10px; border-radius: 4px; font-size: 12px; user-select: all;">${fw.centos_firewalld}</pre>
				
				<p style="font-size: 11px; margin-bottom: 2px; margin-top: 8px;"><b>AWS / Cloud Security Group:</b></p>
				<code style="font-size: 11px; color: #334155;">${fw.aws_security_group}</code>
			</div>
		`;
	}

	let modalHtml = `
		<div style="font-size: 13px;">
			<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
				<span><b>Target URL:</b> <code>${frappe.utils.escape_html(diag.site_url)}</code></span>
				<span><b>Overall Status:</b> <span class="badge ${diag.overall_status === 'Passed' ? 'badge-success' : 'badge-danger'}">${diag.overall_status}</span></span>
			</div>
			${diag.latency_ms ? `<p style="margin-bottom: 10px; color: #059669;"><b>Measured Socket Latency:</b> ${diag.latency_ms} ms</p>` : ''}
			<ul style="padding-left: 0; margin-bottom: 10px;">
				${stepsHtml}
			</ul>
			${firewallHtml}
		</div>
	`;

	frappe.msgprint({
		title: __('Remote Site Network & Port Diagnostics'),
		indicator: indicator,
		message: modalHtml
	});
}
