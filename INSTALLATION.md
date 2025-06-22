# Installation Guide for Inter-Company Transactions App

This guide will help you install and set up the Inter-Company Transactions app in your ERPNext installation.

## Prerequisites

- ERPNext v13 or higher
- Frappe Framework v13 or higher
- Administrator access to your ERPNext instance

## Installation Steps

### Step 1: Get the App

Clone the repository or download the zip file:

```bash
cd /home/frappe/frappe-bench
bench get-app inter_company_transactions https://github.com/your-repo/inter_company_transactions
```

### Step 2: Install the App on Your Site

```bash
bench --site your-site.local install-app inter_company_transactions
```

### Step 3: Run Migrations

```bash
bench --site your-site.local migrate
```

### Step 4: Restart the Server

```bash
bench restart
```

## Configuration

### Step 1: Create Inter-Company Transaction Map

1. Go to **Inter Company Transactions > Inter Company Transaction Map**
2. Create a new record
3. Select your main company
4. Add transaction mappings for each transaction type and company combination
5. Save the document

### Step 2: Test the Configuration

1. Create a transaction (e.g., Sales Order) in your main company
2. When you submit the transaction, a corresponding transaction will be created in the linked company
3. Verify that the transaction was created correctly

## Troubleshooting

If you encounter any issues:

1. Check the Frappe Error Logs
2. Ensure that the companies are correctly set up
3. Verify that the customers and suppliers are correctly linked
4. Make sure the accounts are mapped correctly between companies

## Support

For support, please open an issue on the GitHub repository or contact us at support@example.com.