from collections.abc import Generator

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
