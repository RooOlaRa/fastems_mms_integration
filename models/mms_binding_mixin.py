import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MmsBindingMixin(models.AbstractModel):
    _name = "mms.binding.mixin"
    _description = "MMS Binding Mixin"

    backend_id = fields.Many2one(
        comodel_name="mms.backend",
        string="MMS Backend",
        required=True,
        ondelete="restrict",
    )
    mms_id = fields.Char(
        string="MMS External ID",
        readonly=True,
        help="The identifier of this record in the MMS system",
    )
    sync_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("done", "Synced"),
            ("error", "Error"),
        ],
        string="Sync State",
        default="pending",
        required=True,
        readonly=True,
    )
    sync_date = fields.Datetime(
        string="Last Sync Date",
        readonly=True,
    )
    sync_error = fields.Text(
        string="Sync Error",
        readonly=True,
    )
    integration_active = fields.Boolean(
        string="Integration Active",
        default=True,
        help="Uncheck to pause synchronisation for this record",
    )

    def action_export_to_mms(self):
        """Manually trigger export of selected records as queue jobs."""
        for record in self:
            record.with_delay().export_to_mms()

    def action_reset_to_pending(self):
        """Reset sync state so the record will be retried on the next cron run."""
        self.write({"sync_state": "pending", "sync_error": False})

    def export_to_mms(self):
        """
        Export this binding to MMS. Must be overridden in concrete models.
        """
        raise NotImplementedError(
            "export_to_mms() must be implemented in %s" % self._name
        )

    def _set_sync_done(self, mms_id=None):
        vals = {
            "sync_state": "done",
            "sync_date": fields.Datetime.now(),
            "sync_error": False,
        }
        if mms_id:
            vals["mms_id"] = mms_id
        self.write(vals)

    def _set_sync_error(self, error_message):
        self.write(
            {
                "sync_state": "error",
                "sync_date": fields.Datetime.now(),
                "sync_error": str(error_message),
            }
        )
