from __future__ import annotations

from typing import Any

from integrations.ai.shared.schemas import AmsOverviewParams

from .tools import api_get, as_dict, as_list, compact_dict, safe_text, success, tool_error


def _slot_has_filament(slot: dict[str, Any]) -> bool:
    return any(
        slot.get(key) not in (None, "", 0)
        for key in ("material", "series", "color", "remain", "filament_spool_id", "spool_id")
    )


def map_ams_slot(slot: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "ams_id": safe_text(slot.get("ams_id"), max_length=40),
            "tray_id": safe_text(slot.get("tray_id"), max_length=40),
            "slot_label": safe_text(slot.get("slot_label") or slot.get("location_label"), max_length=80),
            "material": safe_text(slot.get("material") or slot.get("filament_material"), max_length=40),
            "series": safe_text(slot.get("series") or slot.get("filament_series"), max_length=120),
            "color": safe_text(slot.get("color") or slot.get("color_hex"), max_length=16),
            "remain": slot.get("remain"),
            "state_name": safe_text(slot.get("state_name") or slot.get("tray_state_name"), max_length=80),
            "is_active": slot.get("is_active"),
            "is_transitioning": slot.get("is_transitioning"),
            "filament_spool_id": slot.get("filament_spool_id") or slot.get("spool_id"),
            "filament_brand_name": safe_text(slot.get("filament_brand_name"), max_length=120),
        }
    )


async def get_ams_overview(printer_id: int, include_empty_slots: bool = True) -> dict[str, Any]:
    try:
        params = AmsOverviewParams(printer_id=printer_id, include_empty_slots=include_empty_slots)
        payload = as_dict(await api_get(f"/printers/{params.printer_id}/ams/overview"))
        units = []
        for unit in as_list(payload.get("units")):
            if not isinstance(unit, dict):
                continue
            slots = []
            for slot in as_list(unit.get("slots")):
                if not isinstance(slot, dict):
                    continue
                if not params.include_empty_slots and not _slot_has_filament(slot):
                    continue
                slots.append(map_ams_slot(slot))
            units.append(
                compact_dict(
                    {
                        "ams_id": safe_text(unit.get("ams_id"), max_length=40),
                        "display_name": safe_text(unit.get("display_name"), max_length=120),
                        "type": safe_text(unit.get("ams_type_name") or unit.get("type"), max_length=80),
                        "humidity": safe_text(unit.get("humidity"), max_length=40),
                        "temperature": safe_text(unit.get("temperature") or unit.get("temp"), max_length=40),
                        "dry_status_name": safe_text(unit.get("dry_status_name"), max_length=80),
                        "slots": slots,
                    }
                )
            )
        summary = as_dict(payload.get("summary"))
        data = {
            "summary": compact_dict(
                {
                    "ams_count": summary.get("ams_count"),
                    "slot_count": summary.get("slot_count"),
                    "loaded_count": summary.get("loaded_count"),
                    "empty_count": summary.get("empty_count"),
                    "transitioning_count": summary.get("transitioning_count"),
                    "unknown_type_count": summary.get("unknown_type_count"),
                }
            ),
            "units": units,
        }
        return success(data)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
