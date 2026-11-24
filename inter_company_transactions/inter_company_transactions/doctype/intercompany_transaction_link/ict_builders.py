# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from .ict_accounting_builders import (
	create_journal_entry,
	create_journal_entry_from_lcv,
	create_payment_entry,
	create_stock_entry,
)
from .ict_currency import (
	_preserve_intercompany_currency_after_defaults,
	resolve_intercompany_currency_and_rate,
)
from .ict_pricing import resolve_intercompany_target_item
from .ict_utils import get_default_cost_center, get_default_warehouse


def create_corresponding_document(source_doc, mapping_info, direction, settings=None):
	"""Route document creation by target DocType."""
	mapping = mapping_info["mapping"]
	linked_company = mapping_info["linked_company"]
	target_doctype = mapping_info.get("target_doctype")

	if target_doctype == "Sales Invoice":
		return create_sales_invoice(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Purchase Invoice":
		return create_purchase_invoice(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Sales Order":
		return create_sales_order(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Purchase Order":
		return create_purchase_order(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Delivery Note":
		return create_delivery_note(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Purchase Receipt":
		return create_purchase_receipt(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Stock Entry":
		return create_stock_entry(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Journal Entry":
		if getattr(source_doc, "doctype", "") == "Landed Cost Voucher":
			return create_journal_entry_from_lcv(source_doc, mapping, linked_company, direction)
		return create_journal_entry(source_doc, mapping, linked_company, direction)
	elif target_doctype == "Payment Entry":
		return create_payment_entry(source_doc, mapping, linked_company, direction)
	elif target_doctype == "Quotation":
		return create_quotation(source_doc, mapping, linked_company, direction, settings=settings)
	elif target_doctype == "Supplier Quotation":
		return create_supplier_quotation(source_doc, mapping, linked_company, direction, settings=settings)

	return None


def _resolve_party_control_account(party_type, party, company, target_currency, default_fieldname):
	"""Resolve Party Account matching target_currency first, then any Party Account, then Company default."""
	if party and company and hasattr(frappe, "db") and frappe.db:
		pa_rows = frappe.get_all(
			"Party Account",
			filters={"parenttype": party_type, "parent": party, "company": company},
			fields=["account"],
		)
		for row in pa_rows or []:
			acct = row.get("account")
			if acct and target_currency:
				acc_ccy = frappe.db.get_value("Account", acct, "account_currency")
				if acc_ccy == target_currency:
					return acct
		if pa_rows and pa_rows[0].get("account"):
			return pa_rows[0].get("account")
	return frappe.db.get_value("Company", company, default_fieldname) if company else None


def create_sales_invoice(source_doc, mapping, linked_company, direction, settings=None):
	"""Create Sales Invoice from Purchase Invoice or other source."""
	si = frappe.new_doc("Sales Invoice")

	if direction == "other_to_main":
		si.company = mapping.main_company
		si.customer = linked_company.main_company_customer
	else:
		si.company = linked_company.company
		si.customer = linked_company.other_company_customer

	if not si.customer:
		frappe.throw(_("Customer not mapped for company {0}").format(si.company))

	si.posting_date = getattr(source_doc, "posting_date", None) or nowdate()
	si.due_date = getattr(source_doc, "due_date", None) or si.posting_date
	si.po_no = getattr(source_doc, "bill_no", None) or source_doc.name

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		source_doc, si.company, party_type="Customer", party_name=si.customer, date=si.posting_date
	)
	si.currency = target_currency
	si.conversion_rate = conversion_rate

	warehouse = get_default_warehouse(si.company)
	if not warehouse:
		warehouse = frappe.db.get_value("Warehouse", {"company": si.company, "is_group": 0}, "name")

	debit_to = _resolve_party_control_account(
		"Customer", si.customer, si.company, target_currency, "default_receivable_account"
	)
	if debit_to:
		si.debit_to = debit_to

	default_income_account = frappe.db.get_value("Company", si.company, "default_income_account")
	default_cost_center = get_default_cost_center(si.company)

	for item in getattr(source_doc, "items", []):
		target_item = resolve_intercompany_target_item(
			item,
			si.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=source_doc.company,
			transaction_date=si.posting_date,
		)
		item_row = {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"cost_center": default_cost_center,
		}
		if warehouse:
			item_row["warehouse"] = warehouse
		if default_income_account:
			item_row["income_account"] = default_income_account
		si.append("items", item_row)

	si.intercompany_linked_doc_doctype = source_doc.doctype
	si.intercompany_linked_doc_name = source_doc.name
	si.intercompany_linked_company = source_doc.company
	si.intercompany_target_company = source_doc.company

	si.flags.ignore_permissions = True
	si.flags.ignore_mandatory = True
	si.flags.ignore_account_permission = True
	si.flags.ignore_validate = True
	si.flags.ignore_links = True
	si.flags.ignore_pricing_rule = True
	si.flags.ignore_party_validation = True

	try:
		si.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(si, target_currency, conversion_rate, si.posting_date, source_doc=source_doc)

	si.docstatus = 0
	return si


def create_purchase_invoice(source_doc, mapping, linked_company, direction, settings=None):
	"""Create Purchase Invoice from Sales Invoice or other source."""
	pi = frappe.new_doc("Purchase Invoice")

	if direction == "other_to_main":
		pi.company = mapping.main_company
		pi.supplier = linked_company.main_company_supplier
	else:
		pi.company = linked_company.company
		pi.supplier = linked_company.other_company_supplier

	if not pi.supplier:
		frappe.throw(_("Supplier not mapped for company {0}").format(pi.company))

	pi.posting_date = getattr(source_doc, "posting_date", None) or nowdate()
	pi.due_date = getattr(source_doc, "due_date", None) or pi.posting_date
	pi.bill_no = source_doc.name

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		source_doc, pi.company, party_type="Supplier", party_name=pi.supplier, date=pi.posting_date
	)
	pi.currency = target_currency
	pi.conversion_rate = conversion_rate

	warehouse = get_default_warehouse(pi.company)
	if not warehouse:
		warehouse = frappe.db.get_value("Warehouse", {"company": pi.company, "is_group": 0}, "name")

	credit_to = _resolve_party_control_account(
		"Supplier", pi.supplier, pi.company, target_currency, "default_payable_account"
	)
	if credit_to:
		pi.credit_to = credit_to

	default_expense_account = frappe.db.get_value("Company", pi.company, "default_expense_account")
	default_cost_center = get_default_cost_center(pi.company)

	for item in getattr(source_doc, "items", []):
		target_item = resolve_intercompany_target_item(
			item,
			pi.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=source_doc.company,
			transaction_date=pi.posting_date,
		)
		item_row = {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"cost_center": default_cost_center,
		}
		if warehouse:
			item_row["warehouse"] = warehouse
		if default_expense_account:
			item_row["expense_account"] = default_expense_account
		pi.append("items", item_row)

	pi.intercompany_linked_doc_doctype = source_doc.doctype
	pi.intercompany_linked_doc_name = source_doc.name
	pi.intercompany_linked_company = source_doc.company
	pi.intercompany_target_company = source_doc.company

	pi.flags.ignore_permissions = True
	pi.flags.ignore_mandatory = True
	pi.flags.ignore_account_permission = True
	pi.flags.ignore_validate = True
	pi.flags.ignore_links = True
	pi.flags.ignore_pricing_rule = True
	pi.flags.ignore_party_validation = True

	try:
		pi.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(pi, target_currency, conversion_rate, pi.posting_date, source_doc=source_doc)

	pi.docstatus = 0
	return pi


def create_purchase_order(sales_order, mapping, linked_company, direction, settings=None):
	"""Create Purchase Order from Sales Order or Material Request."""
	po = frappe.new_doc("Purchase Order")

	if direction == "other_to_main":
		po.company = mapping.main_company
		po.supplier = linked_company.main_company_supplier
	else:
		po.company = linked_company.company
		po.supplier = linked_company.other_company_supplier

	if not po.supplier:
		frappe.throw(_("Supplier not found for company {0}").format(po.company))

	po.transaction_date = getattr(sales_order, "transaction_date", None) or nowdate()
	po.schedule_date = getattr(sales_order, "delivery_date", None) or getattr(sales_order, "schedule_date", None) or nowdate()
	po.intercompany_target_company = sales_order.company

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		sales_order, po.company, party_type="Supplier", party_name=po.supplier, date=po.transaction_date
	)
	po.currency = target_currency
	po.conversion_rate = conversion_rate

	warehouse = get_default_warehouse(po.company)
	if not warehouse:
		warehouse = frappe.db.get_value("Warehouse", {"company": po.company, "is_group": 0}, "name")

	for item in sales_order.items:
		target_item = resolve_intercompany_target_item(
			item,
			po.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=sales_order.company,
			transaction_date=po.transaction_date,
		)
		po.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"warehouse": warehouse,
			"schedule_date": getattr(item, "delivery_date", None) or getattr(item, "schedule_date", None) or po.schedule_date,
		})

	po.flags.ignore_permissions = True
	po.flags.ignore_mandatory = True
	po.flags.ignore_account_permission = True
	po.flags.ignore_validate = True
	po.flags.ignore_links = True
	po.flags.ignore_pricing_rule = True
	po.flags.ignore_party_validation = True

	try:
		po.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(po, target_currency, conversion_rate, po.transaction_date, source_doc=sales_order)

	po.docstatus = 0
	return po


def create_sales_order(purchase_order, mapping, linked_company, direction, settings=None):
	"""Create Sales Order from Purchase Order or Material Request."""
	so = frappe.new_doc("Sales Order")

	if direction == "other_to_main":
		so.company = mapping.main_company
		so.customer = linked_company.main_company_customer
	else:
		so.company = linked_company.company
		so.customer = linked_company.other_company_customer

	if not so.customer:
		frappe.throw(_("Customer not found for company {0}").format(so.company))

	so.transaction_date = getattr(purchase_order, "transaction_date", None) or nowdate()
	so.delivery_date = getattr(purchase_order, "schedule_date", None) or nowdate()
	so.intercompany_target_company = purchase_order.company

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		purchase_order, so.company, party_type="Customer", party_name=so.customer, date=so.transaction_date
	)
	so.currency = target_currency
	so.conversion_rate = conversion_rate

	warehouse = get_default_warehouse(so.company)
	if not warehouse:
		warehouse = frappe.db.get_value("Warehouse", {"company": so.company, "is_group": 0}, "name")

	for item in purchase_order.items:
		target_item = resolve_intercompany_target_item(
			item,
			so.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=purchase_order.company,
			transaction_date=so.transaction_date,
		)
		so.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"warehouse": warehouse,
			"delivery_date": getattr(item, "schedule_date", None) or so.delivery_date,
		})

	so.flags.ignore_permissions = True
	so.flags.ignore_mandatory = True
	so.flags.ignore_account_permission = True
	so.flags.ignore_validate = True
	so.flags.ignore_links = True
	so.flags.ignore_pricing_rule = True
	so.flags.ignore_party_validation = True

	try:
		so.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(so, target_currency, conversion_rate, so.transaction_date, source_doc=purchase_order)

	so.docstatus = 0
	return so


def create_delivery_note(purchase_receipt, mapping, linked_company, direction, settings=None):
	"""Create Delivery Note from Purchase Receipt."""
	dn = frappe.new_doc("Delivery Note")

	if direction == "other_to_main":
		dn.company = mapping.main_company
		dn.customer = linked_company.main_company_customer
	else:
		dn.company = linked_company.company
		dn.customer = linked_company.other_company_customer

	if not dn.customer:
		frappe.throw(_("Customer not found for company {0}").format(dn.company))

	dn.posting_date = purchase_receipt.posting_date
	dn.posting_time = getattr(purchase_receipt, "posting_time", None)
	dn.set_posting_time = getattr(purchase_receipt, "set_posting_time", 0)

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		purchase_receipt, dn.company, party_type="Customer", party_name=dn.customer, date=dn.posting_date
	)
	dn.currency = target_currency
	dn.conversion_rate = conversion_rate

	target_warehouse = get_default_warehouse(dn.company)
	if not target_warehouse:
		target_warehouse = frappe.db.get_value("Warehouse", {"company": dn.company, "is_group": 0}, "name")

	for item in purchase_receipt.items:
		target_item = resolve_intercompany_target_item(
			item,
			dn.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=purchase_receipt.company,
			transaction_date=dn.posting_date,
		)
		dn.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"warehouse": target_warehouse,
			"against_sales_order": None,
			"against_sales_invoice": None,
		})

	dn.intercompany_linked_doc_doctype = purchase_receipt.doctype
	dn.intercompany_linked_doc_name = purchase_receipt.name
	dn.intercompany_linked_company = purchase_receipt.company
	dn.intercompany_target_company = purchase_receipt.company

	dn.flags.ignore_permissions = True
	dn.flags.ignore_mandatory = True
	dn.flags.ignore_account_permission = True
	dn.flags.ignore_validate = True
	dn.flags.ignore_links = True
	dn.flags.ignore_pricing_rule = True
	dn.flags.ignore_party_validation = True

	try:
		dn.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(dn, target_currency, conversion_rate, dn.posting_date, source_doc=purchase_receipt)

	dn.docstatus = 0
	return dn


def create_purchase_receipt(delivery_note, mapping, linked_company, direction, settings=None):
	"""Create Purchase Receipt from Delivery Note."""
	pr = frappe.new_doc("Purchase Receipt")

	if direction == "other_to_main":
		pr.company = mapping.main_company
		pr.supplier = linked_company.main_company_supplier
	else:
		pr.company = linked_company.company
		pr.supplier = linked_company.other_company_supplier

	if not pr.supplier:
		frappe.throw(_("Supplier not found for company {0}").format(pr.company))

	pr.posting_date = delivery_note.posting_date
	pr.posting_time = getattr(delivery_note, "posting_time", None)
	pr.set_posting_time = getattr(delivery_note, "set_posting_time", 0)

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		delivery_note, pr.company, party_type="Supplier", party_name=pr.supplier, date=pr.posting_date
	)
	pr.currency = target_currency
	pr.conversion_rate = conversion_rate

	target_warehouse = get_default_warehouse(pr.company)
	if not target_warehouse:
		target_warehouse = frappe.db.get_value("Warehouse", {"company": pr.company, "is_group": 0}, "name")

	for item in delivery_note.items:
		target_item = resolve_intercompany_target_item(
			item,
			pr.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=delivery_note.company,
			transaction_date=pr.posting_date,
		)
		pr.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
			"warehouse": target_warehouse,
			"purchase_order": None,
			"purchase_invoice": None,
		})

	pr.intercompany_linked_doc_doctype = delivery_note.doctype
	pr.intercompany_linked_doc_name = delivery_note.name
	pr.intercompany_linked_company = delivery_note.company
	pr.intercompany_target_company = delivery_note.company

	pr.flags.ignore_permissions = True
	pr.flags.ignore_mandatory = True
	pr.flags.ignore_account_permission = True
	pr.flags.ignore_validate = True
	pr.flags.ignore_links = True
	pr.flags.ignore_pricing_rule = True
	pr.flags.ignore_party_validation = True

	try:
		pr.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(pr, target_currency, conversion_rate, pr.posting_date, source_doc=delivery_note)

	pr.docstatus = 0
	return pr


def create_quotation(supplier_quotation, mapping, linked_company, direction, settings=None):
	"""Create Quotation from Supplier Quotation."""
	q = frappe.new_doc("Quotation")
	if direction == "other_to_main":
		q.company = mapping.main_company
		q.party_name = linked_company.main_company_customer
	else:
		q.company = linked_company.company
		q.party_name = linked_company.other_company_customer

	q.quotation_to = "Customer"
	q.transaction_date = getattr(supplier_quotation, "transaction_date", None) or nowdate()

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		supplier_quotation, q.company, party_type="Customer", party_name=q.party_name, date=q.transaction_date
	)
	q.currency = target_currency
	q.conversion_rate = conversion_rate

	for item in supplier_quotation.items:
		target_item = resolve_intercompany_target_item(
			item,
			q.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=supplier_quotation.company,
			transaction_date=q.transaction_date,
		)
		q.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": target_item["rate"],
		})

	q.intercompany_linked_doc_doctype = supplier_quotation.doctype
	q.intercompany_linked_doc_name = supplier_quotation.name
	q.intercompany_linked_company = supplier_quotation.company
	q.intercompany_target_company = supplier_quotation.company

	q.flags.ignore_permissions = True
	q.flags.ignore_mandatory = True
	q.flags.ignore_account_permission = True
	q.flags.ignore_validate = True
	q.flags.ignore_links = True
	q.flags.ignore_pricing_rule = True
	q.flags.ignore_party_validation = True

	try:
		q.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(q, target_currency, conversion_rate, q.transaction_date, source_doc=supplier_quotation)

	q.docstatus = 0
	return q


def create_supplier_quotation(quotation, mapping, linked_company, direction, settings=None):
	"""Create Supplier Quotation from Quotation or Request for Quotation."""
	sq = frappe.new_doc("Supplier Quotation")
	if direction == "other_to_main":
		sq.company = mapping.main_company
		sq.supplier = linked_company.main_company_supplier
	else:
		sq.company = linked_company.company
		sq.supplier = linked_company.other_company_supplier

	sq.transaction_date = getattr(quotation, "transaction_date", None) or nowdate()

	target_currency, conversion_rate, rate_factor = resolve_intercompany_currency_and_rate(
		quotation, sq.company, party_type="Supplier", party_name=sq.supplier, date=sq.transaction_date
	)
	sq.currency = target_currency
	sq.conversion_rate = conversion_rate

	for item in quotation.items:
		target_item = resolve_intercompany_target_item(
			item,
			sq.company,
			mapping=mapping,
			rate_factor=rate_factor,
			settings=settings,
			source_company=quotation.company,
			transaction_date=sq.transaction_date,
		)
		item_rate = flt(target_item["rate"])
		if quotation.doctype == "Request for Quotation" and item_rate <= 0 and hasattr(frappe, "db") and frappe.db:
			from .ict_currency import get_intercompany_exchange_rate
			from .ict_pricing import _get_item_valuation_rate

			t_code = target_item["item_code"]
			if t_code and frappe.db.exists("DocType", "Item Price"):
				ip_row = frappe.db.get_value(
					"Item Price",
					{"item_code": t_code, "buying": 1},
					["price_list_rate", "currency"],
					as_dict=True,
				)
				if ip_row and flt(ip_row.get("price_list_rate")) > 0:
					ip_fx = (
						get_intercompany_exchange_rate(ip_row.get("currency"), target_currency, sq.transaction_date)
						if ip_row.get("currency") and target_currency and ip_row.get("currency") != target_currency
						else 1.0
					)
					item_rate = flt(ip_row.get("price_list_rate")) * flt(ip_fx or 1.0)
			if item_rate <= 0 and t_code:
				std_rate = flt(frappe.db.get_value("Item", t_code, "standard_rate"))
				if std_rate > 0:
					item_rate = std_rate * flt(rate_factor or 1.0)
				else:
					val_rate = _get_item_valuation_rate(getattr(item, "item_code", None) or t_code, quotation.company)
					if val_rate > 0:
						item_rate = flt(val_rate) * flt(rate_factor or 1.0)

		sq.append("items", {
			"item_code": target_item["item_code"],
			"item_name": target_item["item_name"],
			"description": target_item["description"],
			"qty": target_item["qty"],
			"uom": target_item["uom"],
			"rate": item_rate,
		})

	sq.intercompany_linked_doc_doctype = quotation.doctype
	sq.intercompany_linked_doc_name = quotation.name
	sq.intercompany_linked_company = quotation.company
	sq.intercompany_target_company = quotation.company

	sq.flags.ignore_permissions = True
	sq.flags.ignore_mandatory = True
	sq.flags.ignore_account_permission = True
	sq.flags.ignore_validate = True
	sq.flags.ignore_links = True
	sq.flags.ignore_pricing_rule = True
	sq.flags.ignore_party_validation = True

	try:
		sq.set_missing_values(for_validate=True)
	except Exception:
		pass
	_preserve_intercompany_currency_after_defaults(sq, target_currency, conversion_rate, sq.transaction_date, source_doc=quotation)

	sq.docstatus = 0
	return sq
