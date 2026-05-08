from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from filament_manager.db.models import (
    FilamentBrand,
    FilamentColorMapping,
    FilamentSku,
    FilamentSpool,
    FilamentStockBalance,
    FilamentTypeSeries,
)
from filament_manager.services.inventory_constants import HISTORICAL_SPOOL_STATUSES


def filament_brand_to_read(db: Session, brand: FilamentBrand) -> dict[str, Any]:
    type_series_ids = [
        row[0]
        for row in db.execute(
            select(FilamentTypeSeries.id).where(FilamentTypeSeries.brand_id == brand.id)
        ).all()
    ]
    sku_count = 0
    spool_count = 0
    if type_series_ids:
        sku_ids = {
            row[0]
            for row in db.execute(
                select(FilamentSku.id).where(FilamentSku.type_series_id.in_(type_series_ids))
            ).all()
        }
        sku_count = len(sku_ids)
        if sku_ids:
            spool_count = int(
                db.scalar(select(func.count(FilamentSpool.id)).where(FilamentSpool.sku_id.in_(sku_ids))) or 0
            )
    return {
        "id": brand.id,
        "name": brand.name,
        "aliases": brand.aliases or [],
        "note": brand.note,
        "type_series_count": len(type_series_ids),
        "sku_count": sku_count,
        "spool_count": spool_count,
        "created_at": brand.created_at,
        "updated_at": brand.updated_at,
    }


def filament_type_series_to_read(db: Session, type_series: FilamentTypeSeries) -> dict[str, Any]:
    brand = type_series.brand
    brands = [brand_summary(brand)] if brand else []
    sku_ids = [
        row[0]
        for row in db.execute(
            select(FilamentSku.id).where(FilamentSku.type_series_id == type_series.id)
        ).all()
    ]
    spool_count = 0
    if sku_ids:
        spool_count = int(db.scalar(select(func.count(FilamentSpool.id)).where(FilamentSpool.sku_id.in_(sku_ids))) or 0)
    return {
        "id": type_series.id,
        "material_type": type_series.material_type,
        "series_name": type_series.series_name,
        "empty_spool_weight_g": type_series.empty_spool_weight_g,
        "config": type_series.config or {},
        "note": type_series.note,
        "brand_id": type_series.brand_id,
        "brand_name": brand.name if brand else None,
        "brand_ids": [brand["id"] for brand in brands],
        "brands": brands,
        "sku_count": len(set(sku_ids)),
        "spool_count": spool_count,
        "created_at": type_series.created_at,
        "updated_at": type_series.updated_at,
    }


def filament_sku_to_read(sku: FilamentSku) -> dict[str, Any]:
    first_series = sku.type_series
    first_brand = first_series.brand if first_series else None
    type_series = [type_series_summary(first_series)] if first_series else []
    return {
        "id": sku.id,
        "type_series_id": sku.type_series_id,
        "brand_id": first_brand.id if first_brand else None,
        "brand_name": first_brand.name if first_brand else None,
        "material": first_series.material_type if first_series else None,
        "series": first_series.series_name if first_series else None,
        "color_name": sku.color_name,
        "color_hex": sku.color_hex,
        "color_value": sku.color_hex,
        "nominal_weight_g": sku.nominal_weight_g,
        "empty_spool_weight_g": first_series.empty_spool_weight_g if first_series else None,
        "filament_diameter_mm": sku.filament_diameter_mm or 1.75,
        "density_g_cm3": None,
        "tray_info_idx": sku.tray_info_idx,
        "sealed_quantity": sealed_quantity(sku),
        "note": sku.note,
        "type_series_ids": [sku.type_series_id] if sku.type_series_id else [],
        "type_series": type_series,
        "brands": sku_brand_summaries(sku),
        "opened_spool_count": sum(1 for spool in sku.spools if spool.status == "opened_in_storage"),
        "ams_spool_count": sum(
            1
            for spool in sku.spools
            if spool.status not in HISTORICAL_SPOOL_STATUSES and (spool.status == "loaded_in_ams" or spool.current_ams_id)
        ),
        "created_at": sku.created_at,
        "updated_at": sku.updated_at,
    }


def filament_spool_to_read(spool: FilamentSpool) -> dict[str, Any]:
    sku = spool.sku
    first_series = sku.type_series if sku else None
    first_brand = first_series.brand if first_series else None
    config = spool.config or {}
    last_ams_remain_percent = 0 if spool.status == "empty" and spool.actual_weight_g == 0 else config.get("last_ams_remain_percent")
    return {
        "id": spool.id,
        "sku_id": spool.sku_id,
        "legacy_spool_id": None,
        "sku_label": sku_label(sku),
        "brand_id": first_brand.id if first_brand else None,
        "brand_name": first_brand.name if first_brand else None,
        "material": first_series.material_type if first_series else None,
        "series": first_series.series_name if first_series else None,
        "type_series": [type_series_summary(first_series)] if first_series else [],
        "brands": sku_brand_summaries(sku) if sku else [],
        "color_name": sku.color_name if sku else None,
        "color_hex": sku.color_hex if sku else None,
        "color_value": sku.color_hex if sku else None,
        "official_spool_uid": spool.official_spool_uid,
        "identity_key": spool.official_spool_uid,
        "tray_uuid": spool.official_spool_uid,
        "tag_uid": None,
        "identity_source": spool.identity_source,
        "nominal_weight_g": spool.nominal_weight_g,
        "actual_weight_g": spool.actual_weight_g,
        "initial_net_weight_g": spool.nominal_weight_g,
        "current_remaining_g": spool.actual_weight_g,
        "used_weight_g": max(0.0, (spool.nominal_weight_g or 0) - spool.actual_weight_g) if spool.actual_weight_g is not None else 0.0,
        "empty_spool_weight_g": first_series.empty_spool_weight_g if first_series else None,
        "status": spool.status,
        "opened_at": spool.opened_at,
        "first_loaded_at": spool.opened_at,
        "last_used_at": None,
        "current_printer_id": spool.current_printer_id,
        "current_ams_id": spool.current_ams_id,
        "current_tray_id": spool.current_tray_id,
        "storage_location": spool.storage_location,
        "manual_location": spool.storage_location,
        "last_location": config.get("last_location"),
        "status_changed_at": datetime_from_config(config.get("status_changed_at")),
        "empty_at": datetime_from_config(config.get("empty_at")),
        "archived_at": datetime_from_config(config.get("archived_at")),
        "manual_quantity_protected": False,
        "last_weighed_g": spool.actual_weight_g,
        "last_ams_remain_percent": last_ams_remain_percent,
        "note": spool.note,
        "config": config,
        "created_at": spool.created_at,
        "updated_at": spool.updated_at,
    }


def filament_color_mapping_to_read(mapping: FilamentColorMapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "brand_id": mapping.brand_id,
        "brand_name": mapping.brand.name if mapping.brand else None,
        "type_series_id": mapping.type_series_id,
        "material_type": mapping.type_series.material_type if mapping.type_series else None,
        "series_name": mapping.type_series.series_name if mapping.type_series else None,
        "material": mapping.type_series.material_type if mapping.type_series else None,
        "series": mapping.type_series.series_name if mapping.type_series else None,
        "color_name": mapping.color_name,
        "color_hex": mapping.color_hex,
        "hex_value": mapping.color_hex,
        "official_name": mapping.color_name,
        "note": mapping.note,
        "created_at": mapping.created_at,
        "updated_at": mapping.updated_at,
    }


def brand_summary(brand: FilamentBrand) -> dict[str, Any]:
    return {"id": brand.id, "name": brand.name, "aliases": brand.aliases or []}


def type_series_summary(type_series: FilamentTypeSeries) -> dict[str, Any]:
    brand = type_series.brand
    return {
        "id": type_series.id,
        "brand_id": type_series.brand_id,
        "brand_name": brand.name if brand else None,
        "material_type": type_series.material_type,
        "series_name": type_series.series_name,
        "empty_spool_weight_g": type_series.empty_spool_weight_g,
        "brand_ids": [type_series.brand_id] if type_series.brand_id else [],
        "brands": [brand_summary(brand)] if brand else [],
    }


def sku_brand_summaries(sku: FilamentSku | None) -> list[dict[str, Any]]:
    if sku is None or sku.type_series is None or sku.type_series.brand is None:
        return []
    return [brand_summary(sku.type_series.brand)]


def sku_label(sku: FilamentSku | None) -> str | None:
    if sku is None:
        return None
    series = [series_label(sku.type_series)] if sku.type_series else []
    color = sku.color_name or sku.color_hex
    parts = [", ".join(series), color]
    return " / ".join(part for part in parts if part) or f"SKU {sku.id}"


def series_label(type_series: FilamentTypeSeries) -> str:
    return f"{type_series.material_type} {type_series.series_name}".strip()


def sealed_quantity(sku: FilamentSku) -> int:
    if sku.stock_balance is not None:
        return int(sku.stock_balance.sealed_quantity)
    session = object_session(sku)
    if session is None:
        return 0
    balance = session.get(FilamentStockBalance, sku.id)
    return int(balance.sealed_quantity) if balance is not None else 0


def datetime_from_config(value: Any) -> Any:
    return value
