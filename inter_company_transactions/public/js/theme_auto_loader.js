// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// Theme Auto Loader for Company Theme
(function() {
    frappe.provide('frappe.theme_auto_loader');

    frappe.theme_auto_loader.apply_theme = function() {
        if (!frappe.boot || !frappe.boot.company_theme) return;
        var theme = frappe.boot.company_theme;
        if (!theme || !theme.colors) return;

        var styleId = 'company-theme-auto-style';
        var styleEl = document.getElementById(styleId);
        if (!styleEl) {
            styleEl = document.createElement('style');
            styleEl.id = styleId;
            document.head.appendChild(styleEl);
        }

        var colors = theme.colors;
        var css = ':root {\n';
        if (colors.primary) css += '  --primary-color: ' + colors.primary + ';\n';
        if (colors.secondary) css += '  --secondary-color: ' + colors.secondary + ';\n';
        if (colors.accent) css += '  --accent-color: ' + colors.accent + ';\n';
        if (colors.text) css += '  --text-color: ' + colors.text + ';\n';
        if (theme.font && theme.font !== 'inherit') css += '  --font-family: ' + theme.font + ';\n';
        css += '}\n';

        styleEl.innerHTML = css;
    };

    $(document).on('app_ready', function() {
        frappe.theme_auto_loader.apply_theme();
    });
})();
