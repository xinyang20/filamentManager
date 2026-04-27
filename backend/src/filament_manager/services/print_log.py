from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import PrintLogEntry, Printer, PrinterStateSnapshot, RawMqttMessage, utc_now

ACTIVE_STATES = {"RUNNING", "PREPARE", "SLICING", "PAUSE"}
TERMINAL_STATES = {"FINISH", "FAILED", "IDLE"}


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
    query = select(PrintLogEntry)
    if date_from:
        query = query.where(PrintLogEntry.started_at >= date_from)
    if date_to:
        query = query.where(PrintLogEntry.started_at <= date_to)
    rows = list(db.scalars(query).all())
    by_printer: dict[int, dict[str, Any]] = {}
    for row in rows:
        item = by_printer.setdefault(
            row.printer_id,
            {
                "printer_id": row.printer_id,
                "printer_name": row.printer_name_snapshot,
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "duration_seconds": 0,
            },
        )
        item["total"] += 1
        item["duration_seconds"] += row.duration_seconds or 0
        if row.status == "succeeded":
            item["succeeded"] += 1
        if row.status == "failed":
            item["failed"] += 1
    return {
        "from": date_from,
        "to": date_to,
        "total": len(rows),
        "running": sum(1 for row in rows if row.status in {"running", "paused"}),
        "succeeded": sum(1 for row in rows if row.status == "succeeded"),
        "failed": sum(1 for row in rows if row.status == "failed"),
        "cancelled": sum(1 for row in rows if row.status == "cancelled"),
        "total_duration_seconds": sum(row.duration_seconds or 0 for row in rows),
        "by_printer": list(by_printer.values()),
    }


def completed_print_seconds_by_printer(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(PrintLogEntry.printer_id, func.sum(PrintLogEntry.duration_seconds))
        .where(PrintLogEntry.duration_seconds.is_not(None), PrintLogEntry.status.in_(("succeeded", "failed", "cancelled")))
        .group_by(PrintLogEntry.printer_id)
    ).all()
    return {int(printer_id): int(seconds or 0) for printer_id, seconds in rows}


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
