# User Guide for Inter-Company Transactions App

This guide explains how to use the Inter-Company Transactions app to set up and manage inter-company transactions between related companies in ERPNext.

## Overview

The Inter-Company Transactions app allows you to automatically create corresponding transactions between related companies. For example, when you create a Sales Order in Company A, a Purchase Order can be automatically created in Company B.

## Key Features

- Map transaction types between companies
- Automatic creation of corresponding transactions
- Two-way transaction synchronization
- Linked cancellation across companies
- Support for multiple transaction types
- Draft creation mode

## Setting Up

### Creating an Inter-Company Transaction Map

1. Go to **Inter Company Transactions > Inter Company Transaction Map**
2. Click **New**
3. Enter the following details:
   - **Main Company**: Select your primary company
   - **Enabled**: Check this to activate the mapping
   
4. In the **Transaction Mappings** table, add rows for each transaction type:
   - **Main Company Transaction Type**: Select the transaction type (e.g., Sales Order)
   - **Main Company Customer/Supplier**: If applicable, select the customer or supplier
   - **Other Company**: Select the related company
   - **Other Company Transaction Type**: Select the corresponding transaction type (e.g., Purchase Order)
   - **Other Company Customer/Supplier**: If applicable, select the corresponding customer or supplier
   - **Auto Submit**: Check if you want transactions to be automatically submitted

5. Save the document

## Using the App

### Creating Inter-Company Transactions

Once you've set up the mapping, the app works automatically:

1. Create a transaction (e.g., Sales Order) in your main company
2. When you submit the transaction, a corresponding transaction will be created in the linked company
3. Depending on your settings, the linked transaction will be either in Draft state or Submitted

## Using the App

### "Is Intercompany" Checkbox & Dynamic Target Company Selection

In everyday accounting and operations, the vast majority of transactions created in ERPNext (such as standard supplier payments, customer receipts, local purchases, or day-to-day journal entries) are **internal to the single company** and must not trigger mirror transactions in sister companies.

To handle this cleanly and prevent accidental cross-company postings:

1. **Default State (Standard Internal Transaction)**:
   - The **"Is Intercompany"** (`is_intercompany`) checkbox is **unchecked (`0`) by default** on all transactions.
   - The **"Intercompany Target Company"** (`intercompany_target_company`) field remains **read-only** and automatically defaults to your current company (e.g., `ABC Company`).
   - Normal vouchers submit seamlessly without requiring any target company input and without creating duplicate mirror entries in other companies.

2. **Inter-Company Mode (Transaction with Sister Company)**:
   - When creating a transaction intended for a sister company, check the **"Is Intercompany"** box.
   - Upon ticking:
     - **Intercompany Target Company** instantly becomes **editable and mandatory**.
     - If it previously held the current company name, it clears automatically so you can pick the destination company.
     - The company dropdown query automatically **filters out your current company**, ensuring you can only select legitimate sister companies (e.g., `XYZ Logistics Ltd`).
   - If you uncheck the box at any point before submission, the target company resets back to read-only with your current company name.
   - When submitted, the system verifies the target company and automatically creates the corresponding mirror transaction in the target sister company.

---

### Understanding "Inter Company Customer Group" & "Inter Company Supplier Group"

#### Why do we need Inter Company Customer / Supplier Groups?

In ERPNext, a **Customer** or **Supplier** record usually belongs to a standard group (such as `All Customer Groups`, `Commercial`, `Individual`, or `Local`). However, when multi-company intercompany trading is established:
- **Company A** considers sister **Company B** as a **Customer** (when selling goods to it).
- **Company B** considers sister **Company A** as a **Supplier** (when receiving goods from it).

In large groups with dozens of sister companies, entities, or branches, managing direct 1-to-1 links across every single party record can become cumbersome. **"Inter Company Customer Group"** and **"Inter Company Supplier Group"** provide group-level categorization specifically designated for sister companies and internal trading entities.

#### Key Functions of Inter Company Customer Group:
1. **Separation from External Customers**: Keeps intercompany trading partners segregated from regular external commercial clients in financial reports and aging analyses.
2. **Automated Cross-Company Party Discovery**: When the app mirrors a Sales Order into a Purchase Order, it looks up the customer's `ic_customer_group` to find the matching sister entity in the target company chart.
3. **Consolidated Elimination**: Simplifies Year-End and Month-End intercompany elimination entries by allowing accountants to filter receivables and payables specifically tagged with the Inter Company group.

#### Practical Example:
> **Scenario**:
> - Parent group has two companies: **Apex Manufacturing Ltd** (Company A) and **Apex Distribution Ltd** (Company B).
> 
> **Setup**:
> 1. Go to **Selling > Customer Group** and create a group named `Sister Companies` (with `Custom Company` linked to the group).
> 2. Go to **Apex Manufacturing Ltd**'s Customer list:
>    - Create/Open Customer **Apex Distribution Ltd**.
>    - Set standard Customer Group: `Commercial`.
>    - Set **Inter Company Customer Group**: `Sister Companies`.
> 3. Go to **Apex Distribution Ltd**'s Supplier list:
>    - Create/Open Supplier **Apex Manufacturing Ltd**.
>    - Set standard Supplier Group: `Local`.
>    - Set **Inter Company Supplier Group**: `Sister Companies`.
> 
> **Result**:
> When Apex Manufacturing creates an intercompany invoice, checking `Is Intercompany` and picking `Apex Distribution Ltd` allows the automation engine to automatically map and route the mirror purchase entry to the correct internal supplier party using the shared `Sister Companies` classification!

---

## Transaction Type Mappings

### Fully Supported Mirror Transactions (13 DocTypes)

| Source Transaction Type | Mirror Target Transaction Type | Common Direction | Use Case |
| :--- | :--- | :--- | :--- |
| **Sales Order** | **Purchase Order** | Main to Other / Both | Sales order to sister distribution unit creates Purchase Order |
| **Purchase Order** | **Sales Order** | Main to Other / Both | Procurement from internal manufacturing unit creates Sales Order |
| **Sales Invoice** | **Purchase Invoice** | Main to Other / Both | Internal billing mirrors directly into vendor invoice |
| **Purchase Invoice** | **Sales Invoice** | Main to Other / Both | Mirror vendor bill back to sister sales invoice |
| **Delivery Note** | **Purchase Receipt** | Main to Other / Both | Shipping goods creates receiving docket in sister warehouse |
| **Purchase Receipt** | **Delivery Note** | Main to Other / Both | Receiving goods mirrors fulfillment from sister company |
| **Stock Entry** | **Stock Entry** | Main to Other / Both | Material transfer between company warehouses (Issue / Receipt) |
| **Journal Entry** | **Journal Entry** | Main to Other / Both | Cross-company debt allocation, expense splitting, charges |
| **Payment Entry** | **Payment Entry** | Main to Other / Both | Internal treasury settlement, intercompany advances/reimbursements |
| **Quotation** | **Supplier Quotation** | Main to Other / Both | Estimate sent to sister company creates supplier quotation |
| **Supplier Quotation** | **Quotation** | Main to Other / Both | Quote from sister company creates sales quotation |
| **Material Request** | **Sales Order** / **Purchase Order** | Main to Other / Both | Internal replenishment request automatically spawns procurement |
| **Request for Quotation** | **Supplier Quotation** | Main to Other / Both | Formal price inquiry mirrors to sister sales desk |

### Unsupported Transactions & Why

The following ERPNext DocTypes do **not** support automated intercompany mirroring:
- **POS Invoice**: Point-of-Sale transactions are strictly point-of-sale retail encounters with walking customers at a cash register; they are never inter-company wholesale trades.
- **Subcontracting Order / Inward Subcontracting**: These depend on specialized multi-level BOM transfer workflows managed natively by ERPNext subcontracting engines.
- **Asset Capitalization / Asset Movement**: Fixed assets require local legal ownership depreciation books per company; automated cross-company asset mirroring without formal tax asset sale/purchase invoices violates statutory compliance.
- **Bank Clearance / Bank Guarantee**: Bank-specific instrument documents tied exclusively to individual bank institutions of a single legal entity.

---

### Cancelling Transactions

If you cancel a transaction, the linked transaction will also be cancelled automatically:

1. Open the original transaction
2. Click **Cancel**
3. The system will automatically cancel the linked transaction in the other company

### Viewing Linked Transactions

To see the linked transaction:

1. Open your transaction
2. Look for the "Inter Company Reference" field
3. Click on the reference to open the linked transaction

## Transaction Type Mappings

The following transaction types are supported:

- **Sales Order** → **Purchase Order**
- **Purchase Order** → **Sales Order**
- **Journal Entry** → **Journal Entry**
- **Payment Entry** → **Payment Entry**

## Best Practices

1. **Set up companies properly**: Ensure that all companies have the correct settings, including default accounts and cost centers.

2. **Map accounts carefully**: Make sure that accounts are correctly mapped between companies for seamless transactions.

3. **Test before using in production**: Always test the workflow with a few transactions before implementing it in your production environment.

4. **Use the Auto Submit feature carefully**: Only enable Auto Submit when you're confident in your setup and don't need to review transactions before submission.

5. **Regular reconciliation**: Periodically reconcile inter-company accounts to ensure they remain balanced.

## Troubleshooting

### Common Issues

1. **Transaction not created in linked company**:
   - Check if the mapping is enabled
   - Verify that the customer/supplier is correctly selected in the mapping

2. **Accounts mismatch**:
   - Ensure that the accounts exist in both companies
   - Check the account mapping logic in the app

3. **Errors during transaction creation**:
   - Check the Frappe Error Logs for specific error messages
   - Verify that all required fields are populated in the transaction