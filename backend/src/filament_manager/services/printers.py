from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.security import mask_secret
from filament_manager.db.models import Printer, utc_now
from filament_manager.schemas import PrinterCreate, PrinterRead, PrinterUpdate


def printer_to_read(printer: Printer) -> PrinterRead:
    return PrinterRead(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        port=printer.port,
        serial=printer.serial,
        access_code=mask_secret(printer.access_code),
        tls_enabled=printer.tls_enabled,
        certificate_verify=printer.certificate_verify,
        enabled=printer.enabled,
        connection_status=printer.connection_status,
        last_sync_at=printer.last_sync_at,
        last_error=printer.last_error,
        print_hours_offset=printer.print_hours_offset or 0.0,
        created_at=printer.created_at,
        updated_at=printer.updated_at,
    )


def list_printers(db: Session) -> list[Printer]:
    return list(db.scalars(select(Printer).order_by(Printer.id)).all())


def get_printer(db: Session, printer_id: int) -> Printer | None:
    return db.get(Printer, printer_id)


def create_printer(db: Session, data: PrinterCreate) -> Printer:
    printer = Printer(**data.model_dump())
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return printer


def update_printer(db: Session, printer: Printer, data: PrinterUpdate) -> Printer:
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "access_code" and (value is None or value == "" or str(value).startswith("****")):
            continue
        setattr(printer, key, value)
    printer.updated_at = utc_now()
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return printer


def delete_printer(db: Session, printer: Printer) -> None:
    db.delete(printer)
    db.commit()
