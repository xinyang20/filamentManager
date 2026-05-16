from __future__ import annotations

import ssl
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from filament_manager.mqtt import client as mqtt_client_module
from filament_manager.mqtt.client import (
    MqttConnectionManager,
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


def test_printer_mqtt_clients_use_independent_topics_and_client_ids(monkeypatch) -> None:
    created_clients: list[FakePahoClient] = []

    class FakePahoClient:
        def __init__(self, *args, client_id: str, **kwargs) -> None:
            self.client_id = client_id
            created_clients.append(self)

        def username_pw_set(self, *args, **kwargs) -> None:
            pass

        def reconnect_delay_set(self, *args, **kwargs) -> None:
            pass

        def tls_set_context(self, *args, **kwargs) -> None:
            pass

    monkeypatch.setattr(mqtt_client_module.mqtt, "Client", FakePahoClient)

    first = SimpleNamespace(
        id=1,
        host="192.0.2.10",
        port=8883,
        serial="SERIAL-A",
        access_code="secret-access-code",
        tls_enabled=True,
        certificate_verify=False,
    )
    second = SimpleNamespace(
        id=2,
        host="192.0.2.11",
        port=8883,
        serial="SERIAL-B",
        access_code="secret-access-code",
        tls_enabled=True,
        certificate_verify=False,
    )

    first_client = PrinterMqttClient(first)
    second_client = PrinterMqttClient(second)

    assert first_client.report_topic == "device/SERIAL-A/report"
    assert first_client.request_topic == "device/SERIAL-A/request"
    assert second_client.report_topic == "device/SERIAL-B/report"
    assert second_client.request_topic == "device/SERIAL-B/request"
    assert created_clients[0].client_id != created_clients[1].client_id


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


def test_mqtt_connect_success_signals_before_status_write(monkeypatch) -> None:
    class FakePahoClient:
        def __init__(self, *args, **kwargs) -> None:
            self.subscriptions: list[str] = []
            self.published: list[tuple[str, str, int]] = []

        def username_pw_set(self, *args, **kwargs) -> None:
            pass

        def reconnect_delay_set(self, *args, **kwargs) -> None:
            pass

        def tls_set_context(self, *args, **kwargs) -> None:
            pass

        def subscribe(self, topic: str) -> None:
            self.subscriptions.append(topic)

        def publish(self, topic: str, payload: str, qos: int) -> None:
            self.published.append((topic, payload, qos))

    monkeypatch.setattr(mqtt_client_module.mqtt, "Client", FakePahoClient)
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
    status_write_seen: dict[str, bool] = {}

    def fake_update_connection(_status: str, _error: str | None) -> None:
        status_write_seen["connect_event_set"] = client._connect_event.is_set()

    monkeypatch.setattr(client, "_update_printer_connection", fake_update_connection)

    client._on_connect(client.client, None, None, 0, None)

    assert status_write_seen == {"connect_event_set": True}
    assert client._connect_event.is_set() is True
    assert client.client.subscriptions == [client.report_topic]
    assert [item[0] for item in client.client.published] == [client.request_topic, client.request_topic]


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


def test_connection_manager_keeps_printer_clients_isolated(api_client, printer_payload, monkeypatch) -> None:
    instances: list[FakePrinterMqttClient] = []

    class FakePrinterMqttClient:
        def __init__(self, printer: Printer) -> None:
            self.printer_id = printer.id
            self.serial = printer.serial
            self.report_topic = f"device/{printer.serial}/report"
            self.request_topic = f"device/{printer.serial}/request"
            self.connected = False
            self.disconnect_count = 0
            instances.append(self)

        def connect(self) -> None:
            self.connected = True

        def disconnect(self) -> None:
            self.connected = False
            self.disconnect_count += 1

        def is_connected(self) -> bool:
            return self.connected

        def request_pushall(self) -> str:
            return f"push-{self.printer_id}"

        def request_full_refresh(self) -> dict[str, str]:
            return {"pushall": f"push-{self.printer_id}"}

    monkeypatch.setattr(mqtt_client_module, "PrinterMqttClient", FakePrinterMqttClient)
    manager = MqttConnectionManager()
    first = api_client.post("/api/printers", json={**printer_payload, "serial": "SERIAL-A"}).json()
    second = api_client.post(
        "/api/printers",
        json={**printer_payload, "name": "Second", "host": "printer-2.local", "serial": "SERIAL-B"},
    ).json()

    assert db_session.SessionLocal is not None
    with db_session.SessionLocal() as db:
        first_printer = db.get(Printer, first["id"])
        second_printer = db.get(Printer, second["id"])
        assert first_printer is not None
        assert second_printer is not None
        manager.connect(db, first_printer)
        manager.connect(db, second_printer)

    assert manager.is_connected(first["id"]) is True
    assert manager.is_connected(second["id"]) is True
    assert instances[0].report_topic == "device/SERIAL-A/report"
    assert instances[1].request_topic == "device/SERIAL-B/request"

    manager.disconnect(first["id"])

    assert instances[0].disconnect_count == 1
    assert manager.is_connected(first["id"]) is False
    assert manager.is_connected(second["id"]) is True


def test_connection_manager_retries_sqlite_lock_when_marking_connecting(monkeypatch) -> None:
    instances: list[FakePrinterMqttClient] = []

    class FakeDb:
        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0

        def add(self, _value) -> None:
            pass

        def commit(self) -> None:
            self.commits += 1
            if self.commits == 1:
                raise OperationalError("UPDATE printers", {}, Exception("database is locked"))

        def rollback(self) -> None:
            self.rollbacks += 1

    class FakePrinterMqttClient:
        def __init__(self, printer) -> None:
            self.printer_id = printer.id
            self.connected = False
            instances.append(self)

        def connect(self) -> None:
            self.connected = True

        def disconnect(self) -> None:
            self.connected = False

        def is_connected(self) -> bool:
            return self.connected

    monkeypatch.setattr(mqtt_client_module, "PrinterMqttClient", FakePrinterMqttClient)
    monkeypatch.setattr(mqtt_client_module.time, "sleep", lambda _seconds: None)
    manager = MqttConnectionManager()
    db = FakeDb()
    printer = SimpleNamespace(id=1, port=8883, tls_enabled=True, connection_status="disconnected", last_error="old")

    manager.connect(db, printer)

    assert db.commits == 2
    assert db.rollbacks == 1
    assert printer.connection_status == "connecting"
    assert printer.last_error is None
    assert instances[0].connected is True
    assert manager.is_connected(1) is True


def test_updating_connected_printer_connection_settings_marks_reconnect_required(
    api_client,
    printer_payload,
    monkeypatch,
) -> None:
    calls: list[int] = []
    printer = api_client.post("/api/printers", json=printer_payload).json()
    second = api_client.post(
        "/api/printers",
        json={**printer_payload, "name": "Second", "host": "printer-2.local", "serial": "SYNTHETIC456"},
    ).json()

    def fake_is_connected(printer_id: int) -> bool:
        return printer_id == printer["id"]

    def fake_disconnect(printer_id: int) -> None:
        calls.append(printer_id)

    monkeypatch.setattr(routes.mqtt_manager, "is_connected", fake_is_connected)
    monkeypatch.setattr(routes.mqtt_manager, "disconnect", fake_disconnect)

    response = api_client.patch(f"/api/printers/{printer['id']}", json={"host": "printer-new.local"})
    second_response = api_client.patch(f"/api/printers/{second['id']}", json={"name": "Second renamed"})

    assert response.status_code == 200
    assert response.json()["connection_status"] == "disconnected"
    assert "reconnect required" in response.json()["last_error"]
    assert second_response.status_code == 200
    assert calls == [printer["id"]]
