from __future__ import annotations

import re
from typing import Any


DEFAULT_SERIES_NAME = "Standard"


def normalize_type_series_identity(material_type: Any, series_name: Any) -> tuple[str, str]:
    material = _clean_text(material_type) or "Other"
    series = normalize_series_name(material, series_name)
    return material, series


def normalize_series_name(material_type: Any, series_name: Any) -> str:
    material = _clean_text(material_type)
    series = _clean_text(series_name)
    if series is None:
        return DEFAULT_SERIES_NAME
    for prefix in ("Bambu Lab", "BambuLab", "Bambu"):
        series = _strip_edge_phrase(series, prefix)
    if material:
        previous = None
        while previous != series:
            previous = series
            series = _strip_edge_phrase(series, material)
    series = _normalize_spacing(series)
    return series or DEFAULT_SERIES_NAME


def _strip_edge_phrase(value: str, phrase: str) -> str:
    pattern = _phrase_pattern(phrase)
    if not pattern:
        return value
    text = value.strip()
    text = re.sub(rf"^{pattern}(?:[\s_\-/]+|$)", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(rf"(?:^|[\s_\-/]+){pattern}$", "", text, flags=re.IGNORECASE).strip()
    return text.strip(" -_/")


def _phrase_pattern(value: str) -> str:
    parts = [part for part in re.split(r"[\s_\-]+", value.strip()) if part]
    return r"[\s_\-]*".join(re.escape(part) for part in parts)


def _normalize_spacing(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip(" -_/")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
