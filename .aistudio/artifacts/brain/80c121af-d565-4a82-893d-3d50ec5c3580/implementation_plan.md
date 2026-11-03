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
1. **Database Repair for Corrupted Expressions (`uninstall.py`, `intercompany_transaction_link.py`, `install.py`)**:
   - Implemented automated database repair function `repair_all_depends_on_expressions()` across `tabDocField`, `tabCustom Field`, and `tabProperty Setter`.
   - Directly replaces `__islocalanddoc` -> `__islocal && doc`, `__islocaland` -> `__islocal && `, `anddoc.` -> ` && doc.`, and repairs glued `or`/`and` operators.
   - Runs automatically on `after_install`, `before_migrate`, `after_migrate`, `before_uninstall`, and `after_uninstall`.
   - Enhanced client-side `sanitize_depends_on_expression` in `inter_company_common.js` to handle `__islocalanddoc` dynamically.
2. **Comprehensive App Uninstall Hooks (`uninstall.py`)**:
   - Added `inter_company_transactions/uninstall.py` with `before_uninstall()` and `after_uninstall()`.
   - Deletes all Custom Fields (`is_intercompany`, `intercompany_target_company`, `ic_customer_group`, `ic_supplier_group`, `custom_company`, etc.) and Property Setters created by the app.
   - Cleans up `tabCustom DocPerm` for ICT DocTypes.
   - Clears Frappe cache so uninstalled sites return to 100% clean standard ERPNext state.
3. **Tree View Restoration (Customer Group & Supplier Group)**:
   - Removed `Customer Group` and `Supplier Group` custom fields from `custom_fields.json` and `install.py`.
   - Added automatic removal of any existing `Customer Group-custom_company` and `Supplier Group-custom_company` in `fix_legacy_custom_fields()`.
   - Restores clean Tree view without dirty "Save" button locks.
4. **Verification**:
   - Verified Python compilation (`compileall`) with zero errors across all modules.
   - Verified container linter and compiler pass cleanly.
