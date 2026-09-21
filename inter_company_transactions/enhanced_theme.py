# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
import os
import json

THEME_PRESETS = {
    "QuickBooks Classic": {
        "primary_color": "#0077C5",
        "secondary_color": "#2CA01C",
        "accent_color": "#2CA01C",
        "background_color": "#F5F5F5",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#E8F4FD",
        "navbar_color": "#0077C5",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#333333",
        "border_radius": "6px",
        "css_class": "quickbooks-classic-theme quickbooks-theme"
    },
    "QuickBooks Modern": {
        "primary_color": "#2CA01C",
        "secondary_color": "#0077C5",
        "accent_color": "#F7931E",
        "background_color": "#FAFBFC",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#F4F5F7",
        "navbar_color": "#FFFFFF",
        "navbar_text_color": "#172B4D",
        "text_color": "#172B4D",
        "border_radius": "8px",
        "css_class": "quickbooks-modern-theme quickbooks-theme"
    },
    "QuickBooks Pro": {
        "primary_color": "#2CA01C",
        "secondary_color": "#108000",
        "accent_color": "#0077C5",
        "background_color": "#F0F3F6",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#13253A",
        "navbar_color": "#13253A",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#172B4D",
        "border_radius": "8px",
        "css_class": "quickbooks-pro-theme quickbooks-theme"
    },
    "Sage Green": {
        "primary_color": "#00A651",
        "secondary_color": "#7CB342",
        "accent_color": "#FFC107",
        "background_color": "#F8FFF8",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#E8F5E8",
        "navbar_color": "#00A651",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#2E7D32",
        "border_radius": "6px",
        "css_class": "sage-green-theme"
    },
    "Xero Blue": {
        "primary_color": "#13B5EA",
        "secondary_color": "#1976D2",
        "accent_color": "#FF6B35",
        "background_color": "#F0F9FF",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#E3F2FD",
        "navbar_color": "#13B5EA",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#0D47A1",
        "border_radius": "6px",
        "css_class": "xero-blue-theme"
    },
    "FreshBooks Orange": {
        "primary_color": "#F56500",
        "secondary_color": "#FF8A65",
        "accent_color": "#4CAF50",
        "background_color": "#FFF8F0",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#FFF3E0",
        "navbar_color": "#F56500",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#E65100",
        "border_radius": "6px",
        "css_class": "freshbooks-orange-theme"
    },
    "Zoho Purple": {
        "primary_color": "#7B1FA2",
        "secondary_color": "#9C27B0",
        "accent_color": "#E91E63",
        "background_color": "#F8F5FF",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#F3E5F5",
        "navbar_color": "#7B1FA2",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#4A148C",
        "border_radius": "6px",
        "css_class": "zoho-purple-theme"
    },
    "Wave Teal": {
        "primary_color": "#00695C",
        "secondary_color": "#26A69A",
        "accent_color": "#FF7043",
        "background_color": "#F0FDFC",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#E0F2F1",
        "navbar_color": "#00695C",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#004D40",
        "border_radius": "6px",
        "css_class": "wave-teal-theme"
    },
    "Fintech Dark": {
        "primary_color": "#00D4AA",
        "secondary_color": "#1DE9B6",
        "accent_color": "#FF6B6B",
        "background_color": "#0A0E27",
        "surface_color": "#1A1D3A",
        "sidebar_color": "#151937",
        "navbar_color": "#1A1D3A",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "border_radius": "8px",
        "css_class": "fintech-dark-theme"
    },
    "Corporate Elite": {
        "primary_color": "#1565C0",
        "secondary_color": "#1976D2",
        "accent_color": "#FFC107",
        "background_color": "#F8FAFC",
        "surface_color": "#FFFFFF",
        "sidebar_color": "#ECEFF1",
        "navbar_color": "#1565C0",
        "navbar_text_color": "#FFFFFF",
        "text_color": "#263238",
        "border_radius": "6px",
        "css_class": "corporate-elite-theme"
    }
}


def hex_to_rgb(hex_color):
    """Convert hex color to comma-separated RGB string"""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r}, {g}, {b}"
    except Exception:
        return "44, 160, 28"


def get_theme_palette(theme_name):
    """Returns preset palette for theme_name if available"""
    if not theme_name:
        return THEME_PRESETS["QuickBooks Modern"]
    
    # Try exact match
    if theme_name in THEME_PRESETS:
        return THEME_PRESETS[theme_name]
    
    # Try fuzzy match for QuickBooks
    tn_lower = theme_name.lower()
    if "quickbooks" in tn_lower:
        if "classic" in tn_lower:
            return THEME_PRESETS["QuickBooks Classic"]
        elif "pro" in tn_lower:
            return THEME_PRESETS["QuickBooks Pro"]
        else:
            return THEME_PRESETS["QuickBooks Modern"]
            
    for key, val in THEME_PRESETS.items():
        if key.lower() in tn_lower or tn_lower in key.lower():
            return val
            
    return THEME_PRESETS["QuickBooks Modern"]


def generate_theme_css(primary, secondary, accent, bg, surface, sidebar, navbar, navbar_text, text, font, border_radius, custom_css="", theme_name=""):
    """Generate dynamic CSS to style Frappe v15 Desk elements"""
    primary_rgb = hex_to_rgb(primary)
    is_qb = "quickbooks" in (theme_name or "").lower()
    
    css = f"""
/* Generated by Inter-Company Enhanced Theme Manager for {theme_name} */
:root, [data-theme="light"], [data-theme="dark"], body {{
    --primary: {primary} !important;
    --primary-color: {primary} !important;
    --btn-primary-bg: {primary} !important;
    --btn-primary-border: {primary} !important;
    --navbar-bg: {navbar} !important;
    --navbar-text-color: {navbar_text} !important;
    --sidebar-select-color: rgba({primary_rgb}, 0.12) !important;
    --border-radius: {border_radius} !important;
}}

/* Navbar & Brand */
header.navbar, .navbar.navbar-expand {{
    background: {navbar} !important;
    border-bottom: 2px solid {secondary or primary} !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.06) !important;
}}

/* Navbar text & icons */
.navbar .navbar-nav .nav-link,
.navbar-brand,
.navbar .form-control {{
    color: {navbar_text} !important;
}}

.navbar .navbar-nav .nav-link svg,
.navbar .navbar-nav .nav-link i {{
    fill: {navbar_text} !important;
    color: {navbar_text} !important;
}}

/* Desk Sidebar */
.desk-sidebar {{
    background: {sidebar} !important;
}}

.desk-sidebar .sidebar-item-container.active,
.desk-sidebar .standard-sidebar-item.active {{
    background: rgba({primary_rgb}, 0.12) !important;
    color: {primary} !important;
    border-left: 3px solid {primary} !important;
    font-weight: 600 !important;
}}

.desk-sidebar .sidebar-item-container:hover,
.desk-sidebar .standard-sidebar-item:hover {{
    background: rgba({primary_rgb}, 0.06) !important;
}}

/* Primary Buttons */
.btn-primary {{
    background-color: {primary} !important;
    border-color: {primary} !important;
    color: #ffffff !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08) !important;
    transition: all 0.2s ease !important;
}}

.btn-primary:hover, .btn-primary:focus {{
    filter: brightness(0.92) !important;
    box-shadow: 0 2px 6px rgba({primary_rgb}, 0.35) !important;
}}

/* Active Tab Underlines and Links */
.nav-tabs .nav-link.active,
.form-tabs .nav-link.active {{
    border-bottom: 3px solid {primary} !important;
    color: {primary} !important;
    font-weight: 600 !important;
}}

a:not(.btn):not(.nav-link):not(.dropdown-item) {{
    color: {primary};
}}

a:not(.btn):not(.nav-link):not(.dropdown-item):hover {{
    color: {secondary or primary};
}}

/* Form Controls Focus */
.form-control:focus {{
    border-color: {primary} !important;
    box-shadow: 0 0 0 2px rgba({primary_rgb}, 0.2) !important;
}}

/* Indicator Pills & Checkboxes */
.indicator-pill.green, .indicator-pill.primary {{
    background-color: rgba({primary_rgb}, 0.15) !important;
    color: {primary} !important;
}}

input[type="checkbox"]:checked {{
    background-color: {primary} !important;
    border-color: {primary} !important;
}}
"""

    if is_qb:
        css += f"""
/* QuickBooks Specific Brand Accents */
header.navbar {{
    border-bottom: 3px solid #2CA01C !important;
}}

.page-head {{
    border-bottom: 1px solid #E5E7EB !important;
}}

.btn-primary {{
    border-radius: 6px !important;
    font-weight: 600 !important;
}}

.desk-sidebar .sidebar-item-container.active {{
    border-left: 3px solid #2CA01C !important;
}}
"""

    if custom_css:
        css += f"\n/* Custom User Styles */\n{custom_css}\n"

    return css


def format_theme_data(doc):
    """Formats an Enhanced Theme Manager doc into a structured client theme package"""
    theme_name = doc.theme_name or "QuickBooks Classic"
    palette = get_theme_palette(theme_name)
    
    primary = doc.primary_color or palette.get("primary_color", "#2CA01C")
    secondary = doc.secondary_color or palette.get("secondary_color", "#0077C5")
    accent = doc.accent_color or palette.get("accent_color", "#2CA01C")
    bg = doc.background_color or palette.get("background_color", "#F5F5F5")
    surface = doc.surface_color or palette.get("surface_color", "#FFFFFF")
    sidebar = doc.sidebar_color or palette.get("sidebar_color", "#F4F5F7")
    navbar = doc.navbar_color or palette.get("navbar_color", primary)
    navbar_text = doc.navbar_text_color or palette.get("navbar_text_color", "#FFFFFF")
    text = doc.text_color or palette.get("text_color", "#172B4D")
    font = doc.font_family or "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    border_radius = doc.border_radius or palette.get("border_radius", "6px")
    css_class = palette.get("css_class", "quickbooks-theme")

    generated_css = generate_theme_css(
        primary=primary,
        secondary=secondary,
        accent=accent,
        bg=bg,
        surface=surface,
        sidebar=sidebar,
        navbar=navbar,
        navbar_text=navbar_text,
        text=text,
        font=font,
        border_radius=border_radius,
        custom_css=doc.custom_css or "",
        theme_name=theme_name
    )

    # Collect linked target companies
    target_comps = []
    if hasattr(doc, "target_companies") and doc.target_companies:
        target_comps = [tc.company for tc in doc.target_companies if getattr(tc, "company", None)]

    return {
        "name": doc.name,
        "theme_name": theme_name,
        "theme_category": getattr(doc, "theme_category", "Accounting Software"),
        "is_active": doc.is_active,
        "company_specific": getattr(doc, "company_specific", 0),
        "target_companies": target_comps,
        "primary_color": primary,
        "secondary_color": secondary,
        "accent_color": accent,
        "background_color": bg,
        "surface_color": surface,
        "sidebar_color": sidebar,
        "navbar_color": navbar,
        "navbar_text_color": navbar_text,
        "text_color": text,
        "font_family": font,
        "border_radius": border_radius,
        "css_class": css_class,
        "generated_css": generated_css,
        "custom_css": doc.custom_css or "",
        "custom_js": doc.custom_js or ""
    }


@frappe.whitelist()
def get_company_theme(company=None, user=None):
    """
    Get active theme for user or company with priority:
    1. Active theme targeting specified company in target_companies
    2. Active theme targeting user default company
    3. Active theme marked apply_to_all_users = 1
    4. Active theme marked is_default = 1
    5. Any active theme
    """
    try:
        if not frappe.db.table_exists("Enhanced Theme Manager"):
            return {}

        if not company and hasattr(frappe, "session") and frappe.session.user != "Guest":
            company = (
                frappe.defaults.get_user_default("Company")
                or frappe.defaults.get_user_default("company")
                or frappe.db.get_single_value("Global Defaults", "default_company")
            )

        doc = None

        # 1. Company-specific match
        if company and frappe.db.table_exists("Theme Manager Company"):
            match = frappe.db.sql("""
                SELECT tm.name
                FROM `tabEnhanced Theme Manager` tm
                INNER JOIN `tabTheme Manager Company` tmc ON tmc.parent = tm.name
                WHERE tm.is_active = 1
                  AND tmc.company = %s
                ORDER BY tm.modified DESC
                LIMIT 1
            """, (company,))
            if match and match[0][0]:
                doc = frappe.get_doc("Enhanced Theme Manager", match[0][0])

        # 2. Global apply_to_all_users active theme
        if not doc:
            match = frappe.get_all(
                "Enhanced Theme Manager",
                filters={"is_active": 1, "apply_to_all_users": 1},
                order_by="modified desc",
                limit=1
            )
            if match:
                doc = frappe.get_doc("Enhanced Theme Manager", match[0].name)

        # 3. Default active theme
        if not doc:
            match = frappe.get_all(
                "Enhanced Theme Manager",
                filters={"is_active": 1, "is_default": 1},
                order_by="modified desc",
                limit=1
            )
            if match:
                doc = frappe.get_doc("Enhanced Theme Manager", match[0].name)

        # 4. Any active theme
        if not doc:
            match = frappe.get_all(
                "Enhanced Theme Manager",
                filters={"is_active": 1},
                order_by="modified desc",
                limit=1
            )
            if match:
                doc = frappe.get_doc("Enhanced Theme Manager", match[0].name)

        if doc:
            return format_theme_data(doc)

        return {}
    except Exception as e:
        frappe.log_error(f"Error in get_company_theme: {str(e)}", "Enhanced Theme Manager")
        return {}


@frappe.whitelist()
def apply_theme_to_user(theme_name=None, company=None):
    """
    Applies and activates a theme immediately.
    Can be called from the Desk form button or API.
    """
    try:
        if not theme_name:
            frappe.throw(_("Theme Name or Doc Name is required"))

        doc = None
        if frappe.db.exists("Enhanced Theme Manager", theme_name):
            doc = frappe.get_doc("Enhanced Theme Manager", theme_name)
        else:
            # Try finding by theme_name field
            matches = frappe.get_all("Enhanced Theme Manager", filters={"theme_name": theme_name}, limit=1)
            if matches:
                doc = frappe.get_doc("Enhanced Theme Manager", matches[0].name)

        if not doc:
            frappe.throw(_("Theme not found: {0}").format(theme_name))

        doc.is_active = 1
        if company:
            # Ensure company is in target_companies
            existing_companies = [tc.company for tc in (doc.target_companies or [])]
            if company not in existing_companies:
                doc.append("target_companies", {"company": company})
                doc.company_specific = 1

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        theme_data = format_theme_data(doc)
        return {
            "success": True,
            "message": _("Theme '{0}' applied successfully.").format(doc.theme_name),
            "theme": theme_data
        }
    except Exception as e:
        frappe.log_error(f"Error in apply_theme_to_user: {str(e)}", "Enhanced Theme Manager")
        return {
            "success": False,
            "message": str(e)
        }


def apply_user_theme(login_manager=None):
    """Apply theme on user login"""
    try:
        if not hasattr(frappe, "session") or frappe.session.user == "Guest":
            return
        
        theme = get_company_theme()
        if theme and hasattr(frappe, "local") and hasattr(frappe.local, "response"):
            frappe.local.response["theme"] = theme
    except Exception as e:
        frappe.log_error(f"Error applying user theme on login: {str(e)}", "Theme Manager")


@frappe.whitelist()
def get_active_theme():
    """Returns active theme data for current context"""
    return get_company_theme()


def cleanup_old_theme_files():
    """Clean up old theme files"""
    pass
