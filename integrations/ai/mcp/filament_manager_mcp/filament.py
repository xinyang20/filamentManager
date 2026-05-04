from __future__ import annotations

from collections import Counter
from typing import Any

from integrations.ai.shared.schemas import FilamentAnomaliesParams, ListFilamentSpoolsParams

from .ams import map_ams_slot
from .tools import (
    api_get,
    as_dict,
    as_list,
    compact_dict,
    safe_float,
    safe_int,
    safe_text,
    success,
    tool_error,
)


LOW_REMAIN_PERCENT = 15
LOW_WEIGHT_G = 100


def _needs_review(spool: dict[str, Any]) -> bool:
    config = as_dict(spool.get("config"))
    return spool.get("status") == "unknown" or bool(config.get("needs_sku_review")) or spool.get("sku_id") is None


def _ai_status(spool: dict[str, Any]) -> str:
    status = spool.get("status")
    if _needs_review(spool):
        return "needs_review"
    if status == "sealed_stock_virtual":
        return "sealed"
    if status in {"empty", "archived"}:
        return str(status)
    return "active"


def _location(spool: dict[str, Any]) -> str:
    if spool.get("current_ams_id") or spool.get("status") == "loaded_in_ams":
        return "ams"
    if spool.get("storage_location") or spool.get("status") == "opened_in_storage":
        return "storage"
    return "unknown"


def _location_label(spool: dict[str, Any]) -> str | None:
    if _location(spool) == "ams":
        ams_id = spool.get("current_ams_id")
        tray_id = spool.get("current_tray_id")
        if ams_id is not None and tray_id is not None:
            return f"AMS {ams_id} Slot {tray_id}"
        return "AMS"
    if _location(spool) == "storage":
        return safe_text(spool.get("storage_location"), max_length=120) or "Storage"
    return "Unknown"


def _remain_percent(spool: dict[str, Any]) -> int | None:
    explicit = safe_int(spool.get("last_ams_remain_percent"))
    if explicit is not None:
        return explicit
    remaining = safe_float(spool.get("current_remaining_g") or spool.get("actual_weight_g"))
    nominal = safe_float(spool.get("nominal_weight_g"))
    if remaining is None or nominal in (None, 0):
        return None
    return max(0, min(100, int(round((remaining / nominal) * 100))))


def map_spool(spool: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "spool_id": spool.get("id") or spool.get("spool_id"),
            "status": _ai_status(spool),
            "brand_name": safe_text(spool.get("brand_name"), max_length=120),
            "material": safe_text(spool.get("material"), max_length=40),
            "series": safe_text(spool.get("series"), max_length=120),
            "color_name": safe_text(spool.get("color_name"), max_length=120),
            "color_hex": safe_text(spool.get("color_hex") or spool.get("color_value"), max_length=16),
            "remaining_weight_g": safe_float(spool.get("current_remaining_g") or spool.get("actual_weight_g")),
            "remain_percent": _remain_percent(spool),
            "location_label": _location_label(spool),
            "needs_review": _needs_review(spool),
            "updated_at": spool.get("updated_at"),
        }
    )


def _matches_filter(spool: dict[str, Any], params: ListFilamentSpoolsParams) -> bool:
    if params.status and _ai_status(spool) != params.status:
        return False
    if params.location and _location(spool) != params.location:
        return False
    if params.material and (spool.get("material") or "").casefold() != params.material.casefold():
        return False
    if params.brand and (spool.get("brand_name") or "").casefold() != params.brand.casefold():
        return False
    return True


def _is_low_stock(spool: dict[str, Any]) -> bool:
    remain = _remain_percent(spool)
    weight = safe_float(spool.get("current_remaining_g") or spool.get("actual_weight_g"))
    return (remain is not None and remain <= LOW_REMAIN_PERCENT) or (weight is not None and weight <= LOW_WEIGHT_G)


async def get_filament_inventory_summary() -> dict[str, Any]:
    try:
        payload = as_dict(await api_get("/filament/inventory/summary"))
        totals = as_dict(payload.get("totals"))
        spools = []
        for key in ("opened_spools", "ams_spools", "needs_location_spools", "empty_spools", "archived_spools"):
            spools.extend(item for item in as_list(payload.get(key)) if isinstance(item, dict))
        material_counts = Counter(safe_text(spool.get("material"), max_length=40) or "unknown" for spool in spools)
        data = {
            "totals": compact_dict(
                {
                    "sku_count": totals.get("sku_count"),
                    "sealed_quantity": totals.get("sealed_quantity"),
                    "opened_spool_count": totals.get("opened_spool_count"),
                    "ams_spool_count": totals.get("ams_spool_count"),
                    "needs_location_count": totals.get("needs_location_count"),
                    "empty_spool_count": totals.get("empty_spool_count"),
                    "archived_spool_count": totals.get("archived_spool_count"),
                    "tracked_spool_count": len(spools),
                }
            ),
            "material_counts": [{"material": material, "count": count} for material, count in material_counts.most_common()],
            "low_stock_count": sum(1 for spool in spools if _is_low_stock(spool)),
        }
        return success(data)
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


async def list_filament_spools(
    status: str | None = None,
    material: str | None = None,
    brand: str | None = None,
    location: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    try:
        params = ListFilamentSpoolsParams(status=status, material=material, brand=brand, location=location, limit=limit)
        payload = as_list(await api_get("/filament/spools"))
        rows = [item for item in payload if isinstance(item, dict) and _matches_filter(item, params)]
        return success({"spools": [map_spool(item) for item in rows[: params.limit]]})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)


async def find_filament_anomalies(
    printer_id: int,
    include_low_stock: bool = True,
    include_ams_mismatch: bool = True,
    include_review_needed: bool = True,
) -> dict[str, Any]:
    try:
        params = FilamentAnomaliesParams(
            printer_id=printer_id,
            include_low_stock=include_low_stock,
            include_ams_mismatch=include_ams_mismatch,
            include_review_needed=include_review_needed,
        )
        ams_payload = as_dict(await api_get(f"/printers/{params.printer_id}/ams/overview"))
        summary_payload = as_dict(await api_get("/filament/inventory/summary"))
        spools_payload = as_list(await api_get("/filament/spools"))
        anomalies: list[dict[str, Any]] = []

        for unit in as_list(ams_payload.get("units")):
            if not isinstance(unit, dict):
                continue
            for slot in as_list(unit.get("slots")):
                if not isinstance(slot, dict):
                    continue
                mapped_slot = map_ams_slot(slot)
                if slot.get("is_transitioning"):
                    anomalies.append(
                        {
                            "type": "ams_slot_transitioning",
                            "severity": "info",
                            "title": f"{mapped_slot.get('slot_label') or 'AMS slot'} is changing state",
                            "evidence": mapped_slot,
                            "recommended_human_action": "Wait for the AMS state to settle before changing filament records.",
                        }
                    )
                if params.include_ams_mismatch and (slot.get("material") or slot.get("color")) and not (
                    slot.get("filament_spool_id") or slot.get("spool_id")
                ):
                    anomalies.append(
                        {
                            "type": "ams_unknown_filament",
                            "severity": "warning",
                            "title": f"{mapped_slot.get('slot_label') or 'AMS slot'} has unconfirmed filament",
                            "evidence": mapped_slot,
                            "recommended_human_action": "Confirm or bind the spool from the FilamentManager frontend.",
                        }
                    )
                slot_material = safe_text(slot.get("material"), max_length=40)
                bound_material = safe_text(slot.get("filament_material"), max_length=40)
                if params.include_ams_mismatch and slot_material and bound_material and slot_material != bound_material:
                    anomalies.append(
                        {
                            "type": "ams_material_mismatch",
                            "severity": "warning",
                            "title": f"{mapped_slot.get('slot_label') or 'AMS slot'} material differs from the bound spool",
                            "evidence": {
                                "slot_label": mapped_slot.get("slot_label"),
                                "reported_material": slot_material,
                                "bound_material": bound_material,
                            },
                            "recommended_human_action": "Review the AMS slot and spool binding in the frontend.",
                        }
                    )

        if params.include_review_needed:
            for spool in [item for item in spools_payload if isinstance(item, dict) and _needs_review(item)][:20]:
                mapped = map_spool(spool)
                anomalies.append(
                    {
                        "type": "filament_needs_review",
                        "severity": "warning",
                        "title": f"Spool #{mapped.get('spool_id')} needs human review",
                        "evidence": {
                            "spool_id": mapped.get("spool_id"),
                            "material": mapped.get("material"),
                            "color_hex": mapped.get("color_hex"),
                            "location_label": mapped.get("location_label"),
                        },
                        "recommended_human_action": "Open the filament page and confirm the spool identity or SKU manually.",
                    }
                )

        if params.include_low_stock:
            summary_spools: list[dict[str, Any]] = []
            for key in ("opened_spools", "ams_spools", "needs_location_spools"):
                summary_spools.extend(item for item in as_list(summary_payload.get(key)) if isinstance(item, dict))
            for spool in [item for item in summary_spools if _is_low_stock(item)][:20]:
                mapped = map_spool(spool)
                anomalies.append(
                    {
                        "type": "filament_low_stock",
                        "severity": "info",
                        "title": f"Spool #{mapped.get('spool_id')} is low",
                        "evidence": {
                            "spool_id": mapped.get("spool_id"),
                            "material": mapped.get("material"),
                            "remain_percent": mapped.get("remain_percent"),
                            "remaining_weight_g": mapped.get("remaining_weight_g"),
                            "location_label": mapped.get("location_label"),
                        },
                        "recommended_human_action": "Prepare a replacement spool before starting long prints.",
                    }
                )

        return success({"anomalies": anomalies})
    except Exception as exc:  # noqa: BLE001
        return tool_error(exc)
