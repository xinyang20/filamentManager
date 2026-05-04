from __future__ import annotations

from typing import Any

from integrations.ai.shared.schemas import HmsCodeInfoParams, RecentEventsParams

from .tools import api_get, as_dict, as_list, compact_dict, map_event, safe_text, success, tool_error


async def get_recent_events(
    printer_id: int | None = None,
    severity: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    try:
        params = RecentEventsParams(printer_id=printer_id, severity=severity, limit=limit)
        payload = as_list(
            await api_get(
                "/events",
                params={"printer_id": params.printer_id, "severity": params.severity, "limit": params.limit},
            )
        )
        return success({"events": [map_event(item) for item in payload if isinstance(item, dict)]})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


async def get_hms_code_info(short_code: str) -> dict[str, Any]:
    try:
        params = HmsCodeInfoParams(short_code=short_code)
        code_payload = as_dict(await api_get(f"/hms/codes/{params.short_code}"))
        warnings: list[str] = []
        stats_payload: dict[str, Any] = {}
        try:
            stats_payload = as_dict(await api_get(f"/hms/codes/{params.short_code}/stats"))
        except Exception:  # noqa: BLE001
            warnings.append("HMS code stats were unavailable.")
        data = {
            "short_code": safe_text(code_payload.get("short_code"), max_length=80),
            "module": safe_text(code_payload.get("module"), max_length=80),
            "severity": safe_text(code_payload.get("severity"), max_length=40),
            "message_zh": safe_text(code_payload.get("message_zh"), max_length=500),
            "message_en": safe_text(code_payload.get("message_en"), max_length=500),
            "suggestion_zh": safe_text(code_payload.get("suggestion_zh"), max_length=1000),
            "suggestion_en": safe_text(code_payload.get("suggestion_en"), max_length=1000),
            "wiki_url": safe_text(code_payload.get("wiki_url"), max_length=240),
            "known": code_payload.get("known"),
            "actionable": code_payload.get("actionable"),
            "stats": compact_dict(
                {
                    "recent_count": stats_payload.get("recent_count"),
                    "active_count": stats_payload.get("active_count"),
                    "recovered_count": stats_payload.get("recovered_count"),
                    "affected_printers": stats_payload.get("affected_printers"),
                    "last_seen_at": stats_payload.get("last_seen_at"),
                    "last_recovered_at": stats_payload.get("last_recovered_at"),
                    "high_frequency": stats_payload.get("high_frequency"),
                    "recent_events": [
                        map_event(item) for item in as_list(stats_payload.get("recent_events")) if isinstance(item, dict)
                    ],
                }
            ),
        }
        return success(data, warnings=warnings)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
