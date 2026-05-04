from __future__ import annotations

from typing import Any

from integrations.ai.shared.schemas import MaintenanceOverviewParams

from .tools import api_get, as_dict, as_list, compact_dict, safe_text, success, tool_error


def _map_maintenance_item(item: dict[str, Any]) -> dict[str, Any]:
    maintenance_type = as_dict(item.get("maintenance_type"))
    due_status = safe_text(item.get("due_status"), max_length=40)
    action = "No action needed."
    if due_status == "due":
        action = "Perform this maintenance item from the FilamentManager frontend."
    elif due_status == "soon":
        action = "Plan this maintenance item soon from the FilamentManager frontend."
    return compact_dict(
        {
            "printer_id": item.get("printer_id"),
            "printer_name": safe_text(item.get("printer_name"), max_length=120),
            "target_type": safe_text(item.get("target_type"), max_length=80),
            "target_label": safe_text(item.get("target_label"), max_length=120),
            "name": safe_text(maintenance_type.get("name"), max_length=160),
            "description": safe_text(maintenance_type.get("description"), max_length=500),
            "due_status": due_status,
            "hours_until_due": item.get("hours_until_due"),
            "hours_since_last": item.get("hours_since_last"),
            "last_performed_at": item.get("last_performed_at"),
            "recommended_human_action": action,
        }
    )


async def get_maintenance_overview(printer_id: int | None = None, include_ok: bool = False) -> dict[str, Any]:
    try:
        params = MaintenanceOverviewParams(printer_id=printer_id, include_ok=include_ok)
        overview = as_dict(await api_get("/maintenance/overview"))
        if params.printer_id is not None:
            raw_items = as_list(await api_get(f"/printers/{params.printer_id}/maintenance"))
        else:
            raw_items = as_list(overview.get("items"))
        items = [
            _map_maintenance_item(item)
            for item in raw_items
            if isinstance(item, dict) and (params.include_ok or item.get("due_status") != "ok")
        ]
        data = {
            "summary": compact_dict(
                {
                    "total_items": overview.get("total_items"),
                    "due_count": overview.get("due_count"),
                    "soon_count": overview.get("soon_count"),
                    "ok_count": overview.get("ok_count"),
                }
            ),
            "items": items,
        }
        return success(data)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
