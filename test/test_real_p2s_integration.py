from __future__ import annotations

import os
import time
from typing import Any

import pytest


pytestmark = pytest.mark.integration


TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.environ.get("FILAMENT_MANAGER_REAL_P2S_TEST", "").strip().lower() in TRUTHY


def _env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for the real P2S integration test")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _create_real_printer(api_client) -> int:
    payload = {
        "name": os.environ.get("FILAMENT_MANAGER_REAL_P2S_NAME", "Local P2S Integration"),
        "host": _env_required("FILAMENT_MANAGER_REAL_P2S_HOST"),
        "port": _env_int("FILAMENT_MANAGER_REAL_P2S_PORT", 8883),
        "serial": _env_required("FILAMENT_MANAGER_REAL_P2S_SERIAL"),
        "access_code": _env_required("FILAMENT_MANAGER_REAL_P2S_ACCESS_CODE"),
        "tls_enabled": _env_bool("FILAMENT_MANAGER_REAL_P2S_TLS", True),
        "certificate_verify": _env_bool("FILAMENT_MANAGER_REAL_P2S_VERIFY_CERT", False),
    }
    response = api_client.post("/api/printers", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert payload["access_code"] not in response.text
    return int(body["id"])


def _raw_commands(api_client) -> set[str]:
    response = api_client.get("/api/debug/raw-mqtt?limit=100")
    assert response.status_code == 200, response.text
    return {item.get("command") for item in response.json() if item.get("command")}


def _poll_real_device_data(api_client, printer_id: int, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state_response = api_client.get(f"/api/printers/{printer_id}/state")
        snapshot_response = api_client.get(f"/api/printers/{printer_id}/device-snapshot")
        dashboard_response = api_client.get(f"/api/printers/{printer_id}/dashboard")
        units_response = api_client.get(f"/api/printers/{printer_id}/ams/units")
        slots_response = api_client.get(f"/api/printers/{printer_id}/ams/slots")

        assert state_response.status_code == 200, state_response.text
        assert snapshot_response.status_code == 200, snapshot_response.text
        assert dashboard_response.status_code == 200, dashboard_response.text
        assert units_response.status_code == 200, units_response.text
        assert slots_response.status_code == 200, slots_response.text

        state = state_response.json()
        snapshot = snapshot_response.json()
        dashboard = dashboard_response.json()
        units = units_response.json()
        slots = slots_response.json()
        commands = _raw_commands(api_client)
        last = {
            "state": state,
            "snapshot": snapshot,
            "dashboard": dashboard,
            "units": units,
            "slots": slots,
            "commands": sorted(commands),
        }
        missing = _missing_required_data(state, snapshot, dashboard, units, slots, commands)
        if not missing:
            return last
        time.sleep(1.0)
    pytest.fail(f"Timed out waiting for real P2S data; missing={_missing_required_data_from_last(last)}; seen={_seen(last)}")


def _missing_required_data(
    state: dict[str, Any] | None,
    snapshot: dict[str, Any] | None,
    dashboard: dict[str, Any] | None,
    units: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    commands: set[str],
) -> list[str]:
    missing: list[str] = []
    if not state or not state.get("gcode_state"):
        missing.append("printer state")
    if not snapshot:
        missing.append("device snapshot")
        return missing
    if not snapshot.get("print_status", {}).get("gcode_state"):
        missing.append("snapshot.print_status.gcode_state")
    if not snapshot.get("temperatures"):
        missing.append("snapshot.temperatures")
    if not snapshot.get("firmware", {}).get("printer_version"):
        missing.append("snapshot.firmware.printer_version")
    if not snapshot.get("accessories", {}).get("payload"):
        missing.append("snapshot.accessories.payload")
    if "push_status" not in commands:
        missing.append("raw command push_status")
    if "get_version" not in commands:
        missing.append("raw command get_version")
    if "get_accessories" not in commands:
        missing.append("raw command get_accessories")
    external_slots = snapshot.get("external_slots") or []
    if not units and not slots and not external_slots:
        missing.append("AMS units/slots or external slots")
    if not dashboard or not dashboard.get("device_snapshot"):
        missing.append("dashboard.device_snapshot")
    return missing


def _missing_required_data_from_last(last: dict[str, Any]) -> list[str]:
    if not last:
        return ["no responses"]
    return _missing_required_data(
        last.get("state"),
        last.get("snapshot"),
        last.get("dashboard"),
        last.get("units") or [],
        last.get("slots") or [],
        set(last.get("commands") or []),
    )


def _seen(last: dict[str, Any]) -> dict[str, Any]:
    snapshot = last.get("snapshot") or {}
    dashboard = last.get("dashboard") or {}
    return {
        "commands": last.get("commands") or [],
        "state": bool(last.get("state")),
        "snapshot_sections": sorted(snapshot.keys()) if isinstance(snapshot, dict) else [],
        "dashboard": bool(dashboard),
        "ams_units": len(last.get("units") or []),
        "ams_slots": len(last.get("slots") or []),
    }


@pytest.mark.skipif(not _enabled(), reason="set FILAMENT_MANAGER_REAL_P2S_TEST=1 to connect to a real P2S")
def test_real_p2s_current_mode_with_access_code_collects_dashboard_data(api_client) -> None:
    printer_id = _create_real_printer(api_client)
    timeout_seconds = _env_float("FILAMENT_MANAGER_REAL_P2S_TIMEOUT", 30.0)
    try:
        connect_response = api_client.post(f"/api/printers/{printer_id}/connect")
        assert connect_response.status_code == 200, connect_response.text
        assert os.environ["FILAMENT_MANAGER_REAL_P2S_ACCESS_CODE"] not in connect_response.text

        refresh_response = api_client.post(f"/api/printers/{printer_id}/refresh-full")
        assert refresh_response.status_code == 200, refresh_response.text
        assert set(refresh_response.json()) == {"pushall", "get_version", "get_accessories"}

        result = _poll_real_device_data(api_client, printer_id, timeout_seconds)
        assert os.environ["FILAMENT_MANAGER_REAL_P2S_ACCESS_CODE"] not in str(result)
    finally:
        api_client.post(f"/api/printers/{printer_id}/disconnect")
