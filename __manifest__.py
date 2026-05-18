{
    'name': 'Fastems MMS Integration',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': 'Posts manufacturing orders to Fastems MMS and polls for manufacturing reports.',
    'depends': ['mrp'],
    'data': [
        'data/ir_cron.xml',
        'views/mms_production_order_binding_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}