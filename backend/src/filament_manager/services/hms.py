from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def hms_code_table() -> dict[str, dict[str, Any]]:
    data = resources.files("filament_manager.data").joinpath("hms_codes.json").read_text(encoding="utf-8")
    rows = json.loads(data)
    table: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("short_code"):
            table[str(row["short_code"]).upper()] = dict(row)
    return table


def list_hms_codes() -> list[dict[str, Any]]:
    return sorted(hms_code_table().values(), key=lambda item: str(item.get("short_code") or ""))


def get_hms_code(short_code: str) -> dict[str, Any] | None:
    return hms_code_table().get(short_code.upper())


def enrich_hms_error(error: dict[str, Any]) -> dict[str, Any]:
    short_code = str(error.get("short_code") or "").upper()
    info = hms_code_table().get(short_code) if short_code else None
    if info:
        error["known"] = bool(info.get("known", True))
        error["actionable"] = bool(info.get("actionable", True))
        error["module_name"] = info.get("module") or error.get("module_name")
        error["message"] = info.get("message_en") or info.get("message_zh") or error.get("message")
        error["message_zh"] = info.get("message_zh")
        error["message_en"] = info.get("message_en")
        error["suggestion_zh"] = info.get("suggestion_zh")
        error["suggestion_en"] = info.get("suggestion_en")
        if info.get("wiki_url"):
            error["wiki_url"] = info["wiki_url"]
        return error

    error["known"] = False
    error["actionable"] = True
    error["message"] = "未知 HMS 码，打印机未必会弹屏提示。"
    error["message_zh"] = "未知 HMS 码，打印机未必会弹屏提示。"
    error["message_en"] = "Unknown HMS code; the printer may not show an on-screen prompt."
    error["suggestion_zh"] = "保留 attr、code 和 source 原始字段，用于后续对照官方 Wiki 或日志排查。"
    error["suggestion_en"] = "Keep raw attr, code, and source fields for later comparison with official wiki or logs."
    return error
