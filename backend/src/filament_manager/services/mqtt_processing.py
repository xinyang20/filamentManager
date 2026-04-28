from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import (
    AmsSlot,
    AmsUnit,
    PrintJob,
    Printer,
    PrinterEvent,
    PrinterStateSnapshot,
    RawMqttMessage,
    Spool,
    SpoolLocation,
    utc_now,
)
from filament_manager.mqtt.parser import (
    ParsedAmsSlot,
    ParsedAmsUnit,
    extract_command,
    extract_print,
    normalize_state,
    parse_ams_units,
)
from filament_manager.mqtt.state_machine import classify_transition
from filament_manager.services.device_status import (
    merge_ams_version_cache,
    upsert_device_status_from_get_accessories,
    upsert_device_status_from_get_version,
    upsert_device_status_from_push_status,
)
from filament_manager.services.ams import record_ams_slot_history_sample
from filament_manager.services.metrics import record_metric_samples_from_push_status
from filament_manager.services.notifications import dispatch_event_notifications
from filament_manager.services.print_log import upsert_print_log_from_snapshot


def emit_printer_event(
    db: Session,
    *,
    printer_id: int,
    event_type: str,
    message: str,
    severity: str = "info",
    data: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> PrinterEvent:
    if dedupe_key:
        existing = db.scalars(
            select(PrinterEvent)
            .where(PrinterEvent.printer_id == printer_id, PrinterEvent.dedupe_key == dedupe_key)
            .order_by(PrinterEvent.id.desc())
        ).first()
        if existing and existing.event_type == event_type and existing.data == data:
            return existing
    event = PrinterEvent(
        printer_id=printer_id,
        event_type=event_type,
        severity=severity,
        message=message,
        dedupe_key=dedupe_key,
        data=data,
    )
    db.add(event)
    db.flush()
    dispatch_event_notifications(db, event)
    return event


def _success_result(print_section: dict[str, Any]) -> bool:
    result = str(print_section.get("result") or "").upper()
    reason = str(print_section.get("reason") or "").upper()
    return result == "SUCCESS" or reason == "SUCCESS"


def _recent_stop_success(db: Session, printer_id: int, current_raw_id: int) -> bool:
    messages = list(
        db.scalars(
            select(RawMqttMessage)
            .where(RawMqttMessage.printer_id == printer_id, RawMqttMessage.id < current_raw_id)
            .order_by(RawMqttMessage.id.desc())
            .limit(10)
        ).all()
    )
    for message in messages:
        if message.command == "stop" and _success_result(extract_print(message.payload)):
            return True
        if message.command == "push_status":
            state = normalize_state(extract_print(message.payload).get("gcode_state"))
            if state in {"RUNNING", "PAUSE"}:
                return False
    return False


def _upsert_state_snapshot(
    db: Session,
    printer: Printer,
    payload: dict[str, Any],
    raw_message: RawMqttMessage,
) -> PrinterStateSnapshot:
    print_section = extract_print(payload)
    current_state = normalize_state(print_section.get("gcode_state"))
    snapshot = db.scalars(
        select(PrinterStateSnapshot).where(PrinterStateSnapshot.printer_id == printer.id)
    ).first()
    previous_state = snapshot.gcode_state if snapshot else None
    previous_connection_status = printer.connection_status

    values = {
        "gcode_state": current_state,
        "print_type": _as_text(print_section.get("print_type")),
        "mc_percent": _as_int(print_section.get("mc_percent")),
        "mc_remaining_time": _as_int(print_section.get("mc_remaining_time")),
        "gcode_file": _as_text(print_section.get("gcode_file")),
        "subtask_name": _as_text(print_section.get("subtask_name")),
        "project_id": _as_text(print_section.get("project_id")),
        "profile_id": _as_text(print_section.get("profile_id")),
        "task_id": _as_text(print_section.get("task_id")),
        "error_code": _as_text(print_section.get("err_code") or print_section.get("error_code")),
        "payload": payload,
    }

    if snapshot is None:
        snapshot = PrinterStateSnapshot(printer_id=printer.id, **values)
        db.add(snapshot)
    else:
        for key, value in values.items():
            setattr(snapshot, key, value)
        snapshot.updated_at = utc_now()

    printer.last_sync_at = utc_now()
    printer.connection_status = "connected"
    printer.last_error = None
    db.add(printer)
    db.flush()

    if previous_connection_status not in {"connected", "connecting"}:
        emit_printer_event(
            db,
            printer_id=printer.id,
            event_type="printer.connection.restored",
            severity="info",
            message="Printer telemetry connection restored",
            data={"previous_status": previous_connection_status, "current_status": "connected"},
        )

    transition = classify_transition(
        previous_state,
        current_state,
        recent_stop_success=_recent_stop_success(db, printer.id, raw_message.id),
    )
    if transition:
        emit_printer_event(
            db,
            printer_id=printer.id,
            event_type=transition.event_type,
            severity=transition.severity,
            message=transition.message,
            data={
                "previous_state": previous_state,
                "current_state": current_state,
                "task_id": values["task_id"],
                "gcode_file": values["gcode_file"],
            },
        )
        _update_print_job(db, printer.id, snapshot, transition.event_type)
        upsert_print_log_from_snapshot(
            db,
            printer=printer,
            snapshot=snapshot,
            raw_message=raw_message,
            event_type=transition.event_type,
        )
    elif current_state:
        _update_print_job(db, printer.id, snapshot, None)
        upsert_print_log_from_snapshot(
            db,
            printer=printer,
            snapshot=snapshot,
            raw_message=raw_message,
            event_type=None,
        )

    return snapshot


def _update_print_job(
    db: Session,
    printer_id: int,
    snapshot: PrinterStateSnapshot,
    event_type: str | None,
) -> None:
    task_id = snapshot.task_id
    job = None
    if task_id:
        job = db.scalars(
            select(PrintJob)
            .where(PrintJob.printer_id == printer_id, PrintJob.task_id == task_id)
            .order_by(PrintJob.id.desc())
        ).first()
    if job is None and snapshot.gcode_state in {"RUNNING", "PAUSE", "FINISH", "FAILED"}:
        job = db.scalars(
            select(PrintJob)
            .where(PrintJob.printer_id == printer_id)
            .order_by(PrintJob.id.desc())
        ).first()
        if job and job.finished_at is not None:
            job = None
    if job is None and snapshot.gcode_state == "RUNNING":
        job = PrintJob(
            printer_id=printer_id,
            task_id=task_id,
            name=snapshot.subtask_name or snapshot.gcode_file,
            state="RUNNING",
            started_at=utc_now(),
            raw=snapshot.payload,
        )
        db.add(job)
    elif job:
        job.state = snapshot.gcode_state or job.state
        job.name = snapshot.subtask_name or snapshot.gcode_file or job.name
        job.raw = snapshot.payload
        if event_type == "print.started" and job.started_at is None:
            job.started_at = utc_now()
        if event_type in {"print.finished", "print.failed", "print.cancelled"}:
            job.finished_at = utc_now()
        db.add(job)


def _spool_display_name(slot: ParsedAmsSlot) -> str:
    parts = [part for part in [slot.series, slot.material] if part]
    if parts:
        return " ".join(parts)
    return f"AMS {slot.ams_id}-{slot.tray_id} spool"


def _get_or_create_spool_for_slot(db: Session, printer_id: int, slot: ParsedAmsSlot) -> Spool | None:
    identity_key = slot.identity.identity_key
    if identity_key is None:
        return None
    spool = db.scalars(select(Spool).where(Spool.identity_key == identity_key)).first()
    if spool is None:
        spool = Spool(
            identity_key=identity_key,
            identity_source=slot.identity.identity_source,
            display_name=_spool_display_name(slot),
            material=slot.material,
            series=slot.series,
            color=slot.color,
            status="active",
            sealed_quantity=0,
            opened_at=utc_now(),
        )
        db.add(spool)
        db.flush()
        emit_printer_event(
            db,
            printer_id=printer_id,
            event_type="spool.discovered",
            severity="info",
            message="RFID spool discovered",
            dedupe_key=f"spool.discovered:{identity_key}",
            data={
                "identity_key": identity_key,
                "identity_source": slot.identity.identity_source,
                "ams_id": slot.ams_id,
                "tray_id": slot.tray_id,
            },
        )
    return spool


def _update_spool_location_if_stable(
    db: Session,
    *,
    printer_id: int,
    slot: ParsedAmsSlot,
    spool: Spool,
) -> None:
    if slot.is_transitioning:
        return
    unchanged = (
        spool.current_printer_id == printer_id
        and spool.current_ams_id == slot.ams_id
        and spool.current_tray_id == slot.tray_id
    )
    if unchanged:
        return
    spool.current_printer_id = printer_id
    spool.current_ams_id = slot.ams_id
    spool.current_tray_id = slot.tray_id
    db.add(spool)
    db.add(
        SpoolLocation(
            spool_id=spool.id,
            printer_id=printer_id,
            ams_id=slot.ams_id,
            tray_id=slot.tray_id,
            event_type="spool.location_changed",
        )
    )
    emit_printer_event(
        db,
        printer_id=printer_id,
        event_type="spool.location_changed",
        severity="info",
        message="Spool location changed",
        data={
            "spool_id": spool.id,
            "identity_key": spool.identity_key,
            "ams_id": slot.ams_id,
            "tray_id": slot.tray_id,
        },
    )


def _upsert_ams_unit(db: Session, printer_id: int, unit: ParsedAmsUnit) -> AmsUnit:
    raw = merge_ams_version_cache(db, printer_id=printer_id, ams_id=unit.ams_id, raw=unit.raw)
    model = db.scalars(
        select(AmsUnit).where(AmsUnit.printer_id == printer_id, AmsUnit.ams_id == unit.ams_id)
    ).first()
    if model is None:
        model = AmsUnit(printer_id=printer_id, ams_id=unit.ams_id, raw=raw)
        db.add(model)
    model.humidity = unit.humidity
    model.temperature = unit.temperature
    model.raw = raw
    model.updated_at = utc_now()
    return model


def _upsert_ams_slot(db: Session, printer_id: int, parsed: ParsedAmsSlot) -> tuple[AmsSlot, bool]:
    slot = db.scalars(
        select(AmsSlot).where(
            AmsSlot.printer_id == printer_id,
            AmsSlot.ams_id == parsed.ams_id,
            AmsSlot.tray_id == parsed.tray_id,
        )
    ).first()
    created = slot is None
    previous = None if slot is None else {
        "slot_state": slot.slot_state,
        "material": slot.material,
        "series": slot.series,
        "color": slot.color,
        "remain": slot.remain,
        "tray_uuid": slot.tray_uuid,
        "tag_uid": slot.tag_uid,
        "is_transitioning": slot.is_transitioning,
    }
    if slot is None:
        slot = AmsSlot(printer_id=printer_id, ams_id=parsed.ams_id, tray_id=parsed.tray_id, raw=parsed.raw)
        db.add(slot)

    slot.slot_state = parsed.slot_state
    slot.material = parsed.material
    slot.series = parsed.series
    slot.color = parsed.color
    slot.remain = parsed.remain
    slot.tray_uuid = parsed.tray_uuid
    slot.tag_uid = parsed.tag_uid
    slot.identity_key = parsed.identity.identity_key
    slot.identity_source = parsed.identity.identity_source
    slot.identity_confidence = parsed.identity.identity_confidence
    slot.identity_warning = parsed.identity.identity_warning
    slot.is_transitioning = parsed.is_transitioning
    slot.raw = parsed.raw
    slot.updated_at = utc_now()
    changed = created or previous != {
        "slot_state": slot.slot_state,
        "material": slot.material,
        "series": slot.series,
        "color": slot.color,
        "remain": slot.remain,
        "tray_uuid": slot.tray_uuid,
        "tag_uid": slot.tag_uid,
        "is_transitioning": slot.is_transitioning,
    }
    return slot, changed


def _process_ams(db: Session, printer_id: int, payload: dict[str, Any], raw_message: RawMqttMessage) -> None:
    for unit in parse_ams_units(payload):
        ams_unit = _upsert_ams_unit(db, printer_id, unit)
        emit_printer_event(
            db,
            printer_id=printer_id,
            event_type="ams.unit.updated",
            severity="info",
            message="AMS unit updated",
            dedupe_key=f"ams.unit.updated:{printer_id}:{unit.ams_id}",
            data={"ams_id": unit.ams_id, "ams_type_name": ams_unit.ams_type_name, "module_type": ams_unit.module_type},
        )
        for parsed_slot in unit.slots:
            slot, changed = _upsert_ams_slot(db, printer_id, parsed_slot)
            record_ams_slot_history_sample(
                db,
                slot=slot,
                sampled_at=raw_message.received_at,
                raw_message_id=raw_message.id,
            )
            if changed:
                emit_printer_event(
                    db,
                    printer_id=printer_id,
                    event_type="ams.slot.updated",
                    severity="info",
                    message="AMS slot updated",
                    data={
                        "ams_id": parsed_slot.ams_id,
                        "tray_id": parsed_slot.tray_id,
                        "state": slot.state_name or slot.slot_state,
                        "material": parsed_slot.material,
                        "remain": parsed_slot.remain,
                    },
                )
            identity = parsed_slot.identity
            if identity.identity_source == "tag_uid":
                emit_printer_event(
                    db,
                    printer_id=printer_id,
                    event_type="slot.identity_fallback",
                    severity="warning",
                    message="Tray UUID is invalid; tag UID is used as identity fallback",
                    dedupe_key=f"slot.identity_fallback:{printer_id}:{parsed_slot.ams_id}:{parsed_slot.tray_id}",
                    data={
                        "ams_id": parsed_slot.ams_id,
                        "tray_id": parsed_slot.tray_id,
                        "identity_key": identity.identity_key,
                        "warning": identity.identity_warning,
                    },
                )
            if identity.identity_source == "manual_required":
                if not parsed_slot.is_transitioning:
                    slot.spool_id = None
                emit_printer_event(
                    db,
                    printer_id=printer_id,
                    event_type="spool.unidentified",
                    severity="warning",
                    message="AMS slot requires manual spool binding",
                    dedupe_key=f"spool.unidentified:{printer_id}:{parsed_slot.ams_id}:{parsed_slot.tray_id}",
                    data={
                        "ams_id": parsed_slot.ams_id,
                        "tray_id": parsed_slot.tray_id,
                        "warning": identity.identity_warning,
                    },
                )
                continue

            spool = _get_or_create_spool_for_slot(db, printer_id, parsed_slot)
            if spool is not None and not parsed_slot.is_transitioning:
                slot.spool_id = spool.id
                _update_spool_location_if_stable(db, printer_id=printer_id, slot=parsed_slot, spool=spool)
            db.add(slot)


def _record_command_event(
    db: Session,
    printer_id: int,
    command: str,
    payload: dict[str, Any],
) -> None:
    command_section = _command_section(payload, command)
    severity = _command_event_severity(command, command_section)
    emit_printer_event(
        db,
        printer_id=printer_id,
        event_type=f"printer.command.{command}",
        severity=severity,
        message=f"Printer command received: {command}",
        dedupe_key=f"printer.command:{command}:{command_section.get('sequence_id')}",
        data={
            "command": command,
            "sequence_id": command_section.get("sequence_id"),
            "result": command_section.get("result"),
            "reason": command_section.get("reason"),
            "err_code": command_section.get("err_code"),
            "led_node": command_section.get("led_node"),
            "led_mode": command_section.get("led_mode"),
        },
    )


def process_mqtt_payload(
    db: Session,
    *,
    printer_id: int,
    payload: dict[str, Any],
    topic: str | None = None,
) -> RawMqttMessage:
    printer = db.get(Printer, printer_id)
    if printer is None:
        raise ValueError(f"Printer {printer_id} does not exist")

    command = extract_command(payload)
    raw_message = RawMqttMessage(
        printer_id=printer_id,
        topic=topic,
        command=command,
        payload=payload,
    )
    db.add(raw_message)
    db.flush()

    if command == "push_status":
        _upsert_state_snapshot(db, printer, payload, raw_message)
        _process_ams(db, printer_id, payload, raw_message)
        upsert_device_status_from_push_status(db, printer=printer, payload=payload, raw_message=raw_message)
        record_metric_samples_from_push_status(
            db,
            printer_id=printer_id,
            payload=payload,
            raw_message=raw_message,
        )
    elif command == "get_version":
        upsert_device_status_from_get_version(db, printer=printer, payload=payload, raw_message=raw_message)
        _record_command_event(db, printer_id, command, payload)
    elif command == "get_accessories":
        upsert_device_status_from_get_accessories(db, printer=printer, payload=payload, raw_message=raw_message)
        _record_command_event(db, printer_id, command, payload)
    elif command:
        _record_command_event(db, printer_id, command, payload)
    else:
        emit_printer_event(
            db,
            printer_id=printer_id,
            event_type="mqtt.unknown_payload",
            severity="warning",
            message="MQTT payload has no print command",
            data={"topic": topic},
        )

    db.commit()
    db.refresh(raw_message)
    return raw_message


def _as_text(value: Any) -> str | None:
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


def _command_section(payload: dict[str, Any], command: str) -> dict[str, Any]:
    for section_name in ("print", "info", "system", "pushing"):
        section = payload.get(section_name)
        if isinstance(section, dict) and str(section.get("command")) == command:
            return section
    return {}


def _command_event_severity(command: str, command_section: dict[str, Any]) -> str:
    result = str(command_section.get("result") or "").upper()
    if result != "FAIL":
        return "info"
    if _is_benign_ledctrl_failure(command, command_section):
        return "info"
    return "error"


def _is_benign_ledctrl_failure(command: str, command_section: dict[str, Any]) -> bool:
    if command != "ledctrl":
        return False
    reason = str(command_section.get("reason") or "").strip().lower()
    led_node = str(command_section.get("led_node") or "").strip()
    return bool(led_node) and reason == f"did not find the valid led: {led_node}".lower()
