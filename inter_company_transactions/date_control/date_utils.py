import frappe
from frappe.utils import getdate, add_days, date_diff
from datetime import datetime, timedelta

def get_user_permissions(doctype):
    """Get all date permissions for current user and doctype"""
    permissions = frappe.get_all("User Date Permission",
        filters={"user": frappe.session.user, "enabled": 1},
        fields=["name"])
        
    if not permissions:
        return None
        
    perm_detail = frappe.get_all("Date Permission Detail",
        filters={"parent": permissions[0].name, "doctype": doctype},
        fields=["*"])
        
    if not perm_detail:
        return None
        
    return perm_detail[0]

def get_working_days_diff(start_date, end_date):
    """Calculate working days difference excluding holidays"""
    from_date = min(getdate(start_date), getdate(end_date))
    to_date = max(getdate(start_date), getdate(end_date))
    
    delta = timedelta(days=1)
    working_days = 0
    
    while from_date <= to_date:
        if not is_holiday(from_date):
            working_days += 1
        from_date += delta
    
    return working_days

def is_holiday(date):
    """Check if date is a holiday"""
    holiday_lists = frappe.get_all("Holiday List", fields=["name"])
    for holiday_list in holiday_lists:
        if frappe.db.exists("Holiday", {
            "parent": holiday_list.name,
            "holiday_date": date
        }):
            return True
    return False

def get_date_range(start_date, days):
    """Get date range excluding holidays"""
    date = getdate(start_date)
    date_list = []
    
    while len(date_list) < abs(days):
        if not is_holiday(date):
            date_list.append(date)
        
        date += timedelta(days=1) if days > 0 else timedelta(days=-1)
    
    return date_list