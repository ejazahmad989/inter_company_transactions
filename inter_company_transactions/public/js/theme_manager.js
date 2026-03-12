// Theme Manager JavaScript

frappe.ui.form.on('Theme Manager', {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__('Preview Theme'), function() {
            preview_theme(frm);
        });
        
        frm.add_custom_button(__('Apply Theme'), function() {
            apply_theme(frm);
        });
        
        frm.add_custom_button(__('Reset to Default'), function() {
            reset_to_default_theme(frm);
        });
        
        // Add theme templates button
        frm.add_custom_button(__('Load Template'), function() {
            show_theme_templates(frm);
        }, __('Templates'));
        
        // Show theme preview if active
        if (frm.doc.is_active) {
            show_theme_preview(frm);
        }
    },
    
    theme_name: function(frm) {
        if (frm.doc.theme_name && frm.doc.theme_name !== 'Custom Theme') {
            load_theme_preset(frm);
        }
    },
    
    business_type: function(frm) {
        if (frm.doc.business_type) {
            load_business_type_colors(frm);
        }
    },
    
    company_specific: function(frm) {
        if (frm.doc.company_specific) {
            frm.set_value('apply_to_all_users', 0);
        }
    },
    
    primary_color: function(frm) {
        update_color_preview(frm);
    },
    
    secondary_color: function(frm) {
        update_color_preview(frm);
    },
    
    accent_color: function(frm) {
        update_color_preview(frm);
    }
});

function preview_theme(frm) {
    if (!frm.doc.theme_name) {
        frappe.msgprint(__('Please select a theme name first'));
        return;
    }
    
    // Create preview dialog
    let dialog = new frappe.ui.Dialog({
        title: __('Theme Preview'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_html'
            }
        ]
    });
    
    // Generate preview HTML
    let preview_html = generate_theme_preview(frm.doc);
    dialog.fields_dict.preview_html.$wrapper.html(preview_html);
    
    dialog.show();
}

function apply_theme(frm) {
    if (!frm.doc.name) {
        frappe.msgprint(__('Please save the theme first'));
        return;
    }
    
    frappe.call({
        method: 'inter_company_transactions.doctype.theme_manager.theme_manager.apply_theme_to_user',
        args: {
            theme_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint(r.message.message);
                // Reload page to apply theme
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                frappe.msgprint(r.message ? r.message.message : __('Failed to apply theme'));
            }
        }
    });
}

function reset_to_default_theme(frm) {
    frappe.confirm(
        __('Are you sure you want to reset to the default theme?'),
        function() {
            frappe.call({
                method: 'inter_company_transactions.enhanced_theme.get_company_theme',
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__('Default theme applied'));
                        window.location.reload();
                    }
                }
            });
        }
    );
}

function show_theme_templates(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Theme Templates'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'templates_html'
            }
        ]
    });
    
    let templates_html = `
        <div class="theme-templates">
            <div class="row">
                ${get_theme_templates().map(template => `
                    <div class="col-md-6 col-lg-4">
                        <div class="theme-template-card" data-template="${template.name}">
                            <div class="theme-preview-image">
                                <img src="${template.preview}" alt="${template.name}" style="width: 100%; height: 150px; object-fit: cover; border-radius: 8px;">
                            </div>
                            <h5>${template.name}</h5>
                            <p>${template.description}</p>
                            <div class="theme-color-palette">
                                ${template.colors.map(color => `
                                    <div class="theme-color-swatch" style="background-color: ${color}"></div>
                                `).join('')}
                            </div>
                            <button class="btn btn-primary btn-sm load-template" data-template="${template.name}">
                                ${__('Load Template')}
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    dialog.fields_dict.templates_html.$wrapper.html(templates_html);
    
    // Add click handlers
    dialog.fields_dict.templates_html.$wrapper.find('.load-template').click(function() {
        let template_name = $(this).data('template');
        load_template(frm, template_name);
        dialog.hide();
    });
    
    dialog.show();
}

function get_theme_templates() {
    return [
        {
            name: 'Accounting Professional',
            description: 'Professional theme for accounting firms',
            preview: '/assets/inter_company_transactions/images/accounting-theme.png',
            colors: ['#28a745', '#20c997', '#f8f9fa', '#333333'],
            settings: {
                primary_color: '#28a745',
                secondary_color: '#20c997',
                background_color: '#f8f9fa',
                text_color: '#333333',
                font_family: 'Inter'
            }
        },
        {
            name: 'Manufacturing Blue',
            description: 'Industrial theme for manufacturing companies',
            preview: '/assets/inter_company_transactions/images/manufacturing-theme.png',
            colors: ['#007bff', '#6610f2', '#f1f3f4', '#333333'],
            settings: {
                primary_color: '#007bff',
                secondary_color: '#6610f2',
                background_color: '#f1f3f4',
                text_color: '#333333',
                font_family: 'Roboto'
            }
        },
        {
            name: 'Trading Green',
            description: 'Fresh theme for trading companies',
            preview: '/assets/inter_company_transactions/images/trading-theme.png',
            colors: ['#28a745', '#20c997', '#f8fff9', '#333333'],
            settings: {
                primary_color: '#28a745',
                secondary_color: '#20c997',
                background_color: '#f8fff9',
                text_color: '#333333',
                font_family: 'Open Sans'
            }
        }
    ];
}

function load_template(frm, template_name) {
    let templates = get_theme_templates();
    let template = templates.find(t => t.name === template_name);
    
    if (template) {
        // Load template settings
        Object.keys(template.settings).forEach(key => {
            frm.set_value(key, template.settings[key]);
        });
        
        frm.set_value('theme_name', template_name);
        frappe.msgprint(__('Template loaded successfully'));
    }
}

function load_theme_preset(frm) {
    let presets = {
        'Modern Dark': {
            primary_color: '#007bff',
            secondary_color: '#6c757d',
            background_color: '#1a1a1a',
            text_color: '#ffffff',
            sidebar_color: '#2d2d2d'
        },
        'Classic Blue': {
            primary_color: '#0056b3',
            secondary_color: '#007bff',
            background_color: '#f8f9fa',
            text_color: '#333333',
            sidebar_color: '#e9ecef'
        },
        'Minimal White': {
            primary_color: '#6c757d',
            secondary_color: '#adb5bd',
            background_color: '#ffffff',
            text_color: '#333333',
            sidebar_color: '#f8f9fa'
        }
    };
    
    let preset = presets[frm.doc.theme_name];
    if (preset) {
        Object.keys(preset).forEach(key => {
            frm.set_value(key, preset[key]);
        });
    }
}

function load_business_type_colors(frm) {
    let business_colors = {
        'Trading': {
            primary_color: '#28a745',
            secondary_color: '#20c997',
            accent_color: '#17a2b8'
        },
        'Manufacturing': {
            primary_color: '#007bff',
            secondary_color: '#6610f2',
            accent_color: '#e83e8c'
        },
        'Services': {
            primary_color: '#6c757d',
            secondary_color: '#adb5bd',
            accent_color: '#fd7e14'
        },
        'Retail': {
            primary_color: '#fd7e14',
            secondary_color: '#e83e8c',
            accent_color: '#20c997'
        }
    };
    
    let colors = business_colors[frm.doc.business_type];
    if (colors) {
        Object.keys(colors).forEach(key => {
            frm.set_value(key, colors[key]);
        });
    }
}

function update_color_preview(frm) {
    // Update color preview in real-time
    let preview_area = frm.fields_dict.theme_preview.$wrapper;
    if (preview_area.length) {
        let css = `
            .color-preview {
                background: linear-gradient(135deg, 
                    ${frm.doc.primary_color || '#007bff'}, 
                    ${frm.doc.secondary_color || '#6c757d'});
                height: 50px;
                border-radius: 8px;
                margin: 10px 0;
            }
        `;
        
        preview_area.find('style').remove();
        preview_area.append(`<style>${css}</style>`);
    }
}

function generate_theme_preview(doc) {
    return `
        <div class="theme-preview-container">
            <style>
                .theme-preview-container {
                    font-family: ${doc.font_family || 'Inter, sans-serif'};
                    background-color: ${doc.background_color || '#ffffff'};
                    color: ${doc.text_color || '#333333'};
                    padding: 20px;
                    border-radius: ${doc.border_radius ? doc.border_radius.split('(')[0] : '8px'};
                }
                .preview-navbar {
                    background-color: ${doc.navbar_color || '#ffffff'};
                    color: ${doc.navbar_text_color || '#333333'};
                    padding: 10px;
                    border-radius: 4px;
                    margin-bottom: 15px;
                }
                .preview-sidebar {
                    background-color: ${doc.sidebar_color || '#f8f9fa'};
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 15px;
                }
                .preview-button {
                    background-color: ${doc.primary_color || '#007bff'};
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    border-radius: ${doc.border_radius ? doc.border_radius.split('(')[0] : '8px'};
                    margin-right: 10px;
                }
                .preview-button.secondary {
                    background-color: ${doc.secondary_color || '#6c757d'};
                }
            </style>
            
            <div class="preview-navbar">
                <strong>Navigation Bar Preview</strong>
            </div>
            
            <div class="row">
                <div class="col-md-3">
                    <div class="preview-sidebar">
                        <strong>Sidebar</strong>
                        <ul style="list-style: none; padding: 0; margin-top: 10px;">
                            <li style="padding: 5px 0;">Dashboard</li>
                            <li style="padding: 5px 0;">Accounts</li>
                            <li style="padding: 5px 0;">Sales</li>
                            <li style="padding: 5px 0;">Purchase</li>
                        </ul>
                    </div>
                </div>
                <div class="col-md-9">
                    <h3>Theme Preview: ${doc.theme_name}</h3>
                    <p>This is how your theme will look in the application.</p>
                    
                    <div style="margin: 20px 0;">
                        <button class="preview-button">Primary Button</button>
                        <button class="preview-button secondary">Secondary Button</button>
                    </div>
                    
                    <div style="background-color: ${doc.accent_color || '#28a745'}; color: white; padding: 10px; border-radius: 4px; margin: 10px 0;">
                        Accent Color Example
                    </div>
                </div>
            </div>
        </div>
    `;
}

function show_theme_preview(frm) {
    if (frm.doc.theme_preview) {
        let preview_html = `
            <div class="theme-preview-image">
                <img src="${frm.doc.theme_preview}" alt="Theme Preview" style="max-width: 100%; height: auto; border-radius: 8px;">
            </div>
        `;
        
        frm.fields_dict.theme_preview.$wrapper.after(preview_html);
    }
}

// Auto-apply theme on login
$(document).ready(function() {
    if (frappe.session.user !== 'Guest') {
        frappe.call({
            method: 'inter_company_transactions.enhanced_theme.get_company_theme',
            callback: function(r) {
                if (r.message && r.message.theme_file_path) {
                    // Load theme CSS
                    let theme_css = `/assets/inter_company_transactions/themes/${r.message.name.toLowerCase().replace(' ', '_')}/theme.css`;
                    $('head').append(`<link rel="stylesheet" type="text/css" href="${theme_css}">`);
                }
            }
        });
    }
});