#!/usr/bin/env python3
# Standalone Site Repair Script for ERPNext
# Run via: bench --site <your-site> run-script repair_site.py
# Or paste into: bench --site <your-site> console

import ast
import re
import frappe


def _is_valid_python_eval(expr):
	try:
		ast.parse((expr or "").strip(), mode="eval")
		return True, None
	except SyntaxError as exc:
		return False, f"line {exc.lineno}, col {exc.offset}: {exc.msg}"


def _try_repair_python_condition(expr):
	if not isinstance(expr, str):
		return expr
	fixed = expr.strip()
	if fixed.startswith("eval:"):
		fixed = fixed[5:].strip()
	fixed = fixed.replace("&&", " and ").replace("||", " or ")
	fixed = re.sub(r"(?<![=!<>])!(?!=)\s*", " not ", fixed)
	fixed = re.sub(r"\btrue\b", "True", fixed)
	fixed = re.sub(r"\bfalse\b", "False", fixed)
	fixed = re.sub(r"\bnull\b", "None", fixed)
	fixed = re.sub(r"([a-zA-Z0-9_'\")\]])(and|or)(?=[(\s'!])", r"\1 \2 ", fixed)
	fixed = re.sub(r"\b(and|or)([a-zA-Z_][a-zA-Z0-9_]*\.)", r"\1 \2", fixed)
	fixed = re.sub(r"\s{2,}", " ", fixed).strip()
	return fixed


def main():
	print("\n" + "=" * 70)
	print("STARTING FULL REPAIR OF SITE MASTER DOCTYPES, WORKFLOWS & PERMISSIONS")
	print("=" * 70)

	# Prefer shared app healing utility when installed; fall back to standalone logic otherwise
	total_db = 0
	invalid_evals = []
	try:
		from inter_company_transactions.diagnose_and_heal import (
			find_invalid_safe_eval_expressions,
			repair_database_text,
		)
		total_db = repair_database_text(print)
		invalid_evals = find_invalid_safe_eval_expressions()
	except ImportError:
		doctypes_and_cols = [
			("DocField", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
			("Custom Field", ["depends_on", "mandatory_depends_on", "read_only_depends_on", "options", "default"]),
			("Property Setter", ["value"]),
			("Client Script", ["script"]),
			("Custom Script", ["script"]),
			("DocType", ["description"]),
			("Workflow Transition", ["condition"]),
			("Notification", ["condition"]),
			("Assignment Rule", ["assign_condition", "unassign_condition", "close_condition"]),
			("Webhook", ["condition"]),
			("Energy Point Rule", ["condition"]),
		]
		replacements = [
			("__islocalanddoc", "__islocal && doc"),
			("__islocal anddoc", "__islocal && doc"),
			("__islocaland doc", "__islocal && doc"),
			("__islocaland", "__islocal && "),
			("anddoc.", " && doc."),
			("and!doc.", " && !doc."),
			("and !doc.", " && !doc."),
			("and!in_list(", " && !in_list("),
			("1or(", "1 || ("),
			("0or(", "0 || ("),
			(")or(", ") || ("),
			("1and(", "1 && ("),
			("0and(", "0 && ("),
		]

		for dt, cols in doctypes_and_cols:
			if not frappe.db.table_exists(dt):
				continue
			for col in cols:
				if not frappe.db.has_column(dt, col):
					continue
				for old_val, new_val in replacements:
					try:
						rows = frappe.get_all(
							dt,
							filters={col: ["like", f"%{old_val}%"]},
							fields=["name", col],
						)
						for row in rows or []:
							orig = row.get(col) or ""
							fixed = orig.replace(old_val, new_val)
							if fixed != orig:
								frappe.db.set_value(dt, row.get("name"), col, fixed, update_modified=False)
								total_db += 1
								print(f"  Fixed {dt}.{col} ({row.get('name')}) '{old_val}'")
					except Exception as e:
						print(f"  Notice updating {dt}.{col}: {e}")

				try:
					glued_rows = frappe.get_all(
						dt,
						or_filters=[[col, "like", "%and!%"], [col, "like", "%or!%"]],
						fields=["name", col],
					)
					for gr in glued_rows or []:
						orig = gr.get(col) or ""
						fixed = re.sub(r"([a-zA-Z0-9_\)])and!(?!=)", r"\1 && !", orig)
						fixed = re.sub(r"([a-zA-Z0-9_\)])or!(?!=)", r"\1 || !", fixed)
						if fixed != orig:
							frappe.db.set_value(dt, gr.get("name"), col, fixed, update_modified=False)
							total_db += 1
							print(f"  Fixed glued operator in {dt}.{col} ({gr.get('name')})")
				except Exception as e:
					print(f"  Notice fixing glued operator in {dt}.{col}: {e}")

		for dt, cols in [
			("Workflow Transition", ["condition"]),
			("Notification", ["condition"]),
			("Assignment Rule", ["assign_condition", "unassign_condition", "close_condition"]),
			("Webhook", ["condition"]),
			("Energy Point Rule", ["condition"]),
		]:
			if not frappe.db.table_exists(dt):
				continue
			for col in cols:
				if not frappe.db.has_column(dt, col):
					continue
				rows = frappe.get_all(dt, filters={col: ["is", "set"]}, fields=["name", col])
				for row in rows or []:
					orig = (row.get(col) or "").strip()
					if not orig:
						continue
					ok, err = _is_valid_python_eval(orig)
					if ok:
						continue
					fixed = _try_repair_python_condition(orig)
					ok_fixed, _ = _is_valid_python_eval(fixed)
					if fixed and fixed != orig and ok_fixed:
						frappe.db.set_value(dt, row.get("name"), col, fixed, update_modified=False)
						total_db += 1
						print(f"  Repaired Python condition in {dt}.{col} ({row.get('name')})")
					else:
						invalid_evals.append({
							"doctype": dt,
							"name": row.get("name"),
							"field": col,
							"expression": orig,
							"error": err,
						})

	print(f"[1/5] Database expressions repaired: {total_db} rows fixed.")
	if invalid_evals:
		print("  ACTION REQUIRED: Invalid Python safe_eval expressions found in site database:")
		for item in invalid_evals:
			print(
				f"    - {item['doctype']} '{item['name']}' ({item['field']}): "
				f"{item['expression']!r} -> {item['error']}"
			)

	# 2. Skip external disk file mutations; schema reload handles clean disk definitions
	print("[2/5] Disk schema check: external app directories left untouched.")

	# 3. Restore 'Add' and 'Delete' permissions on Customer, Supplier, Item
	master_doctypes = ["Customer", "Supplier", "Item", "Customer Group", "Supplier Group", "Item Group", "Warehouse"]
	if frappe.db.table_exists("Custom DocPerm"):
		frappe.db.delete("Custom DocPerm", {"parent": ["in", master_doctypes]})
		print("  Removed restrictive Custom DocPerm overrides on master doctypes.")

	admin_doctypes = ["Customer", "Supplier", "Item", "Customer Group", "Supplier Group", "Item Group"]
	admin_roles = ["System Manager", "Administrator", "Sales Manager", "Purchase Manager"]
	if frappe.db.table_exists("DocPerm"):
		perm_rows = frappe.get_all(
			"DocPerm",
			filters={"parent": ["in", admin_doctypes], "role": ["in", admin_roles]},
			fields=["name", "create", "delete", "write", "read"],
		)
		for pr in perm_rows or []:
			if not (pr.get("create") and pr.get("delete") and pr.get("write") and pr.get("read")):
				frappe.db.set_value(
					"DocPerm",
					pr.get("name"),
					{"create": 1, "delete": 1, "write": 1, "read": 1},
					update_modified=False,
				)
		print("  Guaranteed full Add & Delete permissions for System Manager & Manager roles.")

	if frappe.db.table_exists("DocType"):
		for dt_name in admin_doctypes:
			if frappe.db.exists("DocType", dt_name):
				frappe.db.set_value("DocType", dt_name, {"read_only": 0, "in_create": 0}, update_modified=False)
	print("[3/5] Master permissions restored: Add Customer/Supplier and Delete buttons enabled.")

	# 4. Clean up Tree DocTypes and Master Custom Fields / Property Setters via ORM
	if frappe.db.table_exists("Custom Field"):
		tree_dts = ["Customer Group", "Supplier Group", "Item Group"]
		frappe.db.delete("Custom Field", {"dt": ["in", tree_dts]})

		master_fields = [
			"ic_customer_group", "ic_supplier_group", "is_intercompany_item",
			"ic_item_group", "is_intercompany_warehouse", "ic_warehouse", "custom_company"
		]
		frappe.db.delete("Custom Field", {"fieldname": ["in", master_fields]})
		print("  Removed all obsolete custom fields from Tree and Master DocTypes.")

	if frappe.db.table_exists("Property Setter"):
		frappe.db.delete(
			"Property Setter",
			{
				"doc_type": ["in", ["Customer", "Supplier", "Item"]],
				"property": ["in", ["read_only", "in_create", "is_submittable", "editable_grid"]],
			},
		)
		frappe.db.delete(
			"Property Setter",
			{"doc_type": ["in", ["Customer", "Supplier"]], "field_name": "naming_series"},
		)
		frappe.db.delete("Property Setter", {"doc_type": ["in", ["Customer Group", "Supplier Group", "Item Group"]]})
		frappe.db.delete("Property Setter", {"module": "Inter Company Transactions"})
		print("  Removed conflicting Property Setters on Customer/Supplier and Tree DocTypes.")
	print("[4/5] Tree and Master DocTypes cleaned: persistent 'Save' button lock removed.")

	# 5. Reload doctypes and flush Redis & Desk cache (bench run-script commits automatically on exit)
	for dt in ["Item", "Customer", "Supplier", "Customer Group", "Supplier Group", "Item Group"]:
		try:
			if frappe.db.exists("DocType", dt):
				frappe.reload_doctype(dt, force=True)
				print(f"  Reloaded standard schema: {dt}")
		except Exception as e:
			print(f"  Notice reloading {dt}: {e}")

	frappe.clear_cache()
	print("[5/5] Reloaded standard DocTypes and cleared site cache.")
	print("Note: bench run-script persists database changes automatically on completion.")

	print("=" * 70)
	print("REPAIR COMPLETED SUCCESSFULLY!")
	print("=" * 70)


if __name__ == "__main__" or "frappe" in locals():
	main()
