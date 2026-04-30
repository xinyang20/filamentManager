from __future__ import annotations

from types import SimpleNamespace

from filament_manager.api.helpers import (
    parse_range_header,
    sanitize_camera_response,
    storage_capacity,
    storage_file_can_inline,
    storage_media_type,
    storage_target_name,
    storage_telemetry_from_sections,
)


def test_parse_range_header_supports_standard_suffix_and_open_ended_ranges() -> None:
    assert parse_range_header("bytes=10-19", 100) == (10, 19)
    assert parse_range_header("bytes=95-", 100) == (95, 99)
    assert parse_range_header("bytes=-5", 100) == (95, 99)

    assert parse_range_header("items=0-10", 100) is None
    assert parse_range_header("bytes=100-120", 100) is None
    assert parse_range_header("bytes=20-10", 100) is None
    assert parse_range_header("bytes=-0", 100) is None


def test_storage_telemetry_capacity_and_target_helpers() -> None:
    telemetry = storage_telemetry_from_sections(
        {"tl_internal_total_kb": "1024", "tl_internal_free_kb": "256", "tl_store_path_type": 1},
        {"tl_external_total_kb": 4096, "tl_external_free_kb": 2048, "tl_store_path_type": 2},
    )

    assert telemetry["tl_store_path_type"] == 2
    assert storage_capacity(telemetry, "internal") == {
        "total_bytes": 1048576,
        "free_bytes": 262144,
        "used_bytes": 786432,
        "used_percent": 75.0,
    }
    assert storage_capacity(telemetry, "external")["used_percent"] == 50.0
    assert storage_target_name(1) == "internal"
    assert storage_target_name("2") == "external"
    assert storage_target_name("unknown") is None


def test_storage_media_helpers_choose_safe_inline_types() -> None:
    video = SimpleNamespace(name="demo.mp4", path="/timelapse/demo.mp4", type="timelapse")
    log = SimpleNamespace(name="system.log", path="/logs/system.log", type="log")
    gcode = SimpleNamespace(name="part.unknown", path="/models/part.unknown", type="gcode")

    assert storage_media_type(video) == "video/mp4"
    assert storage_file_can_inline(video) is True
    assert storage_media_type(log).startswith("text/plain")
    assert storage_file_can_inline(log) is True
    assert storage_media_type(gcode) == "application/octet-stream"
    assert storage_file_can_inline(gcode) is False


def test_sanitize_camera_response_keeps_scalar_status_without_nested_payloads() -> None:
    assert sanitize_camera_response(
        {
            "ipcam_record": True,
            "timelapse": False,
            "rtsp_url": "rtsp://192.0.2.10/live",
            "raw": {"secret": "value"},
            "items": [1, 2],
            "empty": "",
            "missing": None,
        }
    ) == {
        "ipcam_record": True,
        "timelapse": False,
        "rtsp_url": "rtsp://192.0.2.10/live",
    }
