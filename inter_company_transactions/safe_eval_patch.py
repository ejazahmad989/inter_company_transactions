# -*- coding: utf-8 -*-
"""
Safe Eval & Safe Exec Utility for Frappe v15 / ERPNext v15
Provides expression sanitization without monkey-patching Frappe core,
preventing any recursion errors or interference with ERPNext standard evaluation.
"""
from __future__ import unicode_literals
import re

try:
    import frappe
except ImportError:
    frappe = None


def sanitize_expression(code):
    """
    Sanitizes code strings to ensure valid Python syntax if needed.
    """
    if not isinstance(code, str):
        return code

    cleaned = code.strip()
    if cleaned.startswith("eval:"):
        cleaned = cleaned[5:].strip()

    if "function(" in cleaned or "frappe.ui" in cleaned or "frm.call" in cleaned:
        return ""

    cleaned = cleaned.replace("===", "==").replace("!==", "!=")
    cleaned = re.sub(r'(\d)\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'(\))\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'\bor\s*\(', r'or (', cleaned)
    cleaned = re.sub(r'(\d)\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'(\))\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'\band\s*\(', r'and (', cleaned)
    cleaned = re.sub(r'\s*&&\s*', ' and ', cleaned)
    cleaned = re.sub(r'\s*\|\|\s*', ' or ', cleaned)
    cleaned = re.sub(r'!\s*(?=[a-zA-Z_\(\[])', 'not ', cleaned)
    cleaned = re.sub(r'\btrue\b', 'True', cleaned)
    cleaned = re.sub(r'\bfalse\b', 'False', cleaned)
    cleaned = re.sub(r'\bnull\b', 'None', cleaned)

    return cleaned


def safe_eval(code, eval_globals=None, eval_locals=None):
    """
    Safe evaluation helper for custom code that handles errors gracefully.
    """
    if not isinstance(code, str):
        return code
    if not frappe:
        return False
    try:
        sanitized = sanitize_expression(code)
        # Use native frappe safe_eval
        from frappe.utils.safe_exec import safe_eval as core_safe_eval
        return core_safe_eval(sanitized, eval_globals, eval_locals)
    except Exception:
        return False


def apply_safe_eval_patch():
    """
    Frappe v15 and ERPNext v15 core safe_eval and safe_exec are preserved
    natively without monkey-patching. This guarantees zero recursion errors.
    """
    pass
