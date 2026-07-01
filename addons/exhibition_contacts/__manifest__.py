{
    'name': 'Customer Database',
    'version': '1.0',
    'summary': 'Manage exhibition/visitor contacts with card scanning',
    'category': 'CRM',
    'author': 'Custom',
    'depends': ['base', 'crm', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/exhibition_contact_views.xml',
        'views/exhibition_contact_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'exhibition_contacts/static/src/css/exhibition.css',
        ],
    },
    'installable': True,
    'application': False,
}
