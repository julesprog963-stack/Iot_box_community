from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosCommunityIot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.box = cls.env["community_iot_box.iot_box"].create({"name": "POS Box", "state": "online"})
        cls.device = cls.env["community_iot_box.iot_device"].create(
            {
                "name": "POS Receipt",
                "box_id": cls.box.id,
                "device_key": "pos_receipt",
                "type": "ticket_printer",
                "backend": "escpos",
                "interface": "network",
                "connection_host": "192.0.2.10",
                "connection_port": 9100,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Community IoT POS",
                "community_iot_enabled": True,
                "community_iot_box_id": cls.box.id,
                "community_iot_receipt_device_id": cls.device.id,
                "community_iot_receipt_copies": 2,
            }
        )

    def test_receipt_creates_bounded_jobs_through_core(self):
        result = self.config.action_pos_community_iot_print_receipt(
            {
                "order_ref": "Order 001",
                "receipt_data": {"name": "Order 001", "total_with_tax": 10.0},
            }
        )
        self.assertTrue(result["success"])
        jobs = self.env["community_iot_box.iot_job"].browse(result["job_ids"])
        self.assertEqual(len(jobs), 2)
        self.assertEqual(set(jobs.mapped("job_type")), {"ticket_print"})
        self.assertEqual(set(jobs.mapped("device_id")), {self.device})

    def test_invalid_payload_and_oversized_image_are_rejected(self):
        result = self.config.action_pos_community_iot_print_receipt([])
        self.assertFalse(result["success"])
        with self.assertRaises(ValidationError):
            self.config.action_pos_community_iot_print_receipt(
                {"order_ref": "Too Large", "receipt_image_base64": "A" * (8 * 1024 * 1024 + 1)}
            )

    def test_copy_constraint_has_upper_bound(self):
        with self.assertRaises(ValidationError):
            self.config.community_iot_receipt_copies = 11
