from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .iot_helpers import build_folio_lines, build_receipt_lines

MAX_POS_IMAGE_BASE64 = 8 * 1024 * 1024


class PosConfig(models.Model):
    _inherit = "pos.config"

    community_iot_enabled = fields.Boolean(
        string="Community IoT Printing",
        help="Send POS receipts and related print jobs through Community IoT.",
    )
    community_iot_box_id = fields.Many2one(
        "community_iot_box.iot_box",
        string="Community IoT Box",
        check_company=True,
    )
    community_iot_receipt_device_id = fields.Many2one(
        "community_iot_box.iot_device",
        string="Receipt Printer",
        domain="[('box_id', '=', community_iot_box_id), ('type', 'in', ('ticket_printer', 'standard_printer')), ('active', '=', True)]",
    )
    community_iot_auto_receipt = fields.Boolean(
        string="Auto Print Receipt via Community IoT",
        default=True,
    )
    community_iot_receipt_copies = fields.Integer(
        string="Receipt Copies",
        default=1,
    )
    community_iot_folio_device_id = fields.Many2one(
        "community_iot_box.iot_device",
        string="Folio Printer",
        domain="[('box_id', '=', community_iot_box_id), ('type', 'in', ('ticket_printer', 'standard_printer')), ('active', '=', True)]",
    )
    community_iot_folio_copies = fields.Integer(
        string="Folio Copies",
        default=2,
    )

    @api.onchange("community_iot_box_id")
    def _onchange_community_iot_box_id(self):
        for config in self:
            if (
                config.community_iot_receipt_device_id
                and config.community_iot_receipt_device_id.box_id != config.community_iot_box_id
            ):
                config.community_iot_receipt_device_id = False
            if (
                config.community_iot_folio_device_id
                and config.community_iot_folio_device_id.box_id != config.community_iot_box_id
            ):
                config.community_iot_folio_device_id = False

    @api.constrains(
        "community_iot_enabled",
        "community_iot_box_id",
        "community_iot_receipt_device_id",
        "community_iot_folio_device_id",
        "community_iot_receipt_copies",
        "community_iot_folio_copies",
    )
    def _check_community_iot_settings(self):
        for config in self:
            if not config.community_iot_enabled:
                continue
            if not config.community_iot_box_id:
                raise ValidationError(_("Select an IoT Box for Community IoT."))
            for field_name in ("community_iot_receipt_device_id", "community_iot_folio_device_id"):
                device = config[field_name]
                if device and device.box_id != config.community_iot_box_id:
                    raise ValidationError(_("Configured printers must belong to the selected IoT Box."))
            if config.community_iot_receipt_copies < 1:
                raise ValidationError(_("Receipt copies must be at least 1."))
            if config.community_iot_receipt_copies > 10:
                raise ValidationError(_("Receipt copies cannot exceed 10."))
            if config.community_iot_folio_copies < 1:
                raise ValidationError(_("Folio copies must be at least 1."))
            if config.community_iot_folio_copies > 10:
                raise ValidationError(_("Folio copies cannot exceed 10."))

    def action_pos_community_iot_print_receipt(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return {"success": False, "message": _("The receipt payload is invalid.")}
        device = self.community_iot_receipt_device_id
        if not self.community_iot_enabled or not device:
            return {"success": False, "message": _("No Community IoT receipt printer is configured.")}

        receipt_data = payload.get("receipt_data") or {}
        receipt_image_base64 = payload.get("receipt_image_base64") or False
        self._validate_community_iot_image(receipt_image_base64)
        order_ref = payload.get("order_ref") or receipt_data.get("name") or "POS"
        copies = int(payload.get("copies") or self.community_iot_receipt_copies or 1)
        lines = build_receipt_lines(self, device, receipt_data, order_ref=order_ref)
        jobs = self._create_community_iot_jobs(
            device=device,
            lines=lines,
            job_label="POS Receipt",
            order_ref=order_ref,
            order_server_id=payload.get("order_server_id"),
            copies=copies,
            extra_payload={
                "render_mode": "image" if receipt_image_base64 else "text",
                "image_format": payload.get("image_format") or "jpeg",
                "image_base64": receipt_image_base64,
                "receipt_data": receipt_data,
            },
        )
        return {"success": True, "job_ids": jobs.ids}

    def action_pos_community_iot_print_folio(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return {"success": False, "message": _("The folio payload is invalid.")}
        device = self.community_iot_folio_device_id
        if not self.community_iot_enabled or not device:
            return {"success": False, "message": _("No Community IoT folio printer is configured.")}

        folio_data = payload.get("folio_data") or {}
        folio_image_base64 = payload.get("folio_image_base64") or False
        self._validate_community_iot_image(folio_image_base64)
        order_ref = payload.get("order_ref") or folio_data.get("orderName") or "POS"
        copies = int(payload.get("copies") or self.community_iot_folio_copies or 1)
        lines = build_folio_lines(self, device, folio_data)
        jobs = self._create_community_iot_jobs(
            device=device,
            lines=lines,
            job_label="POS Folio",
            order_ref=order_ref,
            order_server_id=payload.get("order_server_id"),
            copies=copies,
            extra_payload={
                "render_mode": "image" if folio_image_base64 else "text",
                "image_format": payload.get("image_format") or "jpeg",
                "image_base64": folio_image_base64,
                "folio_data": folio_data,
                "barcode_value": folio_data.get("orderName") or order_ref,
                "barcode_type": "CODE128",
                "barcode_width": 3,
                "barcode_height": 96,
                "barcode_hri": False,
            },
        )
        return {"success": True, "job_ids": jobs.ids}

    def _create_community_iot_jobs(
        self,
        device,
        lines,
        job_label,
        order_ref,
        order_server_id=False,
        copies=1,
        extra_payload=None,
    ):
        self.ensure_one()
        if not device.box_id:
            raise ValidationError(_("The selected printer has no associated IoT Box."))

        payload = device._build_ticket_payload(lines)
        if extra_payload:
            payload.update({key: value for key, value in extra_payload.items() if value not in (None, False, "")})
        payload.update(
            {
                "source": "pos_community_iot",
                "order_ref": order_ref,
                "pos_config_id": self.id,
            }
        )
        origin_id = int(order_server_id) if order_server_id else False
        return self.env["community_iot_box.iot_job"]._create_ticket_jobs(
            device=device,
            payload=payload,
            name=f"{job_label} - {order_ref}",
            copies=copies,
            origin_model="pos.order",
            origin_id=origin_id,
        )

    @api.model
    def _validate_community_iot_image(self, image_base64):
        if image_base64 and (
            not isinstance(image_base64, str) or len(image_base64) > MAX_POS_IMAGE_BASE64
        ):
            raise ValidationError(_("The ticket image exceeds the allowed limit."))
