# Implementation Plan: Clean Uninstall, Database Expression Repair & Tree View Fix

## Status: COMPLETED

### Root Cause Analysis
1. **Invalid "depends_on" Expression (`doc.__islocalanddoc.is_stock_item`)**:
   - In standard ERPNext `Item`, the `opening_stock` field has expression `eval:(doc.__islocal && doc.is_stock_item && !doc.has_serial_no && !doc.has_batch_no)`.
   - On the user's database, an earlier replacement had inadvertently merged `doc.__islocal` and `doc` into `doc.__islocalanddoc`.
   - While the app was installed, client-side hooks suppressed the unhandled error. Once uninstalled, standard Frappe Desk threw `Uncaught Error: Invalid depends_on expression` on `Item` and related forms, crashing the form lifecycle before primary action and menu buttons ("Delete", "New", "Actions") could render.
2. **Missing `before_uninstall` and `after_uninstall` Hooks**:
   - Frappe relies on `before_uninstall` in `hooks.py` to wipe app-specific custom fields, property setters, and permissions.
   - Without this hook, uninstallation left orphaned custom fields on `Customer`, `Supplier`, `Customer Group`, `Supplier Group`, `Item`, `Warehouse`, etc.
3. **Tree DocTypes Dirtied by Obsolete Custom Fields**:
   - `Customer Group` and `Supplier Group` had custom field `custom_company` inserted.
   - In ERPNext, Tree DocTypes load nodes in tree mode. An orphaned custom field dirtied the model (`frm.is_dirty() = true`), which caused Frappe Desk to replace the tree action buttons ("Add Child", "Delete") with the persistent blue "Save" button.

### Solutions Implemented
1. **Migration Patch `v1_5_repair_item_depends_on_and_clean_trees` & `diagnose_and_heal.py`**:
   - Added patch `inter_company_transactions.patches.v1_5_repair_item_depends_on_and_clean_trees` to `patches.txt`.
   - Wired to run automatically on `bench migrate`, `after_install`, and `before/after_uninstall`.
   - Permanently repairs `__islocalanddoc` -> `__islocal && doc` in MariaDB text columns and in `.json` schema files on disk in `apps/` before reloading doctypes.
   - Restores missing `+ Add Customer`, `+ Add Supplier`, and `Delete` buttons by wiping restrictive `tabCustom DocPerm` overrides and ensuring Manager roles have `create: 1` and `delete: 1`.
   - Resolves the persistent "Save" button on Tree DocTypes (`Supplier Group`, `Customer Group`, `Item Group`) by purging orphaned custom fields and conflicting property setters.
2. **Pruned Fixtures & Custom Fields (`fixtures/`, `custom_fields.json`, `install.py`)**:
   - Removed all master doctypes and tree doctypes from fixtures and custom field definitions so only transaction doctypes have intercompany fields.
3. **Comprehensive App Uninstall Hooks (`uninstall.py`)**:
   - Hardened `before_uninstall` and `after_uninstall` to run `run_full_healing()`, drops all ICT fields and property setters, and cleans master permissions.
4. **Resilient Non-Throwing Client-Side Protection (`inter_company_common.js`)**:
   - Replaced `evaluate_depends_on_value` and `frappe.utils.eval` with a safe, non-throwing evaluation function that never invokes `frappe.throw`, guaranteeing form headers and action buttons always render.
5. **Standalone Console & Runner Script (`repair_site.py`)**:
   - Created `repair_site.py` for direct execution via `bench --site <site> run-script repair_site.py` or via `bench console` even when the app is uninstalled.


