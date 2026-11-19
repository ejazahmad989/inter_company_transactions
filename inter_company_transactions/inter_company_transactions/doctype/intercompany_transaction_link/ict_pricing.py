# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from .ict_utils import _facade_fn, _safe_flt


def ensure_item_exists(item_code, item_name=None, description=None, uom="Nos", item_group=None):
	"""Ensure an item exists in the database; auto-creates it cleanly if enabled."""
	if not item_code:
		return item_code

	if frappe.db.exists("Item", item_code):
		return item_code

	auto_create = True
	try:
		if frappe.db.exists("DocType", "Inter Company Settings"):
			settings = frappe.get_single("Inter Company Settings")
			if settings.auto_create_missing_items is not None:
				auto_create = bool(cint(settings.auto_create_missing_items))
	except Exception:
		pass

	if not auto_create:
		return item_code

	try:
		if not item_group or not frappe.db.exists("Item Group", item_group):
			item_group = (
				frappe.db.get_value("Item Group", {"is_group": 0}, "name")
				or frappe.db.get_value("Item Group", {}, "name")
				or "All Item Groups"
			)

		if not uom or not frappe.db.exists("UOM", uom):
			uom = frappe.db.get_value("UOM", {}, "name") or "Nos"

		item_doc = frappe.get_doc({
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_name or item_code,
			"description": description or item_name or item_code,
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 1,
			"include_item_in_manufacturing": 0,
		})
		item_doc.flags.ignore_permissions = True
		item_doc.flags.ignore_mandatory = True
		item_doc.insert()
		return item_doc.name
	except Exception as e:
		try:
			frappe.log_error(f"Could not auto-create item {item_code}: {e}", "Intercompany Item Creation")
		except Exception:
			pass
		return item_code


def _get_item_valuation_rate(item_code, company=None):
	"""Fetch item valuation rate safely from Bin (company-filtered) or Item master."""
	if not item_code or not (hasattr(frappe, "db") and frappe.db):
		return 0.0
	try:
		if company and frappe.db.exists("DocType", "Bin"):
			bin_rate = frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate")
			if flt(bin_rate) > 0:
				return flt(bin_rate)
		item_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
		if flt(item_rate) > 0:
			return flt(item_rate)
	except Exception:
		pass
	return 0.0


def calculate_transfer_rate(
	item_doc,
	base_rate,
	target_company=None,
	settings=None,
	source_company=None,
	transaction_date=None,
):
	"""
	Compute the arm's-length intercompany transfer rate using:
	1. Active Transfer Pricing Policy (matching target_company, source_company, item_code/item_group, date range)
	2. Global Inter Company Settings (default_transfer_pricing_rule + markup_percentage)
	3. Fallback to base_rate
	"""
	rate = flt(base_rate or 0.0)
	item_code = item_doc.get("item_code") if isinstance(item_doc, dict) else getattr(item_doc, "item_code", None)
	item_group = item_doc.get("item_group") if isinstance(item_doc, dict) else getattr(item_doc, "item_group", None)
	if not item_group and item_code and hasattr(frappe, "db") and frappe.db:
		try:
			item_group = frappe.db.get_value("Item", item_code, "item_group")
		except Exception:
			item_group = None

	tx_date = getdate(transaction_date or nowdate())
	val_rate_fn = _facade_fn("_get_item_valuation_rate", _get_item_valuation_rate)

	if target_company and hasattr(frappe, "db") and frappe.db and frappe.db.exists("DocType", "Transfer Pricing Policy"):
		try:
			active_field = "is_active" if frappe.db.has_column("Transfer Pricing Policy", "is_active") else "enabled"
			policies = frappe.get_all(
				"Transfer Pricing Policy",
				filters={active_field: 1, "to_company": target_company},
				fields=[
					"name", "from_company", "to_company", "item_code", "item_group",
					"methodology", "markup_percentage", "fixed_rate",
					"effective_from", "effective_to",
				],
			)
			best_policy = None
			best_score = -1
			for pol in policies:
				if source_company and pol.get("from_company") and pol.get("from_company") != source_company:
					continue
				if pol.get("item_code") and pol.get("item_code") != item_code:
					continue
				if pol.get("item_group") and pol.get("item_group") != item_group:
					continue
				eff_from = pol.get("effective_from") or pol.get("valid_from")
				eff_to = pol.get("effective_to") or pol.get("valid_to")
				if eff_from and tx_date < getdate(eff_from):
					continue
				if eff_to and tx_date > getdate(eff_to):
					continue

				score = (4 if pol.get("item_code") else 0) + (2 if pol.get("item_group") else 0) + (1 if pol.get("from_company") else 0)
				if score > best_score:
					best_score = score
					best_policy = pol

			if best_policy:
				method = (best_policy.get("methodology") or best_policy.get("pricing_method") or "").strip()
				markup = flt(best_policy.get("markup_percentage") or 0.0)
				if method == "Fixed Transfer Rate":
					return flt(best_policy.get("fixed_rate") or rate)
				elif method == "Cost-Plus Markup %":
					cost_base = val_rate_fn(item_code, source_company) or rate
					return _safe_flt(cost_base * (1.0 + (markup / 100.0)), 4)
				elif method == "Resale Price Method":
					return _safe_flt(rate * (1.0 - (markup / 100.0)), 4)
				elif method == "Comparable Uncontrolled Price (CUP)":
					return _safe_flt(rate, 4)
		except Exception:
			pass

	if settings is not None:
		rule = (
			settings.get("default_transfer_pricing_rule")
			if isinstance(settings, dict)
			else getattr(settings, "default_transfer_pricing_rule", None)
		) or "Source Document Rate"
		markup = flt(
			settings.get("markup_percentage")
			if isinstance(settings, dict)
			else getattr(settings, "markup_percentage", 0.0)
		)
		if rule == "Source Document Rate":
			return flt(rate)
		elif rule == "Cost / Valuation Rate":
			val_rate = val_rate_fn(item_code, source_company)
			return flt(val_rate if val_rate > 0 else rate)
		elif rule == "Cost + Markup %":
			cost_base = val_rate_fn(item_code, source_company) or rate
			return _safe_flt(cost_base * (1.0 + (markup / 100.0)), 4)

	return flt(rate)


def resolve_intercompany_target_item(
	source_item,
	target_company,
	mapping=None,
	rate_factor=1.0,
	settings=None,
	source_company=None,
	transaction_date=None,
):
	"""
	Resolves item code, quantity, rate, and UOM for intercompany target document.
	Translates source SKU to target SKU using child table or standalone Intercompany Item Mapping.
	"""
	source_code = source_item.get("item_code") if isinstance(source_item, dict) else getattr(source_item, "item_code", None)
	source_name = source_item.get("item_name") if isinstance(source_item, dict) else getattr(source_item, "item_name", source_code)
	source_desc = source_item.get("description") if isinstance(source_item, dict) else getattr(source_item, "description", source_name)
	source_qty = flt(source_item.get("qty") if isinstance(source_item, dict) else getattr(source_item, "qty", 1))
	source_rate = flt(source_item.get("rate") if isinstance(source_item, dict) else getattr(source_item, "rate", 0))
	source_uom = source_item.get("uom") if isinstance(source_item, dict) else getattr(source_item, "uom", "Nos")

	target_code = None
	target_name = source_name
	target_desc = source_desc
	conversion_factor = 1.0

	if mapping and hasattr(mapping, "item_mappings"):
		for row in (mapping.get("item_mappings") or []):
			if row.source_item_code == source_code:
				if not row.target_company or row.target_company == target_company:
					target_code = row.target_item_code
					conversion_factor = flt(row.conversion_factor) or 1.0
					break

	if not target_code and frappe.db.exists("DocType", "Intercompany Item Mapping"):
		try:
			mapping_row = frappe.db.get_value(
				"Intercompany Item Mapping",
				{"source_item_code": source_code, "target_company": target_company},
				["target_item_code", "conversion_factor"],
				as_dict=True,
			)
			if mapping_row:
				target_code = mapping_row.target_item_code
				conversion_factor = flt(mapping_row.conversion_factor) or 1.0
		except Exception:
			pass

	if not target_code:
		target_code = source_code
		conversion_factor = 1.0

	if target_code:
		ensure_item_exists(target_code, item_name=target_name, description=target_desc, uom=source_uom)

	effective_source_rate = calculate_transfer_rate(
		source_item,
		source_rate,
		target_company=target_company,
		settings=settings,
		source_company=source_company,
		transaction_date=transaction_date,
	)

	target_qty = source_qty * (conversion_factor if conversion_factor != 0 else 1.0)
	unit_rate = (effective_source_rate * flt(rate_factor)) / (conversion_factor if conversion_factor != 0 else 1.0)

	item_info = frappe.db.get_value("Item", target_code, ["item_name", "stock_uom", "description"], as_dict=True) if target_code else None
	if item_info:
		target_name = item_info.item_name or target_name
		target_desc = item_info.description or target_desc
		target_uom = item_info.stock_uom if conversion_factor != 1.0 else (source_uom or item_info.stock_uom)
	else:
		target_uom = source_uom

	return {
		"item_code": target_code,
		"item_name": target_name,
		"description": target_desc,
		"qty": target_qty,
		"uom": target_uom,
		"rate": unit_rate,
		"conversion_factor": conversion_factor,
	}
