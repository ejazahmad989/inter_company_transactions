# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

logger = frappe.logger("inter_company_transactions")


class IntercompanyTransactionLink(Document):
	def validate(self):
		self.validate_companies()
		self.validate_parties()
		self.validate_accounts()

	def validate_companies(self):
		"""Ensure main company and linked companies are valid and distinct"""
		if not self.main_company:
			frappe.throw(_("Main Company is required"))

		if not self.linked_companies:
			frappe.throw(_("At least one Linked Company must be configured"))

		linked_companies = [d.company for d in self.linked_companies if d.company]
		if self.main_company in linked_companies:
			frappe.throw(_("Main Company cannot be listed in Linked Companies"))

		if len(linked_companies) != len(set(linked_companies)):
			frappe.throw(_("Duplicate companies found in Linked Companies table"))

	def validate_parties(self):
		"""Validate that customers and suppliers are properly mapped between companies"""
		for linked_company in self.linked_companies:
			if not linked_company.company:
				continue

			if linked_company.main_company_customer and not linked_company.other_company_supplier:
				frappe.throw(
					_(
						"Other Company Supplier is required when Main Company Customer is set for linked company {0}"
					).format(frappe.bold(linked_company.company))
				)

			if linked_company.main_company_supplier and not linked_company.other_company_customer:
				frappe.throw(
					_(
						"Other Company Customer is required when Main Company Supplier is set for linked company {0}"
					).format(frappe.bold(linked_company.company))
				)

	def validate_accounts(self):
		"""Validate that clearing accounts are configured if financial entries are used"""
		has_financial = any(
			t.source_type in ["Journal Entry", "Payment Entry"] or t.target_type in ["Journal Entry", "Payment Entry"]
			for t in (self.transaction_types or [])
		)
		if has_financial:
			for lc in self.linked_companies:
				if not lc.main_company_account or not lc.other_company_account:
					frappe.msgprint(
						_(
							"Warning: Clearing accounts (Main Company Account and Other Company Account) "
							"should be configured on linked company {0} for financial transactions."
						).format(frappe.bold(lc.company)),
						indicator="orange",
					)


def create_linked_documents(doc, method=None):
	"""
	Hook called on_submit of supported documents.
	Supports both Synchronous execution and Asynchronous (Background Queue) execution.
	"""
	# Check global Inter Company Settings toggle
	settings = get_settings()
	if settings and not settings.get("enabled", 1):
		logger.debug("Inter Company automation globally disabled in settings")
		return

	# Avoid recursive loops if triggered by automated creation
	if doc.flags.get("intercompany_auto_create"):
		logger.debug(f"Skipping {doc.doctype} {doc.name}: triggered by intercompany auto create flag")
		return

	if doc.get("intercompany_linked_doc_name") and doc.get("intercompany_linked_doc_doctype"):
		logger.debug(f"Skipping {doc.doctype} {doc.name}: document already has a linked reference")
		return

	if not hasattr(doc, "company") or not doc.company:
		return

	# Route to background job if asynchronous mode is active
	execution_mode = settings.get("execution_mode", "Synchronous") if settings else "Synchronous"
	if execution_mode == "Asynchronous (Background Job)":
		frappe.enqueue(
			"inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link._process_linked_documents",
			doc_doctype=doc.doctype,
			doc_name=doc.name,
			queue="default",
			now=frappe.flags.in_test,
		)
		frappe.msgprint(
			_("Intercompany document processing queued in background"),
			title=_("Intercompany Queue"),
			indicator="blue",
		)
		return

	_process_linked_documents(doc.doctype, doc.name)


def _process_linked_documents(doc_doctype, doc_name):
	"""Core execution processor for generating linked cross-company documents"""
	if not frappe.db.exists(doc_doctype, doc_name):
		return

	doc = frappe.get_doc(doc_doctype, doc_name)
	settings = get_settings()

	mappings = find_applicable_mappings(doc)
	if not mappings:
		logger.debug(f"No applicable intercompany mappings found for {doc.doctype} {doc.name} ({doc.company})")
		return

	logger.info(f"Found {len(mappings)} applicable mappings for {doc.doctype} {doc.name}")

	for i, mapping_info in enumerate(mappings):
		link_parent = mapping_info["mapping"]
		trans_type = mapping_info["transaction_type"]
		target_company = mapping_info["company"]
		linked_company = mapping_info["linked_company"]
		direction = mapping_info["direction"]

		if not link_parent.get("auto_create_draft", 1):
			logger.info(
				f"Skipping mapping {i+1}: auto_create_draft is disabled for link {link_parent.name}"
			)
			continue

		try:
			validate_required_parties(doc, mapping_info)

			linked_doc = create_corresponding_document(doc, mapping_info, direction, settings)
			if not linked_doc:
				logger.warning(
					f"create_corresponding_document returned None for {doc.doctype} {doc.name} -> {trans_type.target_type}"
				)
				continue

			# Set standard tracking and provenance fields
			if linked_doc.meta.has_field("intercompany_linked_doc_doctype"):
				linked_doc.intercompany_linked_doc_doctype = doc.doctype
			if linked_doc.meta.has_field("intercompany_linked_doc_name"):
				linked_doc.intercompany_linked_doc_name = doc.name
			if linked_doc.meta.has_field("intercompany_linked_company"):
				linked_doc.intercompany_linked_company = doc.company
			if linked_doc.meta.has_field("intercompany_target_company"):
				linked_doc.intercompany_target_company = doc.company

			# Bypass user permissions for cross-company automated document creation
			linked_doc.flags.ignore_permissions = True
			linked_doc.flags.intercompany_auto_create = True
			linked_doc.docstatus = 0  # Draft

			linked_doc.insert()

			# Record relationship in Inter Company Document Reference
			create_document_reference(doc, linked_doc)

			# Cross-reference back on source document if field exists
			if doc.meta.has_field("intercompany_linked_doc_name"):
				update_dict = {
					"intercompany_linked_doc_name": linked_doc.name,
					"intercompany_linked_company": linked_doc.company,
				}
				if doc.meta.has_field("intercompany_linked_doc_doctype"):
					update_dict["intercompany_linked_doc_doctype"] = linked_doc.doctype
				frappe.db.set_value(doc.doctype, doc.name, update_dict, update_modified=False)

			# Auto-submit if configured in settings and supported
			auto_submit = bool(settings and settings.get("auto_submit_target_doc", 0))
			if auto_submit:
				try:
					linked_doc.flags.ignore_permissions = True
					linked_doc.submit()
					status_label = _("submitted")
				except Exception as submit_err:
					logger.warning(f"Could not auto-submit {linked_doc.doctype} {linked_doc.name}: {str(submit_err)}")
					status_label = _("draft (auto-submit deferred)")
			else:
				status_label = _("draft")

			frappe.msgprint(
				_("Created {0} {1} {2} in company {3}").format(
					status_label,
					linked_doc.doctype,
					frappe.bold(linked_doc.name),
					frappe.bold(linked_doc.company),
				),
				title=_("Intercompany Transaction"),
				indicator="green",
			)
			logger.info(
				f"Successfully created {status_label} {linked_doc.doctype} {linked_doc.name} in {linked_doc.company}"
			)

		except Exception as e:
			error_msg = f"Failed to create intercompany document in company {target_company}: {str(e)}"
			logger.error(f"{error_msg}\n{frappe.get_traceback()}")
			frappe.log_error(
				f"{error_msg}\nSource: {doc.doctype} {doc.name}\nTraceback: {frappe.get_traceback()}",
				"Inter Company Transaction Error",
			)
			frappe.msgprint(error_msg, title=_("Intercompany Error"), indicator="red")


def cancel_linked_documents(doc, method=None):
	"""
	Hook called on_cancel of supported documents.
	Cancels corresponding documents in all linked companies symmetrically.
	"""
	settings = get_settings()
	if settings and not settings.get("enabled", 1):
		return

	if doc.flags.get("intercompany_auto_cancel"):
		logger.debug(f"Skipping {doc.doctype} {doc.name}: triggered by intercompany auto cancel")
		return

	if not hasattr(doc, "company") or not doc.company:
		return

	if not frappe.db.exists("DocType", "Inter Company Document Reference"):
		return

	all_related_docs = []

	# Find documents where current doc is the SOURCE
	try:
		linked_docs = frappe.get_all(
			"Inter Company Document Reference",
			filters={
				"source_doctype": doc.doctype,
				"source_name": doc.name,
				"source_company": doc.company,
			},
			fields=["name", "target_doctype", "target_name", "target_company"],
		)
		for ldoc in linked_docs:
			all_related_docs.append(
				{
					"doctype": ldoc.target_doctype,
					"name": ldoc.target_name,
					"company": ldoc.target_company,
					"relationship": "target",
				}
			)
	except Exception as e:
		logger.error(f"Error finding linked documents as source: {str(e)}")

	# Find documents where current doc is the TARGET
	try:
		reverse_links = frappe.get_all(
			"Inter Company Document Reference",
			filters={
				"target_doctype": doc.doctype,
				"target_name": doc.name,
				"target_company": doc.company,
			},
			fields=["name", "source_doctype", "source_name", "source_company"],
		)
		for rlink in reverse_links:
			all_related_docs.append(
				{
					"doctype": rlink.source_doctype,
					"name": rlink.source_name,
					"company": rlink.source_company,
					"relationship": "source",
				}
			)
	except Exception as e:
		logger.error(f"Error finding reverse linked documents as target: {str(e)}")

	logger.info(f"Found {len(all_related_docs)} related documents to cancel for {doc.doctype} {doc.name}")

	for rel in all_related_docs:
		doctype = rel["doctype"]
		name = rel["name"]
		company = rel["company"]
		relationship = rel["relationship"]

		try:
			if not frappe.db.exists(doctype, name):
				continue

			target_doc = frappe.get_doc(doctype, name)
			if target_doc.docstatus != 1:
				logger.info(f"{doctype} {name} is not submitted (docstatus={target_doc.docstatus}), skipping cancel")
				continue

			target_doc.flags.ignore_permissions = True
			target_doc.flags.intercompany_auto_cancel = True
			target_doc.cancel()

			frappe.msgprint(
				_("Cancelled linked {0} {1} in company {2} ({3})").format(
					doctype, frappe.bold(name), frappe.bold(company), relationship
				),
				title=_("Intercompany Cancellation"),
				indicator="orange",
			)
			logger.info(f"Successfully cancelled {doctype} {name} in {company}")

		except Exception as e:
			err = f"Error cancelling linked {relationship} document {doctype} {name}: {str(e)}"
			logger.error(f"{err}\n{frappe.get_traceback()}")
			frappe.log_error(
				f"{err}\nSource Document: {doc.doctype} {doc.name}\nTraceback: {frappe.get_traceback()}",
				"Inter Company Transaction Error",
			)


def find_applicable_mappings(doc):
	"""
	Identify all valid Intercompany Transaction Link configurations that match
	the given document by company, linked company, party, and transaction type.
	"""
	mappings = []
	links = frappe.get_all("Intercompany Transaction Link", filters={"enabled": 1}, fields=["name"])

	for item in links:
		link = frappe.get_doc("Intercompany Transaction Link", item.name)
		is_main = doc.company == link.main_company
		target_company_from_doc = doc.get("intercompany_target_company")

		if is_main:
			for lc in link.linked_companies:
				if not lc.company:
					continue

				match_by_explicit = target_company_from_doc and target_company_from_doc == lc.company
				match_by_party = False

				if not target_company_from_doc:
					if doc.doctype in ["Sales Order", "Sales Invoice", "Delivery Note"]:
						if lc.main_company_customer and doc.get("customer") == lc.main_company_customer:
							match_by_party = True
					elif doc.doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt"]:
						if lc.main_company_supplier and doc.get("supplier") == lc.main_company_supplier:
							match_by_party = True
					elif doc.doctype == "Payment Entry":
						if doc.get("party_type") == "Customer" and doc.get("party") == lc.main_company_customer:
							match_by_party = True
						elif doc.get("party_type") == "Supplier" and doc.get("party") == lc.main_company_supplier:
							match_by_party = True
					elif doc.doctype == "Journal Entry":
						for acc in doc.get("accounts", []):
							if acc.get("party_type") == "Customer" and acc.get("party") == lc.main_company_customer:
								match_by_party = True
								break
							elif acc.get("party_type") == "Supplier" and acc.get("party") == lc.main_company_supplier:
								match_by_party = True
								break
					elif doc.doctype == "Stock Entry":
						match_by_party = False

				if match_by_explicit or match_by_party:
					for tt in link.transaction_types:
						if tt.source_type == doc.doctype and tt.direction in ["Main to Other", "Both"]:
							mappings.append(
								{
									"mapping": link,
									"transaction_type": tt,
									"company": lc.company,
									"linked_company": lc,
									"direction": "main_to_other",
								}
							)
		else:
			matching_lc = next((lc for lc in link.linked_companies if lc.company == doc.company), None)
			if matching_lc:
				match_by_explicit = target_company_from_doc and target_company_from_doc == link.main_company
				match_by_party = False

				if not target_company_from_doc:
					if doc.doctype in ["Sales Order", "Sales Invoice", "Delivery Note"]:
						if matching_lc.other_company_customer and doc.get("customer") == matching_lc.other_company_customer:
							match_by_party = True
					elif doc.doctype in ["Purchase Order", "Purchase Invoice", "Purchase Receipt"]:
						if matching_lc.other_company_supplier and doc.get("supplier") == matching_lc.other_company_supplier:
							match_by_party = True
					elif doc.doctype == "Payment Entry":
						if doc.get("party_type") == "Customer" and doc.get("party") == matching_lc.other_company_customer:
							match_by_party = True
						elif doc.get("party_type") == "Supplier" and doc.get("party") == matching_lc.other_company_supplier:
							match_by_party = True
					elif doc.doctype == "Journal Entry":
						for acc in doc.get("accounts", []):
							if acc.get("party_type") == "Customer" and acc.get("party") == matching_lc.other_company_customer:
								match_by_party = True
								break
							elif acc.get("party_type") == "Supplier" and acc.get("party") == matching_lc.other_company_supplier:
								match_by_party = True
								break
					elif doc.doctype == "Stock Entry":
						match_by_party = False

				if match_by_explicit or match_by_party:
					for tt in link.transaction_types:
						if tt.source_type == doc.doctype and tt.direction in ["Other to Main", "Both"]:
							mappings.append(
								{
									"mapping": link,
									"transaction_type": tt,
									"company": link.main_company,
									"linked_company": matching_lc,
									"direction": "other_to_main",
								}
							)

	return mappings


def validate_required_parties(doc, mapping_info):
	"""Validate that required parties, accounts, and warehouses exist before creation"""
	lc = mapping_info["linked_company"]
	tt = mapping_info["transaction_type"]
	direction = mapping_info.get("direction")
	target_company = mapping_info["company"]

	if tt.target_type in ["Purchase Order", "Purchase Invoice", "Purchase Receipt"]:
		supplier = lc.main_company_supplier if direction == "other_to_main" else lc.other_company_supplier
		if not supplier:
			field_name = "Main Company Supplier" if direction == "other_to_main" else "Other Company Supplier"
			frappe.throw(
				_("{0} is required on linked company configuration for {1} to create {2}").format(
					field_name, frappe.bold(target_company), tt.target_type
				)
			)

	elif tt.target_type in ["Sales Order", "Sales Invoice", "Delivery Note"]:
		customer = lc.main_company_customer if direction == "other_to_main" else lc.other_company_customer
		if not customer:
			field_name = "Main Company Customer" if direction == "other_to_main" else "Other Company Customer"
			frappe.throw(
				_("{0} is required on linked company configuration for {1} to create {2}").format(
					field_name, frappe.bold(target_company), tt.target_type
				)
			)

	elif tt.target_type in ["Journal Entry", "Payment Entry"]:
		customer = lc.main_company_customer if direction == "other_to_main" else lc.other_company_customer
		supplier = lc.main_company_supplier if direction == "other_to_main" else lc.other_company_supplier
		account = lc.main_company_account if direction == "other_to_main" else lc.other_company_account

		if not customer or not supplier:
			frappe.throw(
				_("Both Customer and Supplier must be configured on linked company {0} for {1}").format(
					frappe.bold(target_company), tt.target_type
				)
			)
		if not account:
			account_label = "Main Company Account" if direction == "other_to_main" else "Other Company Account"
			frappe.throw(
				_("{0} (Clearing Account) is required for company {1}").format(
					account_label, frappe.bold(target_company)
				)
			)

	elif tt.target_type == "Stock Entry":
		s_wh = get_intercompany_warehouse(doc.company)
		t_wh = get_intercompany_warehouse(target_company)
		if not s_wh or not t_wh:
			frappe.throw(
				_("Intercompany warehouses must be configured for both {0} and {1}").format(
					frappe.bold(doc.company), frappe.bold(target_company)
				)
			)


def create_corresponding_document(source_doc, mapping_info, direction, settings=None):
	"""Dispatcher to route creation with transfer pricing support"""
	trans_type = mapping_info["transaction_type"]
	mapping = mapping_info["mapping"]
	linked_company = mapping_info["linked_company"]
	target = trans_type.target_type

	if source_doc.doctype == "Sales Order" and target == "Purchase Order":
		return create_purchase_order(source_doc, mapping, linked_company, direction, settings)
	elif source_doc.doctype == "Purchase Order" and target == "Sales Order":
		return create_sales_order(source_doc, mapping, linked_company, direction, settings)
	elif source_doc.doctype == "Sales Invoice" and target == "Purchase Invoice":
		return create_purchase_invoice(source_doc, mapping, linked_company, direction, settings)
	elif source_doc.doctype == "Purchase Invoice" and target == "Sales Invoice":
		return create_sales_invoice(source_doc, mapping, linked_company, direction, settings)
	elif source_doc.doctype == "Delivery Note" and target == "Purchase Receipt":
		return create_purchase_receipt(source_doc, mapping, linked_company, direction)
	elif source_doc.doctype == "Purchase Receipt" and target == "Delivery Note":
		return create_delivery_note(source_doc, mapping, linked_company, direction)
	elif source_doc.doctype == "Stock Entry" and target == "Stock Entry":
		return create_stock_entry(source_doc, mapping, linked_company, direction)
	elif source_doc.doctype == "Journal Entry" and target == "Journal Entry":
		return create_journal_entry(source_doc, mapping, linked_company, direction)
	elif source_doc.doctype == "Payment Entry" and target == "Payment Entry":
		return create_payment_entry(source_doc, mapping, linked_company, direction)

	logger.warning(f"No document creation mapping found for {source_doc.doctype} -> {target}")
	return None


# -------------------------------------------------------------------------
# Document Creators (With Transfer Pricing & Auto-Allocation)
# -------------------------------------------------------------------------

def calculate_transfer_rate(item_doc, source_rate, source_company, settings):
	"""
	Calculates the item rate based on configured transfer pricing rules:
	1. Source Document Rate
	2. Cost / Valuation Rate
	3. Cost + Markup %
	"""
	if not settings:
		return flt(source_rate)

	rule = settings.get("default_transfer_pricing_rule", "Source Document Rate")
	if rule == "Source Document Rate":
		return flt(source_rate)

	# Fetch item valuation rate from source company bin
	item_code = item_doc.get("item_code")
	val_rate = 0.0
	try:
		val_rate = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": ["in", frappe.get_all("Warehouse", filters={"company": source_company}, pluck="name")]},
				"valuation_rate",
			)
		)
		if not val_rate:
			val_rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	except Exception:
		val_rate = flt(source_rate)

	if not val_rate:
		val_rate = flt(source_rate)

	if rule == "Cost / Valuation Rate":
		return val_rate

	if rule == "Cost + Markup %":
		markup = flt(settings.get("markup_percentage", 0.0))
		return flt(val_rate * (1.0 + (markup / 100.0)), 2)

	return flt(source_rate)


def create_purchase_order(sales_order, mapping, linked_company, direction, settings=None):
	"""Create Purchase Order from Sales Order"""
	po = frappe.new_doc("Purchase Order")

	if direction == "other_to_main":
		po.company = mapping.main_company
		po.supplier = linked_company.main_company_supplier
	else:
		po.company = linked_company.company
		po.supplier = linked_company.other_company_supplier

	if not po.supplier:
		frappe.throw(_("Supplier not found for company {0}").format(po.company))

	po.currency = sales_order.currency
	po.conversion_rate = sales_order.conversion_rate or 1.0
	po.transaction_date = sales_order.transaction_date or nowdate()
	po.schedule_date = sales_order.delivery_date or sales_order.transaction_date or nowdate()

	target_warehouse = get_default_warehouse(po.company)

	for item in sales_order.items:
		rate = calculate_transfer_rate(item, item.rate, sales_order.company, settings)
		po.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": rate,
				"price_list_rate": rate,
				"warehouse": target_warehouse,
				"schedule_date": item.delivery_date or po.schedule_date,
			},
		)

	po.flags.ignore_permissions = True
	po.run_method("set_missing_values")
	po.run_method("calculate_taxes_and_totals")
	po.docstatus = 0
	return po


def create_sales_order(purchase_order, mapping, linked_company, direction, settings=None):
	"""Create Sales Order from Purchase Order"""
	so = frappe.new_doc("Sales Order")

	if direction == "other_to_main":
		so.company = mapping.main_company
		so.customer = linked_company.main_company_customer
	else:
		so.company = linked_company.company
		so.customer = linked_company.other_company_customer

	if not so.customer:
		frappe.throw(_("Customer not found for company {0}").format(so.company))

	so.currency = purchase_order.currency
	so.conversion_rate = purchase_order.conversion_rate or 1.0
	so.transaction_date = purchase_order.transaction_date or nowdate()
	so.delivery_date = purchase_order.schedule_date or purchase_order.transaction_date or nowdate()

	target_warehouse = get_default_warehouse(so.company)

	for item in purchase_order.items:
		rate = calculate_transfer_rate(item, item.rate, purchase_order.company, settings)
		so.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": rate,
				"price_list_rate": rate,
				"warehouse": target_warehouse,
				"delivery_date": item.schedule_date or so.delivery_date,
			},
		)

	so.flags.ignore_permissions = True
	so.run_method("set_missing_values")
	so.run_method("calculate_taxes_and_totals")
	so.docstatus = 0
	return so


def create_purchase_invoice(sales_invoice, mapping, linked_company, direction, settings=None):
	"""Create Purchase Invoice from Sales Invoice (with Return/Credit Note linking)"""
	pi = frappe.new_doc("Purchase Invoice")

	if direction == "other_to_main":
		pi.company = mapping.main_company
		pi.supplier = linked_company.main_company_supplier
	else:
		pi.company = linked_company.company
		pi.supplier = linked_company.other_company_supplier

	if not pi.supplier:
		frappe.throw(_("Supplier not found for company {0}").format(pi.company))

	pi.currency = sales_invoice.currency
	pi.conversion_rate = sales_invoice.conversion_rate or 1.0
	pi.posting_date = sales_invoice.posting_date or nowdate()
	pi.due_date = sales_invoice.due_date or pi.posting_date
	pi.bill_no = sales_invoice.name
	pi.bill_date = sales_invoice.posting_date

	# Handle Return / Credit Note linkage
	if sales_invoice.get("is_return"):
		pi.is_return = 1
		# Find the corresponding linked original Purchase Invoice in target company
		return_against_si = sales_invoice.get("return_against")
		if return_against_si:
			target_original_pi = frappe.db.get_value(
				"Inter Company Document Reference",
				{"source_name": return_against_si, "target_company": pi.company},
				"target_name",
			)
			if not target_original_pi:
				target_original_pi = frappe.db.get_value(
					"Inter Company Document Reference",
					{"target_name": return_against_si, "source_company": pi.company},
					"source_name",
				)
			if target_original_pi:
				pi.return_against = target_original_pi

	target_warehouse = get_default_warehouse(pi.company)
	cost_center = get_default_cost_center(pi.company)

	for item in sales_invoice.items:
		rate = calculate_transfer_rate(item, item.rate, sales_invoice.company, settings)
		pi.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": rate,
				"price_list_rate": rate,
				"discount_percentage": flt(item.discount_percentage),
				"warehouse": target_warehouse,
				"cost_center": cost_center,
			},
		)

	pi.flags.ignore_permissions = True
	pi.run_method("set_missing_values")
	pi.run_method("calculate_taxes_and_totals")
	pi.docstatus = 0
	return pi


def create_sales_invoice(purchase_invoice, mapping, linked_company, direction, settings=None):
	"""Create Sales Invoice from Purchase Invoice (with Return/Debit Note linking)"""
	si = frappe.new_doc("Sales Invoice")

	if direction == "other_to_main":
		si.company = mapping.main_company
		si.customer = linked_company.main_company_customer
	else:
		si.company = linked_company.company
		si.customer = linked_company.other_company_customer

	if not si.customer:
		frappe.throw(_("Customer not found for company {0}").format(si.company))

	si.currency = purchase_invoice.currency
	si.conversion_rate = purchase_invoice.conversion_rate or 1.0
	si.posting_date = purchase_invoice.posting_date or nowdate()
	si.due_date = purchase_invoice.due_date or si.posting_date
	si.po_no = purchase_invoice.name
	si.po_date = purchase_invoice.posting_date

	# Handle Return / Debit Note linkage
	if purchase_invoice.get("is_return"):
		si.is_return = 1
		return_against_pi = purchase_invoice.get("return_against")
		if return_against_pi:
			target_original_si = frappe.db.get_value(
				"Inter Company Document Reference",
				{"source_name": return_against_pi, "target_company": si.company},
				"target_name",
			)
			if not target_original_si:
				target_original_si = frappe.db.get_value(
					"Inter Company Document Reference",
					{"target_name": return_against_pi, "source_company": si.company},
					"source_name",
				)
			if target_original_si:
				si.return_against = target_original_si

	target_warehouse = get_default_warehouse(si.company)
	cost_center = get_default_cost_center(si.company)

	for item in purchase_invoice.items:
		rate = calculate_transfer_rate(item, item.rate, purchase_invoice.company, settings)
		si.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": rate,
				"price_list_rate": rate,
				"discount_percentage": flt(item.discount_percentage),
				"warehouse": target_warehouse,
				"cost_center": cost_center,
			},
		)

	si.flags.ignore_permissions = True
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	si.docstatus = 0
	return si


def create_delivery_note(purchase_receipt, mapping, linked_company, direction):
	"""Create Delivery Note from Purchase Receipt"""
	dn = frappe.new_doc("Delivery Note")

	if direction == "other_to_main":
		dn.company = mapping.main_company
		dn.customer = linked_company.main_company_customer
	else:
		dn.company = linked_company.company
		dn.customer = linked_company.other_company_customer

	if not dn.customer:
		frappe.throw(_("Customer not found for company {0}").format(dn.company))

	dn.posting_date = purchase_receipt.posting_date or nowdate()
	dn.posting_time = purchase_receipt.posting_time
	dn.set_posting_time = purchase_receipt.set_posting_time
	dn.currency = purchase_receipt.currency
	dn.conversion_rate = purchase_receipt.conversion_rate or 1.0

	if purchase_receipt.get("is_return"):
		dn.is_return = 1

	target_warehouse = get_default_warehouse(dn.company)

	for item in purchase_receipt.items:
		if not frappe.db.exists("Item", item.item_code):
			frappe.throw(
				_("Item {0} does not exist in company {1}").format(
					frappe.bold(item.item_code), frappe.bold(dn.company)
				)
			)

		dn.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": flt(item.rate),
				"warehouse": target_warehouse,
			},
		)

	dn.flags.ignore_permissions = True
	dn.run_method("set_missing_values")
	dn.run_method("calculate_taxes_and_totals")
	dn.docstatus = 0
	return dn


def create_purchase_receipt(delivery_note, mapping, linked_company, direction):
	"""Create Purchase Receipt from Delivery Note"""
	pr = frappe.new_doc("Purchase Receipt")

	if direction == "other_to_main":
		pr.company = mapping.main_company
		pr.supplier = linked_company.main_company_supplier
	else:
		pr.company = linked_company.company
		pr.supplier = linked_company.other_company_supplier

	if not pr.supplier:
		frappe.throw(_("Supplier not found for company {0}").format(pr.company))

	pr.posting_date = delivery_note.posting_date or nowdate()
	pr.posting_time = delivery_note.posting_time
	pr.set_posting_time = delivery_note.set_posting_time
	pr.currency = delivery_note.currency
	pr.conversion_rate = delivery_note.conversion_rate or 1.0

	if delivery_note.get("is_return"):
		pr.is_return = 1

	target_warehouse = get_default_warehouse(pr.company)

	for item in delivery_note.items:
		if not frappe.db.exists("Item", item.item_code):
			frappe.throw(
				_("Item {0} does not exist in company {1}").format(
					frappe.bold(item.item_code), frappe.bold(pr.company)
				)
			)

		pr.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"conversion_factor": flt(item.conversion_factor) or 1.0,
				"rate": flt(item.rate),
				"warehouse": target_warehouse,
			},
		)

	pr.flags.ignore_permissions = True
	pr.run_method("set_missing_values")
	pr.run_method("calculate_taxes_and_totals")
	pr.docstatus = 0
	return pr


def create_stock_entry(source_se, mapping, linked_company, direction):
	"""Create Stock Entry for intercompany material transfer"""
	se = frappe.new_doc("Stock Entry")

	if direction == "other_to_main":
		se.company = mapping.main_company
		source_company = linked_company.company
		target_company = mapping.main_company
	else:
		se.company = linked_company.company
		source_company = mapping.main_company
		target_company = linked_company.company

	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.posting_date = source_se.posting_date or nowdate()
	se.posting_time = source_se.posting_time
	se.set_posting_time = source_se.set_posting_time

	source_wh = get_intercompany_warehouse(source_company)
	target_wh = get_intercompany_warehouse(target_company)

	if not source_wh or not target_wh:
		frappe.throw(_("Inter-company warehouses not found for {0} and {1}").format(source_company, target_company))

	for item in source_se.items:
		if not frappe.db.exists("Item", item.item_code):
			frappe.throw(
				_("Item {0} does not exist in target company {1}").format(
					frappe.bold(item.item_code), frappe.bold(se.company)
				)
			)

		se.append(
			"items",
			{
				"item_code": item.item_code,
				"qty": flt(item.qty),
				"uom": item.uom,
				"stock_uom": item.stock_uom or item.uom,
				"s_warehouse": source_wh,
				"t_warehouse": target_wh,
				"basic_rate": flt(item.basic_rate),
				"basic_amount": flt(item.basic_rate) * flt(item.qty),
				"conversion_factor": flt(item.conversion_factor) or 1.0,
			},
		)

	se.flags.ignore_permissions = True
	se.run_method("set_missing_values")
	se.docstatus = 0
	return se


def create_journal_entry(source_je, mapping, linked_company, direction):
	"""Create corresponding Journal Entry with multi-currency support"""
	je = frappe.new_doc("Journal Entry")

	if direction == "other_to_main":
		je.company = mapping.main_company
		supplier = linked_company.main_company_supplier
		customer = linked_company.main_company_customer
		clearing_account = linked_company.main_company_account
	else:
		je.company = linked_company.company
		supplier = linked_company.other_company_supplier
		customer = linked_company.other_company_customer
		clearing_account = linked_company.other_company_account

	je.posting_date = source_je.posting_date or nowdate()
	je.user_remark = f"Auto-generated from {source_je.doctype} {source_je.name}: " + (source_je.user_remark or "")
	cost_center = get_default_cost_center(je.company)

	source_currency = frappe.db.get_value("Company", source_je.company, "default_currency")
	target_currency = frappe.db.get_value("Company", je.company, "default_currency")

	exchange_rate = 1.0
	if source_currency != target_currency:
		exchange_rate = get_exchange_rate(source_currency, target_currency, je.posting_date)

	source_party_type = None
	source_is_credit = False
	total_amount = 0.0

	for acc in source_je.accounts:
		if acc.party_type and acc.party:
			source_party_type = acc.party_type
			source_is_credit = flt(acc.credit_in_account_currency) > 0
			total_amount = flt(acc.credit_in_account_currency) if source_is_credit else flt(acc.debit_in_account_currency)
			break

	if not total_amount:
		total_amount = flt(source_je.total_credit) or flt(source_je.total_debit)

	converted_amount = flt(total_amount * exchange_rate, 2)

	receivable_acc = frappe.db.get_value("Company", je.company, "default_receivable_account")
	payable_acc = frappe.db.get_value("Company", je.company, "default_payable_account")

	if source_party_type == "Supplier" and source_is_credit:
		je.append(
			"accounts",
			{
				"account": receivable_acc,
				"party_type": "Customer",
				"party": customer,
				"debit_in_account_currency": converted_amount,
				"credit_in_account_currency": 0,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": clearing_account,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": converted_amount,
				"cost_center": cost_center,
			},
		)

	elif source_party_type == "Supplier" and not source_is_credit:
		je.append(
			"accounts",
			{
				"account": receivable_acc,
				"party_type": "Customer",
				"party": customer,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": converted_amount,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": clearing_account,
				"debit_in_account_currency": converted_amount,
				"credit_in_account_currency": 0,
				"cost_center": cost_center,
			},
		)

	elif source_party_type == "Customer" and source_is_credit:
		je.append(
			"accounts",
			{
				"account": payable_acc,
				"party_type": "Supplier",
				"party": supplier,
				"debit_in_account_currency": converted_amount,
				"credit_in_account_currency": 0,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": clearing_account,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": converted_amount,
				"cost_center": cost_center,
			},
		)

	else:
		je.append(
			"accounts",
			{
				"account": payable_acc,
				"party_type": "Supplier",
				"party": supplier,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": converted_amount,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": clearing_account,
				"debit_in_account_currency": converted_amount,
				"credit_in_account_currency": 0,
				"cost_center": cost_center,
			},
		)

	je.flags.ignore_permissions = True
	je.run_method("set_missing_values")
	je.docstatus = 0
	return je


def create_payment_entry(source_pe, mapping, linked_company, direction):
	"""Create corresponding Payment Entry with auto-allocation to linked invoices"""
	pe = frappe.new_doc("Payment Entry")

	if direction == "other_to_main":
		pe.company = mapping.main_company
		clearing_account = linked_company.main_company_account
		customer = linked_company.main_company_customer
		supplier = linked_company.main_company_supplier
	else:
		pe.company = linked_company.company
		clearing_account = linked_company.other_company_account
		customer = linked_company.other_company_customer
		supplier = linked_company.other_company_supplier

	pe.posting_date = source_pe.posting_date or nowdate()
	pe.payment_type = "Pay" if source_pe.payment_type == "Receive" else "Receive"
	pe.mode_of_payment = source_pe.mode_of_payment

	if pe.payment_type == "Pay":
		pe.paid_from = clearing_account
		pe.paid_to = frappe.db.get_value("Company", pe.company, "default_payable_account")
		pe.party_type = "Supplier"
		pe.party = supplier
		pe.party_name = frappe.db.get_value("Supplier", supplier, "supplier_name") if supplier else ""
	else:
		pe.paid_from = frappe.db.get_value("Company", pe.company, "default_receivable_account")
		pe.paid_to = clearing_account
		pe.party_type = "Customer"
		pe.party = customer
		pe.party_name = frappe.db.get_value("Customer", customer, "customer_name") if customer else ""

	pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency")
	pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency")

	pe.paid_amount = flt(source_pe.received_amount) or flt(source_pe.paid_amount)
	pe.received_amount = flt(source_pe.paid_amount) or flt(source_pe.received_amount)
	pe.target_exchange_rate = flt(source_pe.target_exchange_rate) or 1.0

	pe.reference_no = source_pe.reference_no or source_pe.name
	pe.reference_date = source_pe.reference_date or source_pe.posting_date

	# Auto-reconcile with linked invoices in target company if source PE has references
	for ref in getattr(source_pe, "references", []):
		target_inv_name = frappe.db.get_value(
			"Inter Company Document Reference",
			{"source_name": ref.reference_name, "target_company": pe.company},
			"target_name",
		)
		if not target_inv_name:
			target_inv_name = frappe.db.get_value(
				"Inter Company Document Reference",
				{"target_name": ref.reference_name, "source_company": pe.company},
				"source_name",
			)

		if target_inv_name:
			target_inv_doctype = "Purchase Invoice" if ref.reference_doctype == "Sales Invoice" else "Sales Invoice"
			if frappe.db.exists(target_inv_doctype, target_inv_name):
				pe.append(
					"references",
					{
						"reference_doctype": target_inv_doctype,
						"reference_name": target_inv_name,
						"allocated_amount": flt(ref.allocated_amount),
					},
				)

	pe.flags.ignore_permissions = True
	pe.run_method("set_missing_values")
	pe.docstatus = 0
	return pe


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def get_settings():
	"""Helper to fetch cached Inter Company Settings safely"""
	try:
		return frappe.get_cached_doc("Inter Company Settings")
	except Exception:
		return None


def get_default_warehouse(company):
	"""Get default non-group warehouse for company with robust fallbacks"""
	company_wh = frappe.db.get_value("Company", company, "default_warehouse")
	if company_wh and frappe.db.exists("Warehouse", company_wh):
		return company_wh

	warehouse = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
	)
	if not warehouse:
		frappe.throw(_("No active non-group warehouse found for company {0}").format(frappe.bold(company)))
	return warehouse


def get_intercompany_warehouse(company):
	"""Get designated intercompany or transit warehouse for company"""
	warehouse = frappe.db.get_value(
		"Warehouse",
		{"company": company, "warehouse_name": ["like", "%inter%company%"], "is_group": 0, "disabled": 0},
		"name",
	)
	if not warehouse:
		warehouse = frappe.db.get_value(
			"Warehouse",
			{"company": company, "warehouse_name": ["like", "%transit%"], "is_group": 0, "disabled": 0},
			"name",
		)
	if not warehouse:
		warehouse = get_default_warehouse(company)
	return warehouse


def get_default_cost_center(company):
	"""Get default cost center for company with fallback to any active non-group cost center"""
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	if cost_center and frappe.db.exists("Cost Center", cost_center):
		return cost_center

	fallback_cc = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
	)
	if fallback_cc:
		return fallback_cc

	frappe.throw(_("No active non-group cost center found for company {0}").format(frappe.bold(company)))


def get_mapped_account(account, to_company):
	"""Find the matching account in the target company by name or type"""
	account_name = frappe.db.get_value("Account", account, "account_name")
	account_type = frappe.db.get_value("Account", account, "account_type")

	mapped = frappe.db.get_value(
		"Account",
		{"account_name": account_name, "company": to_company, "is_group": 0, "disabled": 0},
		"name",
	)
	if mapped:
		return mapped

	if account_type:
		mapped = frappe.db.get_value(
			"Account",
			{"account_type": account_type, "company": to_company, "is_group": 0, "disabled": 0},
			"name",
		)
		if mapped:
			return mapped

	if account_type == "Receivable":
		return frappe.db.get_value("Company", to_company, "default_receivable_account")
	elif account_type == "Payable":
		return frappe.db.get_value("Company", to_company, "default_payable_account")
	else:
		return frappe.db.get_value("Company", to_company, "default_expense_account")


def get_exchange_rate(from_currency, to_currency, transaction_date=None):
	"""Fetch currency exchange rate with fallback to 1.0"""
	if from_currency == to_currency:
		return 1.0

	try:
		from erpnext.setup.utils import get_exchange_rate as erpnext_get_exchange_rate
		rate = erpnext_get_exchange_rate(from_currency, to_currency, transaction_date or nowdate())
		if rate:
			return flt(rate)
	except Exception:
		pass

	return 1.0


def create_document_reference(source_doc, target_doc):
	"""Create tracked relationship in Inter Company Document Reference without manual commits"""
	if source_doc.company == target_doc.company:
		logger.warning(
			f"Cannot create intercompany reference within the same company {source_doc.company}"
		)
		return

	exists = frappe.db.exists(
		"Inter Company Document Reference",
		{
			"source_doctype": source_doc.doctype,
			"source_name": source_doc.name,
			"target_doctype": target_doc.doctype,
			"target_name": target_doc.name,
		},
	)
	if exists:
		return

	try:
		ref_doc = frappe.get_doc(
			{
				"doctype": "Inter Company Document Reference",
				"source_doctype": source_doc.doctype,
				"source_name": source_doc.name,
				"source_company": source_doc.company,
				"target_doctype": target_doc.doctype,
				"target_name": target_doc.name,
				"target_company": target_doc.company,
			}
		)
		ref_doc.flags.ignore_permissions = True
		ref_doc.insert()
		logger.debug(
			f"Created Inter Company Document Reference: {source_doc.doctype} {source_doc.name} -> {target_doc.doctype} {target_doc.name}"
		)
	except Exception as e:
		logger.error(f"Error creating Inter Company Document Reference: {str(e)}")
