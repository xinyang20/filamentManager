from __future__ import annotations

import contextlib
import json
import os
import re
import resource
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.core.config import get_settings
from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import (
    DeviceMetricSample,
    DeviceStatusSnapshot,
    NotificationDelivery,
    Printer,
    PrinterEvent,
    PrintLogEntry,
    RawMqttMessage,
)
from filament_manager.services.maintenance import maintenance_due_counts
from filament_manager.services.notifications import notification_config_summary

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
        _append_print_log_metrics(lines, db, printer.id)
        _append_event_count_metrics(lines, db, printer.id)

    for (printer_id, metric), sample in latest_metrics.items():
        value = _number(sample.value_float if sample.value_float is not None else sample.value_text)
        if value is None:
            continue
        name = _prom_metric_name(metric)
        labels = _labels(printer_id=printer_id)
        lines.append(f"{name}{labels} {value}")
    _append_notification_metrics(lines, db)
    return "\n".join(lines) + "\n"


def support_bundle(db: Session) -> dict[str, Any]:
    printers = list(db.scalars(select(Printer).order_by(Printer.id)).all())
    raw_messages = list(
        db.scalars(select(RawMqttMessage).order_by(RawMqttMessage.id.desc()).limit(20)).all()
    )
    events = list(db.scalars(select(PrinterEvent).order_by(PrinterEvent.id.desc()).limit(50)).all())
    connection_events = [
        event for event in events if event.event_type.startswith("printer.connection.")
    ][:20]
    mqtt_errors = [
        event for event in events if event.event_type.startswith("mqtt.") or event.event_type.startswith("printer.command.")
    ][:20]
    storage_errors = [
        event for event in events if event.event_type == "storage.scan_failed"
    ][:20]
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
        "recent_connection_events": [
            _redact_bundle_value(_event_summary(event), printer_aliases=printer_aliases, serial_aliases=serial_aliases, host_aliases=host_aliases)
            for event in connection_events
        ],
        "recent_mqtt_errors": [
            _redact_bundle_value(_event_summary(event), printer_aliases=printer_aliases, serial_aliases=serial_aliases, host_aliases=host_aliases)
            for event in mqtt_errors
        ],
        "recent_storage_errors": [
            _redact_bundle_value(_event_summary(event), printer_aliases=printer_aliases, serial_aliases=serial_aliases, host_aliases=host_aliases)
            for event in storage_errors
        ],
        "config_summary": _redact_bundle_value(
            {
                "database_url": get_settings().database_url,
                "prometheus_enabled": get_settings().prometheus_enabled,
                "prometheus_bearer_token_configured": bool(get_settings().prometheus_bearer_token),
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
        "notification_summary": _redact_bundle_value(
            notification_config_summary(db),
            printer_aliases=printer_aliases,
            serial_aliases=serial_aliases,
            host_aliases=host_aliases,
        ),
        "experimental_features": {
            "print_log": {"default_enabled": False},
            "timelapse": {"default_enabled": False},
            "maintenance": {"default_enabled": False},
        },
        "frontend": {"app_version": "0.1.0", "browser_info_source": "download_client"},
        "privacy": {
            "redacted": ["access_code", "serial", "ip", "printer_name", "local_paths", "webhook_url", "ntfy_token"],
            "excluded": ["full_database", "large_files", "local_test_environment_document"],
        },
    }


def _append_print_log_metrics(lines: list[str], db: Session, printer_id: int) -> None:
    rows = list(db.scalars(select(PrintLogEntry).where(PrintLogEntry.printer_id == printer_id)).all())
    completed = [row for row in rows if row.status in {"succeeded", "failed", "cancelled"}]
    for status in ("succeeded", "failed", "cancelled"):
        labels = _labels(printer_id=printer_id, status=status)
        count = sum(1 for row in rows if row.status == status)
        lines.append(f"filament_manager_print_total{labels} {count}")
    success_count = sum(1 for row in completed if row.status == "succeeded")
    success_rate = (success_count / len(completed)) if completed else 0.0
    lines.append(f"filament_manager_print_success_rate{_labels(printer_id=printer_id)} {success_rate}")
    durations = [row.duration_seconds or 0 for row in completed if row.duration_seconds is not None]
    average = (sum(durations) / len(durations)) if durations else 0.0
    lines.append(f"filament_manager_print_average_duration_seconds{_labels(printer_id=printer_id)} {average}")


def _append_event_count_metrics(lines: list[str], db: Session, printer_id: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    hms_24h = db.scalar(
        select(func.count())
        .select_from(PrinterEvent)
        .where(
            PrinterEvent.printer_id == printer_id,
            PrinterEvent.event_type == "hms.error",
            PrinterEvent.created_at >= cutoff,
        )
    )
    lines.append(f"filament_manager_hms_recent_24h_total{_labels(printer_id=printer_id)} {int(hms_24h or 0)}")
    for event_type, metric_name in (
        ("printer.connection.disconnected", "filament_manager_connection_state_changes_total"),
        ("printer.connection.restored", "filament_manager_connection_state_changes_total"),
        ("storage.scan", "filament_manager_storage_scan_total"),
        ("storage.scan_failed", "filament_manager_storage_scan_total"),
    ):
        count = int(
            db.scalar(
                select(func.count())
                .select_from(PrinterEvent)
                .where(PrinterEvent.printer_id == printer_id, PrinterEvent.event_type == event_type)
            )
            or 0
        )
        status_label = "failed" if event_type.endswith("failed") or event_type.endswith("disconnected") else "succeeded"
        lines.append(f"{metric_name}{_labels(printer_id=printer_id, event_type=event_type, status=status_label)} {count}")


def _append_notification_metrics(lines: list[str], db: Session) -> None:
    for status in ("sent", "failed", "suppressed", "skipped", "delayed"):
        count = int(
            db.scalar(
                select(func.count())
                .select_from(NotificationDelivery)
                .where(NotificationDelivery.status == status)
            )
            or 0
        )
        lines.append(f"filament_manager_notification_delivery_total{_labels(status=status)} {count}")


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
    process_table = _process_table()
    root_pid = os.getpid()
    process_ids = _project_process_ids(root_pid, process_table)
    backend_rss = process_table.get(root_pid, {}).get("rss_bytes")
    project_rss = sum(int(process_table.get(pid, {}).get("rss_bytes") or 0) for pid in process_ids)
    peak_rss = _backend_peak_rss_bytes()
    if project_rss <= 0:
        project_rss = peak_rss
    if backend_rss is None:
        backend_rss = peak_rss
    return {
        "rss_bytes": project_rss,
        "project_rss_bytes": project_rss,
        "backend_rss_bytes": backend_rss,
        "child_rss_bytes": max(0, project_rss - backend_rss),
        "process_count": len(process_ids) if process_ids else 1,
        "backend_peak_rss_bytes": peak_rss,
    }


def _process_table() -> dict[int, dict[str, int]]:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            ["ps", "-axo", "pid=,ppid=,rss="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, _stderr = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            with contextlib.suppress(Exception):
                process.communicate(timeout=1)
        return {}
    except OSError:
        return {}
    if process.returncode != 0:
        return {}
    rows: dict[int, dict[str, int]] = {}
    sampler_pid = process.pid
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            rss_bytes = int(parts[2]) * 1024
        except ValueError:
            continue
        if pid == sampler_pid:
            continue
        rows[pid] = {"ppid": ppid, "rss_bytes": rss_bytes}
    return rows


def _project_process_ids(root_pid: int, process_table: dict[int, dict[str, int]]) -> set[int]:
    if not process_table:
        return {root_pid}
    children_by_parent: dict[int, list[int]] = {}
    for pid, info in process_table.items():
        children_by_parent.setdefault(info["ppid"], []).append(pid)
    collected = {root_pid}
    stack = [root_pid]
    while stack:
        parent = stack.pop()
        for child in children_by_parent.get(parent, []):
            if child in collected:
                continue
            collected.add(child)
            stack.append(child)
    return collected


def _backend_peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


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


def _event_summary(event: PrinterEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "printer_id": event.printer_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "message": event.message,
        "data": event.data,
        "created_at": event.created_at.isoformat(),
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
