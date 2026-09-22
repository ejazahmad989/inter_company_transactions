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

#### 3.1.0 Transaction Form Behavior: "Is Intercompany" & Dynamic Sister Company Selection
In normal operations, almost all daily transactions (Payment Entry, Journal Entry, Sales Invoices, etc.) belong strictly to the local company. To prevent accidental mirror creation:
1. **Unchecked by Default (`is_intercompany = 0`)**:
   - Every transaction form has the **Is Intercompany** checkbox unticked.
   - The **Intercompany Target Company** field is rendered **read-only** and automatically defaults to the source company name (e.g. *Acme Manufacturing Ltd*).
   - Upon save or submission, it is treated strictly as an internal transaction; no mirror voucher is generated in sister companies.
2. **Checked Mode (`is_intercompany = 1`)**:
   - When user ticks **Is Intercompany**, the **Intercompany Target Company** field immediately becomes **editable and mandatory**.
   - If it was populated with the source company, it automatically clears so the user can select the target sister company.
   - The field lookup dynamically excludes the current company, preventing circular or self-directed intercompany errors.
   - If unticked, it resets to read-only with the current company name.
   - Upon submission, the engine creates the reciprocal mirror entry in the chosen target company.

#### 3.1.1 Comprehensive Matrix of Supported Mirror Transactions (What It CAN Do)
The engine supports real-time, automated document mirroring across all standard trade and accounting workflows in ERPNext:

| # | Initiating (Source) DocType | Target (Mirror) DocType | Direction | Business Process & Behavior |
|---|---|---|---|---|
| 1 | **Sales Order** | **Purchase Order** | Bi-directional | Customer order in selling company generates reciprocal vendor order in buying company with identical items, quantities, pricing, and required dates. |
| 2 | **Purchase Order** | **Sales Order** | Bi-directional | Procurement order in subsidiary generates fulfillment order in parent/sister manufacturing entity. |
| 3 | **Delivery Note** | **Purchase Receipt** | Bi-directional | Dispatch of goods from seller automatically creates incoming Goods Receipt at destination warehouse (reduces in-transit latency). |
| 4 | **Purchase Receipt** | **Delivery Note** | Bi-directional | Receiving goods at destination can trigger delivery note completion at source entity. |
| 5 | **Sales Invoice** | **Purchase Invoice** | Bi-directional | Commercial billing in seller creates reciprocal accounts payable invoice with identical line item breakdown, taxes, and intercompany tags. |
| 6 | **Purchase Invoice** | **Sales Invoice** | Bi-directional | Supplier invoice in buying company creates reciprocal accounts receivable billing in sister company. |
| 7 | **Quotation** | **Supplier Quotation** | Bi-directional | Internal sales estimate generates vendor quotation for purchasing approvals. |
| 8 | **Supplier Quotation** | **Quotation** | Bi-directional | Vendor quote from sister company creates sales quotation. |
| 9 | **Material Request** | **Sales Order / Purchase Order** | Forward | Stock replenishment requisition in a branch automatically initiates order creation in the central warehouse company. |
| 10 | **Request for Quotation** | **Supplier Quotation** | Bi-directional | Formal procurement inquiry creates supplier quote in sister sales department. |
| 11 | **Stock Entry** | **Stock Entry** | Bi-directional | *Material Issue* in Company A triggers an automated *Material Receipt* in Company B at the designated transfer valuation rate. |
| 12 | **Journal Entry** | **Journal Entry** | Bi-directional | Cross-entity fund transfers or expense allocations automatically generate balancing voucher with reversed debit/credit accounts. |
| 13 | **Payment Entry** | **Payment Entry** | Bi-directional | Payment made from Company A to Company B creates a matching Receipt voucher in Company B linked to the open intercompany invoice. |

---

#### 3.1.2 Unsupported Cross-Entity Transactions (What It CANNOT Do and WHY It Is a MUST)
In enterprise multi-company accounting, certain ERPNext DocTypes **cannot and must not** be mirrored directly between separate legal entities. Attempting to mirror these documents directly would violate statutory financial compliance, corporate tax laws, and GAAP/IFRS standards:

1. **Landed Cost Voucher (LCV)**
   - *Why It Cannot Be Mirrored:* A Landed Cost Voucher is strictly an **internal inventory valuation adjustment tool** within a single legal entity. Its sole purpose is to capitalize freight, customs, or handling costs into the moving-average or FIFO valuation rate of an existing Purchase Receipt. It does **not** create legal debtor/creditor claims.
   - *What Is a MUST (Statutory Compliance):* If Sister Company A provides logistics, freight, or clearance services to Sister Company B:
     - Company A **MUST** issue a standard service **Sales Invoice** to Company B.
     - The engine mirrors this into a **Purchase Invoice** (Freight & Handling) in Company B.
     - Company B can then optionally reference this Purchase Invoice inside its own internal Landed Cost Voucher if it wishes to capitalize those freight costs into inventory.

2. **Subcontracting Order**
   - *Why It Cannot Be Mirrored Directly:* A Subcontracting Order in ERPNext v15 is bound to a single entity's internal Bill of Materials (BOM), supplied raw material tracking, and subcontracting receipt valuation algorithms. Sister entities operate independent inventory ledgers and separate tax jurisdictions.
   - *What Is a MUST:* Intercompany subcontracting must be conducted via:
     - Step 1: Subcontracting entity creates a standard **Purchase Order** (Subcontracted) &rarr; mirrored to **Sales Order** (Job Work) in the manufacturing sister company.
     - Step 2: Raw materials transferred using **Stock Entry** (Material Transfer) &rarr; mirrored to **Stock Entry** (Material Receipt) in the manufacturer.
     - Step 3: Finished items delivered via **Delivery Note** &rarr; **Subcontracting Receipt**.

3. **Fixed Asset Movements & Depreciation Entries**
   - *Why It Cannot Be Mirrored Directly:* Fixed assets are governed by entity-specific asset registers, tax depreciation schedules, and legal ownership titles. An automated transfer would corrupt statutory tax depreciation books.
   - *What Is a MUST:* Asset transfers between sister companies must be executed as an arm's-length asset sale:
     - Seller entity raises a **Sales Invoice** (Asset Sale / Disposal).
     - Buying entity books a **Purchase Invoice** with *Asset Category* assignment to initialize the new statutory asset book.

4. **Payroll Entry & Salary Slips**
   - *Why It Cannot Be Mirrored:* Payroll is strictly subject to jurisdiction-specific labor laws, statutory withholding taxes, social security contributions, and local employment contracts.
   - *What Is a MUST:* When management or staff costs are shared across subsidiaries, the employing entity reallocates costs using an arm's-length **Management Services Agreement (MSA)**:
     - Employing entity bills the subsidiary via a **Sales Invoice (Management Services)** or an **Intercompany Journal Entry (Shared Expense Recharge)**.

---

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

### 3.8 Inter Company Customer Group
* **Location:** `Selling > Customer Group` and `Selling > Customer` (`ic_customer_group`)
* **Purpose:** Accounting isolation and automated elimination segregation.

#### 3.8.1 Why Do We Need an "Inter Company Customer Group"?
In standard ERP systems, sales to external third-party buyers and sales to sister companies often get co-mingled in the same default *"All Customer Groups"* or general Accounts Receivable (Debtors) accounts. This creates serious financial problems:
1. **Financial Statement Distortion:** External revenue looks falsely inflated on management dashboards because internal stock transfers look like external commercial sales.
2. **AR Aging Misrepresentation:** Overdue intercompany balances sit in the standard Accounts Receivable aging report alongside external clients, distorting DSO (Days Sales Outstanding) metrics.
3. **Complex Year-End Consolidation:** External auditors must spend days manually sorting through thousands of invoices to extract internal transactions for elimination.
4. **Credit Limits & Tax Policies:** External customers have strict credit limits and standard sales tax (VAT/GST) rules. Sister companies require unlimited credit lines, zero-rated internal transfer pricing, and specific Intercompany Clearing GL accounts.

By creating a designated **Inter Company Customer Group** and tagging it via the app's custom field `ic_customer_group`, ERPNext automatically segregates internal debtors, enables automated period-end elimination, and prevents internal orders from being blocked by standard retail credit policies.

#### 3.8.2 Practical Real-World Setup Example
**Scenario:**
- **Parent Entity:** *Apex Global Industrial Ltd.* (Manufacturing & R&D)
- **Sister Subsidiary:** *Apex Middle East Distribution LLC* (Regional Sales Office)

**Step-by-Step Implementation:**
1. **Create the Inter Company Customer Group:**
   - Go to **Selling > Customer Group > New**.
   - `Customer Group Name`: **Inter Company Trading Group**
   - `Parent Customer Group`: **All Customer Groups**
   - `Is Group`: **No** (Unchecked)
   - Save.

2. **Configure Dedicated Intercompany Clearing Accounts (Recommended):**
   - In the newly created Customer Group form, expand the **Credit Limit and Default Accounts** table:
     - `Company`: *Apex Global Industrial Ltd.*
     - `Default Account`: `1310 - Intercompany Receivables - Apex ME` (instead of standard `1300 - Accounts Receivable Debtors`)
   - Save.

3. **Assign to Internal Customer:**
   - Go to **Selling > Customer > New** (or open existing internal customer):
     - `Customer Name`: **Apex Middle East Distribution LLC (Internal)**
     - `Customer Group`: **Inter Company Trading Group**
     - Under *Inter Company Information*:
       - `Is Internal Customer`: **Checked**
       - `Represents Company`: **Apex Middle East Distribution LLC**
       - `Inter Company Customer Group` (`ic_customer_group`): **Inter Company Trading Group**
   - Save.

4. **Outcome in Trade & Reporting:**
   - When *Apex Global* issues a $100,000 Sales Invoice to *Apex ME*, it posts to `1310 - Intercompany Receivables` rather than third-party trade receivables.
   - On the **Inter Company Elimination Run**, selecting `Customer Group: Inter Company Trading Group` isolates 100% of inter-group invoices and generates the elimination journal entry with zero risk of touching external client balances.

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
