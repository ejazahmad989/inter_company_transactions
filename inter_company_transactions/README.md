# Inter Company Transactions for ERPNext (v14 & v15)

[![Frappe](https://img.shields.io/badge/Frappe-v14%20%7C%20v15-blue.svg)](https://frappeframework.com/)
[![ERPNext](https://img.shields.io/badge/ERPNext-v14%20%7C%20v15-blue.svg)](https://erpnext.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](license.txt)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()
[![Marketplace](https://img.shields.io/badge/Frappe%20Marketplace-Verified-orange.svg)](MARKETPLACE.md)

An enterprise-grade, comprehensive Frappe / ERPNext application designed for corporate groups, holding companies, and conglomerates. Automates intercompany document mirroring, dynamic party-to-company auto-detection, transfer pricing, multilateral netting, period-end elimination entries, dispute management, cross-company balance reconciliation, and **federated remote multi-site synchronization across separate ERPNext servers**.

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
- **Cross-Server Integration**: Connects independent ERPNext instances hosted on separate servers or cloud providers via secure REST APIs.
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
- Consolidates reciprocal receivables and payables across 2, 3, or more sister entities into a unified netting settlement matrix.
- Minimizes bank transaction fees and cross-currency FX losses.
- Generates balancing clearing Journal Entries automatically.

### 8. Automated Financial Elimination Runs (Consolidation)
- Period-end elimination runs for:
  - Reciprocal internal revenues and expenses.
  - Reciprocal debtor and creditor balances.
  - Unrealized internal inventory profit.

### 9. Smart Item, Currency & Tax Synchronization
- **Auto-Create Missing Items**: Automatically replicates item code, description, and UOM into the target company if missing.
- **Multi-Currency Resolver**: Automatically converts foreign currency transactions using daily exchange rates or custom group rates.
- **Tax Handling Strategy**: Choice between mirroring exact net rates or applying target company tax templates for local VAT / GST compliance.

---

## 🌐 Remote Multi-Site Sync: Network & Firewall Setup Guide

When running two or more separate ERPNext instances (e.g. **Site A: `https://erp-a.company.com`** and **Site B: `https://erp-b.company.com`**):

### 1. Port Requirements
| Service | Recommended Port | Purpose | Direction |
|---|---|---|---|
| **HTTPS (Secure REST API)** | `443` | Encrypted intercompany sync | Inbound on both servers |
| **HTTP (Standard)** | `80` | ACME / Let's Encrypt SSL challenges | Inbound on both servers |
| **Custom Bench Port** | `8000` (or custom) | Non-NGINX direct bench access (development only) | Inbound if not using NGINX reverse proxy |

> 🔒 **Security Best Practice:** Always use **HTTPS (Port 443)** for production deployments. Traffic over port 443 uses TLS 1.3 encryption, safeguarding your financial transactions, item pricing, and API tokens.

---

### 2. Firewall Configuration (Step-by-Step)

If the GUI diagnostic tool reports that a port connection timed out, execute the appropriate command on the destination server:

#### A. Ubuntu / Debian (UFW - Uncomplicated Firewall)
```bash
# Allow inbound HTTPS traffic (Port 443)
sudo ufw allow 443/tcp comment 'ERPNext Intercompany Sync'

# If using standard HTTP (Port 80)
sudo ufw allow 80/tcp comment 'ERPNext HTTP'

# If restricting access to only the sending server IP (Recommended for maximum security):
sudo ufw allow from [SOURCE_SERVER_IP] to any port 443 proto tcp comment 'Intercompany Site A'

# Reload firewall to apply changes
sudo ufw reload
sudo ufw status verbose
```

#### B. CentOS / RHEL / Rocky Linux / AlmaLinux (Firewalld)
```bash
# Open port 443 permanently
sudo firewall-cmd --permanent --add-port=443/tcp

# Reload firewall rules
sudo firewall-cmd --reload

# Verify open ports
sudo firewall-cmd --list-ports
```

#### C. Raw Linux iptables
```bash
# Allow established and new inbound connections on port 443
sudo iptables -A INPUT -p tcp --dport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
```

#### D. Cloud Security Groups (AWS EC2, Google Cloud, DigitalOcean, Hetzner, Azure)
If your server is behind a cloud firewall or security group:
1. Navigate to your cloud provider console &rarr; **Security Groups / Firewall Rules**.
2. Add an **Inbound Rule**:
   - **Type:** HTTPS (or Custom TCP)
   - **Port:** `443` (or `80` / custom)
   - **Source:** Either `0.0.0.0/0` (Anywhere) or restrict to `[SOURCE_SERVER_IP]/32` for strict IP whitelisting.
3. Save changes.

---

### 3. NGINX Reverse Proxy Verification

ERPNext production instances use NGINX as the front-facing reverse proxy. Ensure NGINX is actively listening:
```bash
# Verify NGINX is active and listening
sudo systemctl status nginx

# Verify NGINX syntax
sudo nginx -t

# Test local port binding
sudo ss -tulpn | grep ':443'
```

---

### 4. Configuring Federated Remote Site in ERPNext GUI

1. On **Site B (Receiving Instance)**:
   - Navigate to **Users > Administrator** (or create an API integration user `intercompany-sync@company.com`).
   - Scroll to **API Access** &rarr; click **Generate Keys**.
   - Copy the generated **API Key** and **API Secret**.

2. On **Site A (Sending Instance)**:
   - Open **Inter Company Settings**.
   - Set **Deployment Mode** to `Federated Cross-Site (REST API)`.
   - In the **Federated Remote ERPNext Sites** table, click **Add Row**:
     - `Remote Site URL`: `https://erp-b.company.com`
     - `Remote Company Name`: Company Name as defined on Site B
     - `API Key`: Pasted from Site B
     - `API Secret`: Pasted from Site B
     - `HMAC Secret`: Optional shared secret token (e.g. `secret_passphrase_123`)
     - `Active`: Checked
   - Click **Save**.

3. **Verify with GUI Diagnostic Tool**:
   - In *Inter Company Settings*, click **Actions &rarr; Diagnose Network & Firewall**.
   - Select your remote site &rarr; click **Run Diagnostic Test**.
   - The system tests DNS, Port, SSL, API Token, and App Version, reporting green indicators and latency in milliseconds!

---

## 🚀 Installation & Quickstart

### 1. Install via Bench
```bash
bench get-app https://github.com/rahilali/inter_company_transactions.git
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
- **Author:** Rahil Ali (`rahilali3311@gmail.com`)
- **License:** MIT License (Commercial & Marketplace Ready)
- **Documentation:** Full guide available in `USER_GUIDE.md` and `Inter_Company_Transactions_User_Guide.pdf`.
