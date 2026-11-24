# Copyright (c) 2024-2026, Ejaz Tech and contributors
# For license information, please see license.txt

import importlib
import sys

import frappe
from frappe import _
from frappe.model.document import Document

_pkg = __package__
ict_accounting_builders = importlib.import_module(f"{_pkg}.ict_accounting_builders")
ict_api = importlib.import_module(f"{_pkg}.ict_api")
ict_builders = importlib.import_module(f"{_pkg}.ict_builders")
ict_currency = importlib.import_module(f"{_pkg}.ict_currency")
ict_lifecycle = importlib.import_module(f"{_pkg}.ict_lifecycle")
ict_pricing = importlib.import_module(f"{_pkg}.ict_pricing")
ict_utils = importlib.import_module(f"{_pkg}.ict_utils")
ict_validation = importlib.import_module(f"{_pkg}.ict_validation")

_EXPORT_MAP = (
	(
		ict_accounting_builders,
		(
			"_build_je_row",
			"_has_row_field",
			"_precalculate_mirrored_doc_totals",
			"_set_row_value",
			"create_journal_entry",
			"create_journal_entry_from_lcv",
			"create_payment_entry",
			"create_stock_entry",
		),
	),
	(
		ict_api,
		(
			"_SUPPORTED_INTERCOMPANY_DOCTYPES",
			"bulk_create_linked_documents_impl",
			"delete_mirrored_draft_impl",
			"download_user_guide_pdf_impl",
			"get_company_currencies_impl",
			"get_intercompany_balance",
			"get_intercompany_dashboard_data_impl",
			"get_linked_counterpart_for_form_impl",
			"get_party_target_company_impl",
			"intercompany_account_query_impl",
			"intercompany_party_query_impl",
			"reconcile_intercompany_accounts_impl",
			"scan_linked_company_defaults_impl",
			"trigger_manual_intercompany_sync_impl",
			"unlink_mirrored_document_impl",
		),
	),
	(
		ict_builders,
		(
			"_resolve_party_control_account",
			"create_corresponding_document",
			"create_delivery_note",
			"create_purchase_invoice",
			"create_purchase_order",
			"create_purchase_receipt",
			"create_quotation",
			"create_sales_invoice",
			"create_sales_order",
			"create_supplier_quotation",
		),
	),
	(
		ict_currency,
		(
			"_normalize_tx_date",
			"_preserve_intercompany_currency_after_defaults",
			"check_intercompany_exchange_rate_impl",
			"check_stock_entry_same_currency_impl",
			"extract_document_exchange_rate",
			"get_intercompany_exchange_rate",
			"lookup_intercompany_exchange_rate",
			"resolve_intercompany_currency_and_rate",
			"save_intercompany_currency_exchange_impl",
			"validate_intercompany_cross_currency_rate",
			"validate_stock_entry_same_currency",
		),
	),
	(
		ict_lifecycle,
		(
			"_clear_mirrored_link_markers",
			"_execute_linked_documents",
			"cancel_linked_documents",
			"check_active_downstream_transactions",
			"cleanup_intercompany_links_on_trash",
			"create_document_reference",
			"create_linked_documents",
			"find_applicable_mappings",
			"get_linked_counterpart_documents",
			"resolve_target_doctype",
			"validate_intercompany_cancellation",
			"validate_intercompany_items",
			"validate_required_parties",
		),
	),
	(
		ict_pricing,
		(
			"_get_item_valuation_rate",
			"calculate_transfer_rate",
			"ensure_item_exists",
			"resolve_intercompany_target_item",
		),
	),
	(
		ict_utils,
		(
			"_get_company_abbr_token",
			"_get_intercompany_settings",
			"_is_corrupted_or_invalid_eval_expr",
			"_log_local_mirror_error",
			"_safe_flt",
			"_sanitize_intercompany_stock_entry_custom_fields",
			"backfill_sister_company_names",
			"find_existing_clearing_account",
			"fix_legacy_custom_fields",
			"get_default_cost_center",
			"get_default_warehouse",
			"get_intercompany_warehouse",
			"get_mapped_account",
			"get_or_create_ict_parent_group",
			"get_or_create_intercompany_clearing_account",
			"get_or_create_intercompany_warehouse",
			"get_parent_clearing_account",
			"sanitize_intercompany_stock_entry",
		),
	),
	(
		ict_validation,
		(
			"auto_detect_intercompany_party",
			"get_intercompany_party_map_impl",
			"resolve_party_target_company",
			"validate_intercompany_document",
			"validate_locked_mirrored_fields",
		),
	),
)

_this_module = sys.modules[__name__]
for _submod, _attrs in _EXPORT_MAP:
	for _attr in _attrs:
		setattr(_this_module, _attr, getattr(_submod, _attr))


class IntercompanyTransactionLink(Document):
	def autoname(self):
		self.set_sister_company()
		sister = getattr(self, "sister_company", None) or self.get_sister_company_name()
		if self.main_company and sister:
			base = f"{self.main_company} - {sister}"[:130]
			name = base
			count = 1
			while frappe.db.exists("Intercompany Transaction Link", name):
				name = f"{base} ({count})"
				count += 1
			self.name = name
		else:
			from frappe.model.naming import set_new_name

			set_new_name(self)

	def before_insert(self):
		self.set_sister_company()

	def before_save(self):
		self.set_sister_company()

	def onload(self):
		if not getattr(self, "sister_company", None) and self.get("linked_companies"):
			self.set_sister_company()

	def on_update(self):
		sister = self.get_sister_company_name()
		if sister and getattr(self, "sister_company", None) != sister:
			self.db_set("sister_company", sister, update_modified=False)
		if callable(getattr(frappe, "cache", None)):
			try:
				frappe.cache().delete_value("ict_intercompany_party_map")
			except Exception:
				pass

	def on_trash(self):
		if callable(getattr(frappe, "cache", None)):
			try:
				frappe.cache().delete_value("ict_intercompany_party_map")
			except Exception:
				pass

	def get_sister_company_name(self):
		"""Extract sister company name(s) from linked_companies child table."""
		companies = []
		for d in (self.get("linked_companies") or []):
			comp = getattr(d, "company", None) or (d.get("company") if isinstance(d, dict) else None)
			if comp and comp not in companies:
				companies.append(comp)
		return ", ".join(companies)

	def set_sister_company(self):
		"""Auto-populate sister_company field from child table."""
		sister = self.get_sister_company_name()
		if sister:
			self.sister_company = sister
		elif not getattr(self, "sister_company", None):
			self.sister_company = ""

	def validate(self):
		self.set_sister_company()
		self.validate_companies()
		self.validate_parties()
		self.validate_cross_currency_warehouses()
		self.validate_transaction_types_child_table()

	def validate_companies(self):
		"""Ensure main company and linked companies are different."""
		linked_companies = [d.company for d in self.linked_companies if d.company]
		if self.main_company in linked_companies:
			frappe.throw(_("Main Company cannot be in Linked Companies"))

		if len(linked_companies) != len(set(linked_companies)):
			frappe.throw(_("Duplicate companies found in Linked Companies"))

	def validate_cross_currency_warehouses(self):
		"""Clear transit warehouse fields when main and linked company currencies differ."""
		if not self.main_company or not (hasattr(frappe, "db") and frappe.db):
			return
		main_currency = frappe.db.get_value("Company", self.main_company, "default_currency")
		if not main_currency:
			return
		for linked_company in (self.get("linked_companies") or []):
			other_company = getattr(linked_company, "company", None)
			if not other_company:
				continue
			other_currency = frappe.db.get_value("Company", other_company, "default_currency")
			if other_currency and other_currency != main_currency:
				if getattr(linked_company, "main_company_warehouse", None):
					linked_company.main_company_warehouse = None
				if getattr(linked_company, "other_company_warehouse", None):
					linked_company.other_company_warehouse = None

	def validate_parties(self):
		"""Validate that both TMP accounts are present and customers/suppliers are symmetrically paired."""
		for linked_company in (self.get("linked_companies") or []):
			comp_label = linked_company.company or _("Linked Company")

			if not getattr(linked_company, "main_company_account", None) or not getattr(linked_company, "other_company_account", None):
				frappe.throw(
					_("Both Main Company Account and Other Company Account (TMP clearing accounts) are required for {0}.").format(
						comp_label
					)
				)

			if getattr(linked_company, "main_company_customer", None) and not getattr(linked_company, "other_company_customer", None):
				frappe.throw(
					_("Other Company Customer is required when Main Company Customer is set for {0}.").format(
						comp_label
					)
				)

			if getattr(linked_company, "other_company_customer", None) and not getattr(linked_company, "main_company_customer", None):
				frappe.throw(
					_("Main Company Customer is required when Other Company Customer is set for {0}.").format(
						comp_label
					)
				)

			if getattr(linked_company, "main_company_supplier", None) and not getattr(linked_company, "other_company_supplier", None):
				frappe.throw(
					_("Other Company Supplier is required when Main Company Supplier is set for {0}.").format(
						comp_label
					)
				)

			if getattr(linked_company, "other_company_supplier", None) and not getattr(linked_company, "main_company_supplier", None):
				frappe.throw(
					_("Main Company Supplier is required when Other Company Supplier is set for {0}.").format(
						comp_label
					)
				)

	def validate_transaction_types_child_table(self):
		"""Auto-populate or fix target_type and direction for any child row."""
		default_targets = {
			"Sales Order": "Purchase Order",
			"Purchase Order": "Sales Order",
			"Sales Invoice": "Purchase Invoice",
			"Purchase Invoice": "Sales Invoice",
			"Delivery Note": "Purchase Receipt",
			"Purchase Receipt": "Delivery Note",
			"Stock Entry": "Stock Entry",
			"Journal Entry": "Journal Entry",
			"Payment Entry": "Payment Entry",
			"Quotation": "Supplier Quotation",
			"Supplier Quotation": "Quotation",
			"Material Request": "Purchase Order",
			"Request for Quotation": "Supplier Quotation",
			"Subcontracting Order": "Purchase Order",
			"Landed Cost Voucher": "Journal Entry",
		}
		for row in (self.get("transaction_types") or []):
			if row.source_type and not row.target_type:
				row.target_type = default_targets.get(row.source_type, row.source_type)
			if not row.direction:
				row.direction = "Both"

	@frappe.whitelist()
	def populate_default_transaction_types(self):
		"""Populate standard supported intercompany transaction types."""
		self.check_permission("write")
		default_pairs = [
			("Sales Order", "Purchase Order", "Both"),
			("Purchase Order", "Sales Order", "Both"),
			("Sales Invoice", "Purchase Invoice", "Both"),
			("Purchase Invoice", "Sales Invoice", "Both"),
			("Delivery Note", "Purchase Receipt", "Both"),
			("Purchase Receipt", "Delivery Note", "Both"),
			("Quotation", "Supplier Quotation", "Both"),
			("Supplier Quotation", "Quotation", "Both"),
			("Material Request", "Sales Order", "Both"),
			("Material Request", "Purchase Order", "Both"),
			("Stock Entry", "Stock Entry", "Both"),
			("Journal Entry", "Journal Entry", "Both"),
			("Payment Entry", "Payment Entry", "Both"),
			("Request for Quotation", "Supplier Quotation", "Both"),
			("Landed Cost Voucher", "Journal Entry", "Both"),
		]

		existing = {
			(r.source_type, r.target_type)
			for r in (self.get("transaction_types") or [])
			if r.source_type and r.target_type
		}

		count = 0
		for src, tgt, direction in default_pairs:
			if (src, tgt) not in existing:
				self.append(
					"transaction_types",
					{
						"source_type": src,
						"target_type": tgt,
						"direction": direction,
					},
				)
				existing.add((src, tgt))
				count += 1

		if not self.is_new() and count > 0:
			self.save(ignore_permissions=True)

		return count

	@frappe.whitelist()
	def auto_create_intercompany_accounts(self):
		"""Scan Chart of Accounts and auto-provision Bank-typed TMP-<ABBR> Intercompany Clearing accounts."""
		self.check_permission("write")
		created_count = 0
		linked_count = 0

		for row in (self.get("linked_companies") or []):
			if not row.company:
				continue

			main_acc = row.main_company_account
			main_acc_type = (
				frappe.db.get_value("Account", main_acc, "account_type")
				if main_acc and hasattr(frappe, "db") and frappe.db
				else None
			)
			if not main_acc or main_acc_type not in ("Bank", "Cash"):
				acc = ict_utils.get_or_create_intercompany_clearing_account(self.main_company, row.company)
				if acc and acc != main_acc:
					row.main_company_account = acc
					created_count += 1
				elif acc:
					linked_count += 1
			else:
				linked_count += 1

			other_acc = row.other_company_account
			other_acc_type = (
				frappe.db.get_value("Account", other_acc, "account_type")
				if other_acc and hasattr(frappe, "db") and frappe.db
				else None
			)
			if not other_acc or other_acc_type not in ("Bank", "Cash"):
				acc = ict_utils.get_or_create_intercompany_clearing_account(row.company, self.main_company)
				if acc and acc != other_acc:
					row.other_company_account = acc
					created_count += 1
				elif acc:
					linked_count += 1
			else:
				linked_count += 1

		if not self.is_new() and created_count > 0:
			self.save(ignore_permissions=True)

		return {
			"created": created_count,
			"already_configured": linked_count,
			"message": _("Configured {0} Bank TMP clearing account(s) ({1} verified).").format(created_count, linked_count),
		}


@frappe.whitelist()
def scan_linked_company_defaults(main_company: str, other_company: str):
	frappe.has_permission("Intercompany Transaction Link", "read", throw=True)
	return ict_api.scan_linked_company_defaults_impl(main_company, other_company)


@frappe.whitelist()
def get_company_currencies(companies: list | str | None = None):
	frappe.has_permission("Company", "read", throw=True)
	return ict_api.get_company_currencies_impl(companies=companies)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def intercompany_party_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int | str,
	page_len: int | str,
	filters: dict | str | list | None,
):
	return ict_api.intercompany_party_query_impl(doctype, txt, searchfield, start, page_len, filters)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def intercompany_account_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int | str,
	page_len: int | str,
	filters: dict | str | list | None,
):
	return ict_api.intercompany_account_query_impl(doctype, txt, searchfield, start, page_len, filters)


@frappe.whitelist()
def check_intercompany_exchange_rate(
	source_company: str,
	target_company: str,
	transaction_date: str | None = None,
	doc_currency: str | None = None,
	conversion_rate: float | int | str | None = None,
):
	frappe.has_permission("Company", "read", throw=True)
	return ict_currency.check_intercompany_exchange_rate_impl(
		source_company,
		target_company,
		transaction_date=transaction_date,
		doc_currency=doc_currency,
		conversion_rate=conversion_rate,
	)


@frappe.whitelist()
def check_stock_entry_same_currency(source_company: str, target_company: str):
	frappe.has_permission("Company", "read", throw=True)
	return ict_currency.check_stock_entry_same_currency_impl(source_company, target_company)


@frappe.whitelist()
def save_intercompany_currency_exchange(
	from_currency: str,
	to_currency: str,
	exchange_rate: float | int | str,
	date: str | None = None,
):
	return ict_currency.save_intercompany_currency_exchange_impl(from_currency, to_currency, exchange_rate, date=date)


@frappe.whitelist()
def trigger_manual_intercompany_sync(doctype: str, name: str):
	return ict_api.trigger_manual_intercompany_sync_impl(doctype, name)


@frappe.whitelist()
def get_linked_counterpart_for_form(doctype: str, name: str):
	return ict_api.get_linked_counterpart_for_form_impl(doctype, name)


@frappe.whitelist()
def delete_mirrored_draft(doctype: str, name: str):
	return ict_api.delete_mirrored_draft_impl(doctype, name)


@frappe.whitelist()
def unlink_mirrored_document(doctype: str, name: str):
	return ict_api.unlink_mirrored_document_impl(doctype, name)


@frappe.whitelist()
def bulk_create_linked_documents(doc_names: list | str, doctype: str):
	return ict_api.bulk_create_linked_documents_impl(doc_names, doctype)


@frappe.whitelist()
def reconcile_intercompany_accounts():
	frappe.only_for(["System Manager", "Accounts Manager", "Accounts User"])
	return ict_api.reconcile_intercompany_accounts_impl()


@frappe.whitelist()
def get_intercompany_dashboard_data(company: str):
	frappe.only_for(["System Manager", "Accounts Manager", "Accounts User"])
	return ict_api.get_intercompany_dashboard_data_impl(company)


@frappe.whitelist()
def download_user_guide_pdf():
	frappe.has_permission("Intercompany Transaction Link", "read", throw=True)
	return ict_api.download_user_guide_pdf_impl()


@frappe.whitelist()
def get_party_target_company(
	party_name: str,
	party_type: str | None = None,
	current_company: str | None = None,
):
	pt = (party_type or "").strip()
	if pt in ("Customer", "Supplier"):
		frappe.has_permission(pt, "read", throw=True)
	elif not (frappe.has_permission("Customer", "read") or frappe.has_permission("Supplier", "read")):
		frappe.has_permission("Customer", "read", throw=True)
	return ict_api.get_party_target_company_impl(party_name, party_type=party_type, current_company=current_company)


@frappe.whitelist()
def get_intercompany_party_map(company: str | None = None):
	if getattr(getattr(frappe, "session", None), "user", None) == "Guest":
		frappe.throw(_("Authentication required."), exc=getattr(frappe, "PermissionError", Exception))
	if not (frappe.has_permission("Intercompany Transaction Link", "read") or frappe.has_permission("Company", "read")):
		frappe.has_permission("Intercompany Transaction Link", "read", throw=True)
	return ict_validation.get_intercompany_party_map_impl(company=company)
