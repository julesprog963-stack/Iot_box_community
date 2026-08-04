import json

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


PDF_BYTES = b"%PDF-1.4\n% Community IoT Odoo test\n%%EOF\n"


@tagged("post_install", "-at_install")
class TestCommunityIotDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.box = cls.env["community_iot_box.iot_box"].create(
            {
                "name": "PDF Box",
                "state": "online",
                "agent_capabilities": json.dumps(["pdf_print_v1"]),
            }
        )
        cls.device = cls.env["community_iot_box.iot_device"].create(
            {
                "name": "Office A4",
                "box_id": cls.box.id,
                "device_key": "office_a4",
                "type": "standard_printer",
                "backend": "standard",
                "interface": "cups",
                "cups_printer_name": "Office_A4",
            }
        )
        cls.Job = cls.env["community_iot_box.iot_job"]

    def _create_jobs(self, copies=2):
        return self.Job._create_pdf_jobs(
            device=self.device,
            pdf_content=PDF_BYTES,
            filename="quotation.pdf",
            copies=copies,
            name="Quotation",
            payload={"source": "test"},
            origin_model="res.partner",
        )

    def test_pdf_jobs_share_bounded_attachment_and_metadata(self):
        jobs = self._create_jobs(copies=2)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(len(jobs.mapped("document_attachment_id")), 1)
        self.assertEqual(set(jobs.mapped("document_size")), {len(PDF_BYTES)})
        self.assertEqual(set(jobs.mapped("document_mimetype")), {"application/pdf"})
        self.assertTrue(all(len(value) == 64 for value in jobs.mapped("document_sha256")))
        self.assertTrue(all("%PDF" not in payload for payload in jobs.mapped("payload")))

    def test_non_pdf_and_excessive_copies_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.Job._create_pdf_jobs(
                device=self.device,
                pdf_content=b"not-pdf",
                filename="bad.pdf",
            )
        with self.assertRaises(ValidationError):
            self._create_jobs(copies=11)

    def test_capability_filter_keeps_pdf_from_legacy_agent(self):
        jobs = self._create_jobs(copies=1)
        claimed = self.Job.claim_for_box(
            self.box,
            limit=5,
            supported_job_types=["ticket_print"],
        )
        self.assertFalse(claimed)
        self.assertEqual(jobs.state, "pending")

    def test_successful_copies_remove_pdf_only_after_last_result(self):
        jobs = self._create_jobs(copies=2)
        attachment = jobs.document_attachment_id
        claimed = self.Job.claim_for_box(
            self.box,
            limit=2,
            supported_job_types=["document_print"],
        )
        first, second = claimed.sorted("id")
        self.Job.apply_results_for_box(
            self.box,
            [{"job_id": first.id, "lock_token": first.lock_token, "state": "done"}],
        )
        self.assertTrue(attachment.exists())
        self.Job.apply_results_for_box(
            self.box,
            [{"job_id": second.id, "lock_token": second.lock_token, "state": "done"}],
        )
        self.assertFalse(attachment.exists())
        self.assertFalse(jobs.document_attachment_id)

    def test_failed_pdf_can_retry_and_expired_pdf_is_cleaned(self):
        job = self._create_jobs(copies=1)
        claimed = self.Job.claim_for_box(
            self.box,
            limit=1,
            supported_job_types=["document_print"],
        )
        self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": claimed.lock_token, "state": "error"}],
        )
        self.assertEqual(job.state, "error")
        self.assertTrue(job.document_expires_at)
        job.action_retry_document()
        self.assertEqual(job.state, "pending")
        self.assertFalse(job.document_expires_at)

        job.write(
            {
                "state": "error",
                "document_expires_at": fields.Datetime.subtract(fields.Datetime.now(), days=1),
            }
        )
        attachment = job.document_attachment_id
        self.Job._cron_cleanup_expired_documents()
        self.assertFalse(attachment.exists())
        with self.assertRaises(UserError):
            job.action_retry_document()
