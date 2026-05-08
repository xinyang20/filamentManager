from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import mimetypes
from typing import Any
from urllib.parse import quote

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
    PrinterEvent,
    PrinterStorageFile,
    PrinterStateSnapshot,
    PrintLogEntry,
    NotificationDelivery,
    NotificationRule,
    NotificationTarget,
    RawMqttMessage,
    TimelapseNote,
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
    HmsCodeStatsRead,
    FilamentBrandCreate,
    FilamentBrandRead,
    FilamentBrandUpdate,
    FilamentColorMappingGapRead,
    FilamentColorMappingCreate,
    FilamentColorMappingRead,
    FilamentColorMappingUpdate,
    FilamentInventorySummaryRead,
    FilamentSkuCreate,
    FilamentSkuRead,
    FilamentSkuStockAdjust,
    FilamentSkuTypeSeriesSet,
    FilamentSkuUpdate,
    FilamentSpoolCreate,
    FilamentSpoolEventsRead,
    FilamentSpoolLocationUpdate,
    FilamentSpoolRead,
    FilamentSpoolStatusUpdate,
    FilamentSpoolUpdate,
    FilamentSpoolUidConflictResolve,
    FilamentSpoolWeightUpdate,
    FilamentTypeSeriesBrandSet,
    FilamentTypeSeriesCreate,
    FilamentTypeSeriesRead,
    FilamentTypeSeriesUpdate,
    MaintenanceHistoryRead,
    MaintenanceOverviewRead,
    MaintenancePerformRequest,
    MqttPayloadIn,
    NotificationDeliveryRead,
    NotificationRuleCreate,
    NotificationRuleRead,
    NotificationRuleUpdate,
    NotificationTargetCreate,
    NotificationTargetRead,
    NotificationTargetUpdate,
    PrinterMaintenanceRead,
    PrinterMaintenanceUpdate,
    PrintLogAnalyticsRead,
    PrintLogEntryRead,
    PrintLogListRead,
    PrintLogSummaryRead,
    PrinterCreate,
    PrinterAccessCodeRead,
    PrinterCameraCapabilitiesRead,
    PrinterDashboardRead,
    PrinterEventRead,
    PrinterRead,
    PrinterStateRead,
    PrinterStorageFileRead,
    PrinterUpdate,
    RawMqttMessageRead,
    SlotBindRequest,
    StorageSummaryRead,
    StorageScanResultRead,
    SupportBundleRead,
    SystemInfoRead,
    TimelapseNoteRead,
    TimelapseNoteUpdate,
    UnifiedEventRead,
    DeviceCapabilitiesRead,
)
from filament_manager.api.helpers import (
    ams_slot_read as _ams_slot_read,
    ams_unit_read as _ams_unit_read,
    bucket_metric_samples as _bucket_metric_samples,
    device_snapshot_read as _device_snapshot_read,
    metric_group_prefix as _metric_group_prefix,
    metric_sample_read as _metric_sample_read,
    notification_rule_or_404 as _notification_rule_or_404,
    notification_target_or_404 as _notification_target_or_404,
    notification_target_read as _notification_target_read,
    parse_range_header as _parse_range_header,
    print_log_read as _print_log_read,
    printer_or_404 as _printer_or_404,
    reconnect_for_refresh as _reconnect_for_refresh,
    should_reconnect_for_refresh as _should_reconnect_for_refresh,
    state_read as _state_read,
    sanitize_camera_response as _sanitize_camera_response,
    storage_cache_headers as _storage_cache_headers,
    storage_file_can_inline as _storage_file_can_inline,
    storage_media_type as _storage_media_type,
    storage_usage_summary as _storage_usage_summary,
    sync_runtime_connection_status as _sync_runtime_connection_status,
)
from filament_manager.api.filament_routes import router as filament_router
from filament_manager.services.ams import build_ams_overview, build_ams_sensor_history, delete_ams_label, set_ams_label
from filament_manager.services.camera import (
    CAMERA_MJPEG_MEDIA_TYPE,
    CameraStreamError,
    camera_capabilities,
    camera_config_from_printer,
    iter_camera_mjpeg_auto,
    select_camera_sources,
)
from filament_manager.services.discovery import scan_lan_devices
from filament_manager.services.device_capabilities import all_device_capabilities, printer_capabilities
from filament_manager.services.events import list_unified_events, sse_event_generator
from filament_manager.services.exporting import export_csv_zip_bytes, export_json_bytes, import_json_payload
from filament_manager.services.fans import fan_percent, normalize_fan_payload
from filament_manager.services.hms import get_hms_code, hms_code_stats, list_hms_codes
from filament_manager.services.inventory import (
    adjust_sku_stock,
    bind_slot_to_filament_spool,
    build_inventory_summary,
    confirm_filament_spool_sku_review,
    create_brand,
    create_color_mapping,
    create_filament_spool,
    create_sku,
    create_type_series,
    delete_brand,
    delete_color_mapping,
    delete_filament_spool,
    delete_sku,
    delete_type_series,
    DuplicateFilamentSkuError,
    FilamentSpoolUidConflictError,
    filament_brand_to_read,
    filament_color_mapping_to_read,
    filament_sku_to_read,
    filament_spool_to_read,
    filament_type_series_to_read,
    get_brand,
    get_color_mapping,
    get_filament_spool,
    get_sku,
    get_type_series,
    list_brands,
    list_color_mappings,
    list_color_mapping_gaps,
    list_filament_spool_events,
    list_filament_spools,
    list_skus,
    list_type_series,
    resolve_reappeared_uid_conflict,
    set_sku_type_series,
    set_type_series_brands,
    update_brand,
    update_color_mapping,
    update_filament_location,
    update_filament_spool,
    update_filament_status,
    update_filament_weight,
    update_sku,
    update_type_series,
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
from filament_manager.services.notifications import (
    create_rule,
    create_target,
    delete_rule,
    delete_target,
    list_deliveries,
    list_rules,
    list_targets,
    redact_notification_config,
    test_target,
    update_rule,
    update_target,
)
from filament_manager.services.local_records import (
    list_timelapse_notes,
    upsert_timelapse_note,
)
from filament_manager.services.observability import prometheus_metrics, support_bundle, system_info
from filament_manager.services.print_log import list_print_logs, print_log_analytics, print_log_summary
from filament_manager.services.printers import (
    create_printer,
    delete_printer,
    get_printer,
    list_printers,
    printer_to_read,
    update_printer,
)
from filament_manager.services.storage import (
    is_timelapse_storage_file,
    scan_printer_storage,
    stream_printer_storage_file,
)

router = APIRouter()
router.include_router(filament_router)

METRIC_BUCKET_DEFAULT_LOOKBACKS = {
    "minute": timedelta(hours=24),
    "hour": timedelta(days=30),
    "day": timedelta(days=180),
}


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


@router.get("/printers/{printer_id}/access-code", response_model=PrinterAccessCodeRead)
def api_get_printer_access_code(printer_id: int, db: Session = Depends(get_db)) -> PrinterAccessCodeRead:
    printer = _printer_or_404(db, printer_id)
    return PrinterAccessCodeRead(access_code=printer.access_code)


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


@router.get("/printers/{printer_id}/camera/capabilities", response_model=PrinterCameraCapabilitiesRead)
def api_get_printer_camera_capabilities(
    printer_id: int,
    db: Session = Depends(get_db),
) -> PrinterCameraCapabilitiesRead:
    printer = _printer_or_404(db, printer_id)
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    return PrinterCameraCapabilitiesRead.model_validate(camera_capabilities(printer, snapshot))


@router.get("/printers/{printer_id}/camera/mjpeg")
def api_stream_printer_camera_mjpeg(
    printer_id: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    printer = _printer_or_404(db, printer_id)
    snapshot = db.scalars(
        select(DeviceStatusSnapshot).where(DeviceStatusSnapshot.printer_id == printer_id)
    ).first()
    config = camera_config_from_printer(printer)
    try:
        sources = select_camera_sources(printer, snapshot)
    except CameraStreamError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not sources:
        raise HTTPException(status_code=503, detail="No local camera stream endpoint is reachable")
    return StreamingResponse(
        iter_camera_mjpeg_auto(config, sources),
        media_type=CAMERA_MJPEG_MEDIA_TYPE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


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
    if bucket != "raw" and lower_bound is None:
        lookback = METRIC_BUCKET_DEFAULT_LOOKBACKS.get(bucket)
        if lookback is not None:
            lower_bound = (to or datetime.now(timezone.utc)) - lookback
    if lower_bound:
        query = query.where(DeviceMetricSample.sampled_at >= lower_bound)
    if to:
        query = query.where(DeviceMetricSample.sampled_at <= to)
    if bucket == "raw":
        rows = list(
            db.scalars(
                query.order_by(DeviceMetricSample.sampled_at.desc(), DeviceMetricSample.id.desc()).limit(limit)
            ).all()
        )
        rows.reverse()
        return [_metric_sample_read(row) for row in rows]
    rows = list(
        db.scalars(
            query.order_by(DeviceMetricSample.sampled_at, DeviceMetricSample.id)
        ).all()
    )
    return _bucket_metric_samples(rows, bucket)[-limit:]


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
    rows = [row for row in rows if is_timelapse_storage_file(row)]
    return [
        PrinterStorageFileRead.model_validate(row).model_copy(update={"raw": redact_sensitive(row.raw)})
        for row in rows
    ]


@router.get("/printers/{printer_id}/storage/files/download")
def api_download_printer_storage_file(
    printer_id: int,
    path: str = Query(..., min_length=1),
    inline: bool = Query(default=False),
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    printer = _printer_or_404(db, printer_id)
    if "\r" in path or "\n" in path:
        raise HTTPException(status_code=400, detail="Invalid storage path")
    file = db.scalars(
        select(PrinterStorageFile).where(
            PrinterStorageFile.printer_id == printer_id,
            PrinterStorageFile.path == path,
        )
    ).first()
    if file is None:
        raise HTTPException(status_code=404, detail="Storage file is not in the latest scanned file list")
    if not is_timelapse_storage_file(file):
        raise HTTPException(status_code=403, detail="Only timelapse files can be downloaded")
    filename = file.name or path.rsplit("/", 1)[-1] or "printer-file"
    disposition = "inline" if inline and _storage_file_can_inline(file) else "attachment"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
        **_storage_cache_headers(file),
    }
    range_start: int | None = None
    range_end: int | None = None
    status_code = status.HTTP_200_OK
    if range_header and file.size:
        byte_range = _parse_range_header(range_header, file.size)
        if byte_range is None:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid range",
                headers={"Content-Range": f"bytes */{file.size}"},
            )
        range_start, range_end = byte_range
        status_code = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {range_start}-{range_end}/{file.size}"
        headers["Content-Length"] = str(range_end - range_start + 1)
    return StreamingResponse(
        stream_printer_storage_file(printer, path, start=range_start, end=range_end)
        if range_start is not None
        else stream_printer_storage_file(printer, path),
        status_code=status_code,
        media_type=_storage_media_type(file),
        headers=headers,
    )


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
    rows = [row for row in rows if is_timelapse_storage_file(row)]
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
        storage_usage=_storage_usage_summary(db, printer_id),
        recent_files=files[:10],
        timelapse_files=[file for file in files if file.type == "timelapse"][:10],
        last_scan_event=last_scan_event,
        last_scan=last_scan.data if last_scan is not None else None,
    )


@router.get("/printers/{printer_id}/timelapse/notes", response_model=list[TimelapseNoteRead])
def api_get_timelapse_notes(printer_id: int, db: Session = Depends(get_db)) -> list[TimelapseNote]:
    _printer_or_404(db, printer_id)
    return list_timelapse_notes(db, printer_id)


@router.patch("/printers/{printer_id}/timelapse/notes", response_model=TimelapseNoteRead)
def api_update_timelapse_note(
    printer_id: int,
    data: TimelapseNoteUpdate,
    db: Session = Depends(get_db),
) -> TimelapseNote:
    _printer_or_404(db, printer_id)
    return upsert_timelapse_note(
        db,
        printer_id=printer_id,
        path=data.path,
        favorite=data.favorite,
        note=data.note,
        note_set="note" in data.model_fields_set,
        cached_metadata=data.cached_metadata,
        cached_metadata_set="cached_metadata" in data.model_fields_set,
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


@router.get("/print-log/analytics", response_model=PrintLogAnalyticsRead)
def api_print_log_analytics(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    printer_id: int | None = Query(default=None),
    bucket: str = Query(default="day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if printer_id is not None:
        _printer_or_404(db, printer_id)
    return print_log_analytics(db, date_from=from_, date_to=to, printer_id=printer_id, bucket=bucket)


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


@router.get("/hms/codes/{short_code}/stats", response_model=HmsCodeStatsRead)
def api_get_hms_code_stats(
    short_code: str,
    printer_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if printer_id is not None:
        _printer_or_404(db, printer_id)
    return hms_code_stats(db, short_code=short_code, printer_id=printer_id, days=days)


@router.get("/device-capabilities", response_model=dict[str, DeviceCapabilitiesRead])
def api_device_capabilities() -> dict[str, dict[str, Any]]:
    return all_device_capabilities()


@router.get("/printers/{printer_id}/capabilities", response_model=DeviceCapabilitiesRead)
def api_printer_capabilities(printer_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    printer = _printer_or_404(db, printer_id)
    return printer_capabilities(db, printer)


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


@router.get("/notifications/targets", response_model=list[NotificationTargetRead])
def api_list_notification_targets(db: Session = Depends(get_db)) -> list[NotificationTargetRead]:
    return [_notification_target_read(row) for row in list_targets(db)]


@router.post("/notifications/targets", response_model=NotificationTargetRead, status_code=status.HTTP_201_CREATED)
def api_create_notification_target(
    data: NotificationTargetCreate,
    db: Session = Depends(get_db),
) -> NotificationTargetRead:
    return _notification_target_read(create_target(db, channel=data.channel, name=data.name, enabled=data.enabled, config=data.config))


@router.patch("/notifications/targets/{target_id}", response_model=NotificationTargetRead)
def api_update_notification_target(
    target_id: int,
    data: NotificationTargetUpdate,
    db: Session = Depends(get_db),
) -> NotificationTargetRead:
    target = _notification_target_or_404(db, target_id)
    return _notification_target_read(update_target(db, target, **data.model_dump(exclude_unset=True)))


@router.delete("/notifications/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_notification_target(target_id: int, db: Session = Depends(get_db)) -> Response:
    target = _notification_target_or_404(db, target_id)
    delete_target(db, target)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notifications/targets/{target_id}/test", response_model=NotificationDeliveryRead)
def api_test_notification_target(target_id: int, db: Session = Depends(get_db)) -> NotificationDelivery:
    target = _notification_target_or_404(db, target_id)
    return test_target(db, target)


@router.get("/notifications/rules", response_model=list[NotificationRuleRead])
def api_list_notification_rules(db: Session = Depends(get_db)) -> list[NotificationRule]:
    return list_rules(db)


@router.post("/notifications/rules", response_model=NotificationRuleRead, status_code=status.HTTP_201_CREATED)
def api_create_notification_rule(data: NotificationRuleCreate, db: Session = Depends(get_db)) -> NotificationRule:
    return create_rule(
        db,
        name=data.name,
        enabled=data.enabled,
        event_types=data.event_types,
        printer_ids=data.printer_ids,
        severities=data.severities,
        quiet_policy=data.quiet_policy,
    )


@router.patch("/notifications/rules/{rule_id}", response_model=NotificationRuleRead)
def api_update_notification_rule(
    rule_id: int,
    data: NotificationRuleUpdate,
    db: Session = Depends(get_db),
) -> NotificationRule:
    rule = _notification_rule_or_404(db, rule_id)
    return update_rule(db, rule, **data.model_dump(exclude_unset=True))


@router.delete("/notifications/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_notification_rule(rule_id: int, db: Session = Depends(get_db)) -> Response:
    rule = _notification_rule_or_404(db, rule_id)
    delete_rule(db, rule)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications/deliveries", response_model=list[NotificationDeliveryRead])
def api_list_notification_deliveries(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[NotificationDelivery]:
    return list_deliveries(db, limit=limit)


@router.get("/export")
def api_export(
    type: str = Query(default="json", pattern="^(json|csv)$"),  # noqa: A002
    mode: str = Query(default="redacted", pattern="^(redacted|backup)$"),
    sections: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    section_list = [item.strip() for item in sections.split(",") if item.strip()] if sections else None
    if type == "csv":
        return Response(
            content=export_csv_zip_bytes(db, section_list),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=filament-manager-export.zip"},
        )
    return Response(
        content=export_json_bytes(db, section_list, include_sensitive=mode == "backup"),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=filament-manager-export.json"},
    )


@router.post("/import")
def api_import_backup(data: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    mode = str(data.get("mode") or "merge")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Import payload must be a JSON object")
    try:
        return import_json_payload(db, payload, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
