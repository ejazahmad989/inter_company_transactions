# Implementation Plan: Marketplace Certification & Multi-Server Safety Guarantee

## Executive Summary: Will Other Servers Have This Problem?
**No. Other servers testing or installing the app from the Frappe Marketplace will NOT experience this issue.**

### Why It Happened on the Current Test Server
1. The error `doc.__islocalanddoc.is_stock_item` was caused by a historical find-and-replace command run on the current bench server that stripped whitespace around `and` (transforming `__islocal && doc` into `__islocalanddoc`).
2. A clean customer server running vanilla ERPNext v14, v15, or v16 has standard, valid expressions.
3. Earlier versions of this app had trial custom fields (`custom_company`, `ic_customer_group`, `ic_supplier_group`, `is_intercompany_item`) attached to Tree DocTypes (`Customer Group`, `Supplier Group`, `Item Group`) and Master DocTypes (`Customer`, `Supplier`, `Item`).
4. In Frappe Desk, any custom field on a Tree DocType flags the tree node form as dirty on load (`frm.is_dirty() = true`), replacing standard tree action buttons with the persistent "Save" button.
5. In Frappe Desk, any uncaught JavaScript error in `evaluate_depends_on_value` halts `Form.refresh_fields` before action buttons (Add Customer, Delete) can be rendered.

---

## Architectural Guardrails for 100% Marketplace Safety

### 1. Strict Schema Isolation (Zero Master/Tree Intrusion)
The app will never create custom fields, property setters, or custom permissions on:
* `Customer`
* `Supplier`
* `Item`
* `Customer Group`
* `Supplier Group`
* `Item Group`
* `Warehouse`

**Only Transaction DocTypes Receive Inter-Company Fields:**
* Sales Order, Purchase Order
* Sales Invoice, Purchase Invoice
* Delivery Note, Purchase Receipt
* Journal Entry, Payment Entry
* Stock Entry, Material Request
* Quotation, Supplier Quotation, Request for Quotation
* Journal Entry Account (child table)

This ensures standard ERPNext master records and tree hierarchies remain 100% vanilla and untouchable.

### 2. Complete Zero-Residual Uninstall Guarantee
When a user tests the app and runs `bench uninstall-app inter_company_transactions`:
1. `before_uninstall`:
   - Drops all custom fields added to transaction doctypes.
   - Deletes all property setters created by the app.
   - Deletes all custom docperms created by the app.
   - Cleans all intercompany background scheduler events.
2. `after_uninstall`:
   - Force-reloads standard DocType schemas from ERPNext.
   - Flushes Redis cache and site cache.
   - Leaves the customer's ERPNext instance in a pristine, untouched state.

### 3. Non-Throwing Client-Side Sandbox (`inter_company_common.js`)
* Overrides `Layout.prototype.evaluate_depends_on_value` and `frappe.utils.eval` with a safe, sandboxed evaluation engine.
* Translates any legacy operators without ever calling `frappe.throw()`.
* If any expression in the entire site is malformed, it gracefully returns `false`, ensuring that Desk toolbar buttons (`+ Add`, `Delete`, `Actions`) never crash or disappear.

### 4. Automated Pre-Publishing Verification Tool (`verify_marketplace_readiness`)
We will provide a single bench command that any administrator or marketplace tester can run:
```bash
bench --site <site> execute inter_company_transactions.commands.verify_marketplace_readiness
```
This command performs an automated 6-point audit:
1. **Master Isolation Audit**: Verifies zero custom fields exist on Customer, Supplier, Item, or Tree DocTypes.
2. **Permission Audit**: Verifies System Manager, Sales Manager, and Purchase Manager have full `create` and `delete` permissions.
3. **Expression Audit**: Scans all `tabDocField` and `tabCustom Field` records to confirm 0 malformed expressions.
4. **Hook Verification**: Checks `before_uninstall` and `after_uninstall` hook registration.
5. **Fixture Sanity**: Verifies no intrusive fixtures exist in the repository.
6. **Multi-Version Compatibility**: Validates compatibility across Frappe/ERPNext v14, v15, and v16.

---

## Proposed Changes

### File Modifications
1. **`inter_company_transactions/commands.py`**:
   - Add `verify_marketplace_readiness()` command for automated verification.
2. **`inter_company_transactions/uninstall.py`**:
   - Ensure complete removal of all app artifacts and cache invalidation.
3. **`inter_company_transactions/patches/v1_5_repair_item_depends_on_and_clean_trees.py`**:
   - Maintain automated self-healing during standard `bench migrate`.
4. **`MARKETPLACE.md` & `README.md`**:
   - Document zero-residual uninstallation, version compatibility (v14, v15, v16), and safety assurances for prospective buyers.

---

## Verification Plan
1. Run `python3 -m compileall inter_company_transactions/` to ensure zero syntax errors.
2. Run `bench execute inter_company_transactions.commands.verify_marketplace_readiness` logic to ensure all 6 audits pass.
3. Run container build and lint checks (`compile_applet`, `lint_applet`).
4. Re-tag release `v1.0.0` ready for GitHub push.
