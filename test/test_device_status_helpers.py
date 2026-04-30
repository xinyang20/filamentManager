from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from filament_manager.api.helpers import (
    bucket_start,
    metric_group_prefix,
    metric_value_float,
    slot_global_tray_id,
    slot_user_tray_id,
)


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


def test_slot_id_helpers_generate_user_visible_and_global_tray_ids() -> None:
    assert slot_user_tray_id(SimpleNamespace(tray_id="0")) == 1
    assert slot_user_tray_id(SimpleNamespace(tray_id="3")) == 4
    assert slot_user_tray_id(SimpleNamespace(tray_id="external")) is None

    assert slot_global_tray_id(SimpleNamespace(ams_id="0", tray_id="3")) == "3"
    assert slot_global_tray_id(SimpleNamespace(ams_id="1", tray_id="0")) == "4"
    assert slot_global_tray_id(SimpleNamespace(ams_id="128", tray_id="0")) == "16"
    assert slot_global_tray_id(SimpleNamespace(ams_id="external", tray_id="0")) == "external:0"
