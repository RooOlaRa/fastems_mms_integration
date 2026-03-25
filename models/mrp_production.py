import requests
import json
from odoo import models, fields
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    mms_synced = fields.Boolean(string="MMS Synced", default=False, copy=False)

    def action_confirm(self):
        # Run default work order confirmation actions first
        res = super(MrpProduction, self).action_confirm()
        
        for order in self:
            if order.company_id.mms_api_url and order.company_id.mms_api_key:
                self._send_order_to_mms(order)
                
        return res

    def _send_order_to_mms(self, order):
        # Prioritize deadline, fallback current date
        target_date = getattr(order, 'date_deadline', False)
        if not target_date:
            target_date = fields.Datetime.now()
            
        due_date = target_date.isoformat()
        
        payload = {
            "OrderNumber": order.name,
            "PartMasterData": order.product_id.default_code or order.product_id.name,
            "Amount": int(order.product_qty),
            "DueDate": due_date,
            "OrderStatus": "Released"
        }

        headers = {
            'APIKey': order.company_id.mms_api_key,
            'Content-Type': 'application/json'
        }
        
        url = f"{order.company_id.mms_api_url.rstrip('/')}/erp/orders/productionorder"

        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
            if response.status_code == 200:
                order.mms_synced = True
                order.message_post(body="Order sent to Fastems MMS.")
            else:
                order.message_post(body=f"MMS Error: {response.status_code} - {response.text}")
        except Exception as e:
            order.message_post(body=f"MMS Connection Error: {str(e)}")