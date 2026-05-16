from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import PrintLogEntry, Printer, PrinterStateSnapshot, RawMqttMessage, utc_now

ACTIVE_STATES = {"RUNNING", "PREPARE", "SLICING", "PAUSE"}
TERMINAL_STATES = {"FINISH", "FAILED", "IDLE"}
LOGGER = logging.getLogger(__name__)


def upsert_print_log_from_snapshot(
    db: Session,
    *,
    printer: Printer,
    snapshot: PrinterStateSnapshot,
    raw_message: RawMqttMessage,
    event_type: str | None,
) -> PrintLogEntry | None:
    state = (snapshot.gcode_state or "").upper()
    if state not in ACTIVE_STATES | TERMINAL_STATES:
        return None

    entry = _find_log_entry(db, printer.id, snapshot.task_id)
    if entry is None and state in ACTIVE_STATES:
        entry = PrintLogEntry(
            printer_id=printer.id,
            printer_name_snapshot=printer.name,
            task_id=snapshot.task_id,
            print_name=snapshot.subtask_name or snapshot.gcode_file,
            gcode_file=snapshot.gcode_file,
            status="paused" if state == "PAUSE" else "running",
            started_at=raw_message.received_at or utc_now(),
            raw_refs={},
        )
        db.add(entry)
        db.flush()
    elif entry is None:
        return None

    _update_progress(entry, snapshot)
    entry.printer_name_snapshot = entry.printer_name_snapshot or printer.name
    entry.task_id = snapshot.task_id or entry.task_id
    entry.print_name = snapshot.subtask_name or snapshot.gcode_file or entry.print_name
    entry.gcode_file = snapshot.gcode_file or entry.gcode_file
    entry.filament_summary = _filament_summary(snapshot.payload)
    entry.hms_summary = _hms_summary(snapshot.payload)
    entry.failure_reason = _failure_reason(snapshot.payload, state) or entry.failure_reason
    entry.raw_refs = _raw_refs(entry.raw_refs, raw_message)

    if state == "PAUSE":
        entry.status = "paused"
    elif state in {"RUNNING", "PREPARE", "SLICING"}:
        entry.status = "running"
    elif state in TERMINAL_STATES:
        _close_entry(entry, state, event_type, raw_message.received_at or utc_now())

    entry.updated_at = utc_now()
    db.add(entry)
    return entry


def list_print_logs(
    db: Session,
    *,
    printer_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[PrintLogEntry]]:
    query = select(PrintLogEntry)
    count_query = select(func.count()).select_from(PrintLogEntry)
    filters = []
    if printer_id is not None:
        filters.append(PrintLogEntry.printer_id == printer_id)
    if status:
        filters.append(PrintLogEntry.status == status)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(PrintLogEntry.print_name.like(pattern), PrintLogEntry.gcode_file.like(pattern)))
    if date_from:
        filters.append(PrintLogEntry.started_at >= date_from)
    if date_to:
        filters.append(PrintLogEntry.started_at <= date_to)
    for item in filters:
        query = query.where(item)
        count_query = count_query.where(item)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(PrintLogEntry.started_at.desc().nullslast(), PrintLogEntry.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return total, rows


def print_log_summary(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    rows = _filtered_rows(db, date_from=date_from, date_to=date_to)
    return _analytics_payload(rows, date_from=date_from, date_to=date_to, bucket="day")


def print_log_analytics(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    printer_id: int | None = None,
    bucket: str = "day",
) -> dict[str, Any]:
    rows = _filtered_rows(db, date_from=date_from, date_to=date_to, printer_id=printer_id)
    return _analytics_payload(rows, date_from=date_from, date_to=date_to, printer_id=printer_id, bucket=bucket)


def _filtered_rows(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    printer_id: int | None = None,
) -> list[PrintLogEntry]:
    query = select(PrintLogEntry)
    if printer_id is not None:
        query = query.where(PrintLogEntry.printer_id == printer_id)
    if date_from:
        query = query.where(PrintLogEntry.started_at >= date_from)
    if date_to:
        query = query.where(PrintLogEntry.started_at <= date_to)
    return list(db.scalars(query).all())


def _analytics_payload(
    rows: list[PrintLogEntry],
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    printer_id: int | None = None,
    bucket: str,
) -> dict[str, Any]:
    by_printer: dict[int, dict[str, Any]] = {}
    by_date: dict[str, dict[str, Any]] = {}
    by_failure_reason: dict[str, dict[str, Any]] = {}
    by_hms: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = by_printer.setdefault(
            row.printer_id,
            {
                "printer_id": row.printer_id,
                "printer_name": row.printer_name_snapshot,
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "cancelled": 0,
                "duration_seconds": 0,
                "average_duration_seconds": None,
            },
        )
        item["total"] += 1
        item["duration_seconds"] += row.duration_seconds or 0
        if row.status == "succeeded":
            item["succeeded"] += 1
        if row.status == "failed":
            item["failed"] += 1
        if row.status == "cancelled":
            item["cancelled"] += 1

        bucket_key = _bucket_key(row.started_at or row.created_at, bucket)
        date_item = by_date.setdefault(
            bucket_key,
            {"bucket": bucket_key, "total": 0, "succeeded": 0, "failed": 0, "cancelled": 0, "duration_seconds": 0},
        )
        date_item["total"] += 1
        date_item["duration_seconds"] += row.duration_seconds or 0
        if row.status in {"succeeded", "failed", "cancelled"}:
            date_item[row.status if row.status != "succeeded" else "succeeded"] += 1

        if row.status == "failed":
            reason = row.failure_reason or "unknown"
            reason_item = by_failure_reason.setdefault(reason, {"reason": reason, "count": 0})
            reason_item["count"] += 1

        for hms in row.hms_summary or []:
            if not isinstance(hms, dict):
                continue
            code = str(hms.get("short_code") or hms.get("code") or "unknown")
            hms_item = by_hms.setdefault(code, {"code": code, "count": 0})
            hms_item["count"] += 1

    completed = [row for row in rows if row.status in {"succeeded", "failed", "cancelled"}]
    durations = [row.duration_seconds or 0 for row in completed if row.duration_seconds is not None]
    total = len(rows)
    succeeded = sum(1 for row in rows if row.status == "succeeded")
    failed = sum(1 for row in rows if row.status == "failed")
    cancelled = sum(1 for row in rows if row.status == "cancelled")
    for item in by_printer.values():
        completed_count = item["succeeded"] + item["failed"] + item["cancelled"]
        item["average_duration_seconds"] = round(item["duration_seconds"] / completed_count, 2) if completed_count else None
        item["success_rate"] = round(item["succeeded"] / completed_count, 4) if completed_count else 0.0

    return {
        "from": date_from,
        "to": date_to,
        "printer_id": printer_id,
        "bucket": bucket,
        "total": total,
        "running": sum(1 for row in rows if row.status in {"running", "paused"}),
        "succeeded": succeeded,
        "failed": failed,
        "cancelled": cancelled,
        "total_duration_seconds": sum(row.duration_seconds or 0 for row in rows),
        "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else None,
        "longest_duration_seconds": max(durations) if durations else None,
        "success_rate": round(succeeded / len(completed), 4) if completed else 0.0,
        "failure_rate": round(failed / len(completed), 4) if completed else 0.0,
        "cancelled_rate": round(cancelled / len(completed), 4) if completed else 0.0,
        "by_printer": list(by_printer.values()),
        "by_date": sorted(by_date.values(), key=lambda item: item["bucket"]),
        "by_failure_reason": sorted(by_failure_reason.values(), key=lambda item: item["count"], reverse=True),
        "by_hms": sorted(by_hms.values(), key=lambda item: item["count"], reverse=True),
    }


def completed_print_seconds_by_printer(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(PrintLogEntry.printer_id, func.sum(PrintLogEntry.duration_seconds))
        .where(PrintLogEntry.duration_seconds.is_not(None), PrintLogEntry.status.in_(("succeeded", "failed", "cancelled")))
        .group_by(PrintLogEntry.printer_id)
    ).all()
    return {int(printer_id): int(seconds or 0) for printer_id, seconds in rows}


def repair_print_log_printer_ids_from_raw_topics(db: Session) -> int:
    printers_by_serial = {
        _normalize_serial(printer.serial): printer
        for printer in db.scalars(select(Printer)).all()
        if _normalize_serial(printer.serial)
    }
    if not printers_by_serial:
        return 0

    entries = list(db.scalars(select(PrintLogEntry)).all())
    raw_ids: set[int] = set()
    for entry in entries:
        for raw_id in _print_log_raw_ref_ids(entry):
            raw_ids.add(raw_id)
    if not raw_ids:
        return 0

    raw_messages = {
        raw.id: raw
        for raw in db.scalars(select(RawMqttMessage).where(RawMqttMessage.id.in_(raw_ids))).all()
    }
    repaired = 0
    for entry in entries:
        serials = {
            serial
            for raw_id in _print_log_raw_ref_ids(entry)
            for serial in [_serial_from_topic(raw_messages.get(raw_id).topic if raw_messages.get(raw_id) else None)]
            if serial in printers_by_serial
        }
        if len(serials) != 1:
            continue
        target = printers_by_serial[next(iter(serials))]
        if entry.printer_id == target.id:
            continue
        if entry.task_id and _print_log_task_exists(db, target_printer_id=target.id, task_id=entry.task_id, exclude_id=entry.id):
            LOGGER.warning(
                "Skipping print log printer repair for entry %s because task %s already exists on printer %s",
                entry.id,
                entry.task_id,
                target.id,
            )
            continue
        entry.printer_id = target.id
        entry.printer_name_snapshot = entry.printer_name_snapshot or target.name
        entry.updated_at = utc_now()
        db.add(entry)
        repaired += 1
    if repaired:
        db.commit()
    return repaired


def _find_log_entry(db: Session, printer_id: int, task_id: str | None) -> PrintLogEntry | None:
    if task_id:
        entry = db.scalars(
            select(PrintLogEntry)
            .where(PrintLogEntry.printer_id == printer_id, PrintLogEntry.task_id == task_id)
            .order_by(PrintLogEntry.id.desc())
        ).first()
        if entry is not None:
            return entry
    return db.scalars(
        select(PrintLogEntry)
        .where(PrintLogEntry.printer_id == printer_id, PrintLogEntry.finished_at.is_(None))
        .order_by(PrintLogEntry.id.desc())
    ).first()


def _print_log_raw_ref_ids(entry: PrintLogEntry) -> list[int]:
    raw_refs = entry.raw_refs if isinstance(entry.raw_refs, dict) else {}
    ids: list[int] = []
    for key in ("first_raw_mqtt_id", "last_raw_mqtt_id"):
        raw_id = _as_int(raw_refs.get(key))
        if raw_id is not None:
            ids.append(raw_id)
    return ids


def _print_log_task_exists(db: Session, *, target_printer_id: int, task_id: str, exclude_id: int) -> bool:
    return db.scalars(
        select(PrintLogEntry.id)
        .where(
            PrintLogEntry.printer_id == target_printer_id,
            PrintLogEntry.task_id == task_id,
            PrintLogEntry.id != exclude_id,
        )
        .limit(1)
    ).first() is not None


def _serial_from_topic(topic: str | None) -> str | None:
    if not topic:
        return None
    parts = str(topic).split("/")
    if len(parts) >= 3 and parts[0] == "device" and parts[2] == "report":
        return _normalize_serial(parts[1])
    return None


def _normalize_serial(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _update_progress(entry: PrintLogEntry, snapshot: PrinterStateSnapshot) -> None:
    progress = snapshot.mc_percent
    if progress is not None:
        entry.final_progress = progress
        entry.max_progress = max(entry.max_progress or 0, progress)
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    print_section = payload.get("print") if isinstance(payload.get("print"), dict) else {}
    entry.layer_current = _as_int(print_section.get("layer_num")) or entry.layer_current
    entry.layer_total = _as_int(print_section.get("total_layer_num")) or entry.layer_total


def _close_entry(entry: PrintLogEntry, state: str, event_type: str | None, finished_at: datetime) -> None:
    if event_type == "print.cancelled":
        entry.status = "cancelled"
    elif state == "FINISH" or event_type == "print.finished":
        entry.status = "succeeded"
    elif state == "FAILED" or event_type == "print.failed":
        entry.status = "failed"
    elif state == "IDLE":
        entry.status = "succeeded" if (entry.final_progress or entry.max_progress or 0) >= 100 else "cancelled"
    entry.finished_at = entry.finished_at or finished_at
    if entry.started_at and entry.finished_at:
        entry.duration_seconds = max(0, round((_aware(entry.finished_at) - _aware(entry.started_at)).total_seconds()))


def _filament_summary(payload: dict[str, Any]) -> dict[str, Any]:
    print_section = payload.get("print") if isinstance(payload.get("print"), dict) else {}
    ams = print_section.get("ams") if isinstance(print_section.get("ams"), dict) else {}
    materials: list[str] = []
    colors: list[str] = []
    units = ams.get("ams") if isinstance(ams.get("ams"), list) else []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        trays = unit.get("tray") if isinstance(unit.get("tray"), list) else []
        for tray in trays:
            if not isinstance(tray, dict):
                continue
            material = _text(tray.get("tray_type") or tray.get("filament_type"))
            color = _text(tray.get("tray_color") or tray.get("color"))
            if material and material not in materials:
                materials.append(material)
            if color and color not in colors:
                colors.append(color)
    return {"materials": materials, "colors": colors}


def _hms_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    print_section = payload.get("print") if isinstance(payload.get("print"), dict) else {}
    errors = print_section.get("hms")
    if not isinstance(errors, list):
        return []
    summary: list[dict[str, Any]] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        summary.append(redact_sensitive({"attr": item.get("attr"), "code": item.get("code")}))  # type: ignore[arg-type]
    return summary


def _failure_reason(payload: dict[str, Any], state: str) -> str | None:
    print_section = payload.get("print") if isinstance(payload.get("print"), dict) else {}
    for key in ("fail_reason", "failure_reason", "reason", "err_code", "error_code", "print_error"):
        value = _text(print_section.get(key))
        if value:
            return value
    if state == "FAILED":
        return "Printer reported FAILED state"
    return None


def _raw_refs(existing: dict[str, Any] | None, raw_message: RawMqttMessage) -> dict[str, Any]:
    refs = dict(existing or {})
    refs["last_raw_mqtt_id"] = raw_message.id
    refs["last_raw_mqtt_received_at"] = raw_message.received_at.isoformat()
    refs.setdefault("first_raw_mqtt_id", raw_message.id)
    refs.setdefault("first_raw_mqtt_received_at", raw_message.received_at.isoformat())
    return refs


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _bucket_key(value: datetime, bucket: str) -> str:
    aware = _aware(value)
    if bucket == "week":
        start = aware - timedelta(days=aware.weekday())
        return start.date().isoformat()
    if bucket == "month":
        return f"{aware.year:04d}-{aware.month:02d}"
    return aware.date().isoformat()
