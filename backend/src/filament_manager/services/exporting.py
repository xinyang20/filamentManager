from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import (
    AmsLabel,
    AmsSlot,
    AmsSlotHistorySample,
    AmsUnit,
    DeviceMetricSample,
    DeviceStatusSnapshot,
    FilamentBrand,
    FilamentColorMapping,
    FilamentSku,
    FilamentSpool,
    FilamentSpoolEvent,
    FilamentStockBalance,
    FilamentTypeSeries,
    MaintenanceHistory,
    MaintenanceType,
    NotificationDelivery,
    NotificationRule,
    NotificationTarget,
    Printer,
    PrinterEvent,
    PrinterMaintenance,
    PrinterStateSnapshot,
    PrinterStorageFile,
    PrintJob,
    PrintLogEntry,
    RawMqttMessage,
    TimelapseNote,
)
from filament_manager.services.notifications import redact_notification_config

BACKUP_FORMAT = "filament-manager-backup"
BACKUP_VERSION = 1

DEFAULT_SECTIONS = (
    "config",
    "filament_catalog",
    "filament_color_mappings",
    "ams_current",
    "print_logs",
    "ams_history",
    "maintenance_history",
    "events",
    "notifications",
    "storage",
    "telemetry",
)

SECTION_MODELS: dict[str, dict[str, Any]] = {
    "config": {"printers": Printer},
    "filament_catalog": {
        "brands": FilamentBrand,
        "type_series": FilamentTypeSeries,
        "skus": FilamentSku,
        "stock_balances": FilamentStockBalance,
        "spools": FilamentSpool,
    },
    "filament_color_mappings": {"color_mappings": FilamentColorMapping},
    "ams_current": {"ams_units": AmsUnit, "ams_labels": AmsLabel, "ams_slots": AmsSlot},
    "print_logs": {"print_jobs": PrintJob, "print_log_entries": PrintLogEntry},
    "ams_history": {"ams_slot_history_samples": AmsSlotHistorySample},
    "maintenance_history": {
        "maintenance_types": MaintenanceType,
        "printer_maintenance": PrinterMaintenance,
        "maintenance_history": MaintenanceHistory,
    },
    "events": {"printer_events": PrinterEvent, "inventory_events": FilamentSpoolEvent},
    "notifications": {
        "targets": NotificationTarget,
        "rules": NotificationRule,
        "deliveries": NotificationDelivery,
    },
    "storage": {"printer_storage_files": PrinterStorageFile, "timelapse_notes": TimelapseNote},
    "telemetry": {
        "raw_mqtt_messages": RawMqttMessage,
        "printer_state_snapshots": PrinterStateSnapshot,
        "device_status_snapshots": DeviceStatusSnapshot,
        "device_metric_samples": DeviceMetricSample,
    },
}

RESTORE_ORDER = (
    Printer,
    MaintenanceType,
    FilamentBrand,
    FilamentTypeSeries,
    FilamentSku,
    FilamentStockBalance,
    FilamentSpool,
    FilamentColorMapping,
    RawMqttMessage,
    PrinterStateSnapshot,
    DeviceStatusSnapshot,
    DeviceMetricSample,
    AmsUnit,
    AmsLabel,
    AmsSlot,
    AmsSlotHistorySample,
    PrinterStorageFile,
    TimelapseNote,
    PrintJob,
    PrintLogEntry,
    PrinterMaintenance,
    MaintenanceHistory,
    PrinterEvent,
    FilamentSpoolEvent,
    NotificationTarget,
    NotificationRule,
    NotificationDelivery,
)

CLEAR_ORDER = tuple(reversed(RESTORE_ORDER))


def export_json_payload(
    db: Session,
    sections: list[str] | None = None,
    *,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    selected = _selected_sections(sections)
    payload: dict[str, Any] = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": selected,
    }
    for section in selected:
        payload[section] = _section_payload(db, section, redact=not include_sensitive)
    return payload if include_sensitive else redact_sensitive(payload)  # type: ignore[return-value]


def export_json_bytes(
    db: Session,
    sections: list[str] | None = None,
    *,
    include_sensitive: bool = False,
) -> bytes:
    return json.dumps(
        export_json_payload(db, sections, include_sensitive=include_sensitive),
        ensure_ascii=False,
        default=str,
        indent=2,
    ).encode("utf-8")


def export_csv_zip_bytes(db: Session, sections: list[str] | None = None) -> bytes:
    selected = _selected_sections(sections)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for section in selected:
            rows = _flatten_rows(_section_payload(db, section, redact=True))
            archive.writestr(f"{section}.csv", _csv_bytes(rows))
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": BACKUP_FORMAT,
                    "version": BACKUP_VERSION,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "sections": selected,
                    "restorable": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return buffer.getvalue()


def import_json_payload(db: Session, payload: dict[str, Any], mode: str = "merge") -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Import payload must be a JSON object")
    if mode not in {"merge", "replace"}:
        raise ValueError("Import mode must be merge or replace")

    selected = _selected_sections(_payload_sections(payload))
    counts: dict[str, int] = {}
    if mode == "replace":
        _clear_restore_tables(db)

    for section in selected:
        section_payload = payload.get(section)
        if section_payload is None:
            continue
        section_models = SECTION_MODELS[section]
        for key, model in section_models.items():
            if isinstance(section_payload, list) and len(section_models) > 1:
                continue
            rows = _payload_rows(section_payload, key)
            if rows:
                counts[f"{section}.{key}"] = _upsert_rows(db, model, rows)

    db.commit()
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "mode": mode,
        "sections": selected,
        "counts": counts,
    }


def _selected_sections(sections: list[str] | None) -> list[str]:
    if not sections:
        return list(DEFAULT_SECTIONS)
    allowed = set(DEFAULT_SECTIONS)
    return [section for section in sections if section in allowed]


def _payload_sections(payload: dict[str, Any]) -> list[str] | None:
    value = payload.get("sections")
    if not isinstance(value, list):
        return None
    return [str(item) for item in value]


def _section_payload(db: Session, section: str, *, redact: bool) -> Any:
    if section == "config":
        payload = _models_payload(db, SECTION_MODELS[section])
        if redact:
            for index, printer in enumerate(payload["printers"]):
                printer["name"] = f"printer-{index + 1}"
                printer["host"] = f"host-{index + 1}"
                printer["serial"] = f"serial-{index + 1}"
                printer["access_code"] = None
        return payload
    if section == "notifications":
        payload = _models_payload(db, SECTION_MODELS[section])
        if redact:
            for item in payload["targets"]:
                item["config"] = redact_notification_config(item.get("config") or {})
                item["display_config"] = redact_notification_config(item.get("display_config") or {})
        return payload
    if section in SECTION_MODELS:
        return _models_payload(db, SECTION_MODELS[section])
    return {}


def _models_payload(db: Session, models: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        key: [_model_dict(row) for row in db.scalars(select(model).order_by(*_order_columns(model))).all()]
        for key, model in models.items()
    }


def _order_columns(model: Any) -> list[Any]:
    columns = list(model.__table__.primary_key.columns)
    return columns or [model.__table__.columns[0]]


def _model_dict(row: Any) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
    }


def _payload_rows(section_payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(section_payload, list):
        return [row for row in section_payload if isinstance(row, dict)]
    if isinstance(section_payload, dict):
        value = section_payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _upsert_rows(db: Session, model: Any, rows: list[dict[str, Any]]) -> int:
    count = 0
    pk_columns = list(model.__table__.primary_key.columns)
    for row in rows:
        data = _coerce_model_data(model, row)
        identity = _row_identity(pk_columns, data)
        if identity is None:
            continue
        existing = db.get(model, identity)
        if existing is None:
            db.add(model(**data))
        else:
            for key, value in data.items():
                setattr(existing, key, value)
        count += 1
    db.flush()
    return count


def _coerce_model_data(model: Any, row: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in model.__table__.columns:
        if column.name not in row:
            continue
        value = row[column.name]
        if isinstance(column.type, DateTime):
            value = _parse_datetime(value)
        data[column.name] = value
    return data


def _row_identity(pk_columns: list[Any], data: dict[str, Any]) -> Any:
    values = [data.get(column.name) for column in pk_columns]
    if any(value is None for value in values):
        return None
    return values[0] if len(values) == 1 else tuple(values)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clear_restore_tables(db: Session) -> None:
    for model in CLEAR_ORDER:
        db.query(model).delete(synchronize_session=False)
    db.flush()


def _flatten_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [_flat_dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, list):
                for row in item:
                    if isinstance(row, dict):
                        rows.append({"section": key, **_flat_dict(row)})
            elif isinstance(item, dict):
                rows.append({"section": key, **_flat_dict(item)})
        return rows
    return []


def _flat_dict(value: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, item in redact_sensitive(value).items():  # type: ignore[union-attr]
        if isinstance(item, (dict, list)):
            row[key] = json.dumps(item, ensure_ascii=False, default=str)
        else:
            row[key] = item
    return row


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = io.StringIO()
    if not rows:
        text.write("")
        return text.getvalue().encode("utf-8")
    fieldnames = sorted({key for row in rows for key in row.keys()})
    writer = csv.DictWriter(text, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return text.getvalue().encode("utf-8")
