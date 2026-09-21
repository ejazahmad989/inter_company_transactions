// Copyright (c) 2024-2026, Inter Company Transactions and Contributors
// Theme Manager & QuickBooks / ERP UI Theming Engine

frappe.provide('frappe.inter_company_theme');

// Preset Palettes for Accounting Software Themes
frappe.inter_company_theme.PRESETS = {
    'QuickBooks Classic': {
        primary_color: '#0077C5',
        secondary_color: '#2CA01C',
        accent_color: '#2CA01C',
        background_color: '#F5F5F5',
        surface_color: '#FFFFFF',
        sidebar_color: '#E8F4FD',
        navbar_color: '#0077C5',
        navbar_text_color: '#FFFFFF',
        text_color: '#333333',
        border_radius: '6px',
        css_class: 'quickbooks-classic-theme quickbooks-theme'
    },
    'QuickBooks Modern': {
        primary_color: '#2CA01C',
        secondary_color: '#0077C5',
        accent_color: '#F7931E',
        background_color: '#FAFBFC',
        surface_color: '#FFFFFF',
        sidebar_color: '#F4F5F7',
        navbar_color: '#FFFFFF',
        navbar_text_color: '#172B4D',
        text_color: '#172B4D',
        border_radius: '8px',
        css_class: 'quickbooks-modern-theme quickbooks-theme'
    },
    'QuickBooks Pro': {
        primary_color: '#2CA01C',
        secondary_color: '#108000',
        accent_color: '#0077C5',
        background_color: '#F0F3F6',
        surface_color: '#FFFFFF',
        sidebar_color: '#13253A',
        navbar_color: '#13253A',
        navbar_text_color: '#FFFFFF',
        text_color: '#172B4D',
        border_radius: '8px',
        css_class: 'quickbooks-pro-theme quickbooks-theme'
    },
    'Sage Green': {
        primary_color: '#00A651',
        secondary_color: '#7CB342',
        accent_color: '#FFC107',
        background_color: '#F8FFF8',
        surface_color: '#FFFFFF',
        sidebar_color: '#E8F5E8',
        navbar_color: '#00A651',
        navbar_text_color: '#FFFFFF',
        text_color: '#2E7D32',
        border_radius: '6px',
        css_class: 'sage-green-theme'
    },
    'Xero Blue': {
        primary_color: '#13B5EA',
        secondary_color: '#1976D2',
        accent_color: '#FF6B35',
        background_color: '#F0F9FF',
        surface_color: '#FFFFFF',
        sidebar_color: '#E3F2FD',
        navbar_color: '#13B5EA',
        navbar_text_color: '#FFFFFF',
        text_color: '#0D47A1',
        border_radius: '6px',
        css_class: 'xero-blue-theme'
    },
    'FreshBooks Orange': {
        primary_color: '#F56500',
        secondary_color: '#FF8A65',
        accent_color: '#4CAF50',
        background_color: '#FFF8F0',
        surface_color: '#FFFFFF',
        sidebar_color: '#FFF3E0',
        navbar_color: '#F56500',
        navbar_text_color: '#FFFFFF',
        text_color: '#E65100',
        border_radius: '6px',
        css_class: 'freshbooks-orange-theme'
    },
    'Zoho Purple': {
        primary_color: '#7B1FA2',
        secondary_color: '#9C27B0',
        accent_color: '#E91E63',
        background_color: '#F8F5FF',
        surface_color: '#FFFFFF',
        sidebar_color: '#F3E5F5',
        navbar_color: '#7B1FA2',
        navbar_text_color: '#FFFFFF',
        text_color: '#4A148C',
        border_radius: '6px',
        css_class: 'zoho-purple-theme'
    },
    'Wave Teal': {
        primary_color: '#00695C',
        secondary_color: '#26A69A',
        accent_color: '#FF7043',
        background_color: '#F0FDFC',
        surface_color: '#FFFFFF',
        sidebar_color: '#E0F2F1',
        navbar_color: '#00695C',
        navbar_text_color: '#FFFFFF',
        text_color: '#004D40',
        border_radius: '6px',
        css_class: 'wave-teal-theme'
    },
    'Fintech Dark': {
        primary_color: '#00D4AA',
        secondary_color: '#1DE9B6',
        accent_color: '#FF6B6B',
        background_color: '#0A0E27',
        surface_color: '#1A1D3A',
        sidebar_color: '#151937',
        navbar_color: '#1A1D3A',
        navbar_text_color: '#FFFFFF',
        text_color: '#FFFFFF',
        border_radius: '8px',
        css_class: 'fintech-dark-theme'
    },
    'Corporate Elite': {
        primary_color: '#1565C0',
        secondary_color: '#1976D2',
        accent_color: '#FFC107',
        background_color: '#F8FAFC',
        surface_color: '#FFFFFF',
        sidebar_color: '#ECEFF1',
        navbar_color: '#1565C0',
        navbar_text_color: '#FFFFFF',
        text_color: '#263238',
        border_radius: '6px',
        css_class: 'corporate-elite-theme'
    }
};

// Core DOM Applicator: applies variables, classes, and styles directly to document
frappe.inter_company_theme.apply_theme = function(theme) {
    if (!theme || !theme.theme_name) return;

    let primary = theme.primary_color || '#2CA01C';
    let secondary = theme.secondary_color || '#0077C5';
    let navbar = theme.navbar_color || primary;
    let navbar_text = theme.navbar_text_color || '#FFFFFF';
    let sidebar = theme.sidebar_color || '#F4F5F7';
    let css_class = theme.css_class || 'quickbooks-theme';

    // 1. Set CSS root variables
    document.documentElement.style.setProperty('--primary', primary);
    document.documentElement.style.setProperty('--primary-color', primary);
    document.documentElement.style.setProperty('--btn-primary-bg', primary);
    document.documentElement.style.setProperty('--btn-primary-border', primary);
    document.documentElement.style.setProperty('--navbar-bg', navbar);
    document.documentElement.style.setProperty('--navbar-text-color', navbar_text);

    // 2. Remove any prior theme classes and add new class
    const known_classes = [
        'quickbooks-theme', 'quickbooks-classic-theme', 'quickbooks-modern-theme', 'quickbooks-pro-theme',
        'sage-green-theme', 'xero-blue-theme', 'freshbooks-orange-theme', 'zoho-purple-theme',
        'wave-teal-theme', 'fintech-dark-theme', 'corporate-elite-theme'
    ];
    $('body').removeClass(known_classes.join(' '));
    if (css_class) {
        $('body').addClass(css_class);
    }

    // 3. Inject / Update theme CSS stylesheet in <head>
    let css_content = theme.generated_css;
    if (!css_content) {
        css_content = `
            :root, [data-theme="light"], [data-theme="dark"], body {
                --primary: ${primary} !important;
                --primary-color: ${primary} !important;
                --btn-primary-bg: ${primary} !important;
                --btn-primary-border: ${primary} !important;
                --navbar-bg: ${navbar} !important;
                --navbar-text-color: ${navbar_text} !important;
            }
            header.navbar, .navbar.navbar-expand {
                background: ${navbar} !important;
                border-bottom: 2px solid ${secondary} !important;
            }
            .btn-primary {
                background-color: ${primary} !important;
                border-color: ${primary} !important;
            }
            .desk-sidebar .sidebar-item-container.active {
                border-left: 3px solid ${primary} !important;
            }
        `;
    }

    $('#ict-active-theme-styles').remove();
    $('<style id="ict-active-theme-styles">').text(css_content).appendTo('head');

    // 4. Update memory / storage
    if (frappe.boot) {
        frappe.boot.active_theme = theme;
    }
};

// Form Controller for Enhanced Theme Manager
const theme_form_handlers = {
    refresh: function(frm) {
        // Apply Theme Now button
        frm.add_custom_button(__('Apply Theme Now'), function() {
            apply_theme_from_form(frm);
        }).addClass('btn-primary');

        // Preview Theme button
        frm.add_custom_button(__('Preview Theme'), function() {
            preview_theme_dialog(frm);
        });

        // Reset to Default button
        frm.add_custom_button(__('Reset to Standard ERPNext'), function() {
            reset_theme_dialog(frm);
        }, __('Actions'));

        render_theme_swatch(frm);
    },

    theme_name: function(frm) {
        let preset = frappe.inter_company_theme.PRESETS[frm.doc.theme_name];
        if (preset) {
            Object.keys(preset).forEach(field => {
                if (frm.fields_dict[field]) {
                    frm.set_value(field, preset[field]);
                }
            });
            frappe.show_alert({
                message: __(`Loaded presets for ${frm.doc.theme_name}`),
                indicator: 'green'
            });
        }
        render_theme_swatch(frm);
    },

    primary_color: function(frm) { render_theme_swatch(frm); },
    secondary_color: function(frm) { render_theme_swatch(frm); },
    navbar_color: function(frm) { render_theme_swatch(frm); },
    sidebar_color: function(frm) { render_theme_swatch(frm); }
};

frappe.ui.form.on('Enhanced Theme Manager', theme_form_handlers);
frappe.ui.form.on('Theme Manager', theme_form_handlers); // alias support

function apply_theme_from_form(frm) {
    if (frm.is_dirty()) {
        frappe.msgprint(__('Please save the document first before applying.'));
        return;
    }

    let company = null;
    if (frm.doc.company_specific && frm.doc.target_companies && frm.doc.target_companies.length > 0) {
        company = frm.doc.target_companies[0].company;
    }

    frappe.call({
        method: 'inter_company_transactions.enhanced_theme.apply_theme_to_user',
        args: {
            theme_name: frm.doc.name,
            company: company
        },
        freeze: true,
        freeze_message: __('Applying theme across ERPNext...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                });
                if (r.message.theme) {
                    frappe.inter_company_theme.apply_theme(r.message.theme);
                }
            } else {
                frappe.msgprint(r.message ? r.message.message : __('Failed to apply theme'));
            }
        }
    });
}

function reset_theme_dialog(frm) {
    frappe.confirm(
        __('Are you sure you want to disable custom themes and reset to standard ERPNext styling?'),
        function() {
            $('#ict-active-theme-styles').remove();
            $('body').removeClass([
                'quickbooks-theme', 'quickbooks-classic-theme', 'quickbooks-modern-theme', 'quickbooks-pro-theme',
                'sage-green-theme', 'xero-blue-theme', 'freshbooks-orange-theme', 'zoho-purple-theme',
                'wave-teal-theme', 'fintech-dark-theme', 'corporate-elite-theme'
            ].join(' '));
            document.documentElement.style.removeProperty('--primary');
            document.documentElement.style.removeProperty('--primary-color');
            document.documentElement.style.removeProperty('--navbar-bg');

            if (frm.doc.is_active) {
                frm.set_value('is_active', 0);
                frm.save();
            }

            frappe.show_alert({
                message: __('Reset to standard theme.'),
                indicator: 'blue'
            });
        }
    );
}

function render_theme_swatch(frm) {
    let p = frm.doc.primary_color || '#2CA01C';
    let s = frm.doc.secondary_color || '#0077C5';
    let nav = frm.doc.navbar_color || p;

    let html = `
        <div style="margin: 10px 0; padding: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;">
            <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px;">Current Palette Preview:</div>
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div style="width: 24px; height: 24px; border-radius: 4px; background: ${p}; border: 1px solid #ccc;"></div>
                    <span style="font-size: 12px;">Primary: <code>${p}</code></span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div style="width: 24px; height: 24px; border-radius: 4px; background: ${s}; border: 1px solid #ccc;"></div>
                    <span style="font-size: 12px;">Secondary: <code>${s}</code></span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div style="width: 24px; height: 24px; border-radius: 4px; background: ${nav}; border: 1px solid #ccc;"></div>
                    <span style="font-size: 12px;">Navbar: <code>${nav}</code></span>
                </div>
            </div>
        </div>
    `;

    if (frm.fields_dict.theme_preview && frm.fields_dict.theme_preview.$wrapper) {
        frm.fields_dict.theme_preview.$wrapper.html(html);
    }
}

function preview_theme_dialog(frm) {
    let p = frm.doc.primary_color || '#2CA01C';
    let s = frm.doc.secondary_color || '#0077C5';
    let nav = frm.doc.navbar_color || p;
    let nav_text = frm.doc.navbar_text_color || '#FFFFFF';
    let bg = frm.doc.background_color || '#FAFBFC';
    let font = frm.doc.font_family || 'Inter, sans-serif';

    let dialog = new frappe.ui.Dialog({
        title: __('Theme Preview: {0}', [frm.doc.theme_name || 'Custom']),
        size: 'large',
        fields: [{ fieldtype: 'HTML', fieldname: 'preview_html' }]
    });

    let preview_html = `
        <div style="font-family: ${font}; background: ${bg}; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <!-- Fake Navbar -->
            <div style="background: ${nav}; color: ${nav_text}; padding: 12px 18px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid ${s};">
                <div style="font-weight: 700; font-size: 15px;">ERPNext &bull; ${frm.doc.theme_name || 'QuickBooks Style'}</div>
                <div style="font-size: 12px; opacity: 0.9;">Company: Demo Corp | User: Administrator</div>
            </div>

            <!-- Fake Workspace / Cards -->
            <div style="display: grid; grid-template-columns: 200px 1fr; gap: 14px; margin-top: 14px;">
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;">
                    <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px; color: #64748b;">NAVIGATION</div>
                    <div style="padding: 6px 10px; background: rgba(44, 160, 28, 0.1); color: ${p}; border-left: 3px solid ${p}; font-weight: 600; border-radius: 3px; font-size: 13px;">Accounting Console</div>
                    <div style="padding: 6px 10px; color: #475569; font-size: 13px; margin-top: 4px;">Sales Invoices</div>
                    <div style="padding: 6px 10px; color: #475569; font-size: 13px; margin-top: 4px;">Purchase Orders</div>
                    <div style="padding: 6px 10px; color: #475569; font-size: 13px; margin-top: 4px;">Inter-Company Links</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px;">
                    <h5 style="margin: 0 0 12px 0; color: #1e293b;">Inter-Company Operations Dashboard</h5>
                    <p style="font-size: 13px; color: #64748b; margin-bottom: 14px;">Real-time automated transaction synchronization and elimination across entities.</p>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-sm" style="background: ${p}; color: #fff; border: none; font-weight: 600; padding: 6px 14px; border-radius: 4px;">Primary Action</button>
                        <button class="btn btn-sm btn-default" style="border: 1px solid #cbd5e1; padding: 6px 14px; border-radius: 4px;">Secondary</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    dialog.fields_dict.preview_html.$wrapper.html(preview_html);
    dialog.show();
}

// Global Startup: Auto-apply theme when Desk loads
$(document).ready(function() {
    if (!frappe.session || frappe.session.user === 'Guest') return;

    // 1. If active_theme was injected in bootinfo, apply immediately without server trip
    if (frappe.boot && frappe.boot.active_theme && frappe.boot.active_theme.theme_name) {
        frappe.inter_company_theme.apply_theme(frappe.boot.active_theme);
    } else {
        // 2. Otherwise query backend for the company theme
        frappe.call({
            method: 'inter_company_transactions.enhanced_theme.get_company_theme',
            callback: function(r) {
                if (r.message && r.message.theme_name) {
                    frappe.inter_company_theme.apply_theme(r.message);
                }
            }
        });
    }
});
