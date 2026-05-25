from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import FilamentSpoolEvent, PrinterEvent
from filament_manager.db.session import SessionLocal


SSE_EVENT_MAP = {
    "hms.error": "hms.error.active",
    "hms.recovered": "hms.error.recovered",
    "slot.identity_fallback": "ams.slot.updated",
    "spool.unidentified": "ams.slot.updated",
    "spool.discovered": "ams.slot.updated",
    "spool.location_changed": "ams.slot.updated",
    "printer.connection.restored": "printer.status.updated",
    "printer.connection.disconnected": "printer.status.updated",
    "storage.scan": "storage.scan.finished",
    "storage.scan_failed": "storage.scan.failed",
    "print.started": "printer.status.updated",
    "print.paused": "printer.status.updated",
    "print.resumed": "printer.status.updated",
    "print.finished": "printer.status.updated",
    "print.failed": "printer.status.updated",
    "print.cancelled": "printer.status.updated",
}


def list_unified_events(
    db: Session,
    *,
    printer_id: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    active: bool | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    printer_query = select(PrinterEvent)
    if printer_id is not None:
        printer_query = printer_query.where(PrinterEvent.printer_id == printer_id)
    if event_type:
        printer_query = printer_query.where(PrinterEvent.event_type == event_type)
    if severity:
        printer_query = printer_query.where(PrinterEvent.severity == severity)
    if since:
        printer_query = printer_query.where(PrinterEvent.created_at >= since)

    inventory_query = select(FilamentSpoolEvent)
    if event_type:
        inventory_query = inventory_query.where(FilamentSpoolEvent.event_type == event_type)
    if since:
        inventory_query = inventory_query.where(FilamentSpoolEvent.created_at >= since)

    rows = [_printer_event_payload(row) for row in db.scalars(printer_query).all()]
    if printer_id is None and severity is None:
        rows.extend(_inventory_event_payload(row) for row in db.scalars(inventory_query).all())

    if active is not None:
        rows = [row for row in rows if row.get("active") is active]
    rows.sort(key=lambda row: (row["created_at"], row["id"]), reverse=True)
    return rows[:limit]


async def sse_event_generator(poll_interval: float = 2.0) -> Iterable[str]:
    last_printer_id = 0
    last_inventory_id = 0
    while True:
        if SessionLocal is None:
            await asyncio.sleep(poll_interval)
            yield _sse_frame("heartbeat", {"ok": True})
            continue

        with SessionLocal() as db:
            printer_events = list(
                db.scalars(
                    select(PrinterEvent)
                    .where(PrinterEvent.id > last_printer_id)
                    .order_by(PrinterEvent.id)
                    .limit(100)
                ).all()
            )
            inventory_events = list(
                db.scalars(
                    select(FilamentSpoolEvent)
                    .where(FilamentSpoolEvent.id > last_inventory_id)
                    .order_by(FilamentSpoolEvent.id)
                    .limit(100)
                ).all()
            )

        for event in printer_events:
            last_printer_id = max(last_printer_id, event.id)
            payload = _printer_event_payload(event)
            yield _sse_frame(_sse_type(payload), payload)
        for event in inventory_events:
            last_inventory_id = max(last_inventory_id, event.id)
            payload = _inventory_event_payload(event)
            yield _sse_frame(_sse_type(payload), payload)

        if not printer_events and not inventory_events:
            yield _sse_frame("heartbeat", {"ok": True})
        await asyncio.sleep(poll_interval)


def _printer_event_payload(event: PrinterEvent) -> dict[str, Any]:
    data = redact_sensitive(event.data or {})
    return {
        "id": event.id,
        "source": "printer",
        "printer_id": event.printer_id,
        "spool_id": None,
        "type": event.event_type,
        "event_type": event.event_type,
        "severity": event.severity,
        "active": _active_from_data(data),
        "message": event.message,
        "dedupe_key": event.dedupe_key,
        "data": data,
        "created_at": event.created_at,
    }


def _inventory_event_payload(event: FilamentSpoolEvent) -> dict[str, Any]:
    data = redact_sensitive(event.data or {})
    return {
        "id": event.id,
        "source": "inventory",
        "printer_id": event.printer_id,
        "spool_id": event.spool_id,
        "type": event.event_type,
        "event_type": event.event_type,
        "severity": "info",
        "active": _active_from_data(data),
        "message": event.message,
        "dedupe_key": None,
        "data": {
            **(data if isinstance(data, dict) else {}),
            "sku_id": event.sku_id,
            "ams_id": event.ams_id,
            "tray_id": event.tray_id,
            "previous": event.previous,
            "current": event.current,
            "quantity_delta": event.quantity_delta,
            "note": event.note,
        },
        "created_at": event.created_at,
    }


def _active_from_data(data: Any) -> bool | None:
    if isinstance(data, dict) and isinstance(data.get("active"), bool):
        return data["active"]
    return None


def _sse_type(payload: dict[str, Any]) -> str:
    if payload.get("type") == "hms.error" and payload.get("active") is False:
        return "hms.error.recovered"
    return SSE_EVENT_MAP.get(str(payload.get("type") or ""), "device.snapshot.updated")


def _sse_frame(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str, ensure_ascii=False)}\n\n"
