from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _get_pos_ui_pos_config(self, params):
        config = super()._get_pos_ui_pos_config(params)
        receipt_device = self.config_id.community_iot_receipt_device_id
        config.update(
            {
                "community_iot_enabled": self.config_id.community_iot_enabled,
                "community_iot_box_id": self.config_id.community_iot_box_id.id or False,
                "community_iot_receipt_device_id": receipt_device.id or False,
                "community_iot_receipt_ticket_mode": receipt_device.ticket_mode if receipt_device else False,
                "community_iot_receipt_width_px": receipt_device._get_ticket_image_width_px() if receipt_device else False,
                "community_iot_auto_receipt": self.config_id.community_iot_auto_receipt,
                "community_iot_receipt_copies": self.config_id.community_iot_receipt_copies,
                "community_iot_folio_device_id": self.config_id.community_iot_folio_device_id.id or False,
                "community_iot_folio_ticket_mode": self.config_id.community_iot_folio_device_id.ticket_mode if self.config_id.community_iot_folio_device_id else False,
                "community_iot_folio_width_px": self.config_id.community_iot_folio_device_id._get_ticket_image_width_px() if self.config_id.community_iot_folio_device_id else False,
                "community_iot_folio_copies": self.config_id.community_iot_folio_copies,
            }
        )
        return config

    def _loader_params_pos_printer(self):
        params = super()._loader_params_pos_printer()
        fields_list = params["search_params"].setdefault("fields", [])
        for field_name in [
            "community_iot_enabled",
            "community_iot_box_id",
            "community_iot_device_id",
            "community_iot_copies",
        ]:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return params
