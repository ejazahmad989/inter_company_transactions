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