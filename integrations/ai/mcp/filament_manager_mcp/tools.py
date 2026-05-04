from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from integrations.ai.shared.client import ApiAccessError, ApiClientError, FilamentManagerApiClient
from integrations.ai.shared.redaction import clean_error_message, redact_for_ai, redact_text


ClientFactory = Callable[[], Any]

_client_factory: ClientFactory = FilamentManagerApiClient


def configure_client_factory(factory: ClientFactory) -> None:
    global _client_factory
    _client_factory = factory


def reset_client_factory() -> None:
    configure_client_factory(FilamentManagerApiClient)


async def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    client = _client_factory()
    async with client:
        return await client.get_json(path, params=params)


def success(data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    safe_data, redaction_applied = redact_for_ai(data)
    return {
        "ok": True,
        "data": safe_data,
        "warnings": warnings or [],
        "redaction_applied": redaction_applied,
    }


def failure(error_code: str, message: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    cleaned, redaction_applied = clean_error_message(message)
    return {
        "ok": False,
        "error_code": error_code,
        "message": cleaned,
        "warnings": warnings or [],
        "redaction_applied": redaction_applied,
    }


def validation_failure(exc: ValidationError) -> dict[str, Any]:
    messages = []
    for error in exc.errors()[:3]:
        location = ".".join(str(part) for part in error.get("loc", ())) or "arguments"
        messages.append(f"{location}: {error.get('msg', 'invalid value')}")
    return failure("invalid_arguments", "; ".join(messages) or "Invalid tool arguments")


def tool_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValidationError):
        return validation_failure(exc)
    if isinstance(exc, ApiAccessError):
        return failure(exc.code, str(exc))
    if isinstance(exc, ApiClientError):
        return failure(exc.code, exc.message)
    return failure("internal_error", "The MCP tool failed without exposing internal details")


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any, *, max_length: int = 240) -> str | None:
    if value is None:
        return None
    text, _ = redact_text(str(value))
    text = text.strip()
    if not text:
        return None
    return text[:max_length]


def safe_error_summary(value: Any, *, max_length: int = 200) -> str | None:
    text = safe_text(value, max_length=max_length)
    if text is None:
        return None
    for label in ("access code", "access_code", "serial", "host", "hostname", "ip", "token"):
        text = text.replace(label, "[redacted]")
        text = text.replace(label.upper(), "[redacted]")
        text = text.replace(label.title(), "[redacted]")
    return text[:max_length]


def iso_days_ago(days: int) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def safe_print_name(row: dict[str, Any]) -> str | None:
    for key in ("print_name", "subtask_name", "name"):
        raw_value = row.get(key)
        if raw_value is None:
            continue
        raw_text = str(raw_value).strip()
        raw_normalized = raw_text.lower()
        if "/" in raw_text or "\\" in raw_text:
            continue
        if raw_normalized.endswith((".gcode", ".3mf", ".stl", ".step", ".stp")):
            continue
        value = safe_text(raw_text, max_length=160)
        if not value:
            continue
        normalized = value.lower()
        if value == "[redacted]" or normalized.endswith((".gcode", ".3mf", ".stl", ".step", ".stp")):
            continue
        if value:
            return value
    return None


def map_printer(printer: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "printer_id": printer.get("id") or printer.get("printer_id"),
            "name": safe_text(printer.get("name"), max_length=120),
            "enabled": printer.get("enabled"),
            "connection_status": safe_text(printer.get("connection_status"), max_length=40),
            "last_sync_at": printer.get("last_sync_at"),
            "last_error_summary": safe_error_summary(printer.get("last_error"), max_length=200),
        }
    )


def map_hms_error(item: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "short_code": safe_text(item.get("short_code") or item.get("code"), max_length=80),
            "severity": safe_text(item.get("severity_name") or item.get("severity"), max_length=40),
            "active": item.get("active"),
            "message": safe_text(item.get("message") or item.get("message_zh") or item.get("message_en"), max_length=240),
        }
    )


def map_event(item: dict[str, Any]) -> dict[str, Any]:
    return compact_dict(
        {
            "event_id": item.get("id") or item.get("event_id"),
            "source": safe_text(item.get("source"), max_length=60),
            "printer_id": item.get("printer_id"),
            "type": safe_text(item.get("type") or item.get("event_type"), max_length=80),
            "severity": safe_text(item.get("severity"), max_length=40),
            "active": item.get("active"),
            "message": safe_text(item.get("message"), max_length=240),
            "created_at": item.get("created_at"),
        }
    )


def backend_status_to_ai_status(status: str | None) -> str | None:
    if status == "succeeded":
        return "success"
    return status


def ai_status_to_backend_status(status: str | None) -> str | None:
    if status == "success":
        return "succeeded"
    return status
