
# -*- coding: utf-8 -*-
{
    'name': 'CRM White Label Login',
    'version': '1.0.0',
    'category': 'Web',
    'summary': 'Custom login page - remove Odoo branding',
    'depends': ['web'],
    'data': [
        'templates/login.xml',
        'views/dashboard.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'crm_whitelabel/static/src/css/login.css',
        ],
        'web.assets_backend': [
            'crm_whitelabel/static/src/css/dashboard.css',
            'crm_whitelabel/static/src/css/form_custom.css',
            'crm_whitelabel/static/src/xml/dashboard.xml',
            'crm_whitelabel/static/src/css/whitelabel.css',
            'crm_whitelabel/static/src/xml/nav_buttons.xml',
            'crm_whitelabel/static/src/js/dashboard.js',
            'crm_whitelabel/static/src/js/nav_buttons.js',
            'crm_whitelabel/static/src/js/terms_checkbox.js',
            'crm_whitelabel/static/src/js/statusbar_override.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
