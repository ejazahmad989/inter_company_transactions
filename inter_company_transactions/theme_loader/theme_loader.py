import frappe
import json
from frappe.utils import cint

def get_company_css():
    """Inject company-specific CSS"""
    if frappe.session.user == "Guest":
        return
        
    company = frappe.get_value("User", frappe.session.user, "company")
    if not company:
        return
        
    theme_data = frappe.cache().hget("company_themes", company)
    if not theme_data:
        return
        
    theme = json.loads(theme_data)
    
    if theme.get("theme_category") == "Custom Themes":
        return theme.get("custom_css", "")
        
    colors = theme.get("colors", {})
    font = theme.get("font", "inherit")
    
    return f"""
    :root {{
        --primary-color: {colors.get('primary', '#5e64ff')};
        --secondary-color: {colors.get('secondary', '#f5f7fa')};
        --text-color: {colors.get('text', '#36414c')};
        --accent-color: {colors.get('accent', '#e0e6ed')};
        --font-family: {font};
    }}
    
    .navbar, .footer {{
        background-color: var(--primary-color) !important;
    }}
    
    body {{
        font-family: var(--font-family);
        color: var(--text-color);
        background-color: var(--secondary-color);
    }}
    
    .btn-primary {{
        background-color: var(--primary-color);
        border-color: var(--primary-color);
    }}
    
    .card {{
        background-color: var(--accent-color);
    }}
    """

def get_website_theme():
    """Get website theme for login page if configured"""
    if frappe.session.user != "Guest":
        return
        
    company = frappe.form_dict.company or frappe.defaults.get_defaults().company
    if not company:
        return
        
    theme_data = frappe.cache().hget("company_themes", company)
    if not theme_data:
        return
        
    theme = json.loads(theme_data)
    if not cint(theme.get("apply_to_login")):
        return
        
    return {
        "primary_color": theme.get("colors", {}).get("primary", "#5e64ff"),
        "font_family": theme.get("font", "inherit")
    }

def get_active_theme_for_company(company):
    """Retrieve active theme for a given company"""
    if not company:
        return None
    try:
        theme_data = frappe.cache().hget("company_themes", company)
        if theme_data:
            return json.loads(theme_data)
            
        if frappe.db.exists("DocType", "Company Theme"):
            theme_name = frappe.db.get_value("Company Theme", {"company": company, "enabled": 1}, "name")
            if theme_name:
                doc = frappe.get_doc("Company Theme", theme_name)
                return {
                    "name": doc.name,
                    "colors": {
                        "primary": getattr(doc, "primary_color", "#5e64ff"),
                        "secondary": getattr(doc, "secondary_color", "#f5f7fa"),
                        "accent": getattr(doc, "accent_color", "#e0e6ed"),
                        "text": getattr(doc, "text_color", "#36414c"),
                    },
                    "font": getattr(doc, "font_family", "inherit")
                }
    except Exception:
        pass
    return None
