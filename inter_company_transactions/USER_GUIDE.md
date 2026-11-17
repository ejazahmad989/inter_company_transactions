# Inter-Company Transactions for ERPNext: Enterprise User Guide & Tutorial
**Version:** 2.0 (Enterprise Edition)  
**Compatibility:** Frappe Framework v15 & v16 / ERPNext v15 & v16 (Certified)  
**Author:** Ejaz Ahmed (ejazahmad989@gmail.com)  
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

3. **Intelligent Dynamic Party Detection (Zero Manual Ticking Required)**:
   - When you select a **Customer** in *Sales Invoice*, *Sales Order*, *Delivery Note*, or *Quotation*, the system checks if the customer is configured in `Intercompany Transaction Link`.
   - When you select a **Supplier** in *Purchase Invoice*, *Purchase Order*, *Purchase Receipt*, or *Supplier Quotation*, the system checks if the supplier is configured in `Intercompany Transaction Link`.
   - In **Payment Entry**, when choosing `party_type` (Customer/Supplier) and selecting `party`, the engine immediately evaluates the party mapping.
   - In **Journal Entry**, when you add an account line with Debtors/Creditors and choose the `party` (Customer or Supplier), the system instantly sets `intercompany_target_company` on that row, ticks header `Is Intercompany`, and selects the linked sister company.
   - If the party is changed to a regular third party, the system automatically unchecks `Is Intercompany` and restores the standard internal company mode.

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

#### 3.1.2 Intelligent Auto-Switching in Intercompany Transaction Type
When defining transaction pairings in `Intercompany Transaction Link` -> `Transaction Types` child table or `Intercompany Transaction Type`:
- **Instant Auto-Switch**: Whenever you choose or change **Source Transaction Type**, the **Target Transaction Type** field automatically switches to its counterpart:
  - **Sales Order** &rarr; **Purchase Order**
  - **Purchase Order** &rarr; **Sales Order**
  - **Sales Invoice** &rarr; **Purchase Invoice**
  - **Purchase Invoice** &rarr; **Sales Invoice**
  - **Delivery Note** &rarr; **Purchase Receipt**
  - **Purchase Receipt** &rarr; **Delivery Note**
  - **Stock Entry** &rarr; **Stock Entry**
  - **Journal Entry** &rarr; **Journal Entry**
  - **Payment Entry** &rarr; **Payment Entry**
  - **Quotation** &rarr; **Supplier Quotation**
  - **Supplier Quotation** &rarr; **Quotation**
  - **Material Request** &rarr; **Purchase Order**
  - **Request for Quotation** &rarr; **Supplier Quotation**
  - **Subcontracting Order** &rarr; **Purchase Order**
  - **Landed Cost Voucher** &rarr; **Journal Entry**
- **Direction Default**: Direction automatically defaults to **Both** (bi-directional sync) if not specified.
- **Preload All Types Button**: You can also click **Populate All Transaction Types** in `Intercompany Transaction Link` to insert all standard combinations with one click.

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

### 3.7 Inter Company Remote Site (Federated Multi-Site Synchronization)
* **Location:** `Inter Company > Inter Company Settings > Federated Remote ERPNext Sites`
* **Purpose:** Enables real-time, zero-touch transaction mirroring across separate, independent ERPNext instances hosted on distinct physical servers, VPS instances, or cloud environments (e.g., AWS, DigitalOcean, Frappe Cloud).

#### 3.7.1 Architecture & Security Model
1. **REST API Token Authentication:** Communicates via Frappe's standard REST API using API Key and API Secret headers (`Authorization: token api_key:api_secret`).
2. **HMAC-SHA256 Payload Signatures:** Each outbound payload is hashed with a shared HMAC secret. The receiving instance verifies the signature before processing to guarantee authenticity.
3. **Idempotency Guarantee:** Every transaction includes an idempotency token (`{source_site}:{doctype}:{name}`). If a network disruption triggers a retry, the receiving instance recognizes the token and returns the existing mirrored document without duplicating entries.
4. **Offline Resilience & Auto-Retry Worker:** If the remote instance is temporarily offline or unreachable due to a firewall issue, the transaction is saved locally and queued in *Inter Company Error Log* (`Pending Retry`). The hourly background scheduler automatically retries pending syncs once connectivity is restored.
5. **Bi-Directional Cancellation:** When a source document is cancelled on Site A, a signed cancellation request is dispatched to Site B to cleanly cancel or void the mirrored document.

#### 3.7.2 Network, Port & Firewall Configuration Guide
For successful cross-instance communication, the sending and receiving servers must be able to establish TCP connections:

| Port | Protocol | Purpose | Direction |
|---|---|---|---|
| **443** (Recommended) | HTTPS / TLS 1.3 | Encrypted REST API synchronization | Inbound on destination server |
| **80** | HTTP | Plaintext web traffic & SSL challenges | Inbound on destination server |
| **8000** | HTTP | Direct Bench developer port (if not using NGINX) | Inbound on destination server |

**Firewall Rules Setup on the Remote Server:**
* **Ubuntu / Debian (UFW):**
  ```bash
  sudo ufw allow 443/tcp comment 'ERPNext Intercompany Sync'
  sudo ufw reload
  ```
  *(To restrict access strictly to the sending server IP: `sudo ufw allow from [SENDING_IP] to any port 443 proto tcp`)*

* **CentOS / RHEL / AlmaLinux (Firewalld):**
  ```bash
  sudo firewall-cmd --permanent --add-port=443/tcp
  sudo firewall-cmd --reload
  ```

* **AWS EC2 / DigitalOcean Cloud Firewalls:**
  Add an Inbound Rule allowing TCP port `443` from the sending server's public IP address.

#### 3.7.3 Built-in GUI Network & Firewall Diagnostic Tool
You do not need server SSH access to test connectivity:
1. Navigate to **Inter Company Settings**.
2. Click **Actions > Diagnose Network & Firewall**.
3. Select your pre-configured Remote Site or enter any target URL.
4. Click **Run Diagnostic Test**.
5. The diagnostic engine tests 6 layers in real-time:
   - **URL & Protocol:** Validates HTTPS encryption.
   - **DNS Resolution:** Confirms the remote domain name resolves to an IP address.
   - **TCP Port Reachability:** Connects to port 443/80 and measures round-trip socket latency in milliseconds.
   - **SSL/TLS Handshake:** Verifies certificate validity.
   - **Frappe API Authentication:** Tests API Key and Secret against `/api/method/frappe.auth.get_logged_user`.
   - **App Version Handshake:** Verifies that `inter_company_transactions` is installed on the remote instance.
6. If any step fails (e.g. firewall blocking port 443), the dialog generates exact copy-pasteable Linux commands to resolve the issue!


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

### Visual System Architecture: Entity Relationship & Data Flow
```
+------------------------------------------------------------------------------------+
|                         GROUP CONGLOMERATE STRUCTURE                               |
|                                                                                    |
|                            [ Main Company ]                                        |
|                          (Central Manufacturer)                                    |
|                                 /        \                                         |
|                       Trading  /          \  Trading                               |
|                      & Clearing            & Clearing                              |
|                              v              v                                      |
|                  [ Sister Company 1 ] <---> [ Sister Company 2 ]                   |
|                  (Wholesale & Dist.)        (Retail & Export)                      |
|                                                                                    |
|             <=========== 3-Way Multilateral Netting Cycle ===========>             |
|             <===== Group Consolidation & Elimination Journal Run =====>             |
+------------------------------------------------------------------------------------+
```

---

### Example A: Commercial Order-to-Cash & Procure-to-Pay Mirroring
**Scenario:** `Main Company` manufactures 100 units of "Component Alpha" and sells them to `Sister Company 1` at $50/unit ($5,000 total).

```
+------------------------------------------------------------------------------------+
|  SOURCE: Main Company                              TARGET: Sister Company 1        |
|                                                                                    |
|  1. SALES ORDER (SO-2026-0001)     ==============> PURCHASE ORDER (PO-2026-0001)   |
|     Customer: Sister Company 1 (Int)               Supplier: Main Company (Int)    |
|     Item: Component Alpha (Qty: 100)               Item: Component Alpha (Qty: 100)|
|     Rate: $50.00 | Total: $5,000                   Rate: $50.00 | Total: $5,000    |
|     Status: Submitted                              Status: Draft or Submitted      |
|                                                                                    |
|  2. DELIVERY NOTE (DN-2026-0001)   ==============> PURCHASE RECEIPT (PR-2026-0001) |
|     Dispatches 100 units from                      Receives 100 units into         |
|     Main Stores Warehouse                          Sister 1 Finished Goods         |
|                                                                                    |
|  3. SALES INVOICE (SINV-2026-0001) ===============> PURCHASE INVOICE (PINV-0001)   |
|     Dr. Intercompany AR $5,000                     Dr. Inventory / Cost $5,000     |
|     Cr. Sales Revenue   $5,000                     Cr. Intercompany AP  $5,000     |
+------------------------------------------------------------------------------------+
```

#### Step-by-Step Execution:
1. Log into **Main Company**. Create a new **Sales Order**.
2. Select Customer: `Sister Company 1 (Internal)`. Add Item `Component Alpha`, Qty `100`, Rate `$50`.
3. Submit the document.
4. **Instant Result:** A banner confirms:
   `Inter Company: Linked Purchase Order PO-2026-0001 has been automatically created in Sister Company 1.`
5. When `Main Company` creates the **Delivery Note**, the corresponding **Purchase Receipt** is generated automatically in `Sister Company 1`.
6. When `Main Company` creates the **Sales Invoice**, the matching **Purchase Invoice** is generated in `Sister Company 1`.

---

### Example B: Financial Mirroring & 2-Way Settlement
**Scenario:** `Sister Company 1` pays `Main Company` $5,000 to settle the invoice, or `Main Company` reallocates a shared group IT expense to `Sister Company 1`.

```
+------------------------------------------------------------------------------------+
|  CASE 1: PAYMENT ENTRY (SETTLEMENT)                                                |
|  Sister Company 1 (Payer):                         Main Company (Payee):           |
|  Type: Pay (ACC-PAY-2026-0001)     ==============> Type: Receive (ACC-PAY-0002)    |
|  Party: Main Company (Supplier)                    Party: Sister Company 1 (Cust.) |
|  Dr. Accounts Payable $5,000                       Dr. Bank Account $5,000         |
|  Cr. Bank Account     $5,000                       Cr. Accounts Receivable $5,000  |
|                                                                                    |
|  CASE 2: SHARED EXPENSE JOURNAL ENTRY                                              |
|  Main Company (Payer):                             Sister Company 1 (Recharged):   |
|  Journal Entry (ACC-JV-2026-0001)  ==============> Journal Entry (ACC-JV-0002)     |
|  Dr. Interco Clearing $1,000                       Dr. Software Expense $1,000     |
|  Cr. Bank Account     $1,000                       Cr. Interco Clearing $1,000     |
+------------------------------------------------------------------------------------+
```

---

### Example C: Transfer Pricing Policy (OECD Arm's Length Compliance)
**Scenario:** Tax regulations mandate that sales between `Main Company` and `Sister Company 1` must include a **10% Cost-Plus markup** to reflect arm's-length market pricing.

```
+------------------------------------------------------------------------------------+
|                         TRANSFER PRICING POLICY (TPP-0001)                         |
|                                                                                    |
|  From Company: Main Company (Seller)      To Company: Sister Company 1 (Buyer)     |
|  OECD Method:  Cost-Plus Markup %         Markup Percentage: 10.0%                 |
|  Item: Component Alpha                    Effective: 2026-01-01 to 2026-12-31      |
|                                                                                    |
|  PRICING CALCULATION ENGINE:                                                       |
|    Base Valuation Cost in Main Company = $200.00                                   |
|    Transfer Rate = $200.00 x (1 + 0.10) = $220.00                                  |
|                                                                                    |
|  AUTOMATION RESULT:                                                                |
|    When Sales Order is submitted in Main Company at $200.00,                       |
|    the mirrored Purchase Order in Sister Company 1 automatically receives $220.00. |
|    OECD Tax Audit dossier notes are stored for statutory auditors.                 |
+------------------------------------------------------------------------------------+
```

---

### Example D: Raising and Resolving an Inter Company Dispute
**Scenario:** `Main Company` bills `Sister Company 1` for $1,200 on Sales Invoice `SINV-0001` (10 units @ $120). Upon receipt, `Sister Company 1` finds 2 units damaged, claiming they should only pay $960.

```
+------------------------------------------------------------------------------------+
|                         INTER COMPANY DISPUTE WORKFLOW                             |
|                                                                                    |
|  1. INVOICE MISMATCH:                                                              |
|     Main Company Billed:  $1,200 (10 units)                                        |
|     Sister Company 1 Due: $960   (8 units accepted)                                |
|                                                                                    |
|  2. RAISE DISPUTE (New Inter Company Dispute):                                     |
|     Document Type: Sales Invoice | Name: SINV-0001                                 |
|     Source Company: Main Company | Target Company: Sister Company 1                |
|     Reason: Damaged Goods        | Status: Open                                    |
|     Billed Amount:  $1,200.00                                                      |
|     Claimed Amount: $960.00                                                        |
|     Variance Amount: $240.00 (Automatically calculated)                            |
|                                                                                    |
|  3. AUTOMATIC RESOLUTION (Click "Execute Resolution"):                             |
|     Option A: "Issue Credit Note" -> Auto-generates Return Sales Invoice for -$240 |
|     Option B: "Issue Debit Note"  -> Auto-generates Return Purchase Invoice in S1  |
|     Option C: "Journal Adjustment"-> Books balancing JV for $240 variance          |
|     Option D: "Accept Variance"   -> Marks dispute Resolved with no GL entry       |
+------------------------------------------------------------------------------------+
```

---

### Example E: Multilateral 3-Company Netting Cycle
**Scenario:** Month-end cross-company debt settlement between `Main Company`, `Sister Company 1`, and `Sister Company 2`.

```
+------------------------------------------------------------------------------------+
|                      MULTILATERAL 3-COMPANY NETTING CYCLE                          |
|                                                                                    |
|    Main Company   ---- owes $10,000 ---->  Sister Company 1                        |
|         ^                                        |                                 |
|         |                                        |                                 |
|      owes $7,000                             owes $8,000                           |
|         |                                        |                                 |
|         +---------- Sister Company 2 <-----------+                                 |
|                                                                                    |
|  WITHOUT NETTING (Gross Settlements):                                              |
|    3 separate bank wire transfers totaling $25,000 with cross-border banking fees. |
|                                                                                    |
|  NET POSITIONS (Calculated via Multilateral Greedy Solver):                        |
|    * Main Company:     -$3,000 (Net Debtor  - owes money)                          |
|    * Sister Company 1: +$2,000 (Net Creditor - owed money)                         |
|    * Sister Company 2: +$1,000 (Net Creditor - owed money)                         |
|                                                                                    |
|  WITH NETTING (Optimized Settlements Generated on Submit):                         |
|    1. Main Company pays $2,000 directly to Sister Company 1                        |
|    2. Main Company pays $1,000 directly to Sister Company 2                        |
|    TOTAL CASH TRANSFERRED: $3,000 (Liquidity savings: $22,000; wire fees cut by 67%)|
|    Auto-posts clearing Journal Entries across all 3 company ledgers.               |
+------------------------------------------------------------------------------------+
```

---

### Example F: Group Consolidation Elimination Run (Holding Company)
**Scenario:** Preparing group consolidated balance sheet and P&L under IFRS 10 / US GAAP. Internal sales and mutual debts must be eliminated.

```
+------------------------------------------------------------------------------------+
|                    INTER COMPANY ELIMINATION RUN (CONSOLIDATION)                   |
|                                                                                    |
|  Period: March 2026 | Consolidation Company: Parent Group Holdings                 |
|                                                                                    |
|  UNELIMINATED GROUP TOTALS:                                                        |
|    * Intercompany Sales Revenue across entities: $50,000                           |
|    * Intercompany Cost of Goods Sold / Purchases: $50,000                          |
|    * Intercompany Accounts Receivable (AR):       $50,000                          |
|    * Intercompany Accounts Payable (AP):          $50,000                          |
|                                                                                    |
|  ONE-CLICK SUBMISSION ACTION:                                                      |
|    Generates Consolidation Elimination Journal Entry in Parent Group Holdings:     |
|      Dr. Intercompany Sales Revenue  $50,000 (Neutralizes internal revenue)        |
|      Cr. Intercompany COGS           $50,000 (Neutralizes internal cost of sales)  |
|      Dr. Accounts Payable            $50,000 (Neutralizes internal liability)      |
|      Cr. Accounts Receivable         $50,000 (Neutralizes internal asset)          |
|                                                                                    |
|  RESULT: Audited Consolidated P&L and Balance Sheet ready for statutory filing.    |
+------------------------------------------------------------------------------------+
```

---

### Example G: Inter Company Error Log & 1-Click Self-Healing
**Scenario:** An accountant in `Main Company` submits a Sales Order for an item that is temporarily disabled in `Sister Company 1`.

```
+------------------------------------------------------------------------------------+
|                         ERROR LOG & RECOVERY WORKFLOW                              |
|                                                                                    |
|  1. EXCEPTION CAUGHT:                                                              |
|     Target creation in Sister Company 1 halted: "Item COMP-ALPHA is disabled".     |
|     Main Company's Sales Order submits safely without breaking user session.       |
|                                                                                    |
|  2. LOGGED IN "Inter Company Error Log":                                           |
|     * Source: Sales Order SO-2026-0001 | Target: Sister Company 1                   |
|     * Status: Pending / Failed          | Traceback: Full error stack stored        |
|                                                                                    |
|  3. RECOVERY:                                                                      |
|     Administrator enables the item in Sister Company 1,                            |
|     then opens the error log and clicks [Retry Sync].                              |
|     Status updates to "Retried Successfully" and target document is generated.     |
|     * Scheduled task also retries pending records automatically every hour.        |
+------------------------------------------------------------------------------------+
```

---

### Example H: ICT Notification Setting (User-Level Alert Controls)
**Scenario:** Controlling alerts so finance personnel receive critical notices without alert fatigue.

```
+------------------------------------------------------------------------------------+
|                        ICT NOTIFICATION SETTING PER USER                           |
|                                                                                    |
|  User: accounts_lead@company.com                                                   |
|  [X] Enabled                       [X] In-App Bell Alerts                          |
|  [X] Email Notifications           [ ] Status Updates (Daily syncs - muted)        |
|  [X] Approval Requests             [X] Dispute Alerts (Notified when sister co.    |
|  [X] Netting Cycle Alerts              raises a discrepancy)                       |
|  [X] Elimination Run Alerts                                                        |
+------------------------------------------------------------------------------------+
```

---

### Example I: SMS Template & Core ERPNext Integration Architecture
**Scenario:** Sending automated SMS alerts to warehouse managers or drivers upon intercompany dispatches.

```
+------------------------------------------------------------------------------------+
|                           SMS NOTIFICATIONS ARCHITECTURE                           |
|                                                                                    |
|  [ Your Inter Company App ]                  [ ERPNext Core Framework ]            |
|  DocType: "SMS Template"                     DocType: "SMS Settings"               |
|  +---------------------------+               +----------------------------------+  |
|  | Template: Stock Dispatch  |               | Gateway: Twilio / Plivo / Custom |  |
|  | Message: Transfer of      |               | Core API Secret: *************** |  |
|  | {{ qty }} items to sister |               +----------------+-----------------+  |
|  +-------------+-------------+                                |                    |
|                |                                              |                    |
|                +------------> [ Core frappe.sendmail / SMS ] <+                    |
|                                              |                                     |
|                                              v                                     |
|                                    [ Recipient Mobile ]                            |
|                                                                                    |
|  CRITICAL FACTS FOR APP BUYERS & SOLO FOUNDERS:                                    |
|  1. SMS is 100% OPTIONAL: The entire app runs smoothly with zero SMS configuration.|
|  2. NO API KEYS REQUIRED IN THIS APP: Your app requires no secret keys or gateway. |
|  3. NATIVE INTEGRATION: If a customer wants SMS, they configure standard ERPNext   |
|     core "SMS Settings". The app seamlessly leverages that native core connection. |
+------------------------------------------------------------------------------------+
```

---

### Example J: Multi-Currency Intercompany Transactions (Step-by-Step PKR vs USD)
**Scenario:** A conglomerate operates with two entities with different legal currencies:
* **Main Company:** Default Currency: **PKR**
* **Sister Company 1:** Default Currency: **USD**
* **Exchange Rate:** 1 USD = 280 PKR (or 1 PKR = 0.00357 USD)

#### Is there a Custom Field needed for Currency?
**No new custom field is required!** ERPNext natively provides multi-currency capabilities (`currency`, `conversion_rate`, `party_account_currency`) across all transactional documents, and this app automatically integrates with them. You only need the standard transaction control fields:
1. **`is_intercompany` (Check):** Tick on any transaction to trigger intercompany mirroring.
2. **`intercompany_target_company` (Link):** Select the target sister company (`Sister Company 1`).

#### Step-by-Step Setup:
1. **Define Exchange Rates in ERPNext:**
   - Navigate to **Accounting > Setup > Currency Exchange**.
   - Create a record: `From Currency` = **USD**, `To Currency` = **PKR**, `Exchange Rate` = **280.0**.
2. **Setup Internal Customer & Supplier Profiles:**
   - In `Main Company (PKR)`: Set Customer & Supplier for `Sister Company 1` with Billing Currency = **USD**.
   - In `Sister Company 1 (USD)`: Set Customer & Supplier for `Main Company` with Billing Currency = **USD**.
3. **Configure Link:** In **Inter Company > Intercompany Transaction Link**, add `Sister Company 1` in the linked companies table.

#### How Each Document Operates Across Currencies:
* **Sales Order to Purchase Order:** Sales Order created in `Main Company` for $1,000 USD creates a matching Purchase Order in `Sister Company 1` for $1,000 USD.
* **Delivery Note to Purchase Receipt:** Stock valuation rate is accurately converted from PKR to USD so `Sister Company 1`'s stock ledger remains mathematically exact.
* **Payment Entry:** A payment of 280,000 PKR from `Main Company` creates a receipt of $1,000 USD in `Sister Company 1`.
* **Balance Reconciliation Report:** Converts balances using the transaction date exchange rate and reports the true base-currency variance.

---

## 5. Multi-Version Compatibility: ERPNext v15 & v16

### Why this single app runs seamlessly on ERPNext v15 and v16
```
+------------------------------------------------------------------------------------+
|                 COMPATIBILITY MATRIX: ERPNEXT v15 & v16 CERTIFIED                  |
|                                                                                    |
|  Platform Edition  | Python Versions       | Frappe Version | ERPNext Status       |
|  ------------------+-----------------------+----------------+--------------------  |
|  ERPNext v15       | Python 3.10/3.11/3.12 | Frappe v15.x   | Fully Compatible     |
|  ERPNext v16       | Python 3.12 / 3.13+   | Frappe v16.x   | Certified Ready      |
+------------------------------------------------------------------------------------+
```

#### Technical Guarantees for Marketplace Buyers:
1. **Universal ORM & Document API:** The app exclusively uses Frappe's universal ORM functions (`frappe.get_doc`, `frappe.new_doc`, `frappe.db.get_value`, `frappe.db.exists`). These core APIs are 100% stable and identical across Frappe v15 and v16.
2. **Python Compatibility (`>= 3.10`):** The Python codebase uses modern clean syntax compliant with Python 3.10, 3.11, 3.12, and 3.13+. No deprecated Python standard modules (like `imp`, `pipes`, or removed `cgi` utilities) are used.
3. **Collision-Free Migration:** Custom fields are created dynamically with programmatic duplicate-checking rather than rigid SQL dumps. Upgrades from v15 to v16 will never break database constraints.
4. **Modern Build System:** Uses standard `flit_core >=3.4` in `pyproject.toml`, which is the official Frappe packaging standard for Frappe Cloud and bench deployments.


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
