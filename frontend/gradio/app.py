from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

import gradio as gr
from filament_manager.services.discovery import scan_lan_devices as scan_lan_devices_local

API_URL = os.environ.get("FILAMENT_MANAGER_API_URL", "http://127.0.0.1:8000/api").rstrip("/")
LANG_ZH = "简体中文"
LANG_EN = "English"
DEFAULT_LANGUAGE = LANG_ZH
PLATE_RE = re.compile(r"(?:^|/)plate_(\d+)\.gcode(?:$|[/?#])", re.IGNORECASE)

TEXT = {
    "zh": {
        "title_md": "# FilamentManager\n\n本地 3D 打印耗材管理开发界面",
        "language": "界面语言",
        "printer": "打印机",
        "refresh": "刷新",
        "scan_devices": "扫描局域网设备",
        "scan_timeout": "端口超时（秒）",
        "validation_timeout": "验证超时（秒）",
        "discovery_table": "发现的候选设备",
        "no_discovery": "未发现候选设备",
        "name": "名称",
        "host": "主机",
        "port": "端口",
        "serial": "序列号",
        "access_code": "Access Code",
        "tls": "TLS",
        "certificate_verify": "校验证书",
        "save": "保存",
        "delete": "删除",
        "connect": "连接",
        "disconnect": "断开",
        "pushall": "手动同步",
        "full_refresh": "完整刷新",
        "result": "结果",
        "refresh_dashboard": "刷新设备大屏",
        "dashboard_overview": "概览",
        "dashboard_derived": "派生状态",
        "dashboard_thermal": "温度与风扇",
        "dashboard_network_hardware": "网络与硬件",
        "dashboard_camera": "摄像头与检测",
        "dashboard_ams_advanced": "AMS 进阶信息",
        "dashboard_hms": "HMS / 错误",
        "dashboard_coverage": "数据覆盖率",
        "dashboard_snapshot": "设备快照 JSON",
        "refresh_metrics": "刷新历史趋势",
        "metrics_temperatures": "温度历史",
        "metrics_fans_network": "风扇 / WiFi 历史",
        "metrics_ams": "AMS 温湿度历史",
        "metrics_progress": "打印进度历史",
        "scan_storage": "扫描只读存储",
        "refresh_storage": "刷新存储列表",
        "storage_files": "文件列表",
        "storage_stats": "存储统计",
        "refresh_state": "刷新状态",
        "status_table": "状态摘要",
        "state_snapshot": "状态快照",
        "recent_events": "最近事件",
        "refresh_slots": "刷新槽位",
        "slot_table": "AMS 槽位",
        "refresh_inventory": "刷新库存",
        "inventory_table": "库存料卷",
        "brand": "品牌",
        "material": "材料",
        "series": "系列",
        "color": "颜色",
        "sealed_qty": "封存数量",
        "status": "状态",
        "create_spool": "新建料卷",
        "slot_id": "槽位 ID",
        "spool_id": "料卷 ID",
        "bind": "绑定",
        "inventory_result": "库存结果",
        "refresh_debug": "刷新调试信息",
        "raw_mqtt": "原始 MQTT",
        "events": "事件",
        "printers": "打印机",
        "select_printer_first": "请先选择打印机",
        "deleted": "已删除",
        "cannot_reach_backend": "无法连接后端",
        "api_error": "API 错误",
        "status_state": "状态",
        "status_progress": "进度",
        "status_remaining_min": "剩余分钟",
        "status_task": "任务",
        "status_error_code": "错误码",
        "printer_headers": ["ID", "名称", "主机", "端口", "序列号", "连接状态", "最后同步", "错误"],
        "discovery_headers": ["主机", "开放端口", "置信度", "设备名", "型号", "序列号", "连接模式", "绑定状态", "安全连接", "固件版本", "判定原因"],
        "status_headers": ["字段", "值"],
        "dashboard_headers": ["字段", "值"],
        "dashboard_metric_headers": ["分组", "字段", "值"],
        "dashboard_camera_headers": ["分组", "开关/字段", "值"],
        "dashboard_ams_headers": ["类型", "AMS", "槽位", "字段", "值"],
        "dashboard_hms_headers": ["来源", "代码", "模块", "级别", "当前存在", "说明", "Wiki"],
        "dashboard_coverage_headers": ["数据项", "已收到", "最后更新", "Raw ID"],
        "metrics_headers": ["时间", "指标", "值", "单位", "详情"],
        "storage_headers": ["路径", "名称", "大小", "修改时间", "类型", "来源"],
        "event_headers": ["时间", "类型", "级别", "消息"],
        "slot_headers": ["AMS", "槽位", "材料", "系列", "颜色", "剩余", "槽位状态", "身份来源", "告警", "料卷"],
        "inventory_headers": ["ID", "名称", "材料", "系列", "颜色", "状态", "封存数量", "打印机", "AMS", "槽位"],
        "connection_status": {
            "connected": "已连接",
            "connecting": "连接中",
            "disconnected": "已断开",
            "error": "错误",
        },
        "spool_status": {
            "sealed": "封存",
            "opened": "已启封",
            "active": "使用中",
            "archived": "已归档",
        },
        "severity": {
            "info": "信息",
            "warning": "警告",
            "error": "错误",
        },
        "identity_source": {
            "tray_uuid": "tray_uuid",
            "tag_uid": "tag_uid 兜底",
            "manual_required": "需要手动绑定",
        },
    },
    "en": {
        "title_md": "# FilamentManager\n\nLocal 3D printer filament management development UI",
        "language": "UI Language",
        "printer": "Printer",
        "refresh": "Refresh",
        "scan_devices": "Scan LAN Devices",
        "scan_timeout": "Port Timeout (s)",
        "validation_timeout": "Verify Timeout (s)",
        "discovery_table": "Discovered Candidate Devices",
        "no_discovery": "No candidate devices found",
        "name": "Name",
        "host": "Host",
        "port": "Port",
        "serial": "Serial",
        "access_code": "Access Code",
        "tls": "TLS",
        "certificate_verify": "Verify Certificate",
        "save": "Save",
        "delete": "Delete",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "pushall": "Pushall",
        "full_refresh": "Full Refresh",
        "result": "Result",
        "refresh_dashboard": "Refresh Dashboard",
        "dashboard_overview": "Overview",
        "dashboard_derived": "Derived Status",
        "dashboard_thermal": "Temperature & Fans",
        "dashboard_network_hardware": "Network & Hardware",
        "dashboard_camera": "Camera & Detection",
        "dashboard_ams_advanced": "AMS Advanced",
        "dashboard_hms": "HMS / Errors",
        "dashboard_coverage": "Data Coverage",
        "dashboard_snapshot": "Device Snapshot JSON",
        "refresh_metrics": "Refresh Metrics",
        "metrics_temperatures": "Temperature History",
        "metrics_fans_network": "Fans / WiFi History",
        "metrics_ams": "AMS Temperature & Humidity",
        "metrics_progress": "Print Progress History",
        "scan_storage": "Scan Read-only Storage",
        "refresh_storage": "Refresh Storage Files",
        "storage_files": "Files",
        "storage_stats": "Storage Stats",
        "refresh_state": "Refresh State",
        "status_table": "Status Summary",
        "state_snapshot": "State Snapshot",
        "recent_events": "Recent Events",
        "refresh_slots": "Refresh Slots",
        "slot_table": "AMS Slots",
        "refresh_inventory": "Refresh Inventory",
        "inventory_table": "Inventory Spools",
        "brand": "Brand",
        "material": "Material",
        "series": "Series",
        "color": "Color",
        "sealed_qty": "Sealed Qty",
        "status": "Status",
        "create_spool": "Create Spool",
        "slot_id": "Slot ID",
        "spool_id": "Spool ID",
        "bind": "Bind",
        "inventory_result": "Inventory Result",
        "refresh_debug": "Refresh Debug",
        "raw_mqtt": "Raw MQTT",
        "events": "Events",
        "printers": "Printers",
        "select_printer_first": "Select a printer first",
        "deleted": "deleted",
        "cannot_reach_backend": "Cannot reach backend",
        "api_error": "API error",
        "status_state": "State",
        "status_progress": "Progress",
        "status_remaining_min": "Remaining minutes",
        "status_task": "Task",
        "status_error_code": "Error code",
        "printer_headers": ["ID", "Name", "Host", "Port", "Serial", "Status", "Last Sync", "Error"],
        "discovery_headers": ["Host", "Open Ports", "Confidence", "Device Name", "Model", "Serial", "Connection", "Bind State", "Secure Link", "Firmware", "Reason"],
        "status_headers": ["Field", "Value"],
        "dashboard_headers": ["Field", "Value"],
        "dashboard_metric_headers": ["Group", "Field", "Value"],
        "dashboard_camera_headers": ["Group", "Option / Field", "Value"],
        "dashboard_ams_headers": ["Type", "AMS", "Tray", "Field", "Value"],
        "dashboard_hms_headers": ["Source", "Code", "Module", "Severity", "Active", "Message", "Wiki"],
        "dashboard_coverage_headers": ["Item", "Received", "Last Updated", "Raw ID"],
        "metrics_headers": ["Time", "Metric", "Value", "Unit", "Details"],
        "storage_headers": ["Path", "Name", "Size", "Modified", "Type", "Source"],
        "event_headers": ["Time", "Type", "Severity", "Message"],
        "slot_headers": ["AMS", "Tray", "Material", "Series", "Color", "Remain", "State", "Identity Source", "Warning", "Spool"],
        "inventory_headers": ["ID", "Name", "Material", "Series", "Color", "Status", "Sealed Qty", "Printer", "AMS", "Tray"],
        "connection_status": {
            "connected": "connected",
            "connecting": "connecting",
            "disconnected": "disconnected",
            "error": "error",
        },
        "spool_status": {
            "sealed": "sealed",
            "opened": "opened",
            "active": "active",
            "archived": "archived",
        },
        "severity": {
            "info": "info",
            "warning": "warning",
            "error": "error",
        },
        "identity_source": {
            "tray_uuid": "tray_uuid",
            "tag_uid": "tag_uid fallback",
            "manual_required": "manual required",
        },
    },
}


def _lang(language: str | None) -> str:
    if language == LANG_EN:
        return "en"
    return "zh"


def _text(language: str | None, key: str) -> Any:
    return TEXT[_lang(language)][key]


def _display(language: str | None, category: str, value: Any) -> Any:
    if value is None:
        return None
    mapping = TEXT[_lang(language)].get(category, {})
    if not isinstance(mapping, dict):
        return value
    return mapping.get(str(value), value)


def _status_choices(language: str | None) -> list[tuple[str, str]]:
    labels = _text(language, "spool_status")
    return [(labels["sealed"], "sealed"), (labels["opened"], "opened"), (labels["active"], "active"), (labels["archived"], "archived")]


def _select_printer_error(language: str | None) -> None:
    raise gr.Error(_text(language, "select_printer_first"))


def _printer_id_or_error(value: Any, language: str | None) -> int:
    if value is None or value == "" or value == []:
        _select_printer_error(language)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (list, tuple)):
        if not value:
            _select_printer_error(language)
        return _printer_id_or_error(value[0], language)
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "[]":
            _select_printer_error(language)
        if ":" in text:
            text = text.split(":", 1)[0].strip()
        try:
            return int(text)
        except ValueError as exc:
            raise gr.Error(_text(language, "select_printer_first")) from exc
    raise gr.Error(_text(language, "select_printer_first"))


def _request(method: str, path: str, body: dict[str, Any] | None = None, language: str | None = DEFAULT_LANGUAGE) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise gr.Error(f"{_text(language, 'api_error')} {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise gr.Error(f"{_text(language, 'cannot_reach_backend')}: {exc}") from exc


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _timeout_value(value: float | None, default: float) -> float:
    if value is None:
        return default
    return max(0.05, min(float(value), 2.0))


def refresh_printers(language: str | None = DEFAULT_LANGUAGE) -> tuple[list[list[Any]], Any]:
    printers = _request("GET", "/printers", language=language) or []
    rows = [
        [
            item["id"],
            item["name"],
            item["host"],
            item["port"],
            item["serial"],
            _display(language, "connection_status", item["connection_status"]),
            item.get("last_sync_at"),
            item.get("last_error"),
        ]
        for item in printers
    ]
    choices = [
        (
            f'{item["id"]}: {item["name"]} '
            f'({item["host"]}, TLS={item["tls_enabled"]}, '
            f'verify={item["certificate_verify"]}, {item["connection_status"]})',
            item["id"],
        )
        for item in printers
    ]
    selected = choices[0][1] if choices else None
    return rows, gr.update(choices=choices, value=selected)


def scan_devices(
    scan_timeout: float | None = 0.25,
    validation_timeout: float | None = 0.35,
    language: str | None = DEFAULT_LANGUAGE,
    progress: gr.Progress = gr.Progress(),
) -> tuple[list[list[Any]], Any, Any, Any, Any, Any, Any, str]:
    def update_progress(value: float, message: str) -> None:
        progress(value, desc=message)

    candidates = [
        item.to_dict()
        for item in scan_lan_devices_local(
            timeout=_timeout_value(scan_timeout, 0.25),
            validation_timeout=_timeout_value(validation_timeout, 0.35),
            progress_callback=update_progress,
        )
    ]
    rows = [
        [
            item["host"],
            ", ".join(str(port) for port in item.get("open_ports", [])),
            item.get("confidence"),
            item.get("device_name"),
            item.get("model"),
            item.get("serial"),
            item.get("connection_mode"),
            item.get("bind_state"),
            item.get("secure_link"),
            item.get("firmware_version"),
            item.get("reason"),
        ]
        for item in candidates
    ]
    if not candidates:
        return rows, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(value=True), gr.update(value=False), _text(language, "no_discovery")

    first = candidates[0]
    suggested_name = first.get("device_name") or first.get("hostname") or "Bambu Printer"
    suggested_serial = first.get("serial") or ""
    return (
        rows,
        gr.update(value=suggested_name),
        gr.update(value=first["host"]),
        gr.update(value=8883),
        gr.update(value=suggested_serial),
        gr.update(value=True),
        gr.update(value=False),
        _json(first),
    )


def save_printer(
    name: str,
    host: str,
    port: int,
    serial: str,
    access_code: str,
    tls_enabled: bool,
    certificate_verify: bool,
    language: str | None,
) -> tuple[list[list[Any]], list[tuple[str, int]], str]:
    payload = {
        "name": name,
        "host": host,
        "port": int(port),
        "serial": serial,
        "access_code": access_code,
        "tls_enabled": tls_enabled,
        "certificate_verify": certificate_verify,
    }
    printer = _request("POST", "/printers", payload, language=language)
    rows, choices = refresh_printers(language)
    return rows, choices, _json(printer)


def delete_printer(printer_id: Any, language: str | None) -> tuple[list[list[Any]], Any, str]:
    printer_id = _printer_id_or_error(printer_id, language)
    _request("DELETE", f"/printers/{printer_id}", language=language)
    rows, choices = refresh_printers(language)
    return rows, choices, _text(language, "deleted")


def connect_printer(printer_id: Any, language: str | None) -> str:
    printer_id = _printer_id_or_error(printer_id, language)
    return _json(_request("POST", f"/printers/{printer_id}/connect", language=language))


def disconnect_printer(printer_id: Any, language: str | None) -> str:
    printer_id = _printer_id_or_error(printer_id, language)
    return _json(_request("POST", f"/printers/{printer_id}/disconnect", language=language))


def refresh_pushall(printer_id: Any, language: str | None) -> str:
    printer_id = _printer_id_or_error(printer_id, language)
    return _json(_request("POST", f"/printers/{printer_id}/refresh", language=language))


def refresh_full(printer_id: Any, language: str | None) -> str:
    printer_id = _printer_id_or_error(printer_id, language)
    return _json(_request("POST", f"/printers/{printer_id}/refresh-full", language=language))


def refresh_full_and_load_dashboard(
    printer_id: Any,
    language: str | None,
) -> tuple[
    str,
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    str,
]:
    printer_id = _printer_id_or_error(printer_id, language)
    result = _request("POST", f"/printers/{printer_id}/refresh-full", language=language)
    dashboard_rows = _load_dashboard_rows(printer_id, language, wait_seconds=5.0)
    return (_json(result), *dashboard_rows)


def load_state(printer_id: Any, language: str | None) -> tuple[str, list[list[Any]], list[list[Any]], list[list[Any]]]:
    printer_id = _printer_id_or_error(printer_id, language)
    state = _request("GET", f"/printers/{printer_id}/state", language=language)
    slots = _request("GET", f"/printers/{printer_id}/ams/slots", language=language) or []
    events = _request("GET", "/debug/events?limit=25", language=language) or []
    slot_rows = [
        [
            slot["ams_id"],
            slot["tray_id"],
            slot.get("material"),
            slot.get("series"),
            slot.get("color"),
            slot.get("remain"),
            slot.get("slot_state"),
            _display(language, "identity_source", slot.get("identity_source")),
            slot.get("identity_warning"),
            slot.get("spool_id"),
        ]
        for slot in slots
    ]
    event_rows = [
        [
            item["created_at"],
            item["event_type"],
            _display(language, "severity", item["severity"]),
            item["message"],
        ]
        for item in events
        if item["printer_id"] == printer_id
    ]
    status_rows = []
    if state:
        status_rows = [
            [_text(language, "status_state"), state.get("gcode_state")],
            [_text(language, "status_progress"), state.get("mc_percent")],
            [_text(language, "status_remaining_min"), state.get("mc_remaining_time")],
            [_text(language, "status_task"), state.get("subtask_name") or state.get("gcode_file")],
            [_text(language, "status_error_code"), state.get("error_code")],
        ]
    return _json(state), status_rows, slot_rows, event_rows


def load_dashboard(
    printer_id: Any,
    language: str | None,
) -> tuple[
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    str,
]:
    printer_id = _printer_id_or_error(printer_id, language)
    return _load_dashboard_rows(printer_id, language, wait_seconds=1.0)


def _load_dashboard_rows(
    printer_id: int,
    language: str | None,
    wait_seconds: float,
) -> tuple[
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    str,
]:
    deadline = time.monotonic() + wait_seconds
    dashboard: dict[str, Any] = {}
    while True:
        dashboard = _request("GET", f"/printers/{printer_id}/dashboard", language=language) or {}
        if _dashboard_has_display_data(dashboard) or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    return _dashboard_to_rows(dashboard, language)


def _dashboard_has_display_data(dashboard: dict[str, Any]) -> bool:
    snapshot = dashboard.get("device_snapshot") or {}
    state = dashboard.get("state") or {}
    payload = state.get("payload") if isinstance(state, dict) else None
    print_section = payload.get("print") if isinstance(payload, dict) else None
    return any(
        bool(snapshot.get(key))
        for key in ("temperatures", "fans", "network", "hardware", "derived_status", "camera_options")
    ) or isinstance(print_section, dict)


def _dashboard_to_rows(
    dashboard: dict[str, Any],
    language: str | None,
) -> tuple[
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    list[list[Any]],
    str,
]:
    printer = dashboard.get("printer") or {}
    state = dashboard.get("state") or {}
    snapshot = dashboard.get("device_snapshot") or {}
    snapshot = _snapshot_with_state_fallback(snapshot, state)
    firmware = snapshot.get("firmware") or {}

    overview = [
        [_text(language, "name"), printer.get("name")],
        [_text(language, "host"), printer.get("host")],
        [_text(language, "serial"), printer.get("serial")],
        [_text(language, "status_state"), state.get("gcode_state")],
        [_text(language, "status_progress"), state.get("mc_percent")],
        [_text(language, "status_remaining_min"), state.get("mc_remaining_time")],
        [_text(language, "status_task"), state.get("subtask_name") or state.get("gcode_file")],
        ["Stage", (snapshot.get("print_status") or {}).get("stage_name")],
        ["Plate", (snapshot.get("derived_status") or {}).get("current_plate_id")],
        ["Firmware", firmware.get("printer_version")],
        ["Updated", snapshot.get("updated_at")],
    ]

    derived = _section_rows("derived_status", snapshot.get("derived_status") or {})

    thermal = []
    thermal.extend(_section_rows("temperatures", snapshot.get("temperatures") or {}))
    thermal.extend(_section_rows("fans", snapshot.get("fans") or {}))

    network_hardware = []
    for group in ("network", "hardware", "nozzles", "storage", "lights", "speed", "calibration", "ams_status"):
        network_hardware.extend(_section_rows(group, snapshot.get(group) or {}))

    camera_rows = []
    camera_rows.extend(_section_rows("camera", snapshot.get("camera") or {}))
    camera_rows.extend(_section_rows("camera_options", snapshot.get("camera_options") or {}))

    ams_rows = _dashboard_ams_rows(
        dashboard.get("ams_units") or [],
        dashboard.get("ams_slots") or [],
        snapshot.get("ams_status") or {},
        snapshot.get("external_slots") or [],
    )
    hms_rows = [
        [
            item.get("source"),
            item.get("short_code") or item.get("code"),
            item.get("module_name") or item.get("module"),
            item.get("severity_name") or item.get("severity"),
            item.get("active"),
            item.get("message"),
            item.get("wiki_url"),
        ]
        for item in snapshot.get("hms_errors") or []
    ]
    coverage_rows = _coverage_rows(snapshot.get("data_coverage") or {})
    return overview, derived, thermal, network_hardware, camera_rows, ams_rows, hms_rows, coverage_rows, _json(dashboard)


def _snapshot_with_state_fallback(snapshot: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    merged = dict(snapshot or {})
    payload = state.get("payload") if isinstance(state, dict) else None
    print_section = payload.get("print") if isinstance(payload, dict) else None
    if not isinstance(print_section, dict):
        return merged
    fallback = _snapshot_sections_from_print_payload(print_section, payload)
    for key, value in fallback.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def _snapshot_sections_from_print_payload(print_section: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    temperatures = _compact_dict(
        {
            "bed": _as_float(print_section.get("bed_temper")),
            "bed_target": _as_float(print_section.get("bed_target_temper")),
            "nozzle": _as_float(print_section.get("nozzle_temper")),
            "nozzle_target": _as_float(print_section.get("nozzle_target_temper")),
            "chamber": _as_float(print_section.get("chamber_temper")),
            "chamber_target": _as_float(print_section.get("mc_target_cham")),
        }
    )
    fans = {
        key: {"raw": print_section.get(key), "percent": _fan_percent(print_section.get(key))}
        for key in ("fan_gear", "cooling_fan_speed", "big_fan1_speed", "big_fan2_speed", "heatbreak_fan_speed")
        if key in print_section
    }
    wifi_signal_raw = print_section.get("wifi_signal", payload.get("wifi_signal"))
    wifi_signal = _wifi_signal(wifi_signal_raw)
    network = _compact_dict(
        {
            "wifi_signal": wifi_signal,
            "wifi_signal_raw": wifi_signal_raw,
            "wired_network": wifi_signal == -90 if wifi_signal is not None else None,
        }
    )
    device = print_section.get("device") if isinstance(print_section.get("device"), dict) else {}
    extruder = device.get("extruder") if isinstance(device, dict) else {}
    extruder_info = extruder.get("info") if isinstance(extruder, dict) else None
    hardware = _compact_dict(
        {
            "nozzle_type": print_section.get("nozzle_type"),
            "nozzle_diameter": print_section.get("nozzle_diameter"),
            "upgrade_state": print_section.get("upgrade_state"),
            "extruder_count": len(extruder_info) if isinstance(extruder_info, list) else None,
            "device": device or None,
        }
    )
    derived = _compact_dict(
        {
            "heating_bed": _is_heating(temperatures.get("bed"), temperatures.get("bed_target")),
            "heating_nozzle": _is_heating(temperatures.get("nozzle"), temperatures.get("nozzle_target")),
            "printing": str(print_section.get("gcode_state") or "").upper() == "RUNNING",
            "paused": str(print_section.get("gcode_state") or "").upper() == "PAUSE",
            "current_plate_id": _plate_id(print_section.get("gcode_file")),
        }
    )
    xcam = print_section.get("xcam") if isinstance(print_section.get("xcam"), dict) else {}
    camera = _compact_dict(
        {
            "ipcam": print_section.get("ipcam"),
            "ipcam_record": print_section.get("ipcam_record", xcam.get("ipcam_record")),
            "timelapse": print_section.get("timelapse", xcam.get("timelapse")),
            "cfg": xcam.get("cfg"),
        }
    )
    camera_options = _decode_xcam_cfg(xcam.get("cfg"))
    return {
        "derived_status": derived,
        "temperatures": temperatures,
        "fans": fans,
        "network": network,
        "hardware": hardware,
        "camera": camera,
        "camera_options": camera_options,
    }


def _section_rows(group: str, section: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key, value in section.items():
        if isinstance(value, dict) and key != "device":
            for nested_key, nested_value in value.items():
                rows.append([group, f"{key}.{nested_key}", _format_cell(nested_value)])
        else:
            rows.append([group, key, _format_cell(value)])
    return rows


def _dashboard_ams_rows(
    units: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    ams_status: dict[str, Any],
    external_slots: list[dict[str, Any]],
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key in (
        "ams_status_main_name",
        "ams_status_sub_name",
        "tray_now",
        "tray_tar",
        "ams_rfid_status",
        "ams_exist_bits",
        "tray_exist_bits",
        "mapping",
    ):
        value = ams_status.get(key)
        if value is not None and value != "":
            rows.append(["status", "", "", key, _format_cell(value)])
    for unit in units:
        for key in (
            "serial_number",
            "sw_ver",
            "module_type",
            "ams_type_name",
            "humidity_raw",
            "dry_status",
            "dry_status_name",
            "dry_sub_status_name",
            "dry_sf_reason_names",
            "dry_time",
        ):
            value = unit.get(key)
            if value is not None and value != "":
                rows.append(["unit", unit.get("ams_id"), "", key, _format_cell(value)])
    for slot in slots:
        for key in (
            "tray_id_name",
            "tray_info_idx",
            "nozzle_temp_min",
            "nozzle_temp_max",
            "drying_temp",
            "drying_time",
            "cali_idx",
            "k",
            "state_code",
            "state_name",
            "tray_state_name",
        ):
            value = slot.get(key)
            if value is not None and value != "":
                rows.append(["slot", slot.get("ams_id"), slot.get("tray_id"), key, _format_cell(value)])
    for slot in external_slots:
        tray_id = slot.get("normalized_id") or slot.get("id")
        label = slot.get("tray_type") or slot.get("filament_type") or slot.get("tray_id_name")
        rows.append(["external", slot.get("source"), tray_id, "slot", _format_cell(label or slot)])
    return rows


def _coverage_rows(coverage: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key, value in coverage.items():
        if not isinstance(value, dict):
            continue
        rows.append(
            [
                key,
                value.get("received"),
                value.get("last_updated_at"),
                value.get("raw_message_id"),
            ]
        )
    return rows


def _format_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _json(value)
    return value


def _compact_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


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


def _fan_percent(value: Any) -> int | None:
    speed = _as_int(value)
    if speed is None:
        return None
    if speed <= 15:
        return round(speed * 100 / 15)
    if speed <= 255:
        return round(speed * 100 / 255)
    return speed


def _wifi_signal(value: Any) -> int | None:
    if isinstance(value, str):
        value = value.replace("dBm", "").strip()
    return _as_int(value)


def _is_heating(current: Any, target: Any) -> bool:
    current_float = _as_float(current)
    target_float = _as_float(target)
    return current_float is not None and target_float is not None and target_float > 0 and current_float < target_float - 1.0


def _plate_id(value: Any) -> int | None:
    if value is None:
        return None
    match = PLATE_RE.search(str(value))
    if not match:
        return None
    return _as_int(match.group(1))


def _decode_xcam_cfg(value: Any) -> dict[str, bool]:
    cfg = _as_int(value)
    if cfg is None:
        return {}
    flags = {
        0: "spaghetti_detector",
        1: "pileup_detector",
        2: "nozzle_clumping_detector",
        3: "airprint_detector",
        4: "first_layer_inspector",
        5: "printing_monitor",
        6: "buildplate_marker_detector",
        7: "allow_skip_parts",
    }
    return {name: bool(cfg & (1 << bit)) for bit, name in flags.items()}


def load_metrics(
    printer_id: Any,
    language: str | None,
) -> tuple[list[list[Any]], list[list[Any]], list[list[Any]], list[list[Any]]]:
    printer_id = _printer_id_or_error(printer_id, language)
    samples = _request("GET", f"/printers/{printer_id}/metrics?limit=500", language=language) or []
    temperature_rows: list[list[Any]] = []
    fan_network_rows: list[list[Any]] = []
    ams_rows: list[list[Any]] = []
    progress_rows: list[list[Any]] = []
    for sample in samples:
        row = _metric_row(sample)
        metric = str(sample.get("metric") or "")
        if metric.startswith("temperature."):
            temperature_rows.append(row)
        elif metric.startswith("fan.") or metric.startswith("network."):
            fan_network_rows.append(row)
        elif metric.startswith("ams."):
            ams_rows.append(row)
        elif metric.startswith("print."):
            progress_rows.append(row)
    return temperature_rows, fan_network_rows, ams_rows, progress_rows


def scan_storage_and_load(
    printer_id: Any,
    language: str | None,
) -> tuple[str, list[list[Any]], list[list[Any]]]:
    printer_id = _printer_id_or_error(printer_id, language)
    result = _request("POST", f"/printers/{printer_id}/storage/scan", language=language)
    files = result.get("files") if isinstance(result, dict) else []
    if not files:
        files = _request("GET", f"/printers/{printer_id}/storage/files", language=language) or []
    return _json(result), _storage_file_rows(files), _storage_stats_rows(files)


def load_storage(
    printer_id: Any,
    language: str | None,
) -> tuple[list[list[Any]], list[list[Any]]]:
    printer_id = _printer_id_or_error(printer_id, language)
    files = _request("GET", f"/printers/{printer_id}/storage/files", language=language) or []
    return _storage_file_rows(files), _storage_stats_rows(files)


def _metric_row(sample: dict[str, Any]) -> list[Any]:
    value = sample.get("value_float")
    if value is None:
        value = sample.get("value_text")
    return [
        sample.get("sampled_at"),
        sample.get("metric"),
        value,
        sample.get("unit"),
        _format_cell(sample.get("details") or {}),
    ]


def _storage_file_rows(files: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            item.get("path"),
            item.get("name"),
            item.get("size"),
            item.get("modified_at"),
            item.get("type"),
            item.get("source"),
        ]
        for item in files
    ]


def _storage_stats_rows(files: list[dict[str, Any]]) -> list[list[Any]]:
    total_size = sum(int(item.get("size") or 0) for item in files)
    timelapse_count = sum(1 for item in files if item.get("type") == "timelapse" or "/timelapse/" in str(item.get("path") or ""))
    return [
        ["file_count", len(files)],
        ["total_size_bytes", total_size],
        ["timelapse_count", timelapse_count],
    ]


def create_inventory_spool(
    display_name: str,
    brand: str,
    material: str,
    series: str,
    color: str,
    sealed_quantity: int,
    status: str,
    language: str | None,
) -> tuple[list[list[Any]], str]:
    payload = {
        "display_name": display_name,
        "brand": brand or None,
        "material": material or None,
        "series": series or None,
        "color": color or None,
        "sealed_quantity": int(sealed_quantity),
        "status": status,
    }
    result = _request("POST", "/spools", payload, language=language)
    rows = load_inventory(language)
    return rows, _json(result)


def load_inventory(language: str | None = DEFAULT_LANGUAGE) -> list[list[Any]]:
    spools = _request("GET", "/spools", language=language) or []
    return [
        [
            item["id"],
            item["display_name"],
            item.get("material"),
            item.get("series"),
            item.get("color"),
            _display(language, "spool_status", item["status"]),
            item["sealed_quantity"],
            item.get("current_printer_id"),
            item.get("current_ams_id"),
            item.get("current_tray_id"),
        ]
        for item in spools
    ]


def bind_slot(slot_id: int, spool_id: int, language: str | None) -> str:
    return _json(_request("POST", f"/ams/slots/{int(slot_id)}/bind", {"spool_id": int(spool_id)}, language=language))


def load_debug(language: str | None = DEFAULT_LANGUAGE) -> tuple[str, str, str]:
    return (
        _json(_request("GET", "/debug/raw-mqtt?limit=10", language=language)),
        _json(_request("GET", "/debug/events?limit=50", language=language)),
        _json(_request("GET", "/printers", language=language)),
    )


def language_updates(language: str | None) -> list[Any]:
    return [
        gr.update(value=_text(language, "title_md")),
        gr.update(label=_text(language, "printer")),
        gr.update(value=_text(language, "refresh")),
        gr.update(headers=_text(language, "printer_headers")),
        gr.update(value=_text(language, "scan_devices")),
        gr.update(label=_text(language, "scan_timeout")),
        gr.update(label=_text(language, "validation_timeout")),
        gr.update(headers=_text(language, "discovery_headers"), label=_text(language, "discovery_table")),
        gr.update(label=_text(language, "name")),
        gr.update(label=_text(language, "host")),
        gr.update(label=_text(language, "port")),
        gr.update(label=_text(language, "serial")),
        gr.update(label=_text(language, "access_code")),
        gr.update(label=_text(language, "tls")),
        gr.update(label=_text(language, "certificate_verify")),
        gr.update(value=_text(language, "save")),
        gr.update(value=_text(language, "delete")),
        gr.update(value=_text(language, "connect")),
        gr.update(value=_text(language, "disconnect")),
        gr.update(value=_text(language, "pushall")),
        gr.update(value=_text(language, "full_refresh")),
        gr.update(label=_text(language, "result")),
        gr.update(value=_text(language, "refresh_dashboard")),
        gr.update(headers=_text(language, "dashboard_headers"), label=_text(language, "dashboard_overview")),
        gr.update(headers=_text(language, "dashboard_metric_headers"), label=_text(language, "dashboard_derived")),
        gr.update(headers=_text(language, "dashboard_metric_headers"), label=_text(language, "dashboard_thermal")),
        gr.update(headers=_text(language, "dashboard_metric_headers"), label=_text(language, "dashboard_network_hardware")),
        gr.update(headers=_text(language, "dashboard_camera_headers"), label=_text(language, "dashboard_camera")),
        gr.update(headers=_text(language, "dashboard_ams_headers"), label=_text(language, "dashboard_ams_advanced")),
        gr.update(headers=_text(language, "dashboard_hms_headers"), label=_text(language, "dashboard_hms")),
        gr.update(headers=_text(language, "dashboard_coverage_headers"), label=_text(language, "dashboard_coverage")),
        gr.update(label=_text(language, "dashboard_snapshot")),
        gr.update(value=_text(language, "refresh_metrics")),
        gr.update(headers=_text(language, "metrics_headers"), label=_text(language, "metrics_temperatures")),
        gr.update(headers=_text(language, "metrics_headers"), label=_text(language, "metrics_fans_network")),
        gr.update(headers=_text(language, "metrics_headers"), label=_text(language, "metrics_ams")),
        gr.update(headers=_text(language, "metrics_headers"), label=_text(language, "metrics_progress")),
        gr.update(value=_text(language, "scan_storage")),
        gr.update(value=_text(language, "refresh_storage")),
        gr.update(headers=_text(language, "storage_headers"), label=_text(language, "storage_files")),
        gr.update(headers=_text(language, "dashboard_headers"), label=_text(language, "storage_stats")),
        gr.update(value=_text(language, "refresh_state")),
        gr.update(headers=_text(language, "status_headers"), label=_text(language, "status_table")),
        gr.update(label=_text(language, "state_snapshot")),
        gr.update(headers=_text(language, "event_headers"), label=_text(language, "recent_events")),
        gr.update(value=_text(language, "refresh_slots")),
        gr.update(headers=_text(language, "slot_headers"), label=_text(language, "slot_table")),
        gr.update(value=_text(language, "refresh_inventory")),
        gr.update(headers=_text(language, "inventory_headers"), label=_text(language, "inventory_table")),
        gr.update(label=_text(language, "name")),
        gr.update(label=_text(language, "brand")),
        gr.update(label=_text(language, "material")),
        gr.update(label=_text(language, "series")),
        gr.update(label=_text(language, "color")),
        gr.update(label=_text(language, "sealed_qty")),
        gr.update(label=_text(language, "status"), choices=_status_choices(language), value="sealed"),
        gr.update(value=_text(language, "create_spool")),
        gr.update(label=_text(language, "slot_id")),
        gr.update(label=_text(language, "spool_id")),
        gr.update(value=_text(language, "bind")),
        gr.update(label=_text(language, "inventory_result")),
        gr.update(value=_text(language, "refresh_debug")),
        gr.update(label=_text(language, "raw_mqtt")),
        gr.update(label=_text(language, "events")),
        gr.update(label=_text(language, "printers")),
    ]


with gr.Blocks(title="FilamentManager") as demo:
    language = gr.Dropdown(
        label="界面语言 / UI Language",
        choices=[LANG_ZH, LANG_EN],
        value=DEFAULT_LANGUAGE,
        interactive=True,
    )
    title_md = gr.Markdown(_text(DEFAULT_LANGUAGE, "title_md"))
    printer_choice = gr.Dropdown(label=_text(DEFAULT_LANGUAGE, "printer"), choices=[], interactive=True)

    with gr.Tab("打印机配置 / Printer Config"):
        refresh_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh"))
        printer_table = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "printer_headers"),
            datatype=["number", "str", "str", "number", "str", "str", "str", "str"],
            interactive=False,
        )
        with gr.Row():
            scan_timeout = gr.Number(
                label=_text(DEFAULT_LANGUAGE, "scan_timeout"),
                value=0.25,
                precision=2,
            )
            validation_timeout = gr.Number(
                label=_text(DEFAULT_LANGUAGE, "validation_timeout"),
                value=0.35,
                precision=2,
            )
            scan_button = gr.Button(_text(DEFAULT_LANGUAGE, "scan_devices"))
        discovery_table = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "discovery_headers"),
            label=_text(DEFAULT_LANGUAGE, "discovery_table"),
            interactive=False,
        )
        with gr.Row():
            name = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "name"), value="Printer")
            host = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "host"))
            port = gr.Number(label=_text(DEFAULT_LANGUAGE, "port"), value=8883, precision=0)
            serial = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "serial"))
        with gr.Row():
            access_code = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "access_code"), type="password")
            tls_enabled = gr.Checkbox(label=_text(DEFAULT_LANGUAGE, "tls"), value=True)
            certificate_verify = gr.Checkbox(label=_text(DEFAULT_LANGUAGE, "certificate_verify"), value=False)
        with gr.Row():
            save_button = gr.Button(_text(DEFAULT_LANGUAGE, "save"))
            delete_button = gr.Button(_text(DEFAULT_LANGUAGE, "delete"))
            connect_button = gr.Button(_text(DEFAULT_LANGUAGE, "connect"))
            disconnect_button = gr.Button(_text(DEFAULT_LANGUAGE, "disconnect"))
            pushall_button = gr.Button(_text(DEFAULT_LANGUAGE, "pushall"))
            full_refresh_button = gr.Button(_text(DEFAULT_LANGUAGE, "full_refresh"))
        printer_result = gr.Code(label=_text(DEFAULT_LANGUAGE, "result"), language="json")

    with gr.Tab("设备大屏 / Dashboard"):
        dashboard_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_dashboard"))
        dashboard_overview = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_overview"),
            interactive=False,
        )
        dashboard_derived = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_metric_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_derived"),
            interactive=False,
        )
        dashboard_thermal = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_metric_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_thermal"),
            interactive=False,
        )
        dashboard_network_hardware = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_metric_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_network_hardware"),
            interactive=False,
        )
        dashboard_camera = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_camera_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_camera"),
            interactive=False,
        )
        dashboard_ams = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_ams_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_ams_advanced"),
            interactive=False,
        )
        dashboard_hms = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_hms_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_hms"),
            interactive=False,
        )
        dashboard_coverage = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_coverage_headers"),
            label=_text(DEFAULT_LANGUAGE, "dashboard_coverage"),
            interactive=False,
        )
        dashboard_json = gr.Code(label=_text(DEFAULT_LANGUAGE, "dashboard_snapshot"), language="json")

    with gr.Tab("历史趋势 / Metrics"):
        metrics_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_metrics"))
        metrics_temperatures = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "metrics_headers"),
            label=_text(DEFAULT_LANGUAGE, "metrics_temperatures"),
            interactive=False,
        )
        metrics_fans_network = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "metrics_headers"),
            label=_text(DEFAULT_LANGUAGE, "metrics_fans_network"),
            interactive=False,
        )
        metrics_ams = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "metrics_headers"),
            label=_text(DEFAULT_LANGUAGE, "metrics_ams"),
            interactive=False,
        )
        metrics_progress = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "metrics_headers"),
            label=_text(DEFAULT_LANGUAGE, "metrics_progress"),
            interactive=False,
        )

    with gr.Tab("存储 / Storage"):
        with gr.Row():
            storage_scan_button = gr.Button(_text(DEFAULT_LANGUAGE, "scan_storage"))
            storage_refresh_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_storage"))
        storage_result = gr.Code(label=_text(DEFAULT_LANGUAGE, "result"), language="json")
        storage_table = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "storage_headers"),
            label=_text(DEFAULT_LANGUAGE, "storage_files"),
            interactive=False,
        )
        storage_stats = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "dashboard_headers"),
            label=_text(DEFAULT_LANGUAGE, "storage_stats"),
            interactive=False,
        )

    with gr.Tab("实时状态 / Live State"):
        state_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_state"))
        status_table = gr.Dataframe(headers=_text(DEFAULT_LANGUAGE, "status_headers"), label=_text(DEFAULT_LANGUAGE, "status_table"), interactive=False)
        state_json = gr.Code(label=_text(DEFAULT_LANGUAGE, "state_snapshot"), language="json")
        event_table = gr.Dataframe(headers=_text(DEFAULT_LANGUAGE, "event_headers"), label=_text(DEFAULT_LANGUAGE, "recent_events"), interactive=False)

    with gr.Tab("AMS 槽位 / AMS Slots"):
        slot_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_slots"))
        slot_table = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "slot_headers"),
            label=_text(DEFAULT_LANGUAGE, "slot_table"),
            interactive=False,
        )

    with gr.Tab("库存 / Inventory"):
        inventory_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_inventory"))
        inventory_table = gr.Dataframe(
            headers=_text(DEFAULT_LANGUAGE, "inventory_headers"),
            label=_text(DEFAULT_LANGUAGE, "inventory_table"),
            interactive=False,
        )
        with gr.Row():
            spool_name = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "name"))
            spool_brand = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "brand"))
            spool_material = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "material"))
            spool_series = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "series"))
            spool_color = gr.Textbox(label=_text(DEFAULT_LANGUAGE, "color"))
        with gr.Row():
            spool_quantity = gr.Number(label=_text(DEFAULT_LANGUAGE, "sealed_qty"), value=1, precision=0)
            spool_status = gr.Dropdown(label=_text(DEFAULT_LANGUAGE, "status"), choices=_status_choices(DEFAULT_LANGUAGE), value="sealed")
            create_spool_button = gr.Button(_text(DEFAULT_LANGUAGE, "create_spool"))
        with gr.Row():
            bind_slot_id = gr.Number(label=_text(DEFAULT_LANGUAGE, "slot_id"), precision=0)
            bind_spool_id = gr.Number(label=_text(DEFAULT_LANGUAGE, "spool_id"), precision=0)
            bind_button = gr.Button(_text(DEFAULT_LANGUAGE, "bind"))
        inventory_result = gr.Code(label=_text(DEFAULT_LANGUAGE, "inventory_result"), language="json")

    with gr.Tab("调试 / Debug"):
        debug_button = gr.Button(_text(DEFAULT_LANGUAGE, "refresh_debug"))
        raw_json = gr.Code(label=_text(DEFAULT_LANGUAGE, "raw_mqtt"), language="json")
        events_json = gr.Code(label=_text(DEFAULT_LANGUAGE, "events"), language="json")
        printers_json = gr.Code(label=_text(DEFAULT_LANGUAGE, "printers"), language="json")

    language.change(
        language_updates,
        inputs=[language],
        outputs=[
            title_md,
            printer_choice,
            refresh_button,
            printer_table,
            scan_button,
            scan_timeout,
            validation_timeout,
            discovery_table,
            name,
            host,
            port,
            serial,
            access_code,
            tls_enabled,
            certificate_verify,
            save_button,
            delete_button,
            connect_button,
            disconnect_button,
            pushall_button,
            full_refresh_button,
            printer_result,
            dashboard_button,
            dashboard_overview,
            dashboard_derived,
            dashboard_thermal,
            dashboard_network_hardware,
            dashboard_camera,
            dashboard_ams,
            dashboard_hms,
            dashboard_coverage,
            dashboard_json,
            metrics_button,
            metrics_temperatures,
            metrics_fans_network,
            metrics_ams,
            metrics_progress,
            storage_scan_button,
            storage_refresh_button,
            storage_table,
            storage_stats,
            state_button,
            status_table,
            state_json,
            event_table,
            slot_button,
            slot_table,
            inventory_button,
            inventory_table,
            spool_name,
            spool_brand,
            spool_material,
            spool_series,
            spool_color,
            spool_quantity,
            spool_status,
            create_spool_button,
            bind_slot_id,
            bind_spool_id,
            bind_button,
            inventory_result,
            debug_button,
            raw_json,
            events_json,
            printers_json,
        ],
    )
    refresh_button.click(refresh_printers, inputs=[language], outputs=[printer_table, printer_choice])
    scan_button.click(
        scan_devices,
        inputs=[scan_timeout, validation_timeout, language],
        outputs=[discovery_table, name, host, port, serial, tls_enabled, certificate_verify, printer_result],
    )
    save_button.click(
        save_printer,
        inputs=[name, host, port, serial, access_code, tls_enabled, certificate_verify, language],
        outputs=[printer_table, printer_choice, printer_result],
    )
    delete_button.click(delete_printer, inputs=[printer_choice, language], outputs=[printer_table, printer_choice, printer_result])
    connect_button.click(connect_printer, inputs=[printer_choice, language], outputs=[printer_result])
    disconnect_button.click(disconnect_printer, inputs=[printer_choice, language], outputs=[printer_result])
    pushall_button.click(refresh_pushall, inputs=[printer_choice, language], outputs=[printer_result])
    full_refresh_button.click(
        refresh_full_and_load_dashboard,
        inputs=[printer_choice, language],
        outputs=[
            printer_result,
            dashboard_overview,
            dashboard_derived,
            dashboard_thermal,
            dashboard_network_hardware,
            dashboard_camera,
            dashboard_ams,
            dashboard_hms,
            dashboard_coverage,
            dashboard_json,
        ],
    )
    dashboard_button.click(
        load_dashboard,
        inputs=[printer_choice, language],
        outputs=[
            dashboard_overview,
            dashboard_derived,
            dashboard_thermal,
            dashboard_network_hardware,
            dashboard_camera,
            dashboard_ams,
            dashboard_hms,
            dashboard_coverage,
            dashboard_json,
        ],
    )
    metrics_button.click(
        load_metrics,
        inputs=[printer_choice, language],
        outputs=[metrics_temperatures, metrics_fans_network, metrics_ams, metrics_progress],
    )
    storage_scan_button.click(
        scan_storage_and_load,
        inputs=[printer_choice, language],
        outputs=[storage_result, storage_table, storage_stats],
    )
    storage_refresh_button.click(
        load_storage,
        inputs=[printer_choice, language],
        outputs=[storage_table, storage_stats],
    )
    state_button.click(load_state, inputs=[printer_choice, language], outputs=[state_json, status_table, slot_table, event_table])
    slot_button.click(load_state, inputs=[printer_choice, language], outputs=[state_json, status_table, slot_table, event_table])
    inventory_button.click(load_inventory, inputs=[language], outputs=[inventory_table])
    create_spool_button.click(
        create_inventory_spool,
        inputs=[spool_name, spool_brand, spool_material, spool_series, spool_color, spool_quantity, spool_status, language],
        outputs=[inventory_table, inventory_result],
    )
    bind_button.click(bind_slot, inputs=[bind_slot_id, bind_spool_id, language], outputs=[inventory_result])
    debug_button.click(load_debug, inputs=[language], outputs=[raw_json, events_json, printers_json])
    demo.load(refresh_printers, inputs=[language], outputs=[printer_table, printer_choice])


if __name__ == "__main__":
    demo.launch()
