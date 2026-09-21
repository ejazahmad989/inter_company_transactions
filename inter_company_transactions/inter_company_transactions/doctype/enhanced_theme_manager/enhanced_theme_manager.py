# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from inter_company_transactions.enhanced_theme import get_theme_palette, format_theme_data, apply_theme_to_user


class EnhancedThemeManager(Document):
    VALID_BORDER_RADII = [
        "0px (Sharp)",
        "4px (Slightly Rounded)",
        "8px (Rounded)",
        "12px (Very Rounded)",
        "16px (Highly Rounded)",
        "20px (Extra Rounded)",
    ]

    def validate(self):
        self.populate_default_colors()
        self.normalize_border_radius()
        self.ensure_single_default()

    def normalize_border_radius(self):
        """Map raw values like '8px' or '6px' to valid DocType Select options"""
        if not self.border_radius:
            self.border_radius = "8px (Rounded)"
            return

        if self.border_radius in self.VALID_BORDER_RADII:
            return

        radius_map = {
            "0": "0px (Sharp)",
            "0px": "0px (Sharp)",
            "4": "4px (Slightly Rounded)",
            "4px": "4px (Slightly Rounded)",
            "6": "8px (Rounded)",
            "6px": "8px (Rounded)",
            "8": "8px (Rounded)",
            "8px": "8px (Rounded)",
            "12": "12px (Very Rounded)",
            "12px": "12px (Very Rounded)",
            "16": "16px (Highly Rounded)",
            "16px": "16px (Highly Rounded)",
            "20": "20px (Extra Rounded)",
            "20px": "20px (Extra Rounded)",
        }

        val = str(self.border_radius).strip().lower()
        if val in radius_map:
            self.border_radius = radius_map[val]
            return

        for k, v in radius_map.items():
            if k in val:
                self.border_radius = v
                return

        self.border_radius = "8px (Rounded)"

    def populate_default_colors(self):
        """Auto-populate standard colors if blank based on selected theme_name"""
        if self.theme_name:
            palette = get_theme_palette(self.theme_name)
            if not self.primary_color and palette.get("primary_color"):
                self.primary_color = palette.get("primary_color")
            if not self.secondary_color and palette.get("secondary_color"):
                self.secondary_color = palette.get("secondary_color")
            if not self.accent_color and palette.get("accent_color"):
                self.accent_color = palette.get("accent_color")
            if not self.background_color and palette.get("background_color"):
                self.background_color = palette.get("background_color")
            if not self.surface_color and palette.get("surface_color"):
                self.surface_color = palette.get("surface_color")
            if not self.sidebar_color and palette.get("sidebar_color"):
                self.sidebar_color = palette.get("sidebar_color")
            if not self.navbar_color and palette.get("navbar_color"):
                self.navbar_color = palette.get("navbar_color")
            if not self.navbar_text_color and palette.get("navbar_text_color"):
                self.navbar_text_color = palette.get("navbar_text_color")
            if not self.text_color and palette.get("text_color"):
                self.text_color = palette.get("text_color")
            if not self.border_radius and palette.get("border_radius"):
                self.border_radius = palette.get("border_radius")

    def ensure_single_default(self):
        """Ensure only one theme has is_default = 1"""
        if self.is_default:
            frappe.db.sql(
                "UPDATE `tabEnhanced Theme Manager` SET is_default = 0 WHERE name != %s",
                (self.name or ""),
            )

    def on_update(self):
        """Clear cache so theme changes take effect immediately"""
        try:
            frappe.cache().delete_keys("company_themes")
        except Exception:
            pass

    @frappe.whitelist()
    def apply_theme_now(self, company=None):
        """Applies this theme immediately"""
        return apply_theme_to_user(self.name, company)
