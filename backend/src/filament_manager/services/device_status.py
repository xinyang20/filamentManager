from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import AmsUnit, DeviceStatusSnapshot, Printer, PrinterEvent, RawMqttMessage, utc_now
from filament_manager.mqtt.parser import extract_print, identify_tray
from filament_manager.services.fans import fan_percent, packed_fan_bytes
from filament_manager.services.hms import enrich_hms_error


DICT_FIELDS = {
    "print_status",
    "derived_status",
    "temperatures",
    "fans",
    "network",
    "hardware",
    "nozzles",
    "storage",
    "camera",
    "camera_options",
    "lights",
    "speed",
    "calibration",
    "ams_status",
    "firmware",
    "accessories",
    "unsupported_features",
    "data_coverage",
    "raw_refs",
}
REPLACE_FIELDS = {"hms_errors", "external_slots", "firmware", "accessories", "camera", "camera_options"}
AMS_MODULE_PREFIXES = ("ams/", "n1/", "n3/", "n3f/", "n3s/")
PLATE_RE = re.compile(r"(?:^|/)plate_(\d+)\.gcode(?:$|[/?#])", re.IGNORECASE)

PRINT_STAGE_NAMES = {
    1: "idle_or_finished",
    2: "printing_or_preparing",
    3: "paused",
}
PRINT_SUB_STAGE_NAMES = {
    -1: "none",
    0: "actual_printing",
    1: "auto_bed_leveling",
    4: "printing",
    13: "heating",
    29: "ams_filament_change",
    255: "idle",
}
AIRDUCT_MODE_NAMES = {
    0: "cooling_mode",
    1: "chamber_temperature_hold",
}
AIRDUCT_PART_NAMES = {
    16: "toolhead_fan",
    32: "right_aux_fan",
    48: "exhaust_fan",
    160: "left_aux_fan",
}
LIGHT_NODE_NAMES = {
    "chamber_light": "chamber_light",
    "work_light": "work_light",
}
LIGHT_MODE_NAMES = {
    "on": "on",
    "off": "off",
    "flashing": "flashing",
}
BUILD_PLATE_NAMES = {
    "P0301": "cool_supertack_plate",
}
SPEED_LEVEL_NAMES = {
    1: "silent",
    2: "standard",
    3: "sport",
    4: "ludicrous",
}
SDCARD_STATE_NAMES = {
    "HAS_SDCARD_NORMAL": "normal",
    "NO_SDCARD": "missing",
    "HAS_SDCARD_ABNORMAL": "abnormal",
}
AMS_STATUS_MAIN_NAMES = {
    0: "idle",
    1: "busy",
    2: "rfid_or_filament",
    3: "error",
}
AMS_STATUS_SUB_NAMES = {
    0: "none",
    1: "loading",
    2: "rfid_identifying",
    3: "unloading",
    4: "filament_change",
}
HMS_SEVERITY_NAMES = {
    0: "info",
    1: "info",
    2: "warning",
    3: "error",
    4: "fatal",
}
HMS_MODULE_NAMES = {
    0: "system",
    1: "motion",
    2: "thermal",
    3: "extruder",
    4: "ams",
    5: "print_control",
    6: "camera",
    7: "network",
}
XCAM_CFG_FLAGS = {
    0: "spaghetti_detector",
    1: "pileup_detector",
    2: "nozzle_clumping_detector",
    3: "airprint_detector",
    4: "first_layer_inspector",
    5: "printing_monitor",
    6: "buildplate_marker_detector",
    7: "allow_skip_parts",
}
IPCAM_FIELDS = (
    "agora_service",
    "brtc_service",
    "bs_state",
    "cap_pic_enable",
    "ipcam_dev",
    "ipcam_record",
    "laser_preview_res",
    "liveview_preview",
    "mode_bits",
    "resolution",
    "rtsp_url",
    "timelapse",
    "tutk_server",
)


def upsert_device_status_from_push_status(
    db: Session,
    *,
    printer: Printer,
    payload: dict[str, Any],
    raw_message: RawMqttMessage,
) -> DeviceStatusSnapshot:
    print_section = extract_print(payload)
    updates: dict[str, Any] = {
        "raw_refs": {
            "push_status_raw_id": raw_message.id,
            "push_status_received_at": raw_message.received_at.isoformat(),
        },
    }

    for field_name, section in {
        "print_status": _print_status_payload(print_section),
        "derived_status": _derived_status_payload(print_section),
        "temperatures": _temperature_payload(print_section),
        "fans": _fans_payload(print_section),
        "network": _network_payload(payload, print_section),
        "hardware": _hardware_payload(print_section),
        "nozzles": _nozzles_payload(print_section),
        "storage": _storage_payload(print_section),
        "camera": _camera_payload(payload, print_section),
        "camera_options": _camera_options_payload(payload, print_section),
        "lights": _lights_payload(print_section),
        "speed": _speed_payload(print_section),
        "calibration": _calibration_payload(print_section),
        "ams_status": _ams_status_payload(print_section),
        "unsupported_features": _unsupported_features_payload(print_section),
    }.items():
        if section:
            updates[field_name] = section

    if _has_any_key(print_section, "hms", "print_error"):
        updates["hms_errors"] = _hms_errors_payload(print_section)

    if _has_any_key(print_section, "vir_slot", "vt_tray"):
        updates["external_slots"] = _external_slots_payload(print_section)

    snapshot = _upsert_snapshot(db, printer, updates)
    _emit_hms_events(db, printer.id, snapshot.hms_errors)
    return snapshot


def upsert_device_status_from_get_version(
    db: Session,
    *,
    printer: Printer,
    payload: dict[str, Any],
    raw_message: RawMqttMessage,
) -> DeviceStatusSnapshot:
    info_section = payload.get("info")
    if not isinstance(info_section, dict):
        info_section = {}
    firmware = _firmware_payload(info_section)
    snapshot = _upsert_snapshot(
        db,
        printer,
        {
            "firmware": firmware,
            "raw_refs": {
                "get_version_raw_id": raw_message.id,
                "get_version_received_at": raw_message.received_at.isoformat(),
            },
        },
    )
    _apply_ams_version_to_existing_units(db, printer.id, firmware)
    return snapshot


def upsert_device_status_from_get_accessories(
    db: Session,
    *,
    printer: Printer,
    payload: dict[str, Any],
    raw_message: RawMqttMessage,
) -> DeviceStatusSnapshot:
    system_section = payload.get("system")
    if not isinstance(system_section, dict):
        system_section = {}
    return _upsert_snapshot(
        db,
        printer,
        {
            "accessories": {
                "command": system_section.get("command"),
                "sequence_id": system_section.get("sequence_id"),
                "accessory_type": system_section.get("accessory_type"),
                "payload": system_section,
            },
            "raw_refs": {
                "get_accessories_raw_id": raw_message.id,
                "get_accessories_received_at": raw_message.received_at.isoformat(),
            },
        },
    )


def merge_ams_version_cache(
    db: Session,
    *,
    printer_id: int,
    ams_id: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    if snapshot is None or not isinstance(snapshot.firmware, dict):
        return raw
    cached = _ams_module_for_id(snapshot.firmware.get("ams_modules"), ams_id)
    if not cached:
        return raw
    merged = dict(raw)
    for source_key, target_key in (("sw_ver", "sw_ver"), ("sn", "sn"), ("module_type", "module_type")):
        value = cached.get(source_key)
        if value and not merged.get(target_key):
            merged[target_key] = value
    return merged


def _upsert_snapshot(
    db: Session,
    printer: Printer,
    updates: dict[str, Any],
) -> DeviceStatusSnapshot:
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer.id)
    ).first()
    if snapshot is None:
        snapshot = DeviceStatusSnapshot(printer_id=printer.id, **_empty_snapshot_values())
        db.add(snapshot)

    for field_name, value in updates.items():
        if field_name == "hms_errors":
            value = _merge_hms_activity(snapshot.hms_errors or [], value)
        if field_name in DICT_FIELDS and field_name not in REPLACE_FIELDS:
            current = getattr(snapshot, field_name) or {}
            setattr(snapshot, field_name, _merge_dict(current, value))
        else:
            setattr(snapshot, field_name, value)

    snapshot.updated_at = utc_now()
    snapshot.data_coverage = _data_coverage_payload(snapshot)
    printer.last_sync_at = utc_now()
    printer.connection_status = "connected"
    printer.last_error = None
    db.add(printer)
    db.add(snapshot)
    db.flush()
    return snapshot


def _empty_snapshot_values() -> dict[str, Any]:
    return {
        "print_status": {},
        "derived_status": {},
        "temperatures": {},
        "fans": {},
        "network": {},
        "hardware": {},
        "nozzles": {},
        "storage": {},
        "camera": {},
        "camera_options": {},
        "lights": {},
        "speed": {},
        "calibration": {},
        "ams_status": {},
        "hms_errors": [],
        "firmware": {},
        "accessories": {},
        "external_slots": [],
        "unsupported_features": {},
        "data_coverage": {},
        "raw_refs": {},
    }


def _merge_dict(current: Any, update: Any) -> dict[str, Any]:
    merged = dict(current) if isinstance(current, dict) else {}
    if not isinstance(update, dict):
        return merged
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _print_status_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "command",
        "sequence_id",
        "gcode_state",
        "print_type",
        "mc_percent",
        "mc_remaining_time",
        "gcode_file",
        "subtask_name",
        "project_id",
        "profile_id",
        "task_id",
        "err_code",
        "error_code",
        "print_error",
        "layer_num",
        "total_layer_num",
        "mc_print_stage",
        "mc_print_sub_stage",
        "stg_cur",
        "stg_cd",
        "stg",
        "print_gcode_action",
        "print_real_action",
        "mc_action",
        "mc_print_error_code",
        "home_flag",
        "active_extruder",
        "curr_extruder",
        "plate_id",
        "plate_idx",
        "plate_cnt",
        "subtask_id",
        "job_id",
    ]
    status = _compact({key: print_section.get(key) for key in keys if key in print_section})
    stage_code = _int_from_any(print_section.get("mc_print_stage"))
    sub_stage_code = _first_int_from_any(
        print_section.get("mc_print_sub_stage"),
        print_section.get("stg_cur"),
        print_section.get("print_gcode_action"),
        print_section.get("print_real_action"),
    )
    if stage_code is not None:
        status["stage_name"] = _stage_name(stage_code)
    if sub_stage_code is not None:
        status["sub_stage_name"] = _sub_stage_name(sub_stage_code)
    stg_cur_code = _int_from_any(print_section.get("stg_cur"))
    if stg_cur_code is not None:
        status["stg_cur_name"] = _sub_stage_name(stg_cur_code)
    elif sub_stage_code is not None:
        status["stg_cur_name"] = _sub_stage_name(sub_stage_code)
    user_state = _user_print_state(
        str(print_section.get("gcode_state") or "").strip().upper(),
        stage_code,
        stg_cur_code if stg_cur_code is not None else sub_stage_code,
        _int_from_any(print_section.get("layer_num")),
    )
    if user_state:
        status["user_state"] = user_state
    plate_id = _current_plate_id(print_section.get("gcode_file"))
    if plate_id is None:
        plate_id = _int_from_any(print_section.get("plate_id"))
    if plate_id is not None:
        status["current_plate_id"] = plate_id
    return status


def _derived_status_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    state = str(print_section.get("gcode_state") or "").strip().upper()
    bed = _as_float(print_section.get("bed_temper"))
    bed_target = _as_float(print_section.get("bed_target_temper"))
    nozzle = _as_float(print_section.get("nozzle_temper"))
    nozzle_target = _as_float(print_section.get("nozzle_target_temper"))
    stage = _int_from_any(print_section.get("mc_print_stage"))
    sub_stage = _first_int_from_any(
        print_section.get("mc_print_sub_stage"),
        print_section.get("stg_cur"),
        print_section.get("print_gcode_action"),
        print_section.get("print_real_action"),
    )
    stg_cur = _int_from_any(print_section.get("stg_cur"))
    layer_num = _int_from_any(print_section.get("layer_num"))
    user_state = _user_print_state(state, stage, stg_cur if stg_cur is not None else sub_stage, layer_num)
    ams_section = print_section.get("ams")
    ams_dict = ams_section if isinstance(ams_section, dict) else {}
    ams_status = _as_int(print_section.get("ams_status", ams_dict.get("ams_status")))
    ams_sub = ams_status & 0xFF if ams_status is not None else None
    ams_rfid_status = ams_dict.get("ams_rfid_status", print_section.get("ams_rfid_status"))
    tray_reading_bits = ams_dict.get("tray_reading_bits", print_section.get("tray_reading_bits"))
    printing = user_state in {"preparing", "actual_printing"}
    paused = user_state == "paused" or state in {"PAUSE", "PAUSED"} or stage == 3
    has_error = any(
        _error_value_present(print_section.get(key))
        for key in ("print_error", "mc_print_error_code", "mc_err", "err_code", "error_code")
    ) or _has_actionable_hms(print_section)
    derived = {
        "heating_bed": _is_heating(bed, bed_target),
        "heating_nozzle": _is_heating(nozzle, nozzle_target),
        "printing": bool(printing and not paused),
        "preparing": bool(user_state == "preparing"),
        "actual_printing": bool(user_state == "actual_printing"),
        "paused": bool(paused),
        "idle": bool((state in {"", "IDLE", "FINISH", "FAILED"} or stage == 1) and not printing and not paused),
        "ams_filament_change": bool(sub_stage == 29 or ams_sub == 4),
        "ams_rfid_identifying": bool(_truthy_status(ams_rfid_status) or _truthy_status(tray_reading_bits) or ams_sub == 2),
        "has_error": bool(has_error),
        "user_state": user_state,
        "current_plate_id": _current_plate_id(print_section.get("gcode_file")),
    }
    if stage is not None:
        derived["stage_name"] = _stage_name(stage)
    if sub_stage is not None:
        derived["sub_stage_name"] = _sub_stage_name(sub_stage)
    return _compact(derived)


def _temperature_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "bed_temper": "bed",
        "bed_target_temper": "bed_target",
        "nozzle_temper": "nozzle",
        "nozzle_target_temper": "nozzle_target",
        "chamber_temper": "chamber",
        "mc_target_cham": "chamber_target",
        "nozzle_temper_2": "nozzle_2",
        "nozzle_target_temper_2": "nozzle_2_target",
        "left_nozzle_temper": "left_nozzle",
        "left_nozzle_target_temper": "left_nozzle_target",
        "right_nozzle_temper": "right_nozzle",
        "right_nozzle_target_temper": "right_nozzle_target",
    }
    temperatures: dict[str, Any] = {}
    for source, target in mapping.items():
        if source in print_section:
            temperatures[target] = _as_float(print_section.get(source))
    return _compact(temperatures)


def _fans_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    fans: dict[str, Any] = {}
    for key in (
        "fan_gear",
        "cooling_fan_speed",
        "big_fan1_speed",
        "big_fan2_speed",
        "heatbreak_fan_speed",
        "chamber_fan_speed",
        "aux_part_fan_speed",
    ):
        if key in print_section:
            raw = print_section.get(key)
            packed_bytes = packed_fan_bytes(raw)
            fans[key] = {
                "raw": raw,
                "percent": fan_percent(raw),
                "packed_bytes": packed_bytes or None,
            }
    return fans


def _network_payload(payload: dict[str, Any], print_section: dict[str, Any]) -> dict[str, Any]:
    wifi_signal = _first_present(print_section, payload, "wifi_signal")
    wifi_signal_value = _wifi_signal(wifi_signal)
    wired_hint = _first_present(print_section, payload, "wired_network")
    ethernet_hint = _first_present(print_section, payload, "ethernet")
    is_wired = _as_bool(wired_hint) if wired_hint is not None else None
    if is_wired is None and ethernet_hint is not None:
        is_wired = _as_bool(ethernet_hint)
    if is_wired is None and wifi_signal is not None:
        is_wired = wifi_signal_value == -90
    network = {
        "wifi_signal": wifi_signal_value,
        "wifi_signal_raw": wifi_signal,
        "wifi_quality": _wifi_quality(wifi_signal_value),
        "wired_network": is_wired,
        "connection_type": "wired" if is_wired else "wifi" if wifi_signal is not None else None,
    }
    for key in ("ip", "ipv4", "mac", "ssid", "hostname"):
        value = _first_present(print_section, payload, key)
        if value is not None:
            network[key] = value
    return _compact(network)


def _hardware_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    hardware = {
        "nozzle_type": print_section.get("nozzle_type"),
        "nozzle_diameter": print_section.get("nozzle_diameter"),
        "upgrade_state": print_section.get("upgrade_state"),
        "door_state": _first_present(print_section, print_section, "door_state"),
        "door_open": _as_bool(print_section.get("door_open")) if "door_open" in print_section else None,
        "developer_mode": _as_bool(print_section.get("developer_mode")) if "developer_mode" in print_section else None,
    }
    device = print_section.get("device")
    if isinstance(device, dict):
        hardware["device"] = device
        for key in ("toolhead", "bed", "ctc", "airduct", "plate", "cam"):
            if isinstance(device.get(key), (dict, list)):
                if key == "airduct":
                    hardware[key] = _airduct_payload(device.get(key))
                elif key == "plate":
                    hardware[key] = _plate_payload(device.get(key))
                else:
                    hardware[key] = device.get(key)
        nozzle = device.get("nozzle")
        if isinstance(nozzle, dict):
            hardware["device_nozzle"] = nozzle
            info = nozzle.get("info")
            if isinstance(info, list):
                hardware["nozzle_count"] = len(info)
        extruder = device.get("extruder")
        if isinstance(extruder, dict) and isinstance(extruder.get("info"), list):
            hardware["extruder_count"] = len(extruder["info"])
    for key in ("ext_tool", "laser", "fourth_axis"):
        if key in print_section:
            hardware[key] = print_section.get(key)
    return _compact(hardware)


def _nozzles_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    device = print_section.get("device")
    device = device if isinstance(device, dict) else {}
    nozzle = device.get("nozzle") if isinstance(device.get("nozzle"), dict) else {}
    info = nozzle.get("info")
    if not isinstance(info, list):
        extruder = device.get("extruder") if isinstance(device.get("extruder"), dict) else {}
        info = extruder.get("info") if isinstance(extruder.get("info"), list) else []
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(info):
        if not isinstance(raw, dict):
            continue
        item = {
            "id": raw.get("id", raw.get("nozzle_id", index)),
            "type": raw.get("type", raw.get("nozzle_type", print_section.get("nozzle_type"))),
            "diameter": raw.get("diameter", raw.get("nozzle_diameter", print_section.get("nozzle_diameter"))),
            "wear": raw.get("wear"),
            "state": raw.get("state"),
            "serial_number": raw.get("serial_number", raw.get("sn")),
            "raw": raw,
        }
        items.append(_compact(item))
    current_nozzle_id = _first_present(nozzle, print_section, "current_nozzle_id")
    if current_nozzle_id is None:
        current_nozzle_id = _first_present(nozzle, print_section, "cur_nozzle_id")
    target_nozzle_id = _first_present(nozzle, print_section, "target_nozzle_id")
    if target_nozzle_id is None:
        target_nozzle_id = _first_present(nozzle, print_section, "tar_nozzle_id")
    active_extruder = _first_present(nozzle, print_section, "active_extruder")
    if active_extruder is None:
        active_extruder = _first_present(nozzle, print_section, "curr_extruder")
    if active_extruder is None:
        active_extruder = _first_present(nozzle, print_section, "active_extruder_id")
    nozzle_type = print_section.get("nozzle_type")
    nozzle_diameter = print_section.get("nozzle_diameter")
    if not items and current_nozzle_id is None and target_nozzle_id is None and active_extruder is None and not nozzle and nozzle_type is None and nozzle_diameter is None:
        return {}
    return _compact(
        {
            "current_nozzle_id": current_nozzle_id,
            "target_nozzle_id": target_nozzle_id,
            "active_extruder": active_extruder,
            "nozzle_type": nozzle_type,
            "nozzle_diameter": nozzle_diameter,
            "nozzle_count": len(items) or None,
            "items": items,
            "raw": nozzle or None,
        }
    )


def _storage_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    sdcard_state = print_section.get("sdcard") or print_section.get("sdcard_state")
    return _compact(
        {
            "sdcard": print_section.get("sdcard"),
            "sdcard_state": print_section.get("sdcard_state"),
            "sdcard_state_name": SDCARD_STATE_NAMES.get(str(sdcard_state or ""), None),
            "sdcard_total": print_section.get("sdcard_total"),
            "sdcard_free": print_section.get("sdcard_free"),
            "save_to_sdcard": _as_bool(print_section.get("save_to_sdcard")) if "save_to_sdcard" in print_section else None,
            "storage": print_section.get("storage"),
        }
    )


def _camera_payload(payload: dict[str, Any], print_section: dict[str, Any]) -> dict[str, Any]:
    xcam = print_section.get("xcam")
    if not isinstance(xcam, dict):
        top_level_xcam = payload.get("xcam")
        xcam = top_level_xcam if isinstance(top_level_xcam, dict) else {}
    ipcam = print_section.get("ipcam")
    ipcam_dict = ipcam if isinstance(ipcam, dict) else {}
    camera = {
        "ipcam": ipcam if not isinstance(ipcam, dict) else None,
        "ipcam_record": print_section.get("ipcam_record", xcam.get("ipcam_record", ipcam_dict.get("ipcam_record"))),
        "timelapse": print_section.get("timelapse", xcam.get("timelapse", ipcam_dict.get("timelapse"))),
        "xcam_status": print_section.get("xcam_status", xcam.get("status")),
        "cfg": xcam.get("cfg"),
        "first_layer_inspector": xcam.get("first_layer_inspector"),
        "printing_monitor": xcam.get("printing_monitor"),
        "buildplate_marker_detector": xcam.get("buildplate_marker_detector"),
        "print_halt": xcam.get("print_halt"),
    }
    for key in IPCAM_FIELDS:
        if key in ipcam_dict:
            camera[key] = ipcam_dict.get(key)
    return _compact(camera)


def _camera_options_payload(payload: dict[str, Any], print_section: dict[str, Any]) -> dict[str, Any]:
    xcam = print_section.get("xcam")
    if not isinstance(xcam, dict):
        top_level_xcam = payload.get("xcam")
        xcam = top_level_xcam if isinstance(top_level_xcam, dict) else {}
    cfg = xcam.get("cfg", print_section.get("xcam_cfg"))
    options = _decode_xcam_cfg(cfg)
    ipcam = print_section.get("ipcam")
    ipcam_dict = ipcam if isinstance(ipcam, dict) else {}
    for key in XCAM_CFG_FLAGS.values():
        if key in xcam:
            options[key] = _as_bool(xcam.get(key))
        elif key in print_section:
            options[key] = _as_bool(print_section.get(key))
    options.update(
        _compact(
            {
                "raw_cfg": cfg,
                "ipcam": ipcam if not isinstance(ipcam, dict) else None,
                "ipcam_record": print_section.get("ipcam_record", xcam.get("ipcam_record", ipcam_dict.get("ipcam_record"))),
                "timelapse": print_section.get("timelapse", xcam.get("timelapse", ipcam_dict.get("timelapse"))),
                "xcam_status": print_section.get("xcam_status", xcam.get("status")),
            }
        )
    )
    return _compact(options)


def _lights_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    lights_report = print_section.get("lights_report")
    chamber_light = None
    named_report: list[dict[str, Any]] = []
    if isinstance(lights_report, list):
        for item in lights_report:
            if not isinstance(item, dict):
                continue
            node = str(item.get("node") or "")
            mode = str(item.get("mode") or "")
            named_item = dict(item)
            if node:
                named_item["node_name"] = LIGHT_NODE_NAMES.get(node, node)
            if mode:
                named_item["mode_name"] = LIGHT_MODE_NAMES.get(mode, mode)
            named_report.append(named_item)
            if node == "chamber_light":
                chamber_light = mode == "on"
    return _compact(
        {
            "lights_report": lights_report,
            "lights_report_named": named_report or None,
            "chamber_light": chamber_light,
            "light_report": print_section.get("light_report"),
        }
    )


def _speed_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    speed_level = _int_from_any(print_section.get("spd_lvl"))
    return _compact(
        {
            "spd_lvl": print_section.get("spd_lvl"),
            "spd_lvl_name": SPEED_LEVEL_NAMES.get(speed_level) if speed_level is not None else None,
            "spd_mag": print_section.get("spd_mag"),
            "print_speed": print_section.get("print_speed"),
        }
    )


def _calibration_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    stg_cur = _int_from_any(print_section.get("stg_cur"))
    return _compact(
        {
            "home_flag": print_section.get("home_flag"),
            "stg_cur": print_section.get("stg_cur"),
            "stg_cur_name": _sub_stage_name(stg_cur) if stg_cur is not None else None,
            "stg_cd": print_section.get("stg_cd"),
            "stg": print_section.get("stg"),
            "mapping": print_section.get("mapping"),
            "s_obj": print_section.get("s_obj"),
            "cali_version": print_section.get("cali_version"),
            "extrusion_cali": print_section.get("extrusion_cali"),
            "nozzle_cali": print_section.get("nozzle_cali"),
        }
    )


def _ams_status_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    ams_section = print_section.get("ams")
    ams_dict = ams_section if isinstance(ams_section, dict) else {}
    status_raw = print_section.get("ams_status", ams_dict.get("ams_status"))
    status_int = _as_int(status_raw)
    status: dict[str, Any] = {
        "ams_status": status_int,
        "ams_status_raw": status_raw,
        "tray_now": ams_dict.get("tray_now", print_section.get("tray_now")),
        "tray_pre": ams_dict.get("tray_pre", print_section.get("tray_pre")),
        "tray_tar": ams_dict.get("tray_tar", print_section.get("tray_tar")),
        "ams_exist_bits": ams_dict.get("ams_exist_bits", print_section.get("ams_exist_bits")),
        "tray_exist_bits": ams_dict.get("tray_exist_bits", print_section.get("tray_exist_bits")),
        "tray_reading_bits": ams_dict.get("tray_reading_bits", print_section.get("tray_reading_bits")),
        "tray_hall_out_bits": ams_dict.get("tray_hall_out_bits", print_section.get("tray_hall_out_bits")),
        "mapping": ams_dict.get("mapping", print_section.get("mapping")),
        "ams_rfid_status": ams_dict.get("ams_rfid_status", print_section.get("ams_rfid_status")),
        "version": ams_dict.get("version"),
    }
    if status_int is not None:
        status["ams_status_sub"] = status_int & 0xFF
        status["ams_status_main"] = (status_int >> 8) & 0xFF
        status["ams_status_main_name"] = AMS_STATUS_MAIN_NAMES.get(status["ams_status_main"], "unknown")
        status["ams_status_sub_name"] = AMS_STATUS_SUB_NAMES.get(status["ams_status_sub"], "unknown")
    return _compact(status)


def _hms_errors_payload(print_section: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    hms_list = print_section.get("hms")
    if isinstance(hms_list, list):
        for item in hms_list:
            if not isinstance(item, dict):
                continue
            attr = _int_from_any(item.get("attr")) or 0
            raw_code = _int_from_any(item.get("code")) or 0
            code = raw_code & 0xFFFF
            if code < 0x4000:
                continue
            severity = (attr >> 8) & 0xF
            module = (attr >> 24) & 0xFF
            payload = {
                "code": f"0x{code:x}",
                "code_value": code,
                "attr": attr,
                "module": module,
                "severity": severity if severity > 0 else 2,
                "source": "hms",
                "active": True,
            }
            if raw_code != code:
                payload["raw_code_value"] = raw_code
            errors.append(_enrich_hms_error(payload))
    print_error = _int_from_any(print_section.get("print_error"))
    if print_error:
        module = (print_error >> 16) & 0xFFFF
        code = print_error & 0xFFFF
        if code >= 0x4000:
            short_code = f"{module:04X}_{code:04X}"
            if not any(_hms_short_code(item) == short_code for item in errors):
                errors.append(_enrich_hms_error(
                    {
                        "code": f"0x{code:x}",
                        "code_value": code,
                        "attr": print_error,
                        "module": module >> 8,
                        "severity": 3,
                        "short_code": short_code,
                        "source": "print_error",
                        "active": True,
                    }
                ))
    return errors


def _has_actionable_hms(print_section: dict[str, Any]) -> bool:
    if not isinstance(print_section.get("hms"), list) and not print_section.get("print_error"):
        return False
    return any(error.get("actionable") is not False for error in _hms_errors_payload(print_section))


def _external_slots_payload(print_section: dict[str, Any]) -> list[dict[str, Any]]:
    source = "vir_slot" if "vir_slot" in print_section else "vt_tray"
    raw_slots = print_section.get(source)
    if isinstance(raw_slots, dict):
        raw_list = [raw_slots]
    elif isinstance(raw_slots, list):
        raw_list = raw_slots
    else:
        return []

    slots: list[dict[str, Any]] = []
    for raw_slot in raw_list:
        if not isinstance(raw_slot, dict):
            continue
        identity = identify_tray(raw_slot)
        slot = dict(raw_slot)
        slot.update(
            {
                "source": source,
                "identity_key": identity.identity_key,
                "identity_source": identity.identity_source,
                "identity_confidence": identity.identity_confidence,
                "identity_warning": identity.identity_warning,
            }
        )
        if len(raw_list) == 1 and str(slot.get("id")) == "255":
            slot["normalized_id"] = "254"
        slots.append(slot)
    return slots


def _unsupported_features_payload(print_section: dict[str, Any]) -> dict[str, Any]:
    unsupported: dict[str, Any] = {}
    device = print_section.get("device")
    if isinstance(device, dict):
        extruder = device.get("extruder")
        info = extruder.get("info") if isinstance(extruder, dict) else None
        if isinstance(info, list) and len(info) >= 2:
            unsupported["dual_nozzle"] = {
                "detected": True,
                "structured_support": False,
                "raw": {"device.extruder.info": info},
            }
    vir_slot = print_section.get("vir_slot")
    if isinstance(vir_slot, list) and len(vir_slot) > 1:
        unsupported["multi_external_slot"] = {
            "detected": True,
            "structured_support": False,
            "raw_count": len(vir_slot),
        }
    return unsupported


def _firmware_payload(info_section: dict[str, Any]) -> dict[str, Any]:
    modules = info_section.get("module")
    modules_list = modules if isinstance(modules, list) else []
    firmware: dict[str, Any] = {
        "command": info_section.get("command"),
        "sequence_id": info_section.get("sequence_id"),
        "developer_mode": _as_bool(info_section.get("developer_mode")) if "developer_mode" in info_section else None,
        "hardware_version": info_section.get("hw_ver") or info_section.get("hardware_version"),
        "modules": modules_list,
        "ams_modules": {},
    }
    for module in modules_list:
        if not isinstance(module, dict):
            continue
        name = str(module.get("name") or "")
        if name == "ota":
            firmware["printer_version"] = module.get("sw_ver")
            firmware["printer_module"] = module
            continue
        ams_id, module_type = _parse_ams_module_name(name)
        if ams_id is not None:
            firmware["ams_modules"][ams_id] = {
                "name": name,
                "module_type": module_type,
                "sw_ver": module.get("sw_ver"),
                "sn": module.get("sn"),
                "raw": module,
            }
    return _compact(firmware)


def _apply_ams_version_to_existing_units(db: Session, printer_id: int, firmware: dict[str, Any]) -> None:
    ams_modules = firmware.get("ams_modules")
    if not isinstance(ams_modules, dict) or not ams_modules:
        return
    units = db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer_id)).all()
    for unit in units:
        cached = _ams_module_for_id(ams_modules, unit.ams_id)
        if not cached:
            continue
        raw = dict(unit.raw or {})
        changed = False
        for source_key, target_key in (("sw_ver", "sw_ver"), ("sn", "sn"), ("module_type", "module_type")):
            value = cached.get(source_key)
            if value and not raw.get(target_key):
                raw[target_key] = value
                changed = True
        if changed:
            unit.raw = raw
            unit.updated_at = utc_now()
            db.add(unit)


def _emit_hms_events(db: Session, printer_id: int, hms_errors: list[dict[str, Any]]) -> None:
    for error in hms_errors:
        if error.get("active") is False:
            event_type = "hms.recovered"
        else:
            event_type = "hms.error"
        dedupe_key = f"hms.error:{printer_id}:{error.get('attr')}:{error.get('code')}"
        existing = db.scalars(
            select(PrinterEvent)
            .where(PrinterEvent.printer_id == printer_id, PrinterEvent.dedupe_key == dedupe_key)
            .order_by(PrinterEvent.id.desc())
        ).first()
        if existing and existing.data == error and existing.event_type == event_type:
            continue
        severity = "info"
        if error.get("actionable") is not False and error.get("active") is not False:
            severity = "error" if int(error.get("severity") or 0) >= 3 else "warning"
        event = PrinterEvent(
            printer_id=printer_id,
            event_type=event_type,
            severity=severity,
            message=f"HMS error reported: {error.get('message') or error.get('short_code') or error.get('code')}",
            dedupe_key=dedupe_key,
            data=error,
        )
        db.add(event)
        db.flush()


def _parse_ams_module_name(name: str) -> tuple[str | None, str | None]:
    for prefix in AMS_MODULE_PREFIXES:
        if not name.startswith(prefix):
            continue
        module_type = prefix.rstrip("/")
        raw_id = name.split("/", 1)[1]
        parsed_id = _as_int(raw_id)
        return (str(parsed_id) if parsed_id is not None else raw_id, module_type)
    return None, None


def _ams_module_for_id(ams_modules: Any, ams_id: str) -> dict[str, Any] | None:
    if not isinstance(ams_modules, dict):
        return None
    candidates = [str(ams_id)]
    parsed = _as_int(ams_id)
    if parsed is not None:
        candidates.insert(0, str(parsed))
    for candidate in candidates:
        value = ams_modules.get(candidate)
        if isinstance(value, dict):
            return value
    return None


def _hms_short_code(error: dict[str, Any]) -> str | None:
    if error.get("short_code"):
        return str(error["short_code"])
    attr = _int_from_any(error.get("attr"))
    code = _int_from_any(error.get("code_value"))
    if attr is None or code is None:
        return None
    module = (attr >> 16) & 0xFFFF
    return f"{module:04X}_{code & 0xFFFF:04X}"


def _merge_hms_activity(
    previous_errors: list[dict[str, Any]],
    current_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current: list[dict[str, Any]] = []
    active_keys: set[str] = set()
    for error in current_errors:
        enriched = _enrich_hms_error(dict(error))
        enriched["active"] = True
        key = _hms_identity_key(enriched)
        if key:
            active_keys.add(key)
        current.append(enriched)

    for previous in previous_errors:
        key = _hms_identity_key(previous)
        if key and key in active_keys:
            continue
        inactive = _enrich_hms_error(dict(previous))
        inactive["active"] = False
        current.append(inactive)
    return current


def _hms_identity_key(error: dict[str, Any]) -> str | None:
    short_code = _hms_short_code(error)
    if short_code:
        return short_code
    attr = error.get("attr")
    code = error.get("code") or error.get("code_value")
    if attr is None and code is None:
        return None
    return f"{attr}:{code}"


def _enrich_hms_error(error: dict[str, Any]) -> dict[str, Any]:
    short_code = _hms_short_code(error)
    if short_code:
        error["short_code"] = short_code
    severity = _int_from_any(error.get("severity")) or 2
    module = _int_from_any(error.get("module"))
    error["severity_name"] = HMS_SEVERITY_NAMES.get(severity, "unknown")
    error["module_name"] = HMS_MODULE_NAMES.get(module or -1, f"module_{module}")
    error["message"] = "Printer reported an HMS error."
    if short_code:
        error["wiki_url"] = f"https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{short_code}"
    error.setdefault("active", True)
    return enrich_hms_error(error)


def _data_coverage_payload(snapshot: DeviceStatusSnapshot) -> dict[str, Any]:
    raw_refs = snapshot.raw_refs if isinstance(snapshot.raw_refs, dict) else {}

    def item(
        received: bool,
        *,
        raw_id_key: str,
        received_at_key: str,
        section: str | None = None,
    ) -> dict[str, Any]:
        raw_id = raw_refs.get(raw_id_key)
        return {
            "received": bool(received),
            "last_updated_at": raw_refs.get(received_at_key) if received else None,
            "raw_message_id": raw_id if received else None,
            "section": section,
        }

    push_received = raw_refs.get("push_status_raw_id") is not None
    version_received = raw_refs.get("get_version_raw_id") is not None
    accessories_received = raw_refs.get("get_accessories_raw_id") is not None
    return {
        "push_status": item(
            push_received,
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="raw_refs",
        ),
        "get_version": item(
            version_received,
            raw_id_key="get_version_raw_id",
            received_at_key="get_version_received_at",
            section="raw_refs",
        ),
        "get_accessories": item(
            accessories_received,
            raw_id_key="get_accessories_raw_id",
            received_at_key="get_accessories_received_at",
            section="raw_refs",
        ),
        "temperatures": item(
            bool(snapshot.temperatures),
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="temperatures",
        ),
        "fans": item(
            bool(snapshot.fans),
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="fans",
        ),
        "ams": item(
            bool(snapshot.ams_status),
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="ams_status",
        ),
        "firmware": item(
            bool(snapshot.firmware),
            raw_id_key="get_version_raw_id",
            received_at_key="get_version_received_at",
            section="firmware",
        ),
        "accessories": item(
            bool(snapshot.accessories),
            raw_id_key="get_accessories_raw_id",
            received_at_key="get_accessories_received_at",
            section="accessories",
        ),
        "hms": item(
            bool(snapshot.hms_errors),
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="hms_errors",
        ),
        "camera": item(
            bool(snapshot.camera or snapshot.camera_options),
            raw_id_key="push_status_raw_id",
            received_at_key="push_status_received_at",
            section="camera",
        ),
    }


def _stage_name(value: int) -> str:
    return PRINT_STAGE_NAMES.get(value, f"unknown:{value}")


def _sub_stage_name(value: int) -> str:
    return PRINT_SUB_STAGE_NAMES.get(value, f"unknown:{value}")


def _user_print_state(state: str, stage: int | None, sub_stage: int | None, layer_num: int | None) -> str | None:
    if state in {"PAUSE", "PAUSED"} or stage == 3:
        return "paused"
    if state == "FINISH":
        return "finished"
    if state == "FAILED":
        return "failed_or_cancelled"
    if state in {"", "IDLE"} and stage != 2:
        return "idle"
    if state == "RUNNING" or stage == 2:
        if (layer_num is not None and layer_num > 0) or sub_stage == 0:
            return "actual_printing"
        return "preparing"
    return state.lower() if state else None


def _airduct_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    payload = dict(value)
    for key in ("modeCur", "modeFunc", "subMode"):
        mode = _int_from_any(value.get(key))
        if mode is not None:
            payload[f"{key}_name"] = AIRDUCT_MODE_NAMES.get(mode, f"unknown:{mode}")
    parts = value.get("parts")
    if isinstance(parts, list):
        named_parts: list[dict[str, Any]] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            named = dict(part)
            part_id = _int_from_any(named.get("id"))
            if part_id is not None:
                named["part_name"] = AIRDUCT_PART_NAMES.get(part_id, f"unknown:{part_id}")
            named_parts.append(named)
        payload["parts"] = named_parts
    return _compact(payload)


def _plate_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    payload = dict(value)
    cur_id = value.get("cur_id")
    if cur_id is not None and cur_id != "":
        payload["cur_id_name"] = BUILD_PLATE_NAMES.get(str(cur_id), str(cur_id))
    return _compact(payload)


def _current_plate_id(value: Any) -> int | None:
    if value is None:
        return None
    match = PLATE_RE.search(str(value))
    if not match:
        return None
    return _as_int(match.group(1))


def _first_int_from_any(*values: Any) -> int | None:
    for value in values:
        parsed = _int_from_any(value)
        if parsed is not None:
            return parsed
    return None


def _is_heating(current: float | None, target: float | None) -> bool:
    return current is not None and target is not None and target > 0 and current < target - 1.0


def _truthy_status(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    number = _int_from_any(value)
    if number is not None:
        return number != 0
    return str(value).strip().lower() not in {"0", "false", "off", "disable", "disabled", "none"}


def _error_value_present(value: Any) -> bool:
    if value is None or value == "":
        return False
    number = _int_from_any(value)
    if number is not None:
        return number != 0
    return str(value).strip().lower() not in {"0", "none", "ok"}


def _decode_xcam_cfg(value: Any) -> dict[str, Any]:
    cfg = _int_from_any(value)
    if cfg is None:
        return {}
    return {name: bool(cfg & (1 << bit)) for bit, name in XCAM_CFG_FLAGS.items()}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "on", "enable", "enabled", "yes"}


def _compact(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _has_any_key(values: dict[str, Any], *keys: str) -> bool:
    return any(key in values for key in keys)


def _first_present(primary: dict[str, Any], secondary: dict[str, Any], key: str) -> Any:
    if key in primary:
        return primary.get(key)
    return secondary.get(key)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_from_any(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if value is None or value == "":
        return None
    text = str(value).strip().replace("_", "")
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text, 10)
    except ValueError:
        try:
            return int(text, 16)
        except ValueError:
            return None


def _wifi_signal(value: Any) -> int | None:
    if isinstance(value, str):
        value = value.replace("dBm", "").strip()
    return _as_int(value)


def _wifi_quality(value: int | None) -> int | None:
    if value is None or value <= -90:
        return None if value is None else 0
    if value >= -50:
        return 100
    return max(0, min(100, round((value + 90) * 2.5)))
