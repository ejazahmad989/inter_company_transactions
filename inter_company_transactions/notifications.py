# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def get_notification_config():
    """Get notification configuration for the app"""
    return {
        "for_doctype": {
            "Workflow Approval Request": {
                "status": "status",
                "conditions": [
                    {
                        "condition": "status == 'Pending'",
                        "color": "orange"
                    },
                    {
                        "condition": "status == 'Approved'", 
                        "color": "green"
                    },
                    {
                        "condition": "status == 'Rejected'",
                        "color": "red"
                    }
                ]
            },
            "Inter Company Workflow": {
                "status": "workflow_status",
                "conditions": [
                    {
                        "condition": "enabled == 1",
                        "color": "green"
                    },
                    {
                        "condition": "enabled == 0",
                        "color": "gray"
                    }
                ]
            }
        }
    }