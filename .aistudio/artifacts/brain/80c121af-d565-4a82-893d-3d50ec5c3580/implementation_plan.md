# Implementation Plan: Fix False-Positive Intercompany Mirroring & Unify Defaults

## Status: COMPLETED

### Root Cause Analysis & Resolution
1. **User's Checkbox Made Authoritative (`auto_detect_intercompany_party`)**:
   - Location: `inter_company_transactions/doctype/intercompany_transaction_link/intercompany_transaction_link.py`
   - Fixed the issue where auto-detection ignored the user's explicit choice on `Is Intercompany`.
   - If `is_intercompany` is `0` or unchecked (`not cint(doc.get("is_intercompany"))`), the function immediately clears any stale `intercompany_target_company` on the header and on all `accounts` child rows, and returns immediately without auto-enabling intercompany.
2. **Fixed Silent Sync Bug in `install.py`**:
   - Updated `create_custom_fields()` `else:` branch to synchronize all custom field attributes (`default`, `depends_on`, `mandatory_depends_on`, `read_only_depends_on`, `fetch_if_empty`, `columns`, etc.) whenever a custom field already exists, ensuring `default = '0'` reaches the live database upon running `bench migrate`.
3. **Database Migration Enforcement (Patch v1.4 & Helper)**:
   - Updated `patches/v1_4_fix_non_intercompany_submit_and_clean_targets.py` and `fix_legacy_custom_fields()` to directly run SQL ensuring `tabCustom Field` has `default = '0'` for `is_intercompany` and `default = NULL` for `intercompany_target_company`.
4. **Desk Client Script Hardening (`inter_company_common.js`)**:
   - When the user unchecks `Is Intercompany`, all child rows in `accounts` have their `intercompany_target_company` wiped.
   - Tracked user preference so selecting a party in standard mode does not forcefully auto-tick `Is Intercompany`.
   - Cleaned `validate` hook so non-intercompany transactions cannot carry hidden target companies.
5. **Git Tag & Release**:
   - Release commit `344d3f6` created and tagged `v1.0.0` ready for deployment.
