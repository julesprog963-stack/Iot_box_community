import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval, time


class CommunityIotPrintWizard(models.TransientModel):
    _name = "community.iot.print.wizard"
    _description = "Community IoT PDF Print"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    report_action_id = fields.Many2one("ir.actions.report", required=True, readonly=True)
    res_model = fields.Char(required=True, readonly=True)
    res_ids_json = fields.Text(required=True, readonly=True)
    device_id = fields.Many2one(
        "community_iot_box.iot_device",
        string="IoT Printer",
        required=True,
        domain="[('type', '=', 'standard_printer'), ('active', '=', True), ('box_id.company_id', '=', company_id), ('box_id.state', '=', 'online'), ('box_id.pdf_print_capable', '=', True)]",
    )
    copies = fields.Integer(required=True, default=1)
    filename = fields.Char(required=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        company = self.env.company
        report = self.env["ir.actions.report"].browse(values.get("report_action_id")).exists()
        values.setdefault("company_id", company.id)
        values.setdefault("device_id", company.community_iot_print_device_id.id)
        values.setdefault("copies", company.community_iot_print_copies or 1)
        if report:
            values.setdefault("filename", self._build_filename(report, self._context_res_ids(values)))
        return values

    @api.constrains("copies")
    def _check_copies(self):
        for wizard in self:
            if not 1 <= wizard.copies <= 10:
                raise ValidationError(_("Copies must be between 1 and 10."))

    def action_print(self):
        self.ensure_one()
        if not self.env.user.has_group("community_iot_printing.group_community_iot_print_user"):
            raise AccessError(_("You are not allowed to print through Community IoT."))

        report = self.report_action_id.exists()
        report._check_community_iot_report_groups()
        if report.report_type != "qweb-pdf" or report.model != self.res_model:
            raise ValidationError(_("The report is no longer a compatible PDF report."))

        res_ids = self._context_res_ids()
        if not res_ids or len(res_ids) > 100:
            raise ValidationError(_("Select between 1 and 100 records to print."))
        records = self.env[self.res_model].browse(res_ids).exists()
        if len(records) != len(set(res_ids)):
            raise ValidationError(_("One or more selected records no longer exist."))
        records.check_access("read")

        device = self.device_id
        if (
            not device.active
            or device.type != "standard_printer"
            or device.box_id.company_id != self.company_id
            or device.box_id.state != "online"
            or not device.box_id.pdf_print_capable
        ):
            raise ValidationError(_("Select an online PDF-capable Standard Printer for this company."))

        render_context = dict(self.env.context)
        render_context.update(
            {"active_model": self.res_model, "active_ids": res_ids, "active_id": res_ids[0]}
        )
        pdf_content = report.with_context(render_context)._render_qweb_pdf(
            report.report_name,
            res_ids,
        )[0]
        origin_id = res_ids[0] if len(res_ids) == 1 else False
        jobs = self.env["community_iot_box.iot_job"]._create_pdf_jobs(
            device=device,
            pdf_content=pdf_content,
            filename=self.filename,
            copies=self.copies,
            name=report.name,
            payload={
                "source": "community_iot_printing",
                "report_name": report.report_name,
                "report_action_id": report.id,
                "active_model": self.res_model,
            },
            origin_model=self.res_model,
            origin_id=origin_id,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("IoT Print"),
                "message": _("Queued %(count)s PDF print job(s) for %(printer)s.", count=len(jobs), printer=device.name),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _context_res_ids(self, values=None):
        raw = (values or {}).get("res_ids_json") if values is not None else self.res_ids_json
        if isinstance(raw, list):
            parsed = raw
        else:
            try:
                parsed = json.loads(raw or "[]")
            except (TypeError, ValueError):
                parsed = []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, int) and not isinstance(item, bool)]

    def _build_filename(self, report, res_ids):
        if len(res_ids) == 1 and report.print_report_name:
            record = self.env[report.model].browse(res_ids[0])
            try:
                evaluated = safe_eval(report.print_report_name, {"object": record, "time": time})
                if evaluated:
                    return f"{evaluated}.pdf"
            except Exception:
                pass
        return f"{report.name or 'document'}.pdf"
