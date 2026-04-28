from __future__ import annotations


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
    assert info.json()["configured_printers"] == 1

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


def test_device_capabilities_are_conservative_for_p2s(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, {**printer_payload, "name": "Workshop P2S"})

    capabilities = api_client.get(f"/api/printers/{printer_id}/capabilities")
    assert capabilities.status_code == 200
    body = capabilities.json()
    assert body["model_family"] == "p2"
    assert body["has_carbon_rods"] is False
    assert "carbon_rod_cleaning" not in body["recommended_maintenance"]
