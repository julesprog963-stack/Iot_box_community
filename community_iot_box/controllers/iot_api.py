import hashlib
import json
import logging
import re
import secrets

from psycopg2 import OperationalError

from odoo import fields, http
from odoo.http import request


_logger = logging.getLogger(__name__)

LEGACY_AGENT_JOB_TYPES = (
    "ticket_print",
    "cash_drawer",
    "open_cashdrawer",
    "label_print",
    "label_print_zpl",
    "test_ticket",
    "test_label",
    "test_drawer",
)
CAPABILITY_JOB_TYPES = {"pdf_print_v1": ("document_print",)}
CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


def _parse_document_lock_token(raw_token):
    if not isinstance(raw_token, str):
        return "invalid", None
    clean = raw_token.strip()
    if not clean or len(clean) > 256:
        return "invalid", None
    return "ok", clean


class CommunityIotApiController(http.Controller):
    def _json_ok(self, data=None, status=200):
        payload = {"success": True}
        if data:
            payload.update(data)
        return request.make_json_response(payload, status=status)

    def _json_error(self, code, message, status=400):
        return request.make_json_response(
            {
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                },
            },
            status=status,
        )

    def _payload(self, kwargs):
        if kwargs:
            return kwargs

        # Odoo can replay the controller after a serialization failure.
        # Werkzeug must cache the body so the replay sees the same JSON.
        raw_data = request.httprequest.get_data(cache=True, as_text=True)
        if not raw_data:
            return {}

        try:
            payload = json.loads(raw_data)
        except Exception:
            return {}

        if isinstance(payload, dict):
            params = payload.get("params")
            if isinstance(params, dict):
                return params
            return payload
        return {}

    def _get_box_from_token(self, token):
        if not token:
            return None
        return (
            request.env["community_iot_box.iot_box"]
            .sudo()
            .search([("token", "=", token), ("active", "=", True)], limit=1)
        )

    def _get_token_and_box(self):
        token = request.httprequest.headers.get("X-IOT-BOX-TOKEN")
        box = self._get_box_from_token(token)
        if not box:
            return token, None, self._json_error(
                "IOT_INVALID_TOKEN",
                "The provided IoT Box token is invalid or not active.",
                status=401,
            )
        return token, box, None

    def _normalize_capabilities(self, raw_capabilities):
        if not isinstance(raw_capabilities, list) or len(raw_capabilities) > 32:
            return []
        capabilities = []
        for item in raw_capabilities:
            if not isinstance(item, str):
                continue
            clean = item.strip().lower()
            if CAPABILITY_RE.fullmatch(clean) and clean not in capabilities:
                capabilities.append(clean)
        return sorted(capabilities)

    def _box_capabilities(self, box):
        try:
            capabilities = json.loads(box.agent_capabilities or "[]")
        except (TypeError, ValueError):
            return []
        return self._normalize_capabilities(capabilities)

    def _supported_job_types(self, box):
        supported = list(LEGACY_AGENT_JOB_TYPES)
        for capability in self._box_capabilities(box):
            supported.extend(CAPABILITY_JOB_TYPES.get(capability, ()))
        return supported

    def _build_devices_config(self, box):
        devices = []
        for device in box.device_ids.filtered("active"):
            connection = {
                "host": device.connection_host,
                "ip_address": device.connection_host,
                "port": device.connection_port,
                "device": device.connection_device,
                "serial_device_path": device.connection_device,
                "serial_baudrate": device.serial_baudrate,
                "cups_printer_name": device.cups_printer_name,
                "usb_vendor_id": device.usb_vendor_id,
                "usb_product_id": device.usb_product_id,
                "usb_interface": device.usb_interface,
                "usb_in_ep": device.usb_in_ep,
                "usb_out_ep": device.usb_out_ep,
            }
            devices.append(
                {
                    "device_key": device.device_key,
                    "type": device.type,
                    "backend": device.backend,
                    "interface": device.interface,
                    "connection_type": device.interface,
                    "host": device.connection_host,
                    "ip_address": device.connection_host,
                    "port": device.connection_port,
                    "device_path": device.connection_device,
                    "serial_device_path": device.connection_device,
                    "serial_baudrate": device.serial_baudrate,
                    "cups_printer_name": device.cups_printer_name,
                    "usb_vendor_id": device.usb_vendor_id,
                    "usb_product_id": device.usb_product_id,
                    "usb_interface": device.usb_interface,
                    "usb_in_ep": device.usb_in_ep,
                    "usb_out_ep": device.usb_out_ep,
                    "ticket_mode": device.ticket_mode,
                    "printer_width_px": device._get_ticket_image_width_px(),
                    "name": device.name,
                    "auto_detected": device.auto_detected,
                    "last_discovered_at": (
                        fields.Datetime.to_string(device.last_discovered_at)
                        if device.last_discovered_at
                        else False
                    ),
                    "connection": connection,
                }
            )
        return devices

    def _normalize_detected_device(self, payload):
        if not isinstance(payload, dict):
            return None

        name = (payload.get("name") or payload.get("device_key") or "").strip()
        if not name:
            return None

        device_type = (payload.get("device_type") or "standard_printer").strip()
        if device_type not in {"ticket_printer", "standard_printer", "label_printer", "drawer", "other"}:
            device_type = "standard_printer"

        backend = (payload.get("backend") or "standard").strip()
        if backend not in {"escpos", "zpl", "standard", "cups", "cups_generic", "other"}:
            backend = "standard"

        interface = (payload.get("interface") or payload.get("connection_type") or "other").strip()
        if interface not in {"usb", "network", "serial", "cups", "other"}:
            interface = "other"

        auto_identifier = (payload.get("auto_identifier") or "").strip()
        if not auto_identifier:
            auto_identifier = f"{interface}:{name}"

        device_key = (payload.get("device_key") or "").strip()
        if not device_key:
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "device"
            device_key = f"auto_{slug[:45]}"

        ticket_mode = (payload.get("ticket_mode") or "standard").strip()
        if ticket_mode not in {"narrow", "wide", "standard"}:
            ticket_mode = "standard"

        return {
            "name": name,
            "device_key": device_key,
            "type": device_type,
            "backend": backend,
            "interface": interface,
            "connection_host": payload.get("connection_host") or payload.get("host"),
            "connection_port": payload.get("connection_port") or payload.get("port"),
            "connection_device": payload.get("connection_device") or payload.get("device_path"),
            "cups_printer_name": payload.get("cups_printer_name"),
            "serial_baudrate": payload.get("serial_baudrate"),
            "usb_vendor_id": payload.get("usb_vendor_id"),
            "usb_product_id": payload.get("usb_product_id"),
            "usb_interface": payload.get("usb_interface"),
            "ticket_mode": ticket_mode,
            "auto_identifier": auto_identifier,
            "discovery_source": payload.get("discovery_source"),
            "discovery_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        }

    def _find_existing_detected_device(self, box, normalized):
        Device = request.env["community_iot_box.iot_device"].sudo()
        box_domain = [("box_id", "=", box.id)]

        auto_identifier = normalized.get("auto_identifier")
        if auto_identifier:
            record = Device.search(box_domain + [("auto_identifier", "=", auto_identifier)], limit=1)
            if record:
                return record

        cups_name = normalized.get("cups_printer_name")
        if cups_name:
            record = Device.search(box_domain + [("cups_printer_name", "=", cups_name)], limit=1)
            if record:
                return record

        connection_device = normalized.get("connection_device")
        if connection_device:
            record = Device.search(box_domain + [("connection_device", "=", connection_device)], limit=1)
            if record:
                return record

        device_key = normalized.get("device_key")
        if device_key:
            record = Device.search(box_domain + [("device_key", "=", device_key)], limit=1)
            if record:
                return record

        return Device.browse()

    def _prepare_detected_device_vals(self, normalized, record=None):
        vals = {
            "active": True,
            "auto_detected": True,
            "auto_identifier": normalized.get("auto_identifier"),
            "discovery_source": normalized.get("discovery_source"),
            "last_discovered_at": fields.Datetime.now(),
            "discovery_payload": normalized.get("discovery_payload"),
        }

        if not record or record.auto_detected or not record.name:
            vals["name"] = normalized["name"]

        config_vals = {
            "device_key": normalized.get("device_key"),
            "type": normalized.get("type"),
            "backend": normalized.get("backend"),
            "interface": normalized.get("interface"),
            "connection_host": normalized.get("connection_host"),
            "connection_port": normalized.get("connection_port"),
            "connection_device": normalized.get("connection_device"),
            "cups_printer_name": normalized.get("cups_printer_name"),
            "serial_baudrate": normalized.get("serial_baudrate"),
            "usb_vendor_id": normalized.get("usb_vendor_id"),
            "usb_product_id": normalized.get("usb_product_id"),
            "usb_interface": normalized.get("usb_interface"),
            "ticket_mode": normalized.get("ticket_mode"),
        }

        if record and not record.auto_detected:
            for field_name, value in config_vals.items():
                if value in (None, False, ""):
                    continue
                if not record[field_name]:
                    vals[field_name] = value
            return vals

        for field_name, value in config_vals.items():
            if value in (None, False, ""):
                continue
            vals[field_name] = value
        return vals

    def _config_vals_changed(self, record, vals):
        if not record:
            return True
        config_fields = request.env["community_iot_box.iot_device"]._CONFIG_VERSION_FIELDS
        for field_name in config_fields:
            if field_name not in vals:
                continue
            if record[field_name] != vals[field_name]:
                return True
        return False

    @http.route(
        "/iot/api/v1/register",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_register(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            vals = {"state": "online", "last_seen": fields.Datetime.now()}
            for field_name in (
                "box_uid",
                "hostname",
                "agent_version",
                "ip_address",
                "mac_address",
            ):
                if payload.get(field_name) is not None:
                    vals[field_name] = payload.get(field_name)
            vals["agent_capabilities"] = json.dumps(
                self._normalize_capabilities(payload.get("capabilities")),
                separators=(",", ":"),
            )
            box.write(vals)

            return self._json_ok(
                {
                    "box": {
                        "id": box.id,
                        "name": box.name,
                        "company_id": box.company_id.id,
                        "config_version": box.config_version,
                    },
                    "config": {
                        "devices": self._build_devices_config(box),
                    },
                }
            )
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT register endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while registering IoT Box.",
                status=500,
            )
    @http.route(
        "/iot/api/v1/heartbeat",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_heartbeat(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            vals = {"last_seen": fields.Datetime.now()}

            if payload.get("agent_version") is not None:
                vals["agent_version"] = payload.get("agent_version")
            if payload.get("ip_address") is not None:
                vals["ip_address"] = payload.get("ip_address")
            if "capabilities" in payload:
                vals["agent_capabilities"] = json.dumps(
                    self._normalize_capabilities(payload.get("capabilities")),
                    separators=(",", ":"),
                )

            status = payload.get("status")
            if status == "ok":
                vals["state"] = "online"
            elif status == "error":
                vals["state"] = "error"

            box.write(vals)

            return self._json_ok(
                {
                    "box": {
                        "id": box.id,
                        "state": box.state,
                        "config_version": box.config_version,
                    }
                }
            )
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT heartbeat endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while processing heartbeat.",
                status=500,
            )

    @http.route(
        "/iot/api/v1/jobs/poll",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_jobs_poll(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            max_jobs = payload.get("max_jobs", 5)
            try:
                max_jobs = int(max_jobs)
            except Exception:
                max_jobs = 5
            if max_jobs <= 0:
                max_jobs = 5
            if max_jobs > 100:
                max_jobs = 100

            jobs = request.env["community_iot_box.iot_job"].sudo().claim_for_box(
                box,
                limit=max_jobs,
                lease_seconds=900,
                supported_job_types=self._supported_job_types(box),
            )

            data_jobs = []
            for job in jobs:
                job_data = {
                        "job_id": job.id,
                        "job_type": job.job_type,
                        "device_key": job.device_key,
                        "payload": job.payload,
                        "lock_token": job.lock_token,
                        "attempt": job.attempt_count,
                        "lease_expires_at": (
                            fields.Datetime.to_string(job.lease_expires_at)
                            if job.lease_expires_at
                            else False
                        ),
                        "created_at": (
                            fields.Datetime.to_string(job.create_date)
                            if job.create_date
                            else False
                        ),
                    }
                if job.job_type == "document_print" and job.document_attachment_id:
                    job_data["document"] = {
                        "download_path": f"/iot/api/v1/jobs/{job.id}/document",
                        "filename": job.document_filename,
                        "mimetype": job.document_mimetype,
                        "size": job.document_size,
                        "sha256": job.document_sha256,
                    }
                data_jobs.append(job_data)

            return self._json_ok({"jobs": data_jobs})
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT jobs/poll endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while polling jobs.",
                status=500,
            )

    @http.route(
        "/iot/api/v1/jobs/<int:job_id>/document",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def api_job_document(self, job_id, **_kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            token_status, lock_token = _parse_document_lock_token(
                request.httprequest.headers.get("X-IOT-JOB-LOCK-TOKEN")
            )
            if token_status != "ok":
                return self._json_error(
                    "IOT_INVALID_JOB_LOCK",
                    "A valid job lock token is required.",
                    status=403,
                )

            job = request.env["community_iot_box.iot_job"].sudo().browse(job_id).exists()
            now = fields.Datetime.now()
            authorized = bool(
                job
                and job.box_id == box
                and job.job_type == "document_print"
                and job.state == "processing"
                and job.lock_token
                and secrets.compare_digest(job.lock_token, lock_token)
                and job.lease_expires_at
                and job.lease_expires_at > now
                and job.document_attachment_id
            )
            if not authorized:
                return self._json_error(
                    "IOT_DOCUMENT_NOT_AVAILABLE",
                    "The requested document is not available for this lease.",
                    status=404,
                )

            attachment = job.document_attachment_id.sudo()
            content = attachment.raw or b""
            if (
                job.document_mimetype != "application/pdf"
                or not content.startswith(b"%PDF-")
                or len(content) != job.document_size
                or not secrets.compare_digest(
                    hashlib.sha256(content).hexdigest(), job.document_sha256 or ""
                )
            ):
                return self._json_error(
                    "IOT_DOCUMENT_INVALID",
                    "The stored PDF failed validation.",
                    status=409,
                )

            filename = re.sub(r"[^A-Za-z0-9._-]", "_", job.document_filename or "document.pdf")
            return request.make_response(
                content,
                headers=[
                    ("Content-Type", "application/pdf"),
                    ("Content-Length", str(len(content))),
                    ("Content-Disposition", f'attachment; filename="{filename}"'),
                    ("Cache-Control", "no-store, private"),
                    ("X-Content-Type-Options", "nosniff"),
                ],
            )
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT document download endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while downloading the document.",
                status=500,
            )
    @http.route(
        "/iot/api/v1/jobs/lease/renew",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_jobs_lease_renew(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            leases = payload.get("leases")
            if not isinstance(leases, list):
                return self._json_error(
                    "IOT_INVALID_PAYLOAD",
                    "Field 'leases' must be a list.",
                    status=400,
                )
            if len(leases) > 100:
                return self._json_error(
                    "IOT_INVALID_PAYLOAD",
                    "Batch size exceeds maximum limit of 100 items.",
                    status=400,
                )

            res = request.env["community_iot_box.iot_job"].sudo().renew_lease_for_box(
                box, leases, default_lease_seconds=900
            )
            return self._json_ok(res)
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT jobs/lease/renew endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while renewing job leases.",
                status=500,
            )

    @http.route(
        "/iot/api/v1/jobs/result",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_jobs_result(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            results = payload.get("results")
            if not isinstance(results, list):
                return self._json_error(
                    "IOT_INVALID_PAYLOAD",
                    "Field 'results' must be a list.",
                    status=400,
                )
            if len(results) > 100:
                return self._json_error(
                    "IOT_INVALID_PAYLOAD",
                    "Batch size exceeds maximum limit of 100 items.",
                    status=400,
                )

            res = request.env["community_iot_box.iot_job"].sudo().apply_results_for_box(
                box, results
            )
            return self._json_ok(res)
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT jobs/result endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while processing job results.",
                status=500,
            )

    @http.route(
        "/iot/api/v1/config",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_config(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            return self._json_ok(
                {
                    "config_version": box.config_version,
                    "devices": self._build_devices_config(box),
                }
            )
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT config endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while fetching config.",
                status=500,
            )

    @http.route(
        "/iot/api/v1/devices/sync",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def api_devices_sync(self, **kwargs):
        try:
            _token, box, error = self._get_token_and_box()
            if error:
                return error

            payload = self._payload(kwargs)
            devices = payload.get("devices")
            if not isinstance(devices, list):
                return self._json_error(
                    "IOT_INVALID_PAYLOAD",
                    "Field 'devices' must be a list.",
                    status=400,
                )

            replace_auto_detected = payload.get("replace_auto_detected", True)
            Device = request.env["community_iot_box.iot_device"].sudo()
            # Serialize discovery for one box. Concurrent retry requests must
            # not both search before either creates the same device.
            request.env.cr.execute(
                "SELECT id FROM community_iot_box_iot_box WHERE id = %s FOR UPDATE",
                [box.id],
            )
            seen_identifiers = set()
            changed = False
            created_count = 0
            updated_count = 0
            deactivated_count = 0

            for item in devices:
                normalized = self._normalize_detected_device(item)
                if not normalized:
                    continue

                seen_identifiers.add(normalized["auto_identifier"])
                record = self._find_existing_detected_device(box, normalized)
                vals = self._prepare_detected_device_vals(normalized, record=record)

                if record:
                    changed = self._config_vals_changed(record, vals) or changed
                    record.with_context(skip_config_version_bump=True).write(vals)
                    updated_count += 1
                else:
                    vals["box_id"] = box.id
                    Device.with_context(skip_config_version_bump=True).create(vals)
                    changed = True
                    created_count += 1

            if replace_auto_detected:
                stale_devices = Device.search(
                    [
                        ("box_id", "=", box.id),
                        ("auto_detected", "=", True),
                        ("auto_identifier", "!=", False),
                        ("auto_identifier", "not in", list(seen_identifiers) or ["__none__"]),
                        ("active", "=", True),
                    ]
                )
                if stale_devices:
                    stale_devices.with_context(skip_config_version_bump=True).write({"active": False})
                    changed = True
                    deactivated_count = len(stale_devices)

            if changed:
                box._increment_config_version()

            return self._json_ok(
                {
                    "config_version": box.config_version,
                    "devices": self._build_devices_config(box),
                    "summary": {
                        "created": created_count,
                        "updated": updated_count,
                        "deactivated": deactivated_count,
                    },
                }
            )
        except OperationalError:
            raise
        except Exception:
            _logger.exception("IOT devices/sync endpoint failed")
            return self._json_error(
                "IOT_INTERNAL_ERROR",
                "Internal server error while synchronizing devices.",
                status=500,
            )
