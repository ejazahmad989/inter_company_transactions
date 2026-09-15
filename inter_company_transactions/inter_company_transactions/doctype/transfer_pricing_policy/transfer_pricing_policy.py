# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026, Inter Company Transactions and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

class TransferPricingPolicy(Document):
	def validate(self):
		if self.from_company == self.to_company:
			frappe.throw(_("Originating Company and Receiving Company cannot be identical."))

		if self.effective_to and self.effective_from and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To date cannot be earlier than Effective From date."))
