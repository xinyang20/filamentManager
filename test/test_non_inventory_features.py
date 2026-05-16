from __future__ import annotations

import io
import struct
import ssl
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from filament_manager.db import session as db_session
from filament_manager.db.models import PrintLogEntry, Printer, RawMqttMessage
from filament_manager.services import ams as ams_service
from filament_manager.services import camera as camera_service
from filament_manager.services import observability as observability_service
from filament_manager.services.print_log import repair_print_log_printer_ids_from_raw_topics


def _create_printer(api_client, printer_payload) -> int:
    response = api_client.post("/api/printers", json=printer_payload)
    assert response.status_code == 201
    return response.json()["id"]


def _ingest(api_client, printer_id: int, payload: dict) -> None:
    response = api_client.post(
        f"/api/printers/{printer_id}/mqtt/payload",
        json={"topic": "device/SYNTHETIC123/report", "payload": payload},
    )
    assert response.status_code == 200, response.text


def _push_status(state: str = "RUNNING", progress: int = 10) -> dict:
    return {
        "print": {
            "command": "push_status",
            "gcode_state": state,
            "mc_percent": progress,
            "mc_remaining_time": 12,
            "gcode_file": "/Metadata/plate_1.gcode",
            "subtask_name": "Calibration Cube",
            "task_id": "log-task-1",
            "layer_num": 3,
            "total_layer_num": 24,
            "wifi_signal": "-50dBm",
            "bed_temper": "60",
            "nozzle_temper": "210",
            "ams": {
                "tray_now": "0",
                "ams_status": 258,
                "ams": [
                    {
                        "id": "0",
                        "humidity": "3",
                        "humidity_raw": "42",
                        "temp": "27.5",
                        "module_type": "n3",
                        "tray": [
                            {
                                "id": "0",
                                "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                "tray_type": "PLA",
                                "tray_color": "FF6600",
                                "remain": 80,
                                "state": 11,
                                "k": 0.02,
                                "cali_idx": 1,
                            }
                        ],
                    }
                ],
            },
        }
    }


def test_bambu_local_video_auth_packet_uses_documented_layout() -> None:
    packet = camera_service._bambu_local_video_auth_packet("secret")  # noqa: SLF001

    assert len(packet) == 80
    assert packet[:16] == struct.pack("<IIII", 0x40, 0x3000, 0, 0)
    assert packet[16:48].rstrip(b"\x00") == b"bblp"
    assert packet[48:80].rstrip(b"\x00") == b"secret"


def test_camera_jpeg_parser_handles_split_frames() -> None:
    first = b"\xff\xd8first-frame\xff\xd9"
    second = b"\xff\xd8second-frame\xff\xd9"

    frames = list(camera_service._jpeg_images_from_chunks([b"noise" + first[:5], first[5:] + b"gap", second]))  # noqa: SLF001

    assert frames == [first, second]


def test_camera_capabilities_prefers_rtsps_for_p2s_when_available(monkeypatch) -> None:
    printer = SimpleNamespace(
        id=7,
        name="Workshop P2S",
        host="printer.local",
        access_code="secret-access-code",
        certificate_verify=False,
    )

    def fake_port_check(_host: str, port: int, *, timeout: float) -> bool:
        return port == 322

    monkeypatch.setattr(camera_service, "_is_tcp_port_open", fake_port_check)

    capabilities = camera_service.camera_capabilities(printer)

    assert capabilities["available"] is True
    assert capabilities["source"] == "rtsps"
    assert capabilities["stream_path"] == "/printers/7/camera/mjpeg"
    assert "secret-access-code" not in str(capabilities)


def test_camera_capabilities_does_not_fallback_to_6000_for_p2s(monkeypatch) -> None:
    printer = SimpleNamespace(
        id=7,
        name="Workshop P2S",
        host="printer.local",
        access_code="secret-access-code",
        certificate_verify=False,
    )

    def fake_port_check(_host: str, port: int, *, timeout: float) -> bool:
        return port == 6000

    monkeypatch.setattr(camera_service, "_is_tcp_port_open", fake_port_check)

    capabilities = camera_service.camera_capabilities(printer)

    assert capabilities["available"] is False
    assert capabilities["source"] is None
    assert "322" in capabilities["detail"]


def test_camera_stream_family_recognizes_p2s_internal_code() -> None:
    config = camera_service.CameraPrinterConfig(
        id=7,
        name="Workshop",
        host="printer.local",
        access_code="secret-access-code",
        certificate_verify=False,
    )
    snapshot = SimpleNamespace(camera={}, hardware={"model_code": "N7"})

    assert camera_service._camera_stream_family(config, snapshot) == "rtsps"  # noqa: SLF001


def test_camera_tls_context_respects_certificate_verify() -> None:
    insecure = camera_service.CameraPrinterConfig(
        id=7,
        name="Workshop",
        host="printer.local",
        access_code="secret-access-code",
        certificate_verify=False,
    )
    secure = camera_service.CameraPrinterConfig(
        id=8,
        name="Workshop",
        host="printer.local",
        access_code="secret-access-code",
        certificate_verify=True,
    )

    insecure_context = camera_service._camera_tls_context(insecure)  # noqa: SLF001
    secure_context = camera_service._camera_tls_context(secure)  # noqa: SLF001

    assert insecure_context.check_hostname is False
    assert insecure_context.verify_mode == ssl.CERT_NONE
    assert secure_context.check_hostname is True
    assert secure_context.verify_mode == ssl.CERT_REQUIRED


def test_rtsp_proxy_rewrites_digest_auth_without_leaking_secret() -> None:
    config = camera_service.CameraPrinterConfig(
        id=7,
        name="Workshop",
        host="192.0.2.50",
        access_code="secret-access-code",
        certificate_verify=False,
    )
    payload = (
        b"DESCRIBE rtsp://127.0.0.1:12345/streaming/live/1 RTSP/1.0\r\n"
        b"CSeq: 2\r\n"
        b"Authorization: Digest username=\"bblp\", realm=\"Bambu\", nonce=\"abc123\", "
        b"uri=\"rtsp://127.0.0.1:12345/streaming/live/1\", response=\"local-response\", "
        b"algorithm=MD5, qop=auth, nc=00000001, cnonce=\"client123\"\r\n"
        b"\r\n"
    )

    rewritten = camera_service._rewrite_rtsp_client_request(  # noqa: SLF001
        payload,
        b"rtsp://127.0.0.1:12345",
        camera_service._target_rtsp_proxy_base_url(config, 322).encode("ascii"),  # noqa: SLF001
        config,
    )

    assert rewritten.startswith(b"DESCRIBE rtsps://192.0.2.50:322/streaming/live/1 RTSP/1.0\r\n")
    assert b'uri="rtsps://192.0.2.50:322/streaming/live/1"' in rewritten
    assert b"local-response" not in rewritten
    assert b"secret-access-code" not in rewritten


def test_ffmpeg_rtsp_command_does_not_expose_access_code() -> None:
    config = camera_service.CameraPrinterConfig(
        id=7,
        name="Workshop",
        host="192.0.2.50",
        access_code="secret-access-code",
        certificate_verify=False,
    )
    url = camera_service._local_rtsp_proxy_url(  # noqa: SLF001
        config,
        12345,
        "rtsps://bblp:secret-access-code@192.0.2.50:322/streaming/live/1",
    )
    command = camera_service._ffmpeg_rtsp_mjpeg_command(  # noqa: SLF001
        "/tmp/ffmpeg",
        url,
    )

    assert command[0] == "/tmp/ffmpeg"
    assert "-rtsp_flags" in command
    assert "prefer_tcp" in command
    assert "rtsp://bblp:filamentmanager@127.0.0.1:12345/streaming/live/1" in command
    assert "secret-access-code" not in " ".join(command)


def test_process_table_excludes_sampler_process(monkeypatch) -> None:
    class FakeProcess:
        pid = 1234
        returncode = 0

        def communicate(self, timeout: int | None = None) -> tuple[str, str]:
            return (
                "100 1 2048\n"
                "1234 999 1024\n"
                "200 100 4096\n",
                "",
            )

    monkeypatch.setattr(observability_service.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    table = observability_service._process_table()  # noqa: SLF001

    assert 100 in table
    assert 200 in table
    assert 1234 not in table


def test_ams_label_and_sensor_history_are_local_read_only_features(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _push_status())

    label = api_client.patch(
        f"/api/printers/{printer_id}/ams-labels/0",
        json={"display_name": "Dry Box"},
    )
    assert label.status_code == 200, label.text
    assert label.json()["display_name"] == "Dry Box"

    overview = api_client.get(f"/api/printers/{printer_id}/ams/overview").json()
    assert overview["units"][0]["display_name"] == "Dry Box"
    assert overview["units"][0]["active_slot"]["tray_id"] == "0"

    history = api_client.get(f"/api/printers/{printer_id}/ams/0/sensor-history?hours=24").json()
    assert history["temperature"]["avg"] == 27.5
    assert history["humidity"]["avg"] == 42.0

    deleted = api_client.delete(f"/api/printers/{printer_id}/ams-labels/0")
    assert deleted.status_code == 204
    overview = api_client.get(f"/api/printers/{printer_id}/ams/overview").json()
    assert overview["units"][0]["display_name"] is None


def test_ams_label_save_retries_sqlite_write_lock(monkeypatch) -> None:
    class EmptyScalarResult:
        def first(self):
            return None

    class FakeDb:
        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0
            self.added = []

        def scalars(self, _statement):
            return EmptyScalarResult()

        def add(self, value) -> None:
            self.added.append(value)

        def commit(self) -> None:
            self.commits += 1
            if self.commits == 1:
                raise OperationalError("INSERT INTO ams_labels", {}, Exception("database is locked"))

        def rollback(self) -> None:
            self.rollbacks += 1

        def refresh(self, _value) -> None:
            pass

    monkeypatch.setattr(ams_service.time, "sleep", lambda _seconds: None)
    db = FakeDb()

    label = ams_service.set_ams_label(db, printer_id=2, ams_id="128", display_name=" P2S HT ")

    assert label.display_name == "P2S HT"
    assert db.commits == 2
    assert db.rollbacks == 1
    assert [item.display_name for item in db.added] == ["P2S HT", "P2S HT"]


def test_active_slot_prefers_hall_out_bits_for_ams_ht(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _push_status()
    payload["print"]["ams"] = {
        "tray_now": "0",
        "ams_status": 768,
        "tray_exist_bits": "1000f",
        "tray_hall_out_bits": "10000",
        "ams": [
            {
                "id": "0",
                "module_type": "n3f",
                "humidity": "4",
                "temp": "24.1",
                "tray": [
                    {
                        "id": "0",
                        "tray_uuid": "26F2D70B2E154ABCA57FCD1DBBDBE4E9",
                        "tag_uid": "6210CAEC00000100",
                        "tray_type": "PLA",
                        "tray_sub_brands": "PLA Basic",
                        "tray_color": "000000FF",
                        "tray_id_name": "A00-K00",
                        "remain": 88,
                        "state": 11,
                    }
                ],
            },
            {
                "id": "128",
                "module_type": "n3s",
                "humidity": "5",
                "temp": "21.2",
                "tray": [
                    {
                        "id": "0",
                        "tray_uuid": "72D769764FEF48B3868CDFD876FFC545",
                        "tag_uid": "9C947A6600000100",
                        "tray_type": "PETG",
                        "tray_sub_brands": "PETG Basic",
                        "tray_color": "FFFFFFFF",
                        "tray_id_name": "G00-W00",
                        "remain": 36,
                        "state": 27,
                    }
                ],
            },
        ],
    }

    _ingest(api_client, printer_id, payload)

    overview = api_client.get(f"/api/printers/{printer_id}/ams/overview").json()
    assert overview["summary"]["active_slot"]["ams_id"] == "128"
    assert overview["summary"]["active_slot"]["tray_id"] == "0"
    assert overview["summary"]["active_slot"]["global_tray_id"] == "16"
    units = {item["ams_id"]: item for item in overview["units"]}
    assert units["128"]["active_slot"]["tray_id"] == "0"

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    ht_slot = next(slot for slot in slots if slot["ams_id"] == "128")
    assert ht_slot["global_tray_id"] == "16"


def test_ams_slot_history_accepts_changed_samples_after_reload(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _push_status())

    changed = _push_status()
    changed["print"]["ams"]["ams"][0]["tray"][0]["remain"] = 75
    changed["print"]["ams"]["ams"][0]["tray"][0]["k"] = 0.03
    _ingest(api_client, printer_id, changed)

    history = api_client.get(f"/api/printers/{printer_id}/ams/history?ams_id=0&tray_id=0").json()
    assert len(history) == 2
    assert {item["remain"] for item in history} == {75, 80}


def test_print_log_lifecycle_and_maintenance_perform(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _push_status("RUNNING", 10))
    _ingest(api_client, printer_id, _push_status("RUNNING", 65))
    _ingest(api_client, printer_id, _push_status("FINISH", 100))

    logs = api_client.get(f"/api/print-log?printer_id={printer_id}").json()
    assert logs["total"] == 1
    assert logs["items"][0]["status"] == "succeeded"
    assert logs["items"][0]["max_progress"] == 100
    assert logs["items"][0]["layer_current"] == 3

    summary = api_client.get("/api/print-log/summary").json()
    assert summary["succeeded"] == 1

    maintenance = api_client.get(f"/api/printers/{printer_id}/maintenance").json()
    assert maintenance
    item_id = maintenance[0]["id"]
    performed = api_client.post(
        f"/api/maintenance/items/{item_id}/perform",
        json={"note": "cleaned"},
    )
    assert performed.status_code == 200, performed.text
    assert performed.json()["history_count"] == 1
    history = api_client.get(f"/api/maintenance/items/{item_id}/history").json()
    assert history[0]["note"] == "cleaned"


def test_print_log_repair_uses_raw_topic_serial_when_printer_id_was_reused(api_client, printer_payload) -> None:
    _create_printer(api_client, {**printer_payload, "name": "H2C", "serial": "H2C-SERIAL"})
    _create_printer(api_client, {**printer_payload, "name": "P2S", "serial": "P2S-SERIAL", "host": "p2s.local"})
    assert db_session.SessionLocal is not None
    db = db_session.SessionLocal()
    try:
        first_raw = RawMqttMessage(
            printer_id=1,
            topic="device/P2S-SERIAL/report",
            payload={"print": {"task_id": "old-p2s-task"}},
            received_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
        )
        db.add(first_raw)
        db.flush()
        db.add(
            PrintLogEntry(
                printer_id=1,
                printer_name_snapshot="P2S",
                task_id="old-p2s-task",
                print_name="Old P2S job",
                status="succeeded",
                started_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
                raw_refs={"first_raw_mqtt_id": first_raw.id},
            )
        )
        db.commit()

        repaired = repair_print_log_printer_ids_from_raw_topics(db)
        entry = db.query(PrintLogEntry).filter_by(task_id="old-p2s-task").one()

        assert repaired == 1
        assert entry.printer_id == 2
        assert entry.printer_name_snapshot == "P2S"
    finally:
        db.close()


def test_maintenance_mapping_uses_p2s_motion_parts_and_separate_ams_object(api_client, printer_payload) -> None:
    payload = {**printer_payload, "name": "Workshop P2S"}
    printer_id = _create_printer(api_client, payload)

    maintenance = api_client.get(f"/api/printers/{printer_id}/maintenance").json()
    codes = {item["maintenance_type"]["code"] for item in maintenance}
    assert "carbon_rod_cleaning" not in codes
    assert "x_axis_smooth_rod_cleaning" in codes
    assert "ams_cleaning" not in codes

    _ingest(api_client, printer_id, _push_status())
    maintenance = api_client.get(f"/api/printers/{printer_id}/maintenance").json()
    by_code = {item["maintenance_type"]["code"]: item for item in maintenance}
    assert "carbon_rod_cleaning" not in by_code
    assert by_code["x_axis_smooth_rod_cleaning"]["maintenance_type"]["name"] == "X 轴光轴清洁"
    assert by_code["ams_cleaning"]["target_type"] == "ams"
    assert "AMS" in by_code["ams_cleaning"]["target_label"]


def test_system_info_support_bundle_and_prometheus_default(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _push_status())

    info = api_client.get("/api/system/info")
    assert info.status_code == 200
    info_body = info.json()
    assert info_body["configured_printers"] == 1
    assert info_body["memory"]["project_rss_bytes"] > 0
    assert info_body["memory"]["rss_bytes"] == info_body["memory"]["project_rss_bytes"]
    assert info_body["memory"]["process_count"] >= 1

    bundle = api_client.get("/api/support/bundle")
    assert bundle.status_code == 200
    text = bundle.text
    assert printer_payload["access_code"] not in text
    assert printer_payload["host"] not in text
    assert printer_payload["serial"] not in text
    assert ".docs/local_bambu_test_environment.md" not in text

    metrics = api_client.get("/api/metrics/prometheus")
    assert metrics.status_code == 404


def test_notification_rules_dispatch_locally_without_printer_commands(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    target = api_client.post(
        "/api/notifications/targets",
        json={
            "channel": "webhook",
            "name": "Local mock",
            "enabled": True,
            "config": {"url": "mock://notification-target", "token": "secret-token-1234"},
        },
    )
    assert target.status_code == 201, target.text
    assert "secret-token-1234" not in target.text

    rule = api_client.post(
        "/api/notifications/rules",
        json={
            "name": "HMS rule",
            "enabled": True,
            "event_types": ["hms.error"],
            "printer_ids": [printer_id],
            "severities": ["error", "warning"],
            "quiet_policy": {"repeat_suppression_minutes": 30},
        },
    )
    assert rule.status_code == 201, rule.text

    payload = _push_status()
    payload["print"]["hms"] = [{"attr": "0x05000300", "code": "0x8001"}]
    _ingest(api_client, printer_id, payload)

    deliveries = api_client.get("/api/notifications/deliveries").json()
    assert deliveries
    assert deliveries[0]["event_type"] == "hms.error"
    assert deliveries[0]["status"] == "sent"

    raw = api_client.get("/api/debug/raw-mqtt").json()
    assert [row["command"] for row in raw] == ["push_status"]

    stats = api_client.get("/api/hms/codes/0500_8001/stats").json()
    assert stats["recent_count"] >= 1
    assert printer_id in stats["affected_printers"]


def test_print_log_analytics_timelapse_notes_and_export(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _push_status("RUNNING", 10))
    _ingest(api_client, printer_id, _push_status("FINISH", 100))

    analytics = api_client.get(f"/api/print-log/analytics?printer_id={printer_id}").json()
    assert analytics["succeeded"] == 1
    assert analytics["success_rate"] == 1.0
    assert analytics["by_printer"][0]["printer_id"] == printer_id

    assert api_client.get("/api/projects").status_code == 404

    note = api_client.patch(
        f"/api/printers/{printer_id}/timelapse/notes",
        json={"path": "/timelapse/demo.mp4", "favorite": True, "note": "cover ok", "cached_metadata": {"duration": 12}},
    )
    assert note.status_code == 200, note.text
    notes = api_client.get(f"/api/printers/{printer_id}/timelapse/notes").json()
    assert notes[0]["favorite"] is True
    assert notes[0]["note"] == "cover ok"

    export = api_client.get("/api/export?type=json&sections=config,print_logs,notifications")
    assert export.status_code == 200
    assert printer_payload["access_code"] not in export.text
    assert printer_payload["host"] not in export.text
    assert api_client.get("/api/export?type=json&sections=projects").json()["sections"] == []

    telemetry_export = api_client.get("/api/export?type=json&sections=telemetry")
    assert telemetry_export.status_code == 200
    telemetry_body = telemetry_export.json()
    assert "raw_mqtt_messages" not in telemetry_body["telemetry"]
    assert telemetry_body["excluded_tables"]["telemetry"] == ["raw_mqtt_messages"]
    assert telemetry_body["telemetry"]["printer_state_snapshots"]

    csv_export = api_client.get("/api/export?type=csv&sections=telemetry")
    assert csv_export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(csv_export.content)) as archive:
        manifest = archive.read("manifest.json").decode()
        telemetry_csv = archive.read("telemetry.csv").decode()
    assert "raw_mqtt_messages" in manifest
    assert "raw_mqtt_messages" not in telemetry_csv
    assert "printer_state_snapshots" in telemetry_csv


def test_device_capabilities_are_conservative_for_p2s(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, {**printer_payload, "name": "Workshop P2S"})

    capabilities = api_client.get(f"/api/printers/{printer_id}/capabilities")
    assert capabilities.status_code == 200
    body = capabilities.json()
    assert body["model_family"] == "p2"
    assert body["has_carbon_rods"] is False
    assert "carbon_rod_cleaning" not in body["recommended_maintenance"]
