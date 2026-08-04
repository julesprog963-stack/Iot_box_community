import json
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestCommunityIotApiController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.box = cls.env["community_iot_box.iot_box"].create(
            {"name": "API Test Box", "token": "test_box_secret_token_123"}
        )
        cls.Job = cls.env["community_iot_box.iot_job"]
        cls.printer = cls.env["community_iot_box.iot_device"].create(
            {
                "name": "API PDF Printer",
                "box_id": cls.box.id,
                "device_key": "api-pdf-printer",
                "type": "standard_printer",
                "backend": "standard",
                "interface": "cups",
                "cups_printer_name": "API_PDF_Printer",
            }
        )

    def _headers(self):
        return {
            "X-IOT-BOX-TOKEN": self.box.token,
            "Content-Type": "application/json",
        }

    def _new_job(self, **kwargs):
        kwargs.setdefault("name", "API Test Job")
        kwargs.setdefault("box_id", self.box.id)
        kwargs.setdefault("job_type", "ticket_print")
        kwargs.setdefault("payload", json.dumps({"test": 1}))
        return self.Job.create(kwargs)

    def _new_pdf_job(self):
        return self.Job._create_pdf_jobs(
            device=self.printer,
            pdf_content=b"%PDF-1.4\nAPI document\n%%EOF\n",
            filename="api-document.pdf",
        )

    def _document_headers(self, lock_token, box_token=None):
        return {
            "X-IOT-BOX-TOKEN": box_token or self.box.token,
            "X-IOT-JOB-LOCK-TOKEN": lock_token,
        }

    def test_api_document_requires_current_box_lock_and_lease(self):
        unclaimed = self._new_pdf_job()
        url = f"/iot/api/v1/jobs/{unclaimed.id}/document"
        response = self.url_open(url, headers=self._document_headers("x" * 32))
        self.assertEqual(response.status_code, 404)

        claimed = self.Job.claim_for_box(
            self.box, limit=1, supported_job_types=["document_print"]
        )
        response = self.url_open(
            url, headers=self._document_headers(claimed.lock_token)
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")

        repeated = self.url_open(
            url, headers=self._document_headers(claimed.lock_token)
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.content, response.content)

        wrong_lock = self.url_open(
            url, headers=self._document_headers("z" * 32)
        )
        self.assertEqual(wrong_lock.status_code, 404)

        other_box = self.env["community_iot_box.iot_box"].create(
            {"name": "Other API Box", "token": "other_box_secret_token_123"}
        )
        wrong_box = self.url_open(
            url,
            headers=self._document_headers(
                claimed.lock_token, box_token=other_box.token
            ),
        )
        self.assertEqual(wrong_box.status_code, 404)

        invalid_token = self.url_open(
            url,
            headers=self._document_headers(
                claimed.lock_token, box_token="invalid-box-token"
            ),
        )
        self.assertEqual(invalid_token.status_code, 401)

        claimed.lease_expires_at = fields.Datetime.now() - timedelta(seconds=1)
        expired = self.url_open(
            url, headers=self._document_headers(claimed.lock_token)
        )
        self.assertEqual(expired.status_code, 404)

    def test_api_document_rejects_tampered_attachment(self):
        job = self._new_pdf_job()
        claimed = self.Job.claim_for_box(
            self.box, limit=1, supported_job_types=["document_print"]
        )
        job.document_attachment_id.raw = b"%PDF-1.4\nAPI documenz\n%%EOF\n"
        response = self.url_open(
            f"/iot/api/v1/jobs/{job.id}/document",
            headers=self._document_headers(claimed.lock_token),
        )
        self.assertEqual(response.status_code, 409)

    def test_api_jobs_poll_claims_and_returns_lock_token(self):
        job = self._new_job()
        url = "/iot/api/v1/jobs/poll"
        data = json.dumps({"max_jobs": 1})

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)

        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(len(res.get("jobs", [])), 1)

        job_info = res["jobs"][0]
        self.assertEqual(job_info["job_id"], job.id)
        self.assertTrue(job_info["lock_token"])
        self.assertEqual(job_info["attempt"], 1)

        job.invalidate_recordset(["state", "lock_token", "claimed_at"])
        self.assertEqual(job.state, "processing")

    def test_api_jobs_lease_renew(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        url = "/iot/api/v1/jobs/lease/renew"
        data = json.dumps(
            {
                "leases": [
                    {"job_id": job.id, "lock_token": claimed.lock_token}
                ]
            }
        )

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)

        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(len(res.get("accepted", [])), 1)
        self.assertEqual(res["accepted"][0]["job_id"], job.id)

    def test_api_jobs_result_idempotency(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        url = "/iot/api/v1/jobs/result"
        data = json.dumps(
            {
                "results": [
                    {
                        "job_id": job.id,
                        "lock_token": token,
                        "state": "done",
                        "result_status": "success",
                        "result_message": "Printed",
                    }
                ]
            }
        )

        res1 = self.url_open(url, data=data, headers=self._headers()).json()
        self.assertTrue(res1.get("success"))
        self.assertEqual(res1.get("accepted"), 1)

        job.invalidate_recordset(["state", "lock_token", "processed_at", "result_status"])
        self.assertEqual(job.state, "done")

        res2 = self.url_open(url, data=data, headers=self._headers()).json()
        self.assertTrue(res2.get("success"))
        self.assertEqual(res2.get("accepted"), 1)

        job.invalidate_recordset(["state", "lock_token", "processed_at", "result_status"])
        self.assertEqual(job.state, "done")

    def test_api_malformed_items_no_500(self):
        url = "/iot/api/v1/jobs/result"
        data = json.dumps(
            {
                "results": [
                    "not_a_dict",
                    {"job_id": "abc"},
                    {"job_id": 1, "lock_token": "token", "state": []},
                    {"job_id": 1, "lock_token": "token", "result_status": {}},
                    {"job_id": 1, "lock_token": "token", "result_message": ["msg"]},
                ]
            }
        )

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)

        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("accepted"), 0)
        self.assertEqual(len(res.get("rejected", [])), 5)

    def test_api_batch_limit_over_100_rejected(self):
        url_results = "/iot/api/v1/jobs/result"
        data_results = json.dumps({"results": [{"job_id": i, "lock_token": "t"} for i in range(101)]})
        response_results = self.url_open(url_results, data=data_results, headers=self._headers())
        self.assertEqual(response_results.status_code, 400)
        self.assertFalse(response_results.json().get("success"))
        self.assertEqual(response_results.json().get("error", {}).get("code"), "IOT_INVALID_PAYLOAD")

        url_renew = "/iot/api/v1/jobs/lease/renew"
        data_renew = json.dumps({"leases": [{"job_id": i, "lock_token": "t"} for i in range(101)]})
        response_renew = self.url_open(url_renew, data=data_renew, headers=self._headers())
        self.assertEqual(response_renew.status_code, 400)
        self.assertFalse(response_renew.json().get("success"))
        self.assertEqual(response_renew.json().get("error", {}).get("code"), "IOT_INVALID_PAYLOAD")

    def test_api_contradictory_states_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        url = "/iot/api/v1/jobs/result"
        data = json.dumps(
            {
                "results": [
                    {
                        "job_id": job.id,
                        "lock_token": token,
                        "state": "failed",
                        "status": "done",
                    }
                ]
            }
        )

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("accepted"), 0)
        self.assertEqual(len(res.get("rejected", [])), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")

        job.invalidate_recordset(["state"])
        self.assertEqual(job.state, "processing")

    def test_api_float_huge_id_and_booleans_no_500(self):
        url = "/iot/api/v1/jobs/result"
        data = json.dumps(
            {
                "results": [
                    {"job_id": 1.9, "lock_token": "token", "state": "done"},
                    {"job_id": 2147483648, "lock_token": "token", "state": "done"},
                    {"job_id": 1, "lock_token": True, "state": "done"},
                    {"job_id": 1, "lock_token": "token", "state": False},
                ]
            }
        )

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("accepted"), 0)
        self.assertEqual(len(res.get("rejected", [])), 4)

    def test_api_contrary_terminal_result_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        url = "/iot/api/v1/jobs/result"
        data = json.dumps(
            {
                "results": [
                    {
                        "job_id": job.id,
                        "lock_token": token,
                        "state": "error",
                    }
                ]
            }
        )

        response = self.url_open(url, data=data, headers=self._headers())
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("accepted"), 0)
        self.assertEqual(len(res.get("rejected", [])), 1)
        self.assertEqual(res["rejected"][0]["reason"], "terminal_result_mismatch")

    def test_api_operational_error_reraised_for_odoo_retry(self):
        from unittest.mock import MagicMock, patch
        from psycopg2 import OperationalError
        from odoo.addons.community_iot_box.controllers import iot_api

        api_ctrl = iot_api.CommunityIotApiController()

        fake_request = MagicMock()
        fake_env = MagicMock()
        fake_job_model = MagicMock()

        fake_request.env = fake_env
        fake_env.__getitem__.return_value = fake_job_model
        fake_job_model.sudo.return_value = fake_job_model
        fake_job_model.apply_results_for_box.side_effect = OperationalError(
            "could not serialize access due to concurrent update"
        )

        with patch.object(iot_api, "request", fake_request):
            with patch.object(api_ctrl, "_get_token_and_box", return_value=("token", self.box, None)):
                with patch.object(api_ctrl, "_payload", return_value={"results": []}):
                    with self.assertRaises(OperationalError):
                        api_ctrl.api_jobs_result()

        fake_job_model.apply_results_for_box.assert_called_once()
