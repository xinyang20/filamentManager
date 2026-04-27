from __future__ import annotations

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
    assert slots[0]["spool_id"] is not None

    spools = api_client.get("/api/spools").json()
    assert spools[0]["identity_source"] == "tray_uuid"
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
    assert slots[0]["spool_id"] is None
    assert any(item["event_type"] == "spool.unidentified" for item in api_client.get("/api/debug/events").json())


def test_remain_minus_one_does_not_attach_or_move_spool(api_client, printer_payload, fixture_dir) -> None:
    printer_id = _create_printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_remain_unavailable.json").read_text())

    _ingest(api_client, printer_id, payload)

    slots = api_client.get(f"/api/printers/{printer_id}/ams/slots").json()
    assert slots[0]["remain"] == -1
    assert slots[0]["is_transitioning"] is True
    assert slots[0]["spool_id"] is None

    spools = api_client.get("/api/spools").json()
    assert spools[0]["current_ams_id"] is None
    assert spools[0]["current_tray_id"] is None


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
