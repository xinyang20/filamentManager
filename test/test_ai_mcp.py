from __future__ import annotations

import json
import asyncio
from pathlib import Path
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MCP_ROOT = ROOT / "integrations" / "ai" / "mcp"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

from filament_manager_mcp.ams import get_ams_overview
from filament_manager_mcp.filament import list_filament_spools
from filament_manager_mcp.printers import list_printers
from filament_manager_mcp.tools import configure_client_factory, reset_client_factory, safe_print_name
from integrations.ai.shared.client import ApiAccessError, validate_get_path
from integrations.ai.shared.redaction import redact_for_ai


class FakeClient:
    def __init__(self, routes: dict[str, Any], errors: dict[str, Exception] | None = None) -> None:
        self.routes = routes
        self.errors = errors or {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        if path in self.errors:
            raise self.errors[path]
        return self.routes[path]


@pytest.fixture(autouse=True)
def restore_client_factory():
    yield
    reset_client_factory()


def response_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_allowlist_rejects_non_get_and_forbidden_paths() -> None:
    validate_get_path("GET", "/api/printers/1/dashboard")
    validate_get_path("GET", "/printers/1/ams/overview")

    with pytest.raises(ApiAccessError):
        validate_get_path("POST", "/api/printers/1/refresh")
    with pytest.raises(ApiAccessError):
        validate_get_path("GET", "/api/discovery/scan")
    with pytest.raises(ApiAccessError):
        validate_get_path("GET", "http://127.0.0.1:8000/api/printers")


def test_redaction_removes_sensitive_keys_and_values() -> None:
    payload = {
        "name": "P2S",
        "host": "192.168.1.20",
        "serial_number": "01P00A123456789",
        "nested": {
            "message": "Authorization: Bearer abc.def /Users/xinyang20/secret.txt device/01P00A123456789/report",
            "tag_uid": "ABCDEF0123456789",
        },
    }

    redacted, applied = redact_for_ai(payload)
    text = response_text(redacted)

    assert applied is True
    assert "host" not in text
    assert "serial_number" not in text
    assert "tag_uid" not in text
    assert "192.168.1.20" not in text
    assert "Bearer" not in text
    assert "/Users/" not in text
    assert "device/" not in text


def test_safe_print_name_drops_paths_and_raw_gcode_names() -> None:
    assert safe_print_name({"print_name": "/Metadata/plate_2.gcode"}) is None
    assert safe_print_name({"print_name": "plate_2.gcode"}) is None
    assert safe_print_name({"print_name": "满血版洞洞板"}) == "满血版洞洞板"


def test_list_printers_whitelists_and_redacts_fields() -> None:
    async def run() -> None:
        configure_client_factory(
            lambda: FakeClient(
                {
                    "/printers": [
                        {
                            "id": 1,
                            "name": "工作室的P2S",
                            "host": "192.168.1.20",
                            "port": 8883,
                            "serial": "01P00A123456789",
                            "access_code": "12345678",
                            "tls_enabled": True,
                            "certificate_verify": False,
                            "enabled": True,
                            "connection_status": "connected",
                            "last_sync_at": "2026-05-04T10:00:00Z",
                            "last_error": "failed to connect 192.168.1.20 serial 01P00A123456789",
                        }
                    ]
                }
            )
        )

        result = await list_printers()
        text = response_text(result)

        assert result["ok"] is True
        assert result["data"]["printers"][0]["printer_id"] == 1
        assert "host" not in text
        assert "access_code" not in text
        assert "serial" not in text
        assert "192.168.1.20" not in text
        assert "01P00A123456789" not in text

    asyncio.run(run())


def test_ams_overview_removes_ams_identity_fields() -> None:
    async def run() -> None:
        configure_client_factory(
            lambda: FakeClient(
                {
                    "/printers/1/ams/overview": {
                        "summary": {
                            "ams_count": 1,
                            "slot_count": 1,
                            "loaded_count": 1,
                            "empty_count": 0,
                            "transitioning_count": 0,
                            "unknown_type_count": 0,
                        },
                        "units": [
                            {
                                "ams_id": "0",
                                "display_name": "AMS 1",
                                "ams_type_name": "AMS",
                                "serial_number": "AMS-SERIAL-123456",
                                "raw": {"host": "192.168.1.20"},
                                "slots": [
                                    {
                                        "ams_id": "0",
                                        "tray_id": "0",
                                        "slot_label": "A1",
                                        "material": "PLA",
                                        "series": "Basic",
                                        "color": "#FFFFFF",
                                        "remain": 86,
                                        "state_name": "loaded",
                                        "is_active": True,
                                        "is_transitioning": False,
                                        "filament_spool_id": 12,
                                        "filament_brand_name": "Bambu",
                                        "tag_uid": "ABCDEF0123456789",
                                        "tray_uuid": "11111111-2222-3333-4444-555555555555",
                                        "identity_key": "11111111-2222-3333-4444-555555555555",
                                        "raw": {"topic": "device/01P00A123456789/report"},
                                    }
                                ],
                            }
                        ],
                    }
                }
            )
        )

        result = await get_ams_overview(1)
        text = response_text(result)

        assert result["ok"] is True
        assert result["data"]["units"][0]["slots"][0]["filament_spool_id"] == 12
        assert "serial_number" not in text
        assert "tag_uid" not in text
        assert "tray_uuid" not in text
        assert "identity_key" not in text
        assert "ABCDEF0123456789" not in text
        assert "device/" not in text

    asyncio.run(run())


def test_list_filament_spools_validates_and_filters() -> None:
    async def run() -> None:
        configure_client_factory(
            lambda: FakeClient(
                {
                    "/filament/spools": [
                        {
                            "id": 12,
                            "sku_id": 7,
                            "status": "loaded_in_ams",
                            "brand_name": "Bambu",
                            "material": "PLA",
                            "series": "Basic",
                            "color_name": "White",
                            "color_hex": "#FFFFFF",
                            "current_remaining_g": 742,
                            "nominal_weight_g": 1000,
                            "last_ams_remain_percent": 86,
                            "current_ams_id": "0",
                            "current_tray_id": "0",
                            "config": {"token": "secret"},
                            "tag_uid": "ABCDEF0123456789",
                            "updated_at": "2026-05-04T10:00:00Z",
                        },
                        {
                            "id": 13,
                            "status": "archived",
                            "brand_name": "Other",
                            "material": "PETG",
                        },
                    ]
                }
            )
        )

        result = await list_filament_spools(status="active", material="PLA", location="ams", limit=10)
        text = response_text(result)

        assert result["ok"] is True
        assert len(result["data"]["spools"]) == 1
        assert result["data"]["spools"][0]["spool_id"] == 12
        assert "tag_uid" not in text
        assert "ABCDEF0123456789" not in text
        assert "token" not in text

        invalid = await list_filament_spools(status="deleted", limit=10)
        assert invalid["ok"] is False
        assert invalid["error_code"] == "invalid_arguments"

        too_many = await list_filament_spools(limit=101)
        assert too_many["ok"] is False
        assert too_many["error_code"] == "invalid_arguments"

    asyncio.run(run())
