from __future__ import annotations

import json
import logging
import os
import ssl
import threading
import uuid
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from filament_manager.core.config import get_settings
from filament_manager.db.models import Printer, PrinterEvent, utc_now
from filament_manager.db import session as db_session
from filament_manager.services.mqtt_processing import process_mqtt_payload
from filament_manager.services.notifications import dispatch_event_notifications

LOGGER = logging.getLogger(__name__)
MQTT_USERNAME = "bblp"
CERTIFICATE_VERIFY_HINT = (
    "MQTT TLS certificate verification failed. Bambu LAN printers usually use a local/self-signed "
    "certificate; disable certificate verification for this printer while keeping TLS enabled."
)


@dataclass(frozen=True)
class MqttRequest:
    sequence_id: str
    payload: dict[str, Any]


PushAllRequest = MqttRequest


def build_pushall_request() -> MqttRequest:
    sequence_id = uuid.uuid4().hex
    return MqttRequest(
        sequence_id=sequence_id,
        payload={"pushing": {"sequence_id": sequence_id, "command": "pushall"}},
    )


def build_get_version_request() -> MqttRequest:
    sequence_id = uuid.uuid4().hex
    return MqttRequest(
        sequence_id=sequence_id,
        payload={"info": {"sequence_id": sequence_id, "command": "get_version"}},
    )


def build_get_accessories_request() -> MqttRequest:
    sequence_id = uuid.uuid4().hex
    return MqttRequest(
        sequence_id=sequence_id,
        payload={
            "system": {
                "sequence_id": sequence_id,
                "command": "get_accessories",
                "accessory_type": "none",
            }
        },
    )


class PrinterMqttClient:
    _client_instance_counter = 0

    def __init__(self, printer: Printer) -> None:
        self.printer_id = printer.id
        self.host = printer.host
        self.port = printer.port
        self.serial = printer.serial
        self.access_code = printer.access_code
        self.tls_enabled = printer.tls_enabled
        self.certificate_verify = printer.certificate_verify
        self.keepalive = get_settings().mqtt_keepalive_seconds
        self.report_topic = f"device/{self.serial}/report"
        self.request_topic = f"device/{self.serial}/request"
        self._connect_event = threading.Event()
        self._connect_error: str | None = None
        self._manual_disconnect = False
        self._suppress_disconnect_update = False
        PrinterMqttClient._client_instance_counter += 1
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=(
                f"fm_{self.serial}_{os.getpid()}_"
                f"{PrinterMqttClient._client_instance_counter}"
            ),
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(MQTT_USERNAME, self.access_code)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        if self.tls_enabled:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = self.certificate_verify
            ssl_context.verify_mode = ssl.CERT_REQUIRED if self.certificate_verify else ssl.CERT_NONE
            self.client.tls_set_context(ssl_context)

    def connect(self, wait_seconds: float = 5.0) -> None:
        self._connect_event.clear()
        self._connect_error = None
        try:
            self.client.connect(self.host, self.port, keepalive=self.keepalive)
            self.client.loop_start()
        except Exception as exc:
            if is_certificate_verify_error(exc):
                message = CERTIFICATE_VERIFY_HINT
            else:
                message = f"MQTT connection setup failed: {exc}"
            self._update_printer_connection("error", message)
            raise ConnectionError(message) from exc

        if not self._connect_event.wait(wait_seconds):
            self._connect_error = (
                f"Timed out waiting for MQTT connection handshake after {wait_seconds:.1f}s"
            )
            self._update_printer_connection("error", self._connect_error)
            self.disconnect(mark_disconnected=False)
            raise ConnectionError(self._connect_error)
        if self._connect_error:
            self.disconnect(mark_disconnected=False)
            raise ConnectionError(self._connect_error)

    def disconnect(self, *, mark_disconnected: bool = True) -> None:
        self._manual_disconnect = mark_disconnected
        self._suppress_disconnect_update = not mark_disconnected
        self.client.disconnect()
        self.client.loop_stop()
        if mark_disconnected:
            self._update_printer_connection("disconnected", None)

    def request_pushall(self) -> str:
        request = build_pushall_request()
        return self._publish_request(request)

    def request_get_version(self) -> str:
        request = build_get_version_request()
        return self._publish_request(request)

    def request_get_accessories(self) -> str:
        request = build_get_accessories_request()
        return self._publish_request(request)

    def request_full_refresh(self) -> dict[str, str]:
        return {
            "pushall": self.request_pushall(),
            "get_version": self.request_get_version(),
            "get_accessories": self.request_get_accessories(),
        }

    def is_connected(self) -> bool:
        return bool(self.client.is_connected())

    def _publish_request(self, request: MqttRequest) -> str:
        self.client.publish(self.request_topic, json.dumps(request.payload), qos=1)
        return request.sequence_id

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if reason_code != 0 and str(reason_code).lower() not in {"0", "success"}:
            self._connect_error = f"MQTT connect failed: {reason_code}"
            self._update_printer_connection("error", self._connect_error)
            self._connect_event.set()
            LOGGER.warning("MQTT connect failed for printer id %s: %s", self.printer_id, reason_code)
            return
        LOGGER.info("MQTT connected for printer id %s", self.printer_id)
        self._manual_disconnect = False
        self._update_printer_connection("connected", None)
        self._connect_event.set()
        client.subscribe(self.report_topic)
        self.request_pushall()
        self.request_get_version()

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        if self._suppress_disconnect_update:
            LOGGER.info(
                "MQTT disconnected for printer id %s during failed connection cleanup: %s",
                self.printer_id,
                reason_code,
            )
            return
        if self._manual_disconnect:
            self._update_printer_connection("disconnected", None)
            LOGGER.info("MQTT disconnected for printer id %s: %s", self.printer_id, reason_code)
            return
        if not self._connect_event.is_set():
            self._connect_error = f"MQTT disconnected during connect: {reason_code}"
            self._connect_event.set()
        self._update_printer_connection("error", f"MQTT disconnected: {reason_code}")
        LOGGER.info("MQTT disconnected for printer id %s: %s", self.printer_id, reason_code)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Invalid MQTT JSON for printer id %s: %s", self.printer_id, exc)
            return
        if db_session.SessionLocal is None:
            LOGGER.error("Database is not configured; MQTT payload ignored for printer id %s", self.printer_id)
            return
        db: Session = db_session.SessionLocal()
        try:
            process_mqtt_payload(db, printer_id=self.printer_id, payload=payload, topic=message.topic)
        except Exception:
            LOGGER.exception("Failed to process MQTT payload for printer id %s", self.printer_id)
            db.rollback()
        finally:
            db.close()

    def _update_printer_connection(self, status: str, error: str | None) -> None:
        if db_session.SessionLocal is None:
            return
        db: Session = db_session.SessionLocal()
        try:
            printer = db.get(Printer, self.printer_id)
            if printer is None:
                return
            previous_status = printer.connection_status
            printer.connection_status = status
            printer.last_error = error
            if status == "connected":
                printer.last_sync_at = utc_now()
            db.add(printer)
            if previous_status != status and status in {"connected", "disconnected", "error"}:
                event = PrinterEvent(
                    printer_id=printer.id,
                    event_type="printer.connection.restored" if status == "connected" else "printer.connection.disconnected",
                    severity="info" if status == "connected" else "warning",
                    message="Printer MQTT connection restored" if status == "connected" else "Printer MQTT connection disconnected",
                    data={"previous_status": previous_status, "current_status": status, "error": error},
                )
                db.add(event)
                db.flush()
                dispatch_event_notifications(db, event)
            db.commit()
        finally:
            db.close()


class MqttConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[int, PrinterMqttClient] = {}

    def connect(self, db: Session, printer: Printer) -> None:
        if printer.port == 8883 and not printer.tls_enabled:
            raise ValueError("Bambu MQTT port 8883 requires TLS to be enabled")
        self.disconnect(printer.id)
        printer.connection_status = "connecting"
        printer.last_error = None
        db.add(printer)
        db.commit()
        client = PrinterMqttClient(printer)
        self._clients[printer.id] = client
        try:
            client.connect()
        except Exception:
            self._clients.pop(printer.id, None)
            raise

    def disconnect(self, printer_id: int) -> None:
        client = self._clients.pop(printer_id, None)
        if client is not None:
            client.disconnect()

    def disconnect_all(self) -> None:
        printer_ids = list(self._clients)
        for printer_id in printer_ids:
            self.disconnect(printer_id)

    def request_pushall(self, printer_id: int) -> str | None:
        client = self._clients.get(printer_id)
        if client is None or not client.is_connected():
            self._clients.pop(printer_id, None)
            return None
        return client.request_pushall()

    def request_full_refresh(self, printer_id: int) -> dict[str, str] | None:
        client = self._clients.get(printer_id)
        if client is None or not client.is_connected():
            self._clients.pop(printer_id, None)
            return None
        return client.request_full_refresh()

    def is_connected(self, printer_id: int) -> bool:
        client = self._clients.get(printer_id)
        if client is None:
            return False
        if not client.is_connected():
            self._clients.pop(printer_id, None)
            return False
        return True


mqtt_manager = MqttConnectionManager()


def is_certificate_verify_error(value: object) -> bool:
    if isinstance(value, ssl.SSLCertVerificationError):
        return True
    text = str(value).lower()
    return (
        "certificate_verify_failed" in text
        or "certificate verify failed" in text
        or "certificate verification failed" in text
    )
