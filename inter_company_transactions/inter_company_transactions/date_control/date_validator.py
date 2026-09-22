import frappe
from frappe import _
from frappe.utils import nowdate, getdate, date_diff
from frappe.utils.data import cint


def get_primary_date(doc):
    """Get the primary date field from document safely without throwing AttributeError"""
    for field in ["posting_date", "transaction_date", "date", "schedule_date"]:
        val = doc.get(field) if hasattr(doc, "get") else getattr(doc, field, None)
        if val:
            return val
    return None


def validate_transaction_date(doc, method=None):
    try:
        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import fix_legacy_custom_fields
        fix_legacy_custom_fields()
    except Exception:
        pass

    # Administrator bypass: allow all dates immediately
    if frappe.session.user == "Administrator":
        return

    raw_date = get_primary_date(doc)
    if not raw_date:
        return

    tx_date = getdate(raw_date)
    today = getdate(nowdate())

    # Allow today's date unconditionally
    if tx_date == today:
        return

    permissions = get_strict_user_permissions(doc.doctype)
    if not permissions:
        # Check if the feature is even configured/enabled in this site
        has_active_policy = frappe.db.get_value("User Date Permission", {"enabled": 1}, "name")
        if not has_active_policy:
            return

        frappe.throw(_("You don't have date modification permissions for {0} on this date ({1}).").format(doc.doctype, tx_date))

    # Backdated Entry
    if tx_date < today:
        if not permissions.get("allow_backdated"):
            frappe.throw(_("You are not allowed to make backdated entries for {0}.").format(doc.doctype))
        max_days = cint(permissions.get("max_backdated_days", 0))
        if (today - tx_date).days > max_days:
            frappe.throw(_("You can only backdate up to {0} day(s).").format(max_days))
        if permissions.get("require_backdate_reason") and not doc.get("backdate_reason"):
            frappe.throw(_("Backdate Reason is required."))

    # Future-dated Entry
    elif tx_date > today:
        if not permissions.get("allow_futuredated"):
            frappe.throw(_("You are not allowed to make future-dated entries for {0}.").format(doc.doctype))
        max_days = cint(permissions.get("max_futuredated_days", 0))
        if (tx_date - today).days > max_days:
            frappe.throw(_("You can only future-date up to {0} day(s).").format(max_days))
        if permissions.get("require_futuredate_reason") and not doc.get("futuredate_reason"):
            frappe.throw(_("Future Date Reason is required."))


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

    # Fetch relevant child table entry for this doctype (check target_doctype then Form)
    detail = None
    try:
        detail = frappe.db.get_value("Date Permission Detail", {
            "parent": permission_name,
            "target_doctype": doctype
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
    except Exception:
        pass

    if not detail:
        try:
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
        except Exception:
            pass

    return detail
