from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import zipfile

from sqlalchemy import select

from filament_manager.db import session as db_session
from filament_manager.db.models import (
    AmsSlotHistorySample,
    DeviceMetricSample,
    Printer,
    PrinterEvent,
    PrintLogEntry,
    RawMqttArchive,
    RawMqttMessage,
)
from filament_manager.services import database_retention as retention_service
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
    assert payload["raw_mqtt_hot_retention_hours"] == 24
    assert payload["raw_mqtt_archive_enabled"] is True
    assert payload["raw_mqtt_archive_count"] == 0
    assert payload["raw_mqtt_archive_row_count"] == 0

    archives = api_client.get("/api/debug/raw-mqtt-archives")
    assert archives.status_code == 200
    assert archives.json() == []

    updated = api_client.patch("/api/debug/database-retention", json={"raw_mqtt_db_limit": "unlimited"})
    assert updated.status_code == 200
    assert updated.json()["raw_mqtt_db_limit"] == "unlimited"
    assert updated.json()["limit_bytes"] is None

    rejected = api_client.patch("/api/debug/database-retention", json={"raw_mqtt_db_limit": "2gb"})
    assert rejected.status_code == 422


def test_default_setting_is_5gb_and_unlimited_still_keeps_hot_retention(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        assert get_raw_mqtt_db_limit(db) == DEFAULT_RAW_MQTT_DB_LIMIT
        set_raw_mqtt_db_limit(db, "unlimited")
        result = enforce_raw_mqtt_retention(db, database_size_func=lambda _db: 10**12)
        assert result["skipped_reason"] == "no_archive_candidates"
        assert result["deleted_rows"] == 0
        assert result["vacuumed"] is False
    finally:
        db.close()


def test_retention_skips_when_only_hot_or_protected_raw_remains(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        printer = _printer(db)
        _raw_messages(db, printer.id, 2, start=datetime.now(timezone.utc) - timedelta(days=3))
        result = enforce_raw_mqtt_retention(db, database_size_func=lambda _db: 10**12, limit_bytes_override=100)
        assert result["skipped_reason"] == "no_archive_candidates"
        assert result["blocked_non_raw_size"] is False
        assert result["deleted_rows"] == 0
        assert result["vacuumed"] is False
    finally:
        db.close()


def test_retention_archives_oldest_raw_only_and_nulls_references(api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        printer = _printer(db)
        raw_rows = _raw_messages(
            db,
            printer.id,
            105,
            start=datetime.now(timezone.utc) - timedelta(days=2),
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

        result = enforce_raw_mqtt_retention(
            db,
            database_size_func=lambda _db: 10**12,
            limit_bytes_override=100,
            now=datetime.now(timezone.utc),
        )

        assert result["archive_count"] == 1
        assert result["archived_rows"] == 5
        assert result["deleted_rows"] == 5
        assert result["vacuumed"] is False
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

        archive = db.scalars(select(RawMqttArchive)).one()
        assert archive.row_count == 5
        assert archive.file_format == "zip"
        assert archive.first_raw_message_id == raw_rows[0].id
        assert archive.last_raw_message_id == raw_rows[4].id
        assert archive.printer_ids == [printer.id]
        assert archive.command_counts == {"push_status": 5}
        with zipfile.ZipFile(archive.file_path) as archive_zip:
            manifest = json.loads(archive_zip.read("manifest.json"))
            jsonl_rows = archive_zip.read("raw_mqtt.jsonl").decode("utf-8").splitlines()
        assert manifest["row_count"] == 5
        assert manifest["first_raw_message_id"] == raw_rows[0].id
        assert manifest["last_raw_message_id"] == raw_rows[4].id
        assert len(jsonl_rows) == 5
    finally:
        db.close()


def test_raw_mqtt_archive_api_lists_and_downloads_zip(api_client) -> None:
    _reset_retention_state_for_tests()
    with _db_session() as db:
        printer = _printer(db)
        _raw_messages(db, printer.id, 105, start=datetime.now(timezone.utc) - timedelta(days=2))
        enforce_raw_mqtt_retention(db)

    listed = api_client.get("/api/debug/raw-mqtt-archives")
    assert listed.status_code == 200
    archives = listed.json()
    assert len(archives) == 1
    assert archives[0]["row_count"] == 5

    downloaded = api_client.get(f"/api/debug/raw-mqtt-archives/{archives[0]['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    assert downloaded.content.startswith(b"PK")


def test_archive_failure_does_not_delete_raw(monkeypatch, api_client) -> None:
    _reset_retention_state_for_tests()
    db = _db_session()
    try:
        printer = _printer(db)
        rows = _raw_messages(db, printer.id, 105, start=datetime.now(timezone.utc) - timedelta(days=2))
        first_raw_id = rows[0].id

        def fail_archive(*_args, **_kwargs):
            raise RuntimeError("archive write failed")

        monkeypatch.setattr(retention_service, "_write_raw_mqtt_archive", fail_archive)
        result = enforce_raw_mqtt_retention(db)

        assert result["error"] == "archive write failed"
        assert result["deleted_rows"] == 0
        assert db.get(RawMqttMessage, first_raw_id) is not None
        assert db.scalars(select(RawMqttArchive)).all() == []
    finally:
        db.close()
