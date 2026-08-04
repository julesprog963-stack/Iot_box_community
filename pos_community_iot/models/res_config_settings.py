from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_community_iot_enabled = fields.Boolean(related="pos_config_id.community_iot_enabled", readonly=False)
    pos_community_iot_box_id = fields.Many2one(
        related="pos_config_id.community_iot_box_id",
        readonly=False,
    )
    pos_community_iot_receipt_device_id = fields.Many2one(
        related="pos_config_id.community_iot_receipt_device_id",
        readonly=False,
    )
    pos_community_iot_auto_receipt = fields.Boolean(
        related="pos_config_id.community_iot_auto_receipt",
        readonly=False,
    )
    pos_community_iot_receipt_copies = fields.Integer(
        related="pos_config_id.community_iot_receipt_copies",
        readonly=False,
    )
    pos_community_iot_folio_device_id = fields.Many2one(
        related="pos_config_id.community_iot_folio_device_id",
        readonly=False,
    )
    pos_community_iot_folio_copies = fields.Integer(
        related="pos_config_id.community_iot_folio_copies",
        readonly=False,
    )
