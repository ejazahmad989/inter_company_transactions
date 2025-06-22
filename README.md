# Inter Company Transactions

A custom ERPNext application that enables seamless inter-company transactions between related companies. This app allows for automatic creation and synchronization of transactions between a main company and its associated companies.

## Features

- Map transaction types between companies (e.g., Sales Order → Purchase Order)
- Automatic creation of corresponding transactions in linked companies
- Two-way transaction synchronization
- Linked cancellation across companies
- Support for multiple transaction types
- Draft creation mode

## Installation

1. Install the app using bench:
   ```
   bench get-app inter_company_transactions https://github.com/your-repo/inter_company_transactions
   bench --site your-site.local install-app inter_company_transactions
   ```

2. Run migrations:
   ```
   bench --site your-site.local migrate
   ```

## Usage

1. Set up the Inter-Company Mapping in the "Inter-Company Transaction Setup" DocType
2. Create transactions in your main company
3. Corresponding transactions will be automatically created in the linked companies

## License

MIT