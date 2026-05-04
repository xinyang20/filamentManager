from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "integrations" / "ai" / "skills" / "filament-manager"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFUSAL = "我不能通过 AI 工具修改或导出 FilamentManager 的数据。你可以在前端界面中人工确认该操作；我可以只读查看当前状态并给出操作建议。"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_declares_read_only_mcp_workflow() -> None:
    skill = _read(SKILL_PATH)

    assert "read-only MCP tools" in skill
    assert "You may only diagnose, summarize, explain, and recommend human actions." in skill
    assert "Do not ask the model to construct API URLs or raw requests." in skill

    ordered_tools = [
        "`list_printers`",
        "`get_printer_overview`",
        "`get_ams_overview`",
        "`get_recent_events`",
        "`get_print_log_summary`",
    ]
    positions = [skill.index(tool) for tool in ordered_tools]
    assert positions == sorted(positions)


def test_skill_refuses_write_side_effect_and_export_requests() -> None:
    skill = _read(SKILL_PATH)

    assert REFUSAL in skill
    for verb in (
        "add",
        "edit",
        "delete",
        "archive",
        "bind",
        "confirm",
        "refresh",
        "scan",
        "connect",
        "disconnect",
        "import",
        "export",
        "download",
    ):
        assert verb in skill

    for example in (
        "帮我删除料卷 #19",
        "把这个料卷归档",
        "新增一台打印机",
        "刷新打印机状态",
        "导出数据库",
        "显示打印机 IP / access code / 序列号 / RFID / raw MQTT",
    ):
        assert example in skill


def test_skill_blocks_sensitive_output_categories() -> None:
    skill = _read(SKILL_PATH)

    for sensitive_category in (
        "IP address",
        "host",
        "hostname",
        "port",
        "printer serial number",
        "access code",
        "token",
        "API key",
        "password",
        "authorization header",
        "RFID UID",
        "`tag_uid`",
        "`tray_uuid`",
        "`identity_key`",
        "raw MQTT topic or payload",
        "local path",
        "`gcode_file`",
        "camera stream",
        "storage download URL",
        "notification configuration",
        "database path",
        "export bundle",
    ):
        assert sensitive_category in skill


def test_skill_examples_exist_and_keep_read_only_safety_notes() -> None:
    examples = {
        "printer-diagnosis.md": ("list_printers", "get_printer_overview", "Do not include host, IP, serial"),
        "filament-inventory.md": ("get_filament_inventory_summary", "find_filament_anomalies", "Do not include RFID UID"),
        "print-failure-review.md": ("list_recent_print_logs", "get_hms_code_info", "Do not include `task_id`"),
    }

    for filename, expected_fragments in examples.items():
        text = _read(SKILL_DIR / "examples" / filename)
        for fragment in expected_fragments:
            assert fragment in text
        assert "Do not include" in text
        assert "write payload" in text or "raw payload" in text or "raw refs" in text or "storage paths" in text
