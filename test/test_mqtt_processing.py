from __future__ import annotations

import copy
import json

def _create_printer(api_client, printer_payload) -> int:
    response = api_client.post("/api/printers", json=printer_payload)
    assert response.status_code == 201
    return response.json()["id"]


def _ingest(api_client, printer_id: int, payload: dict) -> None:
    response = api_client.post(
        f"/api/printers/{printer_id}/mqtt/payload",
        json={"topic": f"device/SYNTHETIC123/report", "payload": payload},
    )
    assert response.status_code == 200, response.text


def test_valid_tray_uuid_discovers_spool_and_slot(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())

    _ingest(api_client, printer_id, payload)

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["identity_source"] == "tray_uuid"
    assert slots[0]["identity_key"] == "bambu:tray_uuid:11111111-2222-3333-4444-555555555555"
    assert slots[0]["filament_spool_id"] is not None

    spools = api_client.get("/api/filament/spools").json()
    assert spools[0]["identity_source"] == "ams_official_id"
    assert spools[0]["official_spool_uid"] == "11111111-2222-3333-4444-555555555555"
    assert spools[0]["current_ams_id"] == "0"
    assert spools[0]["current_tray_id"] == "0"


def test_tag_uid_fallback_generates_warning(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_tag_uid_fallback.json").read_text())

    _ingest(api_client, printer_id, payload)

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["identity_source"] == "tag_uid"
    assert slots[0]["identity_key"] == "bambu:tag_uid:TAGUID1234567890"

    events = api_client.get("/api/debug/events").json()
    assert any(item["event_type"] == "slot.identity_fallback" for item in events)


def test_unidentified_slot_requires_manual_binding(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_unidentified.json").read_text())

    _ingest(api_client, printer_id, payload)

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["identity_source"] == "manual_required"
    assert slots[0]["identity_key"] is None
    assert slots[0]["filament_spool_id"] is not None
    assert any(item["event_type"] == "spool.unidentified" for item in api_client.get("/api/debug/events").json())


def test_remain_minus_one_with_rfid_payload_attaches_spool(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_remain_unavailable.json").read_text())

    _ingest(api_client, printer_id, payload)

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["remain"] == -1
    assert slots[0]["is_transitioning"] is False
    assert slots[0]["filament_spool_id"] is not None

    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["id"] == slots[0]["filament_spool_id"]
    assert spools[0]["official_spool_uid"] == "C27BF5A592BD43898492BD61E354E427"
    assert spools[0]["current_ams_id"] == "128"
    assert spools[0]["current_tray_id"] == "0"
    assert spools[0]["last_ams_remain_percent"] is None
    assert spools[0]["config"]["ams_raw"]["remain"] == -1
    assert spools[0]["config"]["needs_sku_review"] is True
    assert any(item["event_type"] == "filament.spool.pending_confirmation" for item in api_client.get("/api/debug/events").json())


def test_state_machine_deduplicates_repeated_push_status(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())

    _ingest(api_client, printer_id, payload)
    _ingest(api_client, printer_id, payload)

    events = api_client.get("/api/debug/events").json()
    started = [item for item in events if item["event_type"] == "print.started"]
    assert len(started) == 1


def test_stop_success_then_failed_is_cancelled(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    running = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    failed = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    failed["print"]["gcode_state"] = "FAILED"

    _ingest(api_client, printer_id, running)
    _ingest(
        api_client,
        printer_id,
        {
            "print": {
                "command": "stop",
                "sequence_id": "synthetic-stop-1",
                "result": "SUCCESS",
                "reason": "SUCCESS"
            }
        },
    )
    _ingest(api_client, printer_id, failed)

    events = api_client.get("/api/debug/events").json()
    assert any(item["event_type"] == "print.cancelled" for item in events)
    assert not any(item["event_type"] == "print.failed" for item in events)


def test_ledctrl_unknown_led_node_is_not_error(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)

    _ingest(
        api_client,
        printer_id,
        {
            "print": {
                "command": "ledctrl",
                "sequence_id": "synthetic-led-1",
                "result": "fail",
                "led_node": "chamber_light2",
                "led_mode": "on",
                "reason": "did not find the valid led: chamber_light2",
            }
        },
    )

    events = api_client.get("/api/debug/events").json()
    led_events = [item for item in events if item["event_type"] == "printer.command.ledctrl"]
    assert len(led_events) == 1
    assert led_events[0]["severity"] == "info"
    assert led_events[0]["data"]["led_node"] == "chamber_light2"


def test_access_code_is_masked_in_api_responses(api_client, printer_payload) -> None:
    printer_id = _create_printer(api_client, printer_payload)

    response = api_client.get(f"/api/printers/{printer_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["access_code"] != printer_payload["access_code"]
    assert body["access_code"].startswith("****")
    assert printer_payload["access_code"] not in response.text

    update = api_client.patch(f"/api/printers/{printer_id}", json={"access_code": "new-access-1234"})
    assert update.status_code == 200, update.text
    assert update.json()["access_code"] == "****1234"
    assert "new-access-1234" not in update.text

    unchanged = api_client.patch(f"/api/printers/{printer_id}", json={"access_code": ""})
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["access_code"] == "****1234"

    masked = api_client.patch(f"/api/printers/{printer_id}", json={"access_code": "****9999"})
    assert masked.status_code == 200, masked.text
    assert masked.json()["access_code"] == "****1234"

    revealed = api_client.get(f"/api/printers/{printer_id}/access-code")
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["access_code"] == "new-access-1234"


def test_mqtt_ingestion_keeps_two_printers_isolated(api_client, printer_payload, fixture_dir) -> None:
    first_printer_id = _create_printer(api_client, {**printer_payload, "name": "First", "serial": "SERIAL-ONE"})
    second_printer_id = _create_printer(
        api_client,
        {**printer_payload, "name": "Second", "host": "printer-2.local", "serial": "SERIAL-TWO"},
    )
    first_payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    second_payload = copy.deepcopy(first_payload)
    second_payload["print"]["task_id"] = "synthetic-task-2"
    second_payload["print"]["gcode_file"] = "second-printer.gcode.3mf"
    second_payload["print"]["mc_percent"] = 67
    second_tray = second_payload["print"]["ams"]["ams"][0]["tray"][0]
    second_tray["id"] = "2"
    second_tray["tray_uuid"] = "22222222-3333-4444-5555-666666666666"
    second_tray["tag_uid"] = "SECOND012345678"
    second_tray["tray_color"] = "00AAFF"

    _ingest(api_client, first_printer_id, first_payload)
    _ingest(api_client, second_printer_id, second_payload)

    first_state = api_client.get(f"/api/printers/{first_printer_id}/state").json()
    second_state = api_client.get(f"/api/printers/{second_printer_id}/state").json()
    assert first_state["task_id"] == "synthetic-task-1"
    assert second_state["task_id"] == "synthetic-task-2"
    assert second_state["mc_percent"] == 67

    first_dashboard = api_client.get(f"/api/printers/{first_printer_id}/dashboard").json()
    second_dashboard = api_client.get(f"/api/printers/{second_printer_id}/dashboard").json()
    assert first_dashboard["state"]["task_id"] == "synthetic-task-1"
    assert second_dashboard["state"]["gcode_file"] == "second-printer.gcode.3mf"

    first_slots = api_client.get(f"/api/printers/{first_printer_id}/ams/slots").json()
    second_slots = api_client.get(f"/api/printers/{second_printer_id}/ams/slots").json()
    assert first_slots[0]["printer_id"] == first_printer_id
    assert first_slots[0]["tray_id"] == "0"
    assert first_slots[0]["identity_key"] == "bambu:tray_uuid:11111111-2222-3333-4444-555555555555"
    assert second_slots[0]["printer_id"] == second_printer_id
    assert second_slots[0]["tray_id"] == "2"
    assert second_slots[0]["identity_key"] == "bambu:tray_uuid:22222222-3333-4444-5555-666666666666"

    raw_messages = api_client.get("/api/debug/raw-mqtt?limit=10").json()
    assert {item["printer_id"] for item in raw_messages[:2]} == {first_printer_id, second_printer_id}
