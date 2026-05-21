from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from filament_manager.api.helpers import (
    bucket_start,
    bucket_metric_samples,
    canonical_metric_name,
    metric_group_prefix,
    metric_value_float,
    slot_global_tray_id,
    slot_user_tray_id,
)
from filament_manager.services.hotends import hotend_temperature_readings


def test_metric_group_prefix_maps_supported_filters() -> None:
    assert metric_group_prefix("temperature") == "temperature.%"
    assert metric_group_prefix("fan") == "fan.%"
    assert metric_group_prefix("wifi") == "network.wifi_signal"
    assert metric_group_prefix("ams") == "ams.%"
    assert metric_group_prefix("print") == "print.%"
    assert metric_group_prefix("coverage") == "coverage.%"
    assert metric_group_prefix("unknown") is None
    assert metric_group_prefix(None) is None


def test_bucket_start_truncates_datetime_by_requested_bucket() -> None:
    sampled_at = datetime(2026, 4, 30, 10, 11, 12, 345678, tzinfo=timezone.utc)

    assert bucket_start(sampled_at, "minute") == datetime(2026, 4, 30, 10, 11, tzinfo=timezone.utc)
    assert bucket_start(sampled_at, "hour") == datetime(2026, 4, 30, 10, tzinfo=timezone.utc)
    assert bucket_start(sampled_at, "day") == datetime(2026, 4, 30, tzinfo=timezone.utc)
    assert bucket_start(sampled_at, "raw") == sampled_at


def test_metric_value_float_normalizes_fan_percent_samples() -> None:
    valid = SimpleNamespace(metric="fan.cooling_fan_speed.percent", value_float=53.0, details={})
    raw = SimpleNamespace(metric="fan.cooling_fan_speed.percent", value_float=999.0, details={"raw": "8"})
    clamped = SimpleNamespace(metric="fan.cooling_fan_speed.percent", value_float=150.0, details={})
    temperature = SimpleNamespace(metric="temperature.nozzle", value_float=218.0, details={})

    assert metric_value_float(valid) == 53.0
    assert metric_value_float(raw) == 53.0
    assert metric_value_float(clamped) == 100.0
    assert metric_value_float(temperature) == 218.0


def test_canonical_metric_name_maps_legacy_hotend_metric_names() -> None:
    assert canonical_metric_name("temperature.hotend_a") == "temperature.right_hotend"
    assert canonical_metric_name("temperature.hotend_a_target") == "temperature.right_hotend_target"
    assert canonical_metric_name("temperature.hotend_b") == "temperature.left_hotend"
    assert canonical_metric_name("temperature.hotend_b_target") == "temperature.left_hotend_target"
    assert canonical_metric_name("temperature.bed") == "temperature.bed"


def test_bucket_metric_samples_merges_legacy_and_canonical_hotend_names() -> None:
    sampled_at = datetime(2026, 4, 30, 10, 11, 12, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(id=1, printer_id=1, metric="temperature.hotend_a", value_float=220.0, value_text="220", unit="celsius", raw_message_id=1, details={}, sampled_at=sampled_at),
        SimpleNamespace(id=2, printer_id=1, metric="temperature.right_hotend", value_float=222.0, value_text="222", unit="celsius", raw_message_id=2, details={}, sampled_at=sampled_at),
    ]

    bucketed = bucket_metric_samples(rows, "minute")

    assert len(bucketed) == 1
    assert bucketed[0].metric == "temperature.right_hotend"
    assert bucketed[0].value_float == 221.0


def test_hotend_temperature_readings_decode_dual_extruder_packed_temp() -> None:
    readings = hotend_temperature_readings(
        {
            "nozzle_temper": "199",
            "nozzle_target_temper": "210",
            "device": {
                "extruder": {
                    "info": [
                        {"id": 1, "temp": 0xC800C3},
                        {"id": 0, "temp": 0xDC00DC},
                    ]
                }
            },
        }
    )

    assert [item["key"] for item in readings] == ["right_hotend", "left_hotend"]
    assert readings[0]["current"] == 220.0
    assert readings[0]["target"] == 220.0
    assert readings[0]["raw_extruder_id"] == 0
    assert readings[1]["current"] == 195.0
    assert readings[1]["target"] == 200.0


def test_hotend_temperature_readings_falls_back_to_legacy_nozzle_fields() -> None:
    readings = hotend_temperature_readings({"nozzle_temper": "215", "nozzle_target_temper": "220"})

    assert readings == [
        {
            "key": "nozzle",
            "label_key": "nozzle",
            "current": 215.0,
            "target": 220.0,
            "raw_extruder_id": None,
            "source": "legacy.nozzle_temper",
        }
    ]


def test_slot_id_helpers_generate_user_visible_and_global_tray_ids() -> None:
    assert slot_user_tray_id(SimpleNamespace(tray_id="0")) == 1
    assert slot_user_tray_id(SimpleNamespace(tray_id="3")) == 4
    assert slot_user_tray_id(SimpleNamespace(tray_id="external")) is None

    assert slot_global_tray_id(SimpleNamespace(ams_id="0", tray_id="3")) == "3"
    assert slot_global_tray_id(SimpleNamespace(ams_id="1", tray_id="0")) == "4"
    assert slot_global_tray_id(SimpleNamespace(ams_id="128", tray_id="0")) == "16"
    assert slot_global_tray_id(SimpleNamespace(ams_id="external", tray_id="0")) == "external:0"
