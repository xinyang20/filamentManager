from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from filament_manager.db.models import AmsSlot
from filament_manager.db.session import get_db
from filament_manager.schemas import (
    AmsSlotRead,
    FilamentBrandCreate,
    FilamentBrandRead,
    FilamentBrandUpdate,
    FilamentColorMappingCreate,
    FilamentColorMappingGapRead,
    FilamentColorMappingRead,
    FilamentColorMappingUpdate,
    FilamentInventorySummaryRead,
    FilamentSkuCreate,
    FilamentSkuRead,
    FilamentSkuStockAdjust,
    FilamentSkuTypeSeriesSet,
    FilamentSkuUpdate,
    FilamentSpoolCreate,
    FilamentSpoolEventsRead,
    FilamentSpoolLocationUpdate,
    FilamentSpoolRead,
    FilamentSpoolStatusUpdate,
    FilamentSpoolUidConflictResolve,
    FilamentSpoolUpdate,
    FilamentSpoolWeightUpdate,
    FilamentTypeSeriesBrandSet,
    FilamentTypeSeriesCreate,
    FilamentTypeSeriesRead,
    FilamentTypeSeriesUpdate,
    SlotBindRequest,
)
from filament_manager.services.inventory import (
    DuplicateFilamentSkuError,
    FilamentSpoolUidConflictError,
    adjust_sku_stock,
    bind_slot_to_filament_spool,
    build_inventory_summary,
    confirm_filament_spool_sku_review,
    create_brand,
    create_color_mapping,
    create_filament_spool,
    create_sku,
    create_type_series,
    delete_brand,
    delete_color_mapping,
    delete_filament_spool,
    delete_sku,
    delete_type_series,
    filament_brand_to_read,
    filament_color_mapping_to_read,
    filament_sku_to_read,
    filament_spool_to_read,
    filament_type_series_to_read,
    get_brand,
    get_color_mapping,
    get_filament_spool,
    get_sku,
    get_type_series,
    list_brands,
    list_color_mapping_gaps,
    list_color_mappings,
    list_filament_spool_events,
    list_filament_spools,
    list_skus,
    list_type_series,
    resolve_reappeared_uid_conflict,
    set_sku_type_series,
    set_type_series_brands,
    update_brand,
    update_color_mapping,
    update_filament_location,
    update_filament_spool,
    update_filament_status,
    update_filament_weight,
    update_sku,
    update_type_series,
)

router = APIRouter()


@router.get("/filament/brands", response_model=list[FilamentBrandRead])
def api_list_filament_brands(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [filament_brand_to_read(db, brand) for brand in list_brands(db)]


@router.post("/filament/brands", response_model=FilamentBrandRead, status_code=status.HTTP_201_CREATED)
def api_create_filament_brand(data: FilamentBrandCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        brand = create_brand(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_brand_to_read(db, brand)


@router.patch("/filament/brands/{brand_id}", response_model=FilamentBrandRead)
def api_update_filament_brand(
    brand_id: int,
    data: FilamentBrandUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    brand = get_brand(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Filament brand not found")
    try:
        updated = update_brand(db, brand, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_brand_to_read(db, updated)


@router.delete("/filament/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_filament_brand(brand_id: int, db: Session = Depends(get_db)) -> Response:
    brand = get_brand(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Filament brand not found")
    try:
        delete_brand(db, brand)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/filament/type-series", response_model=list[FilamentTypeSeriesRead])
def api_list_filament_type_series(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [filament_type_series_to_read(db, row) for row in list_type_series(db)]


@router.post("/filament/type-series", response_model=FilamentTypeSeriesRead, status_code=status.HTTP_201_CREATED)
def api_create_filament_type_series(
    data: FilamentTypeSeriesCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        row = create_type_series(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_type_series_to_read(db, row)


@router.patch("/filament/type-series/{type_series_id}", response_model=FilamentTypeSeriesRead)
def api_update_filament_type_series(
    type_series_id: int,
    data: FilamentTypeSeriesUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_type_series(db, type_series_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Filament type series not found")
    try:
        updated = update_type_series(db, row, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_type_series_to_read(db, updated)


@router.delete("/filament/type-series/{type_series_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_filament_type_series(type_series_id: int, db: Session = Depends(get_db)) -> Response:
    row = get_type_series(db, type_series_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Filament type series not found")
    try:
        delete_type_series(db, row)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/filament/type-series/{type_series_id}/brands", response_model=FilamentTypeSeriesRead)
def api_set_filament_type_series_brands(
    type_series_id: int,
    data: FilamentTypeSeriesBrandSet,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_type_series(db, type_series_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Filament type series not found")
    try:
        updated = set_type_series_brands(db, row, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_type_series_to_read(db, updated)


@router.get("/filament/color-mappings", response_model=list[FilamentColorMappingRead])
def api_list_filament_color_mappings(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [filament_color_mapping_to_read(row) for row in list_color_mappings(db)]


@router.post("/filament/color-mappings", response_model=FilamentColorMappingRead, status_code=status.HTTP_201_CREATED)
def api_create_filament_color_mapping(
    data: FilamentColorMappingCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        mapping = create_color_mapping(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_color_mapping_to_read(mapping)


@router.patch("/filament/color-mappings/{mapping_id}", response_model=FilamentColorMappingRead)
def api_update_filament_color_mapping(
    mapping_id: int,
    data: FilamentColorMappingUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    mapping = get_color_mapping(db, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Filament color mapping not found")
    try:
        updated = update_color_mapping(db, mapping, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_color_mapping_to_read(updated)


@router.delete("/filament/color-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_filament_color_mapping(mapping_id: int, db: Session = Depends(get_db)) -> Response:
    mapping = get_color_mapping(db, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Filament color mapping not found")
    delete_color_mapping(db, mapping)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/filament/color-mapping-gaps", response_model=list[FilamentColorMappingGapRead])
def api_list_filament_color_mapping_gaps(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return list_color_mapping_gaps(db)


@router.get("/filament/skus", response_model=list[FilamentSkuRead])
def api_list_filament_skus(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [filament_sku_to_read(row) for row in list_skus(db)]


def _duplicate_sku_http_exception(exc: DuplicateFilamentSkuError) -> HTTPException:
    existing = filament_sku_to_read(exc.existing_sku)
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "duplicate_filament_sku",
            "message": "Duplicate filament SKU",
            "existing_sku": {
                "id": existing["id"],
                "label": _filament_sku_label(existing),
                "brand_name": existing.get("brand_name"),
                "material": existing.get("material"),
                "series": existing.get("series"),
                "color_name": existing.get("color_name"),
                "color_hex": existing.get("color_hex"),
                "nominal_weight_g": existing.get("nominal_weight_g"),
                "filament_diameter_mm": existing.get("filament_diameter_mm"),
                "tray_info_idx": existing.get("tray_info_idx"),
                "sealed_quantity": existing.get("sealed_quantity"),
            },
        },
    )


def _filament_sku_label(sku: dict[str, Any]) -> str:
    parts = [
        sku.get("brand_name"),
        " ".join(str(value) for value in (sku.get("material"), sku.get("series")) if value),
        sku.get("color_name") or sku.get("color_hex"),
        f"{sku.get('nominal_weight_g')}g" if sku.get("nominal_weight_g") is not None else None,
    ]
    return " / ".join(str(part) for part in parts if part) or f"SKU {sku.get('id')}"


@router.post("/filament/skus", response_model=FilamentSkuRead, status_code=status.HTTP_201_CREATED)
def api_create_filament_sku(data: FilamentSkuCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        sku = create_sku(db, data)
    except DuplicateFilamentSkuError as exc:
        raise _duplicate_sku_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_sku_to_read(sku)


@router.patch("/filament/skus/{sku_id}", response_model=FilamentSkuRead)
def api_update_filament_sku(
    sku_id: int,
    data: FilamentSkuUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sku = get_sku(db, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="Filament SKU not found")
    try:
        updated = update_sku(db, sku, data)
    except DuplicateFilamentSkuError as exc:
        raise _duplicate_sku_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_sku_to_read(updated)


@router.delete("/filament/skus/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_filament_sku(
    sku_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
) -> Response:
    sku = get_sku(db, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="Filament SKU not found")
    try:
        delete_sku(db, sku, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/filament/skus/{sku_id}/type-series", response_model=FilamentSkuRead)
def api_set_filament_sku_type_series(
    sku_id: int,
    data: FilamentSkuTypeSeriesSet,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sku = get_sku(db, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="Filament SKU not found")
    try:
        updated = set_sku_type_series(db, sku, data)
    except DuplicateFilamentSkuError as exc:
        raise _duplicate_sku_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_sku_to_read(updated)


@router.post("/filament/skus/{sku_id}/sealed-stock-adjust", response_model=FilamentSkuRead)
def api_adjust_filament_sku_stock(
    sku_id: int,
    data: FilamentSkuStockAdjust,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sku = get_sku(db, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="Filament SKU not found")
    try:
        updated = adjust_sku_stock(db, sku, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_sku_to_read(updated)


@router.get("/filament/inventory/summary", response_model=FilamentInventorySummaryRead)
def api_get_filament_inventory_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_inventory_summary(db)


@router.get("/filament/spools", response_model=list[FilamentSpoolRead])
def api_list_filament_spools(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [filament_spool_to_read(row) for row in list_filament_spools(db)]


@router.post("/filament/spools", response_model=FilamentSpoolRead, status_code=status.HTTP_201_CREATED)
def api_create_filament_spool(data: FilamentSpoolCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        spool = create_filament_spool(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_spool_to_read(spool)


@router.get("/filament/spools/{spool_id}", response_model=FilamentSpoolRead)
def api_get_filament_spool(spool_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    return filament_spool_to_read(spool)


@router.patch("/filament/spools/{spool_id}", response_model=FilamentSpoolRead)
def api_update_filament_spool(
    spool_id: int,
    data: FilamentSpoolUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    try:
        updated = update_filament_spool(db, spool, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_spool_to_read(updated)


@router.post("/filament/spools/{spool_id}/confirm-sku", response_model=FilamentSpoolRead)
def api_confirm_filament_spool_sku(spool_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    return filament_spool_to_read(confirm_filament_spool_sku_review(db, spool))


@router.post("/filament/spools/{spool_id}/status", response_model=FilamentSpoolRead)
def api_update_filament_spool_status(
    spool_id: int,
    data: FilamentSpoolStatusUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    try:
        updated = update_filament_status(db, spool, status=data.status, note=data.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_spool_to_read(updated)


@router.post("/filament/spools/{spool_id}/resolve-uid-conflict", response_model=FilamentSpoolRead)
def api_resolve_filament_spool_uid_conflict(
    spool_id: int,
    data: FilamentSpoolUidConflictResolve,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    try:
        resolved = resolve_reappeared_uid_conflict(db, spool, action=data.action, note=data.note)
    except FilamentSpoolUidConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if resolved is None:
        raise HTTPException(status_code=409, detail="UID conflict was not resolved")
    return filament_spool_to_read(resolved)


@router.delete("/filament/spools/{spool_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_filament_spool(spool_id: int, db: Session = Depends(get_db)) -> Response:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    try:
        delete_filament_spool(db, spool)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/filament/spools/{spool_id}/events", response_model=FilamentSpoolEventsRead)
def api_get_filament_spool_events(spool_id: int, db: Session = Depends(get_db)) -> dict[str, list[Any]]:
    if get_filament_spool(db, spool_id) is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    return list_filament_spool_events(db, spool_id)


@router.post("/filament/spools/{spool_id}/weight", response_model=FilamentSpoolRead)
def api_update_filament_spool_weight(
    spool_id: int,
    data: FilamentSpoolWeightUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    try:
        updated = update_filament_weight(db, spool, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filament_spool_to_read(updated)


@router.post("/filament/spools/{spool_id}/location", response_model=FilamentSpoolRead)
def api_update_filament_spool_location(
    spool_id: int,
    data: FilamentSpoolLocationUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spool = get_filament_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    return filament_spool_to_read(update_filament_location(db, spool, data))


@router.post("/ams/slots/{slot_id}/bind", response_model=AmsSlotRead)
def api_bind_slot(slot_id: int, data: SlotBindRequest, db: Session = Depends(get_db)) -> AmsSlot:
    slot = db.get(AmsSlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="AMS slot not found")
    filament_spool = get_filament_spool(db, data.spool_id)
    if filament_spool is None:
        raise HTTPException(status_code=404, detail="Filament spool not found")
    return bind_slot_to_filament_spool(db, slot, filament_spool)


@router.api_route("/spools", methods=["GET", "POST", "PATCH", "DELETE"])
@router.api_route("/spools/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
def api_legacy_spools_removed(path: str | None = None) -> None:
    raise HTTPException(status_code=410, detail="Legacy /api/spools has been removed; use /api/filament/spools")

