import json

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def get_community_iot_pdf_action_ids(self, action_ids, res_model):
        if not self.env.user.has_group("community_iot_printing.group_community_iot_print_user"):
            return []
        if not isinstance(action_ids, list) or len(action_ids) > 100:
            return []
        reports = self.browse(action_ids).exists()
        return reports.filtered(
            lambda report: report.report_type == "qweb-pdf" and report.model == res_model
        ).ids

    @api.model
    def action_open_community_iot_print_wizard(self, report_id, res_model, res_ids):
        if not self.env.user.has_group("community_iot_printing.group_community_iot_print_user"):
            raise AccessError(_("You are not allowed to print through Community IoT."))
        if not isinstance(res_ids, list) or not res_ids or len(res_ids) > 100:
            raise ValidationError(_("Select between 1 and 100 records to print."))
        if any(isinstance(res_id, bool) or not isinstance(res_id, int) or res_id <= 0 for res_id in res_ids):
            raise ValidationError(_("The selected record identifiers are invalid."))

        report = self.browse(int(report_id)).exists()
        if not report or report.report_type != "qweb-pdf" or report.model != res_model:
            raise ValidationError(_("The selected action is not a compatible PDF report."))
        report._check_community_iot_report_groups()

        records = self.env[res_model].browse(res_ids).exists()
        if len(records) != len(set(res_ids)):
            raise ValidationError(_("One or more selected records no longer exist."))
        records.check_access("read")

        return {
            "type": "ir.actions.act_window",
            "name": _("IoT Print"),
            "res_model": "community.iot.print.wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                **self.env.context,
                "default_report_action_id": report.id,
                "default_res_model": res_model,
                "default_res_ids_json": json.dumps(res_ids),
            },
        }

    def _check_community_iot_report_groups(self):
        self.ensure_one()
        group_field = "groups_id" if "groups_id" in self._fields else "group_ids"
        groups = self[group_field] if group_field in self._fields else self.env["res.groups"]
        user_groups = self.env.user.all_group_ids
        if groups and not (groups & user_groups):
            raise AccessError(_("You are not allowed to use this report."))
