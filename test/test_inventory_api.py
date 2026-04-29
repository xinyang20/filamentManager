from __future__ import annotations

import json
from copy import deepcopy


def _brand(api_client, name: str = "Bambu Lab") -> dict:
    response = api_client.post("/api/filament/brands", json={"name": name, "aliases": ["拓竹"]})
    assert response.status_code == 201, response.text
    return response.json()


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


def _sku(api_client, type_series_id: int, *, color_name: str | None = "Orange", color_hex: str | None = "FF6600", sealed: int = 1) -> dict:
    response = api_client.post(
        "/api/filament/skus",
        json={
            "type_series_id": type_series_id,
            "color_name": color_name,
            "color_hex": color_hex,
            "nominal_weight_g": 1000,
            "sealed_quantity": sealed,
        },
    )
    assert response.status_code == 201, response.text
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
    assert brand["aliases"] == ["拓竹"]

    type_series = _type_series(api_client, brand["id"], series="PLA Basic")
    assert type_series["brand_id"] == brand["id"]
    assert type_series["brand_ids"] == [brand["id"]]
    assert type_series["brands"][0]["name"] == "Bambu Lab"

    sku = _sku(api_client, type_series["id"], sealed=0)
    assert sku["type_series_id"] == type_series["id"]
    assert sku["type_series_ids"] == [type_series["id"]]
    assert sku["brands"][0]["name"] == "Bambu Lab"

    brands = api_client.get("/api/filament/brands").json()
    assert brands[0]["type_series_count"] == 1
    assert brands[0]["sku_count"] == 1

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
    brand = _brand(api_client)
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
    later_gap = _sku(api_client, type_series["id"], color_name="Jade White", color_hex=None, sealed=0)
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
    _, type_series, sku = _inventory_tree(api_client)
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


def test_inventory_summary_and_legacy_spools_removed(api_client) -> None:
    _inventory_tree(api_client)
    summary = api_client.get("/api/filament/inventory/summary")
    assert summary.status_code == 200
    assert summary.json()["totals"]["sealed_quantity"] == 1
    assert api_client.get("/api/spools").status_code == 410
    assert api_client.post("/api/spools", json={}).status_code == 410


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

    assert api_client.get("/api/filament/skus").json()[0]["sealed_quantity"] == 0
    spools = api_client.get("/api/filament/spools").json()
    assert len(spools) == 1
    assert spools[0]["status"] == "loaded_in_ams"


def test_ams_existing_unknown_uid_matching_sku_decrements_stock(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _, _, sku = _inventory_tree(api_client)
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
    _inventory_tree(api_client)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)
    _ingest(api_client, printer["id"], payload)

    skus = api_client.get("/api/filament/skus").json()
    spools = api_client.get("/api/filament/spools").json()
    assert skus[0]["sealed_quantity"] == 0
    assert len(spools) == 1
    assert spools[0]["sku_id"] == skus[0]["id"]
    assert spools[0]["last_ams_remain_percent"] == 88


def test_ams_replacement_with_existing_sku_loads_new_spool_and_decrements_stock(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    brand = _brand(api_client)
    pla_series = _type_series(api_client, brand["id"], material="PLA", series="Basic")
    petg_series = _type_series(api_client, brand["id"], material="PETG", series="Basic")
    pla_sku = _sku(api_client, pla_series["id"], color_name="Orange", color_hex="FF6600", sealed=1)
    petg_sku = _sku(api_client, petg_series["id"], color_name="White", color_hex="FFFFFF", sealed=1)
    first_payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    _ingest(api_client, printer["id"], first_payload)
    first_spool = next(item for item in api_client.get("/api/filament/spools").json() if item["official_spool_uid"] == "11111111-2222-3333-4444-555555555555")

    second_payload = deepcopy(first_payload)
    tray = second_payload["print"]["ams"]["ams"][0]["tray"][0]
    tray["tray_uuid"] = "22222222-3333-4444-5555-666666666666"
    tray["tag_uid"] = "SECOND1234567890"
    tray["tray_type"] = "PETG"
    tray["tray_sub_brands"] = "Basic"
    tray["tray_color"] = "FFFFFF"
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
    tray["tray_color"] = "00AAFF"
    tray["tray_id_name"] = "PLA Basic Cyan"
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
    assert api_client.get("/api/filament/skus").json()[0]["sealed_quantity"] == 0
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
    skus = api_client.get("/api/filament/skus").json()
    assert len(skus) == 1
    assert skus[0]["color_name"] == "Cocoa Brown"
    assert skus[0]["color_hex"] == "6F5034"
    assert skus[0]["nominal_weight_g"] == 250


def test_ams_transition_frame_without_payload_does_not_create_phantom_spool(api_client, printer_payload, fixture_dir) -> None:
    printer = _printer(api_client, printer_payload)
    _inventory_tree(api_client)
    payload = json.loads((fixture_dir / "push_status_valid_tray_uuid.json").read_text())
    payload["print"]["ams"]["ams"][0]["tray"][0]["tray_id_name"] = "PLA Basic Orange"

    _ingest(api_client, printer["id"], payload)
    first_spool = api_client.get("/api/filament/spools").json()[0]

    transition_payload = deepcopy(payload)
    transition_payload["print"]["ams"]["ams"][0]["tray"][0] = {"id": "0", "state": 10}
    _ingest(api_client, printer["id"], transition_payload)

    spools = api_client.get("/api/filament/spools").json()
    assert [item["id"] for item in spools] == [first_spool["id"]]
    slots = api_client.get(f"/api/printers/{printer['id']}/ams/slots").json()
    assert slots[0]["is_transitioning"] is True
    assert slots[0]["filament_spool_id"] == first_spool["id"]
    debug_events = api_client.get("/api/debug/events").json()
    assert not any(item["event_type"] == "spool.unidentified" for item in debug_events)
