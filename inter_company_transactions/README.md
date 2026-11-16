<p align="center">
  <img src="inter_company_transactions/public/images/inter_company_logo.svg" alt="Inter-Company Transactions for ERPNext Logo" width="600" />
</p>

<p align="center">
  <a href="https://frappeframework.com/"><img src="https://img.shields.io/badge/Frappe-v15%20%7C%20v16-blue.svg" alt="Frappe v15 | v16" /></a>
  <a href="https://erpnext.com/"><img src="https://img.shields.io/badge/ERPNext-v15%20%7C%20v16-blue.svg" alt="ERPNext v15 | v16" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg" alt="Python 3.11 | 3.14" /></a>
  <a href="license.txt"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/Build-Passing-brightgreen.svg" alt="Build Status" />
  <a href="MARKETPLACE.md"><img src="https://img.shields.io/badge/Frappe%20Marketplace-Verified-orange.svg" alt="Frappe Marketplace" /></a>
</p>

<p align="center">
  <img src="inter_company_transactions/public/images/marketplace_banner.png" alt="Inter-Company Transactions Hero Banner" width="100%" />
</p>

# Inter-Company Transactions for ERPNext (v15 & v16 Ready)

An enterprise-grade, comprehensive Frappe / ERPNext application engineered for corporate groups, holding companies, multi-entity conglomerates, and multinational enterprises. Automates reciprocal intercompany document mirroring, party-to-company auto-detection, OECD arm's-length transfer pricing, multilateral netting, period-end elimination journal entries, billing dispute management, cross-company balance reconciliation, and **federated remote multi-site synchronization across separate ERPNext instances**.

---

## 🚀 Multi-Version Compatibility: ERPNext v15 & v16

### **Does it work on ERPNext 16 too?**
**Yes! The application is verified by automated CI across both ERPNext v15 and ERPNext v16.**

| Component | ERPNext v15 (Stable) | ERPNext v16 (Latest) | Notes |
|---|:---:|:---:|---|
| **Python Runtime (CI Tested)** | 3.11 | 3.14 | Standard Python type hinting & clean imports |
| **DocType Schemas** | Compatible | Compatible | Standard Frappe JSON schema |
| **Document Hooks (`doc_events`)** | Supported | Supported | `validate`, `on_submit`, `before_cancel`, `on_cancel`, `on_trash` |
| **Frappe ORM & Database** | Supported | Supported | Standard `frappe.get_doc`, `frappe.db`, and safe parameterized queries |
| **Client Script Hooks** | Supported | Supported | Standard `frappe.ui.form.on` and Desk Page API (zero prototype overrides) |
| **REST API & Multi-Site Sync** | Supported | Supported | Standard Token Auth (`Authorization: token key:secret`) + HMAC-SHA256 |
| **Database Migrations** | Zero Conflict | Zero Conflict | Idempotent `after_migrate` checks field existence dynamically |

### Why It Runs Flawlessly Across Both v15 and v16:
1. **Zero Core Monkey-Patching**: The app does NOT tamper with or override core Frappe classes or prototypes (`safe_eval`, `Layout`, `GridRow`, etc.). All business logic executes through standard, public extension hooks (`doc_events`, `scheduler_events`, `on_session_creation`, and custom Desk Pages).
2. **Safe Migration Safeguards**: Custom fields are injected via an idempotent `after_migrate` routine that checks `frappe.db.exists("Custom Field", ...)` before insertion. Running `bench migrate` on v15 or v16 will never crash or overwrite existing customizations.
3. **Pure Python Standard Library Cryptography**: Payload integrity verification uses standard `hmac`, `hashlib`, and `urllib` without volatile native C-extensions.
4. **Universal Desk UI**: Form extensions and the Interactive Desk Console utilize vanilla Frappe standard components compatible with both Frappe 15 and Frappe 16 Desk engines.

---

## 🌟 Key Capabilities

### 1. Zero-Touch Document Mirroring (15 Transaction Types)
Automatically creates, submits, or cancels reciprocal mirror documents in real-time across sister companies:
- **Sales Order ↔ Purchase Order**
- **Sales Invoice ↔ Purchase Invoice** (with full Credit Note & Debit Note return synchronization)
- **Delivery Note ↔ Purchase Receipt**
- **Stock Entry (Material Issue / Transfer) ↔ Stock Entry (Material Receipt)**
- **Journal Entry ↔ Journal Entry** (Inverted Debit/Credit intercompany clearing)
- **Payment Entry ↔ Payment Entry** (Bi-directional intercompany settlement matching)
- **Quotation ↔ Supplier Quotation**
- **Material Request → Purchase Order**
- **Request for Quotation → Supplier Quotation**
- **Subcontracting Order → Purchase Order**
- **Landed Cost Voucher → Journal Entry**

### 2. Dynamic Party & Company Auto-Detection
- **Zero Hardcoding**: Dynamically resolves intercompany relationships from *Intercompany Transaction Link*.
- **Instant Auto-Switch**: When a user creates any Sales Order, Purchase Order, Sales Invoice, Purchase Invoice, or Payment Entry and selects an internal customer or supplier, the system automatically checks `Is Intercompany` and selects the corresponding sister `Intercompany Target Company`.
- **Journal Entry Row-Level Automation**: Automatically inspects *Journal Entry Account* rows containing Debtors / Creditors parties, auto-assigns target companies per row, and sets header-level intercompany properties.

### 3. Intelligent Auto-Switching in Intercompany Transaction Type
- When configuring transaction links, choosing any **Source Transaction Type** automatically switches the **Target Transaction Type** to its reciprocal counterpart (e.g. Sales Order &rarr; Purchase Order, Sales Invoice &rarr; Purchase Invoice, Stock Entry &rarr; Stock Entry).

### 4. Federated Remote Multi-Site Synchronization (Cross-Instance ERPNext)
- **Cross-Server Integration**: Connects independent ERPNext instances hosted on separate servers, VPS instances, or Frappe Cloud benches via secure REST APIs.
- **Idempotent Inbound Engine**: Every cross-site transaction includes an idempotency key (`{source_site}:{doctype}:{name}`), completely eliminating duplicate documents during network retries or transient reconnections.
- **Bi-directional Cancellation**: Cancelling a document on Site A automatically dispatches an authenticated cancellation request to Site B to cancel the mirrored document.
- **HMAC-SHA256 Payload Signatures**: Secure webhook verification prevents spoofing and guarantees payload integrity.
- **Offline Resilience & Auto-Retry Worker**: If the remote server or network is temporarily down, the transaction is saved locally and queued in *Inter Company Error Log* (`Pending Retry`), where an hourly scheduler automatically retries pending syncs.

### 5. In-GUI Network & Firewall Diagnostic Engine
- **One-Click Diagnostic Tool**: Launch **"Diagnose Network & Firewall"** directly from *Inter Company Settings* without touching server terminals.
- **6-Layer Verification**:
  1. URL format & scheme validation (HTTPS vs HTTP).
  2. DNS hostname resolution.
  3. TCP socket port reachability & latency measurement (in milliseconds).
  4. SSL/TLS Certificate handshake.
  5. Frappe API Key/Secret token authentication.
  6. Inter Company Transactions App version compatibility handshake.
- **Automated Linux Firewall Guidance**: Displays copy-pasteable firewall commands (Ubuntu UFW, CentOS Firewalld, iptables, AWS Security Groups) right inside the GUI modal if ports are blocked.

### 6. Configurable Transfer Pricing Engine
- **Source Document Rate**: 1:1 mirroring of original rates.
- **Cost / Valuation Rate**: Price target documents based on the source entity's FIFO / moving average valuation rate.
- **Cost + Markup %**: Automatically compute and apply cost-plus transfer margins.
- **Resale Price Margin**: Deducts distributor margin from retail price.
- **Custom Rule Builder**: Python/Jinja formula execution with safe evaluation.

### 7. Multilateral Netting & Settlement Engine
- **Consolidated Netting Cycles**: Calculate bilateral and multilateral debit/credit positions between group entities over any period.
- **Matrix Settlement**: Consolidates dozens of invoices into a minimal set of net payment entries, slashing bank transfer fees and foreign exchange risk.

### 8. Period-End Elimination Journal Entries
- **Automated Consolidation**: Eliminate intercompany revenue vs expenses and intercompany receivables vs payables.
- **Auditable Elimination Runs**: Creates balanced elimination journal entries against designated consolidation accounts.

### 9. Interactive Control Console & Reconciliation
- **Executive Desk Page**: Real-time stats on pending mirrors, netting cycles, active policies, and unmapped parties.
- **Reconciliation Workbench**: Compare balances between Entity A Debtors and Entity B Creditors with mismatch detection.
- **Dispute Hub**: Log and resolve intercompany discrepancies with direct Credit/Debit Note adjustments.

---

## 🚀 Installation & Quickstart

### 1. Install via Bench
```bash
bench get-app https://github.com/ejazahmad989/inter_company_transactions.git
bench --site [your-site-name] install-app inter_company_transactions
bench --site [your-site-name] migrate
```

### 2. Configure Linked Companies (Single-Bench)
1. In Frappe Desk, search for **Intercompany Transaction Link**.
2. Click **Add Intercompany Transaction Link**.
3. Select your **Main Company**.
4. In **Linked Companies**, add your sister companies along with internal customer and supplier accounts.
5. In **Transaction Types**, define which transactions to mirror.
6. Click **Save**.

### 3. Test Automated Document Creation
Create a Sales Order in Company A for the mapped intercompany customer. The system will automatically check `Is Intercompany` and set Company B as the target company. Upon submitting, a matching Purchase Order in Company B is instantly generated!

### 4. Run Automated Unit Tests
```bash
bench --site [your-site-name] run-tests --app inter_company_transactions
```

---

## 🌐 Multi-Language Support
Out-of-the-box translation support included for:
- English (`en`)
- Spanish (`es`)
- French (`fr`)
- Arabic (`ar`)

---

## 📄 License & Publisher
- **Publisher:** Ejaz Tech (`ejazahmad989@gmail.com`) & Rahil Ali (`rahilali3311@gmail.com`)
- **License:** MIT License (Commercial & Marketplace Ready)
- **Documentation:** Complete setup and operations guide available in [`USER_GUIDE.md`](../USER_GUIDE.md) and inside ERPNext Desk via the User Guide PDF download.
