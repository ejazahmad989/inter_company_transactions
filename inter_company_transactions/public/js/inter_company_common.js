// Copyright (c) 2024-2026, Inter Company Transactions and contributors
// Desk enhancements for intercompany transactions

(function() {
	/**
	 * Client-side sanitizer for depends_on, mandatory_depends_on, and read_only_depends_on.
	 * Translates Python-style operators ("not ", " and ", " or ") into valid JavaScript ("!", " && ", " || ")
	 * and fixes glued operators like 1or(, 0or(, )or(, or(, etc.
	 * Ensures forms, grid rows, and layouts NEVER crash with 'Invalid "depends_on" expression'.
	 */
	function sanitize_depends_on_expression(expression) {
		if (!expression || typeof expression !== 'string') return expression;
		let expr = expression.trim();
		let hasEval = false;
		if (expr.startsWith('eval:')) {
			hasEval = true;
			expr = expr.substring(5).trim();
		}

		// Fix corrupted __islocalanddoc in standard Item / Customer / Supplier forms
		expr = expr.replace(/__islocalanddoc\b/g, '__islocal && doc');
		expr = expr.replace(/__islocalanddoc\./g, '__islocal && doc.');
		expr = expr.replace(/__islocaland/g, '__islocal && ');
		expr = expr.replace(/__islocal\s*and\s*doc\b/g, '__islocal && doc');
		expr = expr.replace(/\banddoc\./g, ' && doc.');
		expr = expr.replace(/(\w+)\s*anddoc\./g, '$1 && doc.');


		// Fix glued 'or' operators (e.g. 1or(, 0or(, )or(, or(, )or, 1or, 0or)
		expr = expr.replace(/(\d)\s*or\s*(?=[(\w])/g, function(m, p1) { return p1 + ' || '; });
		expr = expr.replace(/(\))\s*or\s*(?=[(\w])/g, function(m, p1) { return p1 + ' || '; });
		expr = expr.replace(/\bor\s*\(/g, '|| (');
		expr = expr.replace(/\s+or\s+/g, ' || ');
		expr = expr.replace(/\bor\b/g, ' || ');

		// Fix glued 'and' operators (e.g. 1and(, 0and(, )and(, and(, etc.)
		expr = expr.replace(/(\d)\s*and\s*(?=[(\w])/g, function(m, p1) { return p1 + ' && '; });
		expr = expr.replace(/(\))\s*and\s*(?=[(\w])/g, function(m, p1) { return p1 + ' && '; });
		expr = expr.replace(/\band\s*\(/g, '&& (');
		expr = expr.replace(/\s+and\s+/g, ' && ');
		expr = expr.replace(/\band\b/g, ' && ');

		// Replace Python negation "not " with JS "!"
		expr = expr.replace(/\bnot\s+(?=[a-zA-Z0-9_\(\[\$])/g, '!');

		// Replace Python True, False, None
		expr = expr.replace(/\bTrue\b/g, 'true');
		expr = expr.replace(/\bFalse\b/g, 'false');
		expr = expr.replace(/\bNone\b/g, 'null');

		return hasEval ? ('eval:' + expr) : expr;
	}

	function patch_evaluate_depends_on() {
		try {
			if (!window.frappe) return;

			function safe_eval_expression(code, doc, parent) {
				if (!code) return true;
				let clean = sanitize_depends_on_expression(code);
				if (typeof clean === 'string' && clean.startsWith('eval:')) {
					clean = clean.substring(5).trim();
				}
				let d = doc || (window.cur_frm && window.cur_frm.doc) || {};
				let p = parent || (window.cur_frm && window.cur_frm.doc) || d;
				try {
					let fn = new Function('doc', 'parent', 'let out = ' + clean + '; return out;');
					return !!fn(d, p);
				} catch (e) {
					return false;
				}
			}

			// 1. Wrap Layout.prototype.evaluate_depends_on_value safely
			if (frappe.ui && frappe.ui.form && frappe.ui.form.Layout && frappe.ui.form.Layout.prototype.evaluate_depends_on_value && !frappe.ui.form.Layout.prototype.evaluate_depends_on_value._ict_sanitized) {
				const orig_layout_eval = frappe.ui.form.Layout.prototype.evaluate_depends_on_value;
				frappe.ui.form.Layout.prototype.evaluate_depends_on_value = function(expression, doc) {
					if (!expression) return true;
					try {
						return orig_layout_eval.apply(this, arguments);
					} catch (e) {
						let parent = (this.frm && this.frm.doc) || doc || {};
						let current_doc = doc || parent;
						return safe_eval_expression(expression, current_doc, parent);
					}
				};
				frappe.ui.form.Layout.prototype.evaluate_depends_on_value._ict_sanitized = true;
			}

			// 2. Wrap frappe.ui.form.evaluate_depends_on_value safely
			if (frappe.ui && frappe.ui.form && frappe.ui.form.evaluate_depends_on_value && !frappe.ui.form.evaluate_depends_on_value._ict_sanitized) {
				const orig_form_eval = frappe.ui.form.evaluate_depends_on_value;
				frappe.ui.form.evaluate_depends_on_value = function(expression, doc, parent) {
					if (!expression) return true;
					try {
						return orig_form_eval.apply(this, arguments);
					} catch (e) {
						return safe_eval_expression(expression, doc, parent);
					}
				};
				frappe.ui.form.evaluate_depends_on_value._ict_sanitized = true;
			}

			// 3. Wrap GridRow.prototype.evaluate_depends_on_value safely
			if (frappe.ui && frappe.ui.form && frappe.ui.form.GridRow && frappe.ui.form.GridRow.prototype.evaluate_depends_on_value && !frappe.ui.form.GridRow.prototype.evaluate_depends_on_value._ict_sanitized) {
				const orig_grid_eval = frappe.ui.form.GridRow.prototype.evaluate_depends_on_value;
				frappe.ui.form.GridRow.prototype.evaluate_depends_on_value = function(expression) {
					if (!expression) return true;
					try {
						return orig_grid_eval.apply(this, arguments);
					} catch (e) {
						let doc = this.doc;
						let parent = (this.grid && (this.grid.df.doc || (this.grid.frm && this.grid.frm.doc))) || null;
						return safe_eval_expression(expression, doc, parent);
					}
				};
				frappe.ui.form.GridRow.prototype.evaluate_depends_on_value._ict_sanitized = true;
			}
		} catch (e) {
			// Protection should never fail silently or break caller
		}
	}


	// Install immediately, on DOM ready, and on page-change / route change
	patch_evaluate_depends_on();
	if (typeof $ !== 'undefined') {
		$(document).ready(patch_evaluate_depends_on);
		$(document).on('page-change', patch_evaluate_depends_on);
		$(document).on('form-refresh', patch_evaluate_depends_on);
	}

	const supportedDocTypes = [
		'Sales Order',
		'Purchase Order',
		'Sales Invoice',
		'Purchase Invoice',
		'Delivery Note',
		'Purchase Receipt',
		'Quotation',
		'Supplier Quotation',
		'Material Request',
		'Stock Entry',
		'Journal Entry',
		'Payment Entry',
		'Request for Quotation',
		'Landed Cost Voucher'
	];

	function is_mirrored_counterpart(frm) {
		return !!(frm && frm.doc && (frm.doc.intercompany_linked_doc_name || frm.doc.intercompany_linked_doc_doctype));
	}

	function detect_form_party_target(frm) {
		if (!frm || !frm.doc || !frm.doc.company) return null;
		const map = (frappe.boot && frappe.boot.intercompany_party_map) || window._ict_party_map;
		if (!map || !window.ict || !ict.resolve_target_sync) return null;

		const dt = frm.doc.doctype;
		if (['Sales Order', 'Sales Invoice', 'Delivery Note', 'Quotation'].includes(dt) && frm.doc.customer) {
			return ict.resolve_target_sync(frm.doc.customer, 'customer', frm.doc.company, map);
		}
		if (['Purchase Order', 'Purchase Invoice', 'Purchase Receipt', 'Supplier Quotation'].includes(dt) && frm.doc.supplier) {
			return ict.resolve_target_sync(frm.doc.supplier, 'supplier', frm.doc.company, map);
		}
		if (dt === 'Payment Entry' && frm.doc.party) {
			return ict.resolve_target_sync(frm.doc.party, (frm.doc.party_type || '').toLowerCase(), frm.doc.company, map);
		}
		if (dt === 'Journal Entry' && frm.doc.accounts) {
			for (let i = 0; i < frm.doc.accounts.length; i++) {
				const r = frm.doc.accounts[i];
				if (r && r.party) {
					const tgt = ict.resolve_target_sync(r.party, r.party_type, frm.doc.company, map);
					if (tgt && tgt !== frm.doc.company) return tgt;
				}
			}
		}
		return null;
	}

	function apply_mirrored_counterpart_locks(frm) {
		if (!is_mirrored_counterpart(frm)) return;

		const lockedHeaderFields = [
			'company',
			'currency',
			'conversion_rate',
			'paid_amount',
			'received_amount',
			'source_exchange_rate',
			'target_exchange_rate',
			'paid_from',
			'paid_to',
			'customer',
			'supplier',
			'party_type',
			'party',
			'party_name',
			'payment_type',
			'is_intercompany',
			'intercompany_target_company'
		];

		lockedHeaderFields.forEach(function(fn) {
			if (frm.fields_dict && frm.fields_dict[fn]) {
				frm.set_df_property(fn, 'read_only', 1);
			}
		});

		// Lock item amounts/quantities while keeping local Warehouse & Cost Center editable
		if (frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid) {
			const itemGrid = frm.fields_dict.items.grid;
			const lockedItemCols = ['item_code', 'qty', 'uom', 'rate', 'basic_rate', 'amount', 'basic_amount', 'conversion_factor'];
			lockedItemCols.forEach(function(col) {
				if (typeof itemGrid.update_docfield_property === 'function') {
					itemGrid.update_docfield_property(col, 'read_only', 1);
				}
			});
		}

		// Lock JE financial currency/exchange/amount columns while keeping Expense/Cost Center editable
		if (frm.doc.doctype === 'Journal Entry' && frm.fields_dict && frm.fields_dict.accounts && frm.fields_dict.accounts.grid) {
			const accGrid = frm.fields_dict.accounts.grid;
			const lockedAccCols = [
				'account_currency',
				'exchange_rate',
				'debit_in_account_currency',
				'credit_in_account_currency',
				'debit',
				'credit',
				'party_type',
				'party'
			];
			lockedAccCols.forEach(function(col) {
				if (typeof accGrid.update_docfield_property === 'function') {
					accGrid.update_docfield_property(col, 'read_only', 1);
				}
			});
		}
	}

	function add_linked_doc_ui(frm, targetDocType, targetDocName, targetCompany, isCounterpart) {
		const esc = frappe.utils.escape_html;
		frm.add_custom_button(
			__('Open Linked {0}', [__(targetDocType)]),
			function() {
				frappe.set_route('Form', targetDocType, targetDocName);
			},
			__('Inter Company')
		);

		frm.add_custom_button(
			__('Raise Dispute'),
			function() {
				frappe.new_doc('Inter Company Dispute', {
					source_doctype: frm.doc.doctype,
					source_name: frm.doc.name,
					source_company: frm.doc.company,
					target_company: targetCompany,
					source_amount: frm.doc.grand_total || frm.doc.total || 0,
					dispute_title: __('Dispute for {0} {1}', [frm.doc.doctype, frm.doc.name])
				});
			},
			__('Inter Company')
		);

		if (frm.dashboard && frm.dashboard.set_headline_alert) {
			if (isCounterpart) {
				frm.dashboard.set_headline_alert(
					__('Mirrored Inter-Company Draft from <a href="/app/{0}/{1}"><b>{2} {3}</b></a> ({4}). Currency, exchange rates, parties & amounts are strictly locked \u2014 contact <b>{4}</b> to cancel or amend. Warehouse / Cost Center / Account remain editable.', [
						encodeURIComponent(frappe.router.slug(targetDocType)),
						encodeURIComponent(targetDocName),
						esc(__(targetDocType)),
						esc(targetDocName),
						esc(targetCompany)
					]),
					'orange'
				);
			} else {
				frm.dashboard.set_headline_alert(
					__('Linked Inter-Company Document: <a href="/app/{0}/{1}"><b>{2} {3}</b></a> ({4})', [
						encodeURIComponent(frappe.router.slug(targetDocType)),
						encodeURIComponent(targetDocName),
						esc(__(targetDocType)),
						esc(targetDocName),
						esc(targetCompany)
					]),
					'blue'
				);
			}
		}
	}

	function sync_intercompany_state(frm) {
		try {
			if (!frm || !frm.fields_dict || !frm.fields_dict.is_intercompany || !frm.fields_dict.intercompany_target_company) {
				return;
			}

			// Ensure evaluators are patched before any df properties are touched
			patch_evaluate_depends_on();

			if (is_mirrored_counterpart(frm)) {
				apply_mirrored_counterpart_locks(frm);
				return;
			}

			const is_intercompany = cint(frm.doc.is_intercompany);
			const current_company = frm.doc.company || '';
			const detected_party_target = detect_form_party_target(frm);
			if (detected_party_target && detected_party_target !== current_company) {
				frm._ict_party_locked_target = detected_party_target;
			} else if (!frm._user_manually_checked_intercompany) {
				// Leave any active async lock untouched unless party is cleared
				if (!frm.doc.customer && !frm.doc.supplier && !frm.doc.party) {
					frm._ict_party_locked_target = null;
				}
			}

			if (!is_intercompany) {
				// Normal internal transaction:
				frm.set_df_property('intercompany_target_company', 'read_only', 1);
				frm.set_df_property('intercompany_target_company', 'reqd', 0);
				frm._ict_party_locked_target = null;

				// CRITICAL FOR SUBMIT BUTTON:
				// NEVER call frm.set_value during refresh or onload on saved clean forms!
				if (frm.doc.intercompany_target_company) {
					if (frm.is_new()) {
						frm.set_value('intercompany_target_company', '');
					} else {
						frm.doc.intercompany_target_company = '';
						if (frm.fields_dict.intercompany_target_company.$input) {
							frm.fields_dict.intercompany_target_company.set_input('');
						}
					}
				}

				if (frm.doc.doctype === 'Journal Entry' && frm.doc.accounts) {
					(frm.doc.accounts || []).forEach(row => {
						if (row.intercompany_target_company) {
							row.intercompany_target_company = '';
						}
					});
				}

				frm.set_query('intercompany_target_company', function() {
					return {};
				});
			} else {
				// Intercompany transaction:
				if (frm.doc.docstatus === 0) {
					// Strict lock: if auto-detected from intercompany party, keep target company read-only
					const is_party_locked = !!(frm._ict_party_locked_target && frm.doc.intercompany_target_company === frm._ict_party_locked_target);
					frm.set_df_property('intercompany_target_company', 'read_only', is_party_locked ? 1 : 0);
					frm.set_df_property('intercompany_target_company', 'reqd', 1);

					if (frm.doc.intercompany_target_company && frm.doc.intercompany_target_company === current_company) {
						if (frm.is_new()) {
							frm.set_value('intercompany_target_company', '');
						} else {
							frm.doc.intercompany_target_company = '';
							if (frm.fields_dict.intercompany_target_company.$input) {
								frm.fields_dict.intercompany_target_company.set_input('');
							}
						}
					}
				}

				frm.set_query('intercompany_target_company', function() {
					return {
						filters: [
							['Company', 'name', '!=', current_company]
						]
					};
				});
			}
		} catch (err) {
			console.warn('[ICT] Warning in sync_intercompany_state:', err);
		}
	}

	supportedDocTypes.forEach(function(dt) {
		frappe.ui.form.on(dt, {
			onload: function(frm) {
				sync_intercompany_state(frm);
			},
			refresh: function(frm) {
				sync_intercompany_state(frm);

				// Show navigation button & locks for Mirrored Counterpart
				if (frm.doc.intercompany_linked_doc_name && frm.doc.intercompany_linked_doc_doctype) {
					add_linked_doc_ui(
						frm,
						frm.doc.intercompany_linked_doc_doctype,
						frm.doc.intercompany_linked_doc_name,
						frm.doc.intercompany_linked_company || frm.doc.intercompany_target_company || '',
						true
					);
				} else if (frm.doc.docstatus === 0 && cint(frm.doc.is_intercompany) && frm.dashboard && frm.dashboard.set_headline_alert) {
					if (frm.doc.doctype === 'Stock Entry') {
						frm.dashboard.set_headline_alert(
							__('Inter-Company Stock Transfer: Submit as Material Issue in {0}; a matching Material Receipt will be auto-created in {1}.', [
								frm.doc.company || __('Source Company'),
								frm.doc.intercompany_target_company || __('Target Sister Company')
							]),
							'blue'
						);
					} else if (frm.doc.doctype === 'Landed Cost Voucher') {
						frm.dashboard.set_headline_alert(
							__('Inter-Company Landed Cost Recharge: On submit, a balanced Journal Entry will be auto-created in {0}.', [
								frm.doc.intercompany_target_company || __('Target Sister Company')
							]),
							'blue'
						);
					}
				} else if (frm.doc.docstatus === 1 && cint(frm.doc.is_intercompany) && !frm.is_new()) {
					// Check if a mirrored counterpart already exists in Inter Company Document Reference
					frappe.call({
						method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_linked_counterpart_for_form',
						args: {
							doctype: frm.doc.doctype,
							name: frm.doc.name
						},
						callback: function(r) {
							const cps = (r && r.message && r.message.counterparts) || [];
							if (cps.length > 0) {
								const first = cps[0];
								add_linked_doc_ui(frm, first.doctype, first.name, first.company || '', false);
							} else {
								frm.add_custom_button(
									__('Sync Mirror Now'),
									function() {
										frappe.call({
											method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.trigger_manual_intercompany_sync',
											args: {
												doctype: frm.doc.doctype,
												name: frm.doc.name
											},
											freeze: true,
											freeze_message: __('Processing Inter-Company Mirroring...'),
											callback: function(res) {
												if (res.message && res.message.success) {
													frappe.show_alert({
														message: res.message.message,
														indicator: 'green'
													});
													frm.reload_doc();
												} else if (res.message) {
													frappe.msgprint({
														title: __('Inter-Company Sync Notice'),
														indicator: 'orange',
														message: res.message.message
													});
												}
											}
										});
									},
									__('Inter Company')
								);
							}
						}
					});
				}
			},
			is_intercompany: function(frm) {
				if (is_mirrored_counterpart(frm)) return;
				if (cint(frm.doc.is_intercompany)) {
					if (!frm._ict_party_locked_target) {
						frm._user_manually_checked_intercompany = true;
					}
					frm._user_unchecked_intercompany = false;
					frm.set_df_property('intercompany_target_company', 'read_only', frm._ict_party_locked_target ? 1 : 0);
					frm.set_df_property('intercompany_target_company', 'reqd', 1);
					if (frm.doc.intercompany_target_company === frm.doc.company) {
						frm.set_value('intercompany_target_company', '');
					}
					if (frm.doc.doctype === 'Stock Entry' && frm.doc.docstatus === 0 && !frm.doc.stock_entry_type) {
						frm.set_value('stock_entry_type', 'Material Issue');
					}
					sync_intercompany_state(frm);
					let msg = __('Intercompany mode enabled: Select target sister company in Intercompany Target Company.');
					if (frm.doc.doctype === 'Stock Entry') {
						msg = __('Intercompany Stock Transfer enabled (Material Issue -> Material Receipt in target sister company).');
					} else if (frm.doc.doctype === 'Landed Cost Voucher') {
						msg = __('Intercompany Landed Cost Recharge enabled (mirrors balanced Journal Entry in target sister company).');
					}
					frappe.show_alert({
						message: msg,
						indicator: 'blue'
					});
				} else {
					frm._user_manually_checked_intercompany = false;
					frm._user_unchecked_intercompany = true;
					frm._ict_party_locked_target = null;
					frm.set_df_property('intercompany_target_company', 'read_only', 1);
					frm.set_df_property('intercompany_target_company', 'reqd', 0);
					if (frm.doc.intercompany_target_company) {
						frm.set_value('intercompany_target_company', '');
					}
					if (frm.doc.doctype === 'Journal Entry' && frm.doc.accounts) {
						(frm.doc.accounts || []).forEach(row => {
							if (row.intercompany_target_company) {
								frappe.model.set_value(row.doctype, row.name, 'intercompany_target_company', '');
							}
						});
					}
					sync_intercompany_state(frm);
					frappe.show_alert({
						message: __('Standard internal transaction mode.'),
						indicator: 'gray'
					});
				}
			},
			company: function(frm) {
				if (is_mirrored_counterpart(frm)) return;
				if (cint(frm.doc.is_intercompany)) {
					if (frm.doc.intercompany_target_company === frm.doc.company) {
						frm.set_value('intercompany_target_company', '');
					}
				} else {
					if (frm.doc.intercompany_target_company) {
						frm.set_value('intercompany_target_company', '');
					}
				}
				sync_intercompany_state(frm);
			},
			validate: function(frm) {
				if (is_mirrored_counterpart(frm)) {
					return;
				}
				if (cint(frm.doc.is_intercompany)) {
					if (!frm.doc.intercompany_target_company) {
						frappe.msgprint({
							title: __('Intercompany Target Company Required'),
							indicator: 'red',
							message: __('Please select an Intercompany Target Company for this inter-company transaction.')
						});
						frappe.validated = false;
						return false;
					}
					if (frm.doc.company && frm.doc.intercompany_target_company === frm.doc.company) {
						frappe.msgprint({
							title: __('Invalid Intercompany Target Company'),
							indicator: 'red',
							message: __('For an inter-company transaction, Target Company cannot be the same as Source Company ({0}). Please choose another sister company.', [frm.doc.company])
						});
						frappe.validated = false;
						return false;
					}
				} else {
					if (frm.doc.intercompany_target_company) {
						frm.doc.intercompany_target_company = '';
					}
					if (frm.doc.doctype === 'Journal Entry' && frm.doc.accounts) {
						(frm.doc.accounts || []).forEach(row => {
							if (row.intercompany_target_company) {
								row.intercompany_target_company = '';
							}
						});
					}
				}
			}
		});
	});

	// -------------------------------------------------------------
	// DYNAMIC INTERCOMPANY PARTY AUTOMATION
	// Automatically checks customer/supplier against Intercompany Transaction Link
	// and auto-ticks Is Intercompany & sets Intercompany Target Company
	// -------------------------------------------------------------
	window.ict = window.ict || {};

	ict.resolve_target_sync = function(party_name, party_type, current_company, map) {
		if (!party_name || !map) return null;

		// 1. By current company if available
		if (current_company && map.by_company && map.by_company[current_company]) {
			let comp_dict = map.by_company[current_company];
			let pt = (party_type || '').toLowerCase();
			if (pt && comp_dict[pt] && comp_dict[pt][party_name]) {
				return comp_dict[pt][party_name];
			}
			if (comp_dict.all && comp_dict.all[party_name]) {
				return comp_dict.all[party_name];
			}
		}

		// 2. By universal party type
		let pt = (party_type || '').toLowerCase();
		if (pt && map.universal && map.universal[pt] && map.universal[pt][party_name]) {
			let tgt = map.universal[pt][party_name];
			if (!current_company || tgt !== current_company) return tgt;
		}

		// 3. By global party_to_company
		if (map.party_to_company && map.party_to_company[party_name]) {
			let tgt = map.party_to_company[party_name];
			if (!current_company || tgt !== current_company) return tgt;
		}

		return null;
	};

	ict.get_target_company_for_party = function(party_name, party_type, current_company, callback) {
		let map = (frappe.boot && frappe.boot.intercompany_party_map) || window._ict_party_map;

		if (map) {
			let tgt = ict.resolve_target_sync(party_name, party_type, current_company, map);
			if (tgt) {
				if (callback) callback(tgt);
				return tgt;
			}
		}

		// Fallback direct server call: checks represents_company and Intercompany Linked Company dynamically
		frappe.call({
			method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_party_target_company',
			args: {
				party_name: party_name,
				party_type: party_type,
				current_company: current_company
			},
			callback: function(r) {
				let tgt = (r && r.message && r.message.target_company) || null;
				if (tgt) {
					if (!window._ict_party_map) {
						window._ict_party_map = { party_to_company: {}, by_company: {}, universal: {} };
					}
					window._ict_party_map.party_to_company[party_name] = tgt;
					if (frappe.boot && frappe.boot.intercompany_party_map) {
						frappe.boot.intercompany_party_map.party_to_company[party_name] = tgt;
					}
				}
				if (callback) callback(tgt);
			}
		});
	};

	ict.refresh_party_map = function(callback) {
		frappe.call({
			method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_intercompany_party_map',
			callback: function(r) {
				let fresh_map = r.message || { party_to_company: {}, by_company: {}, universal: {} };
				window._ict_party_map = fresh_map;
				if (frappe.boot) frappe.boot.intercompany_party_map = fresh_map;
				if (callback) callback(fresh_map);
			}
		});
	};

	function handle_party_selection(frm, party_type, party_name) {
		if (!frm || !frm.fields_dict || !frm.fields_dict.is_intercompany) return;
		if (frm.doc.docstatus > 0 || is_mirrored_counterpart(frm)) return;

		if (!party_name) {
			frm._ict_party_locked_target = null;
			if (!frm._user_manually_checked_intercompany) {
				if (cint(frm.doc.is_intercompany)) {
					frm.set_value('is_intercompany', 0);
				}
				if (frm.doc.intercompany_target_company) {
					frm.set_value('intercompany_target_company', '');
				}
				sync_intercompany_state(frm);
			} else {
				sync_intercompany_state(frm);
			}
			return;
		}

		ict.get_target_company_for_party(party_name, party_type, frm.doc.company, function(target_company) {
			if (target_company && target_company !== frm.doc.company) {
				frm._user_manually_unchecked = false;
				frm._user_manually_checked_intercompany = false;
				frm._ict_party_locked_target = target_company;
				frm.set_value('is_intercompany', 1);
				frm.set_value('intercompany_target_company', target_company);
				sync_intercompany_state(frm);
				frappe.show_alert({
					message: __('Intercompany transaction with sister company {0} detected (Target Company locked).', [target_company]),
					indicator: 'blue'
				});
			} else {
				frm._ict_party_locked_target = null;
				if (!frm._user_manually_checked_intercompany) {
					if (cint(frm.doc.is_intercompany)) {
						frm.set_value('is_intercompany', 0);
					}
					if (frm.doc.intercompany_target_company) {
						frm.set_value('intercompany_target_company', '');
					}
					sync_intercompany_state(frm);
				} else {
					sync_intercompany_state(frm);
				}
			}
		});
	}

	function handle_journal_entry_row_party_change(frm, cdt, cdn) {
		if (is_mirrored_counterpart(frm) || frm.doc.docstatus > 0) return;
		let row = locals[cdt] && locals[cdt][cdn];
		if (!row) return;

		let party_name = row.party;
		let party_type = (row.party_type || '').toLowerCase();

		if (!party_name) {
			if (row.intercompany_target_company) {
				frappe.model.set_value(cdt, cdn, 'intercompany_target_company', '');
			}
			check_and_sync_journal_entry_accounts(frm);
			return;
		}

		ict.get_target_company_for_party(party_name, party_type, frm.doc.company, function(target_company) {
			if (target_company && target_company !== frm.doc.company) {
				frappe.model.set_value(cdt, cdn, 'intercompany_target_company', target_company);
				frm._user_manually_unchecked = false;
				frm._user_manually_checked_intercompany = false;
				frm._ict_party_locked_target = target_company;
				if (!cint(frm.doc.is_intercompany)) {
					frm.set_value('is_intercompany', 1);
				}
				if (!frm.doc.intercompany_target_company || frm.doc.intercompany_target_company !== target_company) {
					frm.set_value('intercompany_target_company', target_company);
				}
				sync_intercompany_state(frm);
				frappe.show_alert({
					message: __('Intercompany party {0} mapped to sister company {1}.', [party_name, target_company]),
					indicator: 'blue'
				});
			} else {
				if (row.intercompany_target_company) {
					frappe.model.set_value(cdt, cdn, 'intercompany_target_company', '');
				}
				check_and_sync_journal_entry_accounts(frm);
			}
		});
	}

	function check_and_sync_journal_entry_accounts(frm) {
		if (!frm || !frm.doc || !frm.doc.accounts) return;
		if (frm.doc.docstatus > 0 || is_mirrored_counterpart(frm)) return;

		let map = (frappe.boot && frappe.boot.intercompany_party_map) || window._ict_party_map;
		let found_target_company = null;

		(frm.doc.accounts || []).forEach(row => {
			if (row.party) {
				let tgt = ict.resolve_target_sync(row.party, row.party_type, frm.doc.company, map);
				if (tgt && tgt !== frm.doc.company) {
					if (!found_target_company) found_target_company = tgt;
					if (row.intercompany_target_company !== tgt) {
						frappe.model.set_value(row.doctype, row.name, 'intercompany_target_company', tgt);
					}
				} else if (row.intercompany_target_company && !tgt) {
					frappe.model.set_value(row.doctype, row.name, 'intercompany_target_company', '');
				}
			}
		});

		if (found_target_company) {
			frm._ict_party_locked_target = found_target_company;
			if (!cint(frm.doc.is_intercompany)) {
				frm.set_value('is_intercompany', 1);
			}
			if (frm.doc.intercompany_target_company !== found_target_company) {
				frm.set_value('intercompany_target_company', found_target_company);
			}
			sync_intercompany_state(frm);
		} else if (!frm._user_manually_checked_intercompany) {
			frm._ict_party_locked_target = null;
			// No intercompany party in any accounts row
			if (cint(frm.doc.is_intercompany)) {
				frm.set_value('is_intercompany', 0);
			}
			if (frm.doc.intercompany_target_company) {
				frm.set_value('intercompany_target_company', '');
			}
			(frm.doc.accounts || []).forEach(row => {
				if (row.intercompany_target_company) {
					frappe.model.set_value(row.doctype, row.name, 'intercompany_target_company', '');
				}
			});
			sync_intercompany_state(frm);
		}
	}

	// Attach customer triggers
	['Sales Order', 'Sales Invoice', 'Delivery Note', 'Quotation'].forEach(function(dt) {
		frappe.ui.form.on(dt, {
			customer: function(frm) {
				handle_party_selection(frm, 'customer', frm.doc.customer);
			}
		});
	});

	// Attach supplier triggers
	['Purchase Order', 'Purchase Invoice', 'Purchase Receipt', 'Supplier Quotation'].forEach(function(dt) {
		frappe.ui.form.on(dt, {
			supplier: function(frm) {
				handle_party_selection(frm, 'supplier', frm.doc.supplier);
			}
		});
	});

	// Attach Payment Entry triggers
	frappe.ui.form.on('Payment Entry', {
		party: function(frm) {
			handle_party_selection(frm, (frm.doc.party_type || '').toLowerCase(), frm.doc.party);
		},
		party_type: function(frm) {
			if (frm.doc.party) {
				handle_party_selection(frm, (frm.doc.party_type || '').toLowerCase(), frm.doc.party);
			}
		}
	});

	function fix_journal_entry_accounts_grid_columns(frm) {
		try {
			if (!frm || !frm.fields_dict || !frm.fields_dict.accounts) return;
			const grid = frm.fields_dict.accounts.grid;
			if (!grid || !grid.docfields) return;

			// Ensure optimal column distribution within standard 10-column limit:
			// Account (2) + Party Type (1) + Party (2) + Intercompany Target Company (1) + Debit (2) + Credit (2) = 10
			const target_cols = {
				'account': 2,
				'party_type': 1,
				'party': 2,
				'intercompany_target_company': 1,
				'debit_in_account_currency': 2,
				'credit_in_account_currency': 2
			};

			let changed = false;
			grid.docfields.forEach(function(df) {
				if (target_cols[df.fieldname] !== undefined) {
					if (df.columns !== target_cols[df.fieldname] || !df.in_list_view) {
						df.columns = target_cols[df.fieldname];
						df.in_list_view = 1;
						changed = true;
					}
				}
			});

			if (changed && typeof grid.setup_visible_columns === 'function') {
				grid.setup_visible_columns();
				if (grid.header_row && typeof grid.header_row.render === 'function') {
					grid.header_row.render();
				}
				if (typeof grid.refresh === 'function') {
					grid.refresh();
				}
			}
		} catch (err) {
			console.warn('[ICT] Could not auto-tune Journal Entry grid columns:', err);
		}
	}

	// Attach Journal Entry parent triggers
	frappe.ui.form.on('Journal Entry', {
		setup: function(frm) {
			fix_journal_entry_accounts_grid_columns(frm);
		},
		refresh: function(frm) {
			fix_journal_entry_accounts_grid_columns(frm);
		},
		before_save: function(frm) {
			check_and_sync_journal_entry_accounts(frm);
		},
		validate: function(frm) {
			check_and_sync_journal_entry_accounts(frm);
		}
	});

	// Attach Journal Entry Account child row triggers
	frappe.ui.form.on('Journal Entry Account', {
		party: function(frm, cdt, cdn) {
			handle_journal_entry_row_party_change(frm, cdt, cdn);
		},
		party_type: function(frm, cdt, cdn) {
			handle_journal_entry_row_party_change(frm, cdt, cdn);
		},
		accounts_add: function(frm) {
			fix_journal_entry_accounts_grid_columns(frm);
		},
		accounts_remove: function(frm) {
			check_and_sync_journal_entry_accounts(frm);
		}
	});

	// Refresh cache when Intercompany Transaction Link is saved
	frappe.ui.form.on('Intercompany Transaction Link', {
		after_save: function() {
			if (ict.refresh_party_map) {
				ict.refresh_party_map();
			}
		}
	});
})();

