import frappe
from frappe.utils import nowdate, getdate
from frappe import _
from datetime import timedelta

def validate_backdate(doc, method):
    current_user = frappe.session.user
    today = getdate(nowdate())

    # ? Allow Administrator to post any date
    if current_user == "Administrator":
        return

    # ? Get posting date (supports both posting_date or transaction_date)
    posting_date = getattr(doc, 'posting_date', None) or getattr(doc, 'transaction_date', None)
    if not posting_date:
        return

    posting_date = getdate(posting_date)

    # ? Block future-dated entries for all non-admin users
    if posting_date > today:
        frappe.throw(_("Future-dated {0} entries are not allowed. Use today's date only.").format(doc.doctype))

    # ? Allow sysdate (today) for everyone
    if posting_date == today:
        return

    # ? For backdated entry, check whitelist
    whitelist = frappe.get_all(
        "Backdate Whitelist",
        filters={"user": current_user},
        fields=["name"]
    )

    if not whitelist:
        frappe.throw(_("You are not allowed to post backdated documents for {0}. Use today's date.").format(doc.doctype))

    # ? Find allowed backdate days for this doctype
    whitelist_doc = frappe.get_doc("Backdate Whitelist", whitelist[0].name)
    allowed_days = 0

    for row in whitelist_doc.c_doctype:
        if row.back_doctype == doc.doctype:
            allowed_days = row.allowed_days
            break

    if allowed_days == 0:
        frappe.throw(_("You are not allowed to backdate {0} documents. Use today's date.").format(doc.doctype))

    # ? Check if posting date is within allowed range
    earliest_allowed_date = today - timedelta(days=allowed_days)
    if posting_date < earliest_allowed_date:
        frappe.throw(
            _("Backdate limit exceeded. You can only post {0} documents backdated up to {1} day(s) ago.").format(
                doc.doctype, allowed_days
            )
        )
