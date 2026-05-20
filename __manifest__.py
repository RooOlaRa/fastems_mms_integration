{
    'name': 'Fastems MMS Integration',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': 'Posts manufacturing orders to Fastems MMS and polls for manufacturing reports.',
    'depends': [
        'mrp',
        'queue_job',],
    
    'data': [
        "security/ir.model.access.csv",
        "views/mms_backend_views.xml",
        "views/mms_production_order_binding_views.xml",
        "data/ir_cron.xml",
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}