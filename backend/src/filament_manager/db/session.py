from collections.abc import Generator
from datetime import datetime
from pathlib import Path
import shutil

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, sessionmaker

from filament_manager.core.config import get_settings
from filament_manager.db.models import Base

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def configure_database(database_url: str | None = None) -> Engine:
    global engine, SessionLocal

    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine


def create_schema() -> None:
    if engine is None:
        configure_database()
    assert engine is not None
    _reset_sqlite_inventory_schema_if_needed(engine)
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_additive_migrations(engine)


def reset_database_for_tests(database_url: str) -> None:
    db_engine = configure_database(database_url)
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        configure_database()
        create_schema()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_sqlite_additive_migrations(db_engine: Engine) -> None:
    if db_engine.dialect.name != "sqlite":
        return
    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())
    if "printers" in table_names:
        existing_printer_columns = {column["name"] for column in inspector.get_columns("printers")}
        if "print_hours_offset" not in existing_printer_columns:
            with db_engine.begin() as connection:
                connection.execute(text("ALTER TABLE printers ADD COLUMN print_hours_offset FLOAT NOT NULL DEFAULT 0.0"))

    if "ams_slots" in table_names:
        existing_ams_slot_columns = {column["name"] for column in inspector.get_columns("ams_slots")}
        if "filament_spool_id" not in existing_ams_slot_columns:
            with db_engine.begin() as connection:
                connection.execute(text("ALTER TABLE ams_slots ADD COLUMN filament_spool_id INTEGER"))

    if "device_status_snapshots" not in table_names:
        return
    existing = {column["name"] for column in inspector.get_columns("device_status_snapshots")}
    additions = {
        "derived_status": "JSON NOT NULL DEFAULT '{}'",
        "nozzles": "JSON NOT NULL DEFAULT '{}'",
        "camera_options": "JSON NOT NULL DEFAULT '{}'",
        "data_coverage": "JSON NOT NULL DEFAULT '{}'",
    }
    missing = [(name, ddl) for name, ddl in additions.items() if name not in existing]
    if not missing:
        return
    with db_engine.begin() as connection:
        for name, ddl in missing:
            connection.execute(text(f"ALTER TABLE device_status_snapshots ADD COLUMN {name} {ddl}"))


def _reset_sqlite_inventory_schema_if_needed(db_engine: Engine) -> None:
    if db_engine.dialect.name != "sqlite":
        return
    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())
    if not table_names:
        return
    inventory_tables = {
        "spools",
        "spool_locations",
        "inventory_events",
        "filament_brands",
        "filament_type_series",
        "filament_brand_series_links",
        "filament_skus",
        "filament_sku_series_links",
        "filament_stock_balances",
        "filament_spools",
        "filament_spool_events",
        "filament_spool_location_events",
        "filament_spool_quantity_events",
        "filament_drying_events",
        "filament_color_mappings",
    }
    if not _sqlite_inventory_schema_is_legacy(inspector, table_names):
        return
    _backup_sqlite_database(db_engine)
    with db_engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        for table in sorted(inventory_tables & table_names, reverse=True):
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


def _sqlite_inventory_schema_is_legacy(inspector: object, table_names: set[str]) -> bool:
    legacy_tables = {
        "spools",
        "spool_locations",
        "inventory_events",
        "filament_brand_series_links",
        "filament_sku_series_links",
        "filament_spool_location_events",
        "filament_spool_quantity_events",
        "filament_drying_events",
    }
    if table_names & legacy_tables:
        return True
    if "filament_brands" in table_names:
        columns = {column["name"] for column in inspector.get_columns("filament_brands")}
        if "aliases" not in columns or "default_empty_spool_weight_g" in columns:
            return True
    if "filament_skus" in table_names:
        columns = {column["name"] for column in inspector.get_columns("filament_skus")}
        if {"brand_id", "material", "series", "sealed_quantity"} & columns:
            return True
        if not {"type_series_id", "color_hex"}.issubset(columns):
            return True
    if "filament_type_series" in table_names:
        columns = {column["name"] for column in inspector.get_columns("filament_type_series")}
        if "brand_id" not in columns:
            return True
    if "filament_spools" in table_names:
        columns = {column["name"] for column in inspector.get_columns("filament_spools")}
        if {"legacy_spool_id", "identity_key", "tray_uuid", "tag_uid", "current_remaining_g"} & columns:
            return True
        if "official_spool_uid" not in columns:
            return True
    if "filament_color_mappings" in table_names:
        columns = {column["name"] for column in inspector.get_columns("filament_color_mappings")}
        if {"material", "series", "hex_value", "official_name"} & columns:
            return True
        if not {"brand_id", "type_series_id", "color_name", "color_hex"}.issubset(columns):
            return True
    return False


def _backup_sqlite_database(db_engine: Engine) -> None:
    database = db_engine.url.database
    if not database or database == ":memory:":
        return
    path = Path(database)
    if not path.exists():
        return
    backup_dir = path.parent / ".runtime" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, backup_dir / f"{path.name}.inventory-reset-{timestamp}.bak")
