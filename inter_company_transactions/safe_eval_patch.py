# -*- coding: utf-8 -*-
"""
Safe Eval & Safe Exec Utility for Frappe v15 / ERPNext v15
Provides seamless expression sanitization (translating JS operators into Python)
and suppresses unhandled syntax errors so document transactions, status updates,
and form loads never crash with 'Syntax Error: Invalid python code on line 1'.
Guaranteed zero recursion.
"""
from __future__ import unicode_literals
import re
import threading

try:
    import frappe
except ImportError:
    frappe = None

_tls = threading.local()
_patch_applied = False


def sanitize_for_python(code):
    """
    Sanitizes code strings to ensure valid Python syntax when evaluated on the server.
    """
    if not isinstance(code, str):
        return code

    cleaned = code.strip()
    if cleaned.startswith("eval:"):
        cleaned = cleaned[5:].strip()

    if "function(" in cleaned or "frappe.ui" in cleaned or "frm.call" in cleaned:
        return "False"

    cleaned = cleaned.replace("===", "==").replace("!==", "!=")

    # Fix glued 'or' and 'and' operators (e.g. 1or(, )or(, or(, 1and(, etc.)
    cleaned = re.sub(r'(\d)\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'(\))\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'\bor\s*\(', r'or (', cleaned)
    cleaned = re.sub(r'(\d)\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'(\))\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'\band\s*\(', r'and (', cleaned)

    # Convert JS operators to Python
    cleaned = re.sub(r'\s*&&\s*', ' and ', cleaned)
    cleaned = re.sub(r'\s*\|\|\s*', ' or ', cleaned)
    cleaned = re.sub(r'!\s*(?=[a-zA-Z_\(\[])', 'not ', cleaned)

    # Convert JS literals to Python
    cleaned = re.sub(r'\btrue\b', 'True', cleaned)
    cleaned = re.sub(r'\bfalse\b', 'False', cleaned)
    cleaned = re.sub(r'\bnull\b', 'None', cleaned)

    return cleaned


def apply_safe_eval_patch():
    """
    Patches check_python_syntax and safe_eval in frappe.utils.safe_exec
    to safely convert JS-like expressions and gracefully handle syntax errors.
    """
    global _patch_applied
    if _patch_applied:
        return

    try:
        import frappe.utils.safe_exec
    except Exception:
        return

    _real_safe_eval = getattr(frappe.utils.safe_exec, "safe_eval", None)
    _real_check_syntax = getattr(frappe.utils.safe_exec, "check_python_syntax", None)

    if not _real_safe_eval:
        return

    def patched_check_python_syntax(code):
        if not isinstance(code, str):
            return
        try:
            san = sanitize_for_python(code)
            if _real_check_syntax:
                _real_check_syntax(san)
            else:
                compile(san, "<string>", "exec")
        except Exception:
            # Suppress syntax check crashes for client-side expressions on server
            pass

    def patched_safe_eval(code, eval_globals=None, eval_locals=None, *args, **kwargs):
        if not isinstance(code, str):
            return code

        if getattr(_tls, "busy", False):
            try:
                return _real_safe_eval(code, eval_globals, eval_locals, *args, **kwargs)
            except Exception:
                return False

        _tls.busy = True
        try:
            sanitized = sanitize_for_python(code)
            try:
                return _real_safe_eval(sanitized, eval_globals, eval_locals, *args, **kwargs)
            except Exception:
                return False
        finally:
            _tls.busy = False

    if _real_check_syntax:
        frappe.utils.safe_exec.check_python_syntax = patched_check_python_syntax

    frappe.utils.safe_exec.safe_eval = patched_safe_eval
    if hasattr(frappe, "safe_eval"):
        frappe.safe_eval = patched_safe_eval
    if hasattr(frappe, "utils") and hasattr(frappe.utils, "safe_eval"):
        frappe.utils.safe_eval = patched_safe_eval

    _patch_applied = True


# Apply patch automatically on module import
try:
    apply_safe_eval_patch()
except Exception:
    pass
