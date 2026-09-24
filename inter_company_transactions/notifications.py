# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def get_notification_config():
    """Get notification configuration for Inter Company Transactions"""
    return {
        "for_doctype": {
            "Inter Company Error Log": {
                "status": "status"
            },
            "Inter Company Dispute": {
                "status": "status"
            }
        }
    }
