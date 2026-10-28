# Implementation Plan: Simple, Safe Cancellation & Zero Workflow Complexity

This plan addresses your exact operational flow: keeping things simple, never interfering with company workflows, and preventing accidental cancellation when payments exist.

---

## 1. Clear Answers to Your Questions

### Q1: Will this app create or overwrite workflows in companies?
* **NO! Absolutely NOT.** 
* The app will **NOT** create, modify, or bundle any workflows.
* Every company already runs its own internal processes. Some use standard ERPNext (Draft -> Submit). Some use their own custom approval workflows.
* **Our App's Simple Rule:** The app only creates the counterpart document in **Draft (`docstatus = 0`)**.
  * If Company B has a workflow: ERPNext automatically routes the draft through Company B's existing workflow without our app needing to touch anything.
  * If Company B has no workflow: Company B's users simply open the draft, check it, and click "Submit".
* **Result:** 100% simple, zero risk of overwriting or breaking any company's existing setup.

---

### Q2: How does cancellation work if User A has no permissions in Company B?
* In multi-company ERPNext, **User A** in Company A is restricted by User Permissions and cannot see or open documents in Company B.
* If User A clicks "Cancel" on Sales Invoice `SI-001`:
  * Our backend Python hook runs a safe server-side database check (with system permissions) to inspect the linked Purchase Invoice `PI-001` in Company B.
  * **If Company B has a payment (`PE-001`) or downstream document attached:**
    * The cancellation in Company A is **immediately blocked**.
    * A clear, human-readable message pops up on User A's screen:
      ```
      [Inter-Company Notice]
      Cannot cancel Sales Invoice 'SI-001':
      Linked Purchase Invoice 'PI-001' in company 'Company B' has active payment(s): [PE-001].

      Action Required:
      Please contact the accounting team in 'Company B' (via phone or WhatsApp) to cancel payment 'PE-001' and 'PI-001' first.
      ```
    * Nothing is deleted, nothing is corrupted, and User A knows exactly what to tell User B.
  * **If Company B has NO payments and NO downstream documents:**
    * It safely cancels both in one clean step.

---

## 2. Implementation Steps

1. **Keep App Structure Simple (No Workflows in Code):**
   * Do not add any `Workflow` or `Workflow Action` fixtures or DocTypes.
   * Target documents are created as standard Drafts (`docstatus = 0`).

2. **Add Server-Side Pre-Cancel Validator (`before_cancel`):**
   * Location: `inter_company_transactions/doctype/intercompany_transaction_link/intercompany_transaction_link.py`
   * Method: `validate_intercompany_cancellation(doc, method=None)`
   * Checks for:
     * Active `Payment Entry Reference` (`docstatus = 1`) against the linked document.
     * Active `Journal Entry Account` (`docstatus = 1`) against the linked document.
     * If linked document is an Order or Receipt: downstream submitted Delivery Notes, Purchase Receipts, or Invoices.
   * If any are found:
     * Raises `frappe.throw()` with the friendly error message advising User A to notify User B.

3. **Atomic Safety in `cancel_linked_documents`:**
   * Remove dangerous manual `frappe.db.commit()` calls inside loops.
   * If any error occurs, let Frappe roll back the entire transaction so both companies remain in sync.

4. **Verify & Re-compile:**
   * Validate with `compile_applet` and ensure Python syntax is clean.

5. **Commit with Ejaz Ahmed Author:**
   * Update commit on `main` and tag `v1.0.0` ready for GitHub push.
