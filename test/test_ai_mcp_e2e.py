from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MCP_ROOT = ROOT / "integrations" / "ai" / "mcp"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

from filament_manager_mcp.ams import get_ams_overview
from filament_manager_mcp.events import get_hms_code_info, get_recent_events
from filament_manager_mcp.filament import find_filament_anomalies, get_filament_inventory_summary
from filament_manager_mcp.maintenance import get_maintenance_overview
from filament_manager_mcp.print_log import get_print_log_summary, list_recent_print_logs
from filament_manager_mcp.printers import get_printer_overview, get_system_health, list_printers
from filament_manager_mcp.tools import configure_client_factory, reset_client_factory
from integrations.ai.shared.client import FilamentManagerApiClient
from integrations.ai.shared.config import AiIntegrationSettings


SENSITIVE_FRAGMENTS = (
    "192.168.1.20",
    "01P00A123456789",
    "ACCESS-123456",
    "ABCDEF0123456789",
    "11111111-2222-3333-4444-555555555555",
    "/Metadata/plate_2.gcode",
    "/Users/xinyang20",
    "device/01P00A123456789/report",
    "Authorization: Bearer",
    "raw_refs",
    "gcode_file",
    "task_id",
    "tag_uid",
    "tray_uuid",
    "identity_key",
    "serial_number",
    "access_code",
)


def _response_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _routes() -> dict[str, Any]:
    printer = {
        "id": 1,
        "name": "工作室的P2S",
        "enabled": True,
        "connection_status": "connected",
        "last_sync_at": "2026-05-04T10:00:00Z",
        "last_error": "connected via 192.168.1.20 serial 01P00A123456789",
        "host": "192.168.1.20",
        "port": 8883,
        "serial": "01P00A123456789",
        "access_code": "ACCESS-123456",
    }
    active_spool = {
        "id": 12,
        "sku_id": 7,
        "status": "loaded_in_ams",
        "brand_name": "Bambu",
        "material": "PLA",
        "series": "Basic",
        "color_name": "White",
        "color_hex": "#FFFFFF",
        "current_remaining_g": 88,
        "nominal_weight_g": 1000,
        "last_ams_remain_percent": 9,
        "current_ams_id": "0",
        "current_tray_id": "0",
        "tag_uid": "ABCDEF0123456789",
        "tray_uuid": "11111111-2222-3333-4444-555555555555",
        "identity_key": "11111111-2222-3333-4444-555555555555",
        "config": {"token": "secret-token"},
        "updated_at": "2026-05-04T10:00:00Z",
    }
    review_spool = {
        "id": 13,
        "sku_id": None,
        "status": "unknown",
        "brand_name": "Bambu",
        "material": "PETG",
        "series": "HF",
        "color_hex": "#00FF00",
        "current_ams_id": "0",
        "current_tray_id": "1",
        "config": {"needs_sku_review": True, "path": "/Users/xinyang20/private.txt"},
        "tag_uid": "ABCDEF0123456789",
    }
    maintenance_item = {
        "id": 51,
        "printer_id": 1,
        "printer_name": "工作室的P2S",
        "target_type": "printer",
        "target_label": "运动系统",
        "maintenance_type": {
            "id": 1,
            "code": "carbon_rods",
            "name": "清洁碳杆",
            "description": "Clean carbon rods. See /Users/xinyang20/manual.md for private notes.",
        },
        "due_status": "due",
        "hours_until_due": -3.5,
        "hours_since_last": 203.5,
        "last_performed_at": "2026-04-01T10:00:00Z",
    }
    return {
        "/api/health": {"status": "ok", "database_path": "/Users/xinyang20/Code/filamentManager/filament_manager.db"},
        "/api/printers": [printer],
        "/api/printers/1/dashboard": {
            "printer": printer,
            "state": {
                "gcode_state": "RUNNING",
                "mc_percent": 76,
                "mc_remaining_time": 42,
                "subtask_name": "满血版洞洞板",
                "gcode_file": "/Metadata/plate_2.gcode",
                "task_id": "task-1",
                "payload": {"topic": "device/01P00A123456789/report"},
            },
            "device_snapshot": {
                "print_status": {"layer_num": 205, "total_layer_num": 361, "mc_print_error_code": "0"},
                "temperatures": {"bed": 65, "nozzle": 220, "chamber": 32},
                "fans": {"cooling_fan_speed": {"percent": 53, "raw": 128}},
                "hms_errors": [
                    {
                        "short_code": "0500_8001",
                        "severity_name": "error",
                        "message": "Detected HMS on host 192.168.1.20 serial 01P00A123456789",
                        "active": True,
                    }
                ],
                "network": {"ip": "192.168.1.20"},
                "camera": {"stream_path": "rtsp://192.168.1.20/live"},
                "raw_refs": {"message_id": 99},
            },
            "maintenance_due_count": 1,
        },
        "/api/printers/1/ams/overview": {
            "summary": {
                "ams_count": 1,
                "slot_count": 2,
                "loaded_count": 2,
                "empty_count": 0,
                "transitioning_count": 1,
                "unknown_type_count": 0,
                "active_slot": {"tray_uuid": "11111111-2222-3333-4444-555555555555"},
            },
            "units": [
                {
                    "ams_id": "0",
                    "display_name": "AMS 1",
                    "ams_type_name": "AMS",
                    "humidity": "3",
                    "temperature": "26",
                    "serial_number": "AMS-SERIAL-123456",
                    "raw": {"topic": "device/01P00A123456789/report"},
                    "slots": [
                        {
                            "ams_id": "0",
                            "tray_id": "0",
                            "slot_label": "A1",
                            "material": "PLA",
                            "series": "Basic",
                            "color": "#FFFFFF",
                            "remain": 9,
                            "state_name": "loaded",
                            "is_active": True,
                            "is_transitioning": False,
                            "filament_spool_id": 12,
                            "filament_brand_name": "Bambu",
                            "tag_uid": "ABCDEF0123456789",
                            "tray_uuid": "11111111-2222-3333-4444-555555555555",
                            "identity_key": "11111111-2222-3333-4444-555555555555",
                        },
                        {
                            "ams_id": "0",
                            "tray_id": "1",
                            "slot_label": "A2",
                            "material": "PETG",
                            "series": "HF",
                            "color": "#00FF00",
                            "remain": 75,
                            "state_name": "loaded",
                            "is_transitioning": True,
                            "tag_uid": "ABCDEF0123456789",
                        },
                    ],
                }
            ],
        },
        "/api/filament/inventory/summary": {
            "totals": {
                "sku_count": 2,
                "sealed_quantity": 1,
                "opened_spool_count": 0,
                "ams_spool_count": 2,
                "needs_location_count": 0,
                "empty_spool_count": 0,
                "archived_spool_count": 0,
            },
            "opened_spools": [],
            "ams_spools": [active_spool, review_spool],
            "needs_location_spools": [],
            "empty_spools": [],
            "archived_spools": [],
        },
        "/api/filament/spools": [active_spool, review_spool],
        "/api/print-log/analytics": {
            "total": 2,
            "running": 0,
            "succeeded": 1,
            "failed": 1,
            "cancelled": 0,
            "success_rate": 0.5,
            "average_duration_seconds": 3600,
            "longest_duration_seconds": 7200,
            "by_date": [{"bucket": "2026-05-04", "total": 2, "succeeded": 1, "failed": 1}],
            "by_failure_reason": [{"reason": "0500_8001", "count": 1}],
            "by_hms": [{"code": "0500_8001", "count": 1}],
            "raw_refs": {"task_id": "task-1"},
        },
        "/api/print-log": {
            "total": 1,
            "limit": 20,
            "offset": 0,
            "items": [
                {
                    "id": 17,
                    "printer_name_snapshot": "工作室的P2S",
                    "print_name": "满血版洞洞板",
                    "gcode_file": "/Metadata/plate_2.gcode",
                    "task_id": "task-1",
                    "status": "failed",
                    "started_at": "2026-05-04T08:00:00Z",
                    "finished_at": "2026-05-04T10:00:00Z",
                    "duration_seconds": 7200,
                    "final_progress": 76,
                    "layer_current": 205,
                    "layer_total": 361,
                    "failure_reason": "0500_8001",
                    "hms_summary": [{"short_code": "0500_8001", "message": "host 192.168.1.20"}],
                    "raw_refs": {"topic": "device/01P00A123456789/report"},
                }
            ],
        },
        "/api/events": [
            {
                "id": 123,
                "source": "printer",
                "printer_id": 1,
                "type": "hms",
                "event_type": "hms.error",
                "severity": "warning",
                "active": True,
                "message": "HMS warning at 192.168.1.20 serial 01P00A123456789",
                "dedupe_key": "device/01P00A123456789/report",
                "data": {"access_code": "ACCESS-123456"},
                "created_at": "2026-05-04T10:00:00Z",
            }
        ],
        "/api/hms/codes/0500_8001": {
            "short_code": "0500_8001",
            "module": "motion",
            "severity": "warning",
            "message_zh": "检测到运动系统告警",
            "message_en": "Motion system warning",
            "suggestion_zh": "检查并按前端建议人工处理",
            "suggestion_en": "Inspect manually from the frontend",
            "wiki_url": "https://wiki.bambulab.com/example",
            "known": True,
            "actionable": True,
        },
        "/api/hms/codes/0500_8001/stats": {
            "recent_count": 2,
            "active_count": 1,
            "recovered_count": 1,
            "affected_printers": [1],
            "last_seen_at": "2026-05-04T10:00:00Z",
            "high_frequency": False,
            "recent_events": [
                {
                    "id": 123,
                    "source": "printer",
                    "printer_id": 1,
                    "type": "hms",
                    "severity": "warning",
                    "message": "host 192.168.1.20 serial 01P00A123456789",
                    "data": {"raw": {"topic": "device/01P00A123456789/report"}},
                    "created_at": "2026-05-04T10:00:00Z",
                }
            ],
        },
        "/api/maintenance/overview": {
            "total_items": 1,
            "due_count": 1,
            "soon_count": 0,
            "ok_count": 0,
            "items": [maintenance_item],
        },
        "/api/printers/1/maintenance": [maintenance_item],
    }


def test_ai_mcp_tools_e2e_against_mock_backend_are_get_only_and_redacted() -> None:
    async def run() -> None:
        routes = _routes()
        calls: list[tuple[str, str, dict[str, str]]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path, dict(request.url.params)))
            assert request.method == "GET"
            assert request.url.path in routes
            assert "refresh" not in request.url.path
            assert "camera" not in request.url.path
            assert "storage" not in request.url.path
            assert "export" not in request.url.path
            assert "notifications" not in request.url.path
            return httpx.Response(200, json=routes[request.url.path])

        settings = AiIntegrationSettings(api_base_url="http://backend.test/api", timeout_seconds=5, max_items=100)
        configure_client_factory(lambda: FilamentManagerApiClient(settings, transport=httpx.MockTransport(handler)))
        try:
            results = [
                await get_system_health(),
                await list_printers(),
                await get_printer_overview(1),
                await get_ams_overview(1),
                await get_filament_inventory_summary(),
                await find_filament_anomalies(1),
                await get_print_log_summary(printer_id=1, days=7),
                await list_recent_print_logs(printer_id=1, status="failed", limit=20),
                await get_recent_events(printer_id=1, severity="warning", limit=30),
                await get_hms_code_info("0500_8001"),
                await get_maintenance_overview(printer_id=1),
            ]
        finally:
            reset_client_factory()

        assert all(result["ok"] is True for result in results)
        text = _response_text(results)
        for fragment in SENSITIVE_FRAGMENTS:
            assert fragment not in text

        assert "/api/printers" in {path for _, path, _ in calls}
        assert "/api/printers/1/dashboard" in {path for _, path, _ in calls}
        assert "/api/printers/1/ams/overview" in {path for _, path, _ in calls}
        assert "/api/print-log/analytics" in {path for _, path, _ in calls}
        assert "/api/printers/1/maintenance" in {path for _, path, _ in calls}
        assert {method for method, _, _ in calls} == {"GET"}

        analytics_calls = [params for _, path, params in calls if path == "/api/print-log/analytics"]
        assert analytics_calls[0]["printer_id"] == "1"
        assert analytics_calls[0]["bucket"] == "day"

        anomalies = results[5]["data"]["anomalies"]
        assert {item["type"] for item in anomalies} >= {
            "ams_unknown_filament",
            "ams_slot_transitioning",
            "filament_needs_review",
            "filament_low_stock",
        }

    asyncio.run(run())


def test_ai_mcp_e2e_backend_errors_are_redacted() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(
                500,
                json={
                    "detail": "Traceback at http://192.168.1.20/debug Authorization: Bearer abc.def /Users/xinyang20/app.py"
                },
            )

        settings = AiIntegrationSettings(api_base_url="http://backend.test/api", timeout_seconds=5, max_items=100)
        configure_client_factory(lambda: FilamentManagerApiClient(settings, transport=httpx.MockTransport(handler)))
        try:
            result = await list_printers()
        finally:
            reset_client_factory()

        assert result["ok"] is False
        text = _response_text(result)
        assert "192.168.1.20" not in text
        assert "Bearer" not in text
        assert "/Users/xinyang20" not in text
        assert "http://192.168.1.20" not in text

    asyncio.run(run())
