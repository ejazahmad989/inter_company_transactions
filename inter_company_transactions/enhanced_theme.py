# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import os
import json

@frappe.whitelist()
def get_company_theme(company=None):
    """Get active theme for company"""
    try:
        if not company:
            company = frappe.defaults.get_user_default("Company")
        
        # Get company-specific theme
        theme = frappe.db.get_value(
            "Enhanced Theme Manager",
            {
                "is_active": 1,
                "company_specific": 1
            },
            ["name", "theme_name", "primary_color", "secondary_color", "custom_css"],
            as_dict=True
        )
        
        if not theme:
            # Get default theme
            theme = frappe.db.get_value(
                "Enhanced Theme Manager",
                {"is_default": 1},
                ["name", "theme_name", "primary_color", "secondary_color", "custom_css"],
                as_dict=True
            )
        
        return theme or {}
        
    except Exception as e:
        frappe.log_error(f"Error getting company theme: {str(e)}", "Theme Manager")
        return {}

def apply_user_theme():
    """Apply theme on user login"""
    try:
        if frappe.session.user == "Guest":
            return
        
        theme = get_company_theme()
        if theme:
            # Set theme in session
            frappe.local.response["theme"] = theme
            
    except Exception as e:
        frappe.log_error(f"Error applying user theme: {str(e)}", "Theme Manager")

import frappe

@frappe.whitelist()
def get_active_theme():
    return {
        "theme_class": "default-theme",
        "css_file": "/files/default-theme.css",
        "custom_css": "",
        "custom_js": "console.log('Custom theme loaded');"
    }


def cleanup_old_theme_files():
    """Clean up old theme files"""
    try:
        # Get themes older than 30 days that are not active
        old_themes = frappe.get_all(
            "Enhanced Theme Manager",
            filters={
                "is_active": 0,
                "creation": ["<", frappe.utils.add_days(frappe.utils.now(), -30)]
            },
            fields=["name", "theme_file_path"]
        )
        
        for theme in old_themes:
            if theme.theme_file_path and os.path.exists(theme.theme_file_path):
                os.remove(theme.theme_file_path)
                frappe.db.set_value("Enhanced Theme Manager", theme.name, "theme_file_path", "")
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error cleaning up theme files: {str(e)}", "Theme Manager")