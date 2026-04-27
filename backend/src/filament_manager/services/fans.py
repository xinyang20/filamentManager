from __future__ import annotations

from typing import Any


def fan_percent(value: Any) -> int | None:
    speed = _as_int(value)
    if speed is None or speed < 0:
        return None
    if speed <= 15:
        return round(speed * 100 / 15)
    if speed <= 255:
        return _clamp_percent(round(speed * 100 / 255))
    packed = _packed_fan_bytes(speed)
    if not packed:
        return None
    return _clamp_percent(max(round(byte * 100 / 255) for byte in packed))


def packed_fan_bytes(value: Any) -> list[int]:
    speed = _as_int(value)
    if speed is None or speed <= 255:
        return []
    return _packed_fan_bytes(speed)


def normalize_fan_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            normalized[key] = item
            continue
        next_item = dict(item)
        raw = next_item.get("raw")
        percent = _as_int(next_item.get("percent"))
        if percent is None or percent > 100 or percent < 0:
            next_item["percent"] = fan_percent(raw)
        if not next_item.get("packed_bytes"):
            next_item["packed_bytes"] = packed_fan_bytes(raw) or None
        normalized[key] = next_item
    return normalized


def _packed_fan_bytes(value: int) -> list[int]:
    bytes_ = [(value >> shift) & 0xFF for shift in range(0, 32, 8)]
    return [byte for byte in bytes_ if byte not in (0, 255)]


def _clamp_percent(value: int) -> int:
    return max(0, min(100, value))


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
