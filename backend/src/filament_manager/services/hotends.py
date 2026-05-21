from __future__ import annotations

from typing import Any


HOTEND_FALLBACK_LABEL_KEYS = ("hotend_a", "hotend_b")


def hotend_temperature_readings(print_section: dict[str, Any]) -> list[dict[str, Any]]:
    """Return user-facing nozzle/hotend readings from a push_status print section."""
    dual = _dual_hotend_readings(print_section)
    if len(dual) >= 2:
        return dual[:2]
    single = _single_nozzle_reading(print_section)
    return [single] if single is not None else []


def _dual_hotend_readings(print_section: dict[str, Any]) -> list[dict[str, Any]]:
    device = print_section.get("device")
    if not isinstance(device, dict):
        return []
    extruder = device.get("extruder")
    if not isinstance(extruder, dict):
        return []
    info = extruder.get("info")
    if not isinstance(info, list):
        return []

    packed: list[tuple[int, int | None, int, int]] = []
    for index, item in enumerate(info):
        if not isinstance(item, dict):
            continue
        raw_temp = _as_int(item.get("temp"))
        if raw_temp is None or raw_temp < 0:
            continue
        raw_id = _as_int(item.get("id"))
        sort_id = raw_id if raw_id is not None else index
        packed.append((sort_id, raw_id, raw_temp, index))
    if len(packed) < 2:
        return []

    readings: list[dict[str, Any]] = []
    for position, (_sort_id, raw_id, raw_temp, _index) in enumerate(sorted(packed, key=lambda row: (row[0], row[3]))[:2]):
        label_key = _hotend_label_key(raw_id, position)
        readings.append(
            {
                "key": label_key,
                "label_key": label_key,
                "current": float(raw_temp & 0xFFFF),
                "target": float(raw_temp >> 16),
                "raw_extruder_id": raw_id,
                "source": "device.extruder.info.temp",
            }
        )
    return readings


def _hotend_label_key(raw_id: int | None, position: int) -> str:
    if raw_id == 0:
        return "right_hotend"
    if raw_id == 1:
        return "left_hotend"
    if position < len(HOTEND_FALLBACK_LABEL_KEYS):
        return HOTEND_FALLBACK_LABEL_KEYS[position]
    return f"hotend_{position + 1}"


def _single_nozzle_reading(print_section: dict[str, Any]) -> dict[str, Any] | None:
    current = _as_float(print_section.get("nozzle_temper"))
    target = _as_float(print_section.get("nozzle_target_temper"))
    if current is None and target is None:
        return None
    return {
        "key": "nozzle",
        "label_key": "nozzle",
        "current": current,
        "target": target,
        "raw_extruder_id": None,
        "source": "legacy.nozzle_temper",
    }


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
