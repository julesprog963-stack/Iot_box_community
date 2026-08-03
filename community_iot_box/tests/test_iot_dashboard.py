from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommunityIotDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Box = cls.env["community_iot_box.iot_box"]
        cls.Device = cls.env["community_iot_box.iot_device"]
        cls.Job = cls.env["community_iot_box.iot_job"]

        cls.online_box = cls.Box.create(
            {
                "name": "Dashboard Online",
                "state": "online",
                "last_seen": fields.Datetime.now(),
                "agent_version": "1.0.0",
                "ip_address": "192.0.2.10",
            }
        )
        cls.offline_box = cls.Box.create(
            {
                "name": "Dashboard Offline",
                "state": "offline",
            }
        )
        cls.device = cls.Device.create(
            {
                "name": "Dashboard Printer",
                "box_id": cls.online_box.id,
                "device_key": "dashboard_printer",
                "type": "standard_printer",
                "backend": "cups",
                "interface": "cups",
            }
        )
        cls.pending_job = cls.Job.create(
            {
                "name": "Dashboard Pending",
                "box_id": cls.online_box.id,
                "device_id": cls.device.id,
                "job_type": "test_ticket",
                "payload": "{}",
            }
        )
        cls.error_job = cls.Job.create(
            {
                "name": "Dashboard Error",
                "box_id": cls.online_box.id,
                "device_id": cls.device.id,
                "job_type": "test_ticket",
                "state": "error",
                "result_status": "error",
                "payload": "{}",
            }
        )

    def test_dashboard_returns_real_metrics_without_tokens(self):
        data = self.Box.get_dashboard_data()

        self.assertGreaterEqual(data["metrics"]["boxes_total"], 2)
        self.assertGreaterEqual(data["metrics"]["boxes_online"], 1)
        self.assertGreaterEqual(data["metrics"]["devices_total"], 1)
        self.assertGreaterEqual(data["metrics"]["jobs_pending"], 1)
        self.assertGreaterEqual(data["metrics"]["attention"], 2)

        online_card = next(
            item for item in data["boxes"] if item["id"] == self.online_box.id
        )
        self.assertTrue(online_card["token_configured"])
        self.assertNotIn("token", online_card)
        self.assertNotIn(self.online_box.token, repr(data))

    def test_dashboard_recent_jobs_and_alerts_are_serializable(self):
        data = self.Box.get_dashboard_data()

        job_ids = {item["id"] for item in data["jobs"]}
        self.assertIn(self.pending_job.id, job_ids)
        self.assertIn(self.error_job.id, job_ids)
        self.assertTrue(data["alerts"])

        for alert in data["alerts"]:
            self.assertIsInstance(alert["key"], str)
            self.assertIn(alert["level"], {"warning", "danger"})
