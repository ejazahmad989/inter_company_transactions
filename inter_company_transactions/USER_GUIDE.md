# Inter-Company Transactions for ERPNext: Enterprise User Guide & Tutorial
**Version:** 2.0 (Enterprise Edition)  
**Compatibility:** Frappe Framework v14 & v15 / ERPNext v14 & v15  
**Author:** Inter Company Transactions Contributors  
**Date:** September 2026  

---

## Table of Contents
1. [Introduction & Architectural Overview](#1-introduction--architectural-overview)
2. [Quick-Start Tutorial (1-Click Setup Wizard)](#2-quick-start-tutorial-1-click-setup-wizard)
3. [Deep Dive into Core DocTypes & Configurations](#3-deep-dive-into-core-doctypes--configurations)
   - [3.1 Intercompany Transaction Link](#31-intercompany-transaction-link)
   - [3.2 Inter Company Settings](#32-inter-company-settings)
   - [3.3 Transfer Pricing Policy (OECD Compliance)](#33-transfer-pricing-policy-oecd-compliance)
   - [3.4 Inter Company Netting Cycle](#34-inter-company-netting-cycle)
   - [3.5 Inter Company Elimination Run](#35-inter-company-elimination-run)
   - [3.6 Inter Company Dispute](#36-inter-company-dispute)
   - [3.7 Inter Company Remote Site (Cross-Site Federation)](#37-inter-company-remote-site-cross-site-federation)
4. [Step-by-Step Practical Examples](#4-step-by-step-practical-examples)
   - [Example A: Order-to-Cash & Procure-to-Pay Mirroring](#example-a-order-to-cash--procure-to-pay-mirroring)
   - [Example B: Transfer Pricing Margin Calculation](#example-b-transfer-pricing-margin-calculation)
   - [Example C: Multilateral Netting & Settlement Calculation](#example-c-multilateral-netting--settlement-calculation)
   - [Example D: Raising and Resolving a Billing Dispute](#example-d-raising-and-resolving-a-billing-dispute)
5. [Reporting & Executive Audit Tools](#5-reporting--executive-audit-tools)
6. [Troubleshooting & Error Handling](#6-troubleshooting--error-handling)

---

## 1. Introduction & Architectural Overview

The **Inter-Company Transactions** app transforms ERPNext into a multi-entity conglomerate platform. It solves four foundational challenges in group corporate accounting:
1. **Double Data Entry:** When Entity A sells goods to Entity B, Entity B's purchase order/receipt/invoice is created automatically.
2. **Transfer Pricing Non-Compliance:** Dynamically computes markups, resale prices, and arm's-length benchmarks across tax jurisdictions.
3. **Liquidity Friction:** Consolidates multiple reciprocal invoices into single minimal multilateral netting settlements.
4. **Group Financial Consolidation:** Eliminates internal double-counting of AR/AP, sales, and COGS for parent holding companies.

---

## 2. Quick-Start Tutorial (1-Click Setup Wizard)

### Step 1: Open the Control Console
In ERPNext Desk, navigate to **Workspace > Inter Company** or enter the route directly in your browser:
```
/app/inter-company-console
```

### Step 2: Launch the Wizard
1. On the top right of the Inter-Company Control Console, click the **Quick Setup Wizard** button.
2. Select:
   - **Main Company (Entity A)**: e.g., *Headquarters Inc.*
   - **Counterparty Company (Entity B)**: e.g., *Distribution Subsidiary Ltd.*
3. Click **Establish Connection**.

### What happens automatically under the hood:
* Creates an internal Customer in Entity A representing Entity B.
* Creates an internal Supplier in Entity A representing Entity B.
* Creates an internal Customer in Entity B representing Entity A.
* Creates an internal Supplier in Entity B representing Entity A.
* Creates an **Intercompany Transaction Link** record with 9 pre-configured bidirectional transaction rules:
  - `Sales Order <-> Purchase Order`
  - `Delivery Note <-> Purchase Receipt`
  - `Sales Invoice <-> Purchase Invoice`
  - `Material Request <-> Purchase Order / Sales Order`
  - `Quotation <-> Supplier Quotation`
  - `Journal Entry <-> Journal Entry`

---

## 3. Deep Dive into Core DocTypes & Configurations

### 3.1 Intercompany Transaction Link
* **Location:** `Inter Company > Intercompany Transaction Link`
* **Purpose:** The primary routing engine defining which sister companies trade with each other.
* **Key Fields:**
  - `Main Company`: The initiating parent or sister company.
  - `Enabled`: Master switch for transaction triggering.
  - `Auto Create Internal Parties`: Automatically builds missing customer/supplier records if checked.
  - `Companies Table`: Child table listing counterparty entities, their specific Internal Customer ID, and Internal Supplier ID.
  - `Transaction Types Table`: Defines specific document routing pairs, whether target docs are created as Draft or automatically Submitted, and custom account overrides.

### 3.2 Inter Company Settings
* **Location:** `Inter Company > Inter Company Settings`
* **Purpose:** Global environment configurations.
* **Key Settings:**
  - `Execution Mode`: 
    - *Synchronous:* Targets created immediately on save/submit.
    - *Background (Queue):* Jobs enqueued via Redis queue for high-volume transactions.
  - `Deployment Mode`: 
    - *Local Multi-Company (Single Database):* Both entities reside on the same bench site.
    - *Federated Cross-Site (REST API):* Entities operate on separate ERPNext instances across data centers.
  - `Default Transfer Rate Method`: Default pricing fallback (`Source Document Rate`, `Cost / Valuation Rate`, `Cost + Markup %`).

### 3.3 Transfer Pricing Policy (OECD Compliance)
* **Location:** `Inter Company > Transfer Pricing Policy`
* **Purpose:** Enforces OECD arm's-length transfer pricing rules between specific sister entity pairs.
* **Pricing Methods:**
  - **Cost Plus Markup %:** Takes source warehouse FIFO/moving average valuation rate and adds a configured markup percentage (e.g., Cost + 15%).
  - **Resale Price Method:** Takes downstream retail selling price and deducts distributor margin % (e.g., Retail - 20%).
  - **Comparable Uncontrolled Price (CUP):** Applies predefined market benchmark rates.
  - **Fixed Transfer Rate:** Fixed negotiated price contract per item.

### 3.4 Inter Company Netting Cycle
* **Location:** `Inter Company > Inter Company Netting Cycle`
* **Purpose:** Multilateral settlement of cross-company debts.
* **Algorithm:**
  - Pulls all outstanding unpaid Sales and Purchase Invoices between participant entities.
  - Calculates net debtor/creditor balances.
  - Executes a greedy optimization to settle all debts with the minimal number of bank transfers.
  - Generates balancing clearing Journal Entries with one click.

### 3.5 Inter Company Elimination Run
* **Location:** `Inter Company > Inter Company Elimination Run`
* **Purpose:** Period-end financial consolidation.
* **Capabilities:**
  - Scans reciprocal General Ledger balances between sister entities.
  - Neutralizes internal AR and AP balances.
  - Reverses internal Intercompany Revenue against Intercompany Cost of Goods Sold (COGS).
  - Posts an Elimination Journal Entry to the Holding Company's consolidation account.

### 3.6 Inter Company Dispute
* **Location:** `Inter Company > Inter Company Dispute`
* **Purpose:** Discrepancy management when sister entities disagree on billing rates, missing items, or damaged shipments.
* **Form Action:** Click **Inter Company > Raise Dispute** directly from any linked invoice or delivery note.
* **Resolution Engine:**
  - `Issue Credit Note`: Automatically posts a Return Sales Invoice.
  - `Issue Debit Note`: Automatically posts a Return Purchase Invoice.
  - `Journal Adjustment`: Posts balancing GL adjustment for rounding/rate differences.

### 3.7 Inter Company Remote Site
* **Location:** `Inter Company > Inter Company Remote Site`
* **Purpose:** Cross-site federation connecting disparate Frappe sites via REST API.
* **Features:** API key / secret token management, automated handshake verification (`Test Connection`), and inbound webhook receiver endpoint.

---

## 4. Step-by-Step Practical Examples

### Example A: Order-to-Cash & Procure-to-Pay Mirroring
**Scenario:** Entity A (*Acme Mfg*) sells 100 units of "Widget A" to sister company Entity B (*Acme Retail*) at $50/unit.

1. **Step 1:** In *Acme Mfg*, create a new **Sales Order**.
2. **Step 2:** Select Customer: `Acme Retail (Internal)`. Add Item `Widget A`, Qty `100`, Rate `$50`.
3. **Step 3:** Click **Submit**.
4. **Step 4:** Inspect the form. A blue alert banner appears:
   ```
   Inter Company: Linked Purchase Order PO-2026-00042 has been automatically created in Acme Retail.
   ```
5. **Step 5:** Switch company view to *Acme Retail*. Notice **Purchase Order** `PO-2026-00042` exists with Supplier `Acme Mfg (Internal)` for 100 units of Widget A.
6. **Step 6:** Deliver goods by creating a **Delivery Note** in *Acme Mfg*. Upon submission, a corresponding **Purchase Receipt** is automatically created in *Acme Retail*.

### Example B: Transfer Pricing Margin Calculation
**Scenario:** Headquarters manufactures a customized component with a valuation cost of $200. Regulatory guidelines require a **15% Cost-Plus markup** for sales to foreign subsidiaries.

1. Create a **Transfer Pricing Policy**:
   - `Policy Name`: *US to EU Component Transfer*
   - `Source Company`: *Acme HQ*
   - `Target Company`: *Acme Europe B.V.*
   - `Pricing Method`: *Cost Plus Markup %*
   - `Markup Percentage`: `15.0%`
2. Save and set Status to `Active`.
3. Create a Sales Order in *Acme HQ* for *Acme Europe B.V.*.
4. The system calculates:
   $$\text{Transfer Rate} = \$200 \times (1 + 0.15) = \$230.00$$
5. The mirrored Purchase Order in *Acme Europe B.V.* receives the target rate of **$230.00** automatically.

### Example C: Multilateral Netting & Settlement Calculation
**Scenario:** End of Month settlement between 3 group companies:
- Company A owes Company B **$100,000**
- Company A owes Company C **$50,000**
- Company B owes Company C **$20,000**

Without netting, 3 separate international wire transfers are required ($170,000 total transferred).

1. Go to **Inter Company Netting Cycle > New**.
2. Enter `Cycle Name`: *March 2026 Netting*.
3. In the Companies table, click **Fetch Outstanding Invoices**.
4. The system computes Net Positions:
   - **Company A:** Net Debtor: $-\$150,000$
   - **Company B:** Net Creditor: $+\$80,000$
   - **Company C:** Net Creditor: $+\$70,000$
5. Click **Calculate Netting**.
6. The engine generates 2 optimized settlements:
   - *Settlement 1:* Company A pays Company B **$80,000**
   - *Settlement 2:* Company A pays Company C **$70,000**
7. Total funds wired reduced to **$150,000** (a $20,000 liquidity saving and elimination of cross-border banking fees).
8. Click **Generate Settlement Journal Entries** to post balancing GL records across all 3 ledgers.

### Example D: Raising and Resolving a Billing Dispute
**Scenario:** Company B was billed $1,500 on Sales Invoice `SINV-00100`, but received damaged items worth $300.

1. Open `SINV-00100`.
2. Under the top menu, click **Inter Company > Raise Dispute**.
3. In the new `Inter Company Dispute` document:
   - `Source Amount`: $1,500
   - `Target Amount`: $1,200
   - `Variance Amount`: $300 (calculated automatically)
   - `Dispute Reason`: *Damaged Goods*
4. Set status to `Under Investigation`.
5. Under Resolution Action, select: `Issue Credit Note` for $300.
6. Click **Execute Resolution**.
7. The system creates and links a Credit Note return invoice in the seller entity and updates the intercompany variance to zero.

---

## 5. Reporting & Executive Audit Tools

### 5.1 Inter Company Transaction Matrix
* **Route:** `/app/query-report/Inter Company Transaction Matrix`
* Displays all transaction pairs side-by-side: Source Document vs. Target Document.
* Visual status pills:
  - **Green (Synchronized):** Both documents exist, rates and quantities match.
  - **Red (Variance):** Difference detected between source and target totals.
  - **Orange (Pending Mirror):** Initiating document submitted, target awaiting processing.
* Includes summary cards: Total Volume, Total Absolute Variance, and Sync % Chart.

### 5.2 Inter Company Balance Reconciliation
* **Route:** `/app/query-report/Inter Company Balance Reconciliation`
* Compares reciprocal GL balances: Entity A's Receivable from Entity B vs. Entity B's Payable to Entity A.
* Identifies unposted journal vouchers, currency translation differences, and missing invoices.

---

## 6. Troubleshooting & Error Handling

### Error Log Inspection
If a transaction fails to mirror (e.g., target warehouse closed or missing fiscal year):
1. Navigate to **Inter Company > Inter Company Error Log**.
2. Locate the failed record.
3. Review the traceback, resolve the underlying ledger/master issue in the target company, and click **Retry Sync**.

### Manual Synchronization
If a document was submitted during maintenance or when the link was disabled:
1. Open the submitted document.
2. Click **Inter Company > Sync Mirror Now**.
3. The system processes the document immediately and binds the reciprocal link.

---
*End of User Guide. For technical issues or feature contributions, consult the repository issue tracker.*
