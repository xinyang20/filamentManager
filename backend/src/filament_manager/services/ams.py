from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db import session as db_session
from filament_manager.db.models import AmsLabel, AmsSlot, AmsSlotHistorySample, AmsUnit, DeviceMetricSample, DeviceStatusSnapshot, _slot_state_name, utc_now

HISTORY_DEDUPLICATION_WINDOW = timedelta(seconds=60)
HISTORY_RETENTION_PERIOD = timedelta(days=30)
SQLITE_LOCK_RETRY_DELAYS = (0.1, 0.25, 0.5, 1.0)
LOGGER = logging.getLogger(__name__)


def build_ams_overview(db: Session, printer_id: int) -> dict[str, Any]:
    units = list(db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer_id).order_by(AmsUnit.ams_id)).all())
    slots = list(
        db.scalars(
            select(AmsSlot)
            .where(AmsSlot.printer_id == printer_id)
            .order_by(AmsSlot.ams_id, AmsSlot.tray_id)
        ).all()
    )
    unit_by_id = {unit.ams_id: unit for unit in units}
    labels = {
        label.ams_id: label.display_name
        for label in db.scalars(select(AmsLabel).where(AmsLabel.printer_id == printer_id)).all()
    }
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    active = _active_slot_from_snapshot(snapshot, slots)
    slots_by_unit: dict[str, list[AmsSlot]] = {unit.ams_id: [] for unit in units}
    orphan_slots: list[AmsSlot] = []
    for slot in slots:
        if slot.ams_id in unit_by_id:
            slots_by_unit.setdefault(slot.ams_id, []).append(slot)
        else:
            orphan_slots.append(slot)

    unit_payloads = [
        _unit_overview(unit, slots_by_unit.get(unit.ams_id, []), labels.get(unit.ams_id), active)
        for unit in units
    ]
    if orphan_slots:
        unit_payloads.append(_unknown_unit_overview(orphan_slots, active))

    summary = {
        "ams_count": len(unit_payloads),
        "slot_count": len(slots),
        "loaded_count": sum(1 for slot in slots if _slot_state(slot) == "loaded"),
        "empty_count": sum(1 for slot in slots if _slot_state(slot) == "empty"),
        "transitioning_count": sum(1 for slot in slots if slot.is_transitioning or _slot_state(slot) == "transitioning"),
        "unknown_type_count": sum(1 for unit in unit_payloads if unit["ams_type_name"] == "unknown"),
        "active_slot": _active_slot_payload(active) if active else None,
    }
    return {"summary": summary, "units": unit_payloads}


def set_ams_label(db: Session, *, printer_id: int, ams_id: str, display_name: str) -> AmsLabel:
    clean_name = display_name.strip()
    for attempt in range(len(SQLITE_LOCK_RETRY_DELAYS) + 1):
        try:
            with db_session.sqlite_write_lock:
                label = db.scalars(
                    select(AmsLabel).where(AmsLabel.printer_id == printer_id, AmsLabel.ams_id == ams_id)
                ).first()
                if label is None:
                    label = AmsLabel(printer_id=printer_id, ams_id=ams_id, display_name=clean_name)
                    db.add(label)
                else:
                    label.display_name = clean_name
                    label.updated_at = utc_now()
                    db.add(label)
                db.commit()
            db.refresh(label)
            return label
        except OperationalError as exc:
            db.rollback()
            if _is_sqlite_database_locked(exc) and attempt < len(SQLITE_LOCK_RETRY_DELAYS):
                delay = SQLITE_LOCK_RETRY_DELAYS[attempt]
                LOGGER.warning("SQLite write lock while saving AMS label; retrying in %.2fs", delay)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("Failed to save AMS label")


def delete_ams_label(db: Session, *, printer_id: int, ams_id: str) -> bool:
    for attempt in range(len(SQLITE_LOCK_RETRY_DELAYS) + 1):
        try:
            with db_session.sqlite_write_lock:
                label = db.scalars(
                    select(AmsLabel).where(AmsLabel.printer_id == printer_id, AmsLabel.ams_id == ams_id)
                ).first()
                if label is None:
                    return False
                db.delete(label)
                db.commit()
            return True
        except OperationalError as exc:
            db.rollback()
            if _is_sqlite_database_locked(exc) and attempt < len(SQLITE_LOCK_RETRY_DELAYS):
                delay = SQLITE_LOCK_RETRY_DELAYS[attempt]
                LOGGER.warning("SQLite write lock while deleting AMS label; retrying in %.2fs", delay)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("Failed to delete AMS label")


def build_ams_sensor_history(db: Session, *, printer_id: int, ams_id: str, hours: int) -> dict[str, Any]:
    cutoff = utc_now() - timedelta(hours=hours)
    rows = list(
        db.scalars(
            select(DeviceMetricSample)
            .where(
                DeviceMetricSample.printer_id == printer_id,
                DeviceMetricSample.metric.in_((f"ams.{ams_id}.temperature", f"ams.{ams_id}.humidity")),
                DeviceMetricSample.sampled_at >= cutoff,
            )
            .order_by(DeviceMetricSample.sampled_at, DeviceMetricSample.id)
        ).all()
    )
    points_by_time: dict[datetime, dict[str, Any]] = {}
    for row in rows:
        point = points_by_time.setdefault(row.sampled_at, {"sampled_at": row.sampled_at})
        if row.metric.endswith(".temperature"):
            point["temperature"] = _metric_value(row)
        elif row.metric.endswith(".humidity"):
            point["humidity"] = _metric_value(row)
    points = list(points_by_time.values())
    return {
        "printer_id": printer_id,
        "ams_id": ams_id,
        "hours": hours,
        "points": points,
        "temperature": _stats(point.get("temperature") for point in points),
        "humidity": _stats(point.get("humidity") for point in points),
    }


def record_ams_slot_history_sample(
    db: Session,
    *,
    slot: AmsSlot,
    sampled_at: datetime,
    raw_message_id: int | None,
) -> AmsSlotHistorySample | None:
    sample_values = {
        "state_name": _slot_state(slot),
        "material": slot.material,
        "color": slot.color,
        "remain": slot.remain,
        "k": _text(slot.k),
        "cali_idx": _text(slot.cali_idx),
        "rfid_status": _rfid_status(slot.raw),
    }
    previous = db.scalars(
        select(AmsSlotHistorySample)
        .where(
            AmsSlotHistorySample.printer_id == slot.printer_id,
            AmsSlotHistorySample.ams_id == slot.ams_id,
            AmsSlotHistorySample.tray_id == slot.tray_id,
        )
        .order_by(AmsSlotHistorySample.sampled_at.desc(), AmsSlotHistorySample.id.desc())
        .limit(1)
    ).first()
    if previous is not None and _same_history_sample(previous, sample_values):
        if _aware(sampled_at) - _aware(previous.sampled_at) <= HISTORY_DEDUPLICATION_WINDOW:
            return None

    row = AmsSlotHistorySample(
        printer_id=slot.printer_id,
        ams_id=slot.ams_id,
        tray_id=slot.tray_id,
        sampled_at=sampled_at,
        raw_message_id=raw_message_id,
        **sample_values,
    )
    db.add(row)
    db.flush()
    _delete_old_history(db, printer_id=slot.printer_id, now=sampled_at)
    return row


def _unit_overview(
    unit: AmsUnit,
    slots: list[AmsSlot],
    display_name: str | None,
    active: AmsSlot | None,
) -> dict[str, Any]:
    return {
        "ams_id": unit.ams_id,
        "display_name": display_name,
        "ams_type_name": unit.ams_type_name,
        "module_type": unit.module_type,
        "sw_ver": unit.sw_ver,
        "serial_number": unit.serial_number,
        "humidity": unit.humidity,
        "humidity_raw": unit.humidity_raw,
        "temperature": unit.temperature,
        "dry_time": unit.dry_time,
        "dry_status": unit.dry_status,
        "dry_status_name": unit.dry_status_name,
        "dry_sub_status": unit.dry_sub_status,
        "dry_sub_status_name": unit.dry_sub_status_name,
        "dry_sf_reason": unit.dry_sf_reason,
        "dry_sf_reason_names": unit.dry_sf_reason_names,
        "active_slot": _active_slot_payload(active) if active and active.ams_id == unit.ams_id else None,
        "updated_at": unit.updated_at,
        "raw": redact_sensitive(unit.raw),
        "slots": [_slot_payload(slot, display_name=display_name, active=active) for slot in slots],
    }


def _unknown_unit_overview(slots: list[AmsSlot], active: AmsSlot | None) -> dict[str, Any]:
    updated_at = max((slot.updated_at for slot in slots), default=utc_now())
    return {
        "ams_id": "unknown",
        "display_name": None,
        "ams_type_name": "unknown",
        "module_type": None,
        "sw_ver": None,
        "serial_number": None,
        "humidity": None,
        "humidity_raw": None,
        "temperature": None,
        "dry_time": None,
        "dry_status": None,
        "dry_status_name": None,
        "dry_sub_status": None,
        "dry_sub_status_name": None,
        "dry_sf_reason": None,
        "dry_sf_reason_names": [],
        "active_slot": _active_slot_payload(active) if active and active in slots else None,
        "updated_at": updated_at,
        "raw": {},
        "slots": [_slot_payload(slot, display_name=None, active=active) for slot in slots],
    }


def _slot_payload(slot: AmsSlot, *, display_name: str | None = None, active: AmsSlot | None = None) -> dict[str, Any]:
    location_label = _location_label(slot, display_name)
    context = _filament_context(slot)
    return {
        "id": slot.id,
        "printer_id": slot.printer_id,
        "ams_id": slot.ams_id,
        "tray_id": slot.tray_id,
        "user_tray_id": _user_tray_id(slot),
        "slot_label": _slot_label(slot),
        "global_tray_id": _global_tray_id(slot),
        "location_label": location_label,
        "is_active": bool(active and active.id == slot.id),
        "slot_state": slot.slot_state,
        "material": slot.material,
        "series": slot.series,
        "color": slot.color,
        "remain": slot.remain,
        "tray_uuid": slot.tray_uuid,
        "tag_uid": slot.tag_uid,
        "identity_key": slot.identity_key,
        "identity_source": slot.identity_source,
        "identity_confidence": slot.identity_confidence,
        "identity_warning": slot.identity_warning,
        "is_transitioning": slot.is_transitioning,
        "filament_spool_id": slot.filament_spool_id,
        "filament_brand_id": context["brand_id"],
        "filament_brand_name": context["brand_name"],
        "filament_material": context["material"],
        "filament_series": context["series"],
        "tray_id_name": slot.tray_id_name,
        "tray_color_name": slot.tray_color_name,
        "tray_info_idx": slot.tray_info_idx,
        "nozzle_temp_min": slot.nozzle_temp_min,
        "nozzle_temp_max": slot.nozzle_temp_max,
        "drying_temp": slot.drying_temp,
        "drying_time": slot.drying_time,
        "cali_idx": slot.cali_idx,
        "k": slot.k,
        "state_code": slot.state_code,
        "state_name": _slot_state(slot),
        "tray_state_name": slot.tray_state_name,
        "raw": redact_sensitive(slot.raw),
        "updated_at": slot.updated_at,
    }


def _active_slot_from_snapshot(snapshot: DeviceStatusSnapshot | None, slots: list[AmsSlot]) -> AmsSlot | None:
    if snapshot is None or not isinstance(snapshot.ams_status, dict):
        return None
    active_global = _first_set_bit(snapshot.ams_status.get("tray_hall_out_bits"))
    if active_global is not None:
        for slot in slots:
            if str(active_global) == _global_tray_id(slot):
                return slot
    tray_now = snapshot.ams_status.get("tray_now")
    if tray_now is None or tray_now == "":
        return None
    text = str(tray_now)
    for slot in slots:
        if text in {str(slot.tray_id), _global_tray_id(slot)} and len({item.ams_id for item in slots}) == 1:
            return slot
    for slot in slots:
        if text == _global_tray_id(slot):
            return slot
    return None


def _active_slot_payload(slot: AmsSlot) -> dict[str, Any]:
    context = _filament_context(slot)
    return {
        "ams_id": slot.ams_id,
        "tray_id": slot.tray_id,
        "user_tray_id": _user_tray_id(slot),
        "slot_label": _slot_label(slot),
        "global_tray_id": _global_tray_id(slot),
        "location_label": _location_label(slot, None),
        "material": slot.material,
        "color": slot.color,
        "filament_brand_id": context["brand_id"],
        "filament_brand_name": context["brand_name"],
        "filament_material": context["material"],
        "filament_series": context["series"],
        "tray_id_name": slot.tray_id_name,
        "tray_color_name": slot.tray_color_name,
        "remain": slot.remain,
    }


def _filament_context(slot: AmsSlot) -> dict[str, Any]:
    sku = slot.filament_spool.sku if slot.filament_spool and slot.filament_spool.sku else None
    if sku is None or sku.type_series is None:
        return {"brand_id": None, "brand_name": None, "material": None, "series": None}
    type_series = sku.type_series
    brand = type_series.brand
    return {
        "brand_id": brand.id if brand else None,
        "brand_name": brand.name if brand else None,
        "material": type_series.material_type,
        "series": type_series.series_name,
    }


def _global_tray_id(slot: AmsSlot) -> str:
    ams = _int(slot.ams_id)
    tray = _int(slot.tray_id)
    if ams is None or tray is None:
        return f"{slot.ams_id}:{slot.tray_id}"
    return str((_ams_global_index(ams) * 4) + tray)


def _ams_global_index(ams_id: int) -> int:
    if ams_id >= 128:
        return ams_id - 124
    return ams_id


def _first_set_bit(value: object) -> int | None:
    mask = _bitmask(value)
    if mask is None or mask <= 0:
        return None
    return (mask & -mask).bit_length() - 1


def _bitmask(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def _location_label(slot: AmsSlot, display_name: str | None) -> str:
    ams_label = display_name or f"AMS {slot.ams_id}"
    return f"{ams_label} / {_slot_label(slot)}"


def _slot_label(slot: AmsSlot) -> str:
    user_tray = _user_tray_id(slot)
    if user_tray is None:
        return f"Slot {slot.tray_id}"
    return f"Slot {user_tray}"


def _user_tray_id(slot: AmsSlot) -> int | None:
    tray = _int(slot.tray_id)
    if tray is None:
        return None
    return tray + 1


def _metric_value(row: DeviceMetricSample) -> float | None:
    if row.value_float is not None:
        return float(row.value_float)
    try:
        return float(row.value_text) if row.value_text is not None else None
    except (TypeError, ValueError):
        return None


def _stats(values: Any) -> dict[str, float | None]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return {"min": None, "max": None, "avg": None}
    return {"min": min(numeric), "max": max(numeric), "avg": sum(numeric) / len(numeric)}


def _is_sqlite_database_locked(value: object) -> bool:
    text = str(value).lower()
    return "database is locked" in text or "database is busy" in text


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _slot_state(slot: AmsSlot) -> str | None:
    if slot.slot_state:
        normalized = _slot_state_name(slot.slot_state)
        if normalized is not None and not normalized.startswith("unknown:"):
            return normalized
    return slot.state_name or slot.tray_state_name or slot.slot_state


def _same_history_sample(previous: AmsSlotHistorySample, values: dict[str, Any]) -> bool:
    return all(getattr(previous, key) == value for key, value in values.items())


def _delete_old_history(db: Session, *, printer_id: int, now: datetime) -> None:
    cutoff = _aware(now) - HISTORY_RETENTION_PERIOD
    db.execute(
        delete(AmsSlotHistorySample).where(
            AmsSlotHistorySample.printer_id == printer_id,
            AmsSlotHistorySample.sampled_at < cutoff,
        ).execution_options(synchronize_session=False)
    )


def _rfid_status(raw: dict[str, Any] | None) -> str | None:
    if not isinstance(raw, dict):
        return None
    for key in ("rfid_status", "tray_rfid_status", "tag_uid", "tray_uuid"):
        value = raw.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
