from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from filament_manager.db import session as db_session
from filament_manager.db.models import (
    AmsSlotHistorySample,
    DeviceMetricSample,
    Printer,
    PrinterEvent,
    PrintLogEntry,
    RawMqttMessage,
)
from filament_manager.services.database_retention import (
    DEFAULT_RAW_MQTT_DB_LIMIT,
    enforce_raw_mqtt_retention,
    get_raw_mqtt_db_limit,
    set_raw_mqtt_db_limit,
    _reset_retention_state_for_tests,
)


def _db_session():
    assert db_session.SessionLocal is not None
    return db_session.SessionLocal()


def _printer(db) -> Printer:
    printer = Printer(
        name="Retention Printer",
        host="printer.local",
        port=8883,
        serial="RETENTION123",
        access_code="secret",
        tls_enabled=True,
        certificate_verify=False,
    )
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return printer


def _raw_messages(db, printer_id: int, count: int, *, start: datetime) -> list[RawMqttMessage]:
    rows: list[RawMqttMessage] = []
    for index in range(count):
        rows.append(
            RawMqttMessage(
                printer_id=printer_id,
                topic="device/RETENTION123/report",
                command="push_status",
                payload={"print": {"command": "push_status", "sequence_id": index}, "padding": "x" * 40},
                received_at=start + timedelta(seconds=index),
            )
        )
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def test_database_retention_api_defaults_and_validation(api_client) -> None:
    response = api_client.get("/api/debug/database-retention")
    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_mqtt_db_limit"] == "5gb"
    assert payload["limit_bytes"] == 5 * 1024**3
    assert payload["trigger_threshold_bytes"] == int(5 * 1024**3 * 1.05)

    updated = api_client.patch("/api/debug/database-retention", json={"raw_mqtt_db_limit": "unlimited"})
    assert updated.status_code == 200
    assert updated.json()["raw_mqtt_db_limit"] == "unlimited"
    assert updated.json()["limit_bytes"] is None

    rejected = api_client.patch("/api/debug/database-retention", json={"raw_mqtt_db_limit": "2gb"})
    assert rejected.status_code == 422


def test_default_setting_is_5gb_and_unlimited_skips_cleanup(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        assert get_raw_mqtt_db_limit(db) == DEFAULT_RAW_MQTT_DB_LIMIT
        set_raw_mqtt_db_limit(db, "unlimited")
        result = enforce_raw_mqtt_retention(db, database_size_func=lambda _db: 10**12)
        assert result["skipped_reason"] == "unlimited"
        assert result["deleted_rows"] == 0
        assert result["vacuumed"] is False
    finally:
        db.close()


def test_retention_threshold_boundary(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        below = enforce_raw_mqtt_retention(db, database_size_func=lambda _db: 104, limit_bytes_override=100)
        assert below["skipped_reason"] == "below_threshold"

        at_threshold = enforce_raw_mqtt_retention(db, database_size_func=lambda _db: 105, limit_bytes_override=100)
        assert at_threshold["skipped_reason"] is None
        assert at_threshold["blocked_non_raw_size"] is True
        assert at_threshold["deleted_rows"] == 0
    finally:
        db.close()


def test_retention_deletes_oldest_raw_only_and_nulls_references(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    vacuum_calls: list[bool] = []
    try:
        printer = _printer(db)
        raw_rows = _raw_messages(
            db,
            printer.id,
            105,
            start=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        first_raw = raw_rows[0]
        first_raw_id = first_raw.id
        protected_raw_ids = {row.id for row in raw_rows[-100:]}
        db.add(
            DeviceMetricSample(
                printer_id=printer.id,
                metric="nozzle_temperature",
                value_float=210.0,
                raw_message_id=first_raw_id,
                details={},
                sampled_at=first_raw.received_at,
            )
        )
        db.add(
            AmsSlotHistorySample(
                printer_id=printer.id,
                ams_id="0",
                tray_id="0",
                state_name="loaded",
                sampled_at=first_raw.received_at,
                raw_message_id=first_raw_id,
            )
        )
        db.add(PrintLogEntry(printer_id=printer.id, task_id="task-1", status="running", raw_refs={"first_raw_mqtt_id": first_raw_id}))
        db.add(PrinterEvent(printer_id=printer.id, event_type="print.started", severity="info", message="started"))
        db.commit()

        sizes = iter([106, 90])
        result = enforce_raw_mqtt_retention(
            db,
            database_size_func=lambda _db: next(sizes, 90),
            vacuum_func=lambda _db: vacuum_calls.append(True),
            limit_bytes_override=100,
        )

        assert result["deleted_rows"] == 1
        assert result["vacuumed"] is True
        assert vacuum_calls == [True]
        db.expire_all()
        assert db.get(RawMqttMessage, first_raw_id) is None
        remaining_ids = set(db.scalars(select(RawMqttMessage.id)).all())
        assert protected_raw_ids.issubset(remaining_ids)

        metric = db.scalars(select(DeviceMetricSample)).one()
        history = db.scalars(select(AmsSlotHistorySample)).one()
        assert metric.raw_message_id is None
        assert history.raw_message_id is None
        assert db.scalars(select(PrintLogEntry)).one().raw_refs["first_raw_mqtt_id"] == first_raw_id
        assert db.scalars(select(PrinterEvent)).one().event_type == "print.started"
    finally:
        db.close()


def test_retention_blocks_when_only_recent_or_protected_raw_remains(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        printer = _printer(db)
        _raw_messages(db, printer.id, 2, start=datetime.now(timezone.utc))
        result = enforce_raw_mqtt_retention(
            db,
            database_size_func=lambda _db: 106,
            vacuum_func=lambda _db: (_ for _ in ()).throw(AssertionError("VACUUM should not run")),
            limit_bytes_override=100,
        )
        assert result["blocked_non_raw_size"] is True
        assert result["deleted_rows"] == 0
        assert result["vacuumed"] is False
    finally:
        db.close()
