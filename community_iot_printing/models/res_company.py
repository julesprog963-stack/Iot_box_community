from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    community_iot_print_device_id = fields.Many2one(
        "community_iot_box.iot_device",
        string="Default IoT PDF Printer",
        domain="[('type', '=', 'standard_printer'), ('active', '=', True), ('box_id.company_id', '=', id), ('box_id.pdf_print_capable', '=', True)]",
    )
    community_iot_print_copies = fields.Integer(
        string="Default IoT PDF Copies",
        default=1,
    )

    @api.constrains("community_iot_print_device_id", "community_iot_print_copies")
    def _check_community_iot_print_settings(self):
        for company in self:
            if not 1 <= company.community_iot_print_copies <= 10:
                raise ValidationError("Default IoT PDF copies must be between 1 and 10.")
            device = company.community_iot_print_device_id
            if not device:
                continue
            if device.box_id.company_id != company:
                raise ValidationError("The default IoT PDF printer must belong to the company.")
            if device.type != "standard_printer":
                raise ValidationError(_("The default IoT PDF printer must be a Standard Printer."))
