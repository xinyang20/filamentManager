from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.db.models import MaintenanceHistory, MaintenanceType, Printer, PrinterMaintenance, utc_now
from filament_manager.services.print_log import completed_print_seconds_by_printer

DEFAULT_MAINTENANCE_TYPES = [
    {
        "code": "carbon_rod_cleaning",
        "name": "碳棒清洁",
        "description": "清洁 X 轴碳棒表面残留。",
        "default_interval": 100.0,
        "icon": "sparkles",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "lead_screw_lubrication",
        "name": "丝杆润滑",
        "description": "为 Z 轴丝杆补充润滑。",
        "default_interval": 120.0,
        "icon": "droplets",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "nozzle_inspection",
        "name": "喷嘴检查",
        "description": "检查喷嘴磨损、堵塞和粘料。",
        "default_interval": 80.0,
        "icon": "scan",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "build_plate_cleaning",
        "name": "热床清洁",
        "description": "清洁打印板表面油污和残留。",
        "default_interval": 40.0,
        "icon": "panel-top",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "ams_cleaning",
        "name": "AMS 清洁",
        "description": "清理 AMS 内部碎屑和滚轮区域。",
        "default_interval": 120.0,
        "icon": "boxes",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "poop_chute_inspection",
        "name": "废料通道检查",
        "description": "检查废料通道是否堆积或卡料。",
        "default_interval": 60.0,
        "icon": "route",
        "wiki_url": "https://wiki.bambulab.com/",
    },
]


def maintenance_overview(db: Session) -> dict[str, Any]:
    ensure_maintenance_items(db)
    printers = list(db.scalars(select(Printer).order_by(Printer.id)).all())
    items = [_maintenance_read(db, item, printer=_printer_by_id(printers, item.printer_id)) for item in _all_items(db)]
    grouped: list[dict[str, Any]] = []
    for printer in printers:
        printer_items = [item for item in items if item["printer_id"] == printer.id]
        grouped.append(
            {
                "printer_id": printer.id,
                "printer_name": printer.name,
                "due_count": sum(1 for item in printer_items if item["due_status"] == "due"),
                "soon_count": sum(1 for item in printer_items if item["due_status"] == "soon"),
                "ok_count": sum(1 for item in printer_items if item["due_status"] == "ok"),
            }
        )
    return {
        "total_items": len(items),
        "due_count": sum(1 for item in items if item["due_status"] == "due"),
        "soon_count": sum(1 for item in items if item["due_status"] == "soon"),
        "ok_count": sum(1 for item in items if item["due_status"] == "ok"),
        "printers": grouped,
        "items": items,
    }


def get_printer_maintenance(db: Session, printer: Printer) -> list[dict[str, Any]]:
    ensure_maintenance_items(db, printer_ids=[printer.id])
    rows = list(
        db.scalars(
            select(PrinterMaintenance)
            .where(PrinterMaintenance.printer_id == printer.id)
            .order_by(PrinterMaintenance.id)
        ).all()
    )
    return [_maintenance_read(db, row, printer=printer) for row in rows]


def update_maintenance_item(
    db: Session,
    item: PrinterMaintenance,
    *,
    enabled: bool | None = None,
    custom_interval: float | None = None,
    last_performed_at: datetime | None = None,
    last_performed_print_hours: float | None = None,
) -> dict[str, Any]:
    if enabled is not None:
        item.enabled = enabled
    if custom_interval is not None:
        item.custom_interval = custom_interval
    if last_performed_at is not None:
        item.last_performed_at = last_performed_at
    if last_performed_print_hours is not None:
        item.last_performed_print_hours = last_performed_print_hours
    item.updated_at = utc_now()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _maintenance_read(db, item)


def perform_maintenance_item(
    db: Session,
    item: PrinterMaintenance,
    *,
    note: str | None = None,
    performed_at: datetime | None = None,
    print_hours: float | None = None,
) -> dict[str, Any]:
    current_hours = current_print_hours(db).get(item.printer_id, 0.0)
    performed_hours = print_hours if print_hours is not None else current_hours
    performed_time = performed_at or utc_now()
    item.last_performed_at = performed_time
    item.last_performed_print_hours = performed_hours
    item.updated_at = utc_now()
    db.add(item)
    db.add(
        MaintenanceHistory(
            maintenance_item_id=item.id,
            performed_at=performed_time,
            print_hours=performed_hours,
            note=note,
        )
    )
    db.commit()
    db.refresh(item)
    return _maintenance_read(db, item)


def maintenance_history(db: Session, item: PrinterMaintenance) -> list[MaintenanceHistory]:
    return list(
        db.scalars(
            select(MaintenanceHistory)
            .where(MaintenanceHistory.maintenance_item_id == item.id)
            .order_by(MaintenanceHistory.performed_at.desc(), MaintenanceHistory.id.desc())
        ).all()
    )


def get_maintenance_item(db: Session, item_id: int) -> PrinterMaintenance | None:
    return db.get(PrinterMaintenance, item_id)


def current_print_hours(db: Session) -> dict[int, float]:
    seconds = completed_print_seconds_by_printer(db)
    printers = db.scalars(select(Printer)).all()
    return {
        printer.id: round((seconds.get(printer.id, 0) / 3600.0) + (printer.print_hours_offset or 0.0), 3)
        for printer in printers
    }


def ensure_maintenance_items(db: Session, printer_ids: list[int] | None = None) -> None:
    type_rows = _ensure_default_types(db)
    query = select(Printer)
    if printer_ids:
        query = query.where(Printer.id.in_(printer_ids))
    printers = list(db.scalars(query).all())
    existing = {
        (item.printer_id, item.maintenance_type_id)
        for item in db.scalars(select(PrinterMaintenance)).all()
    }
    for printer in printers:
        for item_type in type_rows:
            key = (printer.id, item_type.id)
            if key in existing:
                continue
            db.add(
                PrinterMaintenance(
                    printer_id=printer.id,
                    maintenance_type_id=item_type.id,
                    enabled=True,
                    custom_interval=None,
                    last_performed_print_hours=0.0,
                )
            )
            existing.add(key)
    db.commit()


def maintenance_due_counts(db: Session) -> dict[int, int]:
    ensure_maintenance_items(db)
    counts: dict[int, int] = {}
    for item in _all_items(db):
        read = _maintenance_read(db, item)
        if read["due_status"] == "due":
            counts[item.printer_id] = counts.get(item.printer_id, 0) + 1
    return counts


def _ensure_default_types(db: Session) -> list[MaintenanceType]:
    existing_by_code = {row.code: row for row in db.scalars(select(MaintenanceType)).all()}
    rows: list[MaintenanceType] = []
    for item in DEFAULT_MAINTENANCE_TYPES:
        row = existing_by_code.get(item["code"])
        if row is None:
            row = MaintenanceType(
                code=item["code"],
                name=item["name"],
                description=item["description"],
                interval_type="print_hours",
                default_interval=item["default_interval"],
                icon=item["icon"],
                wiki_url=item["wiki_url"],
                is_system_default=True,
            )
            db.add(row)
            db.flush()
        rows.append(row)
    db.commit()
    return rows


def _all_items(db: Session) -> list[PrinterMaintenance]:
    return list(db.scalars(select(PrinterMaintenance).order_by(PrinterMaintenance.printer_id, PrinterMaintenance.id)).all())


def _maintenance_read(db: Session, item: PrinterMaintenance, printer: Printer | None = None) -> dict[str, Any]:
    printer = printer or db.get(Printer, item.printer_id)
    current_hours = current_print_hours(db).get(item.printer_id, 0.0)
    interval = item.custom_interval or item.maintenance_type.default_interval
    hours_since_last = max(0.0, current_hours - (item.last_performed_print_hours or 0.0))
    hours_until_due = interval - hours_since_last
    due_status = _due_status(item.enabled, hours_until_due, interval)
    history_count = int(
        db.scalar(
            select(func.count())
            .select_from(MaintenanceHistory)
            .where(MaintenanceHistory.maintenance_item_id == item.id)
        )
        or 0
    )
    return {
        "id": item.id,
        "printer_id": item.printer_id,
        "printer_name": printer.name if printer else None,
        "maintenance_type": item.maintenance_type,
        "enabled": item.enabled,
        "custom_interval": item.custom_interval,
        "interval": interval,
        "last_performed_at": item.last_performed_at,
        "last_performed_print_hours": item.last_performed_print_hours or 0.0,
        "current_print_hours": current_hours,
        "hours_since_last": round(hours_since_last, 3),
        "hours_until_due": round(hours_until_due, 3),
        "due_status": due_status,
        "history_count": history_count,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _due_status(enabled: bool, hours_until_due: float, interval: float) -> str:
    if not enabled:
        return "disabled"
    if hours_until_due <= 0:
        return "due"
    if hours_until_due <= max(10.0, interval * 0.1):
        return "soon"
    return "ok"


def _printer_by_id(printers: list[Printer], printer_id: int) -> Printer | None:
    for printer in printers:
        if printer.id == printer_id:
            return printer
    return None
