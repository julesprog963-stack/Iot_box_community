import json
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


PDF_BYTES = b"%PDF-1.4\n% Community IoT report test\n%%EOF\n"


@tagged("post_install", "-at_install")
class TestCommunityIotPrinting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref("community_iot_printing.group_community_iot_print_user")
        cls.env.user.write({"groups_id": [Command.link(cls.group.id)]})
        cls.box = cls.env["community_iot_box.iot_box"].create(
            {
                "name": "Global PDF Box",
                "state": "online",
                "agent_capabilities": json.dumps(["pdf_print_v1"]),
            }
        )
        cls.device = cls.env["community_iot_box.iot_device"].create(
            {
                "name": "Global A4",
                "box_id": cls.box.id,
                "device_key": "global_a4",
                "type": "standard_printer",
                "backend": "standard",
                "interface": "cups",
                "cups_printer_name": "Global_A4",
            }
        )
        cls.env.company.write(
            {"community_iot_print_device_id": cls.device.id, "community_iot_print_copies": 2}
        )
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "Partner Test PDF",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": "community_iot_printing.partner_test_pdf",
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "PDF Customer"})

    def _wizard(self, copies=2):
        return self.env["community.iot.print.wizard"].create(
            {
                "company_id": self.env.company.id,
                "report_action_id": self.report.id,
                "res_model": "res.partner",
                "res_ids_json": json.dumps([self.partner.id]),
                "device_id": self.device.id,
                "copies": copies,
                "filename": "partner.pdf",
            }
        )

    def test_report_menu_filters_to_pdf_and_opens_wizard(self):
        html_report = self.env["ir.actions.report"].create(
            {
                "name": "HTML Test",
                "model": "res.partner",
                "report_type": "qweb-html",
                "report_name": "community_iot_printing.partner_test_html",
            }
        )
        valid = self.env["ir.actions.report"].get_community_iot_pdf_action_ids(
            [self.report.id, html_report.id],
            "res.partner",
        )
        self.assertEqual(valid, [self.report.id])
        action = self.env["ir.actions.report"].action_open_community_iot_print_wizard(
            self.report.id,
            "res.partner",
            [self.partner.id],
        )
        self.assertEqual(action["res_model"], "community.iot.print.wizard")
        self.assertEqual(action["views"], [(False, "form")])

    def test_wizard_renders_as_user_and_queues_one_job_per_copy(self):
        wizard = self._wizard(copies=2)
        with patch.object(
            type(self.report),
            "_render_qweb_pdf",
            autospec=True,
            return_value=(PDF_BYTES, "pdf"),
        ) as render:
            result = wizard.action_print()
        self.assertEqual(result["tag"], "display_notification")
        render.assert_called_once()
        jobs = self.env["community_iot_box.iot_job"].search(
            [("origin_model", "=", "res.partner"), ("origin_id", "=", self.partner.id)]
        )
        self.assertEqual(len(jobs), 2)
        self.assertEqual(len(jobs.mapped("document_attachment_id")), 1)

    def test_offline_or_incompatible_printer_is_rejected(self):
        wizard = self._wizard(copies=1)
        self.box.state = "offline"
        with self.assertRaises(ValidationError):
            wizard.action_print()

    def test_user_without_group_cannot_open_iot_wizard(self):
        user = self.env["res.users"].create(
            {
                "name": "No IoT Print",
                "login": "no_iot_print",
                "groups_id": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["ir.actions.report"].with_user(user).action_open_community_iot_print_wizard(
                self.report.id,
                "res.partner",
                [self.partner.id],
            )
