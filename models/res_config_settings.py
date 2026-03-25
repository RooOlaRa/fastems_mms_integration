from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    mms_api_url = fields.Char(string='MMS API URL', default='http://mms_mock:8080/mms')
    mms_api_key = fields.Char(string='MMS API Key', default='testkey111')
    mms_last_message_number = fields.Integer(string='Last MMS Message Number', default=0)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mms_api_url = fields.Char(related='company_id.mms_api_url', readonly=False)
    mms_api_key = fields.Char(related='company_id.mms_api_key', readonly=False)