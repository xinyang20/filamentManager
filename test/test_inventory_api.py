from __future__ import annotations

import json
from copy import deepcopy

from filament_manager.db import session as db_session
from filament_manager.db.models import (
    FilamentBrand,
    FilamentColorMapping,
    FilamentSku,
    FilamentSpool,
    FilamentStockBalance,
    FilamentTypeSeries,
)


def _brand(api_client, name: str = "Generic", aliases: list[str] | None = None) -> dict:
    if aliases is None:
        aliases = ["拓竹"] if name.replace(" ", "").lower() in {"bambulab", "bambu"} else []
    response = api_client.post("/api/filament/brands", json={"name": name, "aliases": aliases})
    assert response.status_code == 201, response.text
    return response.json()


def _bambu_brand(api_client) -> dict:
    brands = api_client.get("/api/filament/brands").json()
    for brand in brands:
        key = brand["name"].replace(" ", "").replace("-", "").replace("_", "").lower()
        aliases = {
            alias.replace(" ", "").replace("-", "").replace("_", "").lower()
            for alias in brand.get("aliases", [])
        }
        if key in {"bambulab", "bambu"} or "拓竹" in aliases:
            return brand
    raise AssertionError("Bambu brand was not initialized")


def _type_series(api_client, brand_id: int, material: str = "PLA", series: str = "Basic") -> dict:
    response = api_client.post(
        "/api/filament/type-series",
        json={
            "brand_id": brand_id,
            "material_type": material,
            "series_name": series,
            "empty_spool_weight_g": 210,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _existing_type_series(api_client, brand_id: int, material: str, series: str) -> dict:
    for row in api_client.get("/api/filament/type-series").json():
        if (
            row["brand_id"] == brand_id
            and row["material_type"].lower() == material.lower()
            and row["series_name"].lower() == series.lower()
        ):
            return row
    raise AssertionError(f"Type series not found: {brand_id} {material} {series}")


def _bambu_type_series(api_client, material: str = "PLA", series: str = "Basic") -> dict:
    brand = _bambu_brand(api_client)
    return _existing_type_series(api_client, brand["id"], material, series)


def _sku(
    api_client,
    type_series_id: int,
    *,
    color_name: str | None = "Orange",
    color_hex: str | None = "FF6600",
    sealed: int = 1,
    nominal_weight_g: float = 1000,
) -> dict:
    response = api_client.post(
        "/api/filament/skus",
        json={
            "type_series_id": type_series_id,
            "color_name": color_name,
            "color_hex": color_hex,
            "nominal_weight_g": nominal_weight_g,
            "sealed_quantity": sealed,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bambu_catalog_sku(
    api_client,
    *,
    official_color_code: str | None = None,
    material: str | None = None,
    series: str | None = None,
    color_hex: str | None = None,
    tray_info_idx: str | None = None,
) -> dict:
    for sku in api_client.get("/api/filament/skus").json():
        if official_color_code is not None and sku.get("official_color_code") != official_color_code:
            continue
        if material is not None and sku.get("material") != material:
            continue
        if series is not None and sku.get("series") != series:
            continue
        if color_hex is not None and sku.get("color_hex") != color_hex:
            continue
        if tray_info_idx is not None and sku.get("tray_info_idx") != tray_info_idx:
            continue
        if sku.get("nominal_weight_g") == 1000 and sku.get("filament_diameter_mm") == 1.75:
            return sku
    raise AssertionError("Bambu catalog SKU not found")


def _adjust_stock(api_client, sku_id: int, delta: int) -> dict:
    response = api_client.post(f"/api/filament/skus/{sku_id}/sealed-stock-adjust", json={"delta": delta})
    assert response.status_code == 200, response.text
    return response.json()


def _inventory_tree(api_client) -> tuple[dict, dict, dict]:
    brand = _brand(api_client)
    type_series = _type_series(api_client, brand["id"])
    sku = _sku(api_client, type_series["id"])
    return brand, type_series, sku


def _printer(api_client, printer_payload) -> dict:
    response = api_client.post("/api/printers", json=printer_payload)
    assert response.status_code == 201, response.text
    return response.json()


def _ingest(api_client, printer_id: int, payload: dict) -> None:
    response = api_client.post(
        f"/api/printers/{printer_id}/mqtt/payload",
        json={"topic": "device/SYNTHETIC123/report", "payload": payload},
    )
    assert response.status_code == 200, response.text


def test_brand_type_series_sku_crud_and_stats(api_client) -> None:
    brand = _brand(api_client)
    assert brand["aliases"] == []

    type_series = _type_series(api_client, brand["id"], series="PLA Basic")
    assert type_series["brand_id"] == brand["id"]
    assert type_series["brand_ids"] == [brand["id"]]
    assert type_series["brands"][0]["name"] == "Generic"

    sku = _sku(api_client, type_series["id"], sealed=0)
    assert sku["type_series_id"] == type_series["id"]
    assert sku["type_series_ids"] == [type_series["id"]]
    assert sku["brands"][0]["name"] == "Generic"

    brands = {item["id"]: item for item in api_client.get("/api/filament/brands").json()}
    assert brands[brand["id"]]["type_series_count"] == 1
    assert brands[brand["id"]]["sku_count"] == 1

    update = api_client.patch(f"/api/filament/skus/{sku['id']}", json={"color_name": "Jade White", "color_hex": "FFFFFF"})
    assert update.status_code == 200
    assert update.json()["color_hex"] == "FFFFFF"


def test_type_series_duplicate_returns_json_error(api_client) -> None:
    brand = _brand(api_client)
    first = _type_series(api_client, brand["id"], material="ASA", series="ASA")

    duplicate = api_client.post(
        "/api/filament/type-series",
        json={
            "brand_id": brand["id"],
            "material_type": "ASA",
            "series_name": "ASA",
            "empty_spool_weight_g": 250,
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.headers["content-type"].startswith("application/json")
    assert duplicate.json()["detail"] == "Type series already exists for this brand"

    other = _type_series(api_client, brand["id"], material="ABS", series="ABS")
    rejected_update = api_client.patch(
        f"/api/filament/type-series/{other['id']}",
        json={"material_type": first["material_type"], "series_name": first["series_name"]},
    )
    assert rejected_update.status_code == 400
    assert rejected_update.json()["detail"] == "Type series already exists for this brand"


def test_type_series_series_name_is_normalized(api_client) -> None:
    brand = _brand(api_client, "Generic")
    row = _type_series(api_client, brand["id"], material="PETG", series="PETG Basic")
    assert row["material_type"] == "PETG"
    assert row["series_name"] == "Basic"

    duplicate = api_client.post(
        "/api/filament/type-series",
        json={
            "brand_id": brand["id"],
            "material_type": "PETG",
            "series_name": "Basic",
        },
    )
    assert duplicate.status_code == 400


def test_type_series_startup_normalization_preserves_stock_and_spools(api_client) -> None:
    assert db_session.SessionLocal is not None
    db = db_session.SessionLocal()
    try:
        brand = FilamentBrand(name="Legacy Generic", aliases=[])
        db.add(brand)
        db.flush()
        canonical = FilamentTypeSeries(brand_id=brand.id, material_type="PLA", series_name="Basic")
        legacy = FilamentTypeSeries(brand_id=brand.id, material_type="PLA", series_name="PLA Basic")
        db.add_all([canonical, legacy])
        db.flush()
        sku = FilamentSku(type_series_id=legacy.id, color_name="Orange", color_hex="FF6600", nominal_weight_g=1000)
        db.add(sku)
        db.flush()
        db.add(FilamentStockBalance(sku_id=sku.id, sealed_quantity=7))
        db.add(FilamentSpool(sku_id=sku.id, status="opened_in_storage", actual_weight_g=840))
        db.add(FilamentColorMapping(brand_id=brand.id, type_series_id=legacy.id, color_name="Orange", color_hex="FF6600"))
        db.commit()
        sku_id = sku.id
        canonical_id = canonical.id
    finally:
        db.close()

    db_session.create_schema()

    type_series = api_client.get("/api/filament/type-series").json()
    legacy_rows = [row for row in type_series if row["brand_name"] == "Legacy Generic"]
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["id"] == canonical_id
    assert legacy_rows[0]["series_name"] == "Basic"

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[sku_id]["type_series_id"] == canonical_id
    assert skus[sku_id]["sealed_quantity"] == 7
    spools = api_client.get("/api/filament/spools").json()
    assert any(item["sku_id"] == sku_id and item["actual_weight_g"] == 840 for item in spools)
    mappings = api_client.get("/api/filament/color-mappings").json()
    assert any(item["type_series_id"] == canonical_id and item["color_hex"] == "FF6600" for item in mappings)


def test_duplicate_sku_create_and_update_return_conflict(api_client) -> None:
    brand = _brand(api_client)
    type_series = _type_series(api_client, brand["id"], material="PLA", series="Basic")
    first = _sku(api_client, type_series["id"], color_name="Orange", color_hex="FF6600", sealed=2)

    duplicate = api_client.post(
        "/api/filament/skus",
        json={
            "type_series_id": type_series["id"],
            "color_name": "Orange",
            "color_hex": "FF6600",
            "nominal_weight_g": 1000,
            "filament_diameter_mm": 1.75,
            "sealed_quantity": 0,
            "note": "different note and stock must still be duplicate",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_filament_sku"
    assert duplicate.json()["detail"]["existing_sku"]["id"] == first["id"]

    different_weight_response = api_client.post(
        "/api/filament/skus",
        json={
            "type_series_id": type_series["id"],
            "color_name": "Orange",
            "color_hex": "FF6600",
            "nominal_weight_g": 750,
        },
    )
    assert different_weight_response.status_code == 201, different_weight_response.text
    different_weight = different_weight_response.json()

    rejected_update = api_client.patch(
        f"/api/filament/skus/{different_weight['id']}",
        json={"nominal_weight_g": 1000},
    )
    assert rejected_update.status_code == 409
    assert rejected_update.json()["detail"]["existing_sku"]["id"] == first["id"]


def test_brand_delete_allowed_only_when_unreferenced(api_client) -> None:
    unused = _brand(api_client, "Unused Brand")
    assert api_client.delete(f"/api/filament/brands/{unused['id']}").status_code == 204

    brand = _brand(api_client, "Referenced Brand")
    _type_series(api_client, brand["id"])
    rejected = api_client.delete(f"/api/filament/brands/{brand['id']}")
    assert rejected.status_code == 409


def test_delete_conflicts_and_sealed_stock_adjustment(api_client) -> None:
    _, type_series, sku = _inventory_tree(api_client)

    rejected = api_client.delete(f"/api/filament/skus/{sku['id']}")
    assert rejected.status_code == 409

    force_deleted = _sku(api_client, type_series["id"], color_name="Black", color_hex="000000", sealed=2)
    forced = api_client.delete(f"/api/filament/skus/{force_deleted['id']}?force=true")
    assert forced.status_code == 204
    assert force_deleted["id"] not in {item["id"] for item in api_client.get("/api/filament/skus").json()}

    adjusted = api_client.post(f"/api/filament/skus/{sku['id']}/sealed-stock-adjust", json={"delta": -1})
    assert adjusted.status_code == 200
    assert adjusted.json()["sealed_quantity"] == 0

    negative = api_client.post(f"/api/filament/skus/{sku['id']}/sealed-stock-adjust", json={"delta": -1})
    assert negative.status_code == 400

    spool = api_client.post("/api/filament/spools", json={"sku_id": sku["id"], "status": "opened_in_storage"})
    assert spool.status_code == 201

    rejected_sku = api_client.delete(f"/api/filament/skus/{sku['id']}")
    assert rejected_sku.status_code == 409
    force_rejected_sku = api_client.delete(f"/api/filament/skus/{sku['id']}?force=true")
    assert force_rejected_sku.status_code == 409
    rejected_series = api_client.delete(f"/api/filament/type-series/{type_series['id']}")
    assert rejected_series.status_code == 409


def test_spool_unique_uid_location_weight_events_and_delete_rule(api_client) -> None:
    _, _, sku = _inventory_tree(api_client)
    created = api_client.post(
        "/api/filament/spools",
        json={"sku_id": sku["id"], "official_spool_uid": "UID-001", "status": "opened_in_storage"},
    )
    assert created.status_code == 201
    spool = created.json()

    duplicate = api_client.post(
        "/api/filament/spools",
        json={"sku_id": sku["id"], "official_spool_uid": "UID-001", "status": "opened_in_storage"},
    )
    assert duplicate.status_code == 400

    weighted = api_client.post(f"/api/filament/spools/{spool['id']}/weight", json={"actual_weight_g": 875})
    assert weighted.status_code == 200
    assert weighted.json()["actual_weight_g"] == 875

    located = api_client.post(
        f"/api/filament/spools/{spool['id']}/location",
        json={"storage_location": "Dry box A", "note": "Moved from AMS"},
    )
    assert located.status_code == 200
    assert located.json()["storage_location"] == "Dry box A"

    events = api_client.get(f"/api/filament/spools/{spool['id']}/events").json()["events"]
    assert any(item["event_type"] == "weight_updated" for item in events)
    assert any(item["event_type"] == "location_updated" for item in events)

    delete_rejected = api_client.delete(f"/api/filament/spools/{spool['id']}")
    assert delete_rejected.status_code == 409
    api_client.patch(f"/api/filament/spools/{spool['id']}", json={"status": "archived"})
    assert api_client.delete(f"/api/filament/spools/{spool['id']}").status_code == 204


def test_color_mapping_crud_and_sku_gaps(api_client) -> None:
    brand = _brand(api_client, "Generic")
    type_series = _type_series(api_client, brand["id"])
    _type_series(api_client, brand["id"], material="PETG", series="HF")
    _type_series(api_client, brand["id"], material="PLA", series="Matte")
    complete = _sku(api_client, type_series["id"], color_name="Orange", color_hex="FF6600", sealed=0)
    auto_mappings = api_client.get("/api/filament/color-mappings").json()
    assert len(auto_mappings) == 1
    assert auto_mappings[0]["color_name"] == "Orange"
    assert auto_mappings[0]["color_hex"] == "FF6600"
    assert api_client.delete(f"/api/filament/color-mappings/{auto_mappings[0]['id']}").status_code == 204
    auto_mappings = api_client.get("/api/filament/color-mappings").json()
    assert len(auto_mappings) == 1
    assert auto_mappings[0]["color_name"] == "Orange"
    assert auto_mappings[0]["color_hex"] == "FF6600"
    missing_name = _sku(api_client, type_series["id"], color_name=None, color_hex="FFFFFF", sealed=0)
    missing_hex = _sku(api_client, type_series["id"], color_name="Jade White", color_hex=None, sealed=0)

    gaps = api_client.get("/api/filament/color-mapping-gaps").json()
    assert {item["sku_id"] for item in gaps} == {missing_name["id"], missing_hex["id"]}
    assert complete["id"] not in {item["sku_id"] for item in gaps}

    created = api_client.post(
        "/api/filament/color-mappings",
        json={
            "brand_id": brand["id"],
            "type_series_id": type_series["id"],
            "color_name": "Jade White",
            "color_hex": "#ffffffff",
        },
    )
    assert created.status_code == 201
    assert created.json()["color_hex"] == "FFFFFF"
    mappings = api_client.get("/api/filament/color-mappings").json()
    assert len(mappings) == 2
    assert {item["id"] for item in mappings} == {auto_mappings[0]["id"], created.json()["id"]}
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[missing_name["id"]]["color_name"] == "Jade White"
    assert skus[missing_hex["id"]]["color_hex"] == "FFFFFF"
    assert api_client.get("/api/filament/color-mapping-gaps").json() == []

    duplicate = api_client.post(
        "/api/filament/color-mappings",
        json={
            "brand_id": brand["id"],
            "type_series_id": type_series["id"],
            "color_name": "Jade White",
            "color_hex": "FFFFFF",
        },
    )
    assert duplicate.status_code == 400
    later_gap_response = api_client.post(
        "/api/filament/skus",
        json={
            "type_series_id": type_series["id"],
            "color_name": "Jade White",
            "color_hex": None,
            "nominal_weight_g": 750,
            "sealed_quantity": 0,
        },
    )
    assert later_gap_response.status_code == 201, later_gap_response.text
    later_gap = later_gap_response.json()
    assert later_gap["color_hex"] == "FFFFFF"
    assert api_client.get("/api/filament/color-mapping-gaps").json() == []

    update_source = _sku(api_client, type_series["id"], color_name="Ocean Blue", color_hex=None, sealed=0)
    patched_source = api_client.patch(f"/api/filament/skus/{update_source['id']}", json={"color_hex": "123456"})
    assert patched_source.status_code == 200
    mappings = api_client.get("/api/filament/color-mappings").json()
    assert any(item["color_name"] == "Ocean Blue" and item["color_hex"] == "123456" for item in mappings)

    updated = api_client.patch(f"/api/filament/color-mappings/{created.json()['id']}", json={"color_name": "White"})
    assert updated.status_code == 200
    assert updated.json()["color_name"] == "White"
    mappings_after_update = {item["id"]: item for item in api_client.get("/api/filament/color-mappings").json()}
    assert mappings_after_update[created.json()["id"]]["color_name"] == "White"
    skus_after_update = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus_after_update[missing_name["id"]]["color_name"] == "White"
    assert skus_after_update[missing_hex["id"]]["color_name"] == "White"
    assert api_client.delete(f"/api/filament/color-mappings/{created.json()['id']}").status_code == 204


def test_color_mapping_update_persists_after_auto_sku_sync(api_client) -> None:
    brand = _brand(api_client, "Generic")
    type_series = _type_series(api_client, brand["id"])
    sku = _sku(api_client, type_series["id"])
    mapping = api_client.get("/api/filament/color-mappings").json()[0]

    null_parent_update = api_client.patch(
        f"/api/filament/color-mappings/{mapping['id']}",
        json={"brand_id": None, "type_series_id": None, "note": "nullable parent ids are ignored"},
    )
    assert null_parent_update.status_code == 200
    assert null_parent_update.json()["brand_id"] == mapping["brand_id"]
    assert null_parent_update.json()["type_series_id"] == mapping["type_series_id"]

    updated = api_client.patch(
        f"/api/filament/color-mappings/{mapping['id']}",
        json={"color_name": "Mandarin Orange", "color_hex": "FF7711"},
    )
    assert updated.status_code == 200

    mappings = {item["id"]: item for item in api_client.get("/api/filament/color-mappings").json()}
    assert mappings[mapping["id"]]["color_name"] == "Mandarin Orange"
    assert mappings[mapping["id"]]["color_hex"] == "FF7711"
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[sku["id"]]["type_series_id"] == type_series["id"]
    assert skus[sku["id"]]["color_name"] == "Mandarin Orange"
    assert skus[sku["id"]]["color_hex"] == "FF7711"


def test_bambu_official_colors_override_sku_reads_and_effective_mappings(api_client) -> None:
    petg_translucent = _bambu_type_series(api_client, material="PETG", series="Translucent")
    petg_hf = _bambu_type_series(api_client, material="PETG", series="HF")
    asa = _bambu_type_series(api_client, material="ASA", series="Standard")
    tpu = _bambu_type_series(api_client, material="TPU", series="90A")

    translucent = _sku(api_client, petg_translucent["id"], color_name="Clear", color_hex="FFFFFF", sealed=0, nominal_weight_g=750)
    cream = _sku(api_client, petg_hf["id"], color_name="Cream", color_hex="FFFFFF", sealed=0, nominal_weight_g=750)
    asa_white = _sku(api_client, asa["id"], color_name="White", color_hex="FFFFFF", sealed=0, nominal_weight_g=750)
    frozen = _sku(api_client, tpu["id"], color_name="Frozen", color_hex="FFFFFF", sealed=0, nominal_weight_g=750)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[translucent["id"]]["color_name"] == "透明"
    assert skus[cream["id"]]["color_hex"] == "F9DFB9"
    assert skus[cream["id"]]["official_color_code"] == "33401"
    assert skus[asa_white["id"]]["color_hex"] == "FFFAF2"
    assert skus[frozen["id"]]["official_color_type"] == "gradient"
    assert skus[frozen["id"]]["official_colors"] == ["FFFFFF", "40B6E4"]

    assert api_client.get("/api/filament/color-mappings").json() == []
    effective = api_client.get("/api/filament/effective-color-mappings").json()
    assert any(item["color_source"] == "bambu_official" and item["official_color_code"] == "33401" for item in effective)


def test_bambu_official_color_mapping_catalog_endpoint(api_client) -> None:
    rows = api_client.get("/api/filament/bambu-official-color-mappings").json()
    assert len(rows) == 303
    assert not any(item["official_color_code"] == "65100" for item in rows)
    assert any(item["official_color_code"] == "65104" for item in rows)
    cream = next(item for item in rows if item["official_color_code"] == "33401")
    assert cream["brand_name"] == "Bambu Lab"
    assert cream["material_type"] == "PETG"
    assert cream["series_name"] == "HF"
    assert cream["tray_info_idx"] == "GFG02"
    assert cream["color_name"] == "奶油白"
    assert cream["color_hex"] == "F9DFB9"


def test_bambu_manual_mapping_table_is_kept_but_effective_prefers_official(api_client) -> None:
    brand = _bambu_brand(api_client)
    petg_hf = _bambu_type_series(api_client, material="PETG", series="HF")
    created = api_client.post(
        "/api/filament/color-mappings",
        json={
            "brand_id": brand["id"],
            "type_series_id": petg_hf["id"],
            "color_name": "Cream",
            "color_hex": "FFFFFF",
        },
    )
    assert created.status_code == 201, created.text

    manual = api_client.get("/api/filament/color-mappings").json()
    assert len(manual) == 1
    assert manual[0]["color_source"] == "manual"
    effective = api_client.get("/api/filament/effective-color-mappings").json()
    assert any(item["official_color_code"] == "33401" and item["color_hex"] == "F9DFB9" for item in effective)
    assert not any(item["id"] == manual[0]["id"] for item in effective)


def test_non_bambu_brand_uses_manual_color_mapping_only(api_client) -> None:
    brand = _brand(api_client, "Generic")
    petg_hf = _type_series(api_client, brand["id"], material="PETG", series="HF")
    sku = _sku(api_client, petg_hf["id"], color_name="Cream", color_hex="FFFFFF", sealed=0)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[sku["id"]]["color_hex"] == "FFFFFF"
    assert skus[sku["id"]]["color_source"] == "manual"
    effective = api_client.get("/api/filament/effective-color-mappings").json()
    assert any(item["brand_name"] == "Generic" and item["color_source"] == "manual" for item in effective)
    assert not any(item["brand_name"] == "Generic" and item.get("official_color_code") == "33401" for item in effective)


def test_inventory_summary_and_legacy_spools_removed(api_client) -> None:
    _inventory_tree(api_client)
    summary = api_client.get("/api/filament/inventory/summary")
    assert summary.status_code == 200
    assert summary.json()["totals"]["sealed_quantity"] == 1
    assert api_client.get("/api/spools").status_code == 410
    assert api_client.post("/api/spools", json={}).status_code == 410


def test_spool_empty_and_archived_are_history_not_current_stock(api_client) -> None:
    _, _, sku = _inventory_tree(api_client)
    created = api_client.post(
        "/api/filament/spools",
        json={"sku_id": sku["id"], "status": "opened_in_storage", "actual_weight_g": 480, "storage_location": "Dry box A"},
    )
    assert created.status_code == 201, created.text
    spool = created.json()

    marked_empty = api_client.post(f"/api/filament/spools/{spool['id']}/status", json={"status": "empty"})
    assert marked_empty.status_code == 200, marked_empty.text
    body = marked_empty.json()
    assert body["status"] == "empty"
    assert body["actual_weight_g"] == 0
    assert body["last_ams_remain_percent"] == 0
    assert body["empty_at"] is not None
    assert body["last_location"]["storage_location"] == "Dry box A"

    summary = api_client.get("/api/filament/inventory/summary").json()
    assert summary["totals"]["opened_spool_count"] == 0
    assert summary["totals"]["empty_spool_count"] == 1
    assert summary["history_spools"][0]["id"] == spool["id"]

    restored = api_client.post(f"/api/filament/spools/{spool['id']}/status", json={"status": "opened_in_storage"})
    assert restored.status_code == 200
    restored_body = restored.json()
    assert restored_body["status"] == "opened_in_storage"
    assert restored_body["actual_weight_g"] is None
    assert restored_body["last_ams_remain_percent"] is None
    assert "last_ams_remain_percent" not in restored_body["config"]

    summary = api_client.get("/api/filament/inventory/summary").json()
    assert summary["totals"]["opened_spool_count"] == 1
    assert summary["opened_spools"][0]["id"] == spool["id"]
    assert summary["opened_spools"][0]["last_ams_remain_percent"] is None

    archived = api_client.post(f"/api/filament/spools/{spool['id']}/status", json={"status": "archived"})
    assert archived.status_code == 200
    summary = api_client.get("/api/filament/inventory/summary").json()
    assert summary["totals"]["archived_spool_count"] == 1
    assert summary["totals"]["opened_spool_count"] == 0


def test_spool_zero_weight_update_marks_empty(api_client) -> None:
    _, _, sku = _inventory_tree(api_client)
    created = api_client.post(
        "/api/filament/spools",
        json={"sku_id": sku["id"], "status": "opened_in_storage", "actual_weight_g": 120},
    )
    assert created.status_code == 201, created.text
    spool = created.json()

    weighted = api_client.post(f"/api/filament/spools/{spool['id']}/weight", json={"actual_weight_g": 0})
    assert weighted.status_code == 200, weighted.text
    body = weighted.json()
    assert body["status"] == "empty"
    assert body["actual_weight_g"] == 0
    assert body["last_ams_remain_percent"] == 0
    assert body["empty_at"] is not None

    summary = api_client.get("/api/filament/inventory/summary").json()
    assert summary["totals"]["opened_spool_count"] == 0
    assert summary["totals"]["empty_spool_count"] == 1
    assert summary["history_spools"][0]["id"] == spool["id"]
    events = api_client.get(f"/api/filament/spools/{spool['id']}/events").json()["events"]
    assert any(item["event_type"] == "status_empty" for item in events)


def test_ams_existing_official_uid_does_not_decrement_stock(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _, _, sku = _inventory_tree(api_client)
    api_client.post(
        "/api/filament/spools",
        json={
            "sku_id": sku["id"],
            "official_spool_uid": "11111111-2222-3333-4444-555555555555",
            "status": "opened_in_storage",
        },
    )
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())

    _ingest(api_client, printer["id"], payload)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[sku["id"]]["sealed_quantity"] == 0
    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["status"] == "loaded_in_ams"


def test_ams_archived_official_uid_creates_pending_conflict_instead_of_reusing(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _, _, sku = _inventory_tree(api_client)
    archived_response = api_client.post(
        "/api/filament/spools",
        json={
            "sku_id": sku["id"],
            "official_spool_uid": "11111111-2222-3333-4444-555555555555",
            "status": "archived",
        },
    )
    assert archived_response.status_code == 201, archived_response.text
    archived = archived_response.json()
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())

    _ingest(api_client, printer["id"], payload)

    spools = api_client.get("/api/filament/spools").json()
    old = next(item for item in spools if item["id"] == archived["id"])
    conflict = next(item for item in spools if item["id"] != archived["id"])
    assert old["status"] == "archived"
    assert old["current_ams_id"] is None
    assert conflict["status"] == "unknown"
    assert conflict["official_spool_uid"] is None
    assert conflict["config"]["needs_sku_review"] is True
    assert conflict["config"]["review_reason"] == "archived_uid_reappeared"
    assert conflict["config"]["reappeared_official_spool_uid"] == "11111111-2222-3333-4444-555555555555"
    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["filament_spool_id"] == conflict["id"]


def test_ams_existing_unknown_uid_matching_sku_decrements_stock(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    sku = _bambu_catalog_sku(api_client, official_color_code="10300")
    _adjust_stock(api_client, sku["id"], 1)
    created = api_client.post(
        "/api/filament/spools",
        json={
            "official_spool_uid": "11111111-2222-3333-4444-555555555555",
            "status": "unknown",
        },
    )
    assert created.status_code == 201, created.text

    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    spools = api_client.get("/api/filament/spools").json()
    assert skus[sku["id"]]["sealed_quantity"] == 0
    assert len(spools) == 1
    assert spools[0]["sku_id"] == sku["id"]
    assert spools[0]["status"] == "loaded_in_ams"


def test_ams_new_official_uid_matches_sku_and_decrements_once(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    sku = _bambu_catalog_sku(api_client, official_color_code="10300")
    _adjust_stock(api_client, sku["id"], 1)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)
    _ingest(api_client, printer["id"], payload)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    spools = api_client.get("/api/filament/spools").json()
    assert skus[sku["id"]]["sealed_quantity"] == 0
    assert len(spools) == 1
    assert spools[0]["sku_id"] == sku["id"]
    assert spools[0]["last_ams_remain_percent"] == 88


def test_ams_jade_white_uses_weight_to_match_existing_sku(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    type_series = _bambu_type_series(api_client, material="PLA", series="Basic")
    full_sku = _bambu_catalog_sku(api_client, official_color_code="10100")
    _adjust_stock(api_client, full_sku["id"], 1)
    small_sku = _sku(
        api_client,
        type_series["id"],
        color_name="玉石白",
        color_hex="FFFFFF",
        sealed=1,
        nominal_weight_g=250,
    )
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    tray = payload["print"]["ams"]["ams"][0]["tray"][0]
    tray["tray_uuid"] = "C27BF5A592BD43898492BD61E354E427"
    tray["tag_uid"] = "725BB97700000100"
    tray["tray_type"] = "PLA"
    tray["tray_sub_brands"] = "PLA Basic"
    tray["tray_color"] = "FFFFFFFF"
    tray["tray_id_name"] = "A00-W1"
    tray["tray_info_idx"] = "GFA00"
    tray["tray_weight"] = "1000"
    tray["remain"] = 100

    _ingest(api_client, printer["id"], payload)

    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    spools = api_client.get("/api/filament/spools").json()
    assert skus[full_sku["id"]]["sealed_quantity"] == 0
    assert skus[small_sku["id"]]["sealed_quantity"] == 1
    assert len(spools) == 1
    assert spools[0]["sku_id"] == full_sku["id"]
    assert spools[0]["status"] == "loaded_in_ams"
    assert spools[0]["config"].get("needs_sku_review") is None


def test_ams_remain_unavailable_with_rfid_payload_matches_existing_sku(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    petg_sku = _bambu_catalog_sku(api_client, material="PETG", series="Basic", color_hex="FFFFFF", tray_info_idx="GFG00")
    _adjust_stock(api_client, petg_sku["id"], 1)
    payload = json.loads((fixture_dir / "push_status_remain_unavailable.json").read_text())

    _ingest(api_client, printer["id"], payload)

    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["official_spool_uid"] == "C27BF5A592BD43898492BD61E354E427"
    assert spools[0]["sku_id"] == petg_sku["id"]
    assert spools[0]["status"] == "loaded_in_ams"
    assert spools[0]["current_ams_id"] == "128"
    assert spools[0]["current_tray_id"] == "0"
    assert spools[0]["last_ams_remain_percent"] is None
    assert spools[0]["config"]["ams_raw"]["remain"] == -1
    assert spools[0]["config"].get("needs_sku_review") is None
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[petg_sku["id"]]["sealed_quantity"] == 0
    assert not any(item["event_type"] == "filament.spool.pending_confirmation" for item in api_client.get("/api/debug/events").json())


def test_ams_rfid_payload_reuses_uidless_skuless_placeholder(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    petg_sku = _bambu_catalog_sku(api_client, material="PETG", series="Basic", color_hex="FFFFFF", tray_info_idx="GFG00")
    _adjust_stock(api_client, petg_sku["id"], 1)
    payload = json.loads((fixture_dir / "push_status_remain_unavailable.json").read_text())
    placeholder_payload = deepcopy(payload)
    placeholder_payload["print"]["ams"]["ams"][0]["tray"] = [{"id": "0"}]

    _ingest(api_client, printer["id"], placeholder_payload)
    placeholder = api_client.get("/api/filament/spools").json()[0]
    assert placeholder["official_spool_uid"] is None
    assert placeholder["sku_id"] is None

    _ingest(api_client, printer["id"], payload)

    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["id"] == placeholder["id"]
    assert spools[0]["official_spool_uid"] == "C27BF5A592BD43898492BD61E354E427"
    assert spools[0]["identity_source"] == "ams_official_id"
    assert spools[0]["sku_id"] == petg_sku["id"]
    assert spools[0]["status"] == "loaded_in_ams"
    assert spools[0]["last_ams_remain_percent"] is None
    assert spools[0]["config"]["ams_raw"]["remain"] == -1
    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["filament_spool_id"] == placeholder["id"]


def test_ams_replacement_with_existing_sku_loads_new_spool_and_decrements_stock(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    pla_sku = _bambu_catalog_sku(api_client, official_color_code="10300")
    petg_sku = _bambu_catalog_sku(api_client, material="PETG", series="Basic", color_hex="FFFFFF", tray_info_idx="GFG00")
    _adjust_stock(api_client, pla_sku["id"], 1)
    _adjust_stock(api_client, petg_sku["id"], 1)
    first_payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    first_payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"
    _ingest(api_client, printer["id"], first_payload)
    first_spool = next(item for item in api_client.get("/api/filament/spools").json() if item["official_spool_uid"] == "11111111-2222-3333-4444-555555555555")

    second_payload = deepcopy(first_payload)
    tray = second_payload["print"]["ams"]["ams"][0]["tray"][0]
    tray["tray_uuid"] = "22222222-3333-4444-5555-666666666666"
    tray["tag_uid"] = "SECOND1234567890"
    tray["tray_type"] = "PETG"
    tray["tray_sub_brands"] = "Basic"
    tray["tray_color"] = "FFFFFF"
    tray["tray_info_idx"] = "GFG00"
    tray["tray_id_name"] = "PETG Basic White"
    tray["remain"] = 73
    _ingest(api_client, printer["id"], second_payload)

    spools = api_client.get("/api/filament/spools").json()
    unloaded = next(item for item in spools if item["id"] == first_spool["id"])
    loaded = next(item for item in spools if item["official_spool_uid"] == "22222222-3333-4444-5555-666666666666")
    assert unloaded["status"] == "needs_location"
    assert unloaded["current_ams_id"] is None
    assert loaded["status"] == "loaded_in_ams"
    assert loaded["sku_id"] == petg_sku["id"]
    assert loaded["current_ams_id"] == "0"
    assert loaded["current_tray_id"] == "0"
    assert loaded["last_ams_remain_percent"] == 73
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[pla_sku["id"]]["sealed_quantity"] == 0
    assert skus[petg_sku["id"]]["sealed_quantity"] == 0
    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["filament_spool_id"] == loaded["id"]


def test_ams_replacement_marks_previous_spool_needs_location(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _inventory_tree(api_client)
    first_payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    _ingest(api_client, printer["id"], first_payload)
    first_spool = api_client.get("/api/filament/spools").json()[0]

    second_payload = deepcopy(first_payload)
    tray = second_payload["print"]["ams"]["ams"][0]["tray"][0]
    tray["tray_uuid"] = "22222222-3333-4444-5555-666666666666"
    tray["tag_uid"] = "SECOND1234567890"
    tray["tray_color"] = "12AB34"
    tray["tray_id_name"] = "PLA Basic Unlisted Color"
    _ingest(api_client, printer["id"], second_payload)

    unloaded = api_client.get(f"/api/filament/spools/{first_spool['id']}").json()
    assert unloaded["status"] == "needs_location"
    assert unloaded["current_ams_id"] is None
    spools = api_client.get("/api/filament/spools").json()
    replacement = next(item for item in spools if item["official_spool_uid"] == "22222222-3333-4444-5555-666666666666")
    assert replacement["status"] == "loaded_in_ams"
    assert replacement["sku_id"] is not None
    assert replacement["config"]["needs_sku_review"] is True
    assert replacement["current_ams_id"] == "0"
    confirmed = api_client.post(f"/api/filament/spools/{replacement['id']}/confirm-sku")
    assert confirmed.status_code == 200
    assert confirmed.json()["config"].get("needs_sku_review") is None
    assert confirmed.json()["config"]["sku_review_confirmed_at"]
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    assert skus[replacement["sku_id"]]["sealed_quantity"] == 0
    events = api_client.get(f"/api/filament/spools/{first_spool['id']}/events").json()["events"]
    assert any(item["event_type"] == "unloaded_from_ams" for item in events)
    replacement_events = api_client.get(f"/api/filament/spools/{replacement['id']}/events").json()["events"]
    assert any(item["event_type"] == "sku_confirmed" for item in replacement_events)
    debug_events = api_client.get("/api/debug/events").json()
    assert any(item["event_type"] == "filament.spool.pending_confirmation" for item in debug_events)


def test_ams_unmatched_spool_creates_incomplete_sku_without_decrement(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_uuid"] = "140093853F3A41C19B790915BDAEE083"
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_color"] = "6F5034FF"
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Cocoa Brown"
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_weight"] = "250"

    _ingest(api_client, printer["id"], payload)

    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["status"] == "loaded_in_ams"
    assert spools[0]["sku_id"] is not None
    assert spools[0]["nominal_weight_g"] == 250
    assert spools[0]["config"]["needs_sku_review"] is True
    skus = {item["id"]: item for item in api_client.get("/api/filament/skus").json()}
    created_sku = skus[spools[0]["sku_id"]]
    assert created_sku["color_name"] == "可可棕"
    assert created_sku["color_hex"] == "6F5034"
    assert created_sku["nominal_weight_g"] == 250


def test_ams_transition_frame_without_payload_does_not_create_phantom_spool(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _inventory_tree(api_client)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)
    first_spool = api_client.get("/api/filament/spools").json()[0]

    transition_payload = deepcopy(payload)
    for state in (10, 26):
        transition_payload["print"]["ams"]["ams"][0]["tray"][0] = {"id": "0", "state": state}
        _ingest(api_client, printer["id"], transition_payload)

    spools = api_client.get("/api/filament/spools").json()
    assert [item["id"] for item in spools] == [first_spool["id"]]
    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["is_transitioning"] is True
    assert slots[0]["filament_spool_id"] == first_spool["id"]
    debug_events = api_client.get("/api/debug/events").json()
    assert not any(item["event_type"] == "spool.unidentified" for item in debug_events)


def test_ams_empty_exist_bit_unloads_slot_instead_of_staying_transitioning(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _inventory_tree(api_client)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)
    first_spool = api_client.get("/api/filament/spools").json()[0]

    empty_payload = deepcopy(payload)
    empty_payload["print"]["ams"]["tray_exist_bits"] = "0"
    empty_payload["print"]["ams"]["tray_reading_bits"] = "1"
    empty_payload["print"]["ams"]["ams_status"] = 258
    empty_payload["print"]["ams"]["ams"][0]["tray"][0] = {"id": "0", "state": 26}
    _ingest(api_client, printer["id"], empty_payload)

    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["slot_state"] == "empty"
    assert slots[0]["state_name"] == "empty"
    assert slots[0]["is_transitioning"] is False
    assert slots[0]["filament_spool_id"] is None

    spools = api_client.get("/api/filament/spools").json()
    unloaded = next(item for item in spools if item["id"] == first_spool["id"])
    assert unloaded["status"] == "needs_location"
    assert unloaded["current_ams_id"] is None
    assert unloaded["current_tray_id"] is None


def test_ams_ht_transition_states_without_payload_do_not_create_phantom_spool(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)

    for state in (7, 8, 11, 23, 26):
        payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
        payload["print"]["ams"]["ams"][0]["id"] = "128"
        payload["print"]["ams"]["ams"][0]["tray"] = [{"id": "0", "state": state}]

        _ingest(api_client, printer["id"], payload)

        assert api_client.get("/api/filament/spools").json() == []
        slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
        assert slots[0]["ams_id"] == "128"
        assert slots[0]["tray_id"] == "0"
        assert slots[0]["is_transitioning"] is True
        assert slots[0]["filament_spool_id"] is None

    debug_events = api_client.get("/api/debug/events").json()
    assert not any(item["event_type"] in {"spool.discovered", "spool.unidentified"} for item in debug_events)


def test_historical_ams_ht_transition_phantom_spools_are_hidden(api_client) -> None:
    spool_ids = []
    for state in (7, 8, 23, 26):
        response = api_client.post(
            "/api/filament/spools",
            json={
                "identity_source": "manual",
                "status": "needs_location",
                "config": {"ams_raw": {"id": "0", "state": state}},
            },
        )
        assert response.status_code == 201, response.text
        spool_ids.append(response.json()["id"])

    assert api_client.get("/api/filament/spools").json() == []
    for spool_id in spool_ids:
        assert api_client.get(f"/api/filament/spools/{spool_id}").status_code == 404
