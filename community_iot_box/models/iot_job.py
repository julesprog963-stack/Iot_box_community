import logging
import secrets
from datetime import timedelta

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)

MAX_POSTGRES_INT = 2147483647


def _parse_strict_job_id(raw_job_id):
    if raw_job_id is None or isinstance(raw_job_id, bool):
        return None
    if isinstance(raw_job_id, int):
        val = raw_job_id
    elif isinstance(raw_job_id, str):
        s = raw_job_id.strip()
        if not s.isascii() or not s.isdigit():
            return None
        try:
            val = int(s)
        except ValueError:
            return None
    else:
        return None

    if 1 <= val <= MAX_POSTGRES_INT:
        return val
    return None


def _is_valid_optional_str(val):
    if val is None:
        return True
    if isinstance(val, bool):
        return False
    return isinstance(val, str)


def _parse_lock_token(raw_token):
    if isinstance(raw_token, bool):
        return "invalid", None
    if raw_token is None:
        return "missing", None
    if not isinstance(raw_token, str):
        return "invalid", None
    token_str = raw_token.strip()
    if not token_str:
        return "missing", None
    if len(token_str) > 256:
        return "invalid", None
    return "ok", token_str


def _parse_and_validate_state_status(raw_state, raw_status):
    if not _is_valid_optional_str(raw_state) or not _is_valid_optional_str(raw_status):
        return "invalid_item", None

    state_cat = None
    if isinstance(raw_state, str):
        s_clean = raw_state.strip().lower()
        if s_clean in ("done", "success"):
            state_cat = "done"
        elif s_clean in ("failed", "error"):
            state_cat = "error"
        elif s_clean in ("retry", "pending"):
            state_cat = "pending"
        else:
            return "invalid_result_state", None

    status_cat = None
    if isinstance(raw_status, str):
        st_clean = raw_status.strip().lower()
        if st_clean == "done":
            status_cat = "done"
        elif st_clean in ("failed", "error"):
            status_cat = "error"
        elif st_clean == "retry":
            status_cat = "pending"
        else:
            return "invalid_result_state", None

    if state_cat and status_cat and state_cat != status_cat:
        return "invalid_result_state", None

    final_state = state_cat or status_cat
    if not final_state:
        return "invalid_result_state", None

    return "ok", final_state


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
        help="Internal job status (pending/processing/done/error/cancelled).",
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
        help="Logical identifier of this job's target device.",
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
        help="Technical name of the source model (for example 'pos.order', 'stock.picking').",
    )
    origin_id = fields.Integer(
        string="Origin Record ID",
        help="ID del registro origen relacionado con este job.",
    )
    processed_at = fields.Datetime(
        string="Processed At",
        help="Date and time when the job ended (success or error).",
    )
    claimed_at = fields.Datetime(
        string="Claimed At",
        readonly=True,
        index=True,
        help="Date when an agent claimed the job for processing.",
    )
    lease_expires_at = fields.Datetime(
        string="Lease Expires At",
        readonly=True,
        index=True,
        help="Vencimiento del arrendamiento. Un trabajo sin resultado vuelve a la cola.",
    )
    lock_token = fields.Char(
        string="Lock Token",
        readonly=True,
        copy=False,
        index=True,
        help="Ephemeral token that links the result to the current claim.",
    )
    attempt_count = fields.Integer(
        string="Attempts",
        default=0,
        readonly=True,
        copy=False,
    )

    def init(self):
        super().init()
        # Create stable indexes for queue polling and active lease lookups
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS community_iot_job_pending_box_idx
                      ON community_iot_box_iot_job (box_id, create_date ASC, id ASC)
                   WHERE state = 'pending';
            """
        )
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS community_iot_job_processing_lease_idx
                      ON community_iot_box_iot_job (box_id, lease_expires_at)
                   WHERE state = 'processing';
            """
        )

    @api.constrains("box_id", "state")
    def _check_dispatchable_has_box(self):
        for job in self:
            if job.state in ("pending", "processing") and not job.box_id:
                raise exceptions.ValidationError(
                    _("A job in state '%s' must be assigned to an IoT Box.") % job.state
                )

    @api.model
    def claim_for_box(self, box, limit=5, lease_seconds=900):
        """Atomically claim pending jobs and recover abandoned leases using CTE."""
        box.ensure_one()
        limit = min(max(int(limit or 5), 1), 100)
        lease_seconds = min(max(int(lease_seconds or 900), 30), 3600)
        self.flush_model(
            [
                "box_id",
                "state",
                "claimed_at",
                "lease_expires_at",
                "lock_token",
                "attempt_count",
            ]
        )

        # Non-blocking CTE recovery for expired/legacy processing rows
        self.env.cr.execute(
            """
                WITH expired_jobs AS (
                    SELECT id
                      FROM community_iot_box_iot_job
                     WHERE box_id = %s
                       AND state = 'processing'
                       AND (
                           lease_expires_at < NOW()
                           OR (
                               lease_expires_at IS NULL
                               AND write_date < NOW() - (%s * INTERVAL '1 second')
                           )
                       )
                     ORDER BY id
                     FOR UPDATE SKIP LOCKED
                )
                UPDATE community_iot_box_iot_job AS job
                   SET state = 'pending',
                       claimed_at = NULL,
                       lease_expires_at = NULL,
                       lock_token = NULL,
                       write_date = NOW()
                  FROM expired_jobs
                 WHERE job.id = expired_jobs.id
             RETURNING job.id
            """,
            [box.id, lease_seconds],
        )
        recovered_ids = [row[0] for row in self.env.cr.fetchall()]
        if recovered_ids:
            self.browse(recovered_ids).invalidate_recordset(
                ["state", "claimed_at", "lease_expires_at", "lock_token", "write_date"],
                flush=False,
            )

        # Locks are held until the surrounding Odoo HTTP transaction commits.
        self.env.cr.execute(
            """
                SELECT id
                  FROM community_iot_box_iot_job
                 WHERE box_id = %s
                   AND state = 'pending'
                 ORDER BY create_date ASC, id ASC
                 FOR UPDATE SKIP LOCKED
                 LIMIT %s
            """,
            [box.id, limit],
        )
        jobs = self.browse([row[0] for row in self.env.cr.fetchall()])
        if not jobs:
            return jobs

        claimed_at = fields.Datetime.now()
        lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)
        for job in jobs:
            job.write(
                {
                    "state": "processing",
                    "claimed_at": claimed_at,
                    "lease_expires_at": lease_expires_at,
                    "lock_token": secrets.token_urlsafe(24),
                    "attempt_count": job.attempt_count + 1,
                }
            )
        return jobs

    @api.model
    def renew_lease_for_box(self, box, leases, default_lease_seconds=900):
        box.ensure_one()
        if not isinstance(leases, list):
            return {"accepted": [], "rejected": []}

        self.flush_model(
            ["box_id", "state", "claimed_at", "lease_expires_at", "lock_token"]
        )

        default_lease_seconds = min(max(int(default_lease_seconds or 900), 30), 3600)
        parsed_valid = []
        rejected_items = []

        for idx, lease in enumerate(leases):
            if not isinstance(lease, dict):
                rejected_items.append((idx, {"job_id": False, "reason": "invalid_item"}))
                continue

            job_id = _parse_strict_job_id(lease.get("job_id"))
            if not job_id:
                rejected_items.append((idx, {"job_id": False, "reason": "invalid_item"}))
                continue

            token_res, token_str = _parse_lock_token(lease.get("lock_token"))
            if token_res == "missing":
                rejected_items.append((idx, {"job_id": job_id, "reason": "missing_lock_token"}))
                continue
            if token_res == "invalid":
                rejected_items.append((idx, {"job_id": job_id, "reason": "invalid_item"}))
                continue

            parsed_valid.append((job_id, idx, token_str))

        # Sort valid items deterministically by job_id ASC, idx ASC to prevent deadlocks across batches
        parsed_valid.sort(key=lambda x: (x[0], x[1]))

        accepted_items = []

        for job_id, idx, token_str in parsed_valid:
            # Acquire row lock before validating state or token
            self.env.cr.execute(
                """
                SELECT id
                  FROM community_iot_box_iot_job
                 WHERE id = %s AND box_id = %s
                FOR UPDATE
                """,
                [job_id, box.id],
            )
            row = self.env.cr.fetchone()
            if not row:
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            job = self.browse(job_id)
            job.invalidate_recordset(
                ["state", "lock_token", "lease_expires_at", "box_id"],
                flush=False,
            )

            now = fields.Datetime.now()

            if job.box_id != box or job.state != "processing":
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            if not job.lock_token or not secrets.compare_digest(job.lock_token, token_str):
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            if not job.lease_expires_at or job.lease_expires_at <= now:
                rejected_items.append((idx, {"job_id": job_id, "reason": "expired_lease"}))
                continue

            new_lease_expires_at = now + timedelta(seconds=default_lease_seconds)
            job.write({"lease_expires_at": new_lease_expires_at})
            accepted_items.append(
                (
                    idx,
                    {
                        "job_id": job.id,
                        "lease_expires_at": fields.Datetime.to_string(new_lease_expires_at),
                    },
                )
            )

        # Restore original request ordering
        accepted_items.sort(key=lambda x: x[0])
        rejected_items.sort(key=lambda x: x[0])

        accepted = [item[1] for item in accepted_items]
        rejected = [item[1] for item in rejected_items]

        return {"accepted": accepted, "rejected": rejected}

    @api.model
    def apply_results_for_box(self, box, results):
        box.ensure_one()
        if not isinstance(results, list):
            return {"accepted": 0, "rejected": []}

        self.flush_model(
            [
                "box_id",
                "state",
                "claimed_at",
                "lease_expires_at",
                "lock_token",
                "result_status",
                "device_id",
                "job_type",
            ]
        )

        parsed_valid = []
        rejected_items = []

        for idx, result in enumerate(results):
            if not isinstance(result, dict):
                rejected_items.append((idx, {"job_id": False, "reason": "invalid_item"}))
                continue

            job_id = _parse_strict_job_id(result.get("job_id"))
            if not job_id:
                rejected_items.append((idx, {"job_id": False, "reason": "invalid_item"}))
                continue

            token_res, token_str = _parse_lock_token(result.get("lock_token"))
            if token_res == "missing":
                rejected_items.append((idx, {"job_id": job_id, "reason": "missing_lock_token"}))
                continue
            if token_res == "invalid":
                rejected_items.append((idx, {"job_id": job_id, "reason": "invalid_item"}))
                continue

            # Strict type check on optional text fields
            invalid_type = False
            for field_name in ("result_message", "error_message", "agent_log", "error_code"):
                if field_name in result and not _is_valid_optional_str(result[field_name]):
                    invalid_type = True
                    break
            if invalid_type:
                rejected_items.append((idx, {"job_id": job_id, "reason": "invalid_item"}))
                continue

            if "result_status" in result and not _is_valid_optional_str(result["result_status"]):
                rejected_items.append((idx, {"job_id": job_id, "reason": "invalid_item"}))
                continue

            state_res, final_state = _parse_and_validate_state_status(
                result.get("state"), result.get("status")
            )
            if state_res != "ok":
                rejected_items.append((idx, {"job_id": job_id, "reason": state_res}))
                continue

            parsed_valid.append((job_id, idx, token_str, final_state, result))

        # Sort valid items deterministically by job_id ASC, idx ASC to prevent deadlocks across batches
        parsed_valid.sort(key=lambda x: (x[0], x[1]))

        accepted_count = 0

        for job_id, idx, token_str, final_state, result in parsed_valid:
            # Acquire row lock before reading state/token
            self.env.cr.execute(
                """
                SELECT id
                  FROM community_iot_box_iot_job
                 WHERE id = %s AND box_id = %s
                FOR UPDATE
                """,
                [job_id, box.id],
            )
            row = self.env.cr.fetchone()
            if not row:
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            job = self.browse(job_id)
            job.invalidate_recordset(
                [
                    "state",
                    "lock_token",
                    "lease_expires_at",
                    "claimed_at",
                    "result_status",
                    "box_id",
                    "device_id",
                    "job_type",
                ],
                flush=False,
            )

            now = fields.Datetime.now()

            if job.box_id != box:
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            # Handle terminal job re-submissions idempotently before lease expiry checks
            if job.state in ("done", "error", "cancelled"):
                if not job.lock_token or not secrets.compare_digest(job.lock_token, token_str):
                    rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                    continue

                if job.state == "done":
                    if final_state == "done":
                        accepted_count += 1
                    else:
                        rejected_items.append((idx, {"job_id": job_id, "reason": "terminal_result_mismatch"}))
                elif job.state == "error":
                    if final_state == "error":
                        accepted_count += 1
                    else:
                        rejected_items.append((idx, {"job_id": job_id, "reason": "terminal_result_mismatch"}))
                elif job.state == "cancelled":
                    rejected_items.append((idx, {"job_id": job_id, "reason": "terminal_result_mismatch"}))
                continue

            if job.state != "processing":
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            if not job.lock_token or not secrets.compare_digest(job.lock_token, token_str):
                rejected_items.append((idx, {"job_id": job_id, "reason": "stale_lease"}))
                continue

            if not job.lease_expires_at or job.lease_expires_at <= now:
                rejected_items.append((idx, {"job_id": job_id, "reason": "expired_lease"}))
                continue

            raw_result_status = result.get("result_status")
            if (
                not isinstance(raw_result_status, str)
                or raw_result_status not in {"none", "success", "warning", "error"}
            ):
                result_status = "success" if final_state == "done" else "error"
            else:
                result_status = raw_result_status

            result_message = result.get("result_message") or result.get("error_message")
            agent_log = result.get("agent_log")
            error_code = result.get("error_code")
            error_message = result.get("error_message")

            if final_state == "done":
                job.finish_from_agent(
                    {
                        "state": "done",
                        "result_status": result_status or "success",
                        "result_message": result_message,
                        "agent_log": agent_log,
                        "processed_at": now,
                        "error_code": False,
                        "error_message": False,
                    }
                )
                if job.job_type.startswith("test_") and job.device_id:
                    job.device_id.sudo().write(
                        {
                            "last_test_status": "success",
                            "last_test_date": now,
                        }
                    )
            elif final_state == "error":
                job.finish_from_agent(
                    {
                        "state": "error",
                        "result_status": result_status or "error",
                        "result_message": result_message,
                        "agent_log": agent_log,
                        "error_code": error_code,
                        "error_message": error_message or result_message,
                        "processed_at": now,
                    }
                )
                if job.job_type.startswith("test_") and job.device_id:
                    job.device_id.sudo().write(
                        {
                            "last_test_status": "failed",
                            "last_test_date": now,
                        }
                    )
            elif final_state == "pending":
                job.release_for_retry()

            accepted_count += 1

        rejected_items.sort(key=lambda x: x[0])
        rejected = [item[1] for item in rejected_items]

        return {"accepted": accepted_count, "rejected": rejected}

    def release_for_retry(self):
        self.write(
            {
                "state": "pending",
                "result_status": "none",
                "result_message": False,
                "agent_log": False,
                "claimed_at": False,
                "lease_expires_at": False,
                "lock_token": False,
            }
        )

    def finish_from_agent(self, values):
        self.ensure_one()
        values = dict(values)
        values.update(
            {
                "claimed_at": False,
                "lease_expires_at": False,
            }
        )
        self.write(values)
