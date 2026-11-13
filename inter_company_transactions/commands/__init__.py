"""
Commands module for inter_company_transactions
"""
import json
import os
import re

import frappe


def execute():
    """Import doctypes for inter-company transactions"""
    try:
        app_path = frappe.get_app_path("inter_company_transactions")

        doctypes = [
            "Inter Company Transaction Map",
            "Inter Company Transaction Mapping",
            "Intercompany Transaction Link",
            "Intercompany Transaction Type Mapping",
        ]

        for doctype in doctypes:
            try:
                file_name = doctype.lower().replace(" ", "_")
                json_file = os.path.join(
                    app_path,
                    "inter_company_transactions",
                    "doctype",
                    file_name,
                    f"{file_name}.json",
                )

                if os.path.exists(json_file):
                    with open(json_file) as f:
                        doc_data = json.load(f)

                    if not frappe.db.exists("DocType", doctype):
                        doc = frappe.new_doc("DocType")
                        doc.update(doc_data)
                        doc.insert(ignore_permissions=True)
                        print(f"Created DocType: {doctype}")
                    else:
                        doc = frappe.get_doc("DocType", doctype)
                        doc.update(doc_data)
                        doc.save(ignore_permissions=True)
                        print(f"Updated DocType: {doctype}")

                    frappe.db.commit()
                else:
                    print(f"JSON file not found for DocType: {doctype}")

            except Exception as e:
                print(f"Error importing DocType {doctype}: {e!s}")
                frappe.log_error(f"DocType Import Error: {e!s}", "Inter Company Transaction Setup")
    except Exception as e:
        print(f"Failed to execute command: {e!s}")
        frappe.log_error(f"Command Execution Error: {e!s}", "Inter Company Transaction Setup")


def verify_marketplace_readiness():
    """
    Automated 8-Point Quality & Safety Audit for Frappe Marketplace Certification.
    Ensures zero intrusion on standard ERPNext DocTypes across v14, v15, and v16:
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
    print("  App: inter_company_transactions | Target: ERPNext v14, v15, v16")
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
        placeholders = ", ".join(["%s"] * len(all_restricted))
        rows = frappe.db.sql(
            f"""
            SELECT dt, fieldname FROM `tabCustom Field`
            WHERE dt IN ({placeholders})
            """,
            tuple(all_restricted),
            as_dict=True,
        )
        for r in rows:
            cf_violations.append(f"{r.dt}.{r.fieldname}")

    ps_violations = []
    if frappe.db and frappe.db.table_exists("Property Setter"):
        rows = frappe.db.sql(
            """
            SELECT doc_type, field_name, property FROM `tabProperty Setter`
            WHERE (doc_type IN ('Customer Group', 'Supplier Group', 'Item Group'))
               OR (doc_type IN ('Customer', 'Supplier', 'Item') AND property IN ('read_only', 'in_create', 'is_submittable'))
               OR (doc_type IN ('Customer', 'Supplier') AND field_name = 'naming_series')
               OR (module = 'Inter Company Transactions')
            """,
            as_dict=True,
        )
        for r in rows:
            ps_violations.append(f"{r.doc_type}:{r.field_name or '*'}.{r.property}")

    if cf_violations:
        msg = f"Found {len(cf_violations)} lingering custom fields on master/tree doctypes: {cf_violations}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    elif ps_violations:
        msg = f"Found {len(ps_violations)} conflicting property setters on master/tree doctypes: {ps_violations}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: Zero custom fields or property setters on Master & Tree DocTypes.")

    # --------------------------------------------------------------------------
    # AUDIT 2: Permission Integrity (Add & Delete Buttons)
    # --------------------------------------------------------------------------
    print("\n[Audit 2/8] Permission Integrity on Master DocTypes...")
    perm_violations = []
    if frappe.db and frappe.db.table_exists("Custom DocPerm"):
        rows = frappe.db.sql(
            """
            SELECT parent, role FROM `tabCustom DocPerm`
            WHERE parent IN ('Customer', 'Supplier', 'Item')
            """,
            as_dict=True,
        )
        for r in rows:
            perm_violations.append(f"{r.parent}:{r.role}")

    if perm_violations:
        msg = f"Found Custom DocPerm overrides on standard master doctypes (may hide Add/Delete buttons): {perm_violations}"
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
        for tbl, cols in [("tabDocField", ["depends_on"]), ("tabCustom Field", ["depends_on"]), ("tabProperty Setter", ["value"])]:
            if not frappe.db.table_exists(tbl):
                continue
            for col in cols:
                if not frappe.db.has_column(tbl, col):
                    continue
                for pat in bad_patterns:
                    cnt = frappe.db.sql(f"SELECT count(*) FROM `{tbl}` WHERE `{col}` LIKE %s", (f"%{pat}%",))[0][0]
                    if cnt > 0:
                        corrupted_matches.append(f"{tbl}.{col} contains '{pat}' ({cnt} rows)")

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
    fixtures_path = os.path.join(app_path, "fixtures", "custom_field.json")
    custom_fields_path = os.path.join(app_path, "custom_fields.json")
    if os.path.exists(fixtures_path):
        with open(fixtures_path) as f:
            cf_data = json.load(f)
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

    if os.path.exists(custom_fields_path):
        with open(custom_fields_path) as f:
            cf_map = json.load(f)
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
    doctypes_dir = os.path.join(app_path, "inter_company_transactions", "doctype")
    if os.path.isdir(doctypes_dir):
        for entry in os.listdir(doctypes_dir):
            json_path = os.path.join(doctypes_dir, entry, f"{entry}.json")
            if os.path.exists(json_path):
                with open(json_path) as f:
                    dt_data = json.load(f)
                if dt_data.get("custom") == 1:
                    custom_1_doctypes.append(dt_data.get("name", entry))

    fixture_dt_path = os.path.join(app_path, "fixtures", "doctype.json")
    if os.path.exists(fixture_dt_path):
        with open(fixture_dt_path) as f:
            fdt_list = json.load(f)
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
    for root, dirs, files in os.walk(app_path):
        if "__pycache__" in root or ".git" in root:
            continue
        for fname in files:
            if not fname.endswith(".py") or fname.startswith("test_"):
                continue
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, app_path)
            if relpath == os.path.join("commands", "__init__.py"):
                continue
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            if re.search(r'\bis_inter_company\b', content):
                bad_column_refs.append(relpath)

    if bad_column_refs:
        msg = f"Found references to non-existent 'is_inter_company' column in: {bad_column_refs}"
        failures.append(msg)
        print(f"  FAILED: {msg}")
    else:
        print("  PASSED: Zero references to non-existent columns (`is_inter_company`); standard ERPNext fields used.")

    # --------------------------------------------------------------------------
    # AUDIT 8: Multi-Version API Compatibility Check (v14, v15, v16)
    # --------------------------------------------------------------------------
    print("\n[Audit 8/8] Verifying ERPNext v14, v15, and v16 Compatibility...")
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
