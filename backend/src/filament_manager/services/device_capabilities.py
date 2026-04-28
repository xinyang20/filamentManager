from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.db.models import AmsUnit, DeviceStatusSnapshot, Printer


CAPABILITY_MATRIX: dict[str, dict[str, Any]] = {
    "x1": {
        "supports_ams": True,
        "supports_chamber_temperature": True,
        "supports_aux_fan": True,
        "supports_camera_fields": True,
        "has_carbon_rods": True,
        "xy_motion": "carbon_rod_x_axis",
        "recommended_maintenance": ["carbon_rod_cleaning", "lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning", "poop_chute_inspection"],
    },
    "p1": {
        "supports_ams": True,
        "supports_chamber_temperature": True,
        "supports_aux_fan": True,
        "supports_camera_fields": True,
        "has_carbon_rods": True,
        "xy_motion": "carbon_rod_x_axis",
        "recommended_maintenance": ["carbon_rod_cleaning", "lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning", "poop_chute_inspection"],
    },
    "p2": {
        "supports_ams": True,
        "supports_chamber_temperature": True,
        "supports_aux_fan": True,
        "supports_camera_fields": True,
        "has_carbon_rods": False,
        "xy_motion": "smooth_rod_x_axis",
        "recommended_maintenance": ["x_axis_smooth_rod_cleaning", "lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning", "poop_chute_inspection"],
    },
    "a1": {
        "supports_ams": True,
        "supports_chamber_temperature": False,
        "supports_aux_fan": False,
        "supports_camera_fields": False,
        "has_carbon_rods": False,
        "xy_motion": "bedslinger",
        "recommended_maintenance": ["lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning"],
    },
    "h2": {
        "supports_ams": True,
        "supports_chamber_temperature": True,
        "supports_aux_fan": True,
        "supports_camera_fields": True,
        "has_carbon_rods": False,
        "xy_motion": "corexy_smooth_rail",
        "recommended_maintenance": ["lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning", "poop_chute_inspection"],
    },
}


def all_device_capabilities() -> dict[str, dict[str, Any]]:
    return {family: {"model_family": family, "known": True, **payload} for family, payload in CAPABILITY_MATRIX.items()}


def printer_capabilities(db: Session, printer: Printer) -> dict[str, Any]:
    snapshot = db.scalars(select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer.id)).first()
    family = _printer_family(printer, snapshot)
    known = family in CAPABILITY_MATRIX
    base = dict(CAPABILITY_MATRIX.get(family, {}))
    evidence = _telemetry_evidence(db, printer.id, snapshot)
    if not known:
        base = _conservative_unknown_capabilities(evidence)
    if evidence["ams_units"] > 0:
        base["supports_ams"] = True
    if evidence["ams_ht_units"] > 0:
        base["supports_ams_ht"] = True
    else:
        base.setdefault("supports_ams_ht", False if known else None)
    if evidence["has_chamber_temperature"]:
        base["supports_chamber_temperature"] = True
    if evidence["has_aux_fan"]:
        base["supports_aux_fan"] = True
    if evidence["has_camera_fields"]:
        base["supports_camera_fields"] = True
    visible_fields = _visible_fields(base, evidence)
    return {
        "model_family": family,
        "model_hint": evidence.get("model_hint"),
        "known": known,
        "supports_ams": base.get("supports_ams"),
        "supports_ams_ht": base.get("supports_ams_ht"),
        "supports_chamber_temperature": base.get("supports_chamber_temperature"),
        "supports_aux_fan": base.get("supports_aux_fan"),
        "supports_camera_fields": base.get("supports_camera_fields"),
        "has_carbon_rods": base.get("has_carbon_rods"),
        "xy_motion": base.get("xy_motion"),
        "recommended_maintenance": base.get("recommended_maintenance", []),
        "visible_fields": visible_fields,
        "evidence": evidence,
    }


def _printer_family(printer: Printer, snapshot: DeviceStatusSnapshot | None) -> str:
    parts: list[str] = [printer.name, printer.serial]
    if snapshot is not None:
        for payload in (snapshot.hardware, snapshot.firmware, snapshot.raw_refs):
            if isinstance(payload, dict):
                parts.extend(str(value) for value in payload.values() if isinstance(value, (str, int, float)))
    text = " ".join(str(part) for part in parts if part).upper()
    if "P2" in text or "P2S" in text:
        return "p2"
    if "X1" in text:
        return "x1"
    if "P1" in text:
        return "p1"
    if "A1" in text:
        return "a1"
    if "H2" in text:
        return "h2"
    return "unknown"


def _telemetry_evidence(db: Session, printer_id: int, snapshot: DeviceStatusSnapshot | None) -> dict[str, Any]:
    units = list(db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer_id)).all())
    temperatures = snapshot.temperatures if snapshot is not None and isinstance(snapshot.temperatures, dict) else {}
    fans = snapshot.fans if snapshot is not None and isinstance(snapshot.fans, dict) else {}
    camera = snapshot.camera if snapshot is not None and isinstance(snapshot.camera, dict) else {}
    hardware = snapshot.hardware if snapshot is not None and isinstance(snapshot.hardware, dict) else {}
    firmware = snapshot.firmware if snapshot is not None and isinstance(snapshot.firmware, dict) else {}
    model_hint = _first_text(
        hardware.get("model"),
        hardware.get("printer_model"),
        firmware.get("hardware_version"),
        firmware.get("printer_module"),
    )
    return {
        "ams_units": len(units),
        "ams_ht_units": sum(1 for unit in units if unit.is_ams_ht),
        "has_chamber_temperature": any(key in temperatures for key in ("chamber", "chamber_target")),
        "has_aux_fan": any(key in fans for key in ("big_fan1_speed", "big_fan2_speed", "aux_part_fan_speed")),
        "has_camera_fields": bool(camera),
        "model_hint": model_hint,
        "snapshot_present": snapshot is not None,
        "maintenance_items_known": int(db.scalar(select(func.count()).select_from(AmsUnit).where(AmsUnit.printer_id == printer_id)) or 0),
    }


def _conservative_unknown_capabilities(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "supports_ams": True if evidence["ams_units"] else None,
        "supports_ams_ht": True if evidence["ams_ht_units"] else None,
        "supports_chamber_temperature": True if evidence["has_chamber_temperature"] else None,
        "supports_aux_fan": True if evidence["has_aux_fan"] else None,
        "supports_camera_fields": True if evidence["has_camera_fields"] else None,
        "has_carbon_rods": None,
        "xy_motion": None,
        "recommended_maintenance": ["lead_screw_lubrication", "nozzle_inspection", "build_plate_cleaning"],
    }


def _visible_fields(capabilities: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    fields = ["print_status", "temperatures", "network", "data_coverage"]
    if capabilities.get("supports_ams") or evidence["ams_units"]:
        fields.append("ams")
    if capabilities.get("supports_chamber_temperature") or evidence["has_chamber_temperature"]:
        fields.append("chamber_temperature")
    if capabilities.get("supports_aux_fan") or evidence["has_aux_fan"]:
        fields.append("aux_fan")
    if capabilities.get("supports_camera_fields") or evidence["has_camera_fields"]:
        fields.append("camera")
    return fields


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, dict):
            value = value.get("hw_ver") or value.get("name") or value.get("sw_ver")
        if value is None or value == "":
            continue
        return str(value)
    return None
