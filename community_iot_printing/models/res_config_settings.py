from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    community_iot_print_device_id = fields.Many2one(
        related="company_id.community_iot_print_device_id",
        readonly=False,
    )
    community_iot_print_copies = fields.Integer(
        related="company_id.community_iot_print_copies",
        readonly=False,
    )
