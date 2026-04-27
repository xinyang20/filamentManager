from __future__ import annotations

from filament_manager.api.routes import _sanitize_camera_response
from filament_manager.db.models import AmsSlot
from filament_manager.db import session as db_session
from filament_manager.services import storage as storage_service


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


def _dashboard_push_status() -> dict:
    return {
        "wifi_signal": "-52dBm",
        "print": {
            "command": "push_status",
            "gcode_state": "RUNNING",
            "print_type": "local",
            "mc_percent": 25,
            "mc_remaining_time": 80,
            "gcode_file": "/Metadata/plate_2.gcode",
            "task_id": "dashboard-task-1",
            "mc_print_stage": "2",
            "mc_print_sub_stage": "13",
            "print_gcode_action": 13,
            "print_real_action": 1,
            "mc_print_error_code": "0",
            "layer_num": 12,
            "total_layer_num": 240,
            "bed_temper": "60",
            "bed_target_temper": "65",
            "nozzle_temper": "215",
            "nozzle_target_temper": "220",
            "chamber_temper": "32",
            "fan_gear": 5006848,
            "cooling_fan_speed": "8",
            "big_fan1_speed": "128",
            "heatbreak_fan_speed": "15",
            "wifi_signal": "-51dBm",
            "sdcard": "HAS_SDCARD_NORMAL",
            "spd_lvl": 2,
            "spd_mag": 100,
            "ams_status": 258,
            "lights_report": [{"node": "chamber_light", "mode": "on"}],
            "ipcam": {
                "agora_service": "disable",
                "brtc_service": "enable",
                "bs_state": 0,
                "cap_pic_enable": "enable",
                "ipcam_dev": "1",
                "ipcam_record": "enable",
                "liveview_preview": True,
                "resolution": "1080p",
                "rtsp_url": "disable",
                "timelapse": "disable",
            },
            "xcam": {
                "ipcam_record": "enable",
                "timelapse": "disable",
                "cfg": 224,
                "first_layer_inspector": True,
            },
            "hms": [{"attr": "0x05000300", "code": "0x8001"}],
            "vt_tray": {
                "id": "255",
                "tray_uuid": "99999999-8888-7777-6666-555555555555",
                "tray_type": "PETG",
                "tray_color": "112233",
            },
            "device": {
                "nozzle": {
                    "current_nozzle_id": "0",
                    "target_nozzle_id": "0",
                    "info": [
                        {
                            "id": "0",
                            "type": "hardened_steel",
                            "diameter": "0.4",
                            "wear": "normal",
                            "state": "ready",
                            "sn": "NOZZLE-SYNTH-1",
                        }
                    ],
                },
                "toolhead": {"state": "ready"},
                "bed": {"type": "textured_plate"},
                "ctc": {"state": "ok"},
                "airduct": {
                    "modeCur": 0,
                    "modeFunc": 1,
                    "parts": [
                        {"id": 16, "state": 100},
                        {"id": 32, "state": 0},
                    ],
                },
                "plate": {"id": "plate_2"},
                "cam": {"state": "ready"},
                "extruder": {
                    "info": [
                        {"id": 0, "temp": 215},
                    ]
                }
            },
            "ams": {
                "tray_now": "0",
                "ams_exist_bits": "1",
                "ams": [
                    {
                        "id": "0",
                        "humidity": "3",
                        "humidity_raw": "4",
                        "temp": "26.2",
                        "dry_status": "idle",
                        "dry_sub_status": "0",
                        "dry_sf_reason": [2, 9],
                        "dry_time": 0,
                        "module_type": "n3s",
                        "tray": [
                            {
                                "id": "0",
                                "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                "tag_uid": "ABCDEF0123456789",
                                "tray_type": "PLA",
                                "tray_sub_brands": "Basic",
                                "tray_color": "FF6600",
                                "remain": 88,
                                "tray_state": "idle",
                                "tray_id_name": "PLA Basic Orange",
                                "tray_info_idx": "GFA00",
                                "nozzle_temp_min": 190,
                                "nozzle_temp_max": 230,
                                "drying_temp": 55,
                                "drying_time": 8,
                                "cali_idx": 1,
                                "k": 0.02,
                                "state": 11,
                            }
                        ],
                    }
                ],
            },
        },
    }


def test_push_status_updates_device_dashboard_and_derived_ams_fields(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()

    _ingest(api_client, printer_id, payload)
    _ingest(api_client, printer_id, payload)

    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["temperatures"]["bed"] == 60.0
    assert snapshot["temperatures"]["nozzle_target"] == 220.0
    assert snapshot["fans"]["cooling_fan_speed"]["percent"] == 53
    assert snapshot["fans"]["fan_gear"]["raw"] == 5006848
    assert snapshot["fans"]["fan_gear"]["percent"] == 40
    assert snapshot["fans"]["fan_gear"]["packed_bytes"] == [102, 76]
    assert snapshot["network"]["wifi_signal"] == -51
    assert snapshot["lights"]["chamber_light"] is True
    assert snapshot["print_status"]["stage_name"] == "printing_or_preparing"
    assert snapshot["print_status"]["sub_stage_name"] == "heating"
    assert snapshot["print_status"]["user_state"] == "actual_printing"
    assert snapshot["print_status"]["current_plate_id"] == 2
    assert snapshot["derived_status"]["heating_bed"] is True
    assert snapshot["derived_status"]["heating_nozzle"] is True
    assert snapshot["derived_status"]["printing"] is True
    assert snapshot["derived_status"]["actual_printing"] is True
    assert snapshot["derived_status"]["user_state"] == "actual_printing"
    assert snapshot["derived_status"]["current_plate_id"] == 2
    assert snapshot["hardware"]["toolhead"]["state"] == "ready"
    assert snapshot["hardware"]["airduct"]["modeCur_name"] == "cooling_mode"
    assert snapshot["hardware"]["airduct"]["modeFunc_name"] == "chamber_temperature_hold"
    assert snapshot["hardware"]["airduct"]["parts"][0]["part_name"] == "toolhead_fan"
    assert snapshot["nozzles"]["current_nozzle_id"] == "0"
    assert snapshot["nozzles"]["items"][0]["serial_number"] == "NOZZLE-SYNTH-1"
    assert snapshot["camera_options"]["printing_monitor"] is True
    assert snapshot["camera_options"]["buildplate_marker_detector"] is True
    assert snapshot["camera_options"]["allow_skip_parts"] is True
    assert "ipcam" not in snapshot["camera"]
    assert "ipcam" not in snapshot["camera_options"]
    assert snapshot["camera"]["resolution"] == "1080p"
    assert snapshot["camera"]["brtc_service"] == "enable"
    assert snapshot["camera"]["liveview_preview"] is True
    assert snapshot["ams_status"]["ams_status_main"] == 1
    assert snapshot["ams_status"]["ams_status_sub"] == 2
    assert snapshot["ams_status"]["ams_status_main_name"] == "busy"
    assert snapshot["ams_status"]["ams_status_sub_name"] == "rfid_identifying"
    assert snapshot["hms_errors"][0]["module"] == 5
    assert snapshot["hms_errors"][0]["short_code"] == "0500_8001"
    assert snapshot["hms_errors"][0]["severity_name"] == "error"
    assert snapshot["hms_errors"][0]["active"] is True
    assert snapshot["external_slots"][0]["normalized_id"] == "254"
    assert snapshot["data_coverage"]["push_status"]["received"] is True
    assert snapshot["data_coverage"]["camera"]["received"] is True

    units = api_client.get(f"/api/printers/{printer_id}/ams/units").json()
    assert units[0]["humidity_raw"] == "4"
    assert units[0]["dry_status"] == "idle"
    assert units[0]["ams_type_name"] == "AMS HT"
    assert units[0]["dry_status_name"] == "idle"
    assert units[0]["dry_sub_status_name"] == "none"
    assert "temperature_not_reached" in units[0]["dry_sf_reason_names"]

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["tray_id_name"] == "PLA Basic Orange"
    assert slots[0]["nozzle_temp_max"] == 230
    assert slots[0]["state_code"] == 11
    assert slots[0]["state_name"] == "loaded"
    assert slots[0]["user_tray_id"] == 1
    assert slots[0]["slot_label"] == "Slot 1"

    dashboard = api_client.get(f"/api/printers/{printer_id}/dashboard")
    assert dashboard.status_code == 200
    assert printer_payload["access_code"] not in dashboard.text
    assert dashboard.json()["device_snapshot"]["temperatures"]["bed"] == 60.0

    events = api_client.get("/api/debug/events").json()
    hms_events = [item for item in events if item["event_type"] == "hms.error"]
    assert len(hms_events) == 1

    metrics = api_client.get(f"/api/printers/{printer_id}/metrics").json()
    metric_names = {item["metric"] for item in metrics}
    assert "temperature.bed" in metric_names
    assert "fan.cooling_fan_speed.percent" in metric_names
    assert "fan.fan_gear.percent" in metric_names
    assert "network.wifi_signal" in metric_names
    assert "ams.0.temperature" in metric_names


def test_running_before_first_layer_is_user_visible_preparing(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()
    payload["print"]["layer_num"] = 0
    payload["print"]["mc_percent"] = 15
    payload["print"]["stg_cur"] = 1
    payload["print"].pop("mc_print_sub_stage", None)

    _ingest(api_client, printer_id, payload)

    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["print_status"]["stg_cur_name"] == "auto_bed_leveling"
    assert snapshot["print_status"]["user_state"] == "preparing"
    assert snapshot["derived_status"]["preparing"] is True
    assert snapshot["derived_status"]["actual_printing"] is False
    assert snapshot["derived_status"]["user_state"] == "preparing"


def test_ams_overview_groups_multiple_units_and_orphan_slots(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()
    payload["print"]["ams"]["ams"] = [
        {
            "id": "0",
            "humidity": "2",
            "humidity_raw": "20",
            "temp": "25",
            "module_type": "n3f",
            "sw_ver": "01.00.00.00",
            "sn": "AMS2PRO123456",
            "tray": [
                {
                    "id": "0",
                    "tray_uuid": "11111111-2222-3333-4444-555555555555",
                    "tray_type": "PLA",
                    "tray_color": "FF6600",
                    "remain": 90,
                    "state": 11,
                }
            ],
        },
        {
            "id": "1",
            "humidity": "1",
            "humidity_raw": "10",
            "temp": "31",
            "module_type": "n3s",
            "dry_status": "drying",
            "tray": [
                {
                    "id": "0",
                    "tray_uuid": "22222222-3333-4444-5555-666666666666",
                    "tray_type": "ABS",
                    "tray_color": "222222",
                    "remain": -1,
                    "state": 17,
                }
            ],
        },
    ]
    _ingest(api_client, printer_id, payload)

    assert db_session.SessionLocal is not None
    with db_session.SessionLocal() as db:
        db.add(
            AmsSlot(
                printer_id=printer_id,
                ams_id="9",
                tray_id="3",
                slot_state="idle",
                material="PETG",
                series=None,
                color="336699",
                remain=40,
                tray_uuid=None,
                tag_uid=None,
                identity_key=None,
                identity_source="manual_required",
                identity_confidence=0.0,
                identity_warning=None,
                is_transitioning=False,
                raw={"state": 11},
            )
        )
        db.commit()

    overview = api_client.get(f"/api/printers/{printer_id}/ams/overview")
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["summary"]["ams_count"] == 3
    assert body["summary"]["slot_count"] == 3
    assert body["summary"]["loaded_count"] == 2
    assert body["summary"]["transitioning_count"] == 1
    units = {item["ams_id"]: item for item in body["units"]}
    assert units["0"]["ams_type_name"] == "AMS 2 Pro"
    assert units["1"]["ams_type_name"] == "AMS HT"
    assert units["0"]["slots"][0]["user_tray_id"] == 1
    assert units["0"]["slots"][0]["slot_label"] == "Slot 1"
    assert units["unknown"]["ams_type_name"] == "unknown"
    assert units["unknown"]["slots"][0]["ams_id"] == "9"


def test_hms_code_knowledge_unknown_and_non_actionable(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)

    codes = api_client.get("/api/hms/codes").json()
    assert any(item["short_code"] == "0500_8001" for item in codes)
    assert api_client.get("/api/hms/codes/0500_8001").json()["actionable"] is True

    unknown = _dashboard_push_status()
    unknown["print"]["hms"] = [{"attr": "0x05000300", "code": "0x8123"}]
    _ingest(api_client, printer_id, unknown)
    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["hms_errors"][0]["known"] is False
    assert "未知 HMS 码" in snapshot["hms_errors"][0]["message"]

    non_actionable = _dashboard_push_status()
    non_actionable["print"]["hms"] = [{"attr": "0x00000300", "code": "0x4000"}]
    _ingest(api_client, printer_id, non_actionable)
    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    active = [item for item in snapshot["hms_errors"] if item["active"] is True]
    assert active[0]["actionable"] is False
    assert snapshot["derived_status"]["has_error"] is False


def test_events_metrics_history_and_storage_summary(api_client, printer_payload, monkeypatch) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()
    _ingest(api_client, printer_id, payload)
    _ingest(api_client, printer_id, payload)

    events = api_client.get(f"/api/events?printer_id={printer_id}&severity=warning&limit=5").json()
    assert len(events) <= 5
    assert all(item["printer_id"] == printer_id for item in events)
    assert all(item["severity"] == "warning" for item in events)

    history = api_client.get(f"/api/printers/{printer_id}/ams/history?ams_id=0&tray_id=0").json()
    assert len(history) == 1
    assert history[0]["state_name"] == "loaded"
    assert history[0]["material"] == "PLA"

    metrics = api_client.get(f"/api/printers/{printer_id}/metrics?bucket=hour&group=temperature").json()
    assert metrics
    assert all(item["metric"].startswith("temperature.") for item in metrics)
    assert all(item["details"]["bucket"] == "hour" for item in metrics)

    def fake_list_storage_files(_printer, _directories):
        return [
            {"path": "/model/demo.3mf", "name": "demo.3mf", "size": 100, "modified_at": None, "type": "model", "raw": {}},
            {"path": "/cache/demo.gcode", "name": "demo.gcode", "size": 200, "modified_at": None, "type": "gcode", "raw": {}},
            {"path": "/record/clip.mp4", "name": "clip.mp4", "size": 300, "modified_at": None, "type": "recording", "raw": {}},
        ]

    monkeypatch.setattr(storage_service, "_list_storage_files", fake_list_storage_files)
    scan = api_client.post(f"/api/printers/{printer_id}/storage/scan").json()
    assert scan["new_count"] == 3
    summary = api_client.get(f"/api/printers/{printer_id}/storage/summary").json()
    assert summary["by_type"]["model"] == 1
    assert summary["by_type"]["gcode"] == 1
    assert summary["by_type"]["recording"] == 1


def test_hms_error_becomes_inactive_when_absent_from_next_hms_frame(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()
    _ingest(api_client, printer_id, payload)

    cleared = _dashboard_push_status()
    cleared["print"]["hms"] = []
    _ingest(api_client, printer_id, cleared)

    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["hms_errors"][0]["active"] is False


def test_hms_status_code_with_low_error_bits_is_ignored(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()
    payload["print"]["hms"] = [{"attr": "0x05000300", "code": "0x20070"}]

    _ingest(api_client, printer_id, payload)

    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["hms_errors"] == []

    events = api_client.get("/api/debug/events").json()
    assert [item for item in events if item["event_type"] == "hms.error"] == []


def test_metric_samples_deduplicate_repeated_short_interval_values(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = _dashboard_push_status()

    _ingest(api_client, printer_id, payload)
    _ingest(api_client, printer_id, payload)

    metrics = api_client.get(f"/api/printers/{printer_id}/metrics?metric=temperature.bed").json()
    assert len(metrics) == 1


def test_storage_scan_api_upserts_read_only_file_records(api_client, printer_payload, monkeypatch) -> None:
    printer_id = _create_printer(api_client, printer_payload)

    def fake_list_storage_files(_printer, _directories):
        return [
            {
                "path": "/timelapse/demo.mp4",
                "name": "demo.mp4",
                "size": 1024,
                "modified_at": None,
                "type": "timelapse",
                "raw": {"perm": "read"},
            }
        ]

    monkeypatch.setattr(storage_service, "_list_storage_files", fake_list_storage_files)

    scan = api_client.post(f"/api/printers/{printer_id}/storage/scan")
    assert scan.status_code == 200, scan.text
    assert scan.json()["success"] is True
    assert scan.json()["scanned_count"] == 1

    files = api_client.get(f"/api/printers/{printer_id}/storage/files").json()
    assert files[0]["path"] == "/timelapse/demo.mp4"
    assert files[0]["type"] == "timelapse"


def test_camera_response_sanitizer_removes_stale_raw_objects() -> None:
    sanitized = _sanitize_camera_response(
        {
            "ipcam": {"resolution": "1080p"},
            "xcam": {"cfg": 224},
            "resolution": "1080p",
            "ipcam_record": "enable",
        }
    )

    assert "ipcam" not in sanitized
    assert "xcam" not in sanitized
    assert sanitized["resolution"] == "1080p"
    assert sanitized["ipcam_record"] == "enable"


def test_get_version_and_accessories_update_device_snapshot(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    _ingest(api_client, printer_id, _dashboard_push_status())

    _ingest(
        api_client,
        printer_id,
        {
            "info": {
                "command": "get_version",
                "sequence_id": "version-1",
                "module": [
                    {"name": "ota", "sw_ver": "01.02.03.04"},
                    {"name": "ams/0", "sw_ver": "00.00.06.96", "sn": "AMS-SYNTH-0001"},
                ],
            }
        },
    )
    _ingest(
        api_client,
        printer_id,
        {
            "system": {
                "command": "get_accessories",
                "sequence_id": "accessories-1",
                "accessory_type": "none",
                "nozzle": {"type": "hardened_steel", "diameter": "0.4"},
            }
        },
    )

    snapshot = api_client.get(f"/api/printers/{printer_id}/device-snapshot").json()
    assert snapshot["firmware"]["printer_version"] == "01.02.03.04"
    assert snapshot["firmware"]["ams_modules"]["0"]["sn"] == "AMS-SYNTH-0001"
    assert snapshot["accessories"]["payload"]["nozzle"]["type"] == "hardened_steel"

    units = api_client.get(f"/api/printers/{printer_id}/ams/units").json()
    assert units[0]["sw_ver"] == "00.00.06.96"
    assert units[0]["serial_number"] == "AMS-SYNTH-0001"


def test_refresh_full_requires_connected_printer(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)

    response = api_client.post(f"/api/printers/{printer_id}/refresh-full")

    assert response.status_code == 409
