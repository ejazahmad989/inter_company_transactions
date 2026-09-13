# Copyright (c) 2024, AYP GROUP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class WorkflowApprovalHistory(Document):
    def validate(self):
        self.set_action_date()
        self.calculate_processing_time()
        
    def set_action_date(self):
        if not self.action_date:
            self.action_date = now_datetime()
            
    def calculate_processing_time(self):
        if self.action_date and self.completed_date:
            duration = self.completed_date - self.action_date
            self.processing_time = str(duration)