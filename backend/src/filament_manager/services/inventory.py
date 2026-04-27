from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import AmsSlot, InventoryEvent, Spool, SpoolLocation, utc_now
from filament_manager.schemas import SpoolCreate, SpoolUpdate


def list_spools(db: Session) -> list[Spool]:
    return list(db.scalars(select(Spool).order_by(Spool.id.desc())).all())


def get_spool(db: Session, spool_id: int) -> Spool | None:
    return db.get(Spool, spool_id)


def create_spool(db: Session, data: SpoolCreate) -> Spool:
    spool = Spool(
        identity_source="manual",
        display_name=data.display_name,
        brand=data.brand,
        material=data.material,
        series=data.series,
        color=data.color,
        sealed_quantity=data.sealed_quantity,
        status=data.status,
        opened_at=utc_now() if data.status in {"opened", "active"} else None,
    )
    db.add(spool)
    db.flush()
    db.add(
        InventoryEvent(
            spool_id=spool.id,
            event_type="inventory.spool_created",
            quantity_delta=data.sealed_quantity,
            message="Spool inventory entry created",
            data={"status": data.status},
        )
    )
    db.commit()
    db.refresh(spool)
    return spool


def update_spool(db: Session, spool: Spool, data: SpoolUpdate) -> Spool:
    updates = data.model_dump(exclude_unset=True)
    previous_status = spool.status
    for key, value in updates.items():
        setattr(spool, key, value)
    if previous_status == "sealed" and spool.status in {"opened", "active"} and spool.opened_at is None:
        spool.opened_at = utc_now()
    db.add(spool)
    db.add(
        InventoryEvent(
            spool_id=spool.id,
            event_type="inventory.spool_updated",
            quantity_delta=None,
            message="Spool inventory entry updated",
            data=updates,
        )
    )
    db.commit()
    db.refresh(spool)
    return spool


def bind_slot_to_spool(db: Session, slot: AmsSlot, spool: Spool) -> AmsSlot:
    was_sealed = spool.status == "sealed"
    slot.spool_id = spool.id
    if was_sealed:
        spool.status = "active"
        spool.opened_at = utc_now()
        if spool.sealed_quantity > 0:
            spool.sealed_quantity -= 1
    spool.current_printer_id = slot.printer_id
    spool.current_ams_id = slot.ams_id
    spool.current_tray_id = slot.tray_id
    db.add(slot)
    db.add(spool)
    db.add(
        SpoolLocation(
            spool_id=spool.id,
            printer_id=slot.printer_id,
            ams_id=slot.ams_id,
            tray_id=slot.tray_id,
            event_type="spool.bound_to_slot",
        )
    )
    db.add(
        InventoryEvent(
            spool_id=spool.id,
            event_type="inventory.slot_bound",
            quantity_delta=-1 if was_sealed else None,
            message="Spool bound to AMS slot",
            data={"printer_id": slot.printer_id, "ams_id": slot.ams_id, "tray_id": slot.tray_id},
        )
    )
    db.commit()
    db.refresh(slot)
    return slot
