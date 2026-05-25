from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
import logging
import mimetypes
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db import session as db_session
from filament_manager.db.models import (
    AmsSlot,
    AmsUnit,
    DeviceMetricSample,
    DeviceStatusSnapshot,
    NotificationRule,
    NotificationTarget,
    Printer,
    PrinterStorageFile,
    PrinterStateSnapshot,
    PrintLogEntry,
    RawMqttMessage,
    _slot_state_name,
)
from filament_manager.mqtt.client import is_certificate_verify_error, mqtt_manager
from filament_manager.schemas import (
    AmsSlotRead,
    AmsUnitRead,
    DeviceMetricSampleRead,
    DeviceStatusSnapshotRead,
    NotificationTargetRead,
    PrinterStateRead,
    PrintLogEntryRead,
)
from filament_manager.services.fans import fan_percent, normalize_fan_payload
from filament_manager.services.notifications import redact_notification_config
from filament_manager.services.printers import get_printer


def metric_group_prefix(group: str | None) -> str | None:
    if group == "temperature":
        return "temperature.%"
    if group == "fan":
        return "fan.%"
    if group == "wifi":
        return "network.wifi_signal"
    if group == "ams":
        return "ams.%"
    if group == "print":
        return "print.%"
    if group == "coverage":
        return "coverage.%"
    return None


def bucket_metric_samples(rows: list[DeviceMetricSample], bucket: str) -> list[DeviceMetricSampleRead]:
    buckets: dict[tuple[str, datetime], list[DeviceMetricSample]] = {}
    for row in rows:
        key = (canonical_metric_name(row.metric), bucket_start(row.sampled_at, bucket))
        buckets.setdefault(key, []).append(row)
    aggregated: list[DeviceMetricSampleRead] = []
    for (metric, sampled_at), samples in sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0])):
        numeric_values = [metric_value_float(sample) for sample in samples if metric_value_float(sample) is not None]
        latest = max(samples, key=lambda sample: (sample.sampled_at, sample.id))
        value_float = sum(numeric_values) / len(numeric_values) if numeric_values else None
        aggregated.append(
            DeviceMetricSampleRead(
                id=0,
                printer_id=latest.printer_id,
                metric=metric,
                value_float=value_float,
                value_text=str(round(value_float, 3)) if value_float is not None else latest.value_text,
                unit=latest.unit,
                raw_message_id=latest.raw_message_id,
                details={**(latest.details or {}), "bucket": bucket, "sample_count": len(samples)},
                sampled_at=sampled_at,
            )
        )
    return aggregated


def bucket_start(value: datetime, bucket: str) -> datetime:
    if bucket == "minute":
        return value.replace(second=0, microsecond=0)
    if bucket == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value


def metric_sample_read(row: DeviceMetricSample) -> DeviceMetricSampleRead:
    read = DeviceMetricSampleRead.model_validate(row)
    value_float = metric_value_float(row)
    metric = canonical_metric_name(row.metric)
    if value_float == row.value_float and metric == row.metric:
        return read
    return read.model_copy(
        update={
            "metric": metric,
            "value_float": value_float,
            "value_text": str(value_float) if value_float is not None else None,
        }
    )

LOGGER = logging.getLogger(__name__)


def canonical_metric_name(metric: str) -> str:
    mapping = {
        "temperature.hotend_a": "temperature.right_hotend",
        "temperature.hotend_a_target": "temperature.right_hotend_target",
        "temperature.hotend_b": "temperature.left_hotend",
        "temperature.hotend_b_target": "temperature.left_hotend_target",
    }
    return mapping.get(metric, metric)


def metric_value_float(row: DeviceMetricSample) -> float | None:
    value = row.value_float
    if not row.metric.startswith("fan.") or not row.metric.endswith(".percent"):
        return value
    if value is not None and 0 <= value <= 100:
        return value
    details = row.details if isinstance(row.details, dict) else {}
    normalized = fan_percent(details.get("raw"))
    if normalized is not None:
        return float(normalized)
    if value is None:
        return None
    return float(max(0, min(100, value)))


def print_log_read(row: PrintLogEntry) -> PrintLogEntryRead:
    read = PrintLogEntryRead.model_validate(row)
    return read.model_copy(
        update={
            "filament_summary": redact_sensitive(read.filament_summary),
            "hms_summary": redact_sensitive(read.hms_summary),
            "raw_refs": redact_sensitive(read.raw_refs),
        }
    )


def state_read(snapshot: PrinterStateSnapshot | None) -> PrinterStateRead | None:
    if snapshot is None:
        return None
    read = PrinterStateRead.model_validate(snapshot)
    return read.model_copy(update={"payload": redact_sensitive(read.payload)})


def device_snapshot_read(snapshot: DeviceStatusSnapshot | None) -> DeviceStatusSnapshotRead | None:
    if snapshot is None:
        return None
    read = DeviceStatusSnapshotRead.model_validate(snapshot)
    redacted = {
        key: redact_sensitive(getattr(read, key))
        for key in (
            "print_status",
            "derived_status",
            "temperatures",
            "fans",
            "network",
            "hardware",
            "nozzles",
            "storage",
            "camera",
            "camera_options",
            "lights",
            "speed",
            "calibration",
            "ams_status",
            "hms_errors",
            "firmware",
            "accessories",
            "external_slots",
            "unsupported_features",
            "data_coverage",
            "raw_refs",
        )
    }
    redacted["fans"] = normalize_fan_payload(redacted["fans"])
    redacted["camera"] = sanitize_camera_response(redacted["camera"])
    redacted["camera_options"] = sanitize_camera_response(redacted["camera_options"])
    return read.model_copy(update=redacted)


def ams_unit_read(unit: AmsUnit) -> AmsUnitRead:
    read = AmsUnitRead.model_validate(unit)
    return read.model_copy(update={"raw": redact_sensitive(read.raw)})


def ams_slot_read(slot: AmsSlot) -> AmsSlotRead:
    read = AmsSlotRead.model_validate(slot)
    user_tray_id = slot_user_tray_id(slot)
    slot_label = f"Slot {user_tray_id}" if user_tray_id is not None else f"Slot {slot.tray_id}"
    context = filament_context_from_slot(slot)
    return read.model_copy(
        update={
            "raw": redact_sensitive(read.raw),
            "state_name": ams_slot_state_name(slot),
            "user_tray_id": user_tray_id,
            "slot_label": slot_label,
            "global_tray_id": slot_global_tray_id(slot),
            "location_label": f"AMS {slot.ams_id} / {slot_label}",
            "filament_brand_id": context["brand_id"],
            "filament_brand_name": context["brand_name"],
            "filament_material": context["material"],
            "filament_series": context["series"],
        }
    )


def ams_slot_state_name(slot: AmsSlot) -> str | None:
    if slot.slot_state:
        normalized = _slot_state_name(slot.slot_state)
        if normalized is not None and not normalized.startswith("unknown:"):
            return normalized
    return slot.state_name or slot.tray_state_name or slot.slot_state


def filament_context_from_slot(slot: AmsSlot) -> dict[str, Any]:
    sku = slot.filament_spool.sku if slot.filament_spool and slot.filament_spool.sku else None
    if sku is None:
        return {"brand_id": None, "brand_name": None, "material": None, "series": None}
    first_series = sku.type_series
    first_brand = first_series.brand if first_series else None
    return {
        "brand_id": first_brand.id if first_brand else None,
        "brand_name": first_brand.name if first_brand else None,
        "material": first_series.material_type if first_series else None,
        "series": first_series.series_name if first_series else None,
    }


def slot_user_tray_id(slot: AmsSlot) -> int | None:
    try:
        return int(slot.tray_id) + 1
    except (TypeError, ValueError):
        return None


def slot_global_tray_id(slot: AmsSlot) -> str:
    try:
        ams_id = int(slot.ams_id)
        tray_id = int(slot.tray_id)
    except (TypeError, ValueError):
        return f"{slot.ams_id}:{slot.tray_id}"
    if ams_id >= 128:
        ams_id -= 124
    return str((ams_id * 4) + tray_id)


def storage_media_type(file: PrinterStorageFile) -> str:
    guessed, _encoding = mimetypes.guess_type(file.name or file.path)
    if guessed:
        return guessed
    if file.type == "log":
        return "text/plain; charset=utf-8"
    if file.type in {"gcode", "model"}:
        return "application/octet-stream"
    return "application/octet-stream"


def storage_file_can_inline(file: PrinterStorageFile) -> bool:
    media_type = storage_media_type(file)
    return media_type.startswith(("image/", "video/", "text/"))


def storage_cache_headers(file: PrinterStorageFile) -> dict[str, str]:
    size = file.size or 0
    modified = file.modified_at
    stamp = int(modified.timestamp()) if modified else int(file.last_scanned_at.timestamp())
    headers = {
        "Cache-Control": "private, max-age=604800",
        "ETag": f'W/"printer-storage-{file.id}-{size}-{stamp}"',
    }
    if modified is not None:
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        headers["Last-Modified"] = format_datetime(modified.astimezone(timezone.utc), usegmt=True)
    return headers


def parse_range_header(value: str, size: int) -> tuple[int, int] | None:
    if not value.startswith("bytes=") or size <= 0:
        return None
    spec = value.removeprefix("bytes=").split(",", 1)[0].strip()
    if "-" not in spec:
        return None
    start_text, end_text = spec.split("-", 1)
    try:
        if start_text == "":
            suffix = int(end_text)
            if suffix <= 0:
                return None
            start = max(0, size - suffix)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
    except ValueError:
        return None
    if start < 0 or end < start or start >= size:
        return None
    return start, min(end, size - 1)


def storage_usage_summary(db: Session, printer_id: int) -> dict[str, Any]:
    telemetry = latest_storage_telemetry(db, printer_id)
    if not telemetry:
        return {}
    usage = {
        "internal": storage_capacity(telemetry, "internal"),
        "external": storage_capacity(telemetry, "external"),
        "timelapse_path": telemetry.get("timelapse_path"),
        "store_path_type": telemetry.get("tl_store_path_type"),
        "store_hpd_type": telemetry.get("tl_store_hpd_type"),
        "current_target": storage_target_name(telemetry.get("tl_store_path_type")),
    }
    return {key: value for key, value in usage.items() if value not in (None, {}, "")}


def latest_storage_telemetry(db: Session, printer_id: int) -> dict[str, Any]:
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    if snapshot is not None:
        camera = snapshot.camera if isinstance(snapshot.camera, dict) else {}
        telemetry = storage_telemetry_from_sections(camera, {})
        if telemetry:
            return telemetry

    raw_messages = db.scalars(
        select(RawMqttMessage)
        .where(RawMqttMessage.printer_id == printer_id)
        .order_by(RawMqttMessage.id.desc())
        .limit(20)
    ).all()
    for raw_message in raw_messages:
        if not isinstance(raw_message.payload, dict):
            continue
        payload = raw_message.payload
        print_section = payload.get("print") if isinstance(payload.get("print"), dict) else payload
        if not isinstance(print_section, dict):
            continue
        ipcam = print_section.get("ipcam") if isinstance(print_section.get("ipcam"), dict) else {}
        device = print_section.get("device") if isinstance(print_section.get("device"), dict) else {}
        device_cam = device.get("cam") if isinstance(device.get("cam"), dict) else {}
        telemetry = storage_telemetry_from_sections(ipcam, device_cam)
        if telemetry:
            return telemetry
    return {}


def storage_telemetry_from_sections(ipcam: dict[str, Any], device_cam: dict[str, Any]) -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    for key in (
        "tl_internal_free_kb",
        "tl_internal_total_kb",
        "tl_external_free_kb",
        "tl_external_total_kb",
        "tl_store_path_type",
        "tl_store_hpd_type",
        "timelapse_path",
    ):
        if key in ipcam:
            telemetry[key] = ipcam.get(key)
        if key in device_cam:
            telemetry[key] = device_cam.get(key)
    return telemetry


def storage_capacity(telemetry: dict[str, Any], kind: str) -> dict[str, Any]:
    total_kb = int_or_none(telemetry.get(f"tl_{kind}_total_kb"))
    free_kb = int_or_none(telemetry.get(f"tl_{kind}_free_kb"))
    if total_kb is None and free_kb is None:
        return {}
    total_bytes = total_kb * 1024 if total_kb is not None else None
    free_bytes = free_kb * 1024 if free_kb is not None else None
    used_bytes = total_bytes - free_bytes if total_bytes is not None and free_bytes is not None else None
    used_percent = None
    if used_bytes is not None and total_bytes:
        used_percent = round(max(0, min(100, (used_bytes / total_bytes) * 100)), 1)
    return {
        key: value
        for key, value in {
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "used_bytes": used_bytes,
            "used_percent": used_percent,
        }.items()
        if value is not None
    }


def storage_target_name(value: Any) -> str | None:
    text = str(value)
    if text == "1":
        return "internal"
    if text == "2":
        return "external"
    return None


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def notification_target_read(target: NotificationTarget) -> NotificationTargetRead:
    read = NotificationTargetRead.model_validate(target)
    redacted = redact_notification_config(target.config)
    display = target.display_config if isinstance(target.display_config, dict) and target.display_config else redacted
    return read.model_copy(update={"config": redacted, "display_config": display})


def notification_target_or_404(db: Session, target_id: int) -> NotificationTarget:
    target = db.get(NotificationTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Notification target not found")
    return target


def notification_rule_or_404(db: Session, rule_id: int) -> NotificationRule:
    rule = db.get(NotificationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return rule


def printer_or_404(db: Session, printer_id: int):
    printer = get_printer(db, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


def sync_runtime_connection_status(db: Session, printer: Any) -> None:
    if printer.connection_status not in {"connected", "connecting"}:
        return
    if mqtt_manager.is_connected(printer.id):
        if printer.connection_status != "connected":
            _set_runtime_connection_status(
                printer,
                status="connected",
                last_error=None,
                last_sync_at=datetime.now(timezone.utc),
            )
        return
    _set_runtime_connection_status(
        printer,
        status="disconnected",
        last_error="MQTT session is not active; reconnect required",
        last_sync_at=None,
    )


def _set_runtime_connection_status(
    printer: Any,
    *,
    status: str,
    last_error: str | None,
    last_sync_at: datetime | None,
) -> None:
    printer.connection_status = status
    printer.last_error = last_error
    if last_sync_at is not None:
        printer.last_sync_at = last_sync_at
    _persist_runtime_connection_status_best_effort(
        int(printer.id),
        status=status,
        last_error=last_error,
        last_sync_at=last_sync_at,
    )


def _persist_runtime_connection_status_best_effort(
    printer_id: int,
    *,
    status: str,
    last_error: str | None,
    last_sync_at: datetime | None,
) -> None:
    if db_session.SessionLocal is None:
        return
    try:
        with db_session.sqlite_write_lock:
            with db_session.SessionLocal() as write_db:
                stored = write_db.get(Printer, printer_id)
                if stored is None:
                    return
                stored.connection_status = status
                stored.last_error = last_error
                if last_sync_at is not None:
                    stored.last_sync_at = last_sync_at
                write_db.add(stored)
                write_db.commit()
    except OperationalError as exc:
        if _is_sqlite_database_locked(exc):
            LOGGER.warning("SQLite write lock while syncing printer connection status for printer id %s", printer_id)
            return
        raise


def _is_sqlite_database_locked(value: object) -> bool:
    text = str(value).lower()
    return "database is locked" in text or "database is busy" in text


def should_reconnect_for_refresh(printer: Any) -> bool:
    return bool(printer.enabled and printer.connection_status in {"connected", "connecting"})


def reconnect_for_refresh(db: Session, printer: Any) -> None:
    try:
        mqtt_manager.connect(db, printer)
    except ValueError as exc:
        db.rollback()
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        db.rollback()
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        status_code = 400 if is_certificate_verify_error(exc) else 502
        detail = str(exc) if status_code == 400 else f"Failed to reconnect printer MQTT: {exc}"
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        db.rollback()
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to reconnect printer MQTT: {exc}") from exc


def sanitize_camera_response(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        key: item
        for key, item in value.items()
        if item is not None and item != "" and not isinstance(item, (dict, list))
    }
