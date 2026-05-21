from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from filament_manager.db.models import AppSetting, DeviceMetricSample, RawMqttMessage, utc_now
from filament_manager.mqtt.parser import extract_print
from filament_manager.services.fans import fan_percent
from filament_manager.services.hotends import hotend_temperature_readings

DEDUPLICATION_WINDOW = timedelta(seconds=60)
RETENTION_PERIOD = timedelta(days=30)
DUAL_NOZZLE_METRIC_BACKFILL_SETTING = "dual_nozzle_metric_backfill_v1_completed_at"


def record_metric_samples_from_push_status(
    db: Session,
    *,
    printer_id: int,
    payload: dict[str, Any],
    raw_message: RawMqttMessage,
) -> list[DeviceMetricSample]:
    now = raw_message.received_at or utc_now()
    rows: list[DeviceMetricSample] = []
    for sample in _samples_from_push_status(payload):
        row = _insert_sample_if_changed(
            db,
            printer_id=printer_id,
            raw_message_id=raw_message.id,
            sampled_at=now,
            **sample,
        )
        if row is not None:
            rows.append(row)
    _delete_old_samples(db, printer_id=printer_id, now=now)
    return rows


def _samples_from_push_status(payload: dict[str, Any]) -> list[dict[str, Any]]:
    print_section = extract_print(payload)
    samples: list[dict[str, Any]] = []
    for source, metric, unit in (
        ("bed_temper", "temperature.bed", "celsius"),
        ("bed_target_temper", "temperature.bed_target", "celsius"),
        ("chamber_temper", "temperature.chamber", "celsius"),
        ("mc_target_cham", "temperature.chamber_target", "celsius"),
    ):
        _append_numeric_sample(samples, metric, print_section.get(source), unit=unit)

    nozzle_readings = hotend_temperature_readings(print_section)
    if len(nozzle_readings) >= 2:
        for item in nozzle_readings:
            details = {"raw_extruder_id": item.get("raw_extruder_id"), "source": item.get("source")}
            _append_numeric_sample(samples, f"temperature.{item['key']}", item.get("current"), unit="celsius", details=details)
            _append_numeric_sample(samples, f"temperature.{item['key']}_target", item.get("target"), unit="celsius", details=details)
    else:
        for source, metric, unit in (
            ("nozzle_temper", "temperature.nozzle", "celsius"),
            ("nozzle_target_temper", "temperature.nozzle_target", "celsius"),
        ):
            _append_numeric_sample(samples, metric, print_section.get(source), unit=unit)

    for source in (
        "fan_gear",
        "cooling_fan_speed",
        "big_fan1_speed",
        "big_fan2_speed",
        "heatbreak_fan_speed",
        "chamber_fan_speed",
        "aux_part_fan_speed",
    ):
        raw = print_section.get(source)
        _append_numeric_sample(samples, f"fan.{source}.percent", fan_percent(raw), unit="percent", raw=raw)

    wifi_signal = print_section.get("wifi_signal", payload.get("wifi_signal"))
    _append_numeric_sample(samples, "network.wifi_signal", _wifi_signal(wifi_signal), unit="dBm", raw=wifi_signal)

    _append_numeric_sample(samples, "print.progress", print_section.get("mc_percent"), unit="percent")
    _append_numeric_sample(samples, "print.remaining_time", print_section.get("mc_remaining_time"), unit="minutes")
    _append_numeric_sample(samples, "print.layer_num", print_section.get("layer_num"), unit="layer")
    _append_numeric_sample(samples, "print.total_layer_num", print_section.get("total_layer_num"), unit="layer")

    ams_section = print_section.get("ams")
    ams_dict = ams_section if isinstance(ams_section, dict) else {}
    ams_units = ams_dict.get("ams")
    if isinstance(ams_units, list):
        for unit in ams_units:
            if not isinstance(unit, dict):
                continue
            ams_id = str(unit.get("id") or unit.get("ams_id") or unit.get("idx") or "")
            if not ams_id:
                continue
            details = {"ams_id": ams_id}
            _append_numeric_sample(
                samples,
                f"ams.{ams_id}.temperature",
                unit.get("temp") or unit.get("temperature"),
                unit="celsius",
                details=details,
            )
            _append_numeric_sample(
                samples,
                f"ams.{ams_id}.humidity",
                unit.get("humidity_raw") or unit.get("humidity"),
                unit="percent",
                details=details,
            )
    return samples


def backfill_dual_nozzle_metric_samples(db: Session) -> dict[str, Any]:
    if db.get(AppSetting, DUAL_NOZZLE_METRIC_BACKFILL_SETTING) is not None:
        return {"skipped": True, "inserted": 0}

    cutoff = utc_now() - RETENTION_PERIOD
    raw_rows = list(
        db.scalars(
            select(RawMqttMessage)
            .where(RawMqttMessage.command == "push_status", RawMqttMessage.received_at >= cutoff)
            .order_by(RawMqttMessage.id)
        ).all()
    )
    inserted = 0
    for raw in raw_rows:
        samples = [sample for sample in _samples_from_push_status(raw.payload) if _is_dual_hotend_metric(sample["metric"])]
        if not samples:
            continue
        existing_metrics = set(
            db.scalars(select(DeviceMetricSample.metric).where(DeviceMetricSample.raw_message_id == raw.id)).all()
        )
        for sample in samples:
            if sample["metric"] in existing_metrics:
                continue
            db.add(
                DeviceMetricSample(
                    printer_id=raw.printer_id,
                    metric=sample["metric"],
                    value_float=sample["value_float"],
                    value_text=sample["value_text"],
                    unit=sample["unit"],
                    raw_message_id=raw.id,
                    details=sample["details"],
                    sampled_at=raw.received_at,
                )
            )
            inserted += 1
    db.add(AppSetting(key=DUAL_NOZZLE_METRIC_BACKFILL_SETTING, value=utc_now().isoformat()))
    db.flush()
    return {"skipped": False, "inserted": inserted}


def _is_dual_hotend_metric(metric: str) -> bool:
    return (
        metric.startswith("temperature.hotend_")
        or metric.startswith("temperature.right_hotend")
        or metric.startswith("temperature.left_hotend")
    )


def _insert_sample_if_changed(
    db: Session,
    *,
    printer_id: int,
    metric: str,
    value_float: float | None,
    value_text: str | None,
    unit: str | None,
    raw_message_id: int,
    details: dict[str, Any],
    sampled_at: datetime,
) -> DeviceMetricSample | None:
    previous = db.scalars(
        select(DeviceMetricSample)
        .where(DeviceMetricSample.printer_id == printer_id, DeviceMetricSample.metric == metric)
        .order_by(DeviceMetricSample.sampled_at.desc(), DeviceMetricSample.id.desc())
        .limit(1)
    ).first()
    if previous is not None and _same_sample(previous, value_float, value_text):
        previous_time = _aware(previous.sampled_at)
        current_time = _aware(sampled_at)
        if current_time - previous_time <= DEDUPLICATION_WINDOW:
            return None
    row = DeviceMetricSample(
        printer_id=printer_id,
        metric=metric,
        value_float=value_float,
        value_text=value_text,
        unit=unit,
        raw_message_id=raw_message_id,
        details=details,
        sampled_at=sampled_at,
    )
    db.add(row)
    db.flush()
    return row


def _delete_old_samples(db: Session, *, printer_id: int, now: datetime) -> None:
    cutoff = _aware(now) - RETENTION_PERIOD
    db.execute(
        delete(DeviceMetricSample).where(
            DeviceMetricSample.printer_id == printer_id,
            DeviceMetricSample.sampled_at < cutoff,
        ).execution_options(synchronize_session=False)
    )


def _same_sample(sample: DeviceMetricSample, value_float: float | None, value_text: str | None) -> bool:
    if sample.value_float is None and value_float is None:
        return (sample.value_text or "") == (value_text or "")
    if sample.value_float is None or value_float is None:
        return False
    return abs(sample.value_float - value_float) < 0.000001 and (sample.value_text or "") == (value_text or "")


def _append_numeric_sample(
    samples: list[dict[str, Any]],
    metric: str,
    value: Any,
    *,
    unit: str | None,
    raw: Any | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    parsed = _as_float(value)
    if parsed is None:
        return
    sample_details = dict(details or {})
    if raw is not None:
        sample_details["raw"] = raw
    samples.append(
        {
            "metric": metric,
            "value_float": parsed,
            "value_text": str(value),
            "unit": unit,
            "details": sample_details,
        }
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _wifi_signal(value: Any) -> int | None:
    if isinstance(value, str):
        value = value.replace("dBm", "").strip()
    return _as_int(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
