import frappe

@frappe.whitelist()
def get_company_theme():
    # return dummy or real theme info
    return {
        "theme_file_path": "/assets/inter_company_transactions/css/theme.css"
    }
