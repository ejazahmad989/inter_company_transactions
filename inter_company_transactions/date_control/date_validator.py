import frappe
from frappe import _
from frappe.utils import nowdate, getdate, date_diff
from frappe.utils.data import cint

import frappe
from frappe.utils import getdate, nowdate

def validate_transaction_date(doc, method=None):
    tx_date = getdate(doc.posting_date or doc.transaction_date or doc.date)
    today = getdate(nowdate())

    permissions = get_strict_user_permissions(doc.doctype)
    if not permissions:
        if tx_date == today:
            return
        else:
            frappe.throw("You don't have date modification permissions for this document type on this date.")

    # ? Administrator bypass: allow all dates
    if frappe.session.user == "Administrator":
        return
    
    # Allow today's date unconditionally
    if tx_date == today:
        return

    # Backdated Entry
    if tx_date < today:
        if not permissions.get("allow_backdated"):
            frappe.throw("You are not allowed to make backdated entries for this document type.")
        max_days = permissions.get("max_backdated_days", 0)
        if (today - tx_date).days > max_days:
            frappe.throw(f"You can only backdate up to {max_days} day(s).")
        if permissions.get("require_backdate_reason") and not getattr(doc, "backdate_reason", None):
            frappe.throw("Backdate Reason is required.")

    # Future-dated Entry
    elif tx_date > today:
        if not permissions.get("allow_futuredated"):
            frappe.throw("You are not allowed to make future-dated entries for this document type.")
        max_days = permissions.get("max_futuredated_days", 0)
        if (tx_date - today).days > max_days:
            frappe.throw(f"You can only future-date up to {max_days} day(s).")
        if permissions.get("require_futuredate_reason") and not getattr(doc, "futuredate_reason", None):
            frappe.throw("Future Date Reason is required.")


def enforce_backdate_restrictions(doc, permissions, doc_date, today):
    """Strict enforcement of backdate rules"""
    if not cint(permissions.get("allow_backdated")):
        frappe.throw(_("Backdated transactions are disabled for your account"))

    max_days = cint(permissions.get("max_backdated_days", 0))
    if max_days <= 0:
        frappe.throw(_("Your backdate allowance has expired"))

    days_diff = (today - doc_date).days
    if days_diff > max_days:
        frappe.throw(_(
            f"Backdate limit exceeded: {max_days} day(s) allowed. "
            f"Selected date {doc_date} is {days_diff} days before today."
        ))

    if cint(permissions.get("require_backdate_reason")) and not doc.get("backdate_reason"):
        frappe.throw(_("Backdate reason is required"))

import frappe
from frappe.utils import getdate, nowdate

def get_strict_user_permissions(doctype):
    # Administrator has full access
    if frappe.session.user == "Administrator":
        return {
            "allow_backdated": 1,
            "max_backdated_days": 10000,
            "require_backdate_reason": 0,
            "allow_futuredated": 1,
            "max_futuredated_days": 10000,
            "require_futuredate_reason": 0,
            "require_expiry_date": 0,
            "expiry_date_field": None
        }

    today = getdate(nowdate())

    # Fetch permission record valid for today
    permission_name = frappe.db.sql("""
        SELECT name FROM `tabUser Date Permission`
        WHERE user = %s
        AND enabled = 1
        AND (valid_from IS NULL OR valid_from <= %s)
        AND (valid_until IS NULL OR valid_until >= %s)
        LIMIT 1
    """, (frappe.session.user, today, today), as_dict=True)

    if not permission_name:
        return None

    permission_name = permission_name[0].name

    # Fetch relevant child table entry for this doctype
    detail = frappe.db.get_value("Date Permission Detail", {
        "parent": permission_name,
        "Form": doctype
    }, [
        "allow_backdated",
        "max_backdated_days",
        "require_backdate_reason",
        "allow_futuredated",
        "max_futuredated_days",
        "require_futuredate_reason",
        "require_expiry_date",
        "expiry_date_field"
    ], as_dict=True)

    return detail

def get_primary_date(doc):
    """Get the primary date field from document"""
    for field in ["posting_date", "transaction_date", "date", "schedule_date"]:
        if doc.get(field):
            return doc.get(field)
    return None