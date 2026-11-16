"""
Expression Sanitization Utility for Inter-Company Transactions
Translates JS-style conditional expressions cleanly to valid Python syntax
without modifying or monkey-patching any core Frappe functions.
"""
import re


def sanitize_for_python(code):
	"""
	Sanitizes expression strings to ensure valid Python syntax when evaluated.
	"""
	if not isinstance(code, str):
		return code

	cleaned = code.strip()
	if cleaned.startswith("eval:"):
		cleaned = cleaned[5:].strip()

	if "function(" in cleaned or "frappe.ui" in cleaned or "frm.call" in cleaned:
		return "False"

	cleaned = cleaned.replace("===", "==").replace("!==", "!=")
	cleaned = cleaned.replace("__islocalanddoc", "__islocal and doc")
	cleaned = cleaned.replace("__islocaland", "__islocal and ")
	cleaned = re.sub(r"\banddoc\.", " and doc.", cleaned)

	# Fix glued 'or' and 'and' operators (e.g. 1or(, )or(, or(, 1and(, reference_typeand!in_list)
	cleaned = re.sub(r"([a-zA-Z0-9_\)])or!(?!=)", r"\1 or not ", cleaned)
	cleaned = re.sub(r"([a-zA-Z0-9_\)])and!(?!=)", r"\1 and not ", cleaned)
	cleaned = re.sub(r"(\d)\s*or\s*(?=[(\w])", r"\1 or ", cleaned)
	cleaned = re.sub(r"(\))\s*or\s*(?=[(\w])", r"\1 or ", cleaned)
	cleaned = re.sub(r"\bor\s*\(", r"or (", cleaned)
	cleaned = re.sub(r"(\d)\s*and\s*(?=[(\w])", r"\1 and ", cleaned)
	cleaned = re.sub(r"(\))\s*and\s*(?=[(\w])", r"\1 and ", cleaned)
	cleaned = re.sub(r"\band\s*\(", r"and (", cleaned)

	# Convert JS operators to Python
	cleaned = re.sub(r"\s*&&\s*", " and ", cleaned)
	cleaned = re.sub(r"\s*\|\|\s*", " or ", cleaned)
	cleaned = re.sub(r"!\s*(?=[a-zA-Z_\(\[])", "not ", cleaned)

	# Convert JS literals to Python
	cleaned = re.sub(r"\btrue\b", "True", cleaned)
	cleaned = re.sub(r"\bfalse\b", "False", cleaned)
	cleaned = re.sub(r"\bnull\b", "None", cleaned)

	return cleaned
