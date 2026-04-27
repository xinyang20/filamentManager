from __future__ import annotations

import json


def test_manual_spool_can_bind_unidentified_slot(api_client, printer_payload, fixture_dir) -> None:
    printer = api_client.post("/api/printers", json=printer_payload).json()
    payload = json.loads((fixture_dir / "push_status_unidentified.json").read_text())
    ingest = api_client.post(
        f"/api/printers/{printer['id']}/mqtt/payload",
        json={"topic": "device/SYNTHETIC123/report", "payload": payload},
    )
    assert ingest.status_code == 200
    slot = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()[0]

    spool_response = api_client.post(
        "/api/spools",
        json={
            "display_name": "Manual TPU",
            "material": "TPU",
            "color": "222222",
            "sealed_quantity": 1,
            "status": "sealed",
        },
    )
    assert spool_response.status_code == 201
    spool = spool_response.json()

    bind = api_client.post(f"/api/ams/slots/{slot['id']}/bind", json={"spool_id": spool["id"]})
    assert bind.status_code == 200
    bound_slot = bind.json()
    assert bound_slot["spool_id"] == spool["id"]

    updated_spool = api_client.get("/api/spools").json()[0]
    assert updated_spool["status"] == "active"
    assert updated_spool["sealed_quantity"] == 0
    assert updated_spool["current_ams_id"] == "1"
    assert updated_spool["current_tray_id"] == "2"
