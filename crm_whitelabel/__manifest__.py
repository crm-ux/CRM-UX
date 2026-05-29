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
            'crm_whitelabel/static/src/xml/dashboard.xml',
            'crm_whitelabel/static/src/js/dashboard.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
