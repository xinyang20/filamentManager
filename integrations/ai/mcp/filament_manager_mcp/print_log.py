from __future__ import annotations

from typing import Any

from integrations.ai.shared.schemas import PrintLogSummaryParams, RecentPrintLogsParams

from .tools import (
    ai_status_to_backend_status,
    api_get,
    as_dict,
    as_list,
    backend_status_to_ai_status,
    compact_dict,
    iso_days_ago,
    map_hms_error,
    safe_print_name,
    safe_text,
    success,
    tool_error,
)


async def get_print_log_summary(printer_id: int | None = None, days: int = 7) -> dict[str, Any]:
    try:
        params = PrintLogSummaryParams(printer_id=printer_id, days=days)
        date_from = iso_days_ago(params.days)
        analytics = as_dict(
            await api_get(
                "/print-log/analytics",
                params={"printer_id": params.printer_id, "from": date_from, "bucket": "day"},
            )
        )
        warnings: list[str] = []
        if params.printer_id is None:
            try:
                summary = as_dict(await api_get("/print-log/summary", params={"from": date_from}))
                source = summary or analytics
            except Exception:  # noqa: BLE001
                source = analytics
                warnings.append("Summary endpoint was unavailable; analytics data was used.")
        else:
            source = analytics
        data = {
            "printer_id": params.printer_id,
            "days": params.days,
            "total": source.get("total", 0),
            "running": source.get("running", 0),
            "success": source.get("succeeded", 0),
            "failed": source.get("failed", 0),
            "cancelled": source.get("cancelled", 0),
            "success_rate": source.get("success_rate", 0.0),
            "average_duration_seconds": source.get("average_duration_seconds"),
            "longest_duration_seconds": source.get("longest_duration_seconds"),
            "daily": source.get("by_date", []),
            "failure_reasons": source.get("by_failure_reason", []),
            "hms": source.get("by_hms", []),
        }
        return success(data, warnings=warnings)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


def map_print_log(item: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "print_log_id": item.get("id") or item.get("print_log_id"),
            "printer_name": safe_text(item.get("printer_name_snapshot") or item.get("printer_name"), max_length=120),
            "print_name": safe_print_name(item),
            "status": backend_status_to_ai_status(safe_text(item.get("status"), max_length=40)),
            "started_at": item.get("started_at"),
            "finished_at": item.get("finished_at"),
            "duration_seconds": item.get("duration_seconds"),
            "final_progress": item.get("final_progress"),
            "layer_current": item.get("layer_current"),
            "layer_total": item.get("layer_total"),
            "failure_reason": safe_text(item.get("failure_reason"), max_length=120),
            "hms_summary": [map_hms_error(hms) for hms in as_list(item.get("hms_summary")) if isinstance(hms, dict)],
        }
    )


async def list_recent_print_logs(
    printer_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    try:
        params = RecentPrintLogsParams(printer_id=printer_id, status=status, limit=limit)
        payload = as_dict(
            await api_get(
                "/print-log",
                params={
                    "printer_id": params.printer_id,
                    "status": ai_status_to_backend_status(params.status),
                    "limit": params.limit,
                    "offset": 0,
                },
            )
        )
        return success({"items": [map_print_log(item) for item in as_list(payload.get("items")) if isinstance(item, dict)]})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
