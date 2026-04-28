from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import (
    AmsSlotHistorySample,
    InventoryEvent,
    MaintenanceHistory,
    NotificationRule,
    NotificationTarget,
    Printer,
    PrinterEvent,
    PrintLogEntry,
)
from filament_manager.services.notifications import redact_notification_config

DEFAULT_SECTIONS = ("config", "print_logs", "ams_history", "maintenance_history", "events", "notifications")


def export_json_payload(db: Session, sections: list[str] | None = None) -> dict[str, Any]:
    selected = _selected_sections(sections)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": selected,
    }
    for section in selected:
        payload[section] = _section_payload(db, section)
    return redact_sensitive(payload)  # type: ignore[return-value]


def export_json_bytes(db: Session, sections: list[str] | None = None) -> bytes:
    return json.dumps(export_json_payload(db, sections), ensure_ascii=False, default=str, indent=2).encode("utf-8")


def export_csv_zip_bytes(db: Session, sections: list[str] | None = None) -> bytes:
    selected = _selected_sections(sections)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for section in selected:
            rows = _flatten_rows(_section_payload(db, section))
            archive.writestr(f"{section}.csv", _csv_bytes(rows))
        archive.writestr("manifest.json", json.dumps({"sections": selected}, ensure_ascii=False, indent=2))
    return buffer.getvalue()


def _selected_sections(sections: list[str] | None) -> list[str]:
    if not sections:
        return list(DEFAULT_SECTIONS)
    allowed = set(DEFAULT_SECTIONS)
    return [section for section in sections if section in allowed]


def _section_payload(db: Session, section: str) -> Any:
    if section == "config":
        printers = list(db.scalars(select(Printer).order_by(Printer.id)).all())
        return {
            "printers": [
                {
                    "id": printer.id,
                    "name": f"printer-{index + 1}",
                    "host": f"host-{index + 1}",
                    "port": printer.port,
                    "serial": f"serial-{index + 1}",
                    "tls_enabled": printer.tls_enabled,
                    "certificate_verify": printer.certificate_verify,
                    "enabled": printer.enabled,
                    "connection_status": printer.connection_status,
                    "print_hours_offset": printer.print_hours_offset,
                    "created_at": printer.created_at,
                    "updated_at": printer.updated_at,
                }
                for index, printer in enumerate(printers)
            ]
        }
    if section == "print_logs":
        return [_model_dict(row) for row in db.scalars(select(PrintLogEntry).order_by(PrintLogEntry.id)).all()]
    if section == "ams_history":
        return [_model_dict(row) for row in db.scalars(select(AmsSlotHistorySample).order_by(AmsSlotHistorySample.id)).all()]
    if section == "maintenance_history":
        return [_model_dict(row) for row in db.scalars(select(MaintenanceHistory).order_by(MaintenanceHistory.id)).all()]
    if section == "events":
        return {
            "printer_events": [_model_dict(row) for row in db.scalars(select(PrinterEvent).order_by(PrinterEvent.id)).all()],
            "inventory_events": [_model_dict(row) for row in db.scalars(select(InventoryEvent).order_by(InventoryEvent.id)).all()],
        }
    if section == "notifications":
        targets = []
        for row in db.scalars(select(NotificationTarget).order_by(NotificationTarget.id)).all():
            item = _model_dict(row)
            item["config"] = redact_notification_config(row.config)
            item["display_config"] = redact_notification_config(row.display_config)
            targets.append(item)
        return {
            "targets": targets,
            "rules": [_model_dict(row) for row in db.scalars(select(NotificationRule).order_by(NotificationRule.id)).all()],
        }
    return {}


def _model_dict(row: Any) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"access_code"}
    }


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
