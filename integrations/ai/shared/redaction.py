from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


SENSITIVE_KEYS = {
    "access_code",
    "password",
    "token",
    "secret",
    "authorization",
    "bearer_token",
    "access_token",
    "api_key",
    "host",
    "hostname",
    "ip",
    "port",
    "serial",
    "serial_number",
    "tag_uid",
    "tray_uuid",
    "identity_key",
    "raw",
    "payload",
    "raw_refs",
    "ssdp",
    "topic",
    "config",
    "display_config",
    "path",
    "gcode_file",
    "stream_path",
    "download_url",
    "camera",
    "camera_options",
    "network",
}

SENSITIVE_KEY_FRAGMENTS = (
    "access_code",
    "access-token",
    "bearer",
    "rfid",
    "secret",
)

PRIVATE_URL_RE = re.compile(
    r"\b(?:https?|ftp|rtsp)://(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|[^/\s]+\.local)(?::\d+)?[^\s,;)]*",
    re.IGNORECASE,
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
LONG_HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{16,64}\b")
AUTH_RE = re.compile(r"\b(?:Authorization:\s*)?(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
LOCAL_PATH_RE = re.compile(
    r"(?<!\w)(?:/Users|/home|/var|/tmp|/private|/Volumes|/Metadata|/userdata|/sdcard|/mnt)/[^\s,;)]*",
    re.IGNORECASE,
)
BAMBU_SERIAL_LIKE_RE = re.compile(r"\b(?=[A-Z0-9]{12,32}\b)(?=.*[A-Z])(?=.*\d)[A-Z0-9]{12,32}\b")
MQTT_TOPIC_RE = re.compile(r"\bdevice/[A-Za-z0-9._-]{6,}/(?:report|request|reply)\b", re.IGNORECASE)

VALUE_PATTERNS = (
    PRIVATE_URL_RE,
    AUTH_RE,
    LOCAL_PATH_RE,
    MQTT_TOPIC_RE,
    UUID_RE,
    LONG_HEX_ID_RE,
    BAMBU_SERIAL_LIKE_RE,
    IPV6_RE,
    IPV4_RE,
)


def _sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    if normalized in SENSITIVE_KEYS:
        return True
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_text(value: str) -> tuple[str, bool]:
    redacted = value
    applied = False
    for pattern in VALUE_PATTERNS:
        new_value = pattern.sub("[redacted]", redacted)
        if new_value != redacted:
            applied = True
            redacted = new_value
    redacted = re.sub(r"(?:\[redacted\]\s*){2,}", "[redacted]", redacted).strip()
    return redacted, applied


def clean_error_message(value: Any) -> tuple[str, bool]:
    if isinstance(value, Mapping):
        if "detail" in value:
            return clean_error_message(value["detail"])
        if "message" in value:
            return clean_error_message(value["message"])
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [clean_error_message(item)[0] for item in value[:3]]
        return "; ".join(part for part in parts if part), True
    text = str(value or "Backend request failed")
    cleaned, applied = redact_text(text)
    if not cleaned:
        return "Backend request failed", True
    return cleaned[:300], applied


def redact_for_ai(value: Any) -> tuple[Any, bool]:
    return _redact(value)


def _redact(value: Any) -> tuple[Any, bool]:
    if isinstance(value, Mapping):
        changed = False
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _sensitive_key(key):
                changed = True
                continue
            redacted_item, item_changed = _redact(item)
            changed = changed or item_changed
            if redacted_item is not None:
                result[str(key)] = redacted_item
            else:
                changed = True
        return result, changed

    if isinstance(value, list):
        changed = False
        result = []
        for item in value:
            redacted_item, item_changed = _redact(item)
            changed = changed or item_changed
            if redacted_item is not None:
                result.append(redacted_item)
            else:
                changed = True
        return result, changed

    if isinstance(value, tuple):
        redacted_list, changed = _redact(list(value))
        return redacted_list, changed

    if isinstance(value, str):
        cleaned, changed = redact_text(value)
        return cleaned, changed

    return value, False
