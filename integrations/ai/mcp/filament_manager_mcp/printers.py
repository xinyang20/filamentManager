from __future__ import annotations

from typing import Any

from integrations.ai.shared.schemas import ListPrintersParams, PrinterIdParams

from .tools import (
    api_get,
    as_dict,
    as_list,
    compact_dict,
    first_present,
    map_hms_error,
    map_printer,
    safe_int,
    safe_print_name,
    success,
    tool_error,
)


async def get_system_health() -> dict[str, Any]:
    try:
        payload = as_dict(await api_get("/health"))
        return success({"status": payload.get("status") or "unknown", "backend_reachable": True})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


async def list_printers(include_status: bool = True) -> dict[str, Any]:
    try:
        ListPrintersParams(include_status=include_status)
        payload = as_list(await api_get("/printers"))
        printers = []
        for item in payload:
            if isinstance(item, dict):
                printer = map_printer(item)
                if not include_status:
                    printer.pop("connection_status", None)
                    printer.pop("last_sync_at", None)
                    printer.pop("last_error_summary", None)
                printers.append(printer)
        return success({"printers": printers})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


async def get_printer_overview(printer_id: int) -> dict[str, Any]:
    try:
        params = PrinterIdParams(printer_id=printer_id)
        payload = as_dict(await api_get(f"/printers/{params.printer_id}/dashboard"))
        printer = map_printer(as_dict(payload.get("printer")))
        state = as_dict(payload.get("state"))
        snapshot = as_dict(payload.get("device_snapshot"))
        print_status = as_dict(snapshot.get("print_status"))
        temperatures = as_dict(snapshot.get("temperatures"))
        print_data = compact_dict(
            {
                "state": first_present(state.get("gcode_state"), print_status.get("gcode_state"), print_status.get("user_state")),
                "progress_percent": first_present(state.get("mc_percent"), print_status.get("mc_percent")),
                "remaining_minutes": first_present(state.get("mc_remaining_time"), print_status.get("mc_remaining_time")),
                "print_name": safe_print_name(state) or safe_print_name(print_status),
                "current_layer": safe_int(first_present(state.get("layer_current"), print_status.get("layer_num"))),
                "total_layers": safe_int(first_present(state.get("layer_total"), print_status.get("total_layer_num"))),
                "failure_reason": first_present(state.get("error_code"), print_status.get("mc_print_error_code")),
            }
        )
        if print_data.get("failure_reason") in {"0", 0, ""}:
            print_data["failure_reason"] = None
        data = {
            "printer": {
                "printer_id": printer.get("printer_id"),
                "name": printer.get("name"),
                "connection_status": printer.get("connection_status"),
                "last_sync_at": printer.get("last_sync_at"),
            },
            "print": compact_dict(print_data),
            "temperatures": compact_dict(
                {
                    "bed_c": first_present(temperatures.get("bed"), temperatures.get("bed_c")),
                    "nozzle_c": first_present(temperatures.get("nozzle"), temperatures.get("nozzle_c")),
                    "chamber_c": first_present(temperatures.get("chamber"), temperatures.get("chamber_c")),
                }
            ),
            "fans": as_dict(snapshot.get("fans")),
            "hms_errors": [map_hms_error(item) for item in as_list(snapshot.get("hms_errors")) if isinstance(item, dict)],
            "maintenance_due_count": payload.get("maintenance_due_count") or 0,
        }
        return success(data)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
