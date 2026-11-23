<p align="center">
  <img src="inter_company_transactions/public/images/inter_company_logo.svg" alt="Inter-Company Transactions Logo" width="540" />
</p>

# Inter Company Transactions for ERPNext
### Official Frappe Marketplace Listing & Publisher Package

<p align="center">
  <img src="inter_company_transactions/public/images/marketplace_banner.png" alt="Marketplace Showcase Banner" width="100%" />
</p>

---

## 1. Marketplace Listing Overview

| Listing Field | Value |
|---|---|
| **App Name** | `inter_company_transactions` |
| **App Title** | Inter Company Transactions |
| **Publisher** | Ejaz Tech (`E Tech`) |
| **Publisher Contact** | `ejazahmad989@gmail.com` (Support / Testing: `rahilali3311@gmail.com`) |
| **Category** | Accounting & Finance / Supply Chain / Enterprise Management |
| **Supported Frappe Versions** | **Frappe v15, Frappe v16 (CI Verified)** |
| **Supported ERPNext Versions** | **ERPNext v15, ERPNext v16 (CI Verified)** |
| **App Version** | `1.0.0` (Production Stable) |
| **License** | MIT (Open Source — required for Frappe Cloud Marketplace) |
| **Repository URL** | `https://github.com/ejazahmad989/inter_company_transactions` |
| **Documentation** | Included (`USER_GUIDE.md`, `Inter_Company_Transactions_User_Guide.pdf`, & `Inter_Company_Transactions_Visual_Workbook.pdf`) |
| **App Icon** | `inter_company_transactions/public/images/inter_company_icon_512.png` |
| **Hero Banner** | `inter_company_transactions/public/images/marketplace_banner.png` |

---

## 2. Version Support: ERPNext 15 & ERPNext 16 Compatibility

### **Is this app only for ERPNext 15, or will it work on ERPNext 16 too?**
**It works on BOTH ERPNext 15 AND ERPNext 16!** Automated CI tests fresh install, unit tests, uninstallation, and reinstall across both `version-15` and `version-16`.

### Architecture Highlights for v15 & v16 Compatibility:
- **Zero Core Tampering or Monkey-Patching:** The app uses standard, public Frappe extension hooks (`doc_events`, `scheduler_events`, `on_session_creation`) with zero overrides of core Python functions or JS prototypes.
- **Python Runtime:** Packaged for Python 3.10, 3.11, and 3.12 with standard library dependencies only.
- **Unified DocType Schema:** DocType definitions use standard Frappe JSON specifications supported uniformly across Frappe 15 and 16.
- **Idempotent Bench Migrations:** `after_migrate` checks schema state before creating custom fields, eliminating fixture conflicts during upgrades.
- **REST Multi-Site Federation:** Standard Token Auth and HMAC-SHA256 verification operate identically across Frappe 15 and 16.

---

## 3. Executive Pitch & Tagline

> **Tagline:** *"Eliminate double data entry, reconcile sister-company balances in real-time, and automate multi-company trade, netting, and elimination across your ERPNext group."*

### Why Customers Buy This App:
Managing multi-company enterprises in vanilla ERPNext requires manual re-entry of purchase orders, mirror sales invoices, duplicate delivery notes, manual internal payments, and tedious month-end balance reconciliation across entities.

**Inter Company Transactions** converts multi-entity operations into a zero-touch, automated workflow. When Company A raises a Sales Order, Company B receives a draft Purchase Order instantly. When Company A invoices, Company B receives the matching Purchase Invoice. Balances are reconciled dynamically, transfer pricing rules apply automatically, and multilateral netting cycles settle mutual debts with minimal cash outflow.

---

## 4. Key Feature Matrix (Marketplace Highlights)

### 4.1. Zero-Touch Document Mirroring (14 Supported DocTypes)
Seamless bidirectional mirroring for every operational document:
1. **Sales Order ↔ Purchase Order**
2. **Sales Invoice ↔ Purchase Invoice** (with full Credit/Debit Note return sync)
3. **Delivery Note ↔ Purchase Receipt**
4. **Quotation ↔ Supplier Quotation**
5. **Stock Entry ↔ Stock Entry (Same-Currency Transit Warehouses)**
6. **Journal Entry ↔ Journal Entry (Debit/Credit Inversion)**
7. **Payment Entry ↔ Payment Entry (Payment to Receipt Matching)**
8. **Material Request → Purchase Order / Sales Order**
9. **Request for Quotation → Supplier Quotation**
10. **Landed Cost Voucher → Journal Entry**

### 4.2. Dynamic Party & Company Auto-Detection
- **Dynamic Routing:** No hardcoding required. The system links internal customers/suppliers configured in *Intercompany Transaction Link*.
- **Instant Recognition:** Selecting an intercompany customer or supplier in any Sales Order, Purchase Order, Invoice, or Payment Entry automatically enables `Is Intercompany` and selects the matching `Intercompany Target Company`.
- **Journal Entry Multi-Row Auto-Detection:** Scans *Journal Entry Account* rows with Debtors/Creditors parties, automatically assigning target companies per row and across the parent voucher.

### 4.3. Transfer Pricing Engine (OECD & Arm's Length Compliant)
- **Source Rate:** 1:1 mirroring of original rates.
- **Cost Plus Markup:** Applies fixed or percentage markups (e.g., Cost + 15%).
- **Resale Price Margin:** Deducts distributor margin from retail price.
- **Price List Mapping:** Reads designated intercompany price lists per subsidiary.
- **Custom Rule Builder:** Python/Jinja formula execution with safe evaluation.

### 4.4. Multilateral Netting & Settlement Engine
- Consolidates reciprocal receivables and payables across 2, 3, or more sister companies into a unified settlement matrix.
- Minimizes banking transaction fees and currency conversion losses by calculating net settlement amounts.
- Generates balancing Journal Entries upon submission.

### 4.5. Automated Elimination Entries (Consolidation)
- Generates period-end elimination runs for:
  - Intercompany trade revenue and expense.
  - Reciprocal debtor and creditor balances.
  - Unrealized internal inventory profit.

### 4.6. Federated Remote Multi-Site Synchronization & In-GUI Network Diagnostics
- **Cross-Instance REST API Integration:** Synchronizes independent ERPNext sites running on separate physical servers, VPS, or cloud hosts.
- **Idempotent Inbound Engine:** Eliminates duplicate documents across retries using cryptographic idempotency keys.
- **HMAC-SHA256 Signatures & API Tokens:** Enterprise-level security and webhook verification.
- **Offline Resilience & Auto-Retry Worker:** Transactions queue in *Inter Company Error Log* (`Pending Retry`) and auto-retry hourly if remote servers are temporarily offline.
- **In-GUI Network & Firewall Diagnostics:** One-click socket, DNS, SSL, and port connectivity test in the desk with automated Linux firewall commands (UFW, Firewalld, AWS Security Groups).

### 4.7. Marketplace Screenshots Gallery (`/screenshots`)
Recommended upload order for the Frappe Cloud Marketplace listing gallery:
1. `screenshots/transaction_link.png` — Intercompany Transaction Link master configuration
2. `screenshots/transaction_link_Transaction_type.png` — Bidirectional 15-pair Transaction Type matrix
3. `screenshots/S-order-same_currency.png` — Auto-detected Intercompany Sales Order
4. `screenshots/p-order_mirror_entry_created.png` — Locked mirrored Purchase Order draft in target company
5. `screenshots/journal_entry_mirror.png` — Automated inverted Debit/Credit mirrored Journal Entry
6. `screenshots/payment_entry_mirror_entry.png` — Automated mirrored Payment Entry (`Receive` ↔ `Pay`)

All 16 workflow screenshots (including COA clearing accounts, row settings, and instant creation dialogs) are stored in [`screenshots/`](screenshots/).

---

## 5. Recommended Marketplace Pricing Strategy

When publishing on Frappe Cloud Marketplace, you can offer one of the following models:

| Plan | Price Model | Target Audience | What's Included |
|---|---|---|---|
| **Monthly Subscription** | **$49 / month / site** | Multi-company groups, holding entities | Complete intercompany engine, all 14 supported doctypes, 2-way bilateral trading, automated bridge accounts |
| **Annual Subscription** | **$490 / year / site** (2 Months Free) | Annual subscribers saving $98/year | All features, continuous updates for ERPNext v15 & v16, community support |
| **Enterprise Support Retainer** | **$299 / month** | Large conglomerates & holding groups | Federated Multi-Site Sync, custom ERP integrations, priority engineering SLA |

---

## 6. Frappe Marketplace Submission Checklist & Background/Security Disclosures

### Background Scheduler & Remote Credential Disclosure
- **Hourly Retry Job (`scheduler_events["hourly"]`)**: Runs `inter_company_transactions.inter_company_transactions.doctype.inter_company_error_log.inter_company_error_log.auto_retry_pending_errors` once per hour to automatically retry queued `Inter Company Error Log` entries marked `Pending Retry` (e.g., after a temporary remote-site outage). No background job runs unless configured intercompany transactions encounter a retryable error.
- **Remote-Site Credentials (`Inter Company Remote Site`)**: Optional multi-site federation stores remote instance connection parameters (`site_url`, `api_key`, and encrypted Password fields `api_secret` and `hmac_secret`) strictly inside `Inter Company Remote Site` (child table of `Inter Company Settings`) and signs outbound payloads with HMAC-SHA256 (`X-Intercompany-Signature`).
- **Cross-Company Draft Isolation**: Creating mirrored draft vouchers in a sister company uses `ignore_permissions=True` and `ignore_mandatory=True` *only* after the source submission is authorized and linked in `Intercompany Transaction Link`, allowing target accountants to verify local warehouses and cost centers before submitting.

### Pre-Submission Checklist:

- [x] **App Packaging (`pyproject.toml` / Flit):** Modern PEP 621 `pyproject.toml` (`flit_core`) with Python 3.10, 3.11 & 3.12 classifiers and zero conflicting `setup.py` or pip requirements.
- [x] **CI-Tested for ERPNext v15 & v16:** GitHub Actions runs install, `verify_marketplace_readiness`, unit tests, uninstall, and reinstall on both `version-15` and `version-16`.
- [x] **High-Resolution Branding Assets:** 512x512 app icon (SVG & PNG), horizontal logo, and 1280x640 showcase banner.
- [x] **Hooks Configuration:** Metadata (`app_name`, `app_publisher`, `app_logo_url`, `app_icon`, `required_apps = ["erpnext"]`), `on_session_creation`, `notification_config`, and `scheduler_events` declared (`before_request` removed; version sourced from `__version__`).
- [x] **Federated Remote Multi-Site Sync:** Robust cross-instance push/cancel REST API engine with permission verification, idempotency, and hourly offline auto-retry.
- [x] **In-GUI Network & Firewall Diagnostic Tool:** Automated port and socket diagnostics with copy-pasteable firewall commands.
- [x] **Migration Idempotency:** `after_install`, single-file patches, and `after_migrate` safely check existence and sanitize metadata expressions in MariaDB without modifying core runtime classes.
- [x] **Multi-Language Translations:** Standard CSV translation bundles included for Spanish (`es`), French (`fr`), and Arabic (`ar`).
- [x] **Automated Tests:** Comprehensive unit test suite with 100% passing tests.
- [x] **Zero-Residual Uninstallation:** Certified `before_uninstall` and `after_uninstall` hooks verified in CI.

---

## 7. Zero-Residual Uninstallation & Core Schema Isolation Guarantee

For marketplace evaluators and prospective customers testing the application:

1. **Master & Tree DocType Isolation**:
   - The application **never** adds custom fields, property setters, or custom permissions to standard ERPNext master records (`Customer`, `Supplier`, `Item`, `Warehouse`) or tree structures (`Customer Group`, `Supplier Group`, `Item Group`).
   - Only operational transaction vouchers (`Sales Order`, `Purchase Order`, `Sales Invoice`, `Purchase Invoice`, `Journal Entry`, `Payment Entry`, etc.) receive inter-company routing fields.

2. **Clean Uninstallation Guarantee**:
   - Running `bench --site <site> uninstall-app inter_company_transactions` executes certified cleanup hooks that:
     - Delete all custom fields introduced by the app.
     - Delete all property setters introduced by the app.
     - Remove all custom docperms introduced by the app.
     - Restore standard ERPNext metadata and clear all site and Redis caches.
   - The customer's ERPNext instance is restored to a 100% vanilla state with zero leftover records or schema artifacts.

3. **Built-in Quality Audit Tool**:
   - Verify marketplace readiness and safety at any time:
     ```bash
     bench --site <site> execute inter_company_transactions.commands.verify_marketplace_readiness
     ```

