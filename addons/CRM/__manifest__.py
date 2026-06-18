# -*- coding: utf-8 -*-
{
    'name': 'CRM Extended – Lead & Opportunity',
    'version': '1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Extends default CRM lead/opportunity with custom fields: customer type, purchase timeline, product categories, assign-to rules, and refusal workflow.',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': [
        'crm',      # Core CRM module
        'sale',     # Sales module (for quotations/products)
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/crm_data.xml',
        'views/crm_lead_views.xml',
        'views/crm_refuse_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
