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
1. **Migration Patch `v1_5_repair_item_depends_on_and_clean_trees` in `patches.txt`**:
   - Added patch `inter_company_transactions.patches.v1_5_repair_item_depends_on_and_clean_trees` to `patches.txt`.
   - Guaranteed to execute when running `bench migrate`, regardless of whether previous patches were already logged.
   - Permanently repairs `__islocalanddoc` -> `__islocal && doc` in `tabDocField`, `tabCustom Field`, and `tabProperty Setter`.
   - Removes all obsolete custom fields from Tree DocTypes (`Customer Group`, `Supplier Group`, `Item Group`) and Master DocTypes (`Customer`, `Supplier`, `Item`, `Warehouse`).
   - Removes intrusive property setters that modified `naming_series` on Customer and Supplier.
   - Reloads affected DocTypes (`Item`, `Customer`, `Supplier`, `Customer Group`, `Supplier Group`, `Item Group`) and clears cache.
2. **Pruned Fixtures (`fixtures/custom_field.json` & `fixtures/property_setter.json`)**:
   - Removed `Customer Group-custom_company`, `Supplier Group-custom_company`, `Customer-ic_customer_group`, `Supplier-ic_supplier_group`, `Item-is_intercompany_item`, `Item-ic_item_group`, and `Warehouse` custom fields from `fixtures/custom_field.json`.
   - Removed `Customer/Supplier-naming_series` property setters from `fixtures/property_setter.json`.
   - Removed master doctypes from both `custom_fields.json` files and `install.py`.
3. **Comprehensive App Uninstall Hooks (`uninstall.py`)**:
   - Registered `before_uninstall` and `after_uninstall` in `hooks.py`.
   - Automatically repairs `tabDocField`, drops all app custom fields and property setters, reloads standard master doctypes, and flushes cache so uninstalled sites return to 100% clean standard ERPNext state.
4. **Resilient Client-Side Protection (`inter_company_common.js`)**:
   - Sanitizes and catches invalid depends_on expressions safely without throwing uncaught exceptions, keeping form toolbar buttons (Delete, Add, Actions) fully operational.
5. **Standalone Console Recovery Script**:
   - Provided a 5-line Python snippet that can be pasted directly into `bench --site <site> console` to instantly fix the live database even when the app is currently uninstalled.

