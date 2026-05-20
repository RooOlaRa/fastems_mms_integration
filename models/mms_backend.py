import logging

import requests
from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MmsBackend(models.Model):
    """
    MMS Integration settings and main functionalities

    Done:
    - POST / DELETE for production orders from Odoo to MMS
    - GET production reports from MMS and update work orders in Odoo
    """

    _name = "mms.backend"
    _description = "Fastems MMS Backend"

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(default=True)

    api_url = fields.Char(
        string="API URL",
        required=True,
        help="Base URL of the MMS REST API, e.g. http://mms-server:8080",
    )

    auth_method = fields.Selection(
        selection=[
            ("basic", "HTTP Basic Authentication"),
            ("apikey", "ApiKey Authentication"),
        ],
        string="Authentication Method",
        required=True,
        default="basic",
    )

    api_username = fields.Char(string="Username")
    api_password = fields.Char(string="Password")
    api_key = fields.Char(string="API Key", password=True)

    sync_production_orders = fields.Boolean(
        string="Export Production Orders",
        default=True,
        help="Automatically export pending production order bindings to MMS.",
    )

    import_production_reports = fields.Boolean(
        string="Import Production Reports",
        default=True,
        help="Fetch manufacturing feedback from MMS and update work order states.",
    )

    last_report_message_number = fields.Integer(
        string="Last Imported Message Number",
        default=0,
        help=(
            "MMS message number to start from on the next poll. "
            "Set to 0 to re-fetch from the oldest available message."
        ),
    )
    report_batch_limit = fields.Integer(
        string="Report Batch Size",
        default=100,
        help="How many MMS report messages to request per polling cycle.",
    )

    def action_test_connection(self):
        """Ping the MMS API via the reports endpoint and show result."""
        self.ensure_one()
        try:
            self._make_request(
                "GET",
                "/erp/reports/bufferdata",
                params={"startMessageNumber": 0, "limit": 1},
            )
        except requests.exceptions.RequestException as exc:
            raise UserError(_("Connection error: %s") % str(exc)) from exc

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection successful"),
                "message": _("MMS API is reachable."),
                "type": "success",
                "sticky": False,
            },
        }

    def cron_export_production_orders(self):
        """
        Called by the scheduler.
        Enqueues one export job per pending binding on every active backend.
        """
        for backend in self.search([("sync_production_orders", "=", True)]):
            backend.with_delay().job_export_production_orders()

    def cron_import_production_reports(self):
        """
        Called by the scheduler.
        Enqueues one import job per active backend.
        """
        for backend in self.search([("import_production_reports", "=", True)]):
            backend.with_delay().job_import_production_reports()


    def job_export_production_orders(self):
        """
        Queue job: find all pending/errored bindings for this backend and
        enqueue a separate export job for each one.
        """
        self.ensure_one()
        bindings = self.env["mms.production.order.binding"].search(
            [
                ("backend_id", "=", self.id),
                ("sync_state", "in", ["pending", "error"]),
                ("integration_active", "=", True),
            ]
        )
        _logger.info(
            "MMS backend '%s': enqueueing export for %d production order binding(s).",
            self.name, len(bindings),
        )
        for binding in bindings:
            binding.with_delay().export_to_mms()

    def job_import_production_reports(self):
        """
        Queue job: GET buffered manufacturing reports from MMS and send
        each one to the production order binding for work order updating
        """
        self.ensure_one()

        response = self._make_request(
            "GET",
            "/erp/reports/bufferdata",
            params={
                "startMessageNumber": self.last_report_message_number,
                "limit": self.report_batch_limit,
            },
        )

        data = response.json()
        reports = data.get("Reports", [])

        if not reports:
            _logger.debug("MMS backend '%s': no new reports.", self.name)
            return

        _logger.info(
            "MMS backend '%s': processing %d report(s) from message #%d.",
            self.name, len(reports), self.last_report_message_number,
        )

        binding_model = self.env["mms.production.order.binding"]
        for report in reports:
            binding_model._process_mms_report(self, report)

        # Advance the pointer so the same messages are never re-processed
        max_msg = max(r.get("MessageNumber", 0) for r in reports)
        self.last_report_message_number = max_msg + 1

    def _make_request(self, method, endpoint, **kwargs):
        """Convenience wrapper – delegates to the API request mixin."""
        return self.env["mms.api.request.mixin"]._make_request(
            self, method, endpoint, **kwargs
        )
