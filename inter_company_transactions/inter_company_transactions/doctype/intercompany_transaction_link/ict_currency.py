# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from .ict_utils import _facade_fn, _safe_flt


def _normalize_tx_date(transaction_date=None):
	"""Safely convert date/datetime/ISO/DD-MM-YYYY strings to YYYY-MM-DD."""
	if not transaction_date:
		return str(nowdate())
	try:
		return str(getdate(transaction_date))
	except Exception:
		for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d"):
			try:
				return datetime.strptime(str(transaction_date).strip()[:10], fmt).strftime("%Y-%m-%d")
			except Exception:
				continue
		return str(nowdate())


def lookup_intercompany_exchange_rate(from_currency, to_currency, transaction_date=None):
	"""
	Silently queries Currency Exchange in both forward and inverse (1 / rate) directions
	without triggering erpnext.setup.utils.get_exchange_rate msgprint popups.
	Returns float (9 decimals) or None if no Currency Exchange record exists.
	"""
	from_ccy = str(from_currency).strip().upper() if from_currency else ""
	to_ccy = str(to_currency).strip().upper() if to_currency else ""
	if not from_ccy or not to_ccy or from_ccy == to_ccy:
		return 1.0

	if not (hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Currency Exchange")):
		return None

	tx_date = _normalize_tx_date(transaction_date)

	try:
		fwd = frappe.get_all(
			"Currency Exchange",
			filters={
				"from_currency": from_ccy,
				"to_currency": to_ccy,
				"date": ["<=", tx_date],
			},
			fields=["exchange_rate"],
			order_by="date desc",
			limit=1,
		)
		if fwd and flt(fwd[0].get("exchange_rate")) > 0:
			return _safe_flt(fwd[0].get("exchange_rate"), 9)

		inv = frappe.get_all(
			"Currency Exchange",
			filters={
				"from_currency": to_ccy,
				"to_currency": from_ccy,
				"date": ["<=", tx_date],
			},
			fields=["exchange_rate"],
			order_by="date desc",
			limit=1,
		)
		if inv and flt(inv[0].get("exchange_rate")) > 0:
			return _safe_flt(1.0 / flt(inv[0].get("exchange_rate")), 9)

		fwd_any = frappe.get_all(
			"Currency Exchange",
			filters={"from_currency": from_ccy, "to_currency": to_ccy},
			fields=["exchange_rate"],
			order_by="date desc",
			limit=1,
		)
		if fwd_any and flt(fwd_any[0].get("exchange_rate")) > 0:
			return _safe_flt(fwd_any[0].get("exchange_rate"), 9)

		inv_any = frappe.get_all(
			"Currency Exchange",
			filters={"from_currency": to_ccy, "to_currency": from_ccy},
			fields=["exchange_rate"],
			order_by="date desc",
			limit=1,
		)
		if inv_any and flt(inv_any[0].get("exchange_rate")) > 0:
			return _safe_flt(1.0 / flt(inv_any[0].get("exchange_rate")), 9)
	except Exception as e:
		frappe.logger().warning(f"Currency Exchange lookup error ({from_ccy}->{to_ccy} on {tx_date}): {e!s}")

	try:
		if frappe.db.exists("DocType", "Currency Exchange Settings"):
			meta = frappe.get_meta("Currency Exchange Settings") if hasattr(frappe, "get_meta") else None
			should_query_ext = False
			if meta and hasattr(meta, "has_field") and meta.has_field("use_httpclient"):
				should_query_ext = bool(cint(frappe.db.get_single_value("Currency Exchange Settings", "use_httpclient")))
			elif meta and hasattr(meta, "has_field"):
				is_disabled = (
					bool(cint(frappe.db.get_single_value("Currency Exchange Settings", "disabled")))
					if meta.has_field("disabled")
					else False
				)
				has_provider = (
					bool(frappe.db.get_single_value("Currency Exchange Settings", "service_provider"))
					if meta.has_field("service_provider")
					else False
				)
				should_query_ext = (not is_disabled) and has_provider

			if should_query_ext:
				from erpnext.setup.utils import get_exchange_rate

				prev_mute = getattr(frappe.flags, "mute_messages", False)
				frappe.flags.mute_messages = True
				try:
					ext_rate = _safe_flt(get_exchange_rate(from_ccy, to_ccy, tx_date), 9)
					if ext_rate > 0 and ext_rate != 1.0:
						return ext_rate
				finally:
					frappe.flags.mute_messages = prev_mute
	except Exception:
		pass

	return None


def extract_document_exchange_rate(doc, from_currency, to_currency):
	"""
	Extracts an explicit exchange rate already specified on the source voucher itself
	(e.g., Journal Entry row exchange_rate=275 for USD row in PKR company, or SO/PO conversion_rate=275).
	Returns rounded float (9 decimals) if found, else None.
	"""
	if not doc or not from_currency or not to_currency:
		return None
	if from_currency == to_currency:
		return 1.0

	src_company = getattr(doc, "company", None) or (doc.get("company") if isinstance(doc, dict) else None)
	src_company_ccy = (
		frappe.db.get_value("Company", src_company, "default_currency")
		if src_company and hasattr(frappe, "db") and frappe.db
		else None
	)

	doc_ccy = getattr(doc, "currency", None) or (doc.get("currency") if isinstance(doc, dict) else None)
	conv_rate = flt(getattr(doc, "conversion_rate", 0) or (doc.get("conversion_rate", 0) if isinstance(doc, dict) else 0))
	if doc_ccy and src_company_ccy and doc_ccy != src_company_ccy and conv_rate > 0:
		if from_currency == doc_ccy and to_currency == src_company_ccy:
			return _safe_flt(conv_rate, 9)
		if from_currency == src_company_ccy and to_currency == doc_ccy:
			return _safe_flt(1.0 / conv_rate, 9)

	if (getattr(doc, "doctype", None) or (doc.get("doctype") if isinstance(doc, dict) else None)) == "Payment Entry":
		p_from_ccy = getattr(doc, "paid_from_account_currency", None)
		p_to_ccy = getattr(doc, "paid_to_account_currency", None)
		src_fx = flt(getattr(doc, "source_exchange_rate", 0))
		tgt_fx = flt(getattr(doc, "target_exchange_rate", 0))
		if p_from_ccy and src_company_ccy and p_from_ccy != src_company_ccy and src_fx > 0:
			if from_currency == p_from_ccy and to_currency == src_company_ccy:
				return _safe_flt(src_fx, 9)
			if from_currency == src_company_ccy and to_currency == p_from_ccy:
				return _safe_flt(1.0 / src_fx, 9)
		if p_to_ccy and src_company_ccy and p_to_ccy != src_company_ccy and tgt_fx > 0:
			if from_currency == p_to_ccy and to_currency == src_company_ccy:
				return _safe_flt(tgt_fx, 9)
			if from_currency == src_company_ccy and to_currency == p_to_ccy:
				return _safe_flt(1.0 / tgt_fx, 9)

	rows = getattr(doc, "accounts", None) or (doc.get("accounts") if isinstance(doc, dict) else None) or []
	for row in rows:
		r_ccy = getattr(row, "account_currency", None) or (row.get("account_currency") if isinstance(row, dict) else None)
		r_fx = flt(getattr(row, "exchange_rate", 0) or (row.get("exchange_rate", 0) if isinstance(row, dict) else 0))
		if r_ccy and src_company_ccy and r_ccy != src_company_ccy and r_fx > 0:
			if from_currency == r_ccy and to_currency == src_company_ccy:
				return _safe_flt(r_fx, 9)
			if from_currency == src_company_ccy and to_currency == r_ccy:
				return _safe_flt(1.0 / r_fx, 9)

	return None


def get_intercompany_exchange_rate(from_currency, to_currency, transaction_date=None, raise_if_missing=False):
	"""
	Safely resolve the exchange rate from `from_currency` to `to_currency`.
	Queries Currency Exchange in both directions cleanly without trigger msgprint spam.
	"""
	if not from_currency or not to_currency or from_currency == to_currency:
		return 1.0

	lookup_fn = _facade_fn("lookup_intercompany_exchange_rate", lookup_intercompany_exchange_rate)
	rate = lookup_fn(from_currency, to_currency, transaction_date)
	if rate and flt(rate) > 0:
		return _safe_flt(rate, 9)

	if raise_if_missing:
		frappe.throw(
			_(
				"Currency Exchange rate between <b>{0}</b> and <b>{1}</b> for date <b>{2}</b> is required "
				"so both intercompany ledgers stay 100% tallied. Please add the exchange rate first."
			).format(from_currency, to_currency, transaction_date or nowdate()),
			title=_("Exchange Rate Required"),
		)

	return 1.0


def check_intercompany_exchange_rate_impl(
	source_company,
	target_company,
	transaction_date=None,
	doc_currency=None,
	conversion_rate=None,
):
	"""Check whether an exchange rate is required and exists before saving a cross-currency voucher."""
	if not source_company or not target_company or source_company == target_company:
		return {"required": False, "has_rate": True}

	if not (hasattr(frappe, "db") and frappe.db):
		return {"required": False, "has_rate": True}

	src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
	tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
	if not src_ccy or not tgt_ccy or src_ccy == tgt_ccy:
		return {
			"required": False,
			"has_rate": True,
			"from_currency": src_ccy,
			"to_currency": tgt_ccy,
		}

	tx_date = _normalize_tx_date(transaction_date)
	lookup_fn = _facade_fn("lookup_intercompany_exchange_rate", lookup_intercompany_exchange_rate)
	if doc_currency == tgt_ccy and flt(conversion_rate) > 0:
		rate = _safe_flt(1.0 / flt(conversion_rate), 9)
	else:
		rate = lookup_fn(src_ccy, tgt_ccy, tx_date)

	doc_currency_rate = None
	if doc_currency and doc_currency != src_ccy:
		if flt(conversion_rate) > 0:
			doc_currency_rate = _safe_flt(conversion_rate, 9)
		else:
			doc_currency_rate = lookup_fn(doc_currency, src_ccy, tx_date)

	return {
		"required": True,
		"has_rate": bool(rate and flt(rate) > 0),
		"from_currency": src_ccy,
		"to_currency": tgt_ccy,
		"exchange_rate": _safe_flt(rate, 9) if rate else None,
		"inverse_rate": _safe_flt(1.0 / flt(rate), 9) if rate else None,
		"doc_currency": doc_currency,
		"doc_currency_rate": _safe_flt(doc_currency_rate, 9) if doc_currency_rate else None,
		"transaction_date": tx_date,
	}


def validate_stock_entry_same_currency(source_company, target_company):
	"""Restricts intercompany Stock Entry strictly to companies sharing the same default currency."""
	if not source_company or not target_company or source_company == target_company:
		return
	if not (hasattr(frappe, "db") and frappe.db):
		return

	src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
	tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
	if src_ccy and tgt_ccy and src_ccy != tgt_ccy:
		frappe.throw(
			_(
				"Inter-Company <b>Stock Entry</b> works for <b>Same-Currency companies only</b>.<br><br>"
				"<b>{0}</b> uses <b>{1}</b> while <b>{2}</b> uses <b>{3}</b>.<br><br>"
				"Because ERPNext Stock Entry has no currency or exchange rate field, please use "
				"<b>Delivery Note &rarr; Purchase Receipt</b> or <b>Sales Invoice &rarr; Purchase Invoice</b> "
				"for transfers between companies with different currencies."
			).format(source_company, src_ccy, target_company, tgt_ccy),
			title=_("Same-Currency Only for Stock Entry"),
		)


def check_stock_entry_same_currency_impl(source_company, target_company):
	"""Client-callable check confirming both companies share the same currency for Stock Entry."""
	if not source_company or not target_company or source_company == target_company:
		return {"allowed": True}
	if not (hasattr(frappe, "db") and frappe.db):
		return {"allowed": True}

	src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
	tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
	allowed = not (src_ccy and tgt_ccy and src_ccy != tgt_ccy)
	return {
		"allowed": allowed,
		"source_currency": src_ccy,
		"target_currency": tgt_ccy,
	}


def save_intercompany_currency_exchange_impl(from_currency, to_currency, exchange_rate, date=None):
	"""Saves a Currency Exchange record from the guided Exchange Rate modal dialog."""
	frappe.has_permission("Currency Exchange", "create", throw=True)
	rate = flt(exchange_rate)
	if rate <= 0:
		frappe.throw(_("Exchange rate must be greater than zero."))
	if not from_currency or not to_currency or from_currency == to_currency:
		frappe.throw(_("From Currency and To Currency must be different."))

	tx_date = _normalize_tx_date(date)
	existing = frappe.db.get_value(
		"Currency Exchange",
		{"date": tx_date, "from_currency": from_currency, "to_currency": to_currency},
		"name",
	)
	rounded_rate = _safe_flt(rate, 9)
	if existing:
		frappe.db.set_value("Currency Exchange", existing, "exchange_rate", rounded_rate)
		name = existing
	else:
		ce = frappe.get_doc({
			"doctype": "Currency Exchange",
			"date": tx_date,
			"from_currency": from_currency,
			"to_currency": to_currency,
			"exchange_rate": rounded_rate,
			"for_buying": 1,
			"for_selling": 1,
		})
		ce.insert(ignore_permissions=True)
		name = ce.name

	return {
		"success": True,
		"name": name,
		"from_currency": from_currency,
		"to_currency": to_currency,
		"exchange_rate": rounded_rate,
		"inverse_rate": _safe_flt(1.0 / rate, 9),
		"date": tx_date,
	}


def validate_intercompany_cross_currency_rate(doc):
	"""
	Blocks saving/submitting a source intercompany document across companies with different
	default currencies unless a valid exchange rate exists on the document OR in Currency Exchange.
	Guarantees Company A and Company B ledgers never silently fall back to 1.0.
	"""
	if not doc or not cint(doc.get("is_intercompany")):
		return
	if doc.get("intercompany_linked_doc_name"):
		return

	source_company = doc.get("company")
	target_company = doc.get("intercompany_target_company")
	if not source_company or not target_company or source_company == target_company:
		return
	if not (hasattr(frappe, "db") and frappe.db):
		return

	src_ccy = frappe.db.get_value("Company", source_company, "default_currency")
	tgt_ccy = frappe.db.get_value("Company", target_company, "default_currency")
	if not src_ccy or not tgt_ccy or src_ccy == tgt_ccy:
		return

	tx_date = getattr(doc, "posting_date", None) or getattr(doc, "transaction_date", None) or nowdate()
	doc_rate = extract_document_exchange_rate(doc, src_ccy, tgt_ccy)
	if doc_rate and flt(doc_rate) > 0:
		return

	lookup_fn = _facade_fn("lookup_intercompany_exchange_rate", lookup_intercompany_exchange_rate)
	db_rate = lookup_fn(src_ccy, tgt_ccy, tx_date)
	if db_rate and flt(db_rate) > 0:
		return

	frappe.throw(
		_(
			"Multi-Currency Exchange Rate Required: <b>{0}</b> ({1}) and <b>{2}</b> ({3}) use different currencies.<br><br>"
			"No exchange rate was found between <b>{1}</b> and <b>{3}</b> for <b>{4}</b>. "
			"Please enter the exchange rate on this voucher or "
			"<a href='/app/currency-exchange/new'><b>create a Currency Exchange record</b></a> "
			"so both company ledgers stay 100% tallied."
		).format(source_company, src_ccy, target_company, tgt_ccy, tx_date),
		title=_("Exchange Rate Required"),
	)


def resolve_intercompany_currency_and_rate(source_doc, target_company, party_type=None, party_name=None, date=None):
	"""
	Resolve target document currency, conversion_rate, and item rate factor.
	Honors any explicit exchange rate entered on `source_doc` first, then Currency Exchange (bidirectional).
	"""
	target_company_currency = frappe.db.get_value("Company", target_company, "default_currency")
	source_company = getattr(source_doc, "company", None)
	source_company_currency = frappe.db.get_value("Company", source_company, "default_currency") if source_company else None
	source_currency = getattr(source_doc, "currency", None) or source_company_currency or target_company_currency

	party_currency = None
	if party_type and party_name and frappe.db.exists(party_type, party_name):
		party_currency = frappe.db.get_value(party_type, party_name, "default_currency")

	if party_currency:
		target_currency = party_currency
	elif (
		source_company_currency
		and target_company_currency
		and source_company_currency != target_company_currency
		and source_currency == target_company_currency
	):
		target_currency = source_company_currency
	else:
		target_currency = source_currency or target_company_currency

	if target_currency == target_company_currency:
		conversion_rate = 1.0
	else:
		conversion_rate = (
			extract_document_exchange_rate(source_doc, target_currency, target_company_currency)
			or get_intercompany_exchange_rate(target_currency, target_company_currency, date)
		)
		if not conversion_rate or conversion_rate <= 0:
			conversion_rate = 1.0

	if source_currency == target_currency:
		rate_factor = 1.0
	else:
		rate_factor = (
			extract_document_exchange_rate(source_doc, source_currency, target_currency)
			or get_intercompany_exchange_rate(source_currency, target_currency, date)
		)
		if not rate_factor or rate_factor <= 0:
			rate_factor = 1.0

	return target_currency, (_safe_flt(conversion_rate, 9) or 1.0), (_safe_flt(rate_factor, 9) or 1.0)


def _preserve_intercompany_currency_after_defaults(target_doc, target_currency, conversion_rate, date=None, source_doc=None):
	"""Re-apply exact intercompany currency and conversion_rate after ERPNext set_missing_values."""
	if not target_doc:
		return
	conversion_rate = _safe_flt(conversion_rate, 9) or 1.0
	if hasattr(target_doc, "currency") or isinstance(target_doc, dict):
		target_doc.currency = target_currency
	if hasattr(target_doc, "conversion_rate") or isinstance(target_doc, dict):
		target_doc.conversion_rate = conversion_rate
	if hasattr(target_doc, "price_list_currency") and target_doc.company:
		tgt_comp_ccy = frappe.db.get_value("Company", target_doc.company, "default_currency")
		plc = getattr(target_doc, "price_list_currency", None)
		if not plc or plc == target_currency:
			target_doc.price_list_currency = target_currency
			target_doc.plc_conversion_rate = conversion_rate
		elif tgt_comp_ccy and plc != tgt_comp_ccy:
			if abs(flt(getattr(target_doc, "plc_conversion_rate", 0))) <= 0:
				target_doc.plc_conversion_rate = (
					extract_document_exchange_rate(source_doc, plc, tgt_comp_ccy)
					or get_intercompany_exchange_rate(plc, tgt_comp_ccy, date)
				)
		else:
			target_doc.plc_conversion_rate = 1.0
