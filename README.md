# Inter Company Transactions for ERPNext (v14 & v15)

A comprehensive, production-grade Frappe / ERPNext application that automates inter-company trading, transfer pricing, multi-entity reconciliation, and document synchronization across sister entities.

---

## 🌟 Key Capabilities

### 1. Zero-Friction Document Mirroring & Mapping
Automatically mirror documents across parent and subsidiary companies:
- **Sales Order ↔ Purchase Order**
- **Sales Invoice ↔ Purchase Invoice** (with Credit Note & Debit Note linkage for sales returns)
- **Delivery Note ↔ Purchase Receipt**
- **Stock Entry (Material Issue) ↔ Stock Entry (Material Receipt)**
- **Journal Entry ↔ Journal Entry** (Cross-entity clearing accounts)
- **Payment Entry ↔ Payment Entry** (Bi-directional inter-company settlement)

### 2. Configurable Transfer Pricing Rules
Configure pricing strategies directly in **Inter Company Settings**:
- **Source Document Rate**: Copy pricing directly as invoiced.
- **Cost / Valuation Rate**: Price target documents based on the source entity's FIFO / moving average valuation rate.
- **Cost + Markup %**: Automatically compute and apply cost-plus transfer margins.

### 3. Smart Item & Tax Synchronization
- **Auto-Create Missing Items**: Automatically replicates item code, description, and UOM into the target company if missing, preventing sync failures.
- **Tax Handling Strategy**:
  - *Mirror Net Rate Exactly* (zero extra tax on target invoice to preserve exact settlement total).
  - *Apply Target Company Tax Templates* (for regulatory VAT / GST compliance).

### 4. Background Queue Execution Mode
- Switch between **Synchronous** and **Asynchronous (frappe.enqueue)** processing in *Inter Company Settings* to handle high-volume batch submissions without browser timeout.

### 5. Inter Company Balance Reconciliation Script Report
- Visual reconciliation comparing payables and receivables across sister entities.
- Identifies net variances and flags missing or unmatched documents with color-coded status pills.

### 6. Dedicated Desk Workspace
- Instant access to transaction links, settings, references, and reconciliation reports directly from the Frappe Desk sidebar.

---

## 🚀 Installation & Setup

### 1. Install App
```bash
bench get-app https://github.com/your-repo/inter_company_transactions.git
bench --site [your-site-name] install-app inter_company_transactions
bench --site [your-site-name] migrate
```

All custom fields, workspaces, and DocTypes are automatically provisioned during installation and migration via Frappe fixtures and hooks.

### 2. Configure Linked Companies
1. Navigate to **Inter Company > Intercompany Transaction Link**.
2. Select your **Main Company** and add **Linked Companies** (sister entities).
3. Specify customer, supplier, and clearing accounts for both sides.
4. Set up the document mapping pairs (e.g. Sales Invoice → Purchase Invoice).

### 3. Run Automated Tests
```bash
bench --site [your-site-name] run-tests --app inter_company_transactions
```

---

## 📄 License
MIT License.
