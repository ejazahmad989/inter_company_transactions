# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def boot_session(bootinfo):
    """Add custom data to boot session"""
    try:
        if frappe.session.user != "Guest":
            # Add pending approvals count safely
            bootinfo["pending_approvals"] = 0
            if frappe.db.table_exists("Workflow Approval Request") and frappe.db.table_exists("Inter Company Workflow"):
                workflows = get_user_workflows()
                if workflows:
                    bootinfo["pending_approvals"] = frappe.db.count(
                        "Workflow Approval Request",
                        {
                            "status": "Pending",
                            "workflow": ["in", workflows]
                        }
                    )
            
            # Add active theme safely
            try:
                from inter_company_transactions.enhanced_theme import get_company_theme
                theme = get_company_theme()
                if theme:
                    bootinfo["active_theme"] = theme
            except Exception as te:
                frappe.log_error(f"Error getting boot active theme: {str(te)}", "Boot Session Theme")
                
    except Exception as e:
        frappe.log_error(f"Error in boot session: {str(e)}", "Boot Session")

def extend_bootinfo(bootinfo):
    """Extend bootinfo with additional data"""
    try:
        if frappe.session.user != "Guest":
            # Add workflow permissions
            bootinfo["workflow_permissions"] = get_workflow_permissions()
            
            # Add theme permissions
            bootinfo["theme_permissions"] = get_theme_permissions()
            
    except Exception as e:
        frappe.log_error(f"Error extending bootinfo: {str(e)}", "Boot Session")

def get_user_workflows():
    """Get workflows accessible to current user"""
    try:
        user_roles = frappe.get_roles()
        
        workflows = frappe.get_all(
            "Inter Company Workflow",
            filters={"enabled": 1},
            fields=["name"]
        )
        
        return [w.name for w in workflows]
        
    except:
        return []

def get_workflow_permissions():
    """Get workflow permissions for current user"""
    try:
        user_roles = frappe.get_roles()
        
        permissions = {
            "can_create_workflow": "Workflow Manager" in user_roles or "System Manager" in user_roles,
            "can_approve": "Approver" in user_roles or "System Manager" in user_roles,
            "can_manage_themes": "Theme Administrator" in user_roles or "System Manager" in user_roles
        }
        
        return permissions
        
    except:
        return {}

def get_theme_permissions():
    """Get theme permissions for current user"""
    try:
        user_roles = frappe.get_roles()
        
        permissions = {
            "can_create_theme": "Theme Administrator" in user_roles or "System Manager" in user_roles,
            "can_apply_theme": True,  # All users can apply themes
            "can_manage_company_themes": "System Manager" in user_roles
        }
        
        return permissions
        
    except:
        return {}