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
		expr = expr.replace(/__islocalanddoc/g, '__islocal && doc');
		expr = expr.replace(/__islocaland/g, '__islocal && ');
		expr = expr.replace(/\banddoc\./g, ' && doc.');

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

			// 1. Root patch for frappe.utils.eval (used by layout.js, grid_row.js, controls)
			if (frappe.utils && frappe.utils.eval && !frappe.utils.eval._ict_sanitized) {
				const orig_utils_eval = frappe.utils.eval;
				frappe.utils.eval = function(code, context) {
					if (!code || typeof code !== 'string') return true;
					const sanitized = sanitize_depends_on_expression(code);
					try {
						return orig_utils_eval.call(this, sanitized, context);
					} catch (err) {
						try {
							let clean = sanitized;
							if (clean.startsWith('eval:')) clean = clean.substring(5);
							let doc = (context && context.doc) || (window.cur_frm && window.cur_frm.doc) || {};
							let parent = (context && context.parent) || doc;
							let fn = new Function('doc', 'parent', 'let out = ' + clean + '; return out;');
							return fn(doc, parent);
						} catch (evalErr) {
							console.warn('[ICT utils.eval] Safely caught invalid expression:', code, evalErr);
							return false;
						}
					}
				};
				frappe.utils.eval._ict_sanitized = true;
			}

			// 2. Patch frappe.ui.form.Layout.prototype.evaluate_depends_on_value (layout.js:773)
			if (frappe.ui && frappe.ui.form && frappe.ui.form.Layout && frappe.ui.form.Layout.prototype.evaluate_depends_on_value && !frappe.ui.form.Layout.prototype.evaluate_depends_on_value._ict_sanitized) {
				const orig_layout_eval = frappe.ui.form.Layout.prototype.evaluate_depends_on_value;
				frappe.ui.form.Layout.prototype.evaluate_depends_on_value = function(expression, doc) {
					if (!expression) return true;
					const sanitized = sanitize_depends_on_expression(expression);
					try {
						return orig_layout_eval.call(this, sanitized, doc);
					} catch (err) {
						try {
							let clean = sanitized;
							if (clean.startsWith('eval:')) clean = clean.substring(5);
							let parent = (this.frm && this.frm.doc) || doc || {};
							let fn = new Function('doc', 'parent', 'let out = ' + clean + '; return out;');
							return fn(doc || parent, parent);
						} catch (evalErr) {
							console.warn('[ICT Layout] Safely caught invalid expression:', expression, evalErr);
							return false;
						}
					}
				};
				frappe.ui.form.Layout.prototype.evaluate_depends_on_value._ict_sanitized = true;
			}

			// 3. Patch frappe.ui.form.evaluate_depends_on_value
			if (frappe.ui && frappe.ui.form && frappe.ui.form.evaluate_depends_on_value && !frappe.ui.form.evaluate_depends_on_value._ict_sanitized) {
				const orig_eval = frappe.ui.form.evaluate_depends_on_value;
				frappe.ui.form.evaluate_depends_on_value = function(expression, doc, parent) {
					if (!expression) return true;
					const sanitized = sanitize_depends_on_expression(expression);
					try {
						return orig_eval.call(this, sanitized, doc, parent);
					} catch (err) {
						try {
							let code = sanitized;
							if (code.startsWith('eval:')) {
								code = code.substring(5);
							}
							let fn = new Function('doc', 'parent', 'let out = ' + code + '; return out;');
							return fn(doc, parent);
						} catch (evalErr) {
							console.warn('[ICT] Safely caught invalid depends_on expression:', expression, evalErr);
							return false;
						}
					}
				};
				frappe.ui.form.evaluate_depends_on_value._ict_sanitized = true;
			}

			// 4. Patch frappe.ui.form.GridRow.prototype.evaluate_depends_on_value (grid_row.js:823)
			if (frappe.ui && frappe.ui.form && frappe.ui.form.GridRow && frappe.ui.form.GridRow.prototype.evaluate_depends_on_value && !frappe.ui.form.GridRow.prototype.evaluate_depends_on_value._ict_sanitized) {
				const orig_grid_eval = frappe.ui.form.GridRow.prototype.evaluate_depends_on_value;
				frappe.ui.form.GridRow.prototype.evaluate_depends_on_value = function(expression) {
					if (!expression) return true;
					const sanitized = sanitize_depends_on_expression(expression);
					try {
						return orig_grid_eval.call(this, sanitized);
					} catch (err) {
						try {
							let doc = this.doc;
							let parent = (this.grid && (this.grid.df.doc || (this.grid.frm && this.grid.frm.doc))) || null;
							if (!parent && doc && doc.parent && window.locals && window.locals[doc.parenttype]) {
								parent = window.locals[doc.parenttype][doc.parent];
							}
							let code = sanitized;
							if (code.startsWith('eval:')) {
								code = code.substring(5);
							}
							let fn = new Function('doc', 'parent', 'let out = ' + code + '; return out;');
							return fn(doc, parent);
						} catch (evalErr) {
							console.warn('[ICT GridRow] Safely caught invalid depends_on expression:', expression, evalErr);
							return false;
						}
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
		'Request for Quotation'
	];

	function sync_intercompany_state(frm) {
		try {
			if (!frm || !frm.fields_dict || !frm.fields_dict.is_intercompany || !frm.fields_dict.intercompany_target_company) {
				return;
			}

			// Ensure evaluators are patched before any df properties are touched
			patch_evaluate_depends_on();

			const is_intercompany = cint(frm.doc.is_intercompany);
			const current_company = frm.doc.company || '';

			if (!is_intercompany) {
				// Normal internal transaction:
				// 1. Target company is read-only and not required
				frm.set_df_property('intercompany_target_company', 'read_only', 1);
				frm.set_df_property('intercompany_target_company', 'reqd', 0);

				// CRITICAL FOR SUBMIT BUTTON:
				// NEVER call frm.set_value during refresh or onload on saved clean forms!
				// Calling frm.set_value marks the form dirty (frm.is_dirty() = true),
				// which causes Frappe Desk to keep showing 'Save' and prevents the 'Submit'
				// button from ever appearing after saving non-intercompany transactions.
				if (frm.doc.intercompany_target_company) {
					if (frm.is_new()) {
						frm.set_value('intercompany_target_company', '');
					} else {
						// On already saved forms, clear model property without dirtying the form
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

				// Clear filter query so normal browsing is not blocked
				frm.set_query('intercompany_target_company', function() {
					return {};
				});
			} else {
				// Intercompany transaction:
				// 1. Target company is editable (if draft) and mandatory
				if (frm.doc.docstatus === 0) {
					frm.set_df_property('intercompany_target_company', 'read_only', 0);
					frm.set_df_property('intercompany_target_company', 'reqd', 1);

					// 2. If it is currently holding the source company, clear it to prompt user selection
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

				// 3. Filter query so user can ONLY select other sister companies
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

				// Show navigation button to linked document if one exists
				if (frm.doc.intercompany_linked_doc_name && frm.doc.intercompany_linked_doc_doctype) {
					const targetDocType = frm.doc.intercompany_linked_doc_doctype;
					const targetDocName = frm.doc.intercompany_linked_doc_name;
					const targetCompany = frm.doc.intercompany_linked_company || '';

					frm.add_custom_button(
						__('Open Linked {0}', [__(targetDocType)]),
						function() {
							frappe.set_route('Form', targetDocType, targetDocName);
						},
						__('Inter Company')
					);

					// Raise dispute button for enterprise dispute management
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

					// Add badge/intro banner in dashboard
					if (frm.dashboard && frm.dashboard.set_headline_alert) {
						frm.dashboard.set_headline_alert(
							__('Linked Inter-Company Document: <a href="/app/{0}/{1}"><b>{2} {3}</b></a> ({4})', [
								frappe.router.slug(targetDocType),
								targetDocName,
								__(targetDocType),
								targetDocName,
								targetCompany
							]),
							'blue'
						);
					}
				} else if (frm.doc.docstatus === 1 && cint(frm.doc.is_intercompany)) {
					// Allow manual sync trigger for submitted documents ONLY IF is_intercompany is checked
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
								callback: function(r) {
									if (r.message && r.message.success) {
										frappe.show_alert({
											message: r.message.message,
											indicator: 'green'
										});
										frm.reload_doc();
									} else if (r.message) {
										frappe.msgprint({
											title: __('Inter-Company Sync Notice'),
											indicator: 'orange',
											message: r.message.message
										});
									}
								}
							});
						},
						__('Inter Company')
					);
				}
			},
			is_intercompany: function(frm) {
				if (cint(frm.doc.is_intercompany)) {
					frm._user_manually_checked_intercompany = true;
					frm._user_unchecked_intercompany = false;
					frm.set_df_property('intercompany_target_company', 'read_only', 0);
					frm.set_df_property('intercompany_target_company', 'reqd', 1);
					if (frm.doc.intercompany_target_company === frm.doc.company) {
						frm.set_value('intercompany_target_company', '');
					}
					sync_intercompany_state(frm);
					frappe.show_alert({
						message: __('Intercompany mode enabled: Select target sister company in Intercompany Target Company.'),
						indicator: 'blue'
					});
				} else {
					frm._user_manually_checked_intercompany = false;
					frm._user_unchecked_intercompany = true;
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
		if (frm.doc.docstatus > 0) return; // Only apply to drafts

		if (!party_name) {
			if (!frm._user_manually_checked_intercompany) {
				if (cint(frm.doc.is_intercompany)) {
					frm.set_value('is_intercompany', 0);
				}
				if (frm.doc.intercompany_target_company) {
					frm.set_value('intercompany_target_company', '');
				}
				sync_intercompany_state(frm);
			}
			return;
		}

		ict.get_target_company_for_party(party_name, party_type, frm.doc.company, function(target_company) {
			if (target_company && target_company !== frm.doc.company) {
				frm._user_manually_unchecked = false;
				frm.set_value('is_intercompany', 1);
				frm.set_value('intercompany_target_company', target_company);
				sync_intercompany_state(frm);
				frappe.show_alert({
					message: __('Intercompany transaction with sister company {0} detected.', [target_company]),
					indicator: 'blue'
				});
			} else {
				if (!frm._user_manually_checked_intercompany) {
					if (cint(frm.doc.is_intercompany)) {
						frm.set_value('is_intercompany', 0);
					}
					if (frm.doc.intercompany_target_company) {
						frm.set_value('intercompany_target_company', '');
					}
					sync_intercompany_state(frm);
				}
			}
		});
	}

	function handle_journal_entry_row_party_change(frm, cdt, cdn) {
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
		if (frm.doc.docstatus > 0) return;

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
			if (!cint(frm.doc.is_intercompany)) {
				frm.set_value('is_intercompany', 1);
			}
			if (frm.doc.intercompany_target_company !== found_target_company) {
				frm.set_value('intercompany_target_company', found_target_company);
			}
			sync_intercompany_state(frm);
		} else if (!frm._user_manually_checked_intercompany) {
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

	// Global auto-switch for Intercompany Transaction Type child rows
	const ICT_TARGET_MAPPING = {
		'Sales Order': 'Purchase Order',
		'Purchase Order': 'Sales Order',
		'Sales Invoice': 'Purchase Invoice',
		'Purchase Invoice': 'Sales Invoice',
		'Delivery Note': 'Purchase Receipt',
		'Purchase Receipt': 'Delivery Note',
		'Stock Entry': 'Stock Entry',
		'Journal Entry': 'Journal Entry',
		'Payment Entry': 'Payment Entry',
		'Quotation': 'Supplier Quotation',
		'Supplier Quotation': 'Quotation',
		'Material Request': 'Purchase Order',
		'Request for Quotation': 'Supplier Quotation',
		'Subcontracting Order': 'Purchase Order',
		'Landed Cost Voucher': 'Journal Entry'
	};

	frappe.ui.form.on('Intercompany Transaction Type', {
		source_type: function(frm, cdt, cdn) {
			let row = locals[cdt][cdn];
			if (!row || !row.source_type) return;

			let target = ICT_TARGET_MAPPING[row.source_type];
			if (target) {
				frappe.model.set_value(cdt, cdn, 'target_type', target);
			}

			if (!row.direction) {
				frappe.model.set_value(cdt, cdn, 'direction', 'Both');
			}
		}
	});
})();

