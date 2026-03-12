# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import json

def before_backup():
    """Execute before backup"""
    try:
        # Backup critical workflow data
        backup_workflow_data()
        
        # Backup theme configurations
        backup_theme_data()
        
        frappe.log_error("Pre-backup tasks completed", "Backup Management")
        
    except Exception as e:
        frappe.log_error(f"Error in before backup: {str(e)}", "Backup Management")

def after_backup():
    """Execute after backup"""
    try:
        # Clean up temporary files
        cleanup_backup_files()
        
        # Send backup notification
        send_backup_notification()
        
        frappe.log_error("Post-backup tasks completed", "Backup Management")
        
    except Exception as e:
        frappe.log_error(f"Error in after backup: {str(e)}", "Backup Management")

def backup_workflow_data():
    """Backup workflow data"""
    try:
        workflows = frappe.get_all(
            "Inter Company Workflow",
            fields=["*"]
        )
        
        if workflows:
            frappe.cache().set_value("backup_workflows", workflows, expires_in_sec=86400)
            
    except Exception as e:
        frappe.log_error(f"Error backing up workflow data: {str(e)}", "Backup Management")

def backup_theme_data():
    """Backup theme data"""
    try:
        themes = frappe.get_all(
            "Enhanced Theme Manager",
            fields=["*"]
        )
        
        if themes:
            frappe.cache().set_value("backup_themes", themes, expires_in_sec=86400)
            
    except Exception as e:
        frappe.log_error(f"Error backing up theme data: {str(e)}", "Backup Management")

def cleanup_backup_files():
    """Clean up backup files"""
    try:
        # Remove old cache entries
        frappe.cache().delete_value("backup_workflows")
        frappe.cache().delete_value("backup_themes")
        
    except Exception as e:
        frappe.log_error(f"Error cleaning up backup files: {str(e)}", "Backup Management")

def send_backup_notification():
    """Send backup completion notification"""
    try:
        administrators = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager"},
            fields=["parent"]
        )
        
        for admin in administrators:
            frappe.sendmail(
                recipients=[admin.parent],
                subject="Backup Completed - Inter Company Transactions",
                message="The backup process has been completed successfully.",
                reference_doctype="System Settings",
                reference_name="backup_notification"
            )
            
    except Exception as e:
        frappe.log_error(f"Error sending backup notification: {str(e)}", "Backup Management")