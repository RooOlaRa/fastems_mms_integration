import requests
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class MmsReportSync(models.AbstractModel):
    _name = 'mms.report.sync'
    _description = 'MMS Report Synchronization'

    @api.model
    def poll_mms_reports(self):
        company = self.env.company
        if not company.mms_api_url or not company.mms_api_key:
            return

        headers = {'APIKey': company.mms_api_key}
        start_msg_num = company.mms_last_message_number
        
        url = f"{company.mms_api_url.rstrip('/')}/erp/reports/bufferdata?startMessageNumber={start_msg_num}&limit=50"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return

            data = response.json()
            reports = data.get('Reports', [])
            
            if not reports:
                return

            highest_msg_num = start_msg_num

            for report in reports:
                msg_num = report.get('MessageNumber', 0)
                
                # Skip if message has been handled already
                if msg_num <= start_msg_num:
                    continue

                if msg_num > highest_msg_num:
                    highest_msg_num = msg_num
                    
                self._process_report(report)

            # Update latest message number index on Odoo
            company.mms_last_message_number = highest_msg_num

            # Delete handled messages (Commented out because messages are not saved anywhere on the Odoo side before deleting from MMS)
            # delete_url = f"{company.mms_api_url.rstrip('/')}/erp/reports/bufferdata?fromMessageNumber={start_msg_num}&toMessageNumber={highest_msg_num}"
            # requests.delete(delete_url, headers=headers, timeout=10)

        except Exception as e:
            _logger.error(f"MMS Polling error: {str(e)}")

    def _process_report(self, report):
        report_type = report.get('discriminator')
        order_number = report.get('OrderNumber')
        
        if not order_number:
            return

        production_order = self.env['mrp.production'].search([('name', '=', order_number)], limit=1)
        if not production_order:
            return

        if report_type == 'parts-produced':
            amount = report.get('Amount', 0)
            production_order.message_post(body=f"MMS: {amount} parts manufactured from operation {report.get('OperationNumber')}.")
            # If this is the last operation (IsLastOperation = True), can add to produced amount.
            if report.get('IsLastOperation'):
                production_order.qty_producing += amount
                
        elif report_type == 'orders-completed':
            if production_order.state != 'done':
                production_order.button_mark_done()
                production_order.message_post(body="MMS: Order Ready.")
            
        elif report_type == 'parts-scrapped':
            amount = report.get('Amount', 0)
            reason = report.get('ScrapReason', 'No Reason')
            production_order.message_post(body=f"MMS: {amount} parts scrapped. Reason: {reason}")