// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// For license information, please see license.txt

frappe.pages['inter-company-console'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Inter-Company Control Console'),
		single_column: true
	});

	page.set_primary_action(
		__('Guided Setup Wizard'),
		function() {
			open_quick_setup_wizard(page);
		},
		'octicon octicon-zap'
	);

	page.add_inner_button(__('Interactive Tutorial'), function() {
		show_tutorial_dialog();
	}, __('Learn & Guide'));

	page.add_inner_button(__('Download PDF Guide'), function() {
		window.open('/assets/inter_company_transactions/Inter_Company_Transactions_User_Guide.pdf', '_blank');
	}, __('Learn & Guide'));

	page.add_inner_button(__('Health Audit'), function() {
		run_health_audit();
	}, __('Tools'));

	page.add_inner_button(__('Reconciliation Matrix'), function() {
		frappe.set_route('query-report', 'Inter Company Transaction Matrix');
	}, __('Tools'));

	page.add_inner_button(__('Balance Reconciliation'), function() {
		frappe.set_route('query-report', 'Inter Company Balance Reconciliation');
	}, __('Tools'));

	page.add_inner_button(__('Netting Settlement'), function() {
		frappe.new_doc('Inter Company Netting Cycle');
	}, __('Actions'));

	page.add_inner_button(__('Elimination Run'), function() {
		frappe.new_doc('Inter Company Elimination Run');
	}, __('Actions'));

	page.add_inner_button(__('Transfer Pricing'), function() {
		frappe.set_route('List', 'Transfer Pricing Policy');
	}, __('Actions'));

	page.add_inner_button(__('Settings'), function() {
		frappe.set_route('Form', 'Inter Company Settings');
	}, __('Actions'));

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
	let isHealthy = data.health_status === 'Healthy';

	const esc = frappe.utils.escape_html;
	let html = `
		<div class="ict-console-body" style="padding: 10px 0;">
			<!-- Welcome / Quick Action Banner -->
			<div class="card p-4 shadow-sm border-0 mb-4" style="border-radius: 8px; background: linear-gradient(135deg, #1f2937 0%, #111827 100%); color: #fff;">
				<div class="row align-items-center">
					<div class="col-lg-8 mb-3 mb-lg-0">
						<div class="d-flex align-items-center mb-2">
							<span class="badge ${isHealthy ? 'badge-success' : 'badge-warning'} mr-2" style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">
								<i class="fa ${isHealthy ? 'fa-check-circle' : 'fa-exclamation-triangle'} mr-1"></i>${esc(data.health_status || 'System Ready')}
							</span>
							<span class="text-muted" style="color: #9ca3af !important; font-size: 12px;">
								${__('Deployment Mode')}: <strong class="text-light">${esc(data.deployment_mode || '')}</strong>
							</span>
						</div>
						<h4 class="mb-1 font-weight-bold text-white">${__('Inter-Company Orchestration & Automation Hub')}</h4>
						<p class="mb-0" style="color: #d1d5db; font-size: 13.5px; max-width: 720px;">
							${__('Seamlessly mirror orders, shipments, and invoices between sister companies with OECD transfer pricing, multilateral netting, and period-end elimination.')}
						</p>
					</div>
					<div class="col-lg-4 text-lg-right">
						<button class="btn btn-primary btn-sm btn-quick-wizard mr-2 font-weight-bold shadow-sm" style="padding: 8px 16px;">
							<i class="fa fa-magic mr-1"></i>${__('Launch Setup Wizard')}
						</button>
						<button class="btn btn-outline-light btn-sm btn-open-tutorial font-weight-bold" style="padding: 8px 14px; border-color: #4b5563; color: #e5e7eb;">
							<i class="fa fa-book mr-1"></i>${__('Interactive Tutorial')}
						</button>
					</div>
				</div>
			</div>

			<!-- Top KPI Summary Cards -->
			<div class="row ict-stats-row mb-4">
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #1b68ff !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Active Company Links')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: #1b68ff;">${m.active_links}</h2>
							<span class="badge badge-pill badge-primary" style="font-size: 12px;">${m.companies_count} ${__('Entities')}</span>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #16a34a !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Mirrored Documents')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: #16a34a;">${m.synced_docs_count}</h2>
							<a href="/app/inter-company-document-reference" class="btn btn-xs btn-default">${__('View All')}</a>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid #0284c7 !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Netting Settled')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h3 class="mb-0 font-weight-bold" style="color: #0284c7;">${format_currency(m.total_settled_amount)}</h3>
							<span class="badge badge-pill badge-info" style="font-size: 12px;">${m.elimination_runs} ${__('Elim. Runs')}</span>
						</div>
					</div>
				</div>
				<div class="col-md-3 col-sm-6 mb-3">
					<div class="card p-3 shadow-sm border-0 ict-kpi-card" style="border-radius: 8px; border-left: 4px solid ${m.open_disputes > 0 ? '#dc2626' : '#6b7280'} !important; background: var(--card-bg, #fff);">
						<div class="text-muted text-uppercase font-weight-bold" style="font-size: 11px; letter-spacing: 0.5px;">${__('Open Disputes')}</div>
						<div class="d-flex align-items-center justify-content-between mt-2">
							<h2 class="mb-0 font-weight-bold" style="color: ${m.open_disputes > 0 ? '#dc2626' : '#6b7280'};">${m.open_disputes}</h2>
							<a href="/app/inter-company-dispute" class="btn btn-xs btn-default">${__('Disputes')}</a>
						</div>
					</div>
				</div>
			</div>

			<!-- Quick Function Hub / Navigation Tiles -->
			<div class="row mb-4">
				<div class="col-6 col-md-3 mb-3">
					<a href="/app/intercompany-transaction-link" class="ict-action-tile">
						<div class="tile-icon text-primary"><i class="fa fa-sitemap"></i></div>
						<div class="font-weight-bold">${__('Company Links')}</div>
						<small class="text-muted d-block mt-1">${__('Entity topology & transaction routes')}</small>
					</a>
				</div>
				<div class="col-6 col-md-3 mb-3">
					<a href="/app/transfer-pricing-policy" class="ict-action-tile">
						<div class="tile-icon text-success"><i class="fa fa-tags"></i></div>
						<div class="font-weight-bold">${__('Transfer Pricing')}</div>
						<small class="text-muted d-block mt-1">${__('OECD Cost-plus & resale margins')}</small>
					</a>
				</div>
				<div class="col-6 col-md-3 mb-3">
					<a href="/app/inter-company-netting-cycle" class="ict-action-tile">
						<div class="tile-icon text-info"><i class="fa fa-balance-scale"></i></div>
						<div class="font-weight-bold">${__('Netting Cycles')}</div>
						<small class="text-muted d-block mt-1">${__('Multilateral cross-debt settlement')}</small>
					</a>
				</div>
				<div class="col-6 col-md-3 mb-3">
					<a href="/app/inter-company-elimination-run" class="ict-action-tile">
						<div class="tile-icon text-warning"><i class="fa fa-compress"></i></div>
						<div class="font-weight-bold">${__('Elimination Runs')}</div>
						<small class="text-muted d-block mt-1">${__('Group holding consolidation & GL reversals')}</small>
					</a>
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
			<div class="card p-4 shadow-sm border-0 mb-4" style="border-radius: 8px; background: var(--card-bg, #fff);">
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

			<!-- Guided Educational Hub Footer -->
			<div class="card p-4 shadow-sm border-0" style="border-radius: 8px; background: var(--bg-light-gray, #f8f9fa);">
				<div class="row align-items-center">
					<div class="col-md-9">
						<h6 class="font-weight-bold mb-1"><i class="fa fa-graduation-cap text-primary mr-2"></i>${__('Need step-by-step guidance for enterprise deployment?')}</h6>
						<p class="text-muted mb-0" style="font-size: 13px;">
							${__('Explore real-world accounting scenarios (Order-to-Cash, Procure-to-Pay, Transfer Pricing margins, and Multilateral settlements) with the interactive walk-through or download the comprehensive PDF manual.')}
						</p>
					</div>
					<div class="col-md-3 text-md-right mt-3 mt-md-0">
						<button class="btn btn-sm btn-default btn-open-tutorial mr-1"><i class="fa fa-book mr-1"></i>${__('Tutorial')}</button>
						<a href="/assets/inter_company_transactions/Inter_Company_Transactions_User_Guide.pdf" target="_blank" class="btn btn-sm btn-primary"><i class="fa fa-file-pdf-o mr-1"></i>${__('User Guide PDF')}</a>
					</div>
				</div>
			</div>
		</div>
	`;

	$container.html(html);

	$container.find('.btn-quick-wizard').on('click', function() {
		open_quick_setup_wizard();
	});

	$container.find('.btn-open-tutorial').on('click', function() {
		show_tutorial_dialog();
	});
}

function render_links_cards(links) {
	if (!links || links.length === 0) {
		return `
			<div class="col-12 text-center p-4 text-muted">
				<i class="fa fa-link fa-2x mb-2" style="opacity: 0.5;"></i>
				<p class="mb-2">${__('No Intercompany Transaction Links configured yet.')}</p>
				<button class="btn btn-sm btn-primary btn-quick-wizard">${__('Launch Setup Wizard')}</button>
			</div>
		`;
	}

	const esc = frappe.utils.escape_html;
	return links.map(l => {
		let counterpartiesHtml = (l.counterparties || []).map(cp => `<span class="badge badge-light border mr-1 mb-1 p-1">${esc(cp)}</span>`).join('');
		return `
			<div class="col-md-6 col-lg-4 mb-3">
				<div class="card h-100 p-3 border" style="border-radius: 8px; border-color: var(--border-color, #e2e8f0) !important;">
					<div class="d-flex justify-content-between align-items-center mb-2">
						<span class="badge ${l.enabled ? 'badge-success' : 'badge-secondary'}">${l.enabled ? __('Active') : __('Disabled')}</span>
						<a href="/app/intercompany-transaction-link/${encodeURIComponent(l.name)}" class="btn btn-xs btn-default">${__('Edit')}</a>
					</div>
					<h6 class="font-weight-bold mb-1"><i class="fa fa-building-o mr-1 text-muted"></i>${esc(l.main_company)}</h6>
					<div class="my-2">
						<small class="text-muted d-block mb-1">${__('Connected Entities:')}</small>
						<div>${counterpartiesHtml || '<span class="text-muted" style="font-size: 11px;">None configured</span>'}</div>
					</div>
					<div class="mt-auto pt-2 border-top d-flex justify-content-between align-items-center" style="font-size: 12px;">
						<span class="text-muted">${cint(l.active_types_count)} ${__('Transaction Rules')}</span>
						<a href="/app/inter-company-document-reference?source_company=${encodeURIComponent(l.main_company || '')}" class="text-primary">${__('Audit Logs')} &rarr;</a>
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

	const esc = frappe.utils.escape_html;
	return txList.map(tx => {
		let isMirrored = !!tx.target_name;
		let badgeClass = isMirrored ? 'indicator-pill green' : 'indicator-pill orange';
		let statusText = isMirrored ? __('Synchronized') : __('Pending');

		return `
			<tr>
				<td><b>${esc(tx.source_company)}</b></td>
				<td><a href="/app/${encodeURIComponent(frappe.router.slug(tx.source_doctype))}/${encodeURIComponent(tx.source_name)}">${esc(tx.source_doctype)}: ${esc(tx.source_name)}</a></td>
				<td class="text-center text-muted">&rarr;</td>
				<td><b>${esc(tx.target_company)}</b></td>
				<td>
					${isMirrored 
						? `<a href="/app/${encodeURIComponent(frappe.router.slug(tx.target_doctype))}/${encodeURIComponent(tx.target_name)}">${esc(tx.target_doctype)}: ${esc(tx.target_name)}</a>`
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
	let selectedPreset = 'full';

	let d = new frappe.ui.Dialog({
		title: __('Inter-Company Guided Setup Wizard'),
		size: 'large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'wizard_intro',
				options: `
					<div class="ict-wizard-stepper">
						<div class="ict-wizard-step active" id="step-tab-1"><i class="fa fa-building mr-1"></i>1. ${__('Select Entities')}</div>
						<div class="ict-wizard-step" id="step-tab-2"><i class="fa fa-sliders mr-1"></i>2. ${__('Automation Preset')}</div>
						<div class="ict-wizard-step" id="step-tab-3"><i class="fa fa-check mr-1"></i>3. ${__('Confirm & Activate')}</div>
					</div>
					<div class="alert alert-info" style="font-size: 12.5px; margin-bottom: 20px;">
						<i class="fa fa-info-circle mr-1"></i>
						${__('The wizard will establish bidirectional trade between two sister companies, detect clearing accounts, and configure mirroring rules. Select Customers and Suppliers manually in Intercompany Transaction Link.')}
					</div>
				`
			},
			{
				label: __('Main Company (Initiating Entity)'),
				fieldname: 'main_company',
				fieldtype: 'Link',
				options: 'Company',
				reqd: 1,
				description: __('The parent or selling company in this transaction pipeline')
			},
			{
				label: __('Counterparty Company (Sister Entity)'),
				fieldname: 'counterparty_company',
				fieldtype: 'Link',
				options: 'Company',
				reqd: 1,
				description: __('The subsidiary or purchasing entity')
			},
			{
				fieldtype: 'Section Break',
				label: __('Automation & Transaction Profile')
			},
			{
				fieldtype: 'HTML',
				fieldname: 'preset_selector',
				options: `
					<div class="row">
						<div class="col-md-6">
							<div class="ict-preset-card selected" data-preset="full">
								<div class="d-flex align-items-center justify-content-between mb-1">
									<strong class="text-primary"><i class="fa fa-star mr-1"></i>${__('Full Enterprise Conglomerate')}</strong>
									<span class="badge badge-primary">${__('Recommended')}</span>
								</div>
								<p class="text-muted mb-1" style="font-size: 12px;">
									${__('Enables all trading rules (SO ↔ PO, DN ↔ PR, SI ↔ PI, RFQ → SQ, Material Requests), financial vouchers (JE, PE, Landed Cost → JE), and Stock Transfers.')}
								</p>
								<small class="text-success font-weight-bold"><i class="fa fa-check mr-1"></i>15 Transaction Rules</small>
							</div>
						</div>
						<div class="col-md-6">
							<div class="ict-preset-card" data-preset="trading">
								<div class="d-flex align-items-center justify-content-between mb-1">
									<strong><i class="fa fa-shopping-cart mr-1"></i>${__('Commercial Trading Only')}</strong>
									<span class="badge badge-light border">${__('Order-to-Cash')}</span>
								</div>
								<p class="text-muted mb-1" style="font-size: 12px;">
									${__('Focuses on commercial trading: Sales/Purchase Orders, Invoices, Delivery Notes, Quotations, RFQ, and Material Requests.')}
								</p>
								<small class="text-primary font-weight-bold"><i class="fa fa-check mr-1"></i>11 Trading Rules</small>
							</div>
						</div>
						<div class="col-md-6">
							<div class="ict-preset-card" data-preset="financial">
								<div class="d-flex align-items-center justify-content-between mb-1">
									<strong><i class="fa fa-university mr-1"></i>${__('Treasury & Financial Only')}</strong>
									<span class="badge badge-light border">${__('GL, Payments & LCV')}</span>
								</div>
								<p class="text-muted mb-1" style="font-size: 12px;">
									${__('Mirrors reciprocal Journal Entries, Payment Entries, and Landed Cost Vouchers between sister entity clearing accounts.')}
								</p>
								<small class="text-info font-weight-bold"><i class="fa fa-check mr-1"></i>3 Financial Rules</small>
							</div>
						</div>
						<div class="col-md-6">
							<div class="ict-preset-card" data-preset="inventory">
								<div class="d-flex align-items-center justify-content-between mb-1">
									<strong><i class="fa fa-truck mr-1"></i>${__('Logistics & Inventory Transfers')}</strong>
									<span class="badge badge-light border">${__('Supply Chain')}</span>
								</div>
								<p class="text-muted mb-1" style="font-size: 12px;">
									${__('Internal same-currency stock transfers via Stock Entries (Material Issue → Receipt), and cross-currency shipments via Delivery Notes.')}
								</p>
								<small class="text-secondary font-weight-bold"><i class="fa fa-check mr-1"></i>2 Logistics Rules</small>
							</div>
						</div>
					</div>
				`
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
					counterparty_company: values.counterparty_company,
					preset: selectedPreset
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

	// Bind preset card selection
	d.$wrapper.find('.ict-preset-card').on('click', function() {
		d.$wrapper.find('.ict-preset-card').removeClass('selected');
		$(this).addClass('selected');
		selectedPreset = $(this).data('preset');
	});
}

function show_tutorial_dialog() {
	let d = new frappe.ui.Dialog({
		title: __('Inter-Company Transactions: Practical Tutorials & Examples'),
		size: 'large',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'tutorial_content',
				options: `
					<div class="p-2" style="max-height: 550px; overflow-y: auto;">
						<!-- Example A: Order-to-Cash Mirroring -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-primary mr-2">Example A</span>
									<strong style="font-size: 14px;">Order-to-Cash & Procure-to-Pay Automated Mirroring</strong>
								</div>
								<span class="badge badge-success">Automated</span>
							</div>
							<div class="ict-tutorial-body">
								<p class="text-muted mb-3">
									<strong>Scenario:</strong> Entity A (<em>Acme Manufacturing</em>) sells 100 units of "Industrial Widget" to sister company Entity B (<em>Acme Distribution</em>) at $50/unit.
								</p>
								<div class="ict-flow-step">
									<div class="ict-flow-num">1</div>
									<div>
										<strong>Create Sales Order in Entity A:</strong> Go to <span class="ict-code-pill">Sales Order &gt; New</span>. Set Customer to <span class="ict-code-pill">Acme Distribution (Internal)</span>, Item to "Industrial Widget", Qty: 100, Rate: $50.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">2</div>
									<div>
										<strong>Submit Document:</strong> Upon submission, the engine checks company links and automatically creates a linked <span class="ict-code-pill">Purchase Order</span> in Entity B with Supplier <span class="ict-code-pill">Acme Manufacturing (Internal)</span>.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">3</div>
									<div>
										<strong>Fulfill & Invoice:</strong> Submitting a Delivery Note automatically creates a Purchase Receipt in Entity B. Submitting a Sales Invoice generates a Purchase Invoice. Zero duplicate data entry!
									</div>
								</div>
							</div>
						</div>

						<!-- Example B: Transfer Pricing (OECD) -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-info mr-2">Example B</span>
									<strong style="font-size: 14px;">Transfer Pricing Policy & Automatic Margin Calculation</strong>
								</div>
								<span class="badge badge-light border">OECD Compliant</span>
							</div>
							<div class="ict-tutorial-body">
								<p class="text-muted mb-3">
									<strong>Scenario:</strong> Headquarters manufactures a product at a valuation cost of $200. Tax regulations mandate an arm's-length <strong>15% Cost-Plus markup</strong> when selling to international subsidiaries.
								</p>
								<div class="ict-flow-step">
									<div class="ict-flow-num">1</div>
									<div>
										<strong>Define Policy:</strong> In <span class="ict-code-pill">Transfer Pricing Policy</span>, select Source Company: <em>Acme HQ</em>, Target Company: <em>Acme Europe</em>. Method: <em>Cost Plus Markup %</em>, Markup: <strong>15%</strong>.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">2</div>
									<div>
										<strong>Automated Calculation:</strong> When a Sales Order is placed, the engine queries the source warehouse valuation rate ($200) and calculates: <span class="ict-code-pill">$200 × 1.15 = $230.00</span>.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">3</div>
									<div>
										<strong>Regulatory Audit Trail:</strong> The calculated margin is permanently attached to the mirrored Purchase Order and logged in the Inter Company Document Reference audit record.
									</div>
								</div>
							</div>
						</div>

						<!-- Example C: Multilateral Netting -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-success mr-2">Example C</span>
									<strong style="font-size: 14px;">Multilateral Netting & Liquidity Optimization</strong>
								</div>
								<span class="badge badge-info">Treasury</span>
							</div>
							<div class="ict-tutorial-body">
								<p class="text-muted mb-3">
									<strong>Scenario:</strong> Three entities have circular trade debt: Company A owes B $100k, A owes C $50k, and B owes C $20k (Gross debt: $170k requiring 3 bank wires).
								</p>
								<div class="ict-flow-step">
									<div class="ict-flow-num">1</div>
									<div>
										<strong>Create Netting Cycle:</strong> Open <span class="ict-code-pill">Inter Company Netting Cycle &gt; New</span> and select the participant entities.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">2</div>
									<div>
										<strong>Fetch Invoices & Calculate:</strong> Click <em>Fetch Invoices</em>, then <em>Calculate Netting</em>. The optimization algorithm reduces the gross $170k debt to just 2 transactions totaling $150k (a $20,000 liquidity saving).
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">3</div>
									<div>
										<strong>1-Click Settlement:</strong> Click <em>Generate Settlement Journal Entries</em> to balance reciprocal AR/AP accounts across all three company ledgers instantly.
									</div>
								</div>
							</div>
						</div>

						<!-- Example D: Dispute Resolution -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-warning mr-2">Example D</span>
									<strong style="font-size: 14px;">Raising & Resolving Intercompany Disputes</strong>
								</div>
								<span class="badge badge-secondary">Discrepancy</span>
							</div>
							<div class="ict-tutorial-body">
								<p class="text-muted mb-3">
									<strong>Scenario:</strong> Sister company was billed $1,500 on an invoice, but received $300 worth of damaged goods.
								</p>
								<div class="ict-flow-step">
									<div class="ict-flow-num">1</div>
									<div>
										<strong>Raise Dispute from Desk:</strong> From the Sales/Purchase Invoice form, click <span class="ict-code-pill">Inter Company &gt; Raise Dispute</span>.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">2</div>
									<div>
										<strong>Automatic Variance Calculation:</strong> Enter the target received amount ($1,200). The system computes the $300 variance automatically and locks the document for investigation.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">3</div>
									<div>
										<strong>Execute Resolution:</strong> Choose <em>Issue Credit Note</em> or <em>Journal Adjustment</em> and click <em>Execute Resolution</em>. The correction documents are created and posted automatically.
									</div>
								</div>
							</div>
						</div>

						<!-- Example E: Supported vs Non-Supported Mirror Transactions -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-primary mr-2">Guide E</span>
									<strong style="font-size: 14px;">Mirror Transactions: What Can Be Mirrored vs. What Cannot (and Why)</strong>
								</div>
								<span class="badge badge-success">Architecture</span>
							</div>
							<div class="ict-tutorial-body">
								<h6 class="font-weight-bold text-success mb-2"><i class="fa fa-check-circle mr-1"></i> What It CAN Mirror Automatically:</h6>
								<ul class="mb-3" style="font-size: 13px; padding-left: 20px;">
									<li><strong>Sales Order &harr; Purchase Order:</strong> Creates reciprocal purchase/sale order with line items, delivery dates, and transfer pricing.</li>
									<li><strong>Sales Invoice &harr; Purchase Invoice:</strong> Mirrors billing with matching items, rates, taxes, and automatic elimination tags.</li>
									<li><strong>Delivery Note &harr; Purchase Receipt:</strong> Incoming goods receipt generated directly upon shipment dispatch.</li>
									<li><strong>Quotation &harr; Supplier Quotation:</strong> Intercompany sales estimate matched to supplier RFQ.</li>
									<li><strong>Request for Quotation &rarr; Supplier Quotation:</strong> Generates sister-company quote response directly from RFQ.</li>
									<li><strong>Material Request &rarr; Sales Order / Purchase Order:</strong> Stock requisition in Subsidiary B creates order in Parent A.</li>
									<li><strong>Stock Entry (Material Issue) &rarr; Stock Entry (Material Receipt):</strong> Material Issue in Company A automatically creates Material Receipt in Company B with valuation rate preserved (<strong>Same-Currency companies only</strong>; use Delivery Note or Sales Invoice for different currencies).</li>
									<li><strong>Journal Entry &harr; Journal Entry:</strong> Intercompany GL transfer voucher with auto-swapped debit/credit accounts.</li>
									<li><strong>Payment Entry &harr; Payment Entry:</strong> Intercompany payment matched to receipt voucher.</li>
									<li><strong>Landed Cost Voucher &rarr; Journal Entry:</strong> Automatically recharges landed cost taxes/charges into a balanced Journal Entry in the target sister company.</li>
								</ul>

								<h6 class="font-weight-bold text-danger mb-2"><i class="fa fa-times-circle mr-1"></i> What It CANNOT Do Directly & Why It Is a MUST:</h6>
								<ul class="mb-0" style="font-size: 13px; padding-left: 20px;">
									<li><strong>Subcontracting Order:</strong> <em>Why:</em> Subcontracting in ERPNext v15 requires entity-internal BOM explosion and supplied item tracking. <em>Must do instead:</em> Create paired <code>Purchase Order</code> (Subcontracted) &rarr; <code>Sales Order</code> (Manufacturing).</li>
									<li><strong>Fixed Asset Movements / Depreciation:</strong> <em>Why:</em> Fixed assets belong to statutory legal entity registers. <em>Must do instead:</em> Sell asset via <code>Sales Invoice</code> (Disposal) and receive in sister company via <code>Purchase Invoice</code>.</li>
									<li><strong>Payroll Entry / Salary Slip:</strong> <em>Why:</em> Governed by legal entity tax and social security laws. <em>Must do instead:</em> Shared management costs are recharged via <code>Journal Entry</code> (Intercompany JV) or management fee <code>Sales Invoice</code>.</li>
								</ul>
							</div>
						</div>

						<!-- Example F: Inter Company Customer Group -->
						<div class="ict-tutorial-card">
							<div class="ict-tutorial-header">
								<div>
									<span class="badge badge-info mr-2">Guide F</span>
									<strong style="font-size: 14px;">Inter Company Customer Group: Purpose & Step-by-Step Example</strong>
								</div>
								<span class="badge badge-primary">Accounting Setup</span>
							</div>
							<div class="ict-tutorial-body">
								<p class="text-muted mb-2">
									<strong>What is it?</strong> An <strong>Inter Company Customer Group</strong> is a dedicated Customer Group in ERPNext (e.g., <em>"Inter Company Trading"</em> or <em>"Group Entities"</em>) specifically assigned to internal customers that represent sister companies.
								</p>
								<div class="alert alert-info py-2 px-3 mb-3" style="font-size: 12.5px;">
									<strong>Why is it mandatory for professional enterprise accounting?</strong>
									<ul class="mb-0 mt-1 pl-3">
										<li><strong>Financial Isolation:</strong> Prevents internal transfer turnover from inflating third-party trade revenue on Accounts Receivable Aging reports.</li>
										<li><strong>Automated Consolidation Elimination:</strong> Allows the <em>Inter Company Elimination Run</em> to isolate and eliminate all internal receivables and payables without risk of touching external customer balances.</li>
										<li><strong>Exemptions:</strong> Sister entities can be given 0% internal transfer pricing rules, unlimited credit limits, and custom intercompany GL clearing accounts.</li>
										<li><strong>DocType Custom Field (<code>ic_customer_group</code>):</strong> Enables the app's routing engine to recognize and validate internal partner entities.</li>
									</ul>
								</div>

								<div class="ict-flow-step">
									<div class="ict-flow-num">1</div>
									<div>
										<strong>Create Customer Group:</strong> Navigate to <span class="ict-code-pill">Customer Group &gt; New</span>. Set Name to <strong>Inter Company Group</strong>, Parent Group to <em>All Customer Groups</em>. Leave <em>Is Group</em> unchecked.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">2</div>
									<div>
										<strong>Assign to Internal Customer:</strong> Open the internal customer (e.g., <em>Distribution LLC (Internal)</em>). Set <strong>Customer Group</strong> (or <strong>Inter Company Customer Group</strong>) to <em>Inter Company Group</em>. Check <em>Is Internal Customer</em> and set <em>Represents Company</em>.
									</div>
								</div>
								<div class="ict-flow-step">
									<div class="ict-flow-num">3</div>
									<div>
										<strong>Ready for Clean Consolidation:</strong> All sales invoices issued to this customer are now segregated in group accounts and ready for automated period-end elimination!
									</div>
								</div>
							</div>
						</div>
					</div>
				`
			}
		],
		primary_action_label: __('Open PDF Manual'),
		primary_action: function() {
			window.open('/assets/inter_company_transactions/Inter_Company_Transactions_User_Guide.pdf', '_blank');
		},
		secondary_action_label: __('Close'),
		secondary_action: function() {
			d.hide();
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
	const esc = frappe.utils.escape_html;
	let recsHtml = (h.recommendations || []).length > 0
		? h.recommendations.map(rc => `<li class="text-warning mb-1">${esc(rc)}</li>`).join('')
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
							<span class="badge ${h.status === 'Healthy' ? 'badge-success' : 'badge-warning'}" style="font-size: 14px; padding: 6px 12px;">${esc(h.status)}</span>
						</div>
						<div class="row mb-3 text-center">
							<div class="col-4 border-right">
								<h4 class="mb-0 font-weight-bold text-primary">${cint(h.total_companies)}</h4>
								<small class="text-muted">${__('Total Entities')}</small>
							</div>
							<div class="col-4 border-right">
								<h4 class="mb-0 font-weight-bold text-success">${cint(h.active_links)}</h4>
								<small class="text-muted">${__('Active Channels')}</small>
							</div>
							<div class="col-4">
								<h4 class="mb-0 font-weight-bold ${h.error_log_count > 0 ? 'text-danger' : 'text-secondary'}">${cint(h.error_log_count)}</h4>
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
