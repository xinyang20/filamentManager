from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
from threading import Thread

from fastapi import FastAPI
from sqlalchemy import select

from filament_manager.api.routes import router
from filament_manager.db import session as db_session
from filament_manager.db.models import Printer
from filament_manager.db.session import configure_database, create_schema
from filament_manager.mqtt.client import mqtt_manager

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        configure_database(database_url)
        create_schema()
        _schedule_auto_connect_saved_printers()
        try:
            yield
        finally:
            mqtt_manager.disconnect_all()

    app = FastAPI(title="FilamentManager", version="0.1.0", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    return app


app = create_app()


def _schedule_auto_connect_saved_printers() -> None:
    worker = Thread(target=_auto_connect_saved_printers, name="printer-auto-connect", daemon=True)
    worker.start()


def _auto_connect_saved_printers() -> None:
    if db_session.SessionLocal is None:
        return
    db = db_session.SessionLocal()
    try:
        printers = list(db.scalars(select(Printer).where(Printer.enabled.is_(True)).order_by(Printer.id)).all())
        for printer in printers:
            try:
                mqtt_manager.connect(db, printer)
            except Exception as exc:  # noqa: BLE001 - startup should continue if one printer is unreachable.
                printer.connection_status = "error"
                printer.last_error = f"Auto-connect failed: {exc}"
                db.add(printer)
                db.commit()
                logger.warning("Auto-connect failed for printer id %s: %s", printer.id, exc)
    finally:
        db.close()
