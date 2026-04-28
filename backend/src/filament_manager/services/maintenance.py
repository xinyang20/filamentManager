from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_manager.db.models import (
    AmsUnit,
    DeviceStatusSnapshot,
    MaintenanceHistory,
    MaintenanceType,
    Printer,
    PrinterMaintenance,
    utc_now,
)
from filament_manager.services.print_log import completed_print_seconds_by_printer

DEFAULT_MAINTENANCE_TYPES = [
    {
        "code": "carbon_rod_cleaning",
        "name": "X 轴碳棒清洁",
        "description": "清洁 X1/P1 系列 X 轴碳棒表面残留；碳棒不加油、不上脂。",
        "default_interval": 100.0,
        "icon": "sparkles",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "x_axis_smooth_rod_cleaning",
        "name": "X 轴光轴清洁",
        "description": "清洁 P2 系列 X 轴中空钢光轴；该结构使用光轴 + 皮带，不是碳棒。",
        "default_interval": 100.0,
        "icon": "sparkles",
        "wiki_url": "https://wiki.bambulab.com/",
    },
    {
        "code": "lead_screw_lubrication",
        "name": "Z 轴丝杆润滑",
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
        "description": "作为 AMS 独立维护对象，清理内部碎屑、滚轮区域并检查耗材通道。",
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

MAINTENANCE_RULES: dict[str, dict[str, Any]] = {
    "carbon_rod_cleaning": {
        "families": {"x1", "p1"},
        "target_type": "printer",
    },
    "x_axis_smooth_rod_cleaning": {
        "families": {"p2"},
        "target_type": "printer",
    },
    "lead_screw_lubrication": {
        "families": {"x1", "p1", "p2", "a1", "h2", "unknown"},
        "target_type": "printer",
    },
    "nozzle_inspection": {
        "families": {"x1", "p1", "p2", "a1", "h2", "unknown"},
        "target_type": "printer",
    },
    "build_plate_cleaning": {
        "families": {"x1", "p1", "p2", "a1", "h2", "unknown"},
        "target_type": "printer",
    },
    "poop_chute_inspection": {
        "families": {"x1", "p1", "p2", "h2"},
        "target_type": "printer",
    },
    "ams_cleaning": {
        "requires_ams": True,
        "target_type": "ams",
    },
}


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
    rows = [row for row in rows if _maintenance_type_applies(db, printer, row.maintenance_type.code)]
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
            if not _maintenance_type_applies(db, printer, item_type.code):
                continue
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
        else:
            row.name = item["name"]
            row.description = item["description"]
            row.interval_type = "print_hours"
            row.default_interval = item["default_interval"]
            row.icon = item["icon"]
            row.wiki_url = item["wiki_url"]
            row.is_system_default = True
            db.add(row)
        rows.append(row)
    db.commit()
    return rows


def _all_items(db: Session) -> list[PrinterMaintenance]:
    printers = {printer.id: printer for printer in db.scalars(select(Printer)).all()}
    rows = list(db.scalars(select(PrinterMaintenance).order_by(PrinterMaintenance.printer_id, PrinterMaintenance.id)).all())
    return [
        item
        for item in rows
        if (printer := printers.get(item.printer_id)) is not None
        and _maintenance_type_applies(db, printer, item.maintenance_type.code)
    ]


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
        "target_type": _maintenance_target_type(item),
        "target_label": _maintenance_target_label(db, item, printer),
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


def _maintenance_type_applies(db: Session, printer: Printer, code: str) -> bool:
    rule = MAINTENANCE_RULES.get(code)
    if rule is None:
        return True
    if rule.get("requires_ams"):
        return _printer_has_ams(db, printer.id)
    families = rule.get("families")
    if isinstance(families, set):
        return _printer_family(db, printer) in families
    return True


def _maintenance_target_type(item: PrinterMaintenance) -> str:
    rule = MAINTENANCE_RULES.get(item.maintenance_type.code) or {}
    target_type = rule.get("target_type")
    return str(target_type) if target_type else "printer"


def _maintenance_target_label(db: Session, item: PrinterMaintenance, printer: Printer | None) -> str | None:
    if printer is None:
        return None
    if _maintenance_target_type(item) != "ams":
        return printer.name
    units = list(
        db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer.id).order_by(AmsUnit.ams_id)).all()
    )
    if not units:
        return f"AMS · {printer.name}"
    names = []
    for unit in units:
        ams_name = unit.ams_type_name if unit.ams_type_name != "unknown" else "AMS"
        names.append(f"{ams_name} #{unit.ams_id}")
    return f"{' / '.join(names)} · {printer.name}"


def _printer_has_ams(db: Session, printer_id: int) -> bool:
    return db.scalar(select(func.count()).select_from(AmsUnit).where(AmsUnit.printer_id == printer_id)) > 0


def _printer_family(db: Session, printer: Printer) -> str:
    parts = [printer.name, printer.serial]
    snapshot = db.scalar(select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer.id))
    if snapshot is not None:
        for payload in (snapshot.hardware, snapshot.firmware, snapshot.raw_refs):
            if isinstance(payload, dict):
                parts.extend(str(value) for value in payload.values() if isinstance(value, (str, int, float)))
    text = " ".join(str(part) for part in parts if part).upper()
    if "P2" in text or "P2S" in text:
        return "p2"
    if "X1" in text:
        return "x1"
    if "P1" in text:
        return "p1"
    if "A1" in text:
        return "a1"
    if "H2" in text:
        return "h2"
    return "unknown"


def _printer_by_id(printers: list[Printer], printer_id: int) -> Printer | None:
    for printer in printers:
        if printer.id == printer_id:
            return printer
    return None
