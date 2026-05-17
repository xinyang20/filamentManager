from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.db.models import (
    FilamentBrand,
    FilamentSku,
    FilamentSpool,
    FilamentSpoolEvent,
    FilamentStockBalance,
    FilamentTypeSeries,
)
from filament_manager.services.filament_naming import normalize_type_series_identity

BAMBU_COLOR_SOURCE = "bambu_official"
BAMBU_BRAND_KEYS = {"bambu", "bambulab", "拓竹"}
BAMBU_DEFAULT_BRAND_NAME = "Bambu Lab"
BAMBU_DEFAULT_BRAND_ALIASES = ["Bambu", "拓竹"]
BAMBU_DEFAULT_NOMINAL_WEIGHT_G = 1000.0
BAMBU_DEFAULT_FILAMENT_DIAMETER_MM = 1.75
BAMBU_DEFAULT_EMPTY_SPOOL_WEIGHT_G = 250.0
BAMBU_IGNORED_COLOR_CODE_REPLACEMENTS = {"65100": "65104"}


@dataclass(frozen=True)
class BambuOfficialColor:
    index: int
    color_code: str
    fila_id: str
    fila_type: str
    color_type: str
    color_type_key: str
    names: dict[str, str]
    colors: tuple[str, ...]

    @property
    def primary_color(self) -> str:
        return self.colors[0]

    @property
    def type_key(self) -> str:
        return _key(self.fila_type)

    @property
    def fila_id_key(self) -> str:
        return _key(self.fila_id)

    @property
    def color_set_key(self) -> tuple[str, ...]:
        return _color_set_key(self.colors)

    @property
    def name_keys(self) -> set[str]:
        return {_key(name) for name in self.names.values() if _clean_text(name)}

    def metadata(self, *, ambiguous: bool = False) -> dict[str, Any]:
        return {
            "color_source": BAMBU_COLOR_SOURCE,
            "official_color_code": self.color_code,
            "official_color_type": self.color_type_key,
            "official_color_names": self.names,
            "official_colors": list(self.colors),
            "official_match_ambiguous": ambiguous,
        }


@dataclass(frozen=True)
class BambuOfficialMatch:
    color: BambuOfficialColor
    ambiguous: bool = False

    def metadata(self) -> dict[str, Any]:
        return self.color.metadata(ambiguous=self.ambiguous)


@dataclass
class BambuOfficialSkuCatalogSummary:
    created_brand_count: int = 0
    created_type_series_count: int = 0
    filled_empty_spool_weight_count: int = 0
    created_sku_count: int = 0
    updated_sku_count: int = 0
    merged_duplicate_sku_count: int = 0
    merged_duplicate_groups: list[dict[str, Any]] = field(default_factory=list)
    skipped_ambiguous_groups: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_brand_count": self.created_brand_count,
            "created_type_series_count": self.created_type_series_count,
            "filled_empty_spool_weight_count": self.filled_empty_spool_weight_count,
            "created_sku_count": self.created_sku_count,
            "updated_sku_count": self.updated_sku_count,
            "merged_duplicate_sku_count": self.merged_duplicate_sku_count,
            "merged_duplicate_groups": self.merged_duplicate_groups,
            "skipped_ambiguous_groups": self.skipped_ambiguous_groups,
        }


@dataclass(frozen=True)
class _CatalogIndex:
    rows: tuple[BambuOfficialColor, ...]
    by_color_code: dict[str, BambuOfficialColor]
    by_fila_id: dict[str, tuple[BambuOfficialColor, ...]]
    by_type: dict[str, tuple[BambuOfficialColor, ...]]
    by_fila_id_color_set: dict[tuple[str, tuple[str, ...]], BambuOfficialColor]
    by_type_color_set: dict[tuple[str, tuple[str, ...]], BambuOfficialColor]
    by_type_single_rgb: dict[tuple[str, str], BambuOfficialColor]


def bambu_official_color_count() -> int:
    return len(_catalog().rows)


def bambu_official_type_series_count() -> int:
    return len(_official_type_series_identities())


def is_bambu_brand_name(value: Any) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _brand_key(text) in BAMBU_BRAND_KEYS


def is_bambu_brand(brand_name: Any, aliases: Iterable[Any] | None = None) -> bool:
    if is_bambu_brand_name(brand_name):
        return True
    return any(is_bambu_brand_name(alias) for alias in aliases or [])


def is_known_bambu_fila_id(value: Any) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _key(text) in _catalog().by_fila_id


def official_colors_for_type(*, material: Any = None, series: Any = None) -> list[BambuOfficialColor]:
    rows: dict[str, BambuOfficialColor] = {}
    index = _catalog()
    for type_key in _type_keys(material=material, series=series):
        for row in index.by_type.get(type_key, ()):
            rows[row.color_code] = row
    return sorted(rows.values(), key=lambda row: row.index)


def list_bambu_official_color_mappings() -> list[dict[str, Any]]:
    return [_official_catalog_row(row) for row in _catalog().rows]


def ensure_bambu_official_sku_catalog(db: Session) -> BambuOfficialSkuCatalogSummary:
    summary = BambuOfficialSkuCatalogSummary()
    index = _catalog()
    ambiguous_groups = _ambiguous_catalog_groups(index.rows)
    ignored_groups = _ignored_catalog_groups()
    ambiguous_codes = {
        code
        for group in ambiguous_groups
        for code in group["official_color_codes"]
    }
    summary.skipped_ambiguous_groups = ignored_groups + ambiguous_groups

    brand = _find_or_create_bambu_brand(db, summary)
    type_series_by_identity = _ensure_bambu_type_series(db, brand=brand, summary=summary)

    for row in index.rows:
        if row.color_code in ambiguous_codes:
            continue
        material, series = _split_fila_type(row.fila_type)
        type_series = type_series_by_identity[(material.lower(), series.lower())]
        if _fill_existing_skus_from_official_row(db, type_series=type_series, row=row):
            summary.updated_sku_count += 1
        if _has_official_default_sku(db, type_series=type_series, row=row):
            continue
        db.add(
            FilamentSku(
                type_series_id=type_series.id,
                color_name=_official_color_name(row),
                color_hex=row.primary_color,
                nominal_weight_g=BAMBU_DEFAULT_NOMINAL_WEIGHT_G,
                filament_diameter_mm=BAMBU_DEFAULT_FILAMENT_DIAMETER_MM,
                tray_info_idx=row.fila_id or None,
                note="Auto-created from Bambu official filament catalog.",
            )
        )
        db.flush()
        summary.created_sku_count += 1

    _merge_duplicate_official_skus(db, brand=brand, summary=summary)
    db.commit()
    return summary


def resolve_bambu_official_color(
    *,
    brand_name: Any = None,
    brand_aliases: Iterable[Any] | None = None,
    material: Any = None,
    series: Any = None,
    tray_info_idx: Any = None,
    color_hex: Any = None,
    color_name: Any = None,
    raw: dict[str, Any] | None = None,
    assume_bambu: bool = False,
) -> BambuOfficialMatch | None:
    if not assume_bambu and not is_bambu_brand(brand_name, brand_aliases):
        return None

    raw = raw if isinstance(raw, dict) else {}
    index = _catalog()
    explicit_code = _clean_text(
        raw.get("fila_color_code")
        or raw.get("filament_color_code")
        or raw.get("tray_color_code")
        or raw.get("color_code")
    )
    if explicit_code:
        row = index.by_color_code.get(explicit_code)
        if row is not None and _row_matches_context(row, material=material, series=series, tray_info_idx=tray_info_idx):
            return BambuOfficialMatch(row)

    colors = _raw_color_values(raw, color_hex)
    color_set = _color_set_key(colors)
    name_key = _key(color_name or _raw_color_name(raw))
    if name_key and len(colors) <= 1:
        for row in _context_rows(material=material, series=series, tray_info_idx=tray_info_idx):
            if name_key in row.name_keys:
                return BambuOfficialMatch(row)

    fila_id_key = _key(tray_info_idx)
    if fila_id_key and color_set:
        for row in _context_rows(material=material, series=series, tray_info_idx=tray_info_idx):
            if row.fila_id_key == fila_id_key and row.color_set_key == color_set:
                return BambuOfficialMatch(row)
        row = index.by_fila_id_color_set.get((fila_id_key, color_set))
        if row is not None:
            return BambuOfficialMatch(row)

    for type_key in _type_keys(material=material, series=series):
        if color_set:
            row = index.by_type_color_set.get((type_key, color_set))
            if row is not None:
                return BambuOfficialMatch(row)
        if len(colors) == 1:
            row = index.by_type_single_rgb.get((type_key, colors[0]))
            if row is not None:
                return BambuOfficialMatch(row)

    if name_key:
        for row in _context_rows(material=material, series=series, tray_info_idx=tray_info_idx):
            if name_key in row.name_keys:
                return BambuOfficialMatch(row)

    if not color_set and not name_key and not explicit_code and _clean_text(tray_info_idx):
        rows = _context_rows(material=material, series=series, tray_info_idx=tray_info_idx)
        if rows:
            return BambuOfficialMatch(rows[0], ambiguous=True)

    return None


def official_color_read_fields(match: BambuOfficialMatch) -> dict[str, Any]:
    row = match.color
    return {
        "color_name": row.names.get("zh") or row.names.get("en") or next(iter(row.names.values()), None),
        "color_hex": row.primary_color,
        "color_value": row.primary_color,
        **match.metadata(),
    }


def official_color_effective_mapping(
    row: BambuOfficialColor,
    *,
    brand_id: int,
    brand_name: str | None,
    type_series_id: int,
    material_type: str,
    series_name: str,
) -> dict[str, Any]:
    color_name = row.names.get("zh") or row.names.get("en") or row.primary_color
    return {
        "id": -((type_series_id * 100000) + row.index + 1),
        "brand_id": brand_id,
        "brand_name": brand_name,
        "type_series_id": type_series_id,
        "material_type": material_type,
        "series_name": series_name,
        "material": material_type,
        "series": series_name,
        "color_name": color_name,
        "color_hex": row.primary_color,
        "hex_value": row.primary_color,
        "official_name": color_name,
        "note": None,
        "created_at": None,
        "updated_at": None,
        **row.metadata(),
    }


def _official_catalog_row(row: BambuOfficialColor) -> dict[str, Any]:
    material, series = _split_fila_type(row.fila_type)
    color_name = _official_color_name(row)
    return {
        "id": -(row.index + 1),
        "brand_id": None,
        "brand_name": "Bambu Lab",
        "type_series_id": None,
        "material_type": material,
        "series_name": series,
        "material": material,
        "series": series,
        "tray_info_idx": row.fila_id,
        "color_name": color_name,
        "color_hex": row.primary_color,
        "hex_value": row.primary_color,
        "official_name": color_name,
        "note": None,
        "created_at": None,
        "updated_at": None,
        **row.metadata(),
    }


def _official_type_series_identities() -> tuple[tuple[str, str], ...]:
    identities: dict[tuple[str, str], tuple[str, str]] = {}
    for row in _catalog().rows:
        material, series = _split_fila_type(row.fila_type)
        identities.setdefault((material.lower(), series.lower()), (material, series))
    return tuple(identities.values())


def _find_or_create_bambu_brand(
    db: Session,
    summary: BambuOfficialSkuCatalogSummary,
) -> FilamentBrand:
    brands = list(db.scalars(select(FilamentBrand).order_by(FilamentBrand.id)).all())
    for key in ("bambulab", "bambu", "拓竹"):
        for brand in brands:
            if _brand_key(brand.name) == key:
                return brand
    for brand in brands:
        if is_bambu_brand(brand.name, brand.aliases):
            return brand
    brand = FilamentBrand(
        name=BAMBU_DEFAULT_BRAND_NAME,
        aliases=BAMBU_DEFAULT_BRAND_ALIASES,
        note="Auto-created from Bambu official filament catalog.",
    )
    db.add(brand)
    db.flush()
    summary.created_brand_count += 1
    return brand


def _ensure_bambu_type_series(
    db: Session,
    *,
    brand: FilamentBrand,
    summary: BambuOfficialSkuCatalogSummary,
) -> dict[tuple[str, str], FilamentTypeSeries]:
    result: dict[tuple[str, str], FilamentTypeSeries] = {}
    for material, series in _official_type_series_identities():
        existing = db.scalars(
            select(FilamentTypeSeries).where(
                FilamentTypeSeries.brand_id == brand.id,
                func.lower(FilamentTypeSeries.material_type) == material.lower(),
                func.lower(FilamentTypeSeries.series_name) == series.lower(),
            )
        ).first()
        if existing is None:
            existing = FilamentTypeSeries(
                brand_id=brand.id,
                material_type=material,
                series_name=series,
                empty_spool_weight_g=BAMBU_DEFAULT_EMPTY_SPOOL_WEIGHT_G,
                config={},
                note="Auto-created from Bambu official filament catalog.",
            )
            db.add(existing)
            db.flush()
            summary.created_type_series_count += 1
        elif existing.empty_spool_weight_g is None:
            existing.empty_spool_weight_g = BAMBU_DEFAULT_EMPTY_SPOOL_WEIGHT_G
            db.add(existing)
            summary.filled_empty_spool_weight_count += 1
        result[(material.lower(), series.lower())] = existing
    return result


def _fill_existing_skus_from_official_row(
    db: Session,
    *,
    type_series: FilamentTypeSeries,
    row: BambuOfficialColor,
) -> bool:
    updated = False
    for sku in list(
        db.scalars(select(FilamentSku).where(FilamentSku.type_series_id == type_series.id)).all()
    ):
        if not _sku_matches_official_row(type_series=type_series, sku=sku, row=row):
            continue
        changed = _fill_sku_official_fields(sku, row)
        if changed:
            db.add(sku)
            updated = True
    if updated:
        db.flush()
    return updated


def _has_official_default_sku(
    db: Session,
    *,
    type_series: FilamentTypeSeries,
    row: BambuOfficialColor,
) -> bool:
    skus = list(
        db.scalars(
            select(FilamentSku).where(
                FilamentSku.type_series_id == type_series.id,
                FilamentSku.nominal_weight_g == BAMBU_DEFAULT_NOMINAL_WEIGHT_G,
                FilamentSku.filament_diameter_mm == BAMBU_DEFAULT_FILAMENT_DIAMETER_MM,
            )
        ).all()
    )
    for sku in skus:
        if _sku_matches_official_row(type_series=type_series, sku=sku, row=row):
            return True
    return False


def _sku_matches_official_row(
    type_series: FilamentTypeSeries,
    sku: FilamentSku,
    row: BambuOfficialColor,
) -> bool:
    material, series = _split_fila_type(row.fila_type)
    if (
        type_series.material_type.lower() != material.lower()
        or type_series.series_name.lower() != series.lower()
    ):
        return False

    tray_info_idx = _key(sku.tray_info_idx)
    color_hex = _rgb_hex(sku.color_hex)
    name_key = _key(sku.color_name)
    matched_color_codes: set[str] = set()

    if tray_info_idx:
        if tray_info_idx != row.fila_id_key:
            return False
        match = _single_official_row_matches_field(row, field="tray_info_idx")
        if match is not None:
            matched_color_codes.add(match.color_code)
    if color_hex:
        match = _single_official_row_matches_color(row, color_hex=color_hex)
        if match is not None:
            matched_color_codes.add(match.color_code)
    if name_key:
        match = _single_official_row_matches_name(row, name_key=name_key)
        if match is not None:
            matched_color_codes.add(match.color_code)
    if not matched_color_codes:
        return False
    return matched_color_codes == {row.color_code}


def _single_official_row_matches_field(row: BambuOfficialColor, *, field: str) -> BambuOfficialColor | None:
    matches = []
    for candidate in _catalog().by_type.get(row.type_key, ()):
        if field == "tray_info_idx" and candidate.fila_id_key == row.fila_id_key:
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def _single_official_row_matches_color(
    row: BambuOfficialColor,
    *,
    color_hex: str,
) -> BambuOfficialColor | None:
    matches = [
        candidate
        for candidate in _catalog().by_type.get(row.type_key, ())
        if color_hex in candidate.colors
    ]
    return matches[0] if len(matches) == 1 else None


def _single_official_row_matches_name(
    row: BambuOfficialColor,
    *,
    name_key: str,
) -> BambuOfficialColor | None:
    matches = [
        candidate
        for candidate in _catalog().by_type.get(row.type_key, ())
        if name_key in candidate.name_keys
    ]
    return matches[0] if len(matches) == 1 else None


def _fill_sku_official_fields(sku: FilamentSku, row: BambuOfficialColor) -> bool:
    changed = False
    color_name = _official_color_name(row)
    if color_name and not _clean_text(sku.color_name):
        sku.color_name = color_name
        changed = True
    if row.primary_color and not _clean_text(sku.color_hex):
        sku.color_hex = row.primary_color
        changed = True
    if row.fila_id and not _clean_text(sku.tray_info_idx):
        sku.tray_info_idx = row.fila_id
        changed = True
    return changed


def _merge_duplicate_official_skus(
    db: Session,
    *,
    brand: FilamentBrand,
    summary: BambuOfficialSkuCatalogSummary,
) -> None:
    grouped: dict[tuple[Any, ...], list[tuple[FilamentSku, BambuOfficialColor]]] = {}
    skus = list(
        db.scalars(
            select(FilamentSku)
            .join(FilamentTypeSeries, FilamentSku.type_series_id == FilamentTypeSeries.id)
            .where(FilamentTypeSeries.brand_id == brand.id)
            .order_by(FilamentSku.id)
        ).all()
    )
    for sku in skus:
        type_series = sku.type_series
        if type_series is None:
            continue
        match = resolve_bambu_official_color(
            brand_name=brand.name,
            brand_aliases=brand.aliases,
            material=type_series.material_type,
            series=type_series.series_name,
            tray_info_idx=sku.tray_info_idx,
            color_hex=sku.color_hex,
            color_name=sku.color_name,
        )
        if match is None or match.ambiguous:
            continue
        grouped.setdefault(
            (
                sku.type_series_id,
                match.color.color_code,
                _float_identity(sku.nominal_weight_g),
                _float_identity(sku.filament_diameter_mm or BAMBU_DEFAULT_FILAMENT_DIAMETER_MM),
            ),
            [],
        ).append((sku, match.color))

    for group in grouped.values():
        if len(group) <= 1:
            continue
        canonical, row = _choose_canonical_duplicate_sku(db, group)
        removed_ids: list[int] = []
        for sku, _ in group:
            if sku.id == canonical.id:
                continue
            _merge_duplicate_sku_into(db, source=sku, target=canonical)
            removed_ids.append(sku.id)
        if not removed_ids:
            continue
        _fill_sku_official_fields(canonical, row)
        db.add(canonical)
        db.flush()
        summary.merged_duplicate_sku_count += len(removed_ids)
        material, series = _split_fila_type(row.fila_type)
        summary.merged_duplicate_groups.append(
            {
                "canonical_sku_id": canonical.id,
                "removed_sku_ids": removed_ids,
                "official_color_code": row.color_code,
                "material_type": material,
                "series_name": series,
                "color_name": _official_color_name(row),
                "color_hex": row.primary_color,
                "tray_info_idx": row.fila_id,
                "nominal_weight_g": canonical.nominal_weight_g,
                "filament_diameter_mm": canonical.filament_diameter_mm,
            }
        )


def _choose_canonical_duplicate_sku(
    db: Session,
    group: list[tuple[FilamentSku, BambuOfficialColor]],
) -> tuple[FilamentSku, BambuOfficialColor]:
    return max(group, key=lambda item: _duplicate_sku_keep_score(db, sku=item[0], row=item[1]))


def _duplicate_sku_keep_score(db: Session, *, sku: FilamentSku, row: BambuOfficialColor) -> tuple[Any, ...]:
    spool_count = _sku_spool_count(db, sku.id)
    event_count = _sku_event_count(db, sku.id)
    sealed_quantity = _sku_sealed_quantity(db, sku.id)
    business_score = (spool_count * 1000) + (sealed_quantity * 100) + event_count
    official_field_score = (
        int(_key(sku.tray_info_idx) == row.fila_id_key)
        + int(_rgb_hex(sku.color_hex) == row.primary_color)
        + int(_key(sku.color_name) in row.name_keys)
    )
    is_official_auto = (sku.note or "").strip() == "Auto-created from Bambu official filament catalog."
    if business_score:
        return (1, business_score, int(not is_official_auto), official_field_score, -sku.id)
    return (0, official_field_score, int(is_official_auto), -sku.id)


def _merge_duplicate_sku_into(db: Session, *, source: FilamentSku, target: FilamentSku) -> None:
    source_balance = db.get(FilamentStockBalance, source.id)
    target_balance = db.get(FilamentStockBalance, target.id)
    if source_balance is not None:
        if target_balance is None:
            target_balance = FilamentStockBalance(sku_id=target.id, sealed_quantity=0)
        target_balance.sealed_quantity = int(target_balance.sealed_quantity or 0) + int(source_balance.sealed_quantity or 0)
        db.add(target_balance)
        db.delete(source_balance)
        db.flush()

    for spool in db.scalars(select(FilamentSpool).where(FilamentSpool.sku_id == source.id)).all():
        spool.sku_id = target.id
        db.add(spool)
    for event in db.scalars(select(FilamentSpoolEvent).where(FilamentSpoolEvent.sku_id == source.id)).all():
        event.sku_id = target.id
        db.add(event)
    db.flush()
    db.delete(source)
    db.flush()


def _sku_sealed_quantity(db: Session, sku_id: int) -> int:
    balance = db.get(FilamentStockBalance, sku_id)
    return int(balance.sealed_quantity or 0) if balance is not None else 0


def _sku_spool_count(db: Session, sku_id: int) -> int:
    return int(db.scalar(select(func.count(FilamentSpool.id)).where(FilamentSpool.sku_id == sku_id)) or 0)


def _sku_event_count(db: Session, sku_id: int) -> int:
    return int(db.scalar(select(func.count(FilamentSpoolEvent.id)).where(FilamentSpoolEvent.sku_id == sku_id)) or 0)


def _float_identity(value: Any) -> float:
    return round(float(value or 0), 3)


def _ambiguous_catalog_groups(rows: Iterable[BambuOfficialColor]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[BambuOfficialColor]] = {}
    for row in rows:
        grouped.setdefault(_official_sku_identity(row), []).append(row)
    skipped: list[dict[str, Any]] = []
    for group_rows in grouped.values():
        if len(group_rows) <= 1:
            continue
        first = group_rows[0]
        material, series = _split_fila_type(first.fila_type)
        skipped.append(
            {
                "official_color_codes": [row.color_code for row in group_rows],
                "reason": "duplicate_official_sku_identity",
                "brand_name": BAMBU_DEFAULT_BRAND_NAME,
                "material_type": material,
                "series_name": series,
                "tray_info_idx": first.fila_id,
                "color_name": _official_color_name(first),
                "color_hex": first.primary_color,
                "nominal_weight_g": BAMBU_DEFAULT_NOMINAL_WEIGHT_G,
                "filament_diameter_mm": BAMBU_DEFAULT_FILAMENT_DIAMETER_MM,
            }
        )
    return skipped


def _ignored_catalog_groups() -> list[dict[str, Any]]:
    rows_by_code = _raw_catalog_rows_by_code()
    skipped: list[dict[str, Any]] = []
    for ignored_code, selected_code in BAMBU_IGNORED_COLOR_CODE_REPLACEMENTS.items():
        ignored = rows_by_code.get(ignored_code)
        selected = rows_by_code.get(selected_code)
        if ignored is None:
            continue
        material, series = _split_fila_type(ignored.fila_type)
        skipped.append(
            {
                "official_color_codes": [ignored_code],
                "selected_official_color_code": selected_code,
                "reason": "ignored_in_favor_of_selected_official_color_code",
                "brand_name": BAMBU_DEFAULT_BRAND_NAME,
                "material_type": material,
                "series_name": series,
                "tray_info_idx": ignored.fila_id,
                "color_name": _official_color_name(selected or ignored),
                "color_hex": (selected or ignored).primary_color,
                "nominal_weight_g": BAMBU_DEFAULT_NOMINAL_WEIGHT_G,
                "filament_diameter_mm": BAMBU_DEFAULT_FILAMENT_DIAMETER_MM,
            }
        )
    return skipped


@lru_cache(maxsize=1)
def _raw_catalog_rows_by_code() -> dict[str, BambuOfficialColor]:
    data = resources.files("filament_manager.data").joinpath("filaments_color_codes.json").read_text(encoding="utf-8")
    payload = json.loads(data)
    rows: dict[str, BambuOfficialColor] = {}
    for index, item in enumerate(payload.get("data") or []):
        colors = tuple(color for color in (_rgb_hex(value) for value in item.get("fila_color") or []) if color)
        color_code = str(item.get("fila_color_code") or "").strip()
        if not color_code or not colors:
            continue
        rows[color_code] = BambuOfficialColor(
            index=index,
            color_code=color_code,
            fila_id=str(item.get("fila_id") or "").strip(),
            fila_type=str(item.get("fila_type") or "").strip(),
            color_type=str(item.get("fila_color_type") or "").strip(),
            color_type_key=_color_type_key(item.get("fila_color_type")),
            names={str(key): str(value) for key, value in (item.get("fila_color_name") or {}).items() if _clean_text(value)},
            colors=colors,
        )
    return rows


def _official_sku_identity(row: BambuOfficialColor) -> tuple[Any, ...]:
    material, series = _split_fila_type(row.fila_type)
    return (
        material.lower(),
        series.lower(),
        _key(_official_color_name(row)),
        row.primary_color,
        row.fila_id_key,
        BAMBU_DEFAULT_NOMINAL_WEIGHT_G,
        BAMBU_DEFAULT_FILAMENT_DIAMETER_MM,
    )


def _official_color_name(row: BambuOfficialColor) -> str:
    return row.names.get("zh") or row.names.get("en") or row.primary_color


def _split_fila_type(value: str) -> tuple[str, str]:
    text = _clean_text(value) or ""
    if text.startswith("Support "):
        return normalize_type_series_identity("Support", text.removeprefix("Support ").strip() or text)
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        return normalize_type_series_identity(parts[0], parts[1])
    if "-" in text:
        material, series = text.split("-", maxsplit=1)
        return normalize_type_series_identity(material, series)
    return normalize_type_series_identity(text, text)


def _context_rows(*, material: Any = None, series: Any = None, tray_info_idx: Any = None) -> list[BambuOfficialColor]:
    index = _catalog()
    rows: dict[str, BambuOfficialColor] = {}
    fila_id_key = _key(tray_info_idx)
    type_keys = _type_keys(material=material, series=series)
    if fila_id_key and type_keys:
        for type_key in type_keys:
            for row in index.by_type.get(type_key, ()):
                if row.fila_id_key == fila_id_key:
                    rows[row.color_code] = row
        if rows:
            return sorted(rows.values(), key=lambda row: row.index)
    if fila_id_key:
        for row in index.by_fila_id.get(fila_id_key, ()):
            rows[row.color_code] = row
        return sorted(rows.values(), key=lambda row: row.index)
    for type_key in type_keys:
        for row in index.by_type.get(type_key, ()):
            rows[row.color_code] = row
    return sorted(rows.values(), key=lambda row: row.index)


def _row_matches_context(
    row: BambuOfficialColor,
    *,
    material: Any = None,
    series: Any = None,
    tray_info_idx: Any = None,
) -> bool:
    fila_id_key = _key(tray_info_idx)
    if fila_id_key and row.fila_id_key == fila_id_key:
        return True
    type_keys = _type_keys(material=material, series=series)
    if not fila_id_key and not type_keys:
        return True
    return bool(type_keys and row.type_key in type_keys)


@lru_cache(maxsize=1)
def _catalog() -> _CatalogIndex:
    data = resources.files("filament_manager.data").joinpath("filaments_color_codes.json").read_text(encoding="utf-8")
    payload = json.loads(data)
    rows: list[BambuOfficialColor] = []
    for index, item in enumerate(payload.get("data") or []):
        color_code = str(item.get("fila_color_code") or "").strip()
        if color_code in BAMBU_IGNORED_COLOR_CODE_REPLACEMENTS:
            continue
        colors = tuple(color for color in (_rgb_hex(value) for value in item.get("fila_color") or []) if color)
        if not colors:
            continue
        rows.append(
            BambuOfficialColor(
                index=index,
                color_code=color_code,
                fila_id=str(item.get("fila_id") or "").strip(),
                fila_type=str(item.get("fila_type") or "").strip(),
                color_type=str(item.get("fila_color_type") or "").strip(),
                color_type_key=_color_type_key(item.get("fila_color_type")),
                names={str(key): str(value) for key, value in (item.get("fila_color_name") or {}).items() if _clean_text(value)},
                colors=colors,
            )
        )

    by_color_code = {row.color_code: row for row in rows if row.color_code}
    by_fila_id = _group(rows, lambda row: row.fila_id_key)
    by_type = _group(rows, lambda row: row.type_key)
    by_fila_id_color_set: dict[tuple[str, tuple[str, ...]], BambuOfficialColor] = {}
    by_type_color_set: dict[tuple[str, tuple[str, ...]], BambuOfficialColor] = {}
    by_type_single_rgb: dict[tuple[str, str], BambuOfficialColor] = {}
    for row in rows:
        by_fila_id_color_set.setdefault((row.fila_id_key, row.color_set_key), row)
        by_type_color_set.setdefault((row.type_key, row.color_set_key), row)
        if len(row.colors) == 1 and row.color_type_key == "single":
            by_type_single_rgb.setdefault((row.type_key, row.primary_color), row)
    return _CatalogIndex(
        rows=tuple(rows),
        by_color_code=by_color_code,
        by_fila_id=by_fila_id,
        by_type=by_type,
        by_fila_id_color_set=by_fila_id_color_set,
        by_type_color_set=by_type_color_set,
        by_type_single_rgb=by_type_single_rgb,
    )


def _group(rows: list[BambuOfficialColor], key_fn: Any) -> dict[str, tuple[BambuOfficialColor, ...]]:
    grouped: dict[str, list[BambuOfficialColor]] = {}
    for row in rows:
        key = key_fn(row)
        if key:
            grouped.setdefault(key, []).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _raw_color_values(raw: dict[str, Any], color_hex: Any = None) -> tuple[str, ...]:
    cols = raw.get("cols")
    if isinstance(cols, list):
        colors = tuple(color for color in (_rgb_hex(value) for value in cols) if color)
        if colors:
            return colors
    for value in (raw.get("tray_color"), raw.get("color"), color_hex):
        color = _rgb_hex(value)
        if color:
            return (color,)
    return ()


def _raw_color_name(raw: dict[str, Any]) -> str | None:
    return _clean_text(
        raw.get("tray_color_name")
        or raw.get("color_name")
        or raw.get("filament_color_name")
        or raw.get("color_display_name")
    )


def _type_keys(*, material: Any = None, series: Any = None) -> tuple[str, ...]:
    material_text = _clean_text(material)
    series_text = _clean_text(series)
    candidates: list[str] = []
    if series_text:
        candidates.append(series_text)
    if material_text and series_text:
        candidates.append(f"{material_text} {series_text}")
    if material_text:
        candidates.append(material_text)
    seen: set[str] = set()
    keys: list[str] = []
    for candidate in candidates:
        key = _key(candidate)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def _color_set_key(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted(color for color in (_rgb_hex(value) for value in values) if color))


def _rgb_hex(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    compact = text.removeprefix("#").replace(" ", "").replace("_", "").replace("-", "").upper()
    if len(compact) == 8:
        compact = compact[:6]
    if len(compact) != 6 or any(char not in "0123456789ABCDEF" for char in compact):
        return None
    return compact


def _color_type_key(value: Any) -> str:
    text = _clean_text(value) or ""
    if text == "多拼色":
        return "multi"
    if text == "渐变色":
        return "gradient"
    return "single"


def _brand_key(value: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "").strip().lower())


def _key(value: Any) -> str:
    text = _clean_text(value)
    if text is None:
        return ""
    return re.sub(r"[\s_\-]+", " ", text).strip().lower()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
