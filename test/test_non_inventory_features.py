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
