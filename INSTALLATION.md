# Setup & Configuration Guide — Inter-Company Transactions

This guide helps you install the app via **Frappe Cloud Marketplace** and configure inter-company mirroring across ERPNext v15 and v16.

## Prerequisites

- ERPNext v15 or v16
- Frappe Framework v15 or v16
- System Manager / Administrator access to your ERPNext site

## Marketplace Installation

1. Install **Inter-Company Transactions** directly from the **Frappe Cloud Marketplace** on your target site/bench.
2. Open your ERPNext Desk after installation completes.

## Desk Configuration

### Step 1: Configure Intercompany Transaction Link

1. Search for **Intercompany Transaction Link** in Frappe Desk and click **Add Intercompany Transaction Link**.
2. Select your **Main Company**.
3. In **Linked Companies**, add each sister company and map the internal **Customer**, **Supplier**, `TMP-*` Bank clearing account (or click **Auto-Create Clearing Accounts**), and transit **Warehouse**.
4. In **Transaction Types**, click **Populate Default Transaction Types** to add all supported reciprocal pairs, or add specific rules as needed.
5. Click **Save**.

### Step 2: Configure Inter Company Settings

Open **Inter Company Settings** in Desk to choose:
- **Execution Mode** (*Synchronous* or *Asynchronous Background Job*)
- **Auto-Submit Target Document** (create Drafts vs auto-submit)
- **Cancellation Authority** (*Source Company Only* vs *Bidirectional*)
- **Default Transfer Pricing Rule** (*Source Document Rate*, *Cost / Valuation Rate*, or *Cost + Markup %*)
- **Remote Federated Sites** (optional cross-server synchronization)

### Step 3: Test Automated Mirroring

1. Create a **Sales Order** in Company A for Company B's internal customer (the form automatically marks **Is Intercompany** and sets Company B as target).
2. Submit the document to generate the mirrored **Purchase Order** in Company B automatically.

## Troubleshooting

1. Review **Inter Company Error Log** and **Error Log** in Desk for any sync or missing-account messages.
2. Ensure Companies, internal Customers/Suppliers, Currency Exchange rates (for multi-currency entities), and TMP Bank accounts are properly configured.

## Support

- **Publisher:** Ejaz Tech (`ejazahmad989@gmail.com`)
- **Support:** `rahilali3311@gmail.com`