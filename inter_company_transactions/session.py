# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def on_session_creation(login_manager):
    """Handle session creation"""
    try:
        if frappe.session.user != "Guest":
            # Apply user theme
            from inter_company_transactions.enhanced_theme import apply_user_theme
            apply_user_theme()
            
            # Log session creation
            frappe.log_error(f"Session created for user: {frappe.session.user}", "Session Management")
            
    except Exception as e:
        frappe.log_error(f"Error in session creation: {str(e)}", "Session Management")