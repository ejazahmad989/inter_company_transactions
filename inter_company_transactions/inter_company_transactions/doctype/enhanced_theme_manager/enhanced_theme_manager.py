import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
import requests


class EnhancedThemeManager(Document):
    def validate(self):
        self.create_or_update_website_theme()
        self.setup_login_assets()
        self.inject_custom_login_script()

    def create_or_update_website_theme(self):
        theme_name = self.name
        css = self.custom_css or ''
        web_theme = frappe.get_doc({
            'doctype': 'Website Theme',
            'theme': theme_name,
            'custom_scss': css,
            'theme_scss': ''
        })

        if frappe.db.exists('Website Theme', theme_name):
            web_theme = frappe.get_doc('Website Theme', theme_name)
            web_theme.custom_scss = css
            web_theme.save()
        else:
            web_theme.insert()

        frappe.db.set_single_value('Website Settings', 'website_theme', theme_name)



    def setup_login_assets(self):
        for company in self.company_settings:
            self._save_web_file(
                file_url=company.login_background_url,
                file_name=f"{company.company}_login_background",
                folder='Home Backgrounds'
            )
            self._save_web_file(
                file_url=company.login_logo_url,
                file_name=f"{company.company}_login_logo",
                folder='Login Logos'
            )

    def _save_web_file(self, file_url, file_name, folder):
        if not file_url:
            return

        file_content = self.download_file(file_url)
        if not file_content:
            return

        existing = frappe.db.exists('File', {'file_name': file_name})
        if existing:
            f = frappe.get_doc('File', existing)
            f.content = file_content
            f.save()
        else:
            save_file(
                fname=file_name,
                content=file_content,
                dt=None,
                dn=None,
                folder=folder,
                decode=True,
                is_private=0
            )

    def download_file(self, url):
        try:
            res = requests.get(url)
            if res.status_code == 200:
                return res.content
        except Exception as e:
            frappe.log_error(f"Failed to download file from {url}: {e}")
        return None

    def inject_custom_login_script(self):
        js_path = 'public/js/custom_login.js'
        full_path = frappe.get_app_path('enhanced_theme_manager', js_path)

        js_code = self._generate_login_js()

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(js_code)

    def _generate_login_js(self):
        lines = []

        for company in self.company_settings:
            if company.company:
                lines.append(f"""
if (window.erpnext && window.erpnext.company === "{company.company}") {{
    document.body.style.backgroundImage = "url('{company.login_background_url}')";
    document.querySelector(".login-logo img").src = "{company.login_logo_url}";
}}""")

        return f"""
frappe.ready(function() {{
    {''.join(lines)}
}});
"""

