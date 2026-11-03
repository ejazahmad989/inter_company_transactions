# Implementation Plan: Intercompany Party Auto-Detection & Accurate Mirroring

## Status: COMPLETED

### Problem Analysis
1. **Auto-Detection Inoperative**: When selecting an intercompany customer or supplier in Journal Entry (e.g., `GMP Customer`), the client script and backend hook had guard clauses (`if (!cint(frm.doc.is_intercompany)) return;`) that blocked auto-detection if `Is Intercompany` was unchecked. As a result, `Is Intercompany` stayed 0, `intercompany_target_company` was not populated on the parent or row, and counterpart draft entries were not created.
2. **ERPNext Internal Customer/Supplier Coverage**: Mappings were only checked against `Intercompany Linked Company` child rows, missing standard ERPNext `Customer.represents_company` and `Supplier.represents_company` records.
3. **Draft Creation Integrity**: Counterpart draft documents must be created *if and only if* `is_intercompany = 1` with a valid target sister company. Standard third-party transactions (e.g. with `Dawood`) must never trigger counterpart drafts in sister companies.

### Changes Implemented
1. **Dynamic Backend Party Resolution (`intercompany_transaction_link.py`)**:
   - Added whitelisted endpoint `get_party_target_company(party_name, party_type, current_company)` for fast, reliable party resolution from Desk.
   - Enhanced `get_intercompany_party_map` and `resolve_party_target_company` with 3-tier lookup:
     1. `Intercompany Transaction Link` child rows (`main_company_customer`, `main_company_supplier`, `other_company_customer`, `other_company_supplier` with `enabled != 0`).
     2. Standard ERPNext `Customer.represents_company` and `Supplier.represents_company`.
     3. Direct DB fallback queries on party name / customer name / supplier name.
     4. Guarantees `target_company != current_company`.
   - Updated `auto_detect_intercompany_party`:
     - Detects when any customer, supplier, or Journal Entry account row party is an intercompany entity.
     - Auto-sets `is_intercompany = 1`, `intercompany_target_company = <Target Company>`, and populates `row.intercompany_target_company` on matching child rows.
     - When no intercompany party is present and no target company is specified, cleanly resets `is_intercompany = 0` and wipes `intercompany_target_company`.

2. **Desk Client-Side Form Automation (`inter_company_common.js`)**:
   - Removed blocking guard clauses from `handle_party_selection` and `handle_journal_entry_row_party_change`.
   - When an intercompany party (such as `GMP Customer`) is selected:
     - Automatically ticks `is_intercompany = 1`.
     - Sets `intercompany_target_company` to the resolved sister company (e.g. `GMP FOODS`).
     - In Journal Entry, sets `row.intercompany_target_company = target_company` and syncs grid UI.
     - Unhides and enables the target company fields and displays a helpful alert.
   - When a normal third-party party (e.g. `Dawood`) is selected:
     - Ensures `row.intercompany_target_company` is cleared.
     - Keeps or sets `is_intercompany = 0` and leaves target company blank unless manually checked by the user.
   - Added `accounts_add` event to preserve the 10-column layout: Account (2), Party Type (1), Party (2), Intercompany Target Company (1), Debit (2), Credit (2).

3. **Validation & Verification**:
   - Verified all Python modules compile cleanly with `python3 -m py_compile` and `compileall`.
   - Verified code passes `lint_applet` and `compile_applet` with zero errors.
