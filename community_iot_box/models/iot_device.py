from odoo import api, fields, models
import json


class CommunityIotDevice(models.Model):
    _name = "community_iot_box.iot_device"
    _description = "Community IoT Device"

    _CONFIG_VERSION_FIELDS = {
        "active",
        "box_id",
        "device_key",
        "type",
        "backend",
        "interface",
        "connection_host",
        "connection_port",
        "connection_device",
        "cups_printer_name",
        "serial_baudrate",
        "usb_vendor_id",
        "usb_product_id",
        "usb_interface",
        "usb_in_ep",
        "usb_out_ep",
        "ticket_mode",
    }

    name = fields.Char(required=True)
    box_id = fields.Many2one("community_iot_box.iot_box", string="IoT Box")
    active = fields.Boolean(default=True)
    auto_detected = fields.Boolean(
        string="Auto Detected",
        default=False,
        help="Set when the device was automatically detected by the IoT agent.",
    )
    auto_identifier = fields.Char(
        string="Auto Identifier",
        index=True,
        help="Stable fingerprint reported by the agent to recognize the same device.",
    )
    discovery_source = fields.Char(
        string="Discovery Source",
        help="Autodiscovery source, for example windows_printer or cups.",
    )
    last_discovered_at = fields.Datetime(string="Last Discovered At")
    discovery_payload = fields.Text(
        string="Discovery Payload",
        help="Raw JSON payload reported by the agent when it detects the device.",
    )

    device_key = fields.Char(
        string="Device Key",
        required=True,
        help="Logical identifier used by the IoT agent (for example 'ticket_main', 'kitchen_printer').",
    )
    type = fields.Selection(
        selection=[
            ("ticket_printer", "Ticket Printer"),
            ("standard_printer", "Standard Printer"),
            ("label_printer", "Label Printer"),
            ("drawer", "Cash Drawer"),
            ("other", "Other"),
        ],
        required=True,
        string="Device Type",
    )
    backend = fields.Selection(
        selection=[
            ("escpos", "ESC/POS"),
            ("zpl", "ZPL"),
            ("standard", "Standard (CUPS/lp)"),
            ("cups", "CUPS"),
            ("cups_generic", "CUPS Generic"),
            ("other", "Other"),
        ],
        required=True,
        string="Backend",
    )
    interface = fields.Selection(
        selection=[
            ("usb", "USB"),
            ("network", "Network"),
            ("serial", "Serial"),
            ("cups", "CUPS"),
            ("other", "Other"),
        ],
        string="Interface",
    )
    connection_host = fields.Char(
        string="Host",
        help="Host o IP del dispositivo cuando se usa interfaz de red.",
    )
    connection_port = fields.Integer(
        string="Port",
        help="Puerto TCP del dispositivo cuando se usa interfaz de red (por ejemplo 9100).",
    )
    connection_device = fields.Char(
        string="Device Path",
        help="Ruta del dispositivo local, por ejemplo /dev/usb/lp0.",
    )
    cups_printer_name = fields.Char(
        string="CUPS Printer Name",
        help="Nombre de la impresora tal como aparece en CUPS (por ejemplo Brother_MFC_L2710DW).",
    )
    serial_baudrate = fields.Integer(
        string="Serial Baudrate",
        default=9600,
    )
    usb_vendor_id = fields.Char(
        string="USB Vendor ID",
        help="Vendor ID USB (decimal o hexadecimal, por ejemplo 0x04b8).",
    )
    usb_product_id = fields.Char(
        string="USB Product ID",
        help="Product ID USB (decimal o hexadecimal, por ejemplo 0x0202).",
    )
    usb_interface = fields.Integer(
        string="USB Interface",
        default=0,
    )
    usb_in_ep = fields.Char(
        string="USB IN EP",
        help="Endpoint IN en hexadecimal (por ejemplo 0x82).",
    )
    usb_out_ep = fields.Char(
        string="USB OUT EP",
        help="Endpoint OUT en hexadecimal (por ejemplo 0x01).",
    )
    ticket_mode = fields.Selection(
        selection=[
            ("narrow", "Thermal 58mm"),
            ("wide", "Thermal 80mm"),
            ("standard", "Standard (A4/Carta)"),
        ],
        string="Ticket Mode",
        default="narrow",
    )
    last_test_status = fields.Selection(
        selection=[
            ("unknown", "Unknown"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        string="Last Test Status",
        default="unknown",
    )
    last_test_date = fields.Datetime(string="Last Test Date")
    notes = fields.Text(string="Notes")

    @api.model_create_multi
    def create(self, vals_list):
        devices = super().create(vals_list)
        if not self.env.context.get("skip_config_version_bump"):
            devices.mapped("box_id")._increment_config_version()
        return devices

    def write(self, vals):
        boxes_before = self.mapped("box_id")
        result = super().write(vals)
        if self.env.context.get("skip_config_version_bump"):
            return result
        if self._should_bump_config_version(vals):
            (boxes_before | self.mapped("box_id"))._increment_config_version()
        return result

    def unlink(self):
        boxes = self.mapped("box_id")
        result = super().unlink()
        if not self.env.context.get("skip_config_version_bump"):
            boxes._increment_config_version()
        return result

    def action_print_test_page(self):
        self.ensure_one()
        if self.type not in {"ticket_printer", "standard_printer"}:
            return self._notify(
                "Print test page",
                "Este dispositivo no es una impresora de tickets.",
                "warning",
            )
        if not self.active:
            return self._notify(
                "Print test page",
                "The device is inactive.",
                "warning",
            )
        if not self.box_id or not self.box_id.active:
            return self._notify(
                "Print test page",
                "El dispositivo no tiene una IoT Box activa asociada.",
                "warning",
            )
        if self.box_id.state != "online":
            return self._notify(
                "Print test page",
                "The IoT Box is not online. Check the agent heartbeat.",
                "warning",
            )

        lines = self.box_id._build_generic_test_ticket(self)
        payload = self._build_ticket_payload(lines)
        job = self.env["community_iot_box.iot_job"].sudo().create(
            {
                "name": f"Test Ticket - {self.name or self.device_key}",
                "box_id": self.box_id.id,
                "device_id": self.id,
                "device_key": self.device_key,
                "job_type": "test_ticket",
                "state": "pending",
                "payload": json.dumps(payload),
            }
        )
        self.write(
            {
                "last_test_status": "unknown",
                "last_test_date": fields.Datetime.now(),
            }
        )
        return self._notify(
            "Print test page",
            f"Test job #{job.id} was created. The agent will process it shortly.",
            "success",
        )

    def _prepare_connection_test_job_values(self):
        self.ensure_one()
        if self.type in {"ticket_printer", "standard_printer"}:
            lines = self.box_id._build_generic_test_ticket(self)
            payload = self._build_ticket_payload(lines)
            job_type = "test_ticket"
        elif self.type == "label_printer":
            payload = self._build_label_test_payload()
            job_type = "test_label"
        elif self.type == "drawer":
            payload = self._build_drawer_payload()
            job_type = "test_drawer"
        else:
            lines = self.box_id._build_generic_test_ticket(self)
            payload = self._build_ticket_payload(lines)
            job_type = "test_ticket"

        return {
            "name": f"Connection test - {self.name or self.device_key}",
            "box_id": self.box_id.id,
            "device_id": self.id,
            "device_key": self.device_key,
            "job_type": job_type,
            "state": "pending",
            "payload": json.dumps(payload),
        }

    def _build_ticket_payload(self, lines):
        self.ensure_one()
        backend = self._get_ticket_backend()
        payload = self._build_common_device_payload()
        payload.update(
            {
                "backend": backend,
                "lines": lines,
                "ticket_mode": self.ticket_mode or ("standard" if backend == "standard" else "narrow"),
                "printer_width_px": self._get_ticket_image_width_px(),
                "open_cashdrawer": False,
            }
        )
        return payload

    def _build_label_test_payload(self):
        self.ensure_one()
        payload = self._build_common_device_payload()
        payload.update(
            {
                "backend": "zpl",
                "raw_zpl": (
                    "^XA\n"
                    "^FO20,30^A0N,30,30^FDETIQUETA DE PRUEBA^FS\n"
                    "^FO20,70^A0N,24,24^FDIoT Box Community^FS\n"
                    "^XZ\n"
                ),
            }
        )
        return payload

    def _build_drawer_payload(self):
        self.ensure_one()
        payload = self._build_common_device_payload()
        payload.update(
            {
                "backend": "escpos",
                "open_cashdrawer": True,
            }
        )
        return payload

    def _build_common_device_payload(self):
        self.ensure_one()
        return {
            "device_key": self.device_key,
            "device_type": self.type,
            "backend": self.backend,
            "connection_type": self.interface,
            "interface": self.interface,
            "ticket_mode": self.ticket_mode,
            "printer_width_px": self._get_ticket_image_width_px(),
            "ip_address": self.connection_host,
            "host": self.connection_host,
            "port": self.connection_port,
            "device_path": self.connection_device,
            "serial_device_path": self.connection_device,
            "serial_baudrate": self.serial_baudrate,
            "cups_printer_name": self.cups_printer_name,
            "usb_vendor_id": self.usb_vendor_id,
            "usb_product_id": self.usb_product_id,
            "usb_interface": self.usb_interface,
            "usb_in_ep": self.usb_in_ep,
            "usb_out_ep": self.usb_out_ep,
            "connection": {
                "host": self.connection_host,
                "ip_address": self.connection_host,
                "port": self.connection_port,
                "device": self.connection_device,
                "serial_device_path": self.connection_device,
                "serial_baudrate": self.serial_baudrate,
                "cups_printer_name": self.cups_printer_name,
                "usb_vendor_id": self.usb_vendor_id,
                "usb_product_id": self.usb_product_id,
                "usb_interface": self.usb_interface,
                "usb_in_ep": self.usb_in_ep,
                "usb_out_ep": self.usb_out_ep,
                "ticket_mode": self.ticket_mode,
                "printer_width_px": self._get_ticket_image_width_px(),
            },
        }

    def _get_ticket_backend(self):
        self.ensure_one()
        backend = (self.backend or "").strip().lower()
        if self.type == "standard_printer":
            return "standard"
        if backend in {"standard", "cups_generic"}:
            return "standard"
        if backend == "cups" and self.type == "standard_printer":
            return "standard"
        return "escpos"

    def _get_ticket_text_width(self):
        self.ensure_one()
        if self.type == "standard_printer" or self.ticket_mode == "standard":
            return 80
        if self.ticket_mode == "wide":
            return 56
        return 42

    def _get_ticket_image_width_px(self):
        self.ensure_one()
        if self.type == "standard_printer" or self.ticket_mode == "standard":
            return 768
        if self.ticket_mode == "wide":
            return 576
        return 384

    @api.model
    def _should_bump_config_version(self, vals):
        return bool(set(vals) & self._CONFIG_VERSION_FIELDS)

    def _notify(self, title, message, level="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": level,
                "sticky": False,
            },
        }
