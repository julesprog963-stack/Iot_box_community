from datetime import timedelta

from odoo import exceptions, fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommunityIotJobLease(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.box = cls.env["community_iot_box.iot_box"].create(
            {"name": "Lease test box"}
        )
        cls.box_b = cls.env["community_iot_box.iot_box"].create(
            {"name": "Second test box"}
        )
        cls.device = cls.env["community_iot_box.iot_device"].create(
            {
                "name": "Test Printer",
                "box_id": cls.box.id,
                "device_key": "test_printer_1",
                "type": "ticket_printer",
                "backend": "escpos",
                "interface": "usb",
            }
        )
        cls.Job = cls.env["community_iot_box.iot_job"]

    def _new_job(self, **values):
        values.setdefault("name", "Lease test")
        values.setdefault("box_id", self.box.id)
        values.setdefault("device_id", self.device.id)
        values.setdefault("job_type", "test_ticket")
        values.setdefault("payload", "{}")
        return self.Job.create(values)

    def test_claim_assigns_token_and_prevents_second_claim(self):
        job = self._new_job()

        first = self.Job.claim_for_box(self.box, limit=1)
        second = self.Job.claim_for_box(self.box, limit=1)

        self.assertEqual(first, job)
        self.assertFalse(second)
        self.assertEqual(job.state, "processing")
        self.assertTrue(job.lock_token)
        self.assertEqual(job.attempt_count, 1)
        self.assertTrue(job.lease_expires_at > job.claimed_at)

    def test_two_jobs_claimed_receive_distinct_tokens(self):
        job1 = self._new_job(name="Job 1")
        job2 = self._new_job(name="Job 2")

        claimed = self.Job.claim_for_box(self.box, limit=2)

        self.assertEqual(len(claimed), 2)
        self.assertIn(job1, claimed)
        self.assertIn(job2, claimed)
        self.assertNotEqual(job1.lock_token, job2.lock_token)

    def test_expired_lease_returns_to_queue(self):
        job = self._new_job()
        first = self.Job.claim_for_box(self.box, limit=1)
        first.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '1 second'
             WHERE id = %s
            """,
            [job.id],
        )
        old_token = first.lock_token

        reclaimed = self.Job.claim_for_box(self.box, limit=1)

        self.assertEqual(reclaimed, job)
        self.assertNotEqual(reclaimed.lock_token, old_token)
        self.assertEqual(reclaimed.attempt_count, 2)

    def test_orm_invalidation_reflects_recovery(self):
        job = self._new_job()
        claimed1 = self.Job.claim_for_box(self.box, limit=1, lease_seconds=30)
        old_token = claimed1.lock_token
        old_expires_at = claimed1.lease_expires_at
        self.assertEqual(claimed1.attempt_count, 1)

        claimed1.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '10 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        claimed2 = self.Job.claim_for_box(self.box, limit=1, lease_seconds=900)

        self.assertEqual(claimed2, job)
        self.assertEqual(job.state, "processing")
        self.assertNotEqual(job.lock_token, old_token)
        self.assertEqual(job.attempt_count, 2)
        self.assertTrue(job.lease_expires_at > old_expires_at)

    def test_release_for_retry_clears_lease(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        claimed.release_for_retry()

        self.assertEqual(job.state, "pending")
        self.assertFalse(job.lock_token)
        self.assertFalse(job.claimed_at)
        self.assertFalse(job.lease_expires_at)

    def test_renew_lease_valid(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        old_expires_at = claimed.lease_expires_at

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": job.lock_token}],
            default_lease_seconds=1800,
        )

        self.assertEqual(len(res["accepted"]), 1)
        self.assertEqual(res["accepted"][0]["job_id"], job.id)
        self.assertEqual(len(res["rejected"]), 0)
        self.assertTrue(job.lease_expires_at > old_expires_at)

    def test_renew_lease_invalid_token_rejected(self):
        job = self._new_job()
        self.Job.claim_for_box(self.box, limit=1)

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": "wrong_token"}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")

    def test_renew_lease_other_box_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        res = self.Job.renew_lease_for_box(
            self.box_b,
            [{"job_id": job.id, "lock_token": claimed.lock_token}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")

    def test_renew_lease_terminal_job_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")

    def test_renew_lease_null_lease_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        claimed.write({"lease_expires_at": False})

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": claimed.lock_token}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_renew_lease_expired_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        claimed.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '5 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": claimed.lock_token}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_renew_lease_equal_now_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        boundary = fields.Datetime.now()
        claimed.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = %s
             WHERE id = %s
            """,
            [boundary, job.id],
        )

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": claimed.lock_token}],
        )

        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_result_null_lease_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        claimed.write({"lease_expires_at": False})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_result_expired_lease_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        claimed.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '5 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_result_equal_now_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        boundary = fields.Datetime.now()
        claimed.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = %s
             WHERE id = %s
            """,
            [boundary, job.id],
        )

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    def test_result_contradictory_states_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "failed", "status": "done"}],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")
        self.assertEqual(job.state, "processing")

    def test_result_compound_field_types_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": job.id, "lock_token": token, "state": ["done"]},
                {"job_id": job.id, "lock_token": token, "result_status": {"a": 1}},
            ],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 2)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")

    def test_result_text_fields_compound_types_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": job.id, "lock_token": token, "state": "done", "result_message": ["msg"]},
                {"job_id": job.id, "lock_token": token, "state": "done", "agent_log": {"log": "abc"}},
            ],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 2)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")

    def test_token_length_over_limit_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        huge_token = "a" * 300

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": huge_token, "state": "done"}],
        )

        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")

    def test_duplicate_job_ids_in_batch_handled(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": job.id, "lock_token": token, "state": "done"},
                {"job_id": job.id, "lock_token": token, "state": "done"},
            ],
        )

        self.assertEqual(res["accepted"], 2)
        self.assertEqual(job.state, "done")

    def test_batch_reverse_order_normalized(self):
        job1 = self._new_job(name="Job 1")
        job2 = self._new_job(name="Job 2")
        claimed = self.Job.claim_for_box(self.box, limit=2)
        token1 = job1.lock_token
        token2 = job2.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": job2.id, "lock_token": token2, "state": "done"},
                {"job_id": job1.id, "lock_token": token1, "state": "done"},
            ],
        )

        self.assertEqual(res["accepted"], 2)
        self.assertEqual(job1.state, "done")
        self.assertEqual(job2.state, "done")

    def test_finish_from_agent_conserves_token(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        saved_token = claimed.lock_token

        job.finish_from_agent(
            {
                "state": "done",
                "result_status": "success",
                "result_message": "Print OK",
            }
        )

        self.assertEqual(job.state, "done")
        self.assertEqual(job.lock_token, saved_token)
        self.assertFalse(job.claimed_at)
        self.assertFalse(job.lease_expires_at)

    def test_dispatchable_job_without_box_rejected(self):
        with self.assertRaises(exceptions.ValidationError):
            self.Job.create(
                {
                    "name": "Orphan job",
                    "box_id": False,
                    "state": "pending",
                    "job_type": "ticket_print",
                }
            )

    def test_terminal_job_without_box_allowed(self):
        job = self.Job.create(
            {
                "name": "Historical terminal job",
                "box_id": False,
                "state": "done",
                "job_type": "ticket_print",
            }
        )
        self.assertTrue(job.id)
        self.assertEqual(job.state, "done")

    # --- Terminal Idempotency & Validation Tests ---

    def test_terminal_done_result_error_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "error"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "terminal_result_mismatch")

    def test_terminal_error_result_done_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "error", "result_status": "error"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "terminal_result_mismatch")

    def test_terminal_done_unknown_state_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "unknown_state"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")

    def test_terminal_done_missing_state_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")

    def test_terminal_contradictory_states_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "failed", "status": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")

    def test_terminal_done_result_done_accepted(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "done", "result_status": "success"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(len(res["rejected"]), 0)

    def test_terminal_error_result_error_accepted(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.finish_from_agent({"state": "error", "result_status": "error"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "error"}],
        )
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(len(res["rejected"]), 0)

    def test_terminal_cancelled_same_token_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token
        job.write({"state": "cancelled"})

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "terminal_result_mismatch")

    def test_job_id_float_rejected(self):
        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": 1.9, "lock_token": "token", "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")

    def test_job_id_zero_and_negative_rejected(self):
        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": 0, "lock_token": "token", "state": "done"},
                {"job_id": -5, "lock_token": "token", "state": "done"},
            ],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 2)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")

    def test_job_id_over_max_int_rejected(self):
        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": 2147483648, "lock_token": "token", "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")

    def test_job_id_string_digits_accepted(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": str(job.id), "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(job.state, "done")

    def test_job_id_string_float_and_scientific_rejected(self):
        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": "1.5", "lock_token": "token", "state": "done"},
                {"job_id": "1e3", "lock_token": "token", "state": "done"},
            ],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 2)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")

    def test_explicit_booleans_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [
                {"job_id": job.id, "lock_token": True, "state": "done"},
                {"job_id": job.id, "lock_token": token, "state": False},
                {"job_id": job.id, "lock_token": token, "state": "done", "result_status": True},
                {"job_id": job.id, "lock_token": token, "state": "done", "result_message": False},
            ],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 4)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][2]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][3]["reason"], "invalid_item")

    def test_renew_lease_job_id_and_boolean_validations(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.renew_lease_for_box(
            self.box,
            [
                {"job_id": 1.9, "lock_token": token},
                {"job_id": 2147483648, "lock_token": token},
                {"job_id": job.id, "lock_token": True},
            ],
        )
        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 3)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][1]["reason"], "invalid_item")
        self.assertEqual(res["rejected"][2]["reason"], "invalid_item")

    def test_lock_token_boolean_false_returns_invalid_item(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)

        res_results = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": False, "state": "done"}],
        )
        self.assertEqual(res_results["accepted"], 0)
        self.assertEqual(len(res_results["rejected"]), 1)
        self.assertEqual(res_results["rejected"][0]["reason"], "invalid_item")

        res_renew = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": False}],
        )
        self.assertEqual(len(res_renew["accepted"]), 0)
        self.assertEqual(len(res_renew["rejected"]), 1)
        self.assertEqual(res_renew["rejected"][0]["reason"], "invalid_item")

    def test_sql_override_lease_reads_authoritative_postgres_value(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        future_lease = fields.Datetime.now() + timedelta(seconds=1800)
        claimed.write({"lease_expires_at": future_lease})
        self.assertEqual(job.lease_expires_at, future_lease)

        claimed.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '10 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "expired_lease")

    # --- Restored Tests from Codex Requirements ---

    def test_renew_lease_stale_token_after_reclaim_rejected(self):
        job = self._new_job()
        claimed1 = self.Job.claim_for_box(self.box, limit=1)
        old_token = claimed1.lock_token

        claimed1.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '10 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        claimed2 = self.Job.claim_for_box(self.box, limit=1)
        self.assertNotEqual(claimed2.lock_token, old_token)

        res = self.Job.renew_lease_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": old_token}],
        )
        self.assertEqual(len(res["accepted"]), 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")

    def test_result_stale_token_after_reclaim_rejected(self):
        job = self._new_job()
        claimed1 = self.Job.claim_for_box(self.box, limit=1)
        old_token = claimed1.lock_token

        claimed1.flush_recordset(["lease_expires_at"])
        self.env.cr.execute(
            """
            UPDATE community_iot_box_iot_job
               SET lease_expires_at = NOW() - INTERVAL '10 seconds'
             WHERE id = %s
            """,
            [job.id],
        )

        claimed2 = self.Job.claim_for_box(self.box, limit=1)
        self.assertNotEqual(claimed2.lock_token, old_token)

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": old_token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")

    def test_result_unknown_state_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "super_unknown"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "invalid_result_state")
        self.assertEqual(job.state, "processing")

    def test_result_idempotent_no_side_effects(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res1 = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res1["accepted"], 1)
        self.assertEqual(job.state, "done")
        self.assertTrue(self.device.last_test_date)

        marker_date = fields.Datetime.now() - timedelta(hours=1)
        self.device.write({"last_test_date": marker_date})

        res2 = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res2["accepted"], 1)
        self.assertEqual(self.device.last_test_date, marker_date)

    def test_result_retry_clears_lease(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box,
            [{"job_id": job.id, "lock_token": token, "state": "retry"}],
        )
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(job.state, "pending")
        self.assertFalse(job.lock_token)
        self.assertFalse(job.claimed_at)
        self.assertFalse(job.lease_expires_at)

    def test_result_other_box_rejected(self):
        job = self._new_job()
        claimed = self.Job.claim_for_box(self.box, limit=1)
        token = claimed.lock_token

        res = self.Job.apply_results_for_box(
            self.box_b,
            [{"job_id": job.id, "lock_token": token, "state": "done"}],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 1)
        self.assertEqual(res["rejected"][0]["reason"], "stale_lease")
        self.assertEqual(job.state, "processing")

    def test_malformed_items_rejected_safely(self):
        job = self._new_job()
        res = self.Job.apply_results_for_box(
            self.box,
            [
                "string_item",
                123,
                {"job_id": job.id},
                {"job_id": "invalid_id", "lock_token": "abc"},
            ],
        )
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(len(res["rejected"]), 4)
