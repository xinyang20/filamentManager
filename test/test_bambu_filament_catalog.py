from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from filament_manager.db.models import (
    Base,
    FilamentBrand,
    FilamentColorMapping,
    FilamentSku,
    FilamentSpool,
    FilamentSpoolEvent,
    FilamentStockBalance,
    FilamentTypeSeries,
)
from filament_manager.services.bambu_filament_catalog import (
    bambu_official_color_count,
    bambu_official_type_series_count,
    ensure_bambu_official_sku_catalog,
    official_colors_for_type,
    resolve_bambu_official_color,
)


def test_bambu_catalog_loads_official_rows() -> None:
    assert bambu_official_color_count() == 303
    assert bambu_official_type_series_count() == 44


def test_bambu_catalog_supports_single_multi_and_gradient() -> None:
    pla_silk = official_colors_for_type(material="PLA", series="Silk")
    assert any(row.color_type_key == "multi" and row.names["zh"] == "金粉双色" for row in pla_silk)
    assert any(row.color_type_key == "gradient" and row.names["zh"] == "马卡龙" for row in pla_silk)

    petg_hf = resolve_bambu_official_color(
        brand_name="Bambu Lab",
        material="PETG",
        series="HF",
        color_name="Cream",
    )
    assert petg_hf is not None
    assert petg_hf.color.color_type_key == "single"
    assert petg_hf.color.primary_color == "F9DFB9"


def test_bambu_catalog_prefers_tray_info_idx_over_series_color() -> None:
    match = resolve_bambu_official_color(
        brand_name="Bambu Lab",
        material="PLA",
        series="Basic",
        tray_info_idx="GFG00",
        color_hex="FFFFFFFF",
    )
    assert match is not None
    assert match.color.fila_type == "PETG Basic"
    assert match.color.names["zh"] == "白色"


def test_bambu_catalog_uses_type_series_to_disambiguate_reused_tray_ids() -> None:
    cases = [
        ("ASA", "Aero", "GFB02", "F5F1DD", "白色", "46100"),
        ("ABS", "GF", "GFB50", "F48438", "橙色", "41300"),
        ("ASA", "CF", "GFB51", "000000", "黑色", "46101"),
        ("PC", "FR", "GFC01", "000000", "黑色", "63100"),
    ]

    for material, series, tray_info_idx, color_hex, color_name, code in cases:
        match = resolve_bambu_official_color(
            brand_name="Bambu Lab",
            material=material,
            series=series,
            tray_info_idx=tray_info_idx,
            color_hex=color_hex,
            color_name=color_name,
        )
        assert match is not None
        assert match.color.color_code == code


def test_ensure_bambu_official_sku_catalog_populates_empty_database() -> None:
    db = _memory_db()

    summary = ensure_bambu_official_sku_catalog(db)

    assert summary.created_brand_count == 1
    assert summary.created_type_series_count == 44
    assert summary.created_sku_count == 303
    assert summary.updated_sku_count == 0
    assert _skipped_codes(summary) == [["65100"]]
    assert db.scalar(select(func.count(FilamentBrand.id))) == 1
    assert db.scalar(select(func.count(FilamentTypeSeries.id))) == 44
    assert db.scalar(select(func.count(FilamentSku.id))) == 303
    assert db.scalar(select(func.count(FilamentStockBalance.sku_id))) == 0
    assert db.scalar(select(func.count(FilamentColorMapping.id))) == 0
    assert all(
        row.sealed_quantity == 0
        for row in db.scalars(select(FilamentStockBalance).join(FilamentSku)).all()
    )
    skus = list(db.scalars(select(FilamentSku)).all())
    assert all(sku.nominal_weight_g == 1000 for sku in skus)
    assert all(sku.filament_diameter_mm == 1.75 for sku in skus)

    rerun = ensure_bambu_official_sku_catalog(db)
    assert rerun.created_brand_count == 0
    assert rerun.created_type_series_count == 0
    assert rerun.created_sku_count == 0
    assert rerun.updated_sku_count == 0
    assert _skipped_codes(rerun) == [["65100"]]


def test_ensure_bambu_catalog_updates_existing_250g_sku_and_adds_1000g_default() -> None:
    db = _memory_db()
    brand = FilamentBrand(name="Bambu", aliases=[])
    db.add(brand)
    db.flush()
    petg_hf = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="PETG",
        series_name="HF",
        empty_spool_weight_g=None,
    )
    db.add(petg_hf)
    db.flush()
    existing = FilamentSku(
        type_series_id=petg_hf.id,
        color_name="Cream",
        nominal_weight_g=250,
        filament_diameter_mm=1.75,
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id
    type_series_id = petg_hf.id

    summary = ensure_bambu_official_sku_catalog(db)

    db.refresh(existing)
    db.refresh(petg_hf)
    assert summary.filled_empty_spool_weight_count == 1
    assert summary.updated_sku_count == 1
    assert petg_hf.empty_spool_weight_g == 250
    assert existing.color_name == "Cream"
    assert existing.color_hex == "F9DFB9"
    assert existing.tray_info_idx == "GFG02"
    default_cream = _sku_rows(
        db,
        type_series_id=type_series_id,
        color_hex="F9DFB9",
        tray_info_idx="GFG02",
        nominal_weight_g=1000,
    )
    assert len(default_cream) == 1
    assert default_cream[0].id != existing_id


def test_ensure_bambu_catalog_fills_existing_1000g_sku_without_duplicate() -> None:
    db = _memory_db()
    brand = FilamentBrand(name="Bambu Lab", aliases=["拓竹"])
    db.add(brand)
    db.flush()
    petg_hf = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="PETG",
        series_name="HF",
        empty_spool_weight_g=123,
    )
    db.add(petg_hf)
    db.flush()
    existing = FilamentSku(
        type_series_id=petg_hf.id,
        color_name="Cream",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id
    type_series_id = petg_hf.id

    summary = ensure_bambu_official_sku_catalog(db)

    db.refresh(existing)
    db.refresh(petg_hf)
    assert summary.created_sku_count == 302
    assert summary.updated_sku_count == 1
    assert petg_hf.empty_spool_weight_g == 123
    assert existing.color_name == "Cream"
    assert existing.color_hex == "F9DFB9"
    assert existing.tray_info_idx == "GFG02"
    default_cream = _sku_rows(
        db,
        type_series_id=type_series_id,
        color_hex="F9DFB9",
        tray_info_idx="GFG02",
        nominal_weight_g=1000,
    )
    assert [sku.id for sku in default_cream] == [existing_id]


def test_ensure_bambu_catalog_matches_existing_default_sku_by_unique_official_field() -> None:
    db = _memory_db()
    brand = FilamentBrand(name="Bambu Lab", aliases=["拓竹"])
    db.add(brand)
    db.flush()
    pla_basic = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="PLA",
        series_name="Basic",
        empty_spool_weight_g=250,
    )
    asa_standard = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="ASA",
        series_name="Standard",
        empty_spool_weight_g=250,
    )
    tpu_90a = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="TPU",
        series_name="90A",
        empty_spool_weight_g=250,
    )
    db.add_all([pla_basic, asa_standard, tpu_90a])
    db.flush()
    local_magenta = FilamentSku(
        type_series_id=pla_basic.id,
        color_name="品红色",
        color_hex="EC008C",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
    )
    local_asa_white = FilamentSku(
        type_series_id=asa_standard.id,
        color_name="白色",
        color_hex="FFFFFF",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
    )
    local_tpu_blue = FilamentSku(
        type_series_id=tpu_90a.id,
        color_name="冰封蓝",
        color_hex="A8C6EE",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
    )
    db.add_all([local_magenta, local_asa_white, local_tpu_blue])
    db.commit()

    summary = ensure_bambu_official_sku_catalog(db)

    assert summary.updated_sku_count >= 3
    assert len(_sku_rows(db, type_series_id=pla_basic.id, color_hex="EC008C", nominal_weight_g=1000)) == 1
    assert len(_sku_rows(db, type_series_id=asa_standard.id, color_hex="FFFFFF", nominal_weight_g=1000)) == 1
    assert len(_sku_rows(db, type_series_id=tpu_90a.id, color_hex="A8C6EE", nominal_weight_g=1000)) == 1
    db.refresh(local_magenta)
    db.refresh(local_asa_white)
    db.refresh(local_tpu_blue)
    assert local_magenta.tray_info_idx == "GFA00"
    assert local_asa_white.tray_info_idx == "GFB01"
    assert local_tpu_blue.tray_info_idx == "GFU03"


def test_ensure_bambu_catalog_merges_duplicate_official_skus_without_losing_references() -> None:
    db = _memory_db()
    brand = FilamentBrand(name="Bambu Lab", aliases=["拓竹"])
    db.add(brand)
    db.flush()
    pla_basic = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="PLA",
        series_name="Basic",
        empty_spool_weight_g=250,
    )
    db.add(pla_basic)
    db.flush()
    local_purple = FilamentSku(
        type_series_id=pla_basic.id,
        color_name="蓝紫色",
        color_hex="5E43B7",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
        tray_info_idx="GFA00",
    )
    official_purple = FilamentSku(
        type_series_id=pla_basic.id,
        color_name="紫色",
        color_hex="5E43B7",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
        tray_info_idx="GFA00",
        note="Auto-created from Bambu official filament catalog.",
    )
    db.add_all([local_purple, official_purple])
    db.flush()
    db.add(FilamentStockBalance(sku_id=local_purple.id, sealed_quantity=2))
    db.add(FilamentStockBalance(sku_id=official_purple.id, sealed_quantity=3))
    spool = FilamentSpool(sku_id=local_purple.id, status="opened_in_storage")
    db.add(spool)
    db.flush()
    db.add(
        FilamentSpoolEvent(
            spool_id=spool.id,
            sku_id=local_purple.id,
            event_type="stock_adjusted",
            message="stock adjusted",
        )
    )
    db.commit()
    local_id = local_purple.id
    official_id = official_purple.id
    spool_id = spool.id

    summary = ensure_bambu_official_sku_catalog(db)

    assert summary.merged_duplicate_sku_count == 1
    assert db.get(FilamentSku, local_id) is not None
    assert db.get(FilamentSku, official_id) is None
    assert db.get(FilamentStockBalance, local_id).sealed_quantity == 5
    assert db.get(FilamentStockBalance, official_id) is None
    assert db.get(FilamentSpool, spool_id).sku_id == local_id
    assert db.scalars(select(FilamentSpoolEvent).where(FilamentSpoolEvent.sku_id == local_id)).one()


def test_ensure_bambu_catalog_prefers_official_duplicate_when_no_references_exist() -> None:
    db = _memory_db()
    brand = FilamentBrand(name="Bambu Lab", aliases=["拓竹"])
    db.add(brand)
    db.flush()
    pla_basic = FilamentTypeSeries(
        brand_id=brand.id,
        material_type="PLA",
        series_name="Basic",
        empty_spool_weight_g=250,
    )
    db.add(pla_basic)
    db.flush()
    local_magenta = FilamentSku(
        type_series_id=pla_basic.id,
        color_name="品红色",
        color_hex="EC008C",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
        tray_info_idx="GFA00",
    )
    official_magenta = FilamentSku(
        type_series_id=pla_basic.id,
        color_name="品红",
        color_hex="EC008C",
        nominal_weight_g=1000,
        filament_diameter_mm=1.75,
        tray_info_idx="GFA00",
        note="Auto-created from Bambu official filament catalog.",
    )
    db.add_all([local_magenta, official_magenta])
    db.commit()
    local_id = local_magenta.id
    official_id = official_magenta.id

    summary = ensure_bambu_official_sku_catalog(db)

    assert summary.merged_duplicate_sku_count == 1
    assert db.get(FilamentSku, local_id) is None
    assert db.get(FilamentSku, official_id) is not None


def test_ensure_bambu_catalog_uses_65104_for_support_pla_white() -> None:
    db = _memory_db()

    summary = ensure_bambu_official_sku_catalog(db)

    assert _skipped_codes(summary) == [["65100"]]
    support = db.scalars(
        select(FilamentTypeSeries).where(
            FilamentTypeSeries.material_type == "Support",
            FilamentTypeSeries.series_name == "for PLA",
        )
    ).one()
    support_white_rows = _sku_rows(
        db,
        type_series_id=support.id,
        color_hex="FFFFFF",
        tray_info_idx="GFS02",
        nominal_weight_g=1000,
    )
    assert len(support_white_rows) == 1
    match = resolve_bambu_official_color(
        brand_name="Bambu Lab",
        material="Support",
        series="for PLA",
        tray_info_idx="GFS02",
        color_hex="FFFFFF",
        color_name="白色",
    )
    assert match is not None
    assert match.color.color_code == "65104"


def test_startup_catalog_does_not_populate_manual_color_mappings(api_client) -> None:
    assert api_client.get("/api/filament/color-mappings").json() == []
    skus = api_client.get("/api/filament/skus").json()
    official = [sku for sku in skus if sku.get("color_source") == "bambu_official"]
    assert len(official) == 303
    assert {sku["sealed_quantity"] for sku in official} == {0}


def _memory_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def _skipped_codes(summary) -> list[list[str]]:
    return [group["official_color_codes"] for group in summary.skipped_ambiguous_groups]


def _sku_rows(
    db,
    *,
    type_series_id: int,
    color_hex: str | None = None,
    tray_info_idx: str | None = None,
    nominal_weight_g: float,
) -> list[FilamentSku]:
    stmt = select(FilamentSku).where(
        FilamentSku.type_series_id == type_series_id,
        FilamentSku.nominal_weight_g == nominal_weight_g,
    )
    if color_hex is not None:
        stmt = stmt.where(FilamentSku.color_hex == color_hex)
    if tray_info_idx is not None:
        stmt = stmt.where(FilamentSku.tray_info_idx == tray_info_idx)
    return list(
        db.scalars(stmt).all()
    )
