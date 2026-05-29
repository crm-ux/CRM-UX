# -*- coding: utf-8 -*-
{
    'name': 'CRM Extended - Lead, Quotation & Product Lines',
    'version': '1.3.0',
    'category': 'Sales/CRM',
    'summary': (
        'Extends CRM + Sales: customer type, assign-to rules, refusal workflow, '
        'product interest lines with CSV import, GST-compliant quotation with '
        'per-line and header discounts, PO tracking, and service handoff.'
    ),
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': [
        'crm',
        'sale',
        'sale_crm',
        'uom',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/crm_data.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_create_views.xml',
        'views/crm_lead_product_views.xml',
        'views/sale_order_views.xml',
        'views/sale_quote_preview_wizard_views.xml',
        'views/crm_refuse_wizard_views.xml',
        'views/crm_csv_import_wizard_views.xml',
        'views/crm_lead_wizard_views.xml',
        'views/product_label_view.xml',
        'views/product_make_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_crm_extended/static/src/js/crm_lead_form_view.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}
