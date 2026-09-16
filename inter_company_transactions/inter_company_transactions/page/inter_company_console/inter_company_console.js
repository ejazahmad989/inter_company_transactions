// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.pages['inter-company-console'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Inter-Company Control Console'),
		single_column: true
	});

	page.set_primary_action(
		__('Quick Setup Wizard'),
		function() {
			open_quick_setup_wizard(page);
		},
		'octicon octicon-zap'
	);

	page.add_inner_button(__('Health Audit'), function() {
		run_health_audit();
	});

	page.add_inner_button(__('Netting Settlement'), function() {
		frappe.new_doc('Inter Company Netting Cycle');
	});

	page.add_inner_button(__('Elimination Run'), function() {
		frappe.new_doc('Inter Company Elimination Run');
	});

	page.add_inner_button(__('Reconciliation Matrix'), function() {
		frappe.set_route('query-report', 'Inter Company Transaction Matrix');
	});

	page.add_inner_button(__('Settings'), function() {
		frappe.set_route('Form', 'Inter Company Settings');
	});

	wrapper.page = page;
	render_console(wrapper);
};

frappe.pages['inter-company-console'].refresh = function(wrapper) {
	render_console(wrapper);
};

function render_console(wrapper) {
	let $container = $(wrapper).find('.layout-main-section');
	$container.empty();

	$container.html(`
		<div class="ict-console-wrapper">
			<div class="ict-loading text-center p-5 text-muted">
				<i class="fa fa-spinner fa-spin fa-2x"></i>
				<p class="mt-2">${__('Loading Inter-Company telemetry...')}</p>
			</div>
		</div>
	`);

	frappe.call({
		method: 'inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.get_console_dashboard_data',
		callback: function(r) {
			if (r.message) {
				build_console_ui($container, r.message);
			}
		}
	});
}

function build_console_ui($container, data) {
	let m = data.metrics;
	let healthColor = data.health_status === 'Healthy' ? '#28a745' : '#e06666';

	let html = `
		<div class="ict-console-body" style="padding: 10px 0;">
			<!-- Top KPI Summary Cards -->
			<div class="row ict-stats-row mb-4">
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #5e64ff !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Active Company Links')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: #5e64ff;">${m.active_links}</h2>
							<span class="badge badge-pill badge-primary" style="font-size: 12px;">${m.companies_count} ${__('Entities')}</span>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #28a745 !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Mirrored Documents')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: #28a745;">${m.synced_docs_count}</h2>
							<a href="/app/inter-company-document-reference" class="btn btn-xs btn-default">${__('View All')}</a>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #17a2b8 !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Netting Settled')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h3 class="mb-0 font-weight-bold" style="color: #17a2b8;">${format_currency(m.total_settled_amount)}</h3>
							<span class="badge badge-pill badge-info" style="font-size: 12px;">${m.elimination_runs} ${__('Elim. Runs')}</span>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid ${m.open_disputes > 0 ? '#dc3545' : '#6c757d'} !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Open Disputes')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: ${m.open_disputes > 0 ? '#dc3545' : '#6c757d'};">${m.open_disputes}</h2>
							<a href="/app/inter-company-dispute" class="btn btn-xs btn-default">${__('Disputes')}</a>
						</div>
					</div>
				</div>
			</div>

			<!-- Topology & Multi-Company Links Section -->
			<div class="card p-4 shadow-sm border-0 mb-4" style="border-radius: 8px; background: var(--card-bg, #fff);">
				<div class="d-flex justify-content-between align-items-center mb-3">
					<div>
						<h5 class="mb-1 font-weight-bold"><i class="fa fa-sitemap mr-2 text-primary"></i>${__('Intercompany Topology & Active Channels')}</h5>
						<p class="text-muted mb-0" style="font-size: 13px;">${__('Configured multi-entity synchronization pipelines and party relationships')}</p>
					</div>
					<button class="btn btn-sm btn-primary btn-quick-wizard"><i class="fa fa-plus mr-1"></i>${__('Connect Companies')}</button>
				</div>
				<div class="ict-links-grid row">
					${render_links_cards(data.links)}
				</div>
			</div>

			<!-- Live Activity Stream -->
			<div class="card p-4 shadow-sm border-0" style="border-radius: 8px; background: var(--card-bg, #fff);">
				<div class="d-flex justify-content-between align-items-center mb-3">
					<div>
						<h5 class="mb-1 font-weight-bold"><i class="fa fa-exchange mr-2 text-success"></i>${__('Live Mirroring Stream')}</h5>
						<p class="text-muted mb-0" style="font-size: 13px;">${__('Real-time audit trail of mirrored transactions across sister companies')}</p>
					</div>
					<a href="/app/query-report/Inter Company Transaction Matrix" class="btn btn-sm btn-default"><i class="fa fa-table mr-1"></i>${__('Full Audit Matrix')}</a>
				</div>
				<div class="table-responsive">
					<table class="table table-hover table-striped mb-0" style="font-size: 13px;">
						<thead>
							<tr class="text-muted">
								<th>${__('Source Company')}</th>
								<th>${__('Source Document')}</th>
								<th></th>
								<th>${__('Target Company')}</th>
								<th>${__('Target Document')}</th>
								<th>${__('Status')}</th>
								<th>${__('Timestamp')}</th>
							</tr>
						</thead>
						<tbody>
							${render_recent_tx(data.recent_transactions)}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	`;

	$container.html(html);

	$container.find('.btn-quick-wizard').on('click', function() {
		open_quick_setup_wizard();
	});
}

function render_links_cards(links) {
	if (!links || links.length === 0) {
		return `
			<div class="col-12 text-center p-4 text-muted">
				<i class="fa fa-link fa-2x mb-2" style="opacity: 0.5;"></i>
				<p class="mb-2">${__('No Intercompany Transaction Links configured yet.')}</p>
				<button class="btn btn-sm btn-primary btn-quick-wizard">${__('Launch Quick Setup Wizard')}</button>
			</div>
		`;
	}

	return links.map(l => {
		let counterpartiesHtml = l.counterparties.map(cp => `<span class="badge badge-light border mr-1 mb-1 p-1">${cp}</span>`).join('');
		return `
			<div class="col-md-6 col-lg-4 mb-3">
				<div class="card h-100 p-3 border" style="border-radius: 8px; border-color: var(--border-color, #e2e8f0) !important;">
					<div class="d-flex justify-content-between align-items-center mb-2">
						<span class="badge ${l.enabled ? 'badge-success' : 'badge-secondary'}">${l.enabled ? __('Active') : __('Disabled')}</span>
						<a href="/app/intercompany-transaction-link/${l.name}" class="btn btn-xs btn-default">${__('Edit')}</a>
					</div>
					<h6 class="font-weight-bold mb-1"><i class="fa fa-building-o mr-1 text-muted"></i>${l.main_company}</h6>
					<div class="my-2">
						<small class="text-muted d-block mb-1">${__('Connected Entities:')}</small>
						<div>${counterpartiesHtml || '<span class="text-muted" style="font-size: 11px;">None configured</span>'}</div>
					</div>
					<div class="mt-auto pt-2 border-top d-flex justify-content-between align-items-center" style="font-size: 12px;">
						<span class="text-muted">${l.active_types_count} ${__('Transaction Rules')}</span>
						<a href="/app/inter-company-document-reference?source_company=${encodeURIComponent(l.main_company)}" class="text-primary">${__('Audit Logs')} &rarr;</a>
					</div>
				</div>
			</div>
		`;
	}).join('');
}

function render_recent_tx(txList) {
	if (!txList || txList.length === 0) {
		return `<tr><td colspan="7" class="text-center text-muted p-4">${__('No intercompany transactions logged yet.')}</td></tr>`;
	}

	return txList.map(tx => {
		let isMirrored = !!tx.target_name;
		let badgeClass = isMirrored ? 'indicator-pill green' : 'indicator-pill orange';
		let statusText = isMirrored ? __('Synchronized') : __('Pending');

		return `
			<tr>
				<td><b>${tx.source_company}</b></td>
				<td><a href="/app/${frappe.router.slug(tx.source_doctype)}/${tx.source_name}">${tx.source_doctype}: ${tx.source_name}</a></td>
				<td class="text-center text-muted">&rarr;</td>
				<td><b>${tx.target_company}</b></td>
				<td>
					${isMirrored 
						? `<a href="/app/${frappe.router.slug(tx.target_doctype)}/${tx.target_name}">${tx.target_doctype}: ${tx.target_name}</a>`
						: `<span class="text-muted font-italic">${__('Pending creation')}</span>`
					}
				</td>
				<td><span class="${badgeClass}">${statusText}</span></td>
				<td class="text-muted" style="font-size: 11px;">${frappe.datetime.prettyDate(tx.creation)}</td>
			</tr>
		`;
	}).join('');
}

function open_quick_setup_wizard() {
	let d = new frappe.ui.Dialog({
		title: __('Inter-Company Quick Setup Wizard'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'wizard_intro',
				options: `
					<div class="alert alert-info" style="font-size: 12px; margin-bottom: 15px;">
						<i class="fa fa-info-circle mr-1"></i>
						${__('Select two sister entities. The wizard will automatically configure reciprocal internal parties (Customer & Supplier) and activate standard bidirectional transaction mirroring.')}
					</div>
				`
			},
			{
				label: __('Main Company (Entity A)'),
				fieldname: 'main_company',
				fieldtype: 'Link',
				options: 'Company',
				reqd: 1
			},
			{
				label: __('Counterparty Company (Entity B)'),
				fieldname: 'counterparty_company',
				fieldtype: 'Link',
				options: 'Company',
				reqd: 1
			}
		],
		primary_action_label: __('Establish Connection'),
		primary_action: function(values) {
			if (values.main_company === values.counterparty_company) {
				frappe.msgprint({
					title: __('Validation Error'),
					indicator: 'red',
					message: __('Main Company and Counterparty Company cannot be the same entity.')
				});
				return;
			}

			d.hide();
			frappe.call({
				method: 'inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.quick_setup_intercompany_pair',
				args: {
					main_company: values.main_company,
					counterparty_company: values.counterparty_company
				},
				freeze: true,
				freeze_message: __('Establishing intercompany relationship and transaction rules...'),
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						});
						// Reload page
						if (cur_page && cur_page.page) {
							render_console(cur_page.page.wrapper);
						}
					}
				}
			});
		}
	});

	d.show();
}

function run_health_audit() {
	frappe.call({
		method: 'inter_company_transactions.inter_company_transactions.doctype.inter_company_settings.inter_company_settings.get_enterprise_health_check',
		freeze: true,
		freeze_message: __('Auditing intercompany integrity and ledger configurations...'),
		callback: function(r) {
			if (r.message) {
				show_health_dialog(r.message);
			}
		}
	});
}

function show_health_dialog(h) {
	let recsHtml = h.recommendations.length > 0
		? h.recommendations.map(rc => `<li class="text-warning mb-1">${rc}</li>`).join('')
		: `<li class="text-success"><i class="fa fa-check-circle mr-1"></i>${__('All integrity checks passed with flying colors!')}</li>`;

	let d = new frappe.ui.Dialog({
		title: __('Inter-Company System Health Audit'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'audit_body',
				options: `
					<div class="p-2">
						<div class="d-flex align-items-center justify-content-between p-3 mb-3" style="background: var(--bg-color, #f8f9fa); border-radius: 6px;">
							<div>
								<h6 class="mb-0 font-weight-bold">${__('Overall Integrity Status')}</h6>
								<small class="text-muted">${__('Real-time ledger and topology telemetry')}</small>
							</div>
							<span class="badge ${h.status === 'Healthy' ? 'badge-success' : 'badge-warning'}" style="font-size: 14px; padding: 6px 12px;">${h.status}</span>
						</div>
						<div class="row mb-3 text-center">
							<div class="col-4 border-right">
								<h4 class="mb-0 font-weight-bold text-primary">${h.total_companies}</h4>
								<small class="text-muted">${__('Total Entities')}</small>
							</div>
							<div class="col-4 border-right">
								<h4 class="mb-0 font-weight-bold text-success">${h.active_links}</h4>
								<small class="text-muted">${__('Active Channels')}</small>
							</div>
							<div class="col-4">
								<h4 class="mb-0 font-weight-bold ${h.error_log_count > 0 ? 'text-danger' : 'text-secondary'}">${h.error_log_count}</h4>
								<small class="text-muted">${__('Failed Syncs')}</small>
							</div>
						</div>
						<h6 class="font-weight-bold mt-3">${__('Audit Recommendations & Actions:')}</h6>
						<ul class="pl-3 mb-0" style="font-size: 13px;">
							${recsHtml}
						</ul>
					</div>
				`
			}
		],
		primary_action_label: __('Close'),
		primary_action: function() {
			d.hide();
		}
	});

	d.show();
}
