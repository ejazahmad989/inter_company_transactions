# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def handle_error(error):
    """Handle application errors"""
    try:
        # Log error with context
        frappe.log_error(
            f"Application Error: {str(error)}\nUser: {frappe.session.user}\nURL: {frappe.request.url if frappe.request else 'N/A'}",
            "Application Error Handler"
        )
        
        # Send notification to administrators if critical
        if is_critical_error(error):
            send_error_notification(error)
            
    except Exception as e:
        # Fallback error logging
        frappe.log_error(f"Error in error handler: {str(e)}", "Error Handler")

def is_critical_error(error):
    """Check if error is critical"""
    critical_keywords = [
        "database",
        "connection",
        "permission",
        "workflow",
        "inter_company"
    ]
    
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in critical_keywords)

def send_error_notification(error):
    """Send error notification to administrators"""
    try:
        administrators = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager"},
            fields=["parent"]
        )
        
        for admin in administrators:
            frappe.sendmail(
                recipients=[admin.parent],
                subject="Critical Error in Inter Company Transactions",
                message=f"A critical error occurred: {str(error)}",
                reference_doctype="Error Log",
                reference_name=frappe.utils.now()
            )
            
    except Exception as e:
        frappe.log_error(f"Error sending error notification: {str(e)}", "Error Notification")