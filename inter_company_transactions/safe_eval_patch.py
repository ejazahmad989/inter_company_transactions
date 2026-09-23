# -*- coding: utf-8 -*-
"""
Safe Eval & Safe Exec Patch for Frappe
Intercepts evaluations to translate JavaScript-style logical expressions
(===, !==, &&, ||, !doc, true, false, null, eval:) into valid Python syntax,
and protects against unhandled SyntaxError / 'Invalid python code' crashes
during intercompany transactions and document lifecycle hooks.
"""
from __future__ import unicode_literals
import re

try:
    import frappe
except ImportError:
    frappe = None

_patch_applied = False


def sanitize_expression(code):
    """
    Sanitizes code strings to ensure valid Python syntax:
    - Strips leading 'eval:'
    - Converts JS equality (===, !==) to Python (==, !=)
    - Converts JS logical operators (&&, ||) to Python (and, or)
    - Converts JS negation (!doc, !(x)) to Python (not doc, not (x))
    - Converts JS literals (true, false, null) to Python (True, False, None)
    - Filters out raw JS functions and UI scripting
    """
    if not isinstance(code, str):
        return code

    cleaned = code.strip()
    if cleaned.startswith("eval:"):
        cleaned = cleaned[5:].strip()

    # If it is client-side JS code (such as frappe.ui or function definitions), neutralize it
    if "function(" in cleaned or "frappe.ui" in cleaned or "frm.call" in cleaned:
        return ""

    # Equality
    cleaned = cleaned.replace("===", "==").replace("!==", "!=")

    # Logical operators (surrounded by spaces or word boundaries)
    cleaned = re.sub(r'\s*&&\s*', ' and ', cleaned)
    cleaned = re.sub(r'\s*\|\|\s*', ' or ', cleaned)

    # Negation (!variable, !(expr), !doc)
    cleaned = re.sub(r'!\s*(?=[a-zA-Z_\(\[])', 'not ', cleaned)

    # Boolean and Null literals
    cleaned = re.sub(r'\btrue\b', 'True', cleaned)
    cleaned = re.sub(r'\bfalse\b', 'False', cleaned)
    cleaned = re.sub(r'\bnull\b', 'None', cleaned)

    return cleaned


def apply_safe_eval_patch():
    """
    Monkey-patches safe_eval and safe_exec in frappe and frappe.utils.safe_exec
    so all evaluation across the bench is protected against JS syntax and SyntaxErrors.
    """
    global _patch_applied
    if _patch_applied:
        return

    try:
        import frappe.utils.safe_exec
    except Exception:
        return

    # 1. Patch frappe.safe_eval
    orig_safe_eval = getattr(frappe, "safe_eval", None)
    if not orig_safe_eval and hasattr(frappe.utils.safe_exec, "safe_eval"):
        orig_safe_eval = frappe.utils.safe_exec.safe_eval

    if orig_safe_eval:
        def patched_safe_eval(code, eval_globals=None, eval_locals=None, *args, **kwargs):
            if not isinstance(code, str):
                return code

            sanitized = sanitize_expression(code)
            if not sanitized:
                return False

            try:
                return orig_safe_eval(sanitized, eval_globals, eval_locals, *args, **kwargs)
            except SyntaxError as se:
                frappe.logger("safe_eval_patch").warning(
                    f"safe_eval: caught SyntaxError for expression '{code}' (sanitized: '{sanitized}'): {se}"
                )
                return False
            except Exception as e:
                err_str = str(e)
                if "Invalid python code" in err_str or "SyntaxError" in err_str:
                    frappe.logger("safe_eval_patch").warning(
                        f"safe_eval: caught '{err_str}' for expression '{code}' (sanitized: '{sanitized}')"
                    )
                    return False
                raise

        frappe.safe_eval = patched_safe_eval
        if hasattr(frappe, "utils"):
            frappe.utils.safe_eval = patched_safe_eval
        if hasattr(frappe.utils.safe_exec, "safe_eval"):
            frappe.utils.safe_exec.safe_eval = patched_safe_eval

    # 2. Patch safe_exec
    orig_safe_exec = getattr(frappe.utils.safe_exec, "safe_exec", None)
    if orig_safe_exec:
        def patched_safe_exec(script, *args, **kwargs):
            if not isinstance(script, str):
                return None

            if "function(" in script or "frappe.ui" in script:
                return None

            sanitized = script.replace("===", "==").replace("!==", "!=")
            try:
                return orig_safe_exec(sanitized, *args, **kwargs)
            except SyntaxError as se:
                frappe.logger("safe_eval_patch").warning(f"safe_exec: caught SyntaxError: {se}")
                return None
            except Exception as e:
                if "Invalid python code" in str(e):
                    frappe.logger("safe_eval_patch").warning(f"safe_exec: caught 'Invalid python code': {e}")
                    return None
                raise

        frappe.utils.safe_exec.safe_exec = patched_safe_exec
        if hasattr(frappe, "safe_exec"):
            frappe.safe_exec = patched_safe_exec

    _patch_applied = True
