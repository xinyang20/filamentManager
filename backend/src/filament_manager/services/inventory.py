from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.db.models import (
    AmsSlot,
    FilamentBrand,
    FilamentColorMapping,
    FilamentSku,
    FilamentSpool,
    FilamentSpoolEvent,
    FilamentStockBalance,
    FilamentTypeSeries,
    utc_now,
)
from filament_manager.mqtt.parser import (
    ParsedAmsSlot,
    has_stable_tray_filament_payload,
    is_placeholder_ams_color_frame,
    is_transition_state_without_payload,
    is_valid_identity_value,
)
from filament_manager.services.bambu_filament_catalog import (
    BambuOfficialMatch,
    official_color_effective_mapping,
    official_colors_for_type,
    resolve_bambu_official_color,
    is_bambu_brand,
)
from filament_manager.services.filament_naming import normalize_type_series_identity
from filament_manager.services.inventory_constants import (
    HISTORICAL_SPOOL_STATUSES,
    MATERIAL_TYPES,
    REAL_SPOOL_STATUSES,
)
from filament_manager.services.inventory_serializers import (
    brand_summary as _brand_summary,
    filament_brand_to_read,
    filament_color_mapping_to_read,
    filament_sku_to_read,
    filament_spool_to_read,
    filament_type_series_to_read,
    sealed_quantity as _sealed_quantity,
    sku_brand_summaries as _sku_brand_summaries,
    sku_label as _sku_label,
    type_series_summary as _type_series_summary,
)
from filament_manager.schemas import (
    FilamentBrandCreate,
    FilamentBrandUpdate,
    FilamentColorMappingCreate,
    FilamentColorMappingUpdate,
    FilamentSkuCreate,
    FilamentSkuStockAdjust,
    FilamentSkuTypeSeriesSet,
    FilamentSkuUpdate,
    FilamentSpoolCreate,
    FilamentSpoolLocationUpdate,
    FilamentSpoolUpdate,
    FilamentSpoolWeightUpdate,
    FilamentTypeSeriesBrandSet,
    FilamentTypeSeriesCreate,
    FilamentTypeSeriesUpdate,
)


class DuplicateFilamentSkuError(ValueError):
    def __init__(self, existing_sku: FilamentSku):
        self.existing_sku = existing_sku
        super().__init__("Duplicate filament SKU")


class FilamentSpoolUidConflictError(ValueError):
    pass


class StaleFilamentSpoolUpdateError(ValueError):
    pass


def list_brands(db: Session) -> list[FilamentBrand]:
    return list(db.scalars(select(FilamentBrand).order_by(func.lower(FilamentBrand.name), FilamentBrand.id)).all())


def get_brand(db: Session, brand_id: int) -> FilamentBrand | None:
    return db.get(FilamentBrand, brand_id)


def create_brand(db: Session, data: FilamentBrandCreate) -> FilamentBrand:
    brand = FilamentBrand(
        name=_required_text(data.name, "Brand name"),
        aliases=_clean_aliases(data.aliases),
        note=data.note,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def update_brand(db: Session, brand: FilamentBrand, data: FilamentBrandUpdate) -> FilamentBrand:
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        brand.name = _required_text(updates["name"], "Brand name")
    if "aliases" in updates and updates["aliases"] is not None:
        brand.aliases = _clean_aliases(updates["aliases"])
    if "note" in updates:
        brand.note = updates["note"]
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def delete_brand(db: Session, brand: FilamentBrand) -> None:
    referenced = db.scalars(select(FilamentTypeSeries.id).where(FilamentTypeSeries.brand_id == brand.id).limit(1)).first()
    if referenced is not None:
        raise ValueError("Brand is still associated with filament type series")
    mapping = db.scalars(select(FilamentColorMapping.id).where(FilamentColorMapping.brand_id == brand.id).limit(1)).first()
    if mapping is not None:
        raise ValueError("Brand is still referenced by color mappings")
    db.delete(brand)
    db.commit()


def list_type_series(db: Session) -> list[FilamentTypeSeries]:
    return list(
        db.scalars(
            select(FilamentTypeSeries).order_by(
                func.lower(FilamentTypeSeries.material_type),
                func.lower(FilamentTypeSeries.series_name),
                FilamentTypeSeries.id,
            )
        ).all()
    )


def get_type_series(db: Session, type_series_id: int) -> FilamentTypeSeries | None:
    return db.get(FilamentTypeSeries, type_series_id)


def type_series_exists(
    db: Session,
    *,
    brand_id: int,
    material_type: str,
    series_name: str,
    exclude_id: int | None = None,
) -> bool:
    material_type, series_name = normalize_type_series_identity(material_type, series_name)
    stmt = select(FilamentTypeSeries.id).where(
        FilamentTypeSeries.brand_id == brand_id,
        func.lower(FilamentTypeSeries.material_type) == material_type.lower(),
        func.lower(FilamentTypeSeries.series_name) == series_name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(FilamentTypeSeries.id != exclude_id)
    return db.scalars(stmt.limit(1)).first() is not None


def create_type_series(db: Session, data: FilamentTypeSeriesCreate) -> FilamentTypeSeries:
    payload = _type_series_payload(data.model_dump())
    if get_brand(db, payload["brand_id"]) is None:
        raise ValueError("Brand not found")
    if type_series_exists(
        db,
        brand_id=payload["brand_id"],
        material_type=payload["material_type"],
        series_name=payload["series_name"],
    ):
        raise ValueError("Type series already exists for this brand")
    type_series = FilamentTypeSeries(**payload)
    db.add(type_series)
    db.commit()
    db.refresh(type_series)
    return type_series


def update_type_series(
    db: Session,
    type_series: FilamentTypeSeries,
    data: FilamentTypeSeriesUpdate,
) -> FilamentTypeSeries:
    updates = _type_series_payload(data.model_dump(exclude_unset=True), partial=True)
    if "brand_id" in updates and get_brand(db, updates["brand_id"]) is None:
        raise ValueError("Brand not found")
    next_brand_id = updates.get("brand_id", type_series.brand_id)
    next_material_type = updates.get("material_type", type_series.material_type)
    next_series_name = updates.get("series_name", type_series.series_name)
    next_material_type, next_series_name = normalize_type_series_identity(next_material_type, next_series_name)
    updates["material_type"] = next_material_type
    updates["series_name"] = next_series_name
    if type_series_exists(
        db,
        brand_id=next_brand_id,
        material_type=next_material_type,
        series_name=next_series_name,
        exclude_id=type_series.id,
    ):
        raise ValueError("Type series already exists for this brand")
    for key, value in updates.items():
        setattr(type_series, key, value)
    db.add(type_series)
    db.commit()
    db.refresh(type_series)
    return type_series


def delete_type_series(db: Session, type_series: FilamentTypeSeries) -> None:
    sku_link = db.scalars(select(FilamentSku.id).where(FilamentSku.type_series_id == type_series.id).limit(1)).first()
    if sku_link is not None:
        raise ValueError("Type series is still associated with SKUs")
    spool_link = db.scalars(
        select(FilamentSpool.id)
        .join(FilamentSku, FilamentSpool.sku_id == FilamentSku.id)
        .where(FilamentSku.type_series_id == type_series.id)
        .limit(1)
    ).first()
    if spool_link is not None:
        raise ValueError("Type series is still referenced by filament spools")
    db.delete(type_series)
    db.commit()


def set_type_series_brands(
    db: Session,
    type_series: FilamentTypeSeries,
    data: FilamentTypeSeriesBrandSet,
) -> FilamentTypeSeries:
    brand_id = data.brand_id or (data.brand_ids[0] if data.brand_ids else None)
    if brand_id is None:
        raise ValueError("Brand is required")
    if get_brand(db, brand_id) is None:
        raise ValueError("Brand not found")
    type_series.brand_id = brand_id
    db.add(type_series)
    db.commit()
    db.refresh(type_series)
    return type_series


def list_skus(db: Session) -> list[FilamentSku]:
    return list(db.scalars(select(FilamentSku).order_by(FilamentSku.id.desc())).all())


def get_sku(db: Session, sku_id: int) -> FilamentSku | None:
    return db.get(FilamentSku, sku_id)


def create_sku(db: Session, data: FilamentSkuCreate) -> FilamentSku:
    payload = _sku_payload(data.model_dump())
    if get_type_series(db, payload["type_series_id"]) is None:
        raise ValueError("Type series not found")
    _complete_sku_payload_from_color_mapping(db, payload)
    duplicate = _find_duplicate_sku(db, payload)
    if duplicate is not None:
        raise DuplicateFilamentSkuError(duplicate)
    sku = FilamentSku(**payload)
    db.add(sku)
    db.flush()
    _apply_color_mappings_to_sku_gaps(db)
    _ensure_color_mapping_from_sku(db, sku)
    if data.sealed_quantity > 0:
        balance = _stock_balance(db, sku, create=True)
        balance.sealed_quantity = data.sealed_quantity
        db.add(balance)
        _record_event(
            db,
            sku_id=sku.id,
            event_type="sealed_stock_adjusted",
            quantity_delta=data.sealed_quantity,
            message="Initial sealed stock set",
            current={"sealed_quantity": data.sealed_quantity},
        )
    db.commit()
    db.refresh(sku)
    return sku


def update_sku(db: Session, sku: FilamentSku, data: FilamentSkuUpdate) -> FilamentSku:
    updates = _sku_payload(data.model_dump(exclude_unset=True), partial=True)
    if "type_series_id" in updates and get_type_series(db, updates["type_series_id"]) is None:
        raise ValueError("Type series not found")
    next_payload = _sku_identity_payload(sku, updates)
    _complete_sku_payload_from_color_mapping(db, next_payload)
    duplicate = _find_duplicate_sku(db, next_payload, exclude_id=sku.id)
    if duplicate is not None:
        raise DuplicateFilamentSkuError(duplicate)
    for key in ("color_name", "color_hex"):
        if key in next_payload and key not in updates:
            updates[key] = next_payload[key]
    for key, value in updates.items():
        setattr(sku, key, value)
    db.add(sku)
    _apply_color_mappings_to_sku_gaps(db)
    _ensure_color_mapping_from_sku(db, sku)
    db.commit()
    db.refresh(sku)
    return sku


def set_sku_type_series(
    db: Session,
    sku: FilamentSku,
    data: FilamentSkuTypeSeriesSet,
) -> FilamentSku:
    type_series_id = data.type_series_id or (data.type_series_ids[0] if data.type_series_ids else None)
    if type_series_id is None:
        raise ValueError("Type series is required")
    if get_type_series(db, type_series_id) is None:
        raise ValueError("Type series not found")
    next_payload = _sku_identity_payload(sku, {"type_series_id": type_series_id})
    _complete_sku_payload_from_color_mapping(db, next_payload)
    duplicate = _find_duplicate_sku(db, next_payload, exclude_id=sku.id)
    if duplicate is not None:
        raise DuplicateFilamentSkuError(duplicate)
    sku.type_series_id = type_series_id
    for key in ("color_name", "color_hex"):
        setattr(sku, key, next_payload[key])
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


def delete_sku(db: Session, sku: FilamentSku, *, force: bool = False) -> None:
    referenced = db.scalars(select(FilamentSpool.id).where(FilamentSpool.sku_id == sku.id).limit(1)).first()
    if referenced is not None:
        raise ValueError("SKU is still referenced by filament spools")
    sealed_quantity = _sealed_quantity(sku)
    if sealed_quantity > 0:
        if not force:
            raise ValueError("SKU still has sealed stock balance")
        balance = _stock_balance(db, sku, create=False)
        if balance is not None:
            balance.sealed_quantity = 0
            db.add(balance)
    db.delete(sku)
    db.commit()


def adjust_sku_stock(db: Session, sku: FilamentSku, data: FilamentSkuStockAdjust) -> FilamentSku:
    balance = _stock_balance(db, sku, create=True)
    previous = balance.sealed_quantity
    next_quantity = previous + data.delta
    if next_quantity < 0:
        raise ValueError("Sealed stock cannot become negative")
    balance.sealed_quantity = next_quantity
    db.add(balance)
    _record_event(
        db,
        sku_id=sku.id,
        event_type="sealed_stock_adjusted",
        quantity_delta=data.delta,
        message="Sealed stock adjusted",
        previous={"sealed_quantity": previous},
        current={"sealed_quantity": next_quantity},
        note=data.reason,
    )
    db.commit()
    db.refresh(sku)
    return sku


def list_filament_spools(db: Session) -> list[FilamentSpool]:
    return [
        spool
        for spool in db.scalars(select(FilamentSpool).order_by(FilamentSpool.id.desc())).all()
        if not _is_phantom_ams_spool(spool)
    ]


def get_filament_spool(db: Session, spool_id: int) -> FilamentSpool | None:
    spool = db.get(FilamentSpool, spool_id)
    if spool is not None and _is_phantom_ams_spool(spool):
        return None
    return spool


def create_filament_spool(db: Session, data: FilamentSpoolCreate) -> FilamentSpool:
    sku = _sku_or_none(db, data.sku_id)
    uid = _official_uid_or_none(data.official_spool_uid)
    if uid is not None and _find_spool_by_official_uid(db, uid) is not None:
        raise ValueError("Official spool UID already exists")
    spool = FilamentSpool(
        sku_id=sku.id if sku else None,
        official_spool_uid=uid,
        identity_source=data.identity_source,
        nominal_weight_g=data.nominal_weight_g if data.nominal_weight_g is not None else (sku.nominal_weight_g if sku else None),
        actual_weight_g=data.actual_weight_g,
        status=data.status,
        opened_at=data.opened_at or (utc_now() if data.status in {"opened_in_storage", "loaded_in_ams"} else None),
        current_printer_id=data.current_printer_id,
        current_ams_id=data.current_ams_id,
        current_tray_id=data.current_tray_id,
        storage_location=data.storage_location,
        note=data.note,
        config=data.config,
    )
    db.add(spool)
    db.flush()
    if sku is not None and spool.status in {"opened_in_storage", "loaded_in_ams"}:
        _open_one_from_stock_if_available(db, sku, spool=spool, note="Manual spool created")
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="opened_from_stock" if spool.status in {"opened_in_storage", "loaded_in_ams"} else "location_updated",
        message="Filament spool created",
        current=_spool_snapshot(spool),
    )
    if spool.status == "loaded_in_ams":
        _record_event(
            db,
            spool=spool,
            sku_id=spool.sku_id,
            event_type="loaded_to_ams",
            message="Spool loaded to AMS",
            current=_location_snapshot(spool),
        )
    db.commit()
    db.refresh(spool)
    return spool


def update_filament_spool(db: Session, spool: FilamentSpool, data: FilamentSpoolUpdate) -> FilamentSpool:
    updates = data.model_dump(exclude_unset=True)
    if "sku_id" in updates:
        _sku_or_none(db, updates["sku_id"])
    if "official_spool_uid" in updates:
        uid = _official_uid_or_none(updates["official_spool_uid"])
        existing = _find_spool_by_official_uid(db, uid) if uid else None
        if existing is not None and existing.id != spool.id:
            raise ValueError("Official spool UID already exists")
        updates["official_spool_uid"] = uid
    status_update = updates.pop("status", None)
    previous = _spool_snapshot(spool)
    for key, value in updates.items():
        setattr(spool, key, value)
    if status_update is not None:
        _apply_filament_status_change(db, spool, status=status_update)
    if spool.status in {"opened_in_storage", "loaded_in_ams"} and spool.opened_at is None:
        spool.opened_at = utc_now()
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type=f"status_{status_update}" if status_update is not None else "weight_updated" if "actual_weight_g" in updates else "location_updated",
        message="Filament spool updated",
        previous=previous,
        current=_spool_snapshot(spool),
    )
    db.commit()
    db.refresh(spool)
    return spool


def confirm_filament_spool_sku_review(db: Session, spool: FilamentSpool) -> FilamentSpool:
    previous_config = dict(spool.config or {})
    config = dict(previous_config)
    config.pop("needs_sku_review", None)
    config["sku_review_confirmed_at"] = utc_now().isoformat()
    spool.config = config
    if spool.status == "unknown" and spool.sku_id is not None:
        spool.status = "loaded_in_ams" if spool.current_ams_id is not None else "opened_in_storage"
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="sku_confirmed",
        message="Filament spool SKU confirmed",
        previous={"config": previous_config},
        current={"config": config},
    )
    db.commit()
    db.refresh(spool)
    return spool


def delete_filament_spool(db: Session, spool: FilamentSpool) -> None:
    has_events = db.scalars(select(FilamentSpoolEvent.id).where(FilamentSpoolEvent.spool_id == spool.id).limit(1)).first()
    if has_events is not None and spool.status != "archived":
        raise ValueError("Archive spool before deleting history-bearing spool")
    db.delete(spool)
    db.commit()


def _assert_spool_update_is_current(
    db: Session,
    spool: FilamentSpool,
    expected_updated_at: datetime | None,
) -> None:
    if expected_updated_at is None:
        return
    db.refresh(spool)
    current = _datetime_to_utc(spool.updated_at)
    expected = _datetime_to_utc(expected_updated_at)
    if current != expected:
        raise StaleFilamentSpoolUpdateError("Filament spool was updated by another request; refresh and try again")


def _datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def update_filament_location(
    db: Session,
    spool: FilamentSpool,
    data: FilamentSpoolLocationUpdate,
) -> FilamentSpool:
    _assert_spool_update_is_current(db, spool, data.expected_updated_at)
    previous = _location_snapshot(spool)
    spool.current_printer_id = data.printer_id
    spool.current_ams_id = data.ams_id
    spool.current_tray_id = data.tray_id
    spool.storage_location = data.storage_location
    if data.printer_id and data.ams_id and data.tray_id:
        spool.status = "loaded_in_ams"
        if spool.opened_at is None:
            spool.opened_at = utc_now()
    elif data.storage_location:
        spool.status = "opened_in_storage" if spool.status != "empty" else spool.status
    elif spool.status == "loaded_in_ams":
        spool.status = "needs_location"
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="location_updated",
        message="Filament spool location updated",
        previous=previous,
        current=_location_snapshot(spool),
        note=data.note,
    )
    db.commit()
    db.refresh(spool)
    return spool


def update_filament_weight(
    db: Session,
    spool: FilamentSpool,
    data: FilamentSpoolWeightUpdate,
) -> FilamentSpool:
    _assert_spool_update_is_current(db, spool, data.expected_updated_at)
    previous = _spool_snapshot(spool)
    if data.actual_weight_g == 0:
        if spool.status not in HISTORICAL_SPOOL_STATUSES:
            _apply_filament_status_change(db, spool, status="empty")
            event_type = "status_empty"
            message = "Filament spool marked empty after weight update"
        else:
            spool.actual_weight_g = 0
            config = dict(spool.config or {})
            config["last_ams_remain_percent"] = 0
            spool.config = config
            event_type = "weight_updated"
            message = "Filament spool weight updated"
    else:
        spool.actual_weight_g = data.actual_weight_g
        event_type = "weight_updated"
        message = "Filament spool weight updated"
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type=event_type,
        message=message,
        previous=previous,
        current=_spool_snapshot(spool),
        note=data.note,
    )
    db.commit()
    db.refresh(spool)
    return spool


def update_filament_status(
    db: Session,
    spool: FilamentSpool,
    *,
    status: str,
    note: str | None = None,
    expected_updated_at: datetime | None = None,
) -> FilamentSpool:
    if status not in REAL_SPOOL_STATUSES:
        raise ValueError("Unsupported filament spool status")
    _assert_spool_update_is_current(db, spool, expected_updated_at)
    previous = _spool_snapshot(spool)
    _apply_filament_status_change(db, spool, status=status)
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type=f"status_{status}",
        message="Filament spool status changed",
        previous=previous,
        current=_spool_snapshot(spool),
        note=note,
    )
    db.commit()
    db.refresh(spool)
    return spool


def resolve_reappeared_uid_conflict(
    db: Session,
    conflict_spool: FilamentSpool,
    *,
    action: str,
    note: str | None = None,
) -> FilamentSpool | None:
    config = dict(conflict_spool.config or {})
    if config.get("review_reason") != "archived_uid_reappeared":
        raise FilamentSpoolUidConflictError("Filament spool is not an archived UID conflict")
    uid = _official_uid_or_none(config.get("reappeared_official_spool_uid"))
    archived_spool_id = _positive_int_or_none(config.get("archived_spool_id"))
    archived_spool = db.get(FilamentSpool, archived_spool_id) if archived_spool_id is not None else None
    if archived_spool is None and uid is not None:
        archived_spool = _find_spool_by_official_uid(db, uid)
    if uid is None or archived_spool is None:
        raise FilamentSpoolUidConflictError("Original archived spool was not found")

    if action == "restore_old":
        previous_conflict = _spool_snapshot(conflict_spool)
        previous_archived = _spool_snapshot(archived_spool)
        archived_spool.status = "loaded_in_ams"
        archived_spool.current_printer_id = conflict_spool.current_printer_id
        archived_spool.current_ams_id = conflict_spool.current_ams_id
        archived_spool.current_tray_id = conflict_spool.current_tray_id
        archived_spool.storage_location = None
        archived_spool.opened_at = archived_spool.opened_at or utc_now()
        archived_config = dict(archived_spool.config or {})
        archived_config.pop("archived_at", None)
        archived_config.pop("empty_at", None)
        archived_config["status_changed_at"] = utc_now().isoformat()
        archived_config["uid_conflict_resolved_at"] = utc_now().isoformat()
        archived_config["uid_conflict_resolution"] = action
        archived_spool.config = archived_config
        _bind_location_slots_to_spool(db, conflict_spool, archived_spool.id)
        _apply_filament_status_change(db, conflict_spool, status="archived")
        conflict_config = dict(conflict_spool.config or {})
        conflict_config["uid_conflict_resolution"] = action
        conflict_config["uid_conflict_resolved_at"] = utc_now().isoformat()
        conflict_spool.config = conflict_config
        db.add(archived_spool)
        db.add(conflict_spool)
        _record_event(
            db,
            spool=archived_spool,
            sku_id=archived_spool.sku_id,
            event_type="uid_conflict_restored",
            message="Archived UID conflict resolved by restoring historical spool",
            previous=previous_archived,
            current=_spool_snapshot(archived_spool),
            note=note,
            data={"conflict_spool_id": conflict_spool.id, "official_spool_uid": uid},
        )
        _record_event(
            db,
            spool=conflict_spool,
            sku_id=conflict_spool.sku_id,
            event_type="uid_conflict_resolved",
            message="UID conflict placeholder archived after restoring historical spool",
            previous=previous_conflict,
            current=_spool_snapshot(conflict_spool),
            note=note,
            data={"restored_spool_id": archived_spool.id, "official_spool_uid": uid},
        )
        db.commit()
        db.refresh(archived_spool)
        return archived_spool

    if action == "create_new":
        previous_conflict = _spool_snapshot(conflict_spool)
        previous_archived = _spool_snapshot(archived_spool)
        archived_config = dict(archived_spool.config or {})
        archived_config["archived_official_spool_uid"] = uid
        archived_config["uid_reassigned_to_spool_id"] = conflict_spool.id
        archived_config["uid_conflict_resolution"] = action
        archived_config["uid_conflict_resolved_at"] = utc_now().isoformat()
        archived_spool.official_spool_uid = None
        archived_spool.config = archived_config
        if conflict_spool.sku_id is None:
            conflict_spool.sku_id = archived_spool.sku_id
            conflict_spool.nominal_weight_g = conflict_spool.nominal_weight_g or archived_spool.nominal_weight_g
        conflict_spool.official_spool_uid = uid
        conflict_spool.status = "loaded_in_ams" if conflict_spool.sku_id is not None else "unknown"
        conflict_spool.opened_at = conflict_spool.opened_at or utc_now()
        config.pop("needs_sku_review", None)
        config["uid_conflict_resolution"] = action
        config["uid_conflict_resolved_at"] = utc_now().isoformat()
        config["status_changed_at"] = utc_now().isoformat()
        conflict_spool.config = config
        db.add(archived_spool)
        db.add(conflict_spool)
        _record_event(
            db,
            spool=archived_spool,
            sku_id=archived_spool.sku_id,
            event_type="uid_conflict_reassigned",
            message="Archived UID released for a newly created spool",
            previous=previous_archived,
            current=_spool_snapshot(archived_spool),
            note=note,
            data={"new_spool_id": conflict_spool.id, "official_spool_uid": uid},
        )
        _record_event(
            db,
            spool=conflict_spool,
            sku_id=conflict_spool.sku_id,
            event_type="uid_conflict_resolved",
            message="UID conflict resolved by creating a new spool",
            previous=previous_conflict,
            current=_spool_snapshot(conflict_spool),
            note=note,
            data={"archived_spool_id": archived_spool.id, "official_spool_uid": uid},
        )
        db.commit()
        db.refresh(conflict_spool)
        return conflict_spool

    if action == "ignore":
        previous = _spool_snapshot(conflict_spool)
        _clear_slot_bindings_for_spool(db, conflict_spool)
        _apply_filament_status_change(db, conflict_spool, status="archived")
        config["uid_conflict_resolution"] = action
        config["uid_conflict_resolved_at"] = utc_now().isoformat()
        conflict_spool.config = config
        db.add(conflict_spool)
        _record_event(
            db,
            spool=conflict_spool,
            sku_id=conflict_spool.sku_id,
            event_type="uid_conflict_ignored",
            message="UID conflict observation ignored",
            previous=previous,
            current=_spool_snapshot(conflict_spool),
            note=note,
            data={"archived_spool_id": archived_spool.id, "official_spool_uid": uid},
        )
        db.commit()
        db.refresh(conflict_spool)
        return conflict_spool

    raise FilamentSpoolUidConflictError("Unsupported UID conflict action")


def list_filament_spool_events(db: Session, spool_id: int) -> dict[str, list[Any]]:
    return {
        "events": list(
            db.scalars(
                select(FilamentSpoolEvent)
                .where(FilamentSpoolEvent.spool_id == spool_id)
                .order_by(FilamentSpoolEvent.id.desc())
            ).all()
        )
    }


def list_color_mappings(db: Session) -> list[FilamentColorMapping]:
    if _ensure_color_mappings_from_skus(db):
        db.commit()
    return list(
        db.scalars(
            select(FilamentColorMapping)
            .join(FilamentBrand, FilamentColorMapping.brand_id == FilamentBrand.id)
            .join(FilamentTypeSeries, FilamentColorMapping.type_series_id == FilamentTypeSeries.id)
            .order_by(
                func.lower(FilamentBrand.name),
                func.lower(FilamentTypeSeries.material_type),
                func.lower(FilamentTypeSeries.series_name),
                func.lower(FilamentColorMapping.color_name),
            )
        ).all()
    )


def list_effective_color_mappings(db: Session) -> list[dict[str, Any]]:
    if _ensure_color_mappings_from_skus(db):
        db.commit()
    rows: list[dict[str, Any]] = []
    mappings_by_type_series: dict[int, list[FilamentColorMapping]] = {}
    for mapping in db.scalars(select(FilamentColorMapping)).all():
        mappings_by_type_series.setdefault(mapping.type_series_id, []).append(mapping)

    for type_series in list_type_series(db):
        brand = type_series.brand
        manual_mappings = sorted(
            mappings_by_type_series.get(type_series.id, []),
            key=lambda mapping: ((mapping.color_name or "").lower(), mapping.color_hex, mapping.id),
        )
        if brand is not None and is_bambu_brand(brand.name, brand.aliases):
            official_rows = official_colors_for_type(
                material=type_series.material_type,
                series=type_series.series_name,
            )
            if official_rows:
                rows.extend(
                    official_color_effective_mapping(
                        row,
                        brand_id=brand.id,
                        brand_name=brand.name,
                        type_series_id=type_series.id,
                        material_type=type_series.material_type,
                        series_name=type_series.series_name,
                    )
                    for row in official_rows
                )
                rows.extend(
                    filament_color_mapping_to_read(mapping)
                    for mapping in manual_mappings
                    if _official_match_for_color_mapping(mapping) is None
                )
                continue
        rows.extend(filament_color_mapping_to_read(mapping) for mapping in manual_mappings)
    return rows


def get_color_mapping(db: Session, mapping_id: int) -> FilamentColorMapping | None:
    return db.get(FilamentColorMapping, mapping_id)


def create_color_mapping(db: Session, data: FilamentColorMappingCreate) -> FilamentColorMapping:
    payload = _color_mapping_payload(db, data.model_dump())
    existing = _find_color_mapping(
        db,
        brand_id=payload["brand_id"],
        type_series_id=payload["type_series_id"],
        color_name=payload["color_name"],
        color_hex=payload["color_hex"],
    )
    if existing is not None:
        raise ValueError("Color mapping already exists")
    mapping = FilamentColorMapping(**payload)
    db.add(mapping)
    _apply_color_mapping_to_sku_gaps(db, **payload)
    db.commit()
    db.refresh(mapping)
    return mapping


def update_color_mapping(
    db: Session,
    mapping: FilamentColorMapping,
    data: FilamentColorMappingUpdate,
) -> FilamentColorMapping:
    previous = {
        "brand_id": mapping.brand_id,
        "type_series_id": mapping.type_series_id,
        "color_name": mapping.color_name,
        "color_hex": mapping.color_hex,
    }
    updates = data.model_dump(exclude_unset=True)
    if updates.get("brand_id") is None:
        updates.pop("brand_id", None)
    if updates.get("type_series_id") is None:
        updates.pop("type_series_id", None)
    payload = _color_mapping_payload(
        db,
        {
            "brand_id": updates.get("brand_id", mapping.brand_id),
            "type_series_id": updates.get("type_series_id", mapping.type_series_id),
            "color_name": updates.get("color_name", mapping.color_name),
            "color_hex": updates.get("color_hex", mapping.color_hex),
            "note": updates.get("note", mapping.note),
        },
    )
    existing = _find_color_mapping(
        db,
        brand_id=payload["brand_id"],
        type_series_id=payload["type_series_id"],
        color_name=payload["color_name"],
        color_hex=payload["color_hex"],
    )
    if existing is not None and existing.id != mapping.id:
        raise ValueError("Color mapping already exists")
    for key, value in payload.items():
        setattr(mapping, key, value)
    db.add(mapping)
    _apply_color_mapping_update_to_skus(db, previous=previous, current=payload)
    _apply_color_mapping_to_sku_gaps(db, **payload)
    db.commit()
    db.refresh(mapping)
    return mapping


def delete_color_mapping(db: Session, mapping: FilamentColorMapping) -> None:
    db.delete(mapping)
    db.commit()


def list_color_mapping_gaps(db: Session) -> list[dict[str, Any]]:
    if _ensure_color_mappings_from_skus(db):
        db.commit()
    if _apply_color_mappings_to_sku_gaps(db):
        db.commit()
    gaps: list[dict[str, Any]] = []
    for sku in list_skus(db):
        if _official_match_for_sku(sku) is not None:
            continue
        missing: list[str] = []
        if not _clean_text(sku.color_name):
            missing.append("color_name")
        if not _clean_text(sku.color_hex):
            missing.append("color_hex")
        if not missing:
            continue
        gaps.append(
            {
                "sku_id": sku.id,
                "color_name": sku.color_name,
                "color_hex": sku.color_hex,
                "missing": missing,
                "type_series": [_type_series_summary(sku.type_series)] if sku.type_series else [],
                "brands": _sku_brand_summaries(sku),
            }
        )
    return gaps


def build_inventory_summary(db: Session) -> dict[str, Any]:
    skus = [filament_sku_to_read(sku) for sku in list_skus(db)]
    spools = [filament_spool_to_read(spool) for spool in list_filament_spools(db)]
    sealed_stock = [sku for sku in skus if int(sku["sealed_quantity"]) > 0]
    current_spools = [spool for spool in spools if spool["status"] not in HISTORICAL_SPOOL_STATUSES]
    opened_spools = [spool for spool in current_spools if spool["status"] == "opened_in_storage"]
    ams_spools = [spool for spool in current_spools if spool["current_ams_id"] or spool["status"] == "loaded_in_ams"]
    needs_location = [spool for spool in current_spools if spool["status"] == "needs_location"]
    empty_spools = [spool for spool in spools if spool["status"] == "empty"]
    archived_spools = [spool for spool in spools if spool["status"] == "archived"]
    return {
        "totals": {
            "sku_count": len(skus),
            "sealed_quantity": sum(int(sku["sealed_quantity"]) for sku in skus),
            "opened_spool_count": len(opened_spools),
            "ams_spool_count": len(ams_spools),
            "needs_location_count": len(needs_location),
            "empty_spool_count": len(empty_spools),
            "archived_spool_count": len(archived_spools),
        },
        "skus": skus,
        "sealed_stock": sealed_stock,
        "opened_spools": opened_spools,
        "ams_spools": ams_spools,
        "needs_location_spools": needs_location,
        "empty_spools": empty_spools,
        "archived_spools": archived_spools,
        "history_spools": empty_spools + archived_spools,
    }


def bind_slot_to_filament_spool(db: Session, slot: AmsSlot, spool: FilamentSpool) -> AmsSlot:
    previous = _location_snapshot(spool)
    sku = spool.sku
    if sku is not None and spool.status == "sealed_stock_virtual":
        _open_one_from_stock_if_available(db, sku, spool=spool, note="Spool bound to AMS slot")
    spool.status = "loaded_in_ams"
    spool.opened_at = spool.opened_at or utc_now()
    spool.current_printer_id = slot.printer_id
    spool.current_ams_id = slot.ams_id
    spool.current_tray_id = slot.tray_id
    spool.storage_location = None
    slot.filament_spool_id = spool.id
    db.add(slot)
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="loaded_to_ams",
        message="Spool bound to AMS slot",
        previous=previous,
        current=_location_snapshot(spool),
    )
    db.commit()
    db.refresh(slot)
    return slot


def record_print_filament_context(
    db: Session,
    *,
    printer_id: int,
    task_id: str | None,
    gcode_file: str | None,
    event_type: str,
) -> None:
    return None


def process_ams_slot_filament(
    db: Session,
    *,
    printer_id: int,
    slot_model: AmsSlot,
    parsed_slot: ParsedAmsSlot,
) -> tuple[FilamentSpool | None, bool]:
    previous_spool_id = slot_model.filament_spool_id
    official_uid = _official_uid_from_slot(parsed_slot)
    if parsed_slot.is_transitioning:
        if official_uid:
            return _find_spool_by_official_uid(db, official_uid), False
        return (db.get(FilamentSpool, previous_spool_id), False) if previous_spool_id else (None, False)
    if official_uid is None:
        if _slot_is_empty_observation(parsed_slot):
            if previous_spool_id is not None:
                _record_ams_slot_unload(
                    db,
                    slot=slot_model,
                    previous_spool_id=previous_spool_id,
                    note="AMS slot reports empty",
                )
            slot_model.filament_spool_id = None
            db.add(slot_model)
            return None, False
        if _slot_is_transition_without_payload(parsed_slot):
            return (db.get(FilamentSpool, previous_spool_id), False) if previous_spool_id else (None, False)
        if previous_spool_id is not None:
            previous = db.get(FilamentSpool, previous_spool_id)
            if previous is not None and previous.official_spool_uid is None:
                if previous.sku_id is None and _slot_has_filament_payload(parsed_slot):
                    matched, auto_created_sku = _resolve_sku_for_ams_slot(db, parsed_slot)
                    if matched is not None:
                        previous.sku_id = matched.id
                        previous.nominal_weight_g = previous.nominal_weight_g or matched.nominal_weight_g
                        _fill_sku_color_from_slot(db, matched, parsed_slot)
                        _ensure_color_mapping_from_sku(db, matched)
                        if not auto_created_sku:
                            _open_one_from_stock_if_available(
                                db,
                                matched,
                                spool=previous,
                                note="AMS spool identified without official UID",
                            )
                        if auto_created_sku:
                            config = dict(previous.config or {})
                            config["needs_sku_review"] = True
                            config["auto_created_sku_id"] = matched.id
                            previous.config = config
                _set_filament_loaded_location(db, previous, printer_id=printer_id, parsed_slot=parsed_slot)
                _sync_ams_context(previous, parsed_slot)
                db.add(slot_model)
                db.add(previous)
                return previous, False
            _record_ams_slot_unload(
                db,
                slot=slot_model,
                previous_spool_id=previous_spool_id,
                note="AMS slot no longer reports an official spool UID",
            )
        sku, auto_created_sku = _resolve_sku_for_ams_slot(db, parsed_slot)
        spool = _create_unknown_ams_spool(
            db,
            printer_id=printer_id,
            parsed_slot=parsed_slot,
            sku=sku,
            auto_created_sku=auto_created_sku,
            identity_source="manual",
            review_reason="ams_filament_change" if previous_spool_id is not None and auto_created_sku else None,
        )
        if sku is not None and not auto_created_sku:
            _open_one_from_stock_if_available(db, sku, spool=spool, note="AMS spool identified without official UID")
            _fill_sku_color_from_slot(db, sku, parsed_slot)
            _ensure_color_mapping_from_sku(db, sku)
        _set_filament_loaded_location(db, spool, printer_id=printer_id, parsed_slot=parsed_slot)
        _sync_ams_context(spool, parsed_slot)
        slot_model.filament_spool_id = spool.id
        db.add(slot_model)
        db.add(spool)
        return spool, True

    spool = _find_spool_by_official_uid(db, official_uid)
    if spool is not None and spool.status in HISTORICAL_SPOOL_STATUSES:
        return _handle_historical_uid_reappeared(
            db,
            printer_id=printer_id,
            slot_model=slot_model,
            parsed_slot=parsed_slot,
            historical_spool=spool,
            previous_spool_id=previous_spool_id,
        )
    created = spool is None
    if spool is None:
        placeholder = _official_uid_placeholder_candidate(db, previous_spool_id)
        if placeholder is not None:
            sku, auto_created_sku = _resolve_sku_for_ams_slot(db, parsed_slot)
            spool = placeholder
            created = False
            _complete_placeholder_from_official_slot(
                db,
                spool=spool,
                official_uid=official_uid,
                parsed_slot=parsed_slot,
                sku=sku,
                auto_created_sku=auto_created_sku,
            )
        else:
            sku, auto_created_sku = _resolve_sku_for_ams_slot(db, parsed_slot)
            config = {"last_ams_remain_percent": _ams_remain_percent_or_none(parsed_slot.remain), "ams_raw": parsed_slot.raw}
            if auto_created_sku:
                config["needs_sku_review"] = True
                config["auto_created_sku_id"] = sku.id if sku else None
                if previous_spool_id is not None:
                    config["sku_review_reason"] = "ams_filament_change"
            spool = FilamentSpool(
                sku_id=sku.id if sku else None,
                official_spool_uid=official_uid,
                identity_source="ams_official_id",
                nominal_weight_g=(sku.nominal_weight_g if sku else _slot_nominal_weight_g(parsed_slot)),
                status="loaded_in_ams" if sku else "unknown",
                opened_at=utc_now() if sku else None,
                current_printer_id=printer_id,
                current_ams_id=parsed_slot.ams_id,
                current_tray_id=parsed_slot.tray_id,
                config=config,
            )
            db.add(spool)
            db.flush()
            if sku is not None and not auto_created_sku:
                _open_one_from_stock_if_available(db, sku, spool=spool, note="AMS official spool identified")
                _fill_sku_color_from_slot(db, sku, parsed_slot)
                _ensure_color_mapping_from_sku(db, sku)
                _record_event(
                    db,
                    spool=spool,
                    sku_id=sku.id,
                    event_type="opened_from_stock",
                    message="AMS official spool opened from matched SKU",
                    current=_spool_snapshot(spool),
                )
            elif sku is not None:
                _record_event(
                    db,
                    spool=spool,
                    sku_id=sku.id,
                    event_type="needs_location",
                    message="Replacement AMS spool created with an auto-created SKU that needs review"
                    if previous_spool_id is not None
                    else "AMS spool created with an auto-created SKU that needs review",
                    current=_spool_snapshot(spool),
                    data=_slot_match_context(parsed_slot),
                )
            else:
                _record_event(
                    db,
                    spool=spool,
                    event_type="needs_location",
                    message="AMS spool requires SKU confirmation",
                    current=_spool_snapshot(spool),
                    data=_slot_match_context(parsed_slot),
                )
    elif spool.sku_id is None:
        matched, auto_created_sku = _resolve_sku_for_ams_slot(db, parsed_slot)
        if matched is not None:
            spool.sku_id = matched.id
            spool.nominal_weight_g = spool.nominal_weight_g or matched.nominal_weight_g
            _fill_sku_color_from_slot(db, matched, parsed_slot)
            _ensure_color_mapping_from_sku(db, matched)
            if not auto_created_sku:
                _open_one_from_stock_if_available(
                    db,
                    matched,
                    spool=spool,
                    note="AMS official spool completed from matched SKU",
                )
            if auto_created_sku:
                config = dict(spool.config or {})
                config["needs_sku_review"] = True
                config["auto_created_sku_id"] = matched.id
                if previous_spool_id is not None and previous_spool_id != spool.id:
                    config["sku_review_reason"] = "ams_filament_change"
                spool.config = config
            else:
                config = dict(spool.config or {})
                config.pop("needs_sku_review", None)
                config.pop("auto_created_sku_id", None)
                config.pop("sku_review_reason", None)
                spool.config = config

    if not parsed_slot.is_transitioning:
        if previous_spool_id is not None and previous_spool_id != spool.id:
            _record_ams_slot_unload(
                db,
                slot=slot_model,
                previous_spool_id=previous_spool_id,
                note="AMS slot identity changed",
            )
        _set_filament_loaded_location(db, spool, printer_id=printer_id, parsed_slot=parsed_slot)
        slot_model.filament_spool_id = spool.id
    _sync_ams_context(spool, parsed_slot)
    db.add(slot_model)
    db.add(spool)
    return spool, created


def _type_series_payload(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if "brand_id" in values and values["brand_id"] is not None:
        payload["brand_id"] = int(values["brand_id"])
    elif not partial:
        brand_ids = values.get("brand_ids") or []
        if brand_ids:
            payload["brand_id"] = int(brand_ids[0])
        else:
            raise ValueError("Brand is required")
    if "material_type" in values:
        material = _required_text(values["material_type"], "Material type")
        payload["material_type"] = material if material in MATERIAL_TYPES else material
    elif not partial:
        raise ValueError("Material type is required")
    if "series_name" in values:
        payload["series_name"] = _required_text(values["series_name"], "Series name")
    elif not partial:
        raise ValueError("Series name is required")
    if "empty_spool_weight_g" in values:
        payload["empty_spool_weight_g"] = values["empty_spool_weight_g"]
    if "config" in values:
        payload["config"] = values["config"] or {}
    elif not partial:
        payload["config"] = {}
    if "note" in values:
        payload["note"] = values["note"]
    if "material_type" in payload and "series_name" in payload:
        payload["material_type"], payload["series_name"] = normalize_type_series_identity(
            payload["material_type"],
            payload["series_name"],
        )
    return payload


def _sku_payload(values: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if "type_series_id" in values and values["type_series_id"] is not None:
        payload["type_series_id"] = int(values["type_series_id"])
    elif not partial:
        type_series_ids = values.get("type_series_ids") or []
        if type_series_ids:
            payload["type_series_id"] = int(type_series_ids[0])
        else:
            raise ValueError("Type series is required")
    if "color_name" in values:
        payload["color_name"] = _clean_text(values["color_name"])
    if "color_hex" in values:
        payload["color_hex"] = normalize_color_hex(values["color_hex"]) if values["color_hex"] else None
    if "nominal_weight_g" in values and values["nominal_weight_g"] is not None:
        payload["nominal_weight_g"] = values["nominal_weight_g"]
    elif not partial:
        payload["nominal_weight_g"] = 1000.0
    if "filament_diameter_mm" in values and values["filament_diameter_mm"] is not None:
        payload["filament_diameter_mm"] = values["filament_diameter_mm"]
    elif not partial:
        payload["filament_diameter_mm"] = 1.75
    if "tray_info_idx" in values:
        payload["tray_info_idx"] = _clean_text(values["tray_info_idx"])
    if "note" in values:
        payload["note"] = values["note"]
    return payload


def _sku_identity_payload(sku: FilamentSku, updates: dict[str, Any] | None = None) -> dict[str, Any]:
    updates = updates or {}
    return {
        "type_series_id": int(updates.get("type_series_id", sku.type_series_id)),
        "color_name": updates.get("color_name", sku.color_name),
        "color_hex": _normalize_color_hex_or_none(updates.get("color_hex", sku.color_hex)),
        "nominal_weight_g": float(updates.get("nominal_weight_g", sku.nominal_weight_g)),
        "filament_diameter_mm": float(updates.get("filament_diameter_mm", sku.filament_diameter_mm or 1.75)),
        "tray_info_idx": _clean_text(updates.get("tray_info_idx", sku.tray_info_idx)),
    }


def _complete_sku_payload_from_color_mapping(db: Session, payload: dict[str, Any]) -> None:
    type_series_id = payload.get("type_series_id")
    if type_series_id is None:
        return
    color_name = _clean_text(payload.get("color_name"))
    color_hex = _normalize_color_hex_or_none(payload.get("color_hex"))
    if color_name and not color_hex:
        mapping = db.scalars(
            select(FilamentColorMapping).where(
                FilamentColorMapping.type_series_id == int(type_series_id),
                func.lower(FilamentColorMapping.color_name) == color_name.lower(),
            )
        ).first()
        if mapping is not None and _official_match_for_color_mapping(mapping) is None:
            payload["color_hex"] = mapping.color_hex
    elif color_hex and not color_name:
        mapping = db.scalars(
            select(FilamentColorMapping).where(
                FilamentColorMapping.type_series_id == int(type_series_id),
                FilamentColorMapping.color_hex == color_hex,
            )
        ).first()
        if mapping is not None and _official_match_for_color_mapping(mapping) is None:
            payload["color_name"] = mapping.color_name


def _find_duplicate_sku(
    db: Session,
    payload: dict[str, Any],
    *,
    exclude_id: int | None = None,
) -> FilamentSku | None:
    type_series_id = int(payload["type_series_id"])
    color_name = _clean_text(payload.get("color_name"))
    color_hex = _normalize_color_hex_or_none(payload.get("color_hex"))
    tray_info_idx = _clean_text(payload.get("tray_info_idx"))
    nominal_weight_g = float(payload.get("nominal_weight_g") or 0)
    filament_diameter_mm = float(payload.get("filament_diameter_mm") or 1.75)
    stmt = select(FilamentSku).where(
        FilamentSku.type_series_id == type_series_id,
        _nullable_text_equals(FilamentSku.color_name, color_name, lower=True),
        _nullable_text_equals(FilamentSku.color_hex, color_hex),
        FilamentSku.nominal_weight_g == nominal_weight_g,
        FilamentSku.filament_diameter_mm == filament_diameter_mm,
        _nullable_text_equals(FilamentSku.tray_info_idx, tray_info_idx),
    )
    if exclude_id is not None:
        stmt = stmt.where(FilamentSku.id != exclude_id)
    exact = db.scalars(stmt.limit(1)).first()
    if exact is not None:
        return exact

    official = _official_match_for_payload(db, payload)
    if official is None or official.ambiguous:
        return None
    candidates = list(
        db.scalars(
            select(FilamentSku).where(
                FilamentSku.type_series_id == type_series_id,
                FilamentSku.nominal_weight_g == nominal_weight_g,
                FilamentSku.filament_diameter_mm == filament_diameter_mm,
            )
        ).all()
    )
    for sku in candidates:
        if exclude_id is not None and sku.id == exclude_id:
            continue
        sku_official = _official_match_for_sku(sku)
        if sku_official is not None and sku_official.color.color_code == official.color.color_code:
            return sku
    return None


def _nullable_text_equals(column: Any, value: str | None, *, lower: bool = False) -> Any:
    if value is None:
        return column.is_(None)
    return func.lower(column) == value.lower() if lower else column == value


def _color_mapping_payload(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    brand_id = int(values["brand_id"])
    type_series_id = int(values["type_series_id"])
    if get_brand(db, brand_id) is None:
        raise ValueError("Brand not found")
    type_series = get_type_series(db, type_series_id)
    if type_series is None:
        raise ValueError("Type series not found")
    if type_series.brand_id != brand_id:
        raise ValueError("Type series does not belong to brand")
    return {
        "brand_id": brand_id,
        "type_series_id": type_series_id,
        "color_name": _required_text(values["color_name"], "Color name"),
        "color_hex": normalize_color_hex(values["color_hex"]),
        "note": values.get("note"),
    }


def _apply_color_mapping_to_sku_gaps(
    db: Session,
    *,
    brand_id: int,
    type_series_id: int,
    color_name: str,
    color_hex: str,
    note: str | None = None,
) -> int:
    type_series = get_type_series(db, type_series_id)
    if type_series is not None:
        match = _official_match_for_type_series(
            type_series,
            color_hex=color_hex,
            color_name=color_name,
        )
        if match is not None:
            return 0
    updated = 0
    skus = list(db.scalars(select(FilamentSku).where(FilamentSku.type_series_id == type_series_id)).all())
    for sku in skus:
        changed = False
        sku_color_name = _clean_text(sku.color_name)
        sku_color_hex = _normalize_color_hex_or_none(sku.color_hex)
        if sku_color_name and not sku_color_hex and _same(sku_color_name, color_name):
            sku.color_hex = color_hex
            changed = True
        if sku_color_hex == color_hex and not sku_color_name:
            sku.color_name = color_name
            changed = True
        if changed:
            db.add(sku)
            updated += 1
    return updated


def _apply_color_mapping_update_to_skus(
    db: Session,
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> int:
    updated = 0
    previous_name = _clean_text(previous.get("color_name"))
    previous_hex = _normalize_color_hex_or_none(previous.get("color_hex"))
    if not previous_name or not previous_hex:
        return updated
    skus = list(
        db.scalars(
            select(FilamentSku).where(
                FilamentSku.type_series_id == int(previous["type_series_id"]),
                func.lower(FilamentSku.color_name) == previous_name.lower(),
                FilamentSku.color_hex == previous_hex,
            )
        ).all()
    )
    for sku in skus:
        changed = False
        if sku.type_series_id != current["type_series_id"]:
            sku.type_series_id = current["type_series_id"]
            changed = True
        if sku.color_name != current["color_name"]:
            sku.color_name = current["color_name"]
            changed = True
        if sku.color_hex != current["color_hex"]:
            sku.color_hex = current["color_hex"]
            changed = True
        if changed:
            db.add(sku)
            updated += 1
    return updated


def _apply_color_mappings_to_sku_gaps(db: Session) -> int:
    updated = 0
    mappings = list(db.scalars(select(FilamentColorMapping)).all())
    for mapping in mappings:
        if _official_match_for_color_mapping(mapping) is not None:
            continue
        updated += _apply_color_mapping_to_sku_gaps(
            db,
            brand_id=mapping.brand_id,
            type_series_id=mapping.type_series_id,
            color_name=mapping.color_name,
            color_hex=mapping.color_hex,
            note=mapping.note,
        )
    return updated


def _ensure_color_mapping_from_sku(db: Session, sku: FilamentSku) -> bool:
    if _official_match_for_sku(sku) is not None:
        return False
    color_name = _clean_text(sku.color_name)
    color_hex = _normalize_color_hex_or_none(sku.color_hex)
    if not color_name or not color_hex or sku.type_series_id is None:
        return False
    type_series = sku.type_series or get_type_series(db, sku.type_series_id)
    if type_series is None:
        return False
    existing = _find_color_mapping(
        db,
        brand_id=type_series.brand_id,
        type_series_id=type_series.id,
        color_name=color_name,
        color_hex=color_hex,
    )
    if existing is not None:
        return False
    same_hex = _find_color_mapping_by_hex(
        db,
        brand_id=type_series.brand_id,
        type_series_id=type_series.id,
        color_hex=color_hex,
    )
    if same_hex is not None:
        same_hex.color_name = color_name
        db.add(same_hex)
        return True
    mapping = FilamentColorMapping(
        brand_id=type_series.brand_id,
        type_series_id=type_series.id,
        color_name=color_name,
        color_hex=color_hex,
    )
    db.add(mapping)
    db.flush()
    return True


def _ensure_color_mappings_from_skus(db: Session) -> int:
    updated = 0
    for sku in list(db.scalars(select(FilamentSku)).all()):
        if _ensure_color_mapping_from_sku(db, sku):
            updated += 1
    return updated


def _official_match_for_payload(db: Session, payload: dict[str, Any]) -> BambuOfficialMatch | None:
    type_series_id = payload.get("type_series_id")
    if type_series_id is None:
        return None
    type_series = get_type_series(db, int(type_series_id))
    if type_series is None:
        return None
    return _official_match_for_type_series(
        type_series,
        tray_info_idx=payload.get("tray_info_idx"),
        color_hex=payload.get("color_hex"),
        color_name=payload.get("color_name"),
    )


def _official_match_for_sku(sku: FilamentSku) -> BambuOfficialMatch | None:
    type_series = sku.type_series
    if type_series is None:
        return None
    return _official_match_for_type_series(
        type_series,
        tray_info_idx=sku.tray_info_idx,
        color_hex=sku.color_hex,
        color_name=sku.color_name,
    )


def _official_match_for_color_mapping(mapping: FilamentColorMapping) -> BambuOfficialMatch | None:
    type_series = mapping.type_series
    if type_series is None:
        return None
    return _official_match_for_type_series(
        type_series,
        color_hex=mapping.color_hex,
        color_name=mapping.color_name,
    )


def _official_match_for_slot_type_series(
    type_series: FilamentTypeSeries | None,
    slot: ParsedAmsSlot,
) -> BambuOfficialMatch | None:
    if type_series is None:
        return None
    return _official_match_for_type_series(
        type_series,
        tray_info_idx=_slot_tray_info_idx(slot),
        color_hex=slot.color,
        color_name=_slot_color_name(slot),
        raw=slot.raw if isinstance(slot.raw, dict) else {},
    )


def _official_match_for_type_series(
    type_series: FilamentTypeSeries,
    *,
    tray_info_idx: Any = None,
    color_hex: Any = None,
    color_name: Any = None,
    raw: dict[str, Any] | None = None,
) -> BambuOfficialMatch | None:
    brand = type_series.brand
    if brand is None:
        return None
    match = resolve_bambu_official_color(
        brand_name=brand.name,
        brand_aliases=brand.aliases,
        material=type_series.material_type,
        series=type_series.series_name,
        tray_info_idx=tray_info_idx,
        color_hex=color_hex,
        color_name=color_name,
        raw=raw,
    )
    return None if match is not None and match.ambiguous else match


def _slot_and_sku_official_match(sku: FilamentSku, slot: ParsedAmsSlot) -> bool:
    sku_match = _official_match_for_sku(sku)
    if sku_match is None:
        return False
    slot_match = _official_match_for_slot_type_series(sku.type_series, slot)
    return slot_match is not None and slot_match.color.color_code == sku_match.color.color_code


def _stock_balance(db: Session, sku: FilamentSku, *, create: bool = False) -> FilamentStockBalance:
    balance = sku.stock_balance
    if balance is None:
        balance = db.get(FilamentStockBalance, sku.id)
    if balance is None and create:
        balance = FilamentStockBalance(sku_id=sku.id, sealed_quantity=0)
        db.add(balance)
        db.flush()
        sku.stock_balance = balance
    if balance is None:
        return FilamentStockBalance(sku_id=sku.id, sealed_quantity=0)
    return balance


def _open_one_from_stock_if_available(
    db: Session,
    sku: FilamentSku,
    *,
    spool: FilamentSpool | None,
    note: str,
) -> bool:
    balance = _stock_balance(db, sku, create=True)
    if balance.sealed_quantity <= 0:
        return False
    previous = balance.sealed_quantity
    balance.sealed_quantity -= 1
    db.add(balance)
    _record_event(
        db,
        spool=spool,
        sku_id=sku.id,
        event_type="opened_from_stock",
        quantity_delta=-1,
        message="Opened one spool from sealed stock",
        previous={"sealed_quantity": previous},
        current={"sealed_quantity": balance.sealed_quantity},
        note=note,
    )
    return True


def _sku_or_none(db: Session, sku_id: int | None) -> FilamentSku | None:
    if sku_id is None:
        return None
    sku = get_sku(db, sku_id)
    if sku is None:
        raise ValueError("Filament SKU not found")
    return sku


def _find_spool_by_official_uid(db: Session, uid: str | None) -> FilamentSpool | None:
    if not uid:
        return None
    return db.scalars(select(FilamentSpool).where(FilamentSpool.official_spool_uid == uid)).first()


def _official_uid_placeholder_candidate(db: Session, previous_spool_id: int | None) -> FilamentSpool | None:
    if previous_spool_id is None:
        return None
    spool = db.get(FilamentSpool, previous_spool_id)
    if spool is None:
        return None
    if spool.official_spool_uid is not None or spool.sku_id is not None:
        return None
    if spool.status in HISTORICAL_SPOOL_STATUSES:
        return None
    return spool


def _complete_placeholder_from_official_slot(
    db: Session,
    *,
    spool: FilamentSpool,
    official_uid: str,
    parsed_slot: ParsedAmsSlot,
    sku: FilamentSku | None,
    auto_created_sku: bool,
) -> None:
    spool.official_spool_uid = official_uid
    spool.identity_source = "ams_official_id"
    if sku is not None:
        spool.sku_id = sku.id
        spool.nominal_weight_g = spool.nominal_weight_g or sku.nominal_weight_g
        if spool.opened_at is None:
            spool.opened_at = utc_now()
        _fill_sku_color_from_slot(db, sku, parsed_slot)
        _ensure_color_mapping_from_sku(db, sku)
        if not auto_created_sku:
            _open_one_from_stock_if_available(db, sku, spool=spool, note="AMS official spool completed from placeholder")
    else:
        spool.nominal_weight_g = spool.nominal_weight_g or _slot_nominal_weight_g(parsed_slot)

    config = dict(spool.config or {})
    config["last_ams_remain_percent"] = _ams_remain_percent_or_none(parsed_slot.remain)
    config["ams_raw"] = parsed_slot.raw
    if auto_created_sku:
        config["needs_sku_review"] = True
        config["auto_created_sku_id"] = sku.id if sku else None
    elif sku is not None:
        config.pop("needs_sku_review", None)
        config.pop("auto_created_sku_id", None)
        config.pop("sku_review_reason", None)
    spool.config = config
    db.add(spool)


def _find_color_mapping(
    db: Session,
    *,
    brand_id: int,
    type_series_id: int,
    color_name: str,
    color_hex: str,
) -> FilamentColorMapping | None:
    return db.scalars(
        select(FilamentColorMapping).where(
            FilamentColorMapping.brand_id == brand_id,
            FilamentColorMapping.type_series_id == type_series_id,
            func.lower(FilamentColorMapping.color_name) == color_name.lower(),
            FilamentColorMapping.color_hex == color_hex,
        )
    ).first()


def _find_color_mapping_by_hex(
    db: Session,
    *,
    brand_id: int,
    type_series_id: int,
    color_hex: str,
) -> FilamentColorMapping | None:
    return db.scalars(
        select(FilamentColorMapping).where(
            FilamentColorMapping.brand_id == brand_id,
            FilamentColorMapping.type_series_id == type_series_id,
            FilamentColorMapping.color_hex == color_hex,
        )
    ).first()


def _official_uid_from_slot(slot: ParsedAmsSlot) -> str | None:
    for value in (slot.tray_uuid, slot.tag_uid, slot.identity.identity_key):
        uid = _official_uid_or_none(value)
        if uid is not None:
            return uid
    return None


def _official_uid_or_none(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    for prefix in ("bambu:tray_uuid:", "bambu:tag_uid:"):
        if text.startswith(prefix):
            text = text.removeprefix(prefix)
            break
    if not is_valid_identity_value(text):
        return None
    return text


def _handle_historical_uid_reappeared(
    db: Session,
    *,
    printer_id: int,
    slot_model: AmsSlot,
    parsed_slot: ParsedAmsSlot,
    historical_spool: FilamentSpool,
    previous_spool_id: int | None,
) -> tuple[FilamentSpool, bool]:
    previous = db.get(FilamentSpool, previous_spool_id) if previous_spool_id is not None else None
    if previous is not None and _is_uid_conflict_placeholder(previous, historical_spool.official_spool_uid):
        _sync_uid_conflict_placeholder(previous, parsed_slot)
        previous.current_printer_id = printer_id
        previous.current_ams_id = parsed_slot.ams_id
        previous.current_tray_id = parsed_slot.tray_id
        previous.storage_location = None
        previous.status = "unknown"
        slot_model.filament_spool_id = previous.id
        db.add(slot_model)
        db.add(previous)
        return previous, False

    if previous_spool_id is not None and previous_spool_id != historical_spool.id:
        _record_ams_slot_unload(
            db,
            slot=slot_model,
            previous_spool_id=previous_spool_id,
            note="AMS slot reports a UID that belongs to an archived or empty spool",
        )

    sku = _match_sku_for_slot(db, parsed_slot)
    conflict_spool = FilamentSpool(
        sku_id=(sku.id if sku else historical_spool.sku_id),
        identity_source="ams_official_id",
        nominal_weight_g=(sku.nominal_weight_g if sku else historical_spool.nominal_weight_g or _slot_nominal_weight_g(parsed_slot)),
        status="unknown",
        current_printer_id=printer_id,
        current_ams_id=parsed_slot.ams_id,
        current_tray_id=parsed_slot.tray_id,
        config={
            "needs_sku_review": True,
            "review_reason": "archived_uid_reappeared",
            "reappeared_official_spool_uid": historical_spool.official_spool_uid,
            "archived_spool_id": historical_spool.id,
            "archived_spool_status": historical_spool.status,
            "last_ams_remain_percent": _ams_remain_percent_or_none(parsed_slot.remain),
            "ams_raw": parsed_slot.raw,
        },
    )
    db.add(conflict_spool)
    db.flush()
    slot_model.filament_spool_id = conflict_spool.id
    db.add(slot_model)
    _record_event(
        db,
        spool=conflict_spool,
        sku_id=conflict_spool.sku_id,
        event_type="uid_conflict_pending",
        message="AMS reported a UID that belongs to an archived or empty spool",
        current=_spool_snapshot(conflict_spool),
        data={
            **_slot_match_context(parsed_slot),
            "reappeared_official_spool_uid": historical_spool.official_spool_uid,
            "archived_spool_id": historical_spool.id,
            "archived_spool_status": historical_spool.status,
        },
    )
    return conflict_spool, True


def _is_uid_conflict_placeholder(spool: FilamentSpool, uid: str | None) -> bool:
    config = spool.config if isinstance(spool.config, dict) else {}
    return config.get("review_reason") == "archived_uid_reappeared" and config.get("reappeared_official_spool_uid") == uid


def _sync_uid_conflict_placeholder(spool: FilamentSpool, slot: ParsedAmsSlot) -> None:
    config = dict(spool.config or {})
    config["last_ams_remain_percent"] = _ams_remain_percent_or_none(slot.remain)
    config["ams_raw"] = slot.raw
    spool.config = config


def _create_unknown_ams_spool(
    db: Session,
    *,
    printer_id: int,
    parsed_slot: ParsedAmsSlot,
    sku: FilamentSku | None = None,
    auto_created_sku: bool = False,
    identity_source: str = "ams_official_id",
    review_reason: str | None = None,
) -> FilamentSpool:
    config = {"last_ams_remain_percent": _ams_remain_percent_or_none(parsed_slot.remain), "ams_raw": parsed_slot.raw}
    if auto_created_sku:
        config["needs_sku_review"] = True
        config["auto_created_sku_id"] = sku.id if sku else None
    if review_reason:
        config["sku_review_reason"] = review_reason
    spool = FilamentSpool(
        sku_id=sku.id if sku else None,
        identity_source=identity_source,
        nominal_weight_g=(sku.nominal_weight_g if sku else _slot_nominal_weight_g(parsed_slot)),
        status="loaded_in_ams" if sku else "unknown",
        opened_at=utc_now() if sku else None,
        current_printer_id=printer_id,
        current_ams_id=parsed_slot.ams_id,
        current_tray_id=parsed_slot.tray_id,
        config=config,
    )
    db.add(spool)
    db.flush()
    if sku is not None and auto_created_sku:
        _record_event(
            db,
            spool=spool,
            sku_id=sku.id,
            event_type="needs_location",
            message="Replacement AMS spool created with an auto-created SKU that needs review"
            if review_reason == "ams_filament_change"
            else "AMS spool created with an auto-created SKU that needs review",
            current=_spool_snapshot(spool),
            data=_slot_match_context(parsed_slot),
        )
    elif sku is None:
        _record_event(
            db,
            spool=spool,
            event_type="needs_location",
            message="AMS spool requires SKU confirmation",
            current=_spool_snapshot(spool),
            data=_slot_match_context(parsed_slot),
        )
    return spool


def _record_ams_slot_unload(
    db: Session,
    *,
    slot: AmsSlot,
    previous_spool_id: int | None,
    note: str,
) -> None:
    if previous_spool_id is None:
        return
    spool = db.get(FilamentSpool, previous_spool_id)
    if spool is None:
        return
    was_here = (
        spool.current_printer_id == slot.printer_id
        and spool.current_ams_id == slot.ams_id
        and spool.current_tray_id == slot.tray_id
    )
    if not was_here:
        return
    previous = _location_snapshot(spool)
    spool.current_printer_id = None
    spool.current_ams_id = None
    spool.current_tray_id = None
    spool.status = "needs_location" if spool.status != "empty" else spool.status
    db.add(spool)
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="unloaded_from_ams",
        message="Spool unloaded from AMS",
        previous=previous,
        current=_location_snapshot(spool),
        note=note,
    )
    _record_event(
        db,
        spool=spool,
        sku_id=spool.sku_id,
        event_type="needs_location",
        message="Storage location must be set after AMS unload",
        current=_location_snapshot(spool),
    )


def _apply_filament_status_change(db: Session, spool: FilamentSpool, *, status: str) -> None:
    now = utc_now()
    previous_location = _location_snapshot(spool)
    restoring_from_empty = spool.status == "empty" and status in {"opened_in_storage", "loaded_in_ams", "needs_location", "unknown"}
    config = dict(spool.config or {})
    if any(value is not None and value != "" for value in previous_location.values()):
        config["last_location"] = previous_location
    config["status_changed_at"] = now.isoformat()
    if status == "empty":
        config["empty_at"] = now.isoformat()
        config["last_ams_remain_percent"] = 0
        spool.actual_weight_g = 0
    elif status == "archived":
        config["archived_at"] = now.isoformat()
    elif status in {"opened_in_storage", "loaded_in_ams", "needs_location", "unknown"}:
        if spool.status in HISTORICAL_SPOOL_STATUSES:
            config["restored_at"] = now.isoformat()
        if restoring_from_empty and spool.actual_weight_g == 0:
            spool.actual_weight_g = None
            config.pop("last_ams_remain_percent", None)
        if status == "opened_in_storage":
            config.pop("empty_at", None)
            config.pop("archived_at", None)
    if status in HISTORICAL_SPOOL_STATUSES or status in {"opened_in_storage", "needs_location", "unknown"}:
        _clear_slot_bindings_for_spool(db, spool)
        spool.current_printer_id = None
        spool.current_ams_id = None
        spool.current_tray_id = None
    if status in HISTORICAL_SPOOL_STATUSES:
        spool.storage_location = spool.storage_location or _storage_location_from_config(config)
    if status in {"opened_in_storage", "loaded_in_ams"} and spool.opened_at is None:
        spool.opened_at = now
    spool.status = status
    spool.config = config


def _clear_slot_bindings_for_spool(db: Session, spool: FilamentSpool) -> None:
    if spool.id is None:
        return
    for slot in db.scalars(select(AmsSlot).where(AmsSlot.filament_spool_id == spool.id)).all():
        slot.filament_spool_id = None
        db.add(slot)


def _bind_location_slots_to_spool(db: Session, source_spool: FilamentSpool, spool_id: int) -> None:
    if source_spool.id is not None:
        for slot in db.scalars(select(AmsSlot).where(AmsSlot.filament_spool_id == source_spool.id)).all():
            slot.filament_spool_id = spool_id
            db.add(slot)
    if source_spool.current_printer_id is None or source_spool.current_ams_id is None or source_spool.current_tray_id is None:
        return
    slot = db.scalars(
        select(AmsSlot).where(
            AmsSlot.printer_id == source_spool.current_printer_id,
            AmsSlot.ams_id == source_spool.current_ams_id,
            AmsSlot.tray_id == source_spool.current_tray_id,
        )
    ).first()
    if slot is not None:
        slot.filament_spool_id = spool_id
        db.add(slot)


def _storage_location_from_config(config: dict[str, Any]) -> str | None:
    last_location = config.get("last_location")
    if not isinstance(last_location, dict):
        return None
    return _clean_text(last_location.get("storage_location"))


def _set_filament_loaded_location(
    db: Session,
    spool: FilamentSpool,
    *,
    printer_id: int,
    parsed_slot: ParsedAmsSlot,
) -> None:
    previous = _location_snapshot(spool)
    unchanged = (
        spool.current_printer_id == printer_id
        and spool.current_ams_id == parsed_slot.ams_id
        and spool.current_tray_id == parsed_slot.tray_id
        and spool.status == "loaded_in_ams"
    )
    spool.current_printer_id = printer_id
    spool.current_ams_id = parsed_slot.ams_id
    spool.current_tray_id = parsed_slot.tray_id
    spool.storage_location = None
    if spool.status not in HISTORICAL_SPOOL_STATUSES:
        spool.status = "loaded_in_ams" if spool.sku_id is not None else "unknown"
    if spool.opened_at is None and spool.sku_id is not None:
        spool.opened_at = utc_now()
    if not unchanged:
        _record_event(
            db,
            spool=spool,
            sku_id=spool.sku_id,
            event_type="loaded_to_ams",
            message="AMS slot location observed",
            previous=previous,
            current=_location_snapshot(spool),
        )
    db.add(spool)


def _sync_ams_context(spool: FilamentSpool, slot: ParsedAmsSlot) -> None:
    config = dict(spool.config or {})
    config["last_ams_remain_percent"] = _ams_remain_percent_or_none(slot.remain)
    config["ams_raw"] = slot.raw
    spool.config = config


def _match_sku_for_slot(db: Session, slot: ParsedAmsSlot) -> FilamentSku | None:
    _apply_color_mappings_to_sku_gaps(db)
    material = _clean_text(slot.material)
    series = _clean_text(slot.series)
    color_hex = _normalize_color_hex_or_none(slot.color)
    color_name = _slot_color_name(slot)
    candidates = list(db.scalars(select(FilamentSku)).all())
    matches: list[FilamentSku] = []
    for sku in candidates:
        if not _sku_type_series_matches(sku, material=material, series=series):
            continue
        if _slot_and_sku_official_match(sku, slot):
            matches.append(sku)
            continue
        if color_hex and sku.color_hex and sku.color_hex != color_hex:
            continue
        if color_name and sku.color_name and not _same(sku.color_name, color_name):
            continue
        if (sku.color_hex or sku.color_name) and not (
            (color_hex and sku.color_hex == color_hex) or (color_name and sku.color_name and _same(sku.color_name, color_name))
        ):
            continue
        matches.append(sku)
    return _select_sku_match_for_slot(matches, slot)


def _resolve_sku_for_ams_slot(db: Session, slot: ParsedAmsSlot) -> tuple[FilamentSku | None, bool]:
    sku = _match_sku_for_slot(db, slot)
    if sku is not None:
        return sku, False
    if not _slot_has_filament_payload(slot):
        return None, False
    return _find_or_create_sku_from_ams_slot(db, slot)


def _find_or_create_sku_from_ams_slot(db: Session, slot: ParsedAmsSlot) -> tuple[FilamentSku | None, bool]:
    if not _slot_has_filament_payload(slot):
        return None, False
    material = _clean_text(slot.material) or "Other"
    series = _clean_text(slot.series) or "Unknown"
    brand = _find_or_create_ams_brand(db, slot)
    type_series = _find_or_create_ams_type_series(db, brand=brand, material=material, series=series, slot=slot)
    official = _official_match_for_slot_type_series(type_series, slot)
    if official is not None:
        color_hex = official.color.primary_color
        color_name = official.color.names.get("zh") or official.color.names.get("en") or _slot_color_name(slot)
    else:
        color_hex = _normalize_color_hex_or_none(slot.color)
        color_name = _slot_color_name(slot)
    existing = _find_sku_for_type_series_color(
        db,
        type_series_id=type_series.id,
        color_hex=color_hex,
        color_name=color_name,
        slot=slot,
    )
    if existing is not None:
        _fill_sku_color_from_slot(db, existing, slot)
        _ensure_color_mapping_from_sku(db, existing)
        return existing, False
    sku = FilamentSku(
        type_series_id=type_series.id,
        color_name=color_name,
        color_hex=color_hex,
        nominal_weight_g=_slot_nominal_weight_g(slot) or 1000.0,
        filament_diameter_mm=1.75,
        tray_info_idx=_slot_tray_info_idx(slot) or (official.color.fila_id if official is not None else None),
        note="Auto-created from AMS RFID. Please review SKU details.",
    )
    db.add(sku)
    db.flush()
    _ensure_color_mapping_from_sku(db, sku)
    return sku, True


def _find_or_create_ams_brand(db: Session, slot: ParsedAmsSlot) -> FilamentBrand:
    brand_name = _ams_brand_name(slot)
    existing = _find_brand_by_name_or_alias(db, brand_name)
    if existing is not None:
        return existing
    brand = FilamentBrand(name=brand_name, aliases=[], note="Auto-created from AMS RFID. Please review brand details.")
    db.add(brand)
    db.flush()
    return brand


def _find_or_create_ams_type_series(
    db: Session,
    *,
    brand: FilamentBrand,
    material: str,
    series: str,
    slot: ParsedAmsSlot,
) -> FilamentTypeSeries:
    material, series = normalize_type_series_identity(material, series)
    existing = db.scalars(
        select(FilamentTypeSeries).where(
            FilamentTypeSeries.brand_id == brand.id,
            func.lower(FilamentTypeSeries.material_type) == material.lower(),
            func.lower(FilamentTypeSeries.series_name) == series.lower(),
        )
    ).first()
    if existing is not None:
        return existing
    type_series = FilamentTypeSeries(
        brand_id=brand.id,
        material_type=material,
        series_name=series,
        config={"auto_created_from_ams": True, "ams_raw": slot.raw},
        note="Auto-created from AMS RFID. Please review type / series details.",
    )
    db.add(type_series)
    db.flush()
    return type_series


def _find_sku_for_type_series_color(
    db: Session,
    *,
    type_series_id: int,
    color_hex: str | None,
    color_name: str | None,
    slot: ParsedAmsSlot,
) -> FilamentSku | None:
    type_series = get_type_series(db, type_series_id)
    if type_series is not None:
        official = _official_match_for_type_series(
            type_series,
            tray_info_idx=_slot_tray_info_idx(slot),
            color_hex=color_hex,
            color_name=color_name,
            raw=slot.raw if isinstance(slot.raw, dict) else {},
        )
        if official is not None and not official.ambiguous:
            rows = [
                sku
                for sku in db.scalars(select(FilamentSku).where(FilamentSku.type_series_id == type_series_id)).all()
                if (match := _official_match_for_sku(sku)) is not None
                and match.color.color_code == official.color.color_code
            ]
            selected = _select_sku_match_for_slot(rows, slot)
            if selected is not None:
                return selected
    query = select(FilamentSku).where(FilamentSku.type_series_id == type_series_id)
    if color_hex:
        query = query.where(FilamentSku.color_hex == color_hex)
    elif color_name:
        query = query.where(func.lower(FilamentSku.color_name) == color_name.lower())
    else:
        return None
    rows = list(db.scalars(query).all())
    return _select_sku_match_for_slot(rows, slot)


def _select_sku_match_for_slot(candidates: list[FilamentSku], slot: ParsedAmsSlot) -> FilamentSku | None:
    unique = list({sku.id: sku for sku in candidates}.values())
    pool = unique
    nominal_weight_g = _slot_nominal_weight_g(slot)
    if nominal_weight_g is not None:
        weight_matches = [sku for sku in pool if _same_number(sku.nominal_weight_g, nominal_weight_g)]
        if weight_matches:
            pool = weight_matches
        else:
            return None

    if len(pool) <= 1:
        return pool[0] if pool else None

    manual_matches = [sku for sku in pool if not _is_auto_created_sku(sku)]
    if manual_matches:
        pool = manual_matches

    raw = slot.raw if isinstance(slot.raw, dict) else {}
    tray_info_idx = _clean_text(raw.get("tray_info_idx"))
    if tray_info_idx:
        tray_matches = [sku for sku in pool if sku.tray_info_idx and _same(sku.tray_info_idx, tray_info_idx)]
        if tray_matches:
            pool = tray_matches

    unique = list({sku.id: sku for sku in pool}.values())
    return unique[0] if len(unique) == 1 else None


def _is_auto_created_sku(sku: FilamentSku) -> bool:
    note = _clean_text(sku.note)
    return bool(note and "auto-created from ams" in note.lower())


def _find_brand_by_name_or_alias(db: Session, brand_name: str) -> FilamentBrand | None:
    key = _brand_match_key(brand_name)
    for brand in list_brands(db):
        if _brand_match_key(brand.name) == key:
            return brand
        if any(_brand_match_key(alias) == key for alias in (brand.aliases or [])):
            return brand
    return None


def _ams_brand_name(slot: ParsedAmsSlot) -> str:
    raw = slot.raw if isinstance(slot.raw, dict) else {}
    return (
        _clean_text(
            raw.get("tray_brand")
            or raw.get("brand")
            or raw.get("filament_brand")
            or raw.get("filament_brand_name")
            or raw.get("vendor")
            or raw.get("manufacturer")
        )
        or "BambuLab"
    )


def _brand_match_key(value: Any) -> str:
    return (_clean_text(value) or "").replace(" ", "").replace("-", "").replace("_", "").lower()


def _sku_type_series_matches(sku: FilamentSku, *, material: str | None, series: str | None) -> bool:
    type_series = sku.type_series
    if type_series is None:
        return material is None and series is None
    if material and not _same(type_series.material_type, material):
        return False
    if series and not _series_matches(type_series, material=material, series=series):
        return False
    return True


def _series_matches(type_series: FilamentTypeSeries, *, material: str | None, series: str | None) -> bool:
    if series is None:
        return True
    series_norm = _norm(series)
    type_norm = _norm(type_series.series_name)
    material_norm = _norm(material)
    candidates = {type_norm}
    if material_norm:
        candidates.add(_norm(f"{material} {type_series.series_name}"))
    return series_norm in candidates or type_norm in series_norm or series_norm in type_norm


def _fill_sku_color_from_slot(db: Session, sku: FilamentSku, slot: ParsedAmsSlot) -> None:
    changed = False
    match = _official_match_for_slot_type_series(sku.type_series, slot) if sku.type_series is not None else None
    if match is not None:
        color_name = match.color.names.get("zh") or match.color.names.get("en") or _slot_color_name(slot)
        color_hex = match.color.primary_color
        tray_info_idx = _slot_tray_info_idx(slot)
        if tray_info_idx and not sku.tray_info_idx:
            sku.tray_info_idx = tray_info_idx
            changed = True
    else:
        color_name = _slot_color_name(slot)
        color_hex = _normalize_color_hex_or_none(slot.color)
    if color_name and not sku.color_name:
        sku.color_name = color_name
        changed = True
    if color_hex and not sku.color_hex:
        sku.color_hex = color_hex
        changed = True
    if changed:
        db.add(sku)


def _record_event(
    db: Session,
    *,
    event_type: str,
    message: str,
    spool: FilamentSpool | None = None,
    sku_id: int | None = None,
    previous: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
    quantity_delta: int | None = None,
    note: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    db.add(
        FilamentSpoolEvent(
            spool_id=spool.id if spool else None,
            sku_id=sku_id,
            printer_id=spool.current_printer_id if spool else None,
            ams_id=spool.current_ams_id if spool else None,
            tray_id=spool.current_tray_id if spool else None,
            event_type=event_type,
            previous=previous,
            current=current,
            quantity_delta=quantity_delta,
            message=message,
            note=note,
            data=data,
        )
    )


def _spool_snapshot(spool: FilamentSpool) -> dict[str, Any]:
    return {
        "sku_id": spool.sku_id,
        "official_spool_uid": spool.official_spool_uid,
        "identity_source": spool.identity_source,
        "nominal_weight_g": spool.nominal_weight_g,
        "actual_weight_g": spool.actual_weight_g,
        "status": spool.status,
        "opened_at": spool.opened_at.isoformat() if spool.opened_at else None,
        **_location_snapshot(spool),
        "note": spool.note,
    }


def _location_snapshot(spool: FilamentSpool) -> dict[str, Any]:
    return {
        "printer_id": spool.current_printer_id,
        "ams_id": spool.current_ams_id,
        "tray_id": spool.current_tray_id,
        "storage_location": spool.storage_location,
    }


def _slot_match_context(slot: ParsedAmsSlot) -> dict[str, Any]:
    return {
        "ams_id": slot.ams_id,
        "tray_id": slot.tray_id,
        "material": slot.material,
        "series": slot.series,
        "color": slot.color,
        "color_name": _slot_color_name(slot),
        "remain": slot.remain,
    }


def _slot_has_filament_payload(slot: ParsedAmsSlot) -> bool:
    raw = slot.raw if isinstance(slot.raw, dict) else {}
    if raw:
        return _raw_has_filament_payload(raw)
    fields = (slot.material, slot.series, slot.color, slot.color_name)
    if any(_clean_text(value) for value in fields):
        return True
    return False


def _raw_has_filament_payload(raw: dict[str, Any]) -> bool:
    return has_stable_tray_filament_payload(raw)


def _is_phantom_ams_spool(spool: FilamentSpool) -> bool:
    if spool.official_spool_uid:
        return False
    if spool.status not in {"unknown", "needs_location"}:
        return False
    config = spool.config if isinstance(spool.config, dict) else {}
    if spool.sku_id is not None and config.get("auto_created_sku_id") != spool.sku_id:
        return False
    raw = config.get("ams_raw")
    if not isinstance(raw, dict) or _raw_has_filament_payload(raw):
        return False
    if is_placeholder_ams_color_frame(raw):
        return True
    state = (
        _clean_text(raw.get("tray_state"))
        or _clean_text(raw.get("slot_state"))
        or _clean_text(raw.get("tray_status"))
        or _clean_text(raw.get("state"))
    )
    return is_transition_state_without_payload(state)


def _slot_is_empty_observation(slot: ParsedAmsSlot) -> bool:
    state = _slot_state_text(slot)
    return state in {"0", "1", "empty"} and not _slot_has_filament_payload(slot)


def _slot_is_transition_without_payload(slot: ParsedAmsSlot) -> bool:
    if _slot_has_filament_payload(slot):
        return False
    state = _slot_state_text(slot)
    return slot.is_transitioning or is_transition_state_without_payload(state)


def _slot_state_text(slot: ParsedAmsSlot) -> str:
    raw = slot.raw if isinstance(slot.raw, dict) else {}
    value = (
        _clean_text(slot.slot_state)
        or _clean_text(raw.get("tray_state"))
        or _clean_text(raw.get("slot_state"))
        or _clean_text(raw.get("tray_status"))
        or _clean_text(raw.get("state"))
    )
    return (value or "").lower()


def _ams_remain_percent_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 100 else None


def _slot_nominal_weight_g(slot: ParsedAmsSlot) -> float | None:
    raw = slot.raw if isinstance(slot.raw, dict) else {}
    for key in (
        "tray_weight",
        "tray_weight_g",
        "filament_weight",
        "filament_weight_g",
        "nominal_weight_g",
        "net_weight",
        "net_weight_g",
        "weight",
        "weight_g",
    ):
        parsed = _positive_float_or_none(raw.get(key))
        if parsed is not None:
            return parsed
    return None


def _slot_color_name(slot: ParsedAmsSlot) -> str | None:
    return _clean_text(
        slot.color_name
        or slot.raw.get("tray_color_name")
        or slot.raw.get("color_name")
        or slot.raw.get("filament_color_name")
        or slot.raw.get("color_display_name")
    )


def _slot_tray_info_idx(slot: ParsedAmsSlot) -> str | None:
    raw = slot.raw if isinstance(slot.raw, dict) else {}
    return _clean_text(raw.get("tray_info_idx") or raw.get("fila_id"))


def normalize_color_hex(value: Any) -> str:
    text = _clean_text(value)
    if text is None:
        raise ValueError("Color HEX is required")
    compact = text.removeprefix("#").replace(" ", "").replace("_", "").replace("-", "").upper()
    if len(compact) == 8:
        compact = compact[:6]
    if len(compact) != 6 or any(char not in "0123456789ABCDEF" for char in compact):
        raise ValueError("Color HEX must be 6 or 8 hexadecimal characters")
    return compact


def _normalize_color_hex_or_none(value: Any) -> str | None:
    try:
        return normalize_color_hex(value)
    except ValueError:
        return None


def _required_text(value: Any, label: str) -> str:
    text = _clean_text(value)
    if text is None:
        raise ValueError(f"{label} is required")
    return text


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _positive_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _clean_aliases(values: list[str]) -> list[str]:
    seen: set[str] = set()
    aliases: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text is None:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        aliases.append(text)
    return aliases


def _unique_ints(values: list[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        item = int(value)
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _same(left: Any, right: Any) -> bool:
    return _norm(left) == _norm(right)


def _same_number(left: Any, right: Any) -> bool:
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return False


def _norm(value: Any) -> str:
    return (_clean_text(value) or "").replace("-", " ").replace("_", " ").strip().lower()
