from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any
import zipfile

from sqlalchemy import delete, distinct, func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from filament_manager.core.config import get_settings
from filament_manager.db import session as db_session
from filament_manager.db.models import (
    AmsSlotHistorySample,
    AppSetting,
    DeviceMetricSample,
    RawMqttArchive,
    RawMqttMessage,
    utc_now,
)

LOGGER = logging.getLogger(__name__)

RAW_MQTT_DB_LIMIT_SETTING = "raw_mqtt_db_limit"
DEFAULT_RAW_MQTT_DB_LIMIT = "5gb"
RAW_MQTT_DB_LIMIT_BYTES: dict[str, int | None] = {
    "1gb": 1 * 1024**3,
    "5gb": 5 * 1024**3,
    "10gb": 10 * 1024**3,
    "20gb": 20 * 1024**3,
    "unlimited": None,
}
RAW_MQTT_DB_LIMIT_OPTIONS = tuple(RAW_MQTT_DB_LIMIT_BYTES)

TRIGGER_MULTIPLIER = 1.05
PROTECT_LATEST_PER_PRINTER = 100
RETENTION_CHECK_THROTTLE_SECONDS = 10 * 60
ARCHIVE_BATCH_SIZE = 5000
ARCHIVE_MAX_BATCHES_PER_RUN = 20
RAW_MQTT_ARCHIVE_FORMAT = "zip"

DatabaseSizeFunc = Callable[[Session], int]

_scheduler_lock = threading.Lock()
_retention_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_last_scheduled_monotonic = 0.0
_running_since: datetime | None = None
_last_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class _ArchiveFile:
    file_path: Path
    row_count: int
    compressed_size_bytes: int
    first_raw_message_id: int | None
    last_raw_message_id: int | None
    first_received_at: datetime | None
    last_received_at: datetime | None
    printer_ids: list[int]
    command_counts: dict[str, int]
    sha256: str


def get_raw_mqtt_db_limit(db: Session) -> str:
    row = db.get(AppSetting, RAW_MQTT_DB_LIMIT_SETTING)
    if row is None or row.value not in RAW_MQTT_DB_LIMIT_BYTES:
        return DEFAULT_RAW_MQTT_DB_LIMIT
    return row.value


def set_raw_mqtt_db_limit(db: Session, value: str) -> str:
    if value not in RAW_MQTT_DB_LIMIT_BYTES:
        raise ValueError(f"Unsupported raw MQTT database limit: {value}")
    row = db.get(AppSetting, RAW_MQTT_DB_LIMIT_SETTING)
    if row is None:
        row = AppSetting(key=RAW_MQTT_DB_LIMIT_SETTING, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = utc_now()
    db.commit()
    return value


def raw_mqtt_limit_bytes(value: str) -> int | None:
    return RAW_MQTT_DB_LIMIT_BYTES[value]


def list_raw_mqtt_archives(db: Session, *, limit: int = 100) -> list[RawMqttArchive]:
    return list(
        db.scalars(
            select(RawMqttArchive)
            .order_by(RawMqttArchive.created_at.desc(), RawMqttArchive.id.desc())
            .limit(limit)
        ).all()
    )


def database_retention_status(
    db: Session,
    *,
    database_size_func: DatabaseSizeFunc | None = None,
) -> dict[str, Any]:
    limit_key = get_raw_mqtt_db_limit(db)
    limit_bytes = raw_mqtt_limit_bytes(limit_key)
    threshold_bytes = _threshold_bytes(limit_bytes)
    sqlite = _is_sqlite(db)
    database_size_bytes = _database_size(db) if database_size_func is None else database_size_func(db)
    oldest_received_at, newest_received_at = _raw_mqtt_bounds(db)
    raw_count = int(db.scalar(select(func.count()).select_from(RawMqttMessage)) or 0)
    archive_summary = _raw_mqtt_archive_summary(db)
    return {
        "raw_mqtt_db_limit": limit_key,
        "limit_bytes": limit_bytes,
        "trigger_threshold_bytes": threshold_bytes,
        "database_size_bytes": database_size_bytes,
        "sqlite": sqlite,
        "enforcement_supported": sqlite,
        "is_over_threshold": _is_over_threshold(database_size_bytes, limit_bytes),
        "raw_mqtt_hot_retention_hours": _raw_mqtt_hot_retention_hours(),
        "raw_mqtt_archive_enabled": _raw_mqtt_archive_enabled(),
        "raw_mqtt_row_count": raw_count,
        "raw_mqtt_payload_bytes_estimate": _raw_payload_bytes_estimate(db),
        "raw_mqtt_oldest_received_at": oldest_received_at,
        "raw_mqtt_newest_received_at": newest_received_at,
        **archive_summary,
        "retention_running": _is_running(),
        "retention_running_since": _running_since,
        "last_cleanup": _last_result,
    }


def schedule_raw_mqtt_retention_check(*, throttled: bool = True) -> bool:
    global _last_scheduled_monotonic, _worker_thread

    if db_session.SessionLocal is None:
        return False
    now = time.monotonic()
    with _scheduler_lock:
        if throttled and now - _last_scheduled_monotonic < RETENTION_CHECK_THROTTLE_SECONDS:
            return False
        if _worker_thread is not None and _worker_thread.is_alive():
            return False
        if throttled:
            _last_scheduled_monotonic = now
        _worker_thread = threading.Thread(target=_run_scheduled_retention_check, daemon=True)
        _worker_thread.start()
        return True


def enforce_raw_mqtt_retention(
    db: Session,
    *,
    database_size_func: DatabaseSizeFunc | None = None,
    limit_bytes_override: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not _retention_lock.acquire(blocking=False):
        return _cleanup_result(
            started_at=utc_now(),
            finished_at=utc_now(),
            skipped_reason="already_running",
        )

    global _running_since, _last_result
    started_at = utc_now()
    _running_since = started_at
    try:
        result = _enforce_raw_mqtt_retention_locked(
            db,
            started_at=started_at,
            database_size_func=database_size_func or _database_size,
            limit_bytes_override=limit_bytes_override,
            now=now or datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001 - retention must not break MQTT ingestion.
        LOGGER.exception("Raw MQTT retention cleanup failed")
        result = _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            error=str(exc),
        )
    finally:
        _running_since = None
        _retention_lock.release()
    _last_result = result
    return result


def _enforce_raw_mqtt_retention_locked(
    db: Session,
    *,
    started_at: datetime,
    database_size_func: DatabaseSizeFunc,
    limit_bytes_override: int | None,
    now: datetime,
) -> dict[str, Any]:
    limit_key = get_raw_mqtt_db_limit(db)
    configured_limit_bytes = raw_mqtt_limit_bytes(limit_key)
    limit_bytes = limit_bytes_override if limit_bytes_override is not None else configured_limit_bytes
    threshold_bytes = _threshold_bytes(limit_bytes)
    size_before = database_size_func(db)
    hot_retention_hours = _raw_mqtt_hot_retention_hours()
    archive_enabled = _raw_mqtt_archive_enabled()

    if not _is_sqlite(db):
        return _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            limit_key=limit_key,
            limit_bytes=limit_bytes,
            threshold_bytes=threshold_bytes,
            database_size_before_bytes=size_before,
            database_size_after_bytes=size_before,
            raw_mqtt_hot_retention_hours=hot_retention_hours,
            archive_enabled=archive_enabled,
            skipped_reason="non_sqlite",
        )

    if not archive_enabled:
        return _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            limit_key=limit_key,
            limit_bytes=limit_bytes,
            threshold_bytes=threshold_bytes,
            database_size_before_bytes=size_before,
            database_size_after_bytes=size_before,
            raw_mqtt_hot_retention_hours=hot_retention_hours,
            archive_enabled=False,
            skipped_reason="archive_disabled",
        )

    deleted_rows = 0
    nullified_device_metric_samples = 0
    nullified_ams_slot_history_samples = 0
    archive_count = 0
    archived_rows = 0
    archive_bytes = 0
    archive_ids: list[int] = []

    for _round in range(ARCHIVE_MAX_BATCHES_PER_RUN):
        batch = _select_archive_batch(db, now=now, hot_retention_hours=hot_retention_hours)
        if not batch:
            break
        archive_file = _write_raw_mqtt_archive(db, batch, hot_retention_hours=hot_retention_hours, now=now)
        ids = [row.id for row in batch]
        with db_session.sqlite_write_lock:
            nullified_device_metric_samples += int(
                db.execute(
                    update(DeviceMetricSample)
                    .where(DeviceMetricSample.raw_message_id.in_(ids))
                    .values(raw_message_id=None)
                ).rowcount
                or 0
            )
            nullified_ams_slot_history_samples += int(
                db.execute(
                    update(AmsSlotHistorySample)
                    .where(AmsSlotHistorySample.raw_message_id.in_(ids))
                    .values(raw_message_id=None)
                ).rowcount
                or 0
            )
            deleted = int(db.execute(delete(RawMqttMessage).where(RawMqttMessage.id.in_(ids))).rowcount or 0)
            archive = RawMqttArchive(
                file_path=str(archive_file.file_path),
                file_format=RAW_MQTT_ARCHIVE_FORMAT,
                row_count=archive_file.row_count,
                compressed_size_bytes=archive_file.compressed_size_bytes,
                first_raw_message_id=archive_file.first_raw_message_id,
                last_raw_message_id=archive_file.last_raw_message_id,
                first_received_at=archive_file.first_received_at,
                last_received_at=archive_file.last_received_at,
                printer_ids=archive_file.printer_ids,
                command_counts=archive_file.command_counts,
                sha256=archive_file.sha256,
            )
            db.add(archive)
            db.flush()
            archive_id = int(archive.id)
            db.commit()
        deleted_rows += deleted
        archived_rows += archive_file.row_count
        archive_bytes += archive_file.compressed_size_bytes
        archive_count += 1
        archive_ids.append(archive_id)
        if len(batch) < ARCHIVE_BATCH_SIZE:
            break

    size_after = database_size_func(db)

    return _cleanup_result(
        started_at=started_at,
        finished_at=utc_now(),
        limit_key=limit_key,
        limit_bytes=limit_bytes,
        threshold_bytes=threshold_bytes,
        database_size_before_bytes=size_before,
        database_size_after_bytes=size_after,
        raw_mqtt_hot_retention_hours=hot_retention_hours,
        archive_enabled=archive_enabled,
        archive_count=archive_count,
        archived_rows=archived_rows,
        archive_bytes=archive_bytes,
        archive_ids=archive_ids,
        deleted_rows=deleted_rows,
        nullified_device_metric_samples=nullified_device_metric_samples,
        nullified_ams_slot_history_samples=nullified_ams_slot_history_samples,
        vacuumed=False,
        blocked_non_raw_size=False,
        skipped_reason=None if archived_rows else "no_archive_candidates",
    )


def _select_archive_batch(
    db: Session,
    *,
    now: datetime,
    hot_retention_hours: int,
) -> list[RawMqttMessage]:
    cutoff = now - timedelta(hours=hot_retention_hours)
    protected_ids = _latest_raw_ids_per_printer(db)
    criteria = [RawMqttMessage.received_at < cutoff]
    if protected_ids:
        criteria.append(RawMqttMessage.id.notin_(protected_ids))
    return list(
        db.scalars(
            select(RawMqttMessage)
            .where(*criteria)
            .order_by(RawMqttMessage.received_at.asc(), RawMqttMessage.id.asc())
            .limit(ARCHIVE_BATCH_SIZE)
        ).all()
    )


def _write_raw_mqtt_archive(
    db: Session,
    rows: list[RawMqttMessage],
    *,
    hot_retention_hours: int,
    now: datetime,
) -> _ArchiveFile:
    if not rows:
        raise ValueError("Cannot archive an empty raw MQTT batch")

    archive_dir = _raw_mqtt_archive_dir(db)
    archive_dir.mkdir(parents=True, exist_ok=True)

    raw_ids = [int(row.id) for row in rows]
    received_at_values = [_coerce_datetime(row.received_at) for row in rows]
    first_received_at = min(received_at_values)
    last_received_at = max(received_at_values)
    printer_ids = sorted({int(row.printer_id) for row in rows})
    command_counts = dict(sorted(Counter(str(row.command or "unknown") for row in rows).items()))
    jsonl_text = "".join(_raw_mqtt_jsonl_line(row) for row in rows)
    jsonl_sha256 = hashlib.sha256(jsonl_text.encode("utf-8")).hexdigest()
    manifest = {
        "format": RAW_MQTT_ARCHIVE_FORMAT,
        "version": 1,
        "created_at": utc_now().isoformat(),
        "hot_retention_hours": hot_retention_hours,
        "cutoff_received_at": (now - timedelta(hours=hot_retention_hours)).isoformat(),
        "row_count": len(rows),
        "first_raw_message_id": min(raw_ids),
        "last_raw_message_id": max(raw_ids),
        "first_received_at": first_received_at.isoformat(),
        "last_received_at": last_received_at.isoformat(),
        "printer_ids": printer_ids,
        "command_counts": command_counts,
        "raw_mqtt_jsonl_sha256": jsonl_sha256,
    }

    target_path = _unique_archive_path(
        archive_dir,
        first_received_at=first_received_at,
        first_raw_id=min(raw_ids),
        last_raw_id=max(raw_ids),
    )
    temp_path = target_path.with_name(f"{target_path.name}.tmp")
    try:
        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default))
            archive.writestr("raw_mqtt.jsonl", jsonl_text)
        temp_path.replace(target_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return _ArchiveFile(
        file_path=target_path,
        row_count=len(rows),
        compressed_size_bytes=target_path.stat().st_size,
        first_raw_message_id=min(raw_ids),
        last_raw_message_id=max(raw_ids),
        first_received_at=first_received_at,
        last_received_at=last_received_at,
        printer_ids=printer_ids,
        command_counts=command_counts,
        sha256=_file_sha256(target_path),
    )


def _latest_raw_ids_per_printer(db: Session) -> set[int]:
    printer_ids = list(db.scalars(select(distinct(RawMqttMessage.printer_id))).all())
    protected: set[int] = set()
    for printer_id in printer_ids:
        protected.update(
            int(row_id)
            for row_id in db.scalars(
                select(RawMqttMessage.id)
                .where(RawMqttMessage.printer_id == printer_id)
                .order_by(RawMqttMessage.received_at.desc(), RawMqttMessage.id.desc())
                .limit(PROTECT_LATEST_PER_PRINTER)
            ).all()
        )
    return protected


def _run_scheduled_retention_check() -> None:
    if db_session.SessionLocal is None:
        return
    db = db_session.SessionLocal()
    try:
        enforce_raw_mqtt_retention(db)
    finally:
        db.close()


def _threshold_bytes(limit_bytes: int | None) -> int | None:
    if limit_bytes is None:
        return None
    return int(limit_bytes * TRIGGER_MULTIPLIER)


def _is_over_threshold(database_size_bytes: int, limit_bytes: int | None) -> bool:
    if limit_bytes is None:
        return False
    return database_size_bytes >= int(limit_bytes * TRIGGER_MULTIPLIER)


def _is_sqlite(db: Session) -> bool:
    bind = db.get_bind()
    return bind.dialect.name == "sqlite"


def _database_size(db: Session) -> int:
    if not _is_sqlite(db):
        return 0
    path = _sqlite_database_path(db.get_bind())
    if path is None or not path.exists():
        return 0
    return path.stat().st_size


def _sqlite_database_path(bind: Engine) -> Path | None:
    database = bind.url.database
    if not database or database == ":memory:":
        return None
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _raw_mqtt_archive_dir(db: Session) -> Path:
    path = _sqlite_database_path(db.get_bind())
    if path is None:
        raise RuntimeError("Raw MQTT archive directory is unavailable for this database")
    return path.parent / ".runtime" / "raw-mqtt-archives"


def _unique_archive_path(
    archive_dir: Path,
    *,
    first_received_at: datetime,
    first_raw_id: int,
    last_raw_id: int,
) -> Path:
    timestamp = _coerce_datetime(first_received_at).strftime("%Y%m%dT%H%M%SZ")
    base = f"raw-mqtt-{timestamp}-{first_raw_id}-{last_raw_id}"
    candidate = archive_dir / f"{base}.zip"
    suffix = 1
    while candidate.exists() or candidate.with_name(f"{candidate.name}.tmp").exists():
        suffix += 1
        candidate = archive_dir / f"{base}-{suffix}.zip"
    return candidate


def _raw_mqtt_jsonl_line(row: RawMqttMessage) -> str:
    payload = {
        "id": row.id,
        "printer_id": row.printer_id,
        "topic": row.topic,
        "command": row.command,
        "payload": row.payload,
        "received_at": _coerce_datetime(row.received_at).isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n"


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_mqtt_bounds(db: Session) -> tuple[datetime | None, datetime | None]:
    return (
        db.scalar(select(func.min(RawMqttMessage.received_at))),
        db.scalar(select(func.max(RawMqttMessage.received_at))),
    )


def _raw_payload_bytes_estimate(db: Session) -> int:
    if not _is_sqlite(db):
        return 0
    value = db.scalar(text("SELECT COALESCE(SUM(length(payload)), 0) FROM raw_mqtt_messages"))
    return int(value or 0)


def _raw_mqtt_archive_summary(db: Session) -> dict[str, Any]:
    row = db.execute(
        select(
            func.count(RawMqttArchive.id),
            func.coalesce(func.sum(RawMqttArchive.row_count), 0),
            func.coalesce(func.sum(RawMqttArchive.compressed_size_bytes), 0),
            func.min(RawMqttArchive.first_received_at),
            func.max(RawMqttArchive.last_received_at),
            func.max(RawMqttArchive.created_at),
        )
    ).one()
    return {
        "raw_mqtt_archive_count": int(row[0] or 0),
        "raw_mqtt_archive_row_count": int(row[1] or 0),
        "raw_mqtt_archive_compressed_bytes": int(row[2] or 0),
        "raw_mqtt_archive_oldest_received_at": row[3],
        "raw_mqtt_archive_newest_received_at": row[4],
        "raw_mqtt_archive_last_created_at": row[5],
    }


def _raw_mqtt_hot_retention_hours() -> int:
    return max(int(get_settings().raw_mqtt_hot_retention_hours or 24), 1)


def _raw_mqtt_archive_enabled() -> bool:
    return bool(get_settings().raw_mqtt_archive_enabled)


def _is_running() -> bool:
    return _running_since is not None


def _cleanup_result(
    *,
    started_at: datetime,
    finished_at: datetime,
    limit_key: str | None = None,
    limit_bytes: int | None = None,
    threshold_bytes: int | None = None,
    database_size_before_bytes: int | None = None,
    database_size_after_bytes: int | None = None,
    raw_mqtt_hot_retention_hours: int | None = None,
    archive_enabled: bool | None = None,
    archive_count: int = 0,
    archived_rows: int = 0,
    archive_bytes: int = 0,
    archive_ids: list[int] | None = None,
    deleted_rows: int = 0,
    nullified_device_metric_samples: int = 0,
    nullified_ams_slot_history_samples: int = 0,
    vacuumed: bool = False,
    blocked_non_raw_size: bool = False,
    skipped_reason: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "raw_mqtt_db_limit": limit_key,
        "limit_bytes": limit_bytes,
        "trigger_threshold_bytes": threshold_bytes,
        "database_size_before_bytes": database_size_before_bytes,
        "database_size_after_bytes": database_size_after_bytes,
        "raw_mqtt_hot_retention_hours": raw_mqtt_hot_retention_hours,
        "archive_enabled": archive_enabled,
        "archive_count": archive_count,
        "archived_rows": archived_rows,
        "archive_bytes": archive_bytes,
        "archive_ids": archive_ids or [],
        "deleted_rows": deleted_rows,
        "nullified_device_metric_samples": nullified_device_metric_samples,
        "nullified_ams_slot_history_samples": nullified_ams_slot_history_samples,
        "vacuumed": vacuumed,
        "blocked_non_raw_size": blocked_non_raw_size,
        "skipped_reason": skipped_reason,
        "error": error,
    }


def _reset_retention_state_for_tests() -> None:
    global _last_scheduled_monotonic, _worker_thread, _running_since, _last_result
    _last_scheduled_monotonic = 0.0
    _worker_thread = None
    _running_since = None
    _last_result = None
