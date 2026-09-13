# Installation Guide for Inter-Company Transactions

This ERPNext custom application automates transaction mirroring and synchronization between associated companies.

## System Prerequisites
- Frappe Framework v14 or v15
- ERPNext v14 or v15
- Python >= 3.10

## Bench Installation Steps

1. Change directory to your Frappe bench directory:
   ```bash
   cd ~/frappe-bench
   ```

2. Fetch the custom app repository into bench:
   ```bash
   bench get-app inter_company_transactions https://github.com/your-repo/inter_company_transactions
   ```
   *(Or clone directly into `apps/inter_company_transactions`)*

3. Install the application on your target ERPNext site:
   ```bash
   bench --site <your-site-name> install-app inter_company_transactions
   ```

4. Execute database migrations to provision custom doctypes and custom fields:
   ```bash
   bench --site <your-site-name> migrate
   ```

5. Clear bench cache and restart worker services:
   ```bash
   bench --site <your-site-name> clear-cache
   bench restart
   ```

## Verification
- Log in to your ERPNext desk.
- Search for **"Inter Company Transaction Map"** in the awesome bar.
- Configure your primary company, counterpart entity, and document mappings.
