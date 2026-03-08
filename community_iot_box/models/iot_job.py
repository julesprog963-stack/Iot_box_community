from odoo import api, fields, models


class CommunityIotJob(models.Model):
    _name = "community_iot_box.iot_job"
    _description = "Community IoT Job"

    name = fields.Char()
    box_id = fields.Many2one("community_iot_box.iot_box", string="IoT Box")
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        help="Estado interno del job (pending/processing/done/error/cancelled).",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="box_id.company_id",
        store=True,
        readonly=True,
    )
    device_id = fields.Many2one(
        "community_iot_box.iot_device",
        string="Device",
    )
    device_key = fields.Char(
        string="Device Key",
        help="Identificador lógico del dispositivo objetivo de este job.",
    )
    job_type = fields.Selection(
        selection=[
            ("ticket_print", "Ticket Print"),
            ("cash_drawer", "Cash Drawer"),
            ("open_cashdrawer", "Open Cash Drawer"),
            ("label_print", "Label Print"),
            ("label_print_zpl", "Label Print ZPL"),
            ("test_ticket", "Test Ticket"),
            ("test_label", "Test Label"),
            ("test_drawer", "Test Drawer"),
        ],
        string="Job Type",
        required=True,
        default="ticket_print",
    )
    payload = fields.Text(
        string="Payload",
        help="Contenido JSON serializado con los datos necesarios para el agente IoT.",
    )
    result_status = fields.Selection(
        selection=[
            ("none", "Not Reported"),
            ("success", "Success"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        string="Result Status",
        default="none",
    )
    result_message = fields.Text(string="Result Message")
    agent_log = fields.Text(string="Agent Log")
    error_code = fields.Char(string="Error Code")
    error_message = fields.Text(string="Error Message")
    origin_model = fields.Char(
        string="Origin Model",
        help="Nombre técnico del modelo origen (por ejemplo 'pos.order', 'stock.picking').",
    )
    origin_id = fields.Integer(
        string="Origin Record ID",
        help="ID del registro origen relacionado con este job.",
    )
    processed_at = fields.Datetime(
        string="Processed At",
        help="Fecha y hora en la que el job terminó (éxito o error).",
    )
