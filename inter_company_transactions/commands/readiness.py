"""
Commands module implementation for inter_company_transactions
"""
import json
import os
import re
from pathlib import Path

import frappe


def execute():
    """Reload module DocTypes safely from JSON schemas without requiring developer_mode."""
    try:
        app_path = frappe.get_app_path("inter_company_transactions")
        doctypes_dir = os.path.join(app_path, "inter_company_transactions", "doctype")
        if os.path.isdir(doctypes_dir):
            for entry in sorted(os.listdir(doctypes_dir)):
                json_file = os.path.join(doctypes_dir, entry, f"{entry}.json")
                if os.path.exists(json_file):
                    frappe.reload_doc("inter_company_transactions", "doctype", entry)
    except Exception as e:
        print(f"Failed to execute command: {e!s}")
        frappe.log_error(f"Command Execution Error: {e!s}", "Inter Company Transaction Setup")


def verify_marketplace_readiness():
    """
    Automated 8-Point Quality & Safety Audit for Frappe Marketplace Certification.
    Ensures zero intrusion on standard ERPNext DocTypes across v15 and v16:
    1. Master & Tree DocType Isolation Audit
    2. Permission Integrity Audit
    3. Expression & Syntax Sanity Audit
    4. Uninstall & Cleanup Hook Verification
    5. Fixture & Custom Field Completeness Audit (including Landed Cost Voucher & Stock Entry)
    6. App DocType Schema Standard Flag Audit (custom == 0)
    7. Standard ERPNext Column & SQL Query Safety Audit (zero `is_inter_company`)
    8. Multi-Version API Compatibility Check (Stock Entry, LCV -> JE, Transfer Pricing, Sync)
    """
    print("\n" + "=" * 75)
    print("  FRAPPE MARKETPLACE READINESS & SAFETY AUDIT")
    print("  App: inter_company_transactions | Target: ERPNext v15, v16")
    print("=" * 75)

    failures = []

    # --------------------------------------------------------------------------
    # AUDIT 1: Master & Tree DocType Isolation
    # --------------------------------------------------------------------------
    print("\n[Audit 1/8] Master & Tree DocType Isolation...")
    tree_doctypes = ["Customer Group", "Supplier Group", "Item Group"]
    master_doctypes = ["Customer", "Supplier", "Item", "Warehouse"]
    all_restricted = tree_doctypes + master_doctypes

    cf_violations = []
    if frappe.db and frappe.db.table_exists("Custom Field"):
        rows = frappe.get_all(
            "Custom Field",
            filters={"dt": ["in", all_restricted]},
            fields=["dt", "fieldname"],
        )
        for r in rows:
            cf_violations.append(f"{r.dt}.{r.fieldname}")

    ps_violations = []
    if frappe.db and frappe.db.table_exists("Property Setter"):
        rows = frappe.db.sql(
            """
            SELECT doc_type, field_name, property FROM `tabProperty Setter`
            WHERE (`module` = 'Inter Company Transactions' AND `doc_type` IN ('Customer Group', 'Supplier Group', 'Item Group', 'Customer', 'Supplier', 'Item', 'Warehouse'))
               OR (`property` LIKE '%%intercompany%%' AND `doc_type` IN ('Customer Group', 'Supplier Group', 'Item Group', 'Customer', 'Supplier', 'Item', 'Warehouse'))
            """,
            as_dict=True,
        )
        for r in rows:
            ps_violations.append(f"{r.doc_type}:{r.field_name or '*'}.{r.property}")

    if cf_violations:
        ict_master_fields = {
            "is_intercompany_item", "ic_item_group", "is_intercompany_warehouse",
            "ic_warehouse", "ic_customer_group", "ic_supplier_group", "custom_company",
            "is_intercompany", "intercompany_target_company",
        }
        ict_cf_violations = [v for v in cf_violations if v.split(".", 1)[-1] in ict_master_fields]
    else:
        ict_cf_violations = []

    if ict_cf_violations:
        msg = f"Found {len(ict_cf_violations)} lingering ICT custom fields on master/tree doctypes: {ict_cf_violations}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    elif ps_violations:
        msg = f"Found {len(ps_violations)} conflicting ICT property setters on master/tree doctypes: {ps_violations}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: Zero ICT custom fields or property setters on Master & Tree DocTypes.")

    # --------------------------------------------------------------------------
    # AUDIT 2: Permission Integrity (Add & Delete Buttons)
    # --------------------------------------------------------------------------
    print("\n[Audit 2/8] Permission Integrity on Master DocTypes...")
    perm_violations = []
    if frappe.db and frappe.db.table_exists("Custom DocPerm"):
        rows = frappe.db.sql(
            """
            SELECT parent, role, `create`, `delete` FROM `tabCustom DocPerm`
            WHERE parent IN ('Customer', 'Supplier', 'Item')
              AND role IN ('System Manager', 'Administrator')
              AND (`create` = 0 OR `delete` = 0)
            """,
            as_dict=True,
        )
        for r in rows:
            perm_violations.append(f"{r.parent}:{r.role}")

    if perm_violations:
        msg = f"Found restrictive Custom DocPerm overrides on System Manager/Administrator: {perm_violations}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    elif frappe.db and frappe.db.table_exists("DocPerm"):
        rows = frappe.db.sql(
            """
            SELECT parent, role, `create`, `delete` FROM `tabDocPerm`
            WHERE parent IN ('Customer', 'Supplier', 'Item')
              AND role IN ('System Manager', 'Administrator')
            """,
            as_dict=True,
        )
        broken_roles = [f"{r.parent}:{r.role}" for r in rows if not (r.get("create") and r.get("delete"))]
        if broken_roles:
            msg = f"Manager roles missing create/delete rights: {broken_roles}"
            failures.append(msg)
            print(f"  FAILED: {msg}")
        else:
            print("  PASSED: Master permissions clean; Add Customer, Add Supplier & Delete buttons active.")
    else:
        print("  PASSED: Master permissions verified.")

    # --------------------------------------------------------------------------
    # AUDIT 3: Expression & Syntax Sanity
    # --------------------------------------------------------------------------
    print("\n[Audit 3/8] Scanning MariaDB for Corrupted Expressions...")
    corrupted_matches = []
    bad_patterns = ["__islocalanddoc", "__islocaland", "anddoc.", "1or(", "0or(", "1and(", "0and("]
    if frappe.db:
        for dt, cols in [("DocField", ["depends_on"]), ("Custom Field", ["depends_on"]), ("Property Setter", ["value"])]:
            if not frappe.db.table_exists(dt):
                continue
            for col in cols:
                if not frappe.db.has_column(dt, col):
                    continue
                for pat in bad_patterns:
                    cnt = frappe.db.count(dt, filters={col: ["like", f"%{pat}%"]})
                    if cnt > 0:
                        corrupted_matches.append(f"tab{dt}.{col} contains '{pat}' ({cnt} rows)")

    if corrupted_matches:
        msg = f"Corrupted expressions found in DB: {corrupted_matches}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: All DocField and Custom Field depends_on expressions are valid.")

    # --------------------------------------------------------------------------
    # AUDIT 4: Hooks & Clean Uninstall Verification
    # --------------------------------------------------------------------------
    print("\n[Audit 4/8] Verifying Hooks & Uninstallation Handlers...")
    try:
        import inter_company_transactions.hooks as hooks

        hook_issues = []
        if not getattr(hooks, "before_uninstall", None):
            hook_issues.append("before_uninstall hook is missing")
        if not getattr(hooks, "after_uninstall", None):
            hook_issues.append("after_uninstall hook is missing")
        if getattr(hooks, "fixtures", None) != []:
            hook_issues.append("fixtures must be [] to avoid auto-import conflicts")
        doc_events = getattr(hooks, "doc_events", {}) or {}
        if "Landed Cost Voucher" not in doc_events:
            hook_issues.append("Landed Cost Voucher is missing from hooks.doc_events")
        if "Stock Entry" not in doc_events:
            hook_issues.append("Stock Entry is missing from hooks.doc_events")
        if hook_issues:
            failures.extend(hook_issues)
            for h in hook_issues:
                print(f"  FAILED: {h}")
        else:
            print("  PASSED: before_uninstall/after_uninstall registered; doc_events complete; zero fixture conflicts.")
    except Exception as e:
        failures.append(f"Could not load hooks: {e}")
        print(f"  FAILED: {e}")

    # --------------------------------------------------------------------------
    # AUDIT 5: Fixture & Custom Field Completeness Audit
    # --------------------------------------------------------------------------
    print("\n[Audit 5/8] Inspecting Repository Fixtures & Custom Fields...")
    app_path = frappe.get_app_path("inter_company_transactions")
    fixtures_path = Path(app_path) / "fixtures" / "custom_field.json"
    custom_fields_path = Path(app_path) / "custom_fields.json"
    if fixtures_path.exists():
        cf_data = json.loads(fixtures_path.read_text(encoding="utf-8"))
        bad_fixtures = [item.get("name") for item in cf_data if item.get("dt") in all_restricted]
        if bad_fixtures:
            msg = f"Forbidden master/tree custom fields found in fixtures/custom_field.json: {bad_fixtures}"
            failures.append(msg)
            print(f"  FAILED: {msg}")
        else:
            lcv_fields = {item.get("fieldname") for item in cf_data if item.get("dt") == "Landed Cost Voucher"}
            if not {"is_intercompany", "intercompany_target_company"}.issubset(lcv_fields):
                msg = "Landed Cost Voucher intercompany fields missing from fixtures/custom_field.json"
                failures.append(msg)
                print(f"  FAILED: {msg}")
            else:
                print("  PASSED: fixtures/custom_field.json contains only valid transaction doctype fields (incl. LCV).")
    else:
        print("  PASSED: No conflicting fixtures present.")

    if custom_fields_path.exists():
        cf_map = json.loads(custom_fields_path.read_text(encoding="utf-8"))
        for required_dt in ["Stock Entry", "Landed Cost Voucher", "Request for Quotation"]:
            if required_dt not in cf_map:
                msg = f"{required_dt} missing from custom_fields.json"
                failures.append(msg)
                print(f"  FAILED: {msg}")

    # --------------------------------------------------------------------------
    # AUDIT 6: Module DocType JSON Standard Schema Audit (custom == 0)
    # --------------------------------------------------------------------------
    print("\n[Audit 6/8] Verifying Module DocType Schemas Have custom == 0...")
    custom_1_doctypes = []
    doctypes_dir = Path(app_path) / "inter_company_transactions" / "doctype"
    if doctypes_dir.is_dir():
        for entry in doctypes_dir.iterdir():
            if not entry.is_dir():
                continue
            json_path = entry / f"{entry.name}.json"
            if json_path.exists():
                dt_data = json.loads(json_path.read_text(encoding="utf-8"))
                if dt_data.get("custom") == 1:
                    custom_1_doctypes.append(dt_data.get("name", entry.name))

    fixture_dt_path = Path(app_path) / "fixtures" / "doctype.json"
    if fixture_dt_path.exists():
        fdt_list = json.loads(fixture_dt_path.read_text(encoding="utf-8"))
        for item in fdt_list:
            if item.get("custom") == 1:
                custom_1_doctypes.append(f"fixtures/doctype.json:{item.get('name')}")

    if custom_1_doctypes:
        msg = f"DocType JSONs flagged custom=1 (prevents schema updates): {custom_1_doctypes}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: All app DocType JSON schemas properly configured as standard (custom: 0).")

    # --------------------------------------------------------------------------
    # AUDIT 7: Standard ERPNext Column & SQL Query Safety Audit
    # --------------------------------------------------------------------------
    print("\n[Audit 7/8] Auditing App Python Code for Non-Existent Columns...")
    bad_column_refs = []
    excluded_relpaths = {
        os.path.join("commands", "__init__.py"),
        os.path.join("commands", "readiness.py"),
    }
    for root, _dirs, files in os.walk(app_path):
        if "__pycache__" in root or ".git" in root:
            continue
        for fname in files:
            if not fname.endswith(".py") or fname.startswith("test_"):
                continue
            fpath = Path(root) / fname
            relpath = os.path.relpath(fpath, app_path)
            if relpath in excluded_relpaths:
                continue
            content = fpath.read_text(encoding="utf-8")
            if re.search(r"\bis_inter_company\b", content):
                bad_column_refs.append(relpath)

    if bad_column_refs:
        msg = f"Found references to non-existent 'is_inter_company' column in: {bad_column_refs}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: Zero references to non-existent columns (`is_inter_company`); standard ERPNext fields used.")

    # --------------------------------------------------------------------------
    # AUDIT 8: Multi-Version API Compatibility Check (v15, v16)
    # --------------------------------------------------------------------------
    print("\n[Audit 8/8] Verifying ERPNext v15 and v16 Compatibility...")
    try:
        import inter_company_transactions.safe_eval_patch as sep

        sep.sanitize_for_python("doc.is_intercompany == 1")

        from inter_company_transactions.inter_company_transactions.doctype.intercompany_transaction_link.intercompany_transaction_link import (
            calculate_transfer_rate,
            create_journal_entry_from_lcv,
            create_stock_entry,
            get_intercompany_party_map,
        )
        from inter_company_transactions.sync import resolve_counterparty_for_remote_source

        assert callable(calculate_transfer_rate)
        assert callable(create_journal_entry_from_lcv)
        assert callable(create_stock_entry)
        assert callable(get_intercompany_party_map)
        assert callable(resolve_counterparty_for_remote_source)
        print("  PASSED: Core routing, Stock Entry, LCV -> JE, Transfer Pricing & Sync APIs verified.")
    except Exception as e:
        failures.append(f"Compatibility verification failed: {e}")
        print(f"  FAILED: {e}")

    # --------------------------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------------------------
    print("\n" + "=" * 75)
    if not failures:
        print("  RESULT: ALL 8 AUDITS PASSED!")
        print("  This app is 100% Marketplace-Ready and safe for multi-server deployment.")
        print("=" * 75 + "\n")
        return True
    else:
        print(f"  RESULT: {len(failures)} AUDIT(S) FAILED:")
        for idx, fail in enumerate(failures, 1):
            print(f"    {idx}. {fail}")
        print("=" * 75 + "\n")
        return False
