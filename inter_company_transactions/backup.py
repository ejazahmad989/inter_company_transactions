# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def before_backup():
    """Execute before backup"""
    try:
        frappe.logger().info("Pre-backup tasks for Inter Company Transactions")
    except Exception as e:
        frappe.log_error(f"Error in before backup: {str(e)}", "Backup Management")

def after_backup():
    """Execute after backup"""
    try:
        frappe.logger().info("Post-backup tasks for Inter Company Transactions")
    except Exception as e:
        frappe.log_error(f"Error in after backup: {str(e)}", "Backup Management")
