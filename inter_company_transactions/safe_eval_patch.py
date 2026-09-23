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
import threading

try:
    import frappe
except ImportError:
    frappe = None

_patch_applied = False
_local_eval = threading.local()


def sanitize_expression(code):
    """
    Sanitizes code strings to ensure valid Python syntax:
    - Strips leading 'eval:'
    - Fixes glued logical operators (1or(, )or(, or(, )or, 1and(, etc.)
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

    # Fix glued 'or' and 'and' operators (e.g. 1or(, )or(, or(, etc.)
    cleaned = re.sub(r'(\d)\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'(\))\s*or\s*(?=[(\w])', r'\1 or ', cleaned)
    cleaned = re.sub(r'\bor\s*\(', r'or (', cleaned)
    cleaned = re.sub(r'(\d)\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'(\))\s*and\s*(?=[(\w])', r'\1 and ', cleaned)
    cleaned = re.sub(r'\band\s*\(', r'and (', cleaned)

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
    so all evaluation across the bench is protected against JS syntax, SyntaxErrors,
    and recursion errors.
    """
    global _patch_applied
    if _patch_applied:
        return

    try:
        import frappe.utils.safe_exec
    except Exception:
        return

    # Grab the ACTUAL underlying safe_eval implementation (from safe_exec, NOT the wrapper in frappe.__init__)
    orig_safe_eval = getattr(frappe.utils.safe_exec, "safe_eval", None)

    if orig_safe_eval:
        def patched_safe_eval(code, eval_globals=None, eval_locals=None, *args, **kwargs):
            if not isinstance(code, str):
                return code

            # Guard against any recursive re-entry
            if getattr(_local_eval, "active", False):
                try:
                    return orig_safe_eval(code, eval_globals, eval_locals, *args, **kwargs)
                except Exception:
                    return False

            _local_eval.active = True
            try:
                sanitized = sanitize_expression(code)
                if not sanitized:
                    return False

                try:
                    return orig_safe_eval(sanitized, eval_globals, eval_locals, *args, **kwargs)
                except SyntaxError as se:
                    frappe.logger("safe_eval_patch").warning(
                        f"safe_eval: caught SyntaxError for '{code}': {se}"
                    )
                    return False
                except Exception as e:
                    # Catch any evaluation errors (Invalid python code, NameError, AttributeError, etc.)
                    # so document submission and workflows NEVER crash on a bad status/condition expression
                    frappe.logger("safe_eval_patch").warning(
                        f"safe_eval: handled exception for '{code}': {e}"
                    )
                    return False
            finally:
                _local_eval.active = False

        # Apply patch to safe_exec module first, then top-level frappe
        frappe.utils.safe_exec.safe_eval = patched_safe_eval
        frappe.safe_eval = patched_safe_eval
        if hasattr(frappe, "utils"):
            frappe.utils.safe_eval = patched_safe_eval

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
                frappe.logger("safe_eval_patch").warning(f"safe_exec: caught error: {e}")
                return None

        frappe.utils.safe_exec.safe_exec = patched_safe_exec
        frappe.safe_exec = patched_safe_exec

    _patch_applied = True
