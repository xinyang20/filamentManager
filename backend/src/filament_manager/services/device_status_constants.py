from __future__ import annotations

import re

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
REPLACE_FIELDS = {"hms_errors", "external_slots", "firmware", "accessories", "camera", "camera_options", "unsupported_features"}
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
    1: "toolhead_fan",
    2: "right_aux_fan",
    3: "chamber_fan",
    6: "filter_fan",
    9: "ext_toolhead_fan",
    10: "left_aux_fan",
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
    "tl_external_free_kb",
    "tl_external_total_kb",
    "tl_internal_free_kb",
    "tl_internal_total_kb",
    "tl_store_hpd_type",
    "tl_store_path_type",
    "tutk_server",
)
