from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any

from sqlalchemy import delete, distinct, func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from filament_manager.db import session as db_session
from filament_manager.db.models import (
    AmsSlotHistorySample,
    AppSetting,
    DeviceMetricSample,
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
PROTECT_RECENT_SECONDS = 10 * 60
PROTECT_LATEST_PER_PRINTER = 100
RETENTION_CHECK_THROTTLE_SECONDS = 10 * 60
DELETE_BATCH_SIZE = 1000

DatabaseSizeFunc = Callable[[Session], int]
VacuumFunc = Callable[[Session], None]

_scheduler_lock = threading.Lock()
_retention_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_last_scheduled_monotonic = 0.0
_running_since: datetime | None = None
_last_result: dict[str, Any] | None = None


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
    return {
        "raw_mqtt_db_limit": limit_key,
        "limit_bytes": limit_bytes,
        "trigger_threshold_bytes": threshold_bytes,
        "database_size_bytes": database_size_bytes,
        "sqlite": sqlite,
        "enforcement_supported": sqlite,
        "is_over_threshold": _is_over_threshold(database_size_bytes, limit_bytes),
        "raw_mqtt_row_count": raw_count,
        "raw_mqtt_payload_bytes_estimate": _raw_payload_bytes_estimate(db),
        "raw_mqtt_oldest_received_at": oldest_received_at,
        "raw_mqtt_newest_received_at": newest_received_at,
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
    vacuum_func: VacuumFunc | None = None,
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
            vacuum_func=vacuum_func or _vacuum_sqlite,
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
    vacuum_func: VacuumFunc,
    limit_bytes_override: int | None,
    now: datetime,
) -> dict[str, Any]:
    limit_key = get_raw_mqtt_db_limit(db)
    configured_limit_bytes = raw_mqtt_limit_bytes(limit_key)
    limit_bytes = limit_bytes_override if limit_bytes_override is not None else configured_limit_bytes
    threshold_bytes = _threshold_bytes(limit_bytes)
    size_before = database_size_func(db)

    if not _is_sqlite(db):
        return _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            limit_key=limit_key,
            limit_bytes=limit_bytes,
            threshold_bytes=threshold_bytes,
            database_size_before_bytes=size_before,
            database_size_after_bytes=size_before,
            skipped_reason="non_sqlite",
        )

    if limit_bytes is None:
        return _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            limit_key=limit_key,
            limit_bytes=None,
            threshold_bytes=None,
            database_size_before_bytes=size_before,
            database_size_after_bytes=size_before,
            skipped_reason="unlimited",
        )

    if not _is_over_threshold(size_before, limit_bytes):
        return _cleanup_result(
            started_at=started_at,
            finished_at=utc_now(),
            limit_key=limit_key,
            limit_bytes=limit_bytes,
            threshold_bytes=threshold_bytes,
            database_size_before_bytes=size_before,
            database_size_after_bytes=size_before,
            skipped_reason="below_threshold",
        )

    deleted_rows = 0
    nullified_device_metric_samples = 0
    nullified_ams_slot_history_samples = 0
    vacuumed = False
    blocked_non_raw_size = False
    size_after = size_before
    size_current = size_before

    for _round in range(5):
        if size_current <= limit_bytes:
            size_after = size_current
            break
        target_delete_bytes = max(size_current - limit_bytes, 1)
        batch = _select_deletion_batch(db, target_delete_bytes=target_delete_bytes, now=now)
        if not batch:
            blocked_non_raw_size = True
            size_after = size_current
            break
        ids = [row_id for row_id, _payload_bytes in batch]
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
        deleted_rows += int(
            db.execute(delete(RawMqttMessage).where(RawMqttMessage.id.in_(ids))).rowcount or 0
        )
        db.commit()
        vacuum_func(db)
        vacuumed = True
        size_after = database_size_func(db)
        size_current = size_after
        if size_after <= limit_bytes:
            break
    else:
        blocked_non_raw_size = size_after > limit_bytes

    return _cleanup_result(
        started_at=started_at,
        finished_at=utc_now(),
        limit_key=limit_key,
        limit_bytes=limit_bytes,
        threshold_bytes=threshold_bytes,
        database_size_before_bytes=size_before,
        database_size_after_bytes=size_after,
        deleted_rows=deleted_rows,
        nullified_device_metric_samples=nullified_device_metric_samples,
        nullified_ams_slot_history_samples=nullified_ams_slot_history_samples,
        vacuumed=vacuumed,
        blocked_non_raw_size=blocked_non_raw_size,
    )


def _select_deletion_batch(
    db: Session,
    *,
    target_delete_bytes: int,
    now: datetime,
) -> list[tuple[int, int]]:
    cutoff = now - timedelta(seconds=PROTECT_RECENT_SECONDS)
    protected_ids = _latest_raw_ids_per_printer(db)
    criteria = [RawMqttMessage.received_at < cutoff]
    if protected_ids:
        criteria.append(RawMqttMessage.id.notin_(protected_ids))
    rows = list(
        db.execute(
            select(
                RawMqttMessage.id,
                func.coalesce(func.length(RawMqttMessage.payload), 0),
            )
            .where(*criteria)
            .order_by(RawMqttMessage.received_at.asc(), RawMqttMessage.id.asc())
            .limit(DELETE_BATCH_SIZE)
        ).all()
    )
    selected: list[tuple[int, int]] = []
    selected_bytes = 0
    for row_id, payload_bytes in rows:
        selected.append((int(row_id), int(payload_bytes or 0)))
        selected_bytes += max(int(payload_bytes or 0), 1)
        if selected_bytes >= target_delete_bytes:
            break
    return selected


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


def _vacuum_sqlite(db: Session) -> None:
    if not _is_sqlite(db):
        return
    bind = db.get_bind()
    with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM"))


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
