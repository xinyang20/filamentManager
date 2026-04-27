from __future__ import annotations

import json
import os
import re
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.config import get_settings
from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import DeviceMetricSample, DeviceStatusSnapshot, Printer, PrinterEvent, RawMqttMessage
from filament_manager.services.maintenance import maintenance_due_counts

APP_STARTED_AT = time.monotonic()
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SERIALISH_RE = re.compile(r"\b[A-Z0-9]{8,}\b")


def system_info(db: Session) -> dict[str, Any]:
    printers = list(db.scalars(select(Printer)).all())
    return {
        "app_version": "0.1.0",
        "uptime_seconds": round(time.monotonic() - APP_STARTED_AT, 3),
        "database_size_bytes": _database_size(),
        "storage_size_bytes": _directory_size(Path.cwd()),
        "cpu_percent": _load_average_percent(),
        "memory": _memory_info(),
        "configured_printers": len(printers),
        "online_printers": sum(1 for printer in printers if printer.connection_status == "connected"),
    }


def prometheus_metrics(db: Session) -> str:
    lines = [
        "# HELP filament_manager_printer_online Printer MQTT connection status.",
        "# TYPE filament_manager_printer_online gauge",
    ]
    due_counts = maintenance_due_counts(db)
    snapshots = {
        snapshot.printer_id: snapshot
        for snapshot in db.scalars(select(DeviceStatusSnapshot)).all()
    }
    latest_metrics = _latest_metrics(db)
    for printer in db.scalars(select(Printer).order_by(Printer.id)).all():
        labels = _labels(printer_id=printer.id)
        lines.append(f"filament_manager_printer_online{labels} {1 if printer.connection_status == 'connected' else 0}")
        snapshot = snapshots.get(printer.id)
        if snapshot:
            state = snapshot.print_status.get("gcode_state") if isinstance(snapshot.print_status, dict) else None
            progress = _number(snapshot.print_status.get("mc_percent")) if isinstance(snapshot.print_status, dict) else None
            remaining = _number(snapshot.print_status.get("mc_remaining_time")) if isinstance(snapshot.print_status, dict) else None
            lines.append(f"filament_manager_printer_printing{labels} {1 if state == 'RUNNING' else 0}")
            if progress is not None:
                lines.append(f"filament_manager_print_progress_percent{labels} {progress}")
            if remaining is not None:
                lines.append(f"filament_manager_print_remaining_seconds{labels} {remaining * 60}")
            hms_active = sum(
                1
                for item in (snapshot.hms_errors or [])
                if isinstance(item, dict) and item.get("active") is not False and item.get("actionable") is not False
            )
            lines.append(f"filament_manager_hms_active{labels} {hms_active}")
        lines.append(f"filament_manager_maintenance_due{labels} {due_counts.get(printer.id, 0)}")

    for (printer_id, metric), sample in latest_metrics.items():
        value = _number(sample.value_float if sample.value_float is not None else sample.value_text)
        if value is None:
            continue
        name = _prom_metric_name(metric)
        labels = _labels(printer_id=printer_id)
        lines.append(f"{name}{labels} {value}")
    return "\n".join(lines) + "\n"


def support_bundle(db: Session) -> dict[str, Any]:
    printers = list(db.scalars(select(Printer).order_by(Printer.id)).all())
    raw_messages = list(
        db.scalars(select(RawMqttMessage).order_by(RawMqttMessage.id.desc()).limit(20)).all()
    )
    events = list(db.scalars(select(PrinterEvent).order_by(PrinterEvent.id.desc()).limit(50)).all())
    printer_aliases = {printer.name: f"printer-{index + 1}" for index, printer in enumerate(printers)}
    serial_aliases = {printer.serial: f"serial-{index + 1}" for index, printer in enumerate(printers)}
    host_aliases = {printer.host: f"host-{index + 1}" for index, printer in enumerate(printers)}
    return {
        "generated_at": datetime.now(timezone.utc),
        "system": system_info(db),
        "recent_events": [
            _redact_bundle_value(
                {
                    "id": event.id,
                    "printer_id": event.printer_id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "message": event.message,
                    "data": event.data,
                    "created_at": event.created_at.isoformat(),
                },
                printer_aliases=printer_aliases,
                serial_aliases=serial_aliases,
                host_aliases=host_aliases,
            )
            for event in events
        ],
        "recent_mqtt": [
            _redact_bundle_value(
                {
                    "id": row.id,
                    "printer_id": row.printer_id,
                    "topic": row.topic,
                    "command": row.command,
                    "received_at": row.received_at.isoformat(),
                    "payload_summary": _payload_summary(row.payload),
                },
                printer_aliases=printer_aliases,
                serial_aliases=serial_aliases,
                host_aliases=host_aliases,
            )
            for row in raw_messages
        ],
        "config_summary": _redact_bundle_value(
            {
                "database_url": get_settings().database_url,
                "prometheus_enabled": get_settings().prometheus_enabled,
                "printer_count": len(printers),
                "printers": [
                    {
                        "id": printer.id,
                        "name": printer.name,
                        "host": printer.host,
                        "serial": printer.serial,
                        "port": printer.port,
                        "tls_enabled": printer.tls_enabled,
                        "certificate_verify": printer.certificate_verify,
                        "enabled": printer.enabled,
                        "connection_status": printer.connection_status,
                    }
                    for printer in printers
                ],
            },
            printer_aliases=printer_aliases,
            serial_aliases=serial_aliases,
            host_aliases=host_aliases,
        ),
        "privacy": {
            "redacted": ["access_code", "serial", "ip", "printer_name", "local_paths"],
            "excluded": ["full_database", "large_files", "local_test_environment_document"],
        },
    }


def _latest_metrics(db: Session) -> dict[tuple[int, str], DeviceMetricSample]:
    rows = db.scalars(select(DeviceMetricSample).order_by(DeviceMetricSample.sampled_at.desc(), DeviceMetricSample.id.desc())).all()
    latest: dict[tuple[int, str], DeviceMetricSample] = {}
    for row in rows:
        latest.setdefault((row.printer_id, row.metric), row)
    return latest


def _labels(**values: Any) -> str:
    if not values:
        return ""
    parts = [f'{key}="{_escape_label(value)}"' for key, value in values.items() if value is not None]
    return "{" + ",".join(parts) + "}"


def _escape_label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _prom_metric_name(metric: str) -> str:
    return "filament_manager_" + re.sub(r"[^a-zA-Z0-9_]", "_", metric)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _database_size() -> int:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        return 0
    path = Path(url.replace("sqlite:///", "", 1))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.stat().st_size if path.exists() else 0


def _directory_size(path: Path) -> int:
    total = 0
    excluded = {".git", "node_modules", ".venv", "__pycache__"}
    for root, dirs, files in os.walk(path):
        dirs[:] = [item for item in dirs if item not in excluded]
        for file_name in files:
            file_path = Path(root) / file_name
            if str(file_path).endswith(".docs/local_bambu_test_environment.md"):
                continue
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _load_average_percent() -> float | None:
    try:
        load1, _, _ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        return round(min(100.0, (load1 / cpu_count) * 100), 2)
    except OSError:
        return None


def _memory_info() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"rss_bytes": int(usage.ru_maxrss) * 1024}


def _payload_summary(payload: Any) -> dict[str, Any]:
    payload = redact_sensitive(payload)
    if not isinstance(payload, dict):
        return {}
    print_section = payload.get("print") if isinstance(payload.get("print"), dict) else {}
    return {
        "top_level_keys": sorted(payload.keys()),
        "print_keys": sorted(print_section.keys())[:80],
        "command": print_section.get("command"),
        "gcode_state": print_section.get("gcode_state"),
        "task_id": print_section.get("task_id"),
        "mc_percent": print_section.get("mc_percent"),
        "has_ams": isinstance(print_section.get("ams"), dict),
        "hms_count": len(print_section.get("hms")) if isinstance(print_section.get("hms"), list) else 0,
    }


def _redact_bundle_value(
    value: Any,
    *,
    printer_aliases: dict[str, str],
    serial_aliases: dict[str, str],
    host_aliases: dict[str, str],
) -> Any:
    value = redact_sensitive(value)
    if isinstance(value, dict):
        return {
            key: _redact_bundle_value(
                item,
                printer_aliases=printer_aliases,
                serial_aliases=serial_aliases,
                host_aliases=host_aliases,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_bundle_value(
                item,
                printer_aliases=printer_aliases,
                serial_aliases=serial_aliases,
                host_aliases=host_aliases,
            )
            for item in value
        ]
    if isinstance(value, str):
        text = value
        for name, alias in printer_aliases.items():
            if name:
                text = text.replace(name, alias)
        for serial, alias in serial_aliases.items():
            if serial:
                text = text.replace(serial, alias)
        for host, alias in host_aliases.items():
            if host:
                text = text.replace(host, alias)
        text = IP_RE.sub("[redacted-ip]", text)
        if "/" in text and ("/Users/" in text or "/home/" in text):
            text = "[redacted-path]"
        return SERIALISH_RE.sub(lambda match: serial_aliases.get(match.group(0), match.group(0)), text)
    return value


def support_bundle_json(db: Session) -> str:
    return json.dumps(support_bundle(db), ensure_ascii=False, default=str, indent=2)
