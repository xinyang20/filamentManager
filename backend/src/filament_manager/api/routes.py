from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.config import get_settings
from filament_manager.core.security import redact_sensitive
from filament_manager.db.models import (
    AmsLabel,
    AmsSlot,
    AmsSlotHistorySample,
    AmsUnit,
    DeviceStatusSnapshot,
    DeviceMetricSample,
    InventoryEvent,
    PrinterEvent,
    PrinterStorageFile,
    PrinterStateSnapshot,
    PrintLogEntry,
    RawMqttMessage,
    SpoolLocation,
)
from filament_manager.db.session import get_db
from filament_manager.mqtt.client import is_certificate_verify_error, mqtt_manager
from filament_manager.schemas import (
    AmsOverviewRead,
    AmsLabelRead,
    AmsLabelUpdate,
    AmsSensorHistoryRead,
    AmsSlotRead,
    AmsSlotHistorySampleRead,
    AmsUnitRead,
    DashboardSummaryItemRead,
    DeviceStatusSnapshotRead,
    DeviceMetricSampleRead,
    DiscoveryCandidateRead,
    HmsCodeInfoRead,
    InventoryEventRead,
    MaintenanceHistoryRead,
    MaintenanceOverviewRead,
    MaintenancePerformRequest,
    MqttPayloadIn,
    PrinterMaintenanceRead,
    PrinterMaintenanceUpdate,
    PrintLogEntryRead,
    PrintLogListRead,
    PrintLogSummaryRead,
    PrinterCreate,
    PrinterDashboardRead,
    PrinterEventRead,
    PrinterRead,
    PrinterStateRead,
    PrinterStorageFileRead,
    PrinterUpdate,
    RawMqttMessageRead,
    SlotBindRequest,
    SpoolCreate,
    SpoolRead,
    SpoolUpdate,
    StorageSummaryRead,
    StorageScanResultRead,
    SupportBundleRead,
    SystemInfoRead,
    UnifiedEventRead,
)
from filament_manager.services.ams import build_ams_overview, build_ams_sensor_history, delete_ams_label, set_ams_label
from filament_manager.services.discovery import scan_lan_devices
from filament_manager.services.events import list_unified_events, sse_event_generator
from filament_manager.services.fans import fan_percent, normalize_fan_payload
from filament_manager.services.hms import get_hms_code, list_hms_codes
from filament_manager.services.inventory import (
    bind_slot_to_spool,
    create_spool,
    get_spool,
    list_spools,
    update_spool,
)
from filament_manager.services.maintenance import (
    get_maintenance_item,
    get_printer_maintenance,
    maintenance_due_counts,
    maintenance_history,
    maintenance_overview,
    perform_maintenance_item,
    update_maintenance_item,
)
from filament_manager.services.mqtt_processing import process_mqtt_payload
from filament_manager.services.observability import prometheus_metrics, support_bundle, system_info
from filament_manager.services.print_log import list_print_logs, print_log_summary
from filament_manager.services.printers import (
    create_printer,
    delete_printer,
    get_printer,
    list_printers,
    printer_to_read,
    update_printer,
)
from filament_manager.services.storage import scan_printer_storage

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/discovery/scan", response_model=list[DiscoveryCandidateRead])
def api_scan_discovery(
    cidr: str | None = Query(
        default=None,
        description="Optional IPv4 CIDR. Defaults to the current local /24 network.",
    ),
    timeout: float = Query(default=0.25, ge=0.05, le=2.0),
    validation_timeout: float | None = Query(default=None, ge=0.05, le=2.0),
    max_hosts: int = Query(default=512, ge=1, le=2048),
) -> list[dict[str, Any]]:
    try:
        return [
            candidate.to_dict()
            for candidate in scan_lan_devices(
                cidr=cidr,
                timeout=timeout,
                validation_timeout=validation_timeout,
                max_hosts=max_hosts,
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/printers", response_model=list[PrinterRead])
def api_list_printers(db: Session = Depends(get_db)) -> list[PrinterRead]:
    printers = list_printers(db)
    for printer in printers:
        _sync_runtime_connection_status(db, printer)
    return [printer_to_read(printer) for printer in printers]


@router.post("/printers", response_model=PrinterRead, status_code=status.HTTP_201_CREATED)
def api_create_printer(data: PrinterCreate, db: Session = Depends(get_db)) -> PrinterRead:
    return printer_to_read(create_printer(db, data))


@router.get("/printers/{printer_id}", response_model=PrinterRead)
def api_get_printer(printer_id: int, db: Session = Depends(get_db)) -> PrinterRead:
    printer = _printer_or_404(db, printer_id)
    _sync_runtime_connection_status(db, printer)
    return printer_to_read(printer)


@router.patch("/printers/{printer_id}", response_model=PrinterRead)
def api_update_printer(printer_id: int, data: PrinterUpdate, db: Session = Depends(get_db)) -> PrinterRead:
    printer = _printer_or_404(db, printer_id)
    return printer_to_read(update_printer(db, printer, data))


@router.delete("/printers/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_printer(printer_id: int, db: Session = Depends(get_db)) -> Response:
    printer = _printer_or_404(db, printer_id)
    mqtt_manager.disconnect(printer.id)
    delete_printer(db, printer)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/printers/{printer_id}/connect", response_model=PrinterRead)
def api_connect_printer(printer_id: int, db: Session = Depends(get_db)) -> PrinterRead:
    printer = _printer_or_404(db, printer_id)
    try:
        mqtt_manager.connect(db, printer)
    except ValueError as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        status_code = 400 if is_certificate_verify_error(exc) else 502
        detail = str(exc) if status_code == 400 else f"Failed to connect to printer MQTT: {exc}"
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to connect to printer MQTT: {exc}") from exc
    db.refresh(printer)
    return printer_to_read(printer)


@router.post("/printers/{printer_id}/disconnect", response_model=PrinterRead)
def api_disconnect_printer(printer_id: int, db: Session = Depends(get_db)) -> PrinterRead:
    printer = _printer_or_404(db, printer_id)
    mqtt_manager.disconnect(printer.id)
    printer.connection_status = "disconnected"
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return printer_to_read(printer)


@router.post("/printers/{printer_id}/refresh")
def api_refresh_printer(printer_id: int, db: Session = Depends(get_db)) -> dict[str, str | None]:
    printer = _printer_or_404(db, printer_id)
    sequence_id = mqtt_manager.request_pushall(printer_id)
    if sequence_id is None and _should_reconnect_for_refresh(printer):
        _reconnect_for_refresh(db, printer)
        sequence_id = mqtt_manager.request_pushall(printer_id)
    if sequence_id is None:
        _sync_runtime_connection_status(db, printer)
        raise HTTPException(status_code=409, detail="Printer is not connected")
    return {"sequence_id": sequence_id}


@router.post("/printers/{printer_id}/refresh-full")
def api_refresh_printer_full(printer_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    printer = _printer_or_404(db, printer_id)
    sequence_ids = mqtt_manager.request_full_refresh(printer_id)
    if sequence_ids is None and _should_reconnect_for_refresh(printer):
        _reconnect_for_refresh(db, printer)
        sequence_ids = mqtt_manager.request_full_refresh(printer_id)
    if sequence_ids is None:
        _sync_runtime_connection_status(db, printer)
        raise HTTPException(status_code=409, detail="Printer is not connected")
    return sequence_ids


@router.get("/printers/{printer_id}/state", response_model=PrinterStateRead | None)
def api_get_printer_state(printer_id: int, db: Session = Depends(get_db)) -> PrinterStateRead | None:
    _printer_or_404(db, printer_id)
    snapshot = db.scalars(
        select(PrinterStateSnapshot).where(PrinterStateSnapshot.printer_id == printer_id)
    ).first()
    return _state_read(snapshot)


@router.get("/printers/{printer_id}/device-snapshot", response_model=DeviceStatusSnapshotRead | None)
def api_get_device_snapshot(
    printer_id: int,
    db: Session = Depends(get_db),
) -> DeviceStatusSnapshotRead | None:
    _printer_or_404(db, printer_id)
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    return _device_snapshot_read(snapshot)


@router.get("/printers/{printer_id}/dashboard", response_model=PrinterDashboardRead)
def api_get_printer_dashboard(
    printer_id: int,
    db: Session = Depends(get_db),
) -> PrinterDashboardRead:
    printer = _printer_or_404(db, printer_id)
    _sync_runtime_connection_status(db, printer)
    state = db.scalars(
        select(PrinterStateSnapshot).where(PrinterStateSnapshot.printer_id == printer_id)
    ).first()
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    units = list(
        db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer_id).order_by(AmsUnit.ams_id)).all()
    )
    slots = list(
        db.scalars(
            select(AmsSlot)
            .where(AmsSlot.printer_id == printer_id)
            .order_by(AmsSlot.ams_id, AmsSlot.tray_id)
        ).all()
    )
    events = list(
        db.scalars(
            select(PrinterEvent)
            .where(PrinterEvent.printer_id == printer_id)
            .order_by(PrinterEvent.id.desc())
            .limit(50)
        ).all()
    )
    recent_print_logs = list(
        db.scalars(
            select(PrintLogEntry)
            .where(PrintLogEntry.printer_id == printer_id)
            .order_by(PrintLogEntry.started_at.desc().nullslast(), PrintLogEntry.id.desc())
            .limit(5)
        ).all()
    )
    due_counts = maintenance_due_counts(db)
    return PrinterDashboardRead(
        printer=printer_to_read(printer),
        state=_state_read(state),
        device_snapshot=_device_snapshot_read(snapshot),
        ams_units=[_ams_unit_read(unit) for unit in units],
        ams_slots=[_ams_slot_read(slot) for slot in slots],
        recent_events=[PrinterEventRead.model_validate(event) for event in events],
        recent_print_logs=[_print_log_read(row) for row in recent_print_logs],
        maintenance_due_count=due_counts.get(printer_id, 0),
    )


@router.get("/printers/{printer_id}/metrics", response_model=list[DeviceMetricSampleRead])
def api_get_printer_metrics(
    printer_id: int,
    metric: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    bucket: str = Query(default="raw", pattern="^(raw|minute|hour|day)$"),
    group: str | None = Query(default=None, pattern="^(temperature|fan|wifi|ams|print|coverage)$"),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[DeviceMetricSampleRead]:
    _printer_or_404(db, printer_id)
    query = select(DeviceMetricSample).where(DeviceMetricSample.printer_id == printer_id)
    if metric:
        query = query.where(DeviceMetricSample.metric == metric)
    prefix = _metric_group_prefix(group)
    if prefix:
        query = query.where(DeviceMetricSample.metric.like(prefix))
    lower_bound = from_ or since
    if lower_bound:
        query = query.where(DeviceMetricSample.sampled_at >= lower_bound)
    if to:
        query = query.where(DeviceMetricSample.sampled_at <= to)
    rows = list(
        db.scalars(
            query.order_by(DeviceMetricSample.sampled_at.desc(), DeviceMetricSample.id.desc()).limit(limit)
        ).all()
    )
    rows.reverse()
    if bucket == "raw":
        return [_metric_sample_read(row) for row in rows]
    return _bucket_metric_samples(rows, bucket)


@router.post("/printers/{printer_id}/storage/scan", response_model=StorageScanResultRead)
def api_scan_printer_storage(
    printer_id: int,
    db: Session = Depends(get_db),
) -> StorageScanResultRead:
    printer = _printer_or_404(db, printer_id)
    result = scan_printer_storage(db, printer=printer)
    db.commit()
    files = [
        PrinterStorageFileRead.model_validate(file).model_copy(update={"raw": redact_sensitive(file.raw)})
        for file in result.files
    ]
    return StorageScanResultRead(
        success=result.success,
        error=result.error,
        scanned_count=result.scanned_count,
        new_count=result.new_count,
        existing_count=result.existing_count,
        failed_count=result.failed_count,
        files=files,
    )


@router.get("/printers/{printer_id}/storage/files", response_model=list[PrinterStorageFileRead])
def api_get_printer_storage_files(
    printer_id: int,
    db: Session = Depends(get_db),
) -> list[PrinterStorageFileRead]:
    _printer_or_404(db, printer_id)
    rows = list(
        db.scalars(
            select(PrinterStorageFile)
            .where(PrinterStorageFile.printer_id == printer_id)
            .order_by(PrinterStorageFile.path)
        ).all()
    )
    return [
        PrinterStorageFileRead.model_validate(row).model_copy(update={"raw": redact_sensitive(row.raw)})
        for row in rows
    ]


@router.get("/printers/{printer_id}/storage/summary", response_model=StorageSummaryRead)
def api_get_printer_storage_summary(
    printer_id: int,
    db: Session = Depends(get_db),
) -> StorageSummaryRead:
    _printer_or_404(db, printer_id)
    rows = list(
        db.scalars(
            select(PrinterStorageFile)
            .where(PrinterStorageFile.printer_id == printer_id)
            .order_by(PrinterStorageFile.modified_at.desc().nullslast(), PrinterStorageFile.id.desc())
        ).all()
    )
    files = [
        PrinterStorageFileRead.model_validate(row).model_copy(update={"raw": redact_sensitive(row.raw)})
        for row in rows
    ]
    by_type: dict[str, int] = {}
    for row in rows:
        file_type = row.type or "other"
        by_type[file_type] = by_type.get(file_type, 0) + 1
    last_scan = db.scalars(
        select(PrinterEvent)
        .where(
            PrinterEvent.printer_id == printer_id,
            PrinterEvent.event_type.in_(("storage.scan", "storage.scan_failed")),
        )
        .order_by(PrinterEvent.id.desc())
        .limit(1)
    ).first()
    last_scan_event = None
    if last_scan is not None:
        last_scan_event = list_unified_events(db, printer_id=printer_id, event_type=last_scan.event_type, limit=1)[0]
    return StorageSummaryRead(
        printer_id=printer_id,
        file_count=len(rows),
        total_size=sum(row.size or 0 for row in rows),
        by_type=by_type,
        recent_files=files[:10],
        timelapse_files=[file for file in files if file.type == "timelapse"][:10],
        last_scan_event=last_scan_event,
        last_scan=last_scan.data if last_scan is not None else None,
    )


@router.get("/dashboard/summary", response_model=list[DashboardSummaryItemRead])
def api_get_dashboard_summary(db: Session = Depends(get_db)) -> list[DashboardSummaryItemRead]:
    rows: list[DashboardSummaryItemRead] = []
    due_counts = maintenance_due_counts(db)
    for printer in list_printers(db):
        _sync_runtime_connection_status(db, printer)
        state = db.scalars(
            select(PrinterStateSnapshot).where(PrinterStateSnapshot.printer_id == printer.id)
        ).first()
        snapshot = db.scalars(
            select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer.id)
        ).first()
        recent_print_logs = list(
            db.scalars(
                select(PrintLogEntry)
                .where(PrintLogEntry.printer_id == printer.id)
                .order_by(PrintLogEntry.started_at.desc().nullslast(), PrintLogEntry.id.desc())
                .limit(5)
            ).all()
        )
        rows.append(
            DashboardSummaryItemRead(
                printer=printer_to_read(printer),
                state=_state_read(state),
                device_snapshot=_device_snapshot_read(snapshot),
                recent_print_logs=[_print_log_read(row) for row in recent_print_logs],
                maintenance_due_count=due_counts.get(printer.id, 0),
            )
        )
    return rows


@router.get("/printers/{printer_id}/ams/overview", response_model=AmsOverviewRead)
def api_get_ams_overview(printer_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    _printer_or_404(db, printer_id)
    return build_ams_overview(db, printer_id)


@router.patch("/printers/{printer_id}/ams-labels/{ams_id}", response_model=AmsLabelRead)
def api_set_ams_label(
    printer_id: int,
    ams_id: str,
    data: AmsLabelUpdate,
    db: Session = Depends(get_db),
) -> AmsLabel:
    _printer_or_404(db, printer_id)
    return set_ams_label(db, printer_id=printer_id, ams_id=ams_id, display_name=data.display_name)


@router.delete("/printers/{printer_id}/ams-labels/{ams_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_ams_label(
    printer_id: int,
    ams_id: str,
    db: Session = Depends(get_db),
) -> Response:
    _printer_or_404(db, printer_id)
    delete_ams_label(db, printer_id=printer_id, ams_id=ams_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/printers/{printer_id}/ams/units", response_model=list[AmsUnitRead])
def api_get_ams_units(printer_id: int, db: Session = Depends(get_db)) -> list[AmsUnit]:
    _printer_or_404(db, printer_id)
    return list(
        db.scalars(select(AmsUnit).where(AmsUnit.printer_id == printer_id).order_by(AmsUnit.ams_id)).all()
    )


@router.get("/printers/{printer_id}/ams/slots", response_model=list[AmsSlotRead])
def api_get_ams_slots(printer_id: int, db: Session = Depends(get_db)) -> list[AmsSlotRead]:
    _printer_or_404(db, printer_id)
    slots = list(
        db.scalars(
            select(AmsSlot)
            .where(AmsSlot.printer_id == printer_id)
            .order_by(AmsSlot.ams_id, AmsSlot.tray_id)
        ).all()
    )
    return [_ams_slot_read(slot) for slot in slots]


@router.get("/printers/{printer_id}/ams/history", response_model=list[AmsSlotHistorySampleRead])
def api_get_ams_history(
    printer_id: int,
    ams_id: str | None = Query(default=None),
    tray_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[AmsSlotHistorySample]:
    _printer_or_404(db, printer_id)
    query = select(AmsSlotHistorySample).where(AmsSlotHistorySample.printer_id == printer_id)
    if ams_id:
        query = query.where(AmsSlotHistorySample.ams_id == ams_id)
    if tray_id:
        query = query.where(AmsSlotHistorySample.tray_id == tray_id)
    if since:
        query = query.where(AmsSlotHistorySample.sampled_at >= since)
    rows = list(
        db.scalars(
            query.order_by(AmsSlotHistorySample.sampled_at.desc(), AmsSlotHistorySample.id.desc()).limit(limit)
        ).all()
    )
    rows.reverse()
    return rows


@router.get("/printers/{printer_id}/ams/{ams_id}/sensor-history", response_model=AmsSensorHistoryRead)
def api_get_ams_sensor_history(
    printer_id: int,
    ams_id: str,
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _printer_or_404(db, printer_id)
    return build_ams_sensor_history(db, printer_id=printer_id, ams_id=ams_id, hours=hours)


@router.get("/print-log", response_model=PrintLogListRead)
def api_list_print_log(
    printer_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PrintLogListRead:
    if printer_id is not None:
        _printer_or_404(db, printer_id)
    total, rows = list_print_logs(
        db,
        printer_id=printer_id,
        status=status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PrintLogListRead(total=total, limit=limit, offset=offset, items=[_print_log_read(row) for row in rows])


@router.get("/print-log/summary", response_model=PrintLogSummaryRead)
def api_print_log_summary(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return print_log_summary(db, date_from=from_, date_to=to)


@router.get("/maintenance/overview", response_model=MaintenanceOverviewRead)
def api_maintenance_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    return maintenance_overview(db)


@router.get("/printers/{printer_id}/maintenance", response_model=list[PrinterMaintenanceRead])
def api_get_printer_maintenance(
    printer_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    printer = _printer_or_404(db, printer_id)
    return get_printer_maintenance(db, printer)


@router.patch("/maintenance/items/{item_id}", response_model=PrinterMaintenanceRead)
def api_update_maintenance_item(
    item_id: int,
    data: PrinterMaintenanceUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = get_maintenance_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Maintenance item not found")
    updates = data.model_dump(exclude_unset=True)
    return update_maintenance_item(db, item, **updates)


@router.post("/maintenance/items/{item_id}/perform", response_model=PrinterMaintenanceRead)
def api_perform_maintenance_item(
    item_id: int,
    data: MaintenancePerformRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = get_maintenance_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Maintenance item not found")
    return perform_maintenance_item(
        db,
        item,
        note=data.note,
        performed_at=data.performed_at,
        print_hours=data.print_hours,
    )


@router.get("/maintenance/items/{item_id}/history", response_model=list[MaintenanceHistoryRead])
def api_get_maintenance_history(
    item_id: int,
    db: Session = Depends(get_db),
) -> list[Any]:
    item = get_maintenance_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Maintenance item not found")
    return maintenance_history(db, item)


@router.get("/hms/codes", response_model=list[HmsCodeInfoRead])
def api_list_hms_codes() -> list[dict[str, Any]]:
    return list_hms_codes()


@router.get("/hms/codes/{short_code}", response_model=HmsCodeInfoRead)
def api_get_hms_code(short_code: str) -> dict[str, Any]:
    code = get_hms_code(short_code)
    if code is None:
        raise HTTPException(status_code=404, detail="HMS code not found")
    return code


@router.get("/events", response_model=list[UnifiedEventRead])
def api_list_events(
    printer_id: int | None = Query(default=None),
    type: str | None = Query(default=None),  # noqa: A002
    severity: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return list_unified_events(
        db,
        printer_id=printer_id,
        event_type=type,
        severity=severity,
        active=active,
        since=since,
        limit=limit,
    )


@router.get("/events/stream")
async def api_stream_events() -> StreamingResponse:
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/printers/{printer_id}/mqtt/payload", response_model=RawMqttMessageRead)
def api_ingest_mqtt_payload(
    printer_id: int,
    data: MqttPayloadIn,
    db: Session = Depends(get_db),
) -> RawMqttMessageRead:
    _printer_or_404(db, printer_id)
    raw = process_mqtt_payload(db, printer_id=printer_id, topic=data.topic, payload=data.payload)
    read = RawMqttMessageRead.model_validate(raw)
    return read.model_copy(update={"payload": redact_sensitive(read.payload)})


@router.get("/spools", response_model=list[SpoolRead])
def api_list_spools(db: Session = Depends(get_db)) -> list[Any]:
    return list_spools(db)


@router.post("/spools", response_model=SpoolRead, status_code=status.HTTP_201_CREATED)
def api_create_spool(data: SpoolCreate, db: Session = Depends(get_db)) -> Any:
    return create_spool(db, data)


@router.patch("/spools/{spool_id}", response_model=SpoolRead)
def api_update_spool(spool_id: int, data: SpoolUpdate, db: Session = Depends(get_db)) -> Any:
    spool = get_spool(db, spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Spool not found")
    return update_spool(db, spool, data)


@router.post("/ams/slots/{slot_id}/bind", response_model=AmsSlotRead)
def api_bind_slot(slot_id: int, data: SlotBindRequest, db: Session = Depends(get_db)) -> AmsSlot:
    slot = db.get(AmsSlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="AMS slot not found")
    spool = get_spool(db, data.spool_id)
    if spool is None:
        raise HTTPException(status_code=404, detail="Spool not found")
    return bind_slot_to_spool(db, slot, spool)


@router.get("/spools/{spool_id}/locations")
def api_get_spool_locations(spool_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    if get_spool(db, spool_id) is None:
        raise HTTPException(status_code=404, detail="Spool not found")
    rows = db.scalars(
        select(SpoolLocation).where(SpoolLocation.spool_id == spool_id).order_by(SpoolLocation.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "spool_id": row.spool_id,
            "printer_id": row.printer_id,
            "ams_id": row.ams_id,
            "tray_id": row.tray_id,
            "event_type": row.event_type,
            "moved_at": row.moved_at,
        }
        for row in rows
    ]


@router.get("/debug/raw-mqtt", response_model=list[RawMqttMessageRead])
def api_list_raw_mqtt(limit: int = 50, db: Session = Depends(get_db)) -> list[RawMqttMessageRead]:
    rows = db.scalars(select(RawMqttMessage).order_by(RawMqttMessage.id.desc()).limit(limit)).all()
    return [
        RawMqttMessageRead.model_validate(row).model_copy(update={"payload": redact_sensitive(row.payload)})
        for row in rows
    ]


@router.get("/debug/events", response_model=list[PrinterEventRead])
def api_list_printer_events(limit: int = 100, db: Session = Depends(get_db)) -> list[PrinterEvent]:
    return list(db.scalars(select(PrinterEvent).order_by(PrinterEvent.id.desc()).limit(limit)).all())


@router.get("/debug/inventory-events", response_model=list[InventoryEventRead])
def api_list_inventory_events(limit: int = 100, db: Session = Depends(get_db)) -> list[InventoryEvent]:
    return list(db.scalars(select(InventoryEvent).order_by(InventoryEvent.id.desc()).limit(limit)).all())


@router.get("/metrics/prometheus")
def api_prometheus_metrics(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    if not settings.prometheus_enabled:
        raise HTTPException(status_code=404, detail="Prometheus metrics are disabled")
    if settings.prometheus_bearer_token:
        expected = f"Bearer {settings.prometheus_bearer_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
    return Response(content=prometheus_metrics(db), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/system/info", response_model=SystemInfoRead)
def api_system_info(db: Session = Depends(get_db)) -> dict[str, Any]:
    return system_info(db)


@router.get("/support/bundle", response_model=SupportBundleRead)
def api_support_bundle(db: Session = Depends(get_db)) -> dict[str, Any]:
    return support_bundle(db)


def _metric_group_prefix(group: str | None) -> str | None:
    if group == "temperature":
        return "temperature.%"
    if group == "fan":
        return "fan.%"
    if group == "wifi":
        return "network.wifi_signal"
    if group == "ams":
        return "ams.%"
    if group == "print":
        return "print.%"
    if group == "coverage":
        return "coverage.%"
    return None


def _bucket_metric_samples(rows: list[DeviceMetricSample], bucket: str) -> list[DeviceMetricSampleRead]:
    buckets: dict[tuple[str, datetime], list[DeviceMetricSample]] = {}
    for row in rows:
        key = (row.metric, _bucket_start(row.sampled_at, bucket))
        buckets.setdefault(key, []).append(row)
    aggregated: list[DeviceMetricSampleRead] = []
    for (metric, sampled_at), samples in sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0])):
        numeric_values = [_metric_value_float(sample) for sample in samples if _metric_value_float(sample) is not None]
        latest = max(samples, key=lambda sample: (sample.sampled_at, sample.id))
        value_float = sum(numeric_values) / len(numeric_values) if numeric_values else None
        aggregated.append(
            DeviceMetricSampleRead(
                id=0,
                printer_id=latest.printer_id,
                metric=metric,
                value_float=value_float,
                value_text=str(round(value_float, 3)) if value_float is not None else latest.value_text,
                unit=latest.unit,
                raw_message_id=latest.raw_message_id,
                details={**(latest.details or {}), "bucket": bucket, "sample_count": len(samples)},
                sampled_at=sampled_at,
            )
        )
    return aggregated


def _bucket_start(value: datetime, bucket: str) -> datetime:
    if bucket == "minute":
        return value.replace(second=0, microsecond=0)
    if bucket == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value


def _metric_sample_read(row: DeviceMetricSample) -> DeviceMetricSampleRead:
    read = DeviceMetricSampleRead.model_validate(row)
    value_float = _metric_value_float(row)
    if value_float == row.value_float:
        return read
    return read.model_copy(update={"value_float": value_float, "value_text": str(value_float) if value_float is not None else None})


def _metric_value_float(row: DeviceMetricSample) -> float | None:
    value = row.value_float
    if not row.metric.startswith("fan.") or not row.metric.endswith(".percent"):
        return value
    if value is not None and 0 <= value <= 100:
        return value
    details = row.details if isinstance(row.details, dict) else {}
    normalized = fan_percent(details.get("raw"))
    if normalized is not None:
        return float(normalized)
    if value is None:
        return None
    return float(max(0, min(100, value)))


def _print_log_read(row: PrintLogEntry) -> PrintLogEntryRead:
    read = PrintLogEntryRead.model_validate(row)
    return read.model_copy(
        update={
            "filament_summary": redact_sensitive(read.filament_summary),
            "hms_summary": redact_sensitive(read.hms_summary),
            "raw_refs": redact_sensitive(read.raw_refs),
        }
    )


def _state_read(snapshot: PrinterStateSnapshot | None) -> PrinterStateRead | None:
    if snapshot is None:
        return None
    read = PrinterStateRead.model_validate(snapshot)
    return read.model_copy(update={"payload": redact_sensitive(read.payload)})


def _device_snapshot_read(snapshot: DeviceStatusSnapshot | None) -> DeviceStatusSnapshotRead | None:
    if snapshot is None:
        return None
    read = DeviceStatusSnapshotRead.model_validate(snapshot)
    redacted = {
        key: redact_sensitive(getattr(read, key))
        for key in (
            "print_status",
            "derived_status",
            "temperatures",
            "fans",
            "network",
            "hardware",
            "nozzles",
            "storage",
            "camera",
            "camera_options",
            "lights",
            "speed",
            "calibration",
            "ams_status",
            "hms_errors",
            "firmware",
            "accessories",
            "external_slots",
            "unsupported_features",
            "data_coverage",
            "raw_refs",
        )
    }
    redacted["fans"] = normalize_fan_payload(redacted["fans"])
    redacted["camera"] = _sanitize_camera_response(redacted["camera"])
    redacted["camera_options"] = _sanitize_camera_response(redacted["camera_options"])
    return read.model_copy(update=redacted)


def _ams_unit_read(unit: AmsUnit) -> AmsUnitRead:
    read = AmsUnitRead.model_validate(unit)
    return read.model_copy(update={"raw": redact_sensitive(read.raw)})


def _ams_slot_read(slot: AmsSlot) -> AmsSlotRead:
    read = AmsSlotRead.model_validate(slot)
    user_tray_id = _slot_user_tray_id(slot)
    slot_label = f"Slot {user_tray_id}" if user_tray_id is not None else f"Slot {slot.tray_id}"
    return read.model_copy(
        update={
            "raw": redact_sensitive(read.raw),
            "user_tray_id": user_tray_id,
            "slot_label": slot_label,
            "global_tray_id": _slot_global_tray_id(slot),
            "location_label": f"AMS {slot.ams_id} / {slot_label}",
        }
    )


def _slot_user_tray_id(slot: AmsSlot) -> int | None:
    try:
        return int(slot.tray_id) + 1
    except (TypeError, ValueError):
        return None


def _slot_global_tray_id(slot: AmsSlot) -> str:
    try:
        return str((int(slot.ams_id) * 4) + int(slot.tray_id))
    except (TypeError, ValueError):
        return f"{slot.ams_id}:{slot.tray_id}"


def _printer_or_404(db: Session, printer_id: int):
    printer = get_printer(db, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


def _sync_runtime_connection_status(db: Session, printer: Any) -> None:
    if printer.connection_status not in {"connected", "connecting"}:
        return
    if mqtt_manager.is_connected(printer.id):
        return
    printer.connection_status = "disconnected"
    printer.last_error = "MQTT session is not active; reconnect required"
    db.add(printer)
    db.commit()
    db.refresh(printer)


def _should_reconnect_for_refresh(printer: Any) -> bool:
    return bool(printer.enabled and printer.connection_status in {"connected", "connecting"})


def _reconnect_for_refresh(db: Session, printer: Any) -> None:
    try:
        mqtt_manager.connect(db, printer)
    except ValueError as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        status_code = 400 if is_certificate_verify_error(exc) else 502
        detail = str(exc) if status_code == 400 else f"Failed to reconnect printer MQTT: {exc}"
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        printer.connection_status = "error"
        printer.last_error = str(exc)
        db.add(printer)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to reconnect printer MQTT: {exc}") from exc


def _sanitize_camera_response(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        key: item
        for key, item in value.items()
        if item is not None and item != "" and not isinstance(item, (dict, list))
    }
