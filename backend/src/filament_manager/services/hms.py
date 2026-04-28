from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import PrinterEvent, utc_now


@lru_cache(maxsize=1)
def hms_code_table() -> dict[str, dict[str, Any]]:
    data = resources.files("filament_manager.data").joinpath("hms_codes.json").read_text(encoding="utf-8")
    rows = json.loads(data)
    table: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("short_code"):
            table[str(row["short_code"]).upper()] = dict(row)
    return table


def list_hms_codes() -> list[dict[str, Any]]:
    return sorted(hms_code_table().values(), key=lambda item: str(item.get("short_code") or ""))


def get_hms_code(short_code: str) -> dict[str, Any] | None:
    return hms_code_table().get(short_code.upper())


def enrich_hms_error(error: dict[str, Any]) -> dict[str, Any]:
    short_code = str(error.get("short_code") or "").upper()
    info = hms_code_table().get(short_code) if short_code else None
    if info:
        error["known"] = bool(info.get("known", True))
        error["actionable"] = bool(info.get("actionable", True))
        error["module_name"] = info.get("module") or error.get("module_name")
        error["message"] = info.get("message_en") or info.get("message_zh") or error.get("message")
        error["message_zh"] = info.get("message_zh")
        error["message_en"] = info.get("message_en")
        error["suggestion_zh"] = info.get("suggestion_zh")
        error["suggestion_en"] = info.get("suggestion_en")
        if info.get("wiki_url"):
            error["wiki_url"] = info["wiki_url"]
        return error

    error["known"] = False
    error["actionable"] = True
    error["message"] = "未知 HMS 码，打印机未必会弹屏提示。"
    error["message_zh"] = "未知 HMS 码，打印机未必会弹屏提示。"
    error["message_en"] = "Unknown HMS code; the printer may not show an on-screen prompt."
    error["suggestion_zh"] = "保留 attr、code 和 source 原始字段，用于后续对照官方 Wiki 或日志排查。"
    error["suggestion_en"] = "Keep raw attr, code, and source fields for later comparison with official wiki or logs."
    return error


def hms_code_stats(
    db: Session,
    *,
    short_code: str,
    printer_id: int | None = None,
    days: int = 30,
) -> dict[str, Any]:
    normalized = short_code.upper()
    cutoff = utc_now() - timedelta(days=days)
    query = (
        select(PrinterEvent)
        .where(
            PrinterEvent.event_type.in_(("hms.error", "hms.recovered")),
            PrinterEvent.created_at >= cutoff,
        )
        .order_by(PrinterEvent.created_at.desc(), PrinterEvent.id.desc())
    )
    if printer_id is not None:
        query = query.where(PrinterEvent.printer_id == printer_id)
    rows = [
        row
        for row in db.scalars(query).all()
        if _event_short_code(row) == normalized
    ]
    active = [row for row in rows if _event_active(row) is not False and row.event_type == "hms.error"]
    recovered = [row for row in rows if _event_active(row) is False or row.event_type == "hms.recovered"]
    affected = sorted({row.printer_id for row in rows})
    last_seen = rows[0].created_at if rows else None
    last_recovered = recovered[0].created_at if recovered else None
    return {
        "short_code": normalized,
        "printer_id": printer_id,
        "days": days,
        "recent_count": len(rows),
        "active_count": len(active),
        "recovered_count": len(recovered),
        "affected_printers": affected,
        "last_seen_at": last_seen,
        "last_recovered_at": last_recovered,
        "high_frequency": len(rows) >= max(3, days // 7),
        "recent_events": [
            {
                "id": row.id,
                "printer_id": row.printer_id,
                "event_type": row.event_type,
                "severity": row.severity,
                "message": row.message,
                "active": _event_active(row),
                "created_at": row.created_at,
                "data": row.data,
            }
            for row in rows[:20]
        ],
    }


def _event_short_code(event: PrinterEvent) -> str | None:
    data = event.data if isinstance(event.data, dict) else {}
    value = data.get("short_code")
    if value:
        return str(value).upper()
    attr = _as_int(data.get("attr"))
    code = _as_int(data.get("code_value"))
    if attr is None or code is None:
        return None
    module = (attr >> 16) & 0xFFFF
    return f"{module:04X}_{code & 0xFFFF:04X}"


def _event_active(event: PrinterEvent) -> bool | None:
    data = event.data if isinstance(event.data, dict) else {}
    value = data.get("active")
    return value if isinstance(value, bool) else None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.lower().startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
