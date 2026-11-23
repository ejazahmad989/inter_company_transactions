// Copyright (c) 2024-2026, Ejaz Tech and Contributors
// Desk enhancements for intercompany transactions

(function() {

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
		if (dt === 'Quotation' && frm.doc.quotation_to === 'Customer' && (frm.doc.party_name || frm.doc.customer)) {
			return ict.resolve_target_sync(frm.doc.party_name || frm.doc.customer, 'customer', frm.doc.company, map);
		}
		if (['Sales Order', 'Sales Invoice', 'Delivery Note'].includes(dt) && frm.doc.customer) {
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
		if (frm.fields_dict && frm.fields_dict.intercompany_target_company) {
			frm.set_df_property('intercompany_target_company', 'reqd', 0);
		}

		// On mirrored Payment Entry drafts, allow switching the Bank/Cash side account (e.g. TMP -> Cash/Bank)
		// while keeping party control account, currency, amounts, and exchange rates strictly locked.
		if (frm.doc.doctype === 'Payment Entry') {
			if (!frm.is_dirty() || !frm._ict_pe_snapshot) {
				frm._ict_pe_snapshot = {
					paid_amount: frm.doc.paid_amount,
					received_amount: frm.doc.received_amount,
					source_exchange_rate: frm.doc.source_exchange_rate,
					target_exchange_rate: frm.doc.target_exchange_rate,
					paid_from_account_currency: frm.doc.paid_from_account_currency,
					paid_to_account_currency: frm.doc.paid_to_account_currency
				};
			}
			const peType = frm.doc.payment_type;
			const isDraft = cint(frm.doc.docstatus) === 0;
			if (frm.fields_dict && frm.fields_dict.paid_from) {
				frm.set_df_property('paid_from', 'read_only', (isDraft && peType !== 'Receive') ? 0 : 1);
			}
			if (frm.fields_dict && frm.fields_dict.paid_to) {
				frm.set_df_property('paid_to', 'read_only', (isDraft && peType !== 'Pay') ? 0 : 1);
			}
			['paid_from_account_currency', 'paid_to_account_currency'].forEach(function(fn) {
				if (frm.fields_dict && frm.fields_dict[fn]) {
					frm.set_df_property(fn, 'read_only', 1);
				}
			});
		}

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
				'party',
				'intercompany_target_company'
			];
			lockedAccCols.forEach(function(col) {
				if (typeof accGrid.update_docfield_property === 'function') {
					accGrid.update_docfield_property(col, 'read_only', 1);
				}
			});
		}
	}

	function add_linked_doc_ui(frm, targetDocType, targetDocName, targetCompany, isCounterpart, counterpartMeta) {
		const esc = frappe.utils.escape_html;
		const isOrphan = !!(
			counterpartMeta &&
			isCounterpart &&
			!counterpartMeta.is_remote &&
			(counterpartMeta.exists === false || cint(counterpartMeta.docstatus) === 2)
		);

		if (!counterpartMeta || counterpartMeta.exists !== false) {
			frm.add_custom_button(
				__('Open Linked {0}', [__(targetDocType)]),
				function() {
					frappe.set_route('Form', targetDocType, targetDocName);
				},
				__('Inter Company')
			);
		}

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

		if (isCounterpart && frm.doc.docstatus === 0 && !frm.is_new() && frappe.model && frappe.model.can_delete(frm.doc.doctype)) {
			frm.add_custom_button(
				__('Delete Mirrored Draft'),
				function() {
					frappe.confirm(
						__('Permanently delete Draft {0} <b>{1}</b> and remove its inter-company document reference?', [esc(__(frm.doc.doctype)), esc(frm.doc.name)]),
						function() {
							frappe.call({
								method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.delete_mirrored_draft',
								args: {
									doctype: frm.doc.doctype,
									name: frm.doc.name
								},
								freeze: true,
								freeze_message: __('Deleting Mirrored Draft...'),
								callback: function(res) {
									if (res && res.message && res.message.deleted) {
										frappe.show_alert({
											message: __('{0} {1} deleted.', [__(frm.doc.doctype), frm.doc.name]),
											indicator: 'green'
										});
										frappe.set_route('List', frm.doc.doctype);
									}
								}
							});
						}
					);
				},
				__('Inter Company')
			);
		}

		const isManager = frappe.user && (frappe.user.has_role('System Manager') || frappe.user.has_role('Accounts Manager'));
		if (isCounterpart && !frm.is_new() && (isOrphan || isManager)) {
			frm.add_custom_button(
				isOrphan ? __('Unlink Orphan Reference') : __('Unlink Counterpart Reference'),
				function() {
					const promptMsg = isOrphan
						? __('Source {0} <b>{1}</b> no longer exists or is cancelled. Unlink <b>{2}</b> so it can be edited, cancelled, or deleted independently?', [esc(__(targetDocType)), esc(targetDocName), esc(frm.doc.name)])
						: __('Manually unlink <b>{0} {1}</b> from source {2} <b>{3}</b>? Any tracking row in Inter Company Document Reference will be removed.', [esc(__(frm.doc.doctype)), esc(frm.doc.name), esc(__(targetDocType)), esc(targetDocName)]);
					frappe.confirm(
						promptMsg,
						function() {
							frappe.call({
								method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.unlink_mirrored_document',
								args: {
									doctype: frm.doc.doctype,
									name: frm.doc.name
								},
								freeze: true,
								freeze_message: __('Unlinking Inter-Company Reference...'),
								callback: function(res) {
									if (res && res.message && res.message.unlinked) {
										frappe.show_alert({
											message: __('Inter-company link removed from {0}.', [frm.doc.name]),
											indicator: 'green'
										});
										frm.reload_doc();
									}
								}
							});
						}
					);
				},
				__('Inter Company')
			);
		}

		if (frm.dashboard && frm.dashboard.set_headline_alert) {
			if (isCounterpart && isOrphan) {
				frm.dashboard.set_headline_alert(
					__('Source document <b>{0} {1}</b> ({2}) was deleted or cancelled. You can now cancel, delete, or click <b>Inter Company -> Unlink Orphan Reference</b> to manage this entry independently.', [
						esc(__(targetDocType)),
						esc(targetDocName),
						esc(targetCompany)
					]),
					'orange'
				);
			} else if (isCounterpart) {
				const docStateLabel = frm.doc.docstatus === 0 ? __('Draft') : (frm.doc.docstatus === 1 ? __('Document') : __('Cancelled Document'));
				frm.dashboard.set_headline_alert(
					__('Mirrored Inter-Company {5} from <a href="/app/{0}/{1}"><b>{2} {3}</b></a> ({4}). Currency, exchange rates, parties & amounts are strictly locked \u2014 contact <b>{4}</b> to cancel or amend. Warehouse / Cost Center / Account remain editable.', [
						encodeURIComponent(frappe.router.slug(targetDocType)),
						encodeURIComponent(targetDocName),
						esc(__(targetDocType)),
						esc(targetDocName),
						esc(targetCompany),
						docStateLabel
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

	function get_voucher_tx_date(frm) {
		return (frm && frm.doc && (frm.doc.posting_date || frm.doc.transaction_date)) || frappe.datetime.get_today();
	}

	function doc_has_inline_cross_currency_rate(frm, info) {
		if (!frm || !frm.doc || !info) return false;
		const src_ccy = info.from_currency;
		const tgt_ccy = info.to_currency;
		if (!src_ccy || !tgt_ccy || src_ccy === tgt_ccy) return true;

		if (frm.doc.currency && frm.doc.currency !== src_ccy && flt(frm.doc.conversion_rate) > 0 && flt(frm.doc.conversion_rate) !== 1) {
			return true;
		}
		if (frm.doc.doctype === 'Payment Entry') {
			if (frm.doc.paid_from_account_currency && frm.doc.paid_from_account_currency !== src_ccy && flt(frm.doc.source_exchange_rate) > 0 && flt(frm.doc.source_exchange_rate) !== 1) {
				return true;
			}
			if (frm.doc.paid_to_account_currency && frm.doc.paid_to_account_currency !== src_ccy && flt(frm.doc.target_exchange_rate) > 0 && flt(frm.doc.target_exchange_rate) !== 1) {
				return true;
			}
		}
		if (frm.doc.doctype === 'Journal Entry' && Array.isArray(frm.doc.accounts)) {
			for (let i = 0; i < frm.doc.accounts.length; i++) {
				const row = frm.doc.accounts[i];
				if (row && row.account_currency && row.account_currency !== src_ccy && flt(row.exchange_rate) > 0 && flt(row.exchange_rate) !== 1) {
					return true;
				}
			}
		}
		return false;
	}

	function prompt_exchange_rate_dialog(frm, info, on_saved, on_cancel) {
		const esc = frappe.utils.escape_html;
		const from_ccy = info.from_currency;
		const to_ccy = info.to_currency;
		const tx_date = info.transaction_date || get_voucher_tx_date(frm);
		const opt_to_to_from = __('1 {0} = ? {1}', [to_ccy, from_ccy]);
		const opt_from_to_to = __('1 {0} = ? {1}', [from_ccy, to_ccy]);

		let saved_done = false;
		let default_dir = opt_to_to_from;
		let default_rate = info.inverse_rate || '';
		if (!default_rate && info.exchange_rate) {
			default_dir = opt_from_to_to;
			default_rate = info.exchange_rate;
		}

		const dialog = new frappe.ui.Dialog({
			title: __('Exchange Rate Required ({0} ↔ {1})', [from_ccy, to_ccy]),
			fields: [
				{
					fieldname: 'intro_html',
					fieldtype: 'HTML',
					options: '<div style="margin-bottom: 10px; line-height: 1.5;">' +
						__('<b>{0}</b> ({1}) and <b>{2}</b> ({3}) use different base currencies.<br>Save a Currency Exchange rate for <b>{4}</b> so both companies\' ledgers stay 100% balanced.', [
							esc(frm.doc.company || ''),
							esc(from_ccy),
							esc(frm.doc.intercompany_target_company || ''),
							esc(to_ccy),
							esc(tx_date)
						]) +
						'</div>'
				},
				{
					fieldname: 'direction',
					fieldtype: 'Select',
					label: __('Quote Direction'),
					options: [opt_to_to_from, opt_from_to_to].join('\n'),
					default: default_dir,
					reqd: 1
				},
				{
					fieldname: 'rate',
					fieldtype: 'Float',
					label: __('Exchange Rate'),
					precision: 9,
					default: default_rate || undefined,
					reqd: 1,
					description: __('Example: if 1 {0} = 275 {1}, enter 275.', [to_ccy, from_ccy])
				},
				{
					fieldname: 'date',
					fieldtype: 'Date',
					label: __('Effective Date'),
					default: tx_date,
					reqd: 1
				},
				{
					fieldname: 'preview_html',
					fieldtype: 'HTML'
				}
			],
			primary_action_label: __('Save Exchange Rate'),
			primary_action: function(values) {
				const entered = flt(values.rate);
				if (entered <= 0) {
					frappe.msgprint({
						title: __('Invalid Exchange Rate'),
						indicator: 'red',
						message: __('Exchange rate must be greater than zero.')
					});
					return;
				}
				const is_to_from = values.direction === opt_to_to_from;
				const save_from = is_to_from ? to_ccy : from_ccy;
				const save_to = is_to_from ? from_ccy : to_ccy;

				frappe.call({
					method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.save_intercompany_currency_exchange',
					args: {
						from_currency: save_from,
						to_currency: save_to,
						exchange_rate: entered,
						date: values.date || tx_date
					},
					freeze: true,
					freeze_message: __('Saving Currency Exchange...'),
					callback: function(res) {
						if (res && res.message && res.message.success) {
							saved_done = true;
							dialog.hide();
							frappe.show_alert({
								message: __('Saved exchange rate: 1 {0} = {1} {2}', [save_from, flt(entered, 6), save_to]),
								indicator: 'green'
							});
							if (typeof on_saved === 'function') {
								on_saved(res.message);
							}
						}
					}
				});
			}
		});

		function update_preview() {
			const v = flt(dialog.get_value('rate'));
			const dir = dialog.get_value('direction');
			const $wrapper = dialog.fields_dict.preview_html && dialog.fields_dict.preview_html.$wrapper;
			if (!$wrapper) return;
			if (v > 0) {
				const is_to_from = dir === opt_to_to_from;
				const r_to_from = is_to_from ? v : (1.0 / v);
				const r_from_to = is_to_from ? (1.0 / v) : v;
				$wrapper.html(
					'<div class="text-muted small" style="padding: 6px 0;">' +
					__('Converted Rates: <b>1 {0} = {1} {2}</b> &nbsp;|&nbsp; <b>1 {2} = {3} {0}</b>', [
						esc(to_ccy),
						flt(r_to_from, 6),
						esc(from_ccy),
						flt(r_from_to, 9)
					]) +
					'</div>'
				);
			} else {
				$wrapper.html('');
			}
		}

		['rate', 'direction'].forEach(function(fn) {
			const field = dialog.fields_dict[fn];
			if (field && field.$input) {
				field.$input.on('input change', update_preview);
			}
		});

		if (dialog.$wrapper) {
			dialog.$wrapper.on('hidden.bs.modal', function() {
				if (!saved_done && typeof on_cancel === 'function') {
					on_cancel();
				}
			});
		}

		dialog.show();
		update_preview();
	}

	function check_stock_entry_same_currency_ui(frm, clear_on_mismatch, on_result) {
		if (!frm || !frm.doc || frm.doc.doctype !== 'Stock Entry' || frm.doc.docstatus !== 0 || is_mirrored_counterpart(frm)) {
			if (typeof on_result === 'function') on_result(true);
			return;
		}
		if (!cint(frm.doc.is_intercompany) || !frm.doc.company || !frm.doc.intercompany_target_company) {
			if (typeof on_result === 'function') on_result(true);
			return;
		}
		if (frm.doc.company === frm.doc.intercompany_target_company) {
			if (typeof on_result === 'function') on_result(false);
			return;
		}

		const esc = frappe.utils.escape_html;
		frappe.call({
			method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.check_stock_entry_same_currency',
			args: {
				source_company: frm.doc.company,
				target_company: frm.doc.intercompany_target_company
			},
			callback: function(r) {
				const info = r && r.message;
				if (!info || info.allowed) {
					frm._ict_se_currency_mismatch = false;
					if (typeof on_result === 'function') on_result(true);
					return;
				}

				frm._ict_se_currency_mismatch = info;
				const msg = __(
					'<b>Stock Entry</b> only works for <b>Same-Currency companies</b>.<br><br><b>{0}</b> uses <b>{1}</b> while <b>{2}</b> uses <b>{3}</b>.<br><br>For different currencies, please use <b>Delivery Note &rarr; Purchase Receipt</b> or <b>Sales Invoice &rarr; Purchase Invoice</b>.',
					[
						esc(frm.doc.company),
						esc(info.source_currency),
						esc(frm.doc.intercompany_target_company),
						esc(info.target_currency)
					]
				);
				if (frm.dashboard && frm.dashboard.set_headline_alert) {
					frm.dashboard.set_headline_alert(msg, 'orange');
				}
				if (clear_on_mismatch) {
					frappe.msgprint({
						title: __('Same-Currency Only for Stock Entry'),
						indicator: 'orange',
						message: msg
					});
					frm.set_value('intercompany_target_company', '');
				}
				if (typeof on_result === 'function') on_result(false);
			},
			error: function() {
				if (typeof on_result === 'function') on_result(true);
			}
		});
	}

	function check_and_update_exchange_rate_ui(frm) {
		if (!frm || !frm.doc || frm.doc.docstatus !== 0 || is_mirrored_counterpart(frm)) return;
		if (frm.doc.doctype === 'Stock Entry') {
			check_stock_entry_same_currency_ui(frm, false);
			return;
		}
		if (!cint(frm.doc.is_intercompany) || !frm.doc.company || !frm.doc.intercompany_target_company) return;
		if (frm.doc.company === frm.doc.intercompany_target_company) return;

		const esc = frappe.utils.escape_html;
		frappe.call({
			method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.check_intercompany_exchange_rate',
			args: {
				source_company: frm.doc.company,
				target_company: frm.doc.intercompany_target_company,
				transaction_date: get_voucher_tx_date(frm),
				doc_currency: frm.doc.currency || null,
				conversion_rate: frm.doc.conversion_rate || null
			},
			callback: function(r) {
				const info = r && r.message;
				if (!info) return;
				frm._ict_fx_info = info;
				if (!info.required) return;

				const has_inline = doc_has_inline_cross_currency_rate(frm, info);
				if (!info.has_rate && !has_inline) {
					if (frm.dashboard && frm.dashboard.set_headline_alert) {
						frm.dashboard.set_headline_alert(
							__('Cross-Currency Exchange Rate Required: <b>{0}</b> ({1}) ↔ <b>{2}</b> ({3}) on <b>{4}</b>. Click <b>Inter Company → Set Exchange Rate</b> before submitting.', [
								esc(frm.doc.company),
								esc(info.from_currency),
								esc(frm.doc.intercompany_target_company),
								esc(info.to_currency),
								esc(info.transaction_date || get_voucher_tx_date(frm))
							]),
							'orange'
						);
					}
					frm.add_custom_button(
						__('Set Exchange Rate ({0} ↔ {1})', [info.from_currency, info.to_currency]),
						function() {
							prompt_exchange_rate_dialog(frm, info, function() {
								frm.refresh();
							});
						},
						__('Inter Company')
					);
				} else {
					frm.add_custom_button(
						__('Update Exchange Rate ({0} ↔ {1})', [info.from_currency, info.to_currency]),
						function() {
							prompt_exchange_rate_dialog(frm, info, function() {
								frm.refresh();
							});
						},
						__('Inter Company')
					);
				}
			}
		});
	}

	supportedDocTypes.forEach(function(dt) {
		frappe.ui.form.on(dt, {
			onload: function(frm) {
				sync_intercompany_state(frm);
			},
			refresh: function(frm) {
				sync_intercompany_state(frm);

				// Show navigation button, draft delete, orphan unlink & locks for Mirrored Counterpart
				if (frm.doc.intercompany_linked_doc_name && frm.doc.intercompany_linked_doc_doctype) {
					const fallbackDt = frm.doc.intercompany_linked_doc_doctype;
					const fallbackName = frm.doc.intercompany_linked_doc_name;
					const fallbackCo = frm.doc.intercompany_linked_company || frm.doc.intercompany_target_company || '';
					if (!frm.is_new()) {
						frappe.call({
							method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.get_linked_counterpart_for_form',
							args: {
								doctype: frm.doc.doctype,
								name: frm.doc.name
							},
							callback: function(r) {
								const cps = (r && r.message && r.message.counterparts) || [];
								const first = cps.length > 0 ? cps[0] : null;
								add_linked_doc_ui(
									frm,
									(first && first.doctype) || fallbackDt,
									(first && first.name) || fallbackName,
									(first && first.company) || fallbackCo,
									true,
									first
								);
							}
						});
					} else {
						add_linked_doc_ui(frm, fallbackDt, fallbackName, fallbackCo, true, null);
					}
				} else if (frm.doc.docstatus === 0 && cint(frm.doc.is_intercompany)) {
					if (frm.dashboard && frm.dashboard.set_headline_alert) {
						if (frm.doc.doctype === 'Stock Entry') {
							frm.dashboard.set_headline_alert(
								__('Inter-Company Stock Transfer (Same-Currency Companies Only): Submit as Material Issue in {0}; a matching Material Receipt will be auto-created in {1}. Use Delivery Note or Sales Invoice for different currencies.', [
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
					}
					check_and_update_exchange_rate_ui(frm);
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
								add_linked_doc_ui(frm, first.doctype, first.name, first.company || '', false, first);
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
					check_and_update_exchange_rate_ui(frm);
					let msg = __('Intercompany mode enabled: Select target sister company in Intercompany Target Company.');
					if (frm.doc.doctype === 'Stock Entry') {
						msg = __('Intercompany Stock Transfer enabled (Same-Currency companies only: Material Issue -> Material Receipt).');
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
			intercompany_target_company: function(frm) {
				if (is_mirrored_counterpart(frm)) return;
				sync_intercompany_state(frm);
				if (frm.doc.doctype === 'Stock Entry') {
					check_stock_entry_same_currency_ui(frm, true);
				} else {
					check_and_update_exchange_rate_ui(frm);
				}
			},
			posting_date: function(frm) {
				check_and_update_exchange_rate_ui(frm);
			},
			transaction_date: function(frm) {
				check_and_update_exchange_rate_ui(frm);
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
				if (frm.doc.doctype === 'Stock Entry') {
					check_stock_entry_same_currency_ui(frm, true);
				} else {
					check_and_update_exchange_rate_ui(frm);
				}
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
			},
			before_submit: function(frm) {
				if (
					is_mirrored_counterpart(frm) ||
					!cint(frm.doc.is_intercompany) ||
					!frm.doc.company ||
					!frm.doc.intercompany_target_company ||
					frm.doc.company === frm.doc.intercompany_target_company
				) {
					return;
				}

				if (frm.doc.doctype === 'Stock Entry') {
					return new Promise(function(resolve) {
						check_stock_entry_same_currency_ui(frm, true, function(allowed) {
							if (!allowed) {
								frappe.validated = false;
							}
							resolve();
						});
					});
				}

				return new Promise(function(resolve) {
					frappe.call({
						method: 'inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link.check_intercompany_exchange_rate',
						args: {
							source_company: frm.doc.company,
							target_company: frm.doc.intercompany_target_company,
							transaction_date: get_voucher_tx_date(frm),
							doc_currency: frm.doc.currency || null,
							conversion_rate: frm.doc.conversion_rate || null
						},
						callback: function(r) {
							const info = r && r.message;
							if (!info || !info.required || info.has_rate || doc_has_inline_cross_currency_rate(frm, info)) {
								resolve();
								return;
							}
							prompt_exchange_rate_dialog(
								frm,
								info,
								function() {
									resolve();
								},
								function() {
									frappe.validated = false;
									frappe.show_alert({
										message: __('Submission cancelled — Currency Exchange rate between {0} and {1} is required.', [info.from_currency, info.to_currency]),
										indicator: 'orange'
									});
									resolve();
								}
							);
						},
						error: function() {
							resolve();
						}
					});
				});
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
	['Sales Order', 'Sales Invoice', 'Delivery Note'].forEach(function(dt) {
		frappe.ui.form.on(dt, {
			customer: function(frm) {
				handle_party_selection(frm, 'customer', frm.doc.customer);
			}
		});
	});
	frappe.ui.form.on('Quotation', {
		customer: function(frm) {
			handle_party_selection(frm, 'customer', frm.doc.customer || frm.doc.party_name);
		},
		party_name: function(frm) {
			if (frm.doc.quotation_to === 'Customer') {
				handle_party_selection(frm, 'customer', frm.doc.party_name);
			}
		}
	});

	// Attach supplier triggers
	['Purchase Order', 'Purchase Invoice', 'Purchase Receipt', 'Supplier Quotation'].forEach(function(dt) {
		frappe.ui.form.on(dt, {
			supplier: function(frm) {
				handle_party_selection(frm, 'supplier', frm.doc.supplier);
			}
		});
	});

	function preserve_mirrored_pe_locked_values(frm, account_fieldname) {
		if (!is_mirrored_counterpart(frm) || cint(frm.doc.docstatus) !== 0 || !frm._ict_pe_snapshot) return;
		const snap = frm._ict_pe_snapshot;
		const restore = function() {
			if (!frm || !frm.doc) return;
			const ccyField = account_fieldname === 'paid_from' ? 'paid_from_account_currency' : 'paid_to_account_currency';
			const expectedCcy = snap[ccyField];
			if (expectedCcy && frm.doc[ccyField] && frm.doc[ccyField] !== expectedCcy) {
				frappe.msgprint({
					title: __('Account Currency Locked'),
					indicator: 'orange',
					message: __('On mirrored Payment Entries, please select a Bank or Cash account in currency {0}.', [expectedCcy])
				});
			}
			['source_exchange_rate', 'target_exchange_rate', 'paid_amount', 'received_amount'].forEach(function(fn) {
				if (snap[fn] !== undefined && snap[fn] !== null && Math.abs(flt(frm.doc[fn]) - flt(snap[fn])) > 0.0001) {
					frm.set_value(fn, snap[fn]);
				}
			});
		};
		if (typeof frappe.after_ajax === 'function') {
			frappe.after_ajax(function() {
				setTimeout(restore, 50);
			});
		} else {
			setTimeout(restore, 250);
		}
	}

	// Attach Payment Entry triggers
	frappe.ui.form.on('Payment Entry', {
		party: function(frm) {
			handle_party_selection(frm, (frm.doc.party_type || '').toLowerCase(), frm.doc.party);
		},
		party_type: function(frm) {
			if (frm.doc.party) {
				handle_party_selection(frm, (frm.doc.party_type || '').toLowerCase(), frm.doc.party);
			}
		},
		paid_from: function(frm) {
			preserve_mirrored_pe_locked_values(frm, 'paid_from');
		},
		paid_to: function(frm) {
			preserve_mirrored_pe_locked_values(frm, 'paid_to');
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

