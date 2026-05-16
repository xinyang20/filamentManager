from __future__ import annotations

from dataclasses import dataclass
from typing import Any


INVALID_IDENTITY_VALUES = {
    "",
    "0",
    "00",
    "0000",
    "00000000",
    "0000000000000000",
    "000000000000000000000000",
    "00000000-0000-0000-0000-000000000000",
    "ffffffffffffffff",
    "ffffffffffffffffffffffff",
    "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "unknown",
    "null",
    "none",
    "n/a",
}

AMS_TRANSITION_WITHOUT_PAYLOAD_STATES = {
    "4",
    "5",
    "7",
    "8",
    "9",
    "10",
    "11",
    "17",
    "21",
    "23",
    "25",
    "26",
    "27",
    "FILAMENT_PRESENT",
    "LOADING",
    "UNLOADING",
    "READING",
    "RFID_READING",
    "RFID_READING_OR_TRANSITIONING",
    "BUSY",
    "TRANSITIONING",
}

AMS_TRANSITION_STATE_MARKERS = {"LOADING", "UNLOADING", "READING", "BUSY", "CHANGE", "TRANSITION"}

AMS_STATUS_IDLE = 0x00
AMS_STATUS_FILAMENT_CHANGE = 0x01
AMS_STATUS_RFID_IDENTIFYING = 0x02
AMS_STATUS_ASSIST = 0x03
AMS_STATUS_CALIBRATION = 0x04
AMS_STATUS_COLD_PULL = 0x07
AMS_STATUS_SELF_CHECK = 0x10
AMS_STATUS_DEBUG = 0x20
AMS_STATUS_UNKNOWN = 0xFF

AMS_STATUS_TRANSITION_WITHOUT_PAYLOAD = {
    AMS_STATUS_FILAMENT_CHANGE,
    AMS_STATUS_RFID_IDENTIFYING,
}


@dataclass(frozen=True)
class SpoolIdentity:
    identity_key: str | None
    identity_source: str
    identity_confidence: float
    identity_warning: str | None = None


@dataclass(frozen=True)
class ParsedAmsSlot:
    ams_id: str
    tray_id: str
    slot_state: str | None
    material: str | None
    series: str | None
    color: str | None
    color_name: str | None
    remain: int | None
    tray_uuid: str | None
    tag_uid: str | None
    identity: SpoolIdentity
    is_transitioning: bool
    raw: dict[str, Any]


@dataclass(frozen=True)
class ParsedAmsUnit:
    ams_id: str
    humidity: str | None
    temperature: str | None
    raw: dict[str, Any]
    slots: list[ParsedAmsSlot]


def extract_print(payload: dict[str, Any]) -> dict[str, Any]:
    print_section = payload.get("print")
    if isinstance(print_section, dict):
        return print_section
    return {}


def extract_command(payload: dict[str, Any]) -> str | None:
    for section_name in ("print", "info", "system", "pushing"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        command = section.get("command")
        if command is not None:
            return str(command)
    return None


def normalize_state(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def is_valid_identity_value(value: Any) -> bool:
    text = clean_text(value)
    if text is None:
        return False
    compact = text.replace(":", "").replace("-", "").strip().lower()
    if text.lower() in INVALID_IDENTITY_VALUES or compact in INVALID_IDENTITY_VALUES:
        return False
    if compact and set(compact) == {"0"}:
        return False
    if compact and set(compact) == {"f"}:
        return False
    return True


def is_transition_state_without_payload(value: Any) -> bool:
    state = normalize_state(value)
    if state is None:
        return False
    if state in AMS_TRANSITION_WITHOUT_PAYLOAD_STATES:
        return True
    return any(marker in state for marker in AMS_TRANSITION_STATE_MARKERS)


def identify_tray(tray: dict[str, Any]) -> SpoolIdentity:
    tray_uuid = clean_text(tray.get("tray_uuid"))
    tag_uid = clean_text(tray.get("tag_uid"))
    if is_valid_identity_value(tray_uuid):
        return SpoolIdentity(
            identity_key=f"bambu:tray_uuid:{tray_uuid}",
            identity_source="tray_uuid",
            identity_confidence=1.0,
        )
    if is_valid_identity_value(tag_uid):
        return SpoolIdentity(
            identity_key=f"bambu:tag_uid:{tag_uid}",
            identity_source="tag_uid",
            identity_confidence=0.7,
            identity_warning="tray_uuid_invalid_tag_uid_fallback",
        )
    return SpoolIdentity(
        identity_key=None,
        identity_source="manual_required",
        identity_confidence=0.0,
        identity_warning="identity_missing_manual_binding_required",
    )


def is_transitioning_tray(
    tray: dict[str, Any],
    remain: int | None,
    *,
    ams_id: Any = None,
    tray_id: Any = None,
    ams_status: int | None = None,
    tray_exist_bits: int | None = None,
    tray_reading_bits: int | None = None,
    tray_read_done_bits: int | None = None,
) -> bool:
    if _slot_is_empty_by_exist_bits(
        tray,
        ams_id=ams_id,
        tray_id=tray_id,
        tray_exist_bits=tray_exist_bits,
    ):
        return False
    if _tray_has_filament_payload(tray):
        return False
    if _slot_is_reading(
        ams_id=ams_id,
        tray_id=tray_id,
        tray_reading_bits=tray_reading_bits,
        tray_read_done_bits=tray_read_done_bits,
    ):
        return True
    if _ams_status_code(ams_status) in AMS_STATUS_TRANSITION_WITHOUT_PAYLOAD:
        return True
    state = normalize_state(
        tray.get("tray_state")
        or tray.get("state")
        or tray.get("slot_state")
        or tray.get("tray_status")
    )
    if state is None:
        return False
    return is_transition_state_without_payload(state)


def _parse_ams_status(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(text, 16)
        except ValueError:
            return None


def _ams_status_code(value: Any) -> int | None:
    parsed = _parse_ams_status(value)
    if parsed is None:
        return None
    return parsed & 0xFF


def parse_tray_bitfield(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip().lower()
    if not text:
        return None
    if text.startswith("0x"):
        text = text[2:]
    if any(char not in "0123456789abcdef" for char in text):
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def tray_bit_index(ams_id: Any, tray_id: Any) -> int | None:
    ams_num = as_int(ams_id)
    tray_num = as_int(tray_id)
    if ams_num is None or tray_num is None:
        return None
    if ams_num >= 128:
        return 16 + (ams_num - 128)
    return ams_num * 4 + tray_num


def tray_bit_is_set(bits: int | None, *, ams_id: Any, tray_id: Any) -> bool | None:
    if bits is None:
        return None
    index = tray_bit_index(ams_id, tray_id)
    if index is None:
        return None
    return bool(bits & (1 << index))


def _slot_is_reading(
    *,
    ams_id: Any,
    tray_id: Any,
    tray_reading_bits: int | None,
    tray_read_done_bits: int | None,
) -> bool:
    reading = tray_bit_is_set(tray_reading_bits, ams_id=ams_id, tray_id=tray_id)
    if not reading:
        return False
    read_done = tray_bit_is_set(tray_read_done_bits, ams_id=ams_id, tray_id=tray_id)
    return read_done is not True


def _tray_has_filament_payload(tray: dict[str, Any]) -> bool:
    fields = (
        "tray_type",
        "tray_sub_brands",
        "tray_color",
        "color",
        "tray_id_name",
        "tray_info_idx",
        "filament_name",
        "tray_color_name",
        "color_name",
        "filament_color_name",
        "color_display_name",
    )
    if any(clean_text(tray.get(field)) for field in fields):
        return True
    cols = tray.get("cols")
    return isinstance(cols, list) and any(clean_text(value) for value in cols)


def _slot_state(tray: dict[str, Any]) -> str | None:
    return clean_text(
        tray.get("tray_state")
        or tray.get("state")
        or tray.get("slot_state")
        or tray.get("tray_status")
    )


def _first_value(key: str, *sources: dict[str, Any]) -> Any:
    for source in sources:
        if key in source and source.get(key) not in (None, ""):
            return source.get(key)
    return None


def _slot_state_with_bitfields(
    tray: dict[str, Any],
    *,
    ams_id: Any,
    tray_id: Any,
    tray_exist_bits: int | None,
) -> str | None:
    state = _slot_state(tray)
    if _slot_is_empty_by_exist_bits(
        tray,
        ams_id=ams_id,
        tray_id=tray_id,
        tray_exist_bits=tray_exist_bits,
    ):
        return "empty"
    return state


def _slot_is_empty_by_exist_bits(
    tray: dict[str, Any],
    *,
    ams_id: Any,
    tray_id: Any,
    tray_exist_bits: int | None,
) -> bool:
    exists = tray_bit_is_set(tray_exist_bits, ams_id=ams_id, tray_id=tray_id)
    return exists is False and not _tray_has_filament_payload(tray)


def _find_token_sequence(parts: list[str], needle: str | None) -> int | None:
    if needle is None:
        return None
    needle_parts = [part.lower() for part in needle.split() if part.strip()]
    if not needle_parts:
        return None
    lower_parts = [part.lower() for part in parts]
    for index in range(0, len(lower_parts) - len(needle_parts) + 1):
        if lower_parts[index : index + len(needle_parts)] == needle_parts:
            return index + len(needle_parts)
    return None


def _tray_color_name(tray: dict[str, Any], *, material: str | None, series: str | None, color: str | None) -> str | None:
    explicit = clean_text(
        tray.get("tray_color_name")
        or tray.get("color_name")
        or tray.get("filament_color_name")
        or tray.get("color_display_name")
    )
    if explicit is not None:
        return explicit
    name = clean_text(tray.get("tray_id_name"))
    if name is None:
        return None
    compact = name.replace("-", "").replace("_", "").strip()
    if compact and compact.isalnum() and any(char.isdigit() for char in compact) and not any(char.isspace() for char in name):
        return None
    parts = name.split()
    start_index = _find_token_sequence(parts, series)
    if start_index is None:
        start_index = _find_token_sequence(parts, material)
    candidate = " ".join(parts[start_index:]).strip() if start_index is not None else name
    if color and candidate.replace("#", "").lower() == color.replace("#", "").lower():
        return None
    return candidate or None


def parse_ams_units(payload: dict[str, Any]) -> list[ParsedAmsUnit]:
    print_section = extract_print(payload)
    ams_section = print_section.get("ams")
    if not isinstance(ams_section, dict):
        return []

    ams_items = ams_section.get("ams")
    if not isinstance(ams_items, list):
        return []

    parsed_units: list[ParsedAmsUnit] = []
    for unit in ams_items:
        if not isinstance(unit, dict):
            continue
        ams_id = clean_text(unit.get("id") or unit.get("ams_id") or unit.get("idx"))
        if ams_id is None:
            continue
        ams_status = _parse_ams_status(_first_value("ams_status", unit, ams_section, print_section))
        tray_reading_bits = parse_tray_bitfield(_first_value("tray_reading_bits", unit, ams_section, print_section))
        tray_read_done_bits = parse_tray_bitfield(_first_value("tray_read_done_bits", unit, ams_section, print_section))
        tray_exist_bits = parse_tray_bitfield(_first_value("tray_exist_bits", unit, ams_section, print_section))
        raw_trays = unit.get("tray")
        trays = raw_trays if isinstance(raw_trays, list) else []
        parsed_slots: list[ParsedAmsSlot] = []
        for tray in trays:
            if not isinstance(tray, dict):
                continue
            tray_id = clean_text(tray.get("id") or tray.get("tray_id") or tray.get("slot_id"))
            if tray_id is None:
                continue
            remain = as_int(tray.get("remain"))
            material = clean_text(tray.get("tray_type") or tray.get("filament_type"))
            series = clean_text(
                tray.get("tray_sub_brands")
                or tray.get("tray_info_idx")
                or tray.get("filament_name")
            )
            color = clean_text(tray.get("tray_color") or tray.get("color"))
            identity = identify_tray(tray)
            warning = identity.identity_warning
            slot_state = _slot_state_with_bitfields(
                tray,
                ams_id=ams_id,
                tray_id=tray_id,
                tray_exist_bits=tray_exist_bits,
            )
            if remain == -1 and warning:
                warning = f"{warning};remain_unavailable"
                identity = SpoolIdentity(
                    identity.identity_key,
                    identity.identity_source,
                    identity.identity_confidence,
                    warning,
                )
            elif remain == -1:
                identity = SpoolIdentity(
                    identity.identity_key,
                    identity.identity_source,
                    identity.identity_confidence,
                    "remain_unavailable",
                )
            parsed_slots.append(
                ParsedAmsSlot(
                    ams_id=ams_id,
                    tray_id=tray_id,
                    slot_state=slot_state,
                    material=material,
                    series=series,
                    color=color,
                    color_name=_tray_color_name(tray, material=material, series=series, color=color),
                    remain=remain,
                    tray_uuid=clean_text(tray.get("tray_uuid")),
                    tag_uid=clean_text(tray.get("tag_uid")),
                    identity=identity,
                    is_transitioning=is_transitioning_tray(
                        tray,
                        remain,
                        ams_id=ams_id,
                        tray_id=tray_id,
                        ams_status=ams_status,
                        tray_exist_bits=tray_exist_bits,
                        tray_reading_bits=tray_reading_bits,
                        tray_read_done_bits=tray_read_done_bits,
                    ),
                    raw=tray,
                )
            )
        parsed_units.append(
            ParsedAmsUnit(
                ams_id=ams_id,
                humidity=clean_text(unit.get("humidity") or unit.get("humidity_raw")),
                temperature=clean_text(unit.get("temp") or unit.get("temperature")),
                raw=unit,
                slots=parsed_slots,
            )
        )
    return parsed_units
