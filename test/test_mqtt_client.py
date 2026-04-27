from __future__ import annotations

import ssl
from types import SimpleNamespace

import pytest

from filament_manager.mqtt import client as mqtt_client_module
from filament_manager.mqtt.client import (
    PrinterMqttClient,
    build_get_accessories_request,
    build_get_version_request,
    build_pushall_request,
)
from filament_manager.api import routes
from filament_manager.db import session as db_session
from filament_manager.db.models import Printer


def test_connect_rejects_plaintext_on_bambu_tls_port(api_client, printer_payload) -> None:
    payload = {**printer_payload, "tls_enabled": False}
    printer = api_client.post("/api/printers", json=payload).json()

    response = api_client.post(f"/api/printers/{printer['id']}/connect")

    assert response.status_code == 400
    assert "requires TLS" in response.json()["detail"]
    stored = api_client.get(f"/api/printers/{printer['id']}").json()
    assert stored["connection_status"] == "error"
    assert "requires TLS" in stored["last_error"]


def test_read_refresh_request_payloads_are_read_only() -> None:
    pushall = build_pushall_request()
    version = build_get_version_request()
    accessories = build_get_accessories_request()

    assert pushall.payload["pushing"]["command"] == "pushall"
    assert version.payload["info"]["command"] == "get_version"
    assert accessories.payload["system"]["command"] == "get_accessories"
    assert accessories.payload["system"]["accessory_type"] == "none"


def test_mqtt_connect_timeout_raises_and_disconnects(monkeypatch) -> None:
    fake_instances: list[FakePahoClient] = []

    class FakePahoClient:
        def __init__(self, *args, **kwargs) -> None:
            self.disconnected = False
            self.loop_stopped = False
            fake_instances.append(self)

        def username_pw_set(self, *args, **kwargs) -> None:
            pass

        def reconnect_delay_set(self, *args, **kwargs) -> None:
            pass

        def tls_set_context(self, *args, **kwargs) -> None:
            pass

        def connect(self, *args, **kwargs) -> None:
            pass

        def loop_start(self) -> None:
            pass

        def disconnect(self) -> None:
            self.disconnected = True

        def loop_stop(self) -> None:
            self.loop_stopped = True

    monkeypatch.setattr(mqtt_client_module.mqtt, "Client", FakePahoClient)
    monkeypatch.setattr(mqtt_client_module.db_session, "SessionLocal", None)

    printer = SimpleNamespace(
        id=1,
        host="192.0.2.10",
        port=8883,
        serial="SYNTHETIC-SERIAL",
        access_code="secret-access-code",
        tls_enabled=True,
        certificate_verify=False,
    )
    client = PrinterMqttClient(printer)

    with pytest.raises(ConnectionError, match="Timed out waiting for MQTT connection handshake"):
        client.connect(wait_seconds=0.01)

    assert fake_instances[0].disconnected is True
    assert fake_instances[0].loop_stopped is True


def test_certificate_verify_failure_returns_actionable_400(api_client, printer_payload, monkeypatch) -> None:
    class FakePahoClient:
        def __init__(self, *args, **kwargs) -> None:
            self.on_connect = None
            self.on_disconnect = None
            self.on_message = None

        def username_pw_set(self, *args, **kwargs) -> None:
            pass

        def reconnect_delay_set(self, *args, **kwargs) -> None:
            pass

        def tls_set_context(self, *args, **kwargs) -> None:
            pass

        def connect(self, *args, **kwargs) -> None:
            raise ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer certificate")

        def loop_start(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        def loop_stop(self) -> None:
            pass

    monkeypatch.setattr(mqtt_client_module.mqtt, "Client", FakePahoClient)
    printer = api_client.post("/api/printers", json={**printer_payload, "certificate_verify": True}).json()

    response = api_client.post(f"/api/printers/{printer['id']}/connect")

    assert response.status_code == 400
    assert "disable certificate verification" in response.json()["detail"]
    stored = api_client.get(f"/api/printers/{printer['id']}").json()
    assert stored["connection_status"] == "error"
    assert "disable certificate verification" in stored["last_error"]


def test_printer_list_reconciles_stale_connected_status(api_client, printer_payload) -> None:
    printer = api_client.post("/api/printers", json=printer_payload).json()

    assert db_session.SessionLocal is not None
    with db_session.SessionLocal() as db:
        stored = db.get(Printer, printer["id"])
        assert stored is not None
        stored.connection_status = "connected"
        stored.last_error = None
        db.add(stored)
        db.commit()

    mqtt_client_module.mqtt_manager.disconnect(printer["id"])
    body = api_client.get("/api/printers").json()
    refreshed = next(item for item in body if item["id"] == printer["id"])

    assert refreshed["connection_status"] == "disconnected"
    assert "reconnect required" in refreshed["last_error"]


def test_full_refresh_reconnects_stale_runtime_session(api_client, printer_payload, monkeypatch) -> None:
    printer = api_client.post("/api/printers", json=printer_payload).json()
    calls = {"connect": 0, "request": 0}

    assert db_session.SessionLocal is not None
    with db_session.SessionLocal() as db:
        stored = db.get(Printer, printer["id"])
        assert stored is not None
        stored.connection_status = "connected"
        stored.last_error = None
        db.add(stored)
        db.commit()

    def fake_request_full_refresh(printer_id: int):
        calls["request"] += 1
        if calls["connect"] == 0:
            return None
        return {"pushall": "push", "get_version": "version", "get_accessories": "accessories"}

    def fake_connect(db, stored_printer):
        calls["connect"] += 1
        stored_printer.connection_status = "connected"
        stored_printer.last_error = None
        db.add(stored_printer)
        db.commit()

    monkeypatch.setattr(routes.mqtt_manager, "request_full_refresh", fake_request_full_refresh)
    monkeypatch.setattr(routes.mqtt_manager, "connect", fake_connect)

    response = api_client.post(f"/api/printers/{printer['id']}/refresh-full")

    assert response.status_code == 200
    assert response.json()["pushall"] == "push"
    assert calls == {"connect": 1, "request": 2}
