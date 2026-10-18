# Production Release Status & Push Instructions

The clean release repository has been prepared inside the project:
* **Commit:** `feat: initial production release v1.0.0 for ERPNext v14, v15 & v16`
* **Author:** `Ejaz Ahmed <ejazahmad989@gmail.com>`
* **Co-author:** `Rahil Ali <rahilali3311@gmail.com>`
* **Release Tag:** `v1.0.0`
* **Target Repository:** `https://github.com/ejazahmad989/inter_company_transactions.git`

---

## Final Push Instructions (2 Minutes)

### Step 1: Generate a GitHub Personal Access Token (PAT)
1. On GitHub (logged into `ejazahmad989`), go to:
   **[https://github.com/settings/tokens](https://github.com/settings/tokens)**
2. Click **Generate new token** > **Generate new token (classic)**.
3. Note: `Marketplace Push`
4. Expiration: 30 days or No expiration
5. Select scopes: Check **`repo`** (Full control of repositories).
6. Click **Generate token** and copy the string (it starts with `ghp_...`).

### Step 2: Push to GitHub
In your terminal, run:
```bash
git push -u origin main --tags
```
When prompted:
* **Username:** `ejazahmad989`
* **Password:** *(Paste your copied token `ghp_...`)*

---

## Frappe Cloud Marketplace Listing Details
Once pushed, submit your listing at **[https://frappecloud.com/marketplace](https://frappecloud.com/marketplace)**:

| Field | Value |
| :--- | :--- |
| **Publisher Name** | `Ejaz Ahmed` |
| **Publisher Email** | `ejazahmad989@gmail.com` |
| **App Name** | `inter_company_transactions` |
| **App Title** | `Inter Company Transactions` |
| **Repository URL** | `https://github.com/ejazahmad989/inter_company_transactions` |
| **Release Tag** | `v1.0.0` |
| **Monthly Pricing** | `$49 / month` |
| **Yearly Pricing** | `$490 / year` (2 months free) |
| **Supported Versions** | Frappe & ERPNext v14, v15, and v16 |
