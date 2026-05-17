from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RawMqttDbLimit = Literal["1gb", "5gb", "10gb", "20gb", "unlimited"]


class PrinterCreate(BaseModel):
    name: str = Field(default="Printer", min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=8883, ge=1, le=65535)
    serial: str = Field(min_length=1, max_length=128)
    access_code: str = Field(min_length=1, max_length=255)
    tls_enabled: bool = True
    certificate_verify: bool = False
    enabled: bool = True
    print_hours_offset: float = Field(default=0.0, ge=0)


class PrinterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    serial: str | None = Field(default=None, min_length=1, max_length=128)
    access_code: str | None = Field(default=None, max_length=255)
    tls_enabled: bool | None = None
    certificate_verify: bool | None = None
    enabled: bool | None = None
    print_hours_offset: float | None = Field(default=None, ge=0)


class PrinterRead(BaseModel):
    id: int
    name: str
    host: str
    port: int
    serial: str
    access_code: str | None
    tls_enabled: bool
    certificate_verify: bool
    enabled: bool
    connection_status: str
    last_sync_at: datetime | None
    last_error: str | None
    print_hours_offset: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrinterAccessCodeRead(BaseModel):
    access_code: str


class PrinterStateRead(BaseModel):
    id: int
    printer_id: int
    gcode_state: str | None
    print_type: str | None
    mc_percent: int | None
    mc_remaining_time: int | None
    gcode_file: str | None
    subtask_name: str | None
    project_id: str | None
    profile_id: str | None
    task_id: str | None
    error_code: str | None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmsUnitRead(BaseModel):
    id: int
    printer_id: int
    ams_id: str
    humidity: str | None
    temperature: str | None
    humidity_raw: Any | None = None
    serial_number: Any | None = None
    sw_ver: Any | None = None
    module_type: Any | None = None
    dry_time: Any | None = None
    dry_status: Any | None = None
    dry_sub_status: Any | None = None
    dry_sf_reason: Any | None = None
    is_ams_ht: bool = False
    ams_type_name: str = "unknown"
    dry_status_name: str | None = None
    dry_sub_status_name: str | None = None
    dry_sf_reason_names: list[str] = []
    raw: dict[str, Any]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmsSlotRead(BaseModel):
    id: int
    printer_id: int
    ams_id: str
    tray_id: str
    slot_state: str | None
    material: str | None
    series: str | None
    color: str | None
    remain: int | None
    tray_uuid: str | None
    tag_uid: str | None
    identity_key: str | None
    identity_source: str
    identity_confidence: float
    identity_warning: str | None
    is_transitioning: bool
    spool_id: int | None = None
    filament_spool_id: int | None = None
    filament_brand_id: int | None = None
    filament_brand_name: str | None = None
    filament_material: str | None = None
    filament_series: str | None = None
    user_tray_id: int | None = None
    slot_label: str | None = None
    global_tray_id: str | None = None
    location_label: str | None = None
    is_active: bool = False
    tray_id_name: Any | None = None
    tray_color_name: Any | None = None
    tray_info_idx: Any | None = None
    nozzle_temp_min: Any | None = None
    nozzle_temp_max: Any | None = None
    drying_temp: Any | None = None
    drying_time: Any | None = None
    cali_idx: Any | None = None
    k: Any | None = None
    state_code: Any | None = None
    state_name: str | None = None
    tray_state_name: str | None = None
    color_source: str | None = None
    official_color_code: str | None = None
    official_color_type: str | None = None
    official_color_names: dict[str, str] | None = None
    official_colors: list[str] | None = None
    official_match_ambiguous: bool | None = None
    raw: dict[str, Any]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmsOverviewSummaryRead(BaseModel):
    ams_count: int
    slot_count: int
    loaded_count: int
    empty_count: int
    transitioning_count: int
    unknown_type_count: int
    active_slot: dict[str, Any] | None = None


class AmsUnitOverviewRead(BaseModel):
    ams_id: str
    display_name: str | None = None
    ams_type_name: str
    module_type: Any | None = None
    sw_ver: Any | None = None
    serial_number: Any | None = None
    humidity: str | None = None
    humidity_raw: Any | None = None
    temperature: str | None = None
    dry_time: Any | None = None
    dry_status: Any | None = None
    dry_status_name: str | None = None
    dry_sub_status: Any | None = None
    dry_sub_status_name: str | None = None
    dry_sf_reason: Any | None = None
    dry_sf_reason_names: list[str] = Field(default_factory=list)
    active_slot: dict[str, Any] | None = None
    updated_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
    slots: list[AmsSlotRead] = Field(default_factory=list)


class AmsOverviewRead(BaseModel):
    summary: AmsOverviewSummaryRead
    units: list[AmsUnitOverviewRead]


class AmsSlotHistorySampleRead(BaseModel):
    id: int
    printer_id: int
    ams_id: str
    tray_id: str
    state_name: str | None
    material: str | None
    color: str | None
    remain: int | None
    k: str | None
    cali_idx: str | None
    rfid_status: str | None
    sampled_at: datetime
    raw_message_id: int | None

    model_config = ConfigDict(from_attributes=True)


class AmsLabelUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class AmsLabelRead(BaseModel):
    id: int
    printer_id: int
    ams_id: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AmsSensorHistoryPointRead(BaseModel):
    sampled_at: datetime
    temperature: float | None = None
    humidity: float | None = None


class SensorStatsRead(BaseModel):
    min: float | None = None
    max: float | None = None
    avg: float | None = None


class AmsSensorHistoryRead(BaseModel):
    printer_id: int
    ams_id: str
    hours: int
    points: list[AmsSensorHistoryPointRead]
    temperature: SensorStatsRead
    humidity: SensorStatsRead


class FilamentBrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    note: str | None = None


class FilamentBrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    note: str | None = None


class FilamentBrandRead(BaseModel):
    id: int
    name: str
    aliases: list[str]
    note: str | None
    type_series_count: int = 0
    sku_count: int = 0
    spool_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilamentTypeSeriesCreate(BaseModel):
    brand_id: int | None = Field(default=None, gt=0)
    material_type: str = Field(min_length=1, max_length=40)
    series_name: str = Field(min_length=1, max_length=120)
    empty_spool_weight_g: float | None = Field(default=None, ge=0)
    config: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    brand_ids: list[int] = Field(default_factory=list)


class FilamentTypeSeriesUpdate(BaseModel):
    brand_id: int | None = Field(default=None, gt=0)
    material_type: str | None = Field(default=None, min_length=1, max_length=40)
    series_name: str | None = Field(default=None, min_length=1, max_length=120)
    empty_spool_weight_g: float | None = Field(default=None, ge=0)
    config: dict[str, Any] | None = None
    note: str | None = None


class FilamentTypeSeriesBrandSet(BaseModel):
    brand_id: int | None = Field(default=None, gt=0)
    brand_ids: list[int] = Field(default_factory=list)


class FilamentTypeSeriesRead(BaseModel):
    id: int
    brand_id: int
    brand_name: str | None = None
    material_type: str
    series_name: str
    empty_spool_weight_g: float | None
    config: dict[str, Any]
    note: str | None
    brand_ids: list[int] = Field(default_factory=list)
    brands: list[dict[str, Any]] = Field(default_factory=list)
    sku_count: int = 0
    spool_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilamentSkuCreate(BaseModel):
    type_series_id: int | None = Field(default=None, gt=0)
    color_name: str | None = Field(default=None, max_length=120)
    color_hex: str | None = Field(default=None, max_length=16)
    nominal_weight_g: float = Field(default=1000.0, ge=0)
    filament_diameter_mm: float = Field(default=1.75, gt=0)
    tray_info_idx: str | None = Field(default=None, max_length=120)
    note: str | None = None
    type_series_ids: list[int] = Field(default_factory=list)
    sealed_quantity: int = Field(default=0, ge=0)


class FilamentSkuUpdate(BaseModel):
    type_series_id: int | None = Field(default=None, gt=0)
    color_name: str | None = Field(default=None, max_length=120)
    color_hex: str | None = Field(default=None, max_length=16)
    nominal_weight_g: float | None = Field(default=None, ge=0)
    filament_diameter_mm: float | None = Field(default=None, gt=0)
    tray_info_idx: str | None = Field(default=None, max_length=120)
    note: str | None = None


class FilamentSkuTypeSeriesSet(BaseModel):
    type_series_id: int | None = Field(default=None, gt=0)
    type_series_ids: list[int] = Field(default_factory=list)


class FilamentSkuStockAdjust(BaseModel):
    delta: int
    reason: str | None = None


class FilamentSkuRead(BaseModel):
    id: int
    type_series_id: int | None = None
    brand_id: int | None = None
    brand_name: str | None = None
    material: str | None = None
    series: str | None = None
    color_name: str | None
    color_hex: str | None
    color_value: str | None = None
    nominal_weight_g: float
    empty_spool_weight_g: float | None = None
    filament_diameter_mm: float = 1.75
    density_g_cm3: float | None = None
    tray_info_idx: str | None = None
    sealed_quantity: int
    note: str | None
    type_series_ids: list[int] = Field(default_factory=list)
    type_series: list[dict[str, Any]] = Field(default_factory=list)
    brands: list[dict[str, Any]] = Field(default_factory=list)
    opened_spool_count: int = 0
    ams_spool_count: int = 0
    color_source: str | None = None
    official_color_code: str | None = None
    official_color_type: str | None = None
    official_color_names: dict[str, str] | None = None
    official_colors: list[str] | None = None
    official_match_ambiguous: bool | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilamentSpoolCreate(BaseModel):
    sku_id: int | None = None
    official_spool_uid: str | None = Field(default=None, max_length=220)
    identity_source: str = Field(default="manual", pattern="^(ams_official_id|manual|imported)$")
    nominal_weight_g: float | None = Field(default=None, ge=0)
    actual_weight_g: float | None = Field(default=None, ge=0)
    status: str = Field(
        default="opened_in_storage",
        pattern="^(sealed_stock_virtual|opened_in_storage|loaded_in_ams|needs_location|empty|archived|unknown)$",
    )
    opened_at: datetime | None = None
    current_printer_id: int | None = None
    current_ams_id: str | None = Field(default=None, max_length=40)
    current_tray_id: str | None = Field(default=None, max_length=40)
    storage_location: str | None = None
    note: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class FilamentSpoolUpdate(BaseModel):
    sku_id: int | None = None
    official_spool_uid: str | None = Field(default=None, max_length=220)
    identity_source: str | None = Field(default=None, pattern="^(ams_official_id|manual|imported)$")
    nominal_weight_g: float | None = Field(default=None, ge=0)
    actual_weight_g: float | None = Field(default=None, ge=0)
    status: str | None = Field(
        default=None,
        pattern="^(sealed_stock_virtual|opened_in_storage|loaded_in_ams|needs_location|empty|archived|unknown)$",
    )
    opened_at: datetime | None = None
    current_printer_id: int | None = None
    current_ams_id: str | None = Field(default=None, max_length=40)
    current_tray_id: str | None = Field(default=None, max_length=40)
    storage_location: str | None = None
    note: str | None = None
    config: dict[str, Any] | None = None


class FilamentSpoolWeightUpdate(BaseModel):
    actual_weight_g: float = Field(ge=0)
    note: str | None = None


class FilamentSpoolLocationUpdate(BaseModel):
    printer_id: int | None = None
    ams_id: str | None = Field(default=None, max_length=40)
    tray_id: str | None = Field(default=None, max_length=40)
    storage_location: str | None = None
    note: str | None = None


class FilamentSpoolStatusUpdate(BaseModel):
    status: str = Field(pattern="^(opened_in_storage|loaded_in_ams|needs_location|empty|archived|unknown)$")
    note: str | None = None


class FilamentSpoolUidConflictResolve(BaseModel):
    action: str = Field(pattern="^(restore_old|create_new|ignore)$")
    note: str | None = None


class FilamentSpoolRead(BaseModel):
    id: int
    sku_id: int | None
    legacy_spool_id: int | None = None
    sku_label: str | None = None
    brand_id: int | None = None
    brand_name: str | None = None
    material: str | None = None
    series: str | None = None
    type_series: list[dict[str, Any]] = Field(default_factory=list)
    brands: list[dict[str, Any]] = Field(default_factory=list)
    color_name: str | None = None
    color_hex: str | None = None
    color_value: str | None = None
    official_spool_uid: str | None
    identity_key: str | None = None
    tray_uuid: str | None = None
    tag_uid: str | None = None
    identity_source: str
    nominal_weight_g: float | None
    actual_weight_g: float | None
    initial_net_weight_g: float | None = None
    current_remaining_g: float | None = None
    used_weight_g: float = 0
    empty_spool_weight_g: float | None = None
    status: str
    opened_at: datetime | None
    first_loaded_at: datetime | None = None
    last_used_at: datetime | None = None
    current_printer_id: int | None
    current_ams_id: str | None
    current_tray_id: str | None
    storage_location: str | None
    manual_location: str | None = None
    last_location: dict[str, Any] | None = None
    status_changed_at: datetime | None = None
    empty_at: datetime | None = None
    archived_at: datetime | None = None
    manual_quantity_protected: bool = False
    last_weighed_g: float | None = None
    last_ams_remain_percent: int | None = None
    color_source: str | None = None
    official_color_code: str | None = None
    official_color_type: str | None = None
    official_color_names: dict[str, str] | None = None
    official_colors: list[str] | None = None
    official_match_ambiguous: bool | None = None
    note: str | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilamentSpoolEventRead(BaseModel):
    id: int
    spool_id: int | None
    sku_id: int | None
    printer_id: int | None
    ams_id: str | None
    tray_id: str | None
    event_type: str
    previous: dict[str, Any] | None
    current: dict[str, Any] | None
    quantity_delta: int | None
    message: str
    note: str | None
    data: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FilamentSpoolEventsRead(BaseModel):
    events: list[FilamentSpoolEventRead]


class FilamentColorMappingCreate(BaseModel):
    brand_id: int = Field(gt=0)
    type_series_id: int = Field(gt=0)
    color_name: str = Field(min_length=1, max_length=120)
    color_hex: str = Field(min_length=1, max_length=16)
    note: str | None = None


class FilamentColorMappingUpdate(BaseModel):
    brand_id: int | None = Field(default=None, gt=0)
    type_series_id: int | None = Field(default=None, gt=0)
    color_name: str | None = Field(default=None, min_length=1, max_length=120)
    color_hex: str | None = Field(default=None, min_length=1, max_length=16)
    note: str | None = None


class FilamentColorMappingRead(BaseModel):
    id: int
    brand_id: int | None = None
    brand_name: str | None = None
    type_series_id: int | None = None
    material_type: str | None = None
    series_name: str | None = None
    material: str | None = None
    series: str | None = None
    tray_info_idx: str | None = None
    color_name: str
    color_hex: str
    hex_value: str | None = None
    official_name: str | None = None
    note: str | None
    color_source: str | None = None
    official_color_code: str | None = None
    official_color_type: str | None = None
    official_color_names: dict[str, str] | None = None
    official_colors: list[str] | None = None
    official_match_ambiguous: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FilamentColorMappingGapRead(BaseModel):
    sku_id: int
    color_name: str | None
    color_hex: str | None
    missing: list[str]
    type_series: list[dict[str, Any]] = Field(default_factory=list)
    brands: list[dict[str, Any]] = Field(default_factory=list)


class FilamentInventorySummaryRead(BaseModel):
    totals: dict[str, int]
    skus: list[dict[str, Any]]
    sealed_stock: list[dict[str, Any]]
    opened_spools: list[dict[str, Any]]
    ams_spools: list[dict[str, Any]]
    needs_location_spools: list[dict[str, Any]]
    empty_spools: list[dict[str, Any]] = Field(default_factory=list)
    archived_spools: list[dict[str, Any]] = Field(default_factory=list)
    history_spools: list[dict[str, Any]] = Field(default_factory=list)


class SlotBindRequest(BaseModel):
    spool_id: int


class RawMqttMessageRead(BaseModel):
    id: int
    printer_id: int
    topic: str | None
    command: str | None
    payload: dict[str, Any]
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatabaseRetentionCleanupRead(BaseModel):
    started_at: datetime
    finished_at: datetime
    raw_mqtt_db_limit: str | None = None
    limit_bytes: int | None = None
    trigger_threshold_bytes: int | None = None
    database_size_before_bytes: int | None = None
    database_size_after_bytes: int | None = None
    deleted_rows: int = 0
    nullified_device_metric_samples: int = 0
    nullified_ams_slot_history_samples: int = 0
    vacuumed: bool = False
    blocked_non_raw_size: bool = False
    skipped_reason: str | None = None
    error: str | None = None


class DatabaseRetentionStatusRead(BaseModel):
    raw_mqtt_db_limit: RawMqttDbLimit
    limit_bytes: int | None = None
    trigger_threshold_bytes: int | None = None
    database_size_bytes: int
    sqlite: bool
    enforcement_supported: bool
    is_over_threshold: bool
    raw_mqtt_row_count: int
    raw_mqtt_payload_bytes_estimate: int
    raw_mqtt_oldest_received_at: datetime | None = None
    raw_mqtt_newest_received_at: datetime | None = None
    retention_running: bool
    retention_running_since: datetime | None = None
    last_cleanup: DatabaseRetentionCleanupRead | None = None


class DatabaseRetentionUpdate(BaseModel):
    raw_mqtt_db_limit: RawMqttDbLimit


class PrinterEventRead(BaseModel):
    id: int
    printer_id: int
    event_type: str
    severity: str
    message: str
    dedupe_key: str | None
    data: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedEventRead(BaseModel):
    id: int
    source: str
    printer_id: int | None = None
    spool_id: int | None = None
    type: str
    event_type: str
    severity: str
    active: bool | None = None
    message: str
    dedupe_key: str | None = None
    data: dict[str, Any] | None = None
    created_at: datetime


class PrintLogEntryRead(BaseModel):
    id: int
    printer_id: int
    printer_name_snapshot: str | None
    task_id: str | None
    print_name: str | None
    gcode_file: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: int | None
    max_progress: int | None
    final_progress: int | None
    layer_current: int | None
    layer_total: int | None
    filament_summary: dict[str, Any]
    hms_summary: list[dict[str, Any]]
    failure_reason: str | None
    raw_refs: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrintLogListRead(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PrintLogEntryRead]


class PrintLogSummaryRead(BaseModel):
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    total: int
    running: int
    succeeded: int
    failed: int
    cancelled: int
    total_duration_seconds: int
    average_duration_seconds: float | None = None
    longest_duration_seconds: int | None = None
    success_rate: float = 0.0
    failure_rate: float = 0.0
    cancelled_rate: float = 0.0
    by_printer: list[dict[str, Any]] = Field(default_factory=list)
    by_date: list[dict[str, Any]] = Field(default_factory=list)
    by_failure_reason: list[dict[str, Any]] = Field(default_factory=list)
    by_hms: list[dict[str, Any]] = Field(default_factory=list)


class PrintLogAnalyticsRead(BaseModel):
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    printer_id: int | None = None
    bucket: str
    total: int
    running: int
    succeeded: int
    failed: int
    cancelled: int
    success_rate: float
    failure_rate: float
    cancelled_rate: float
    total_duration_seconds: int
    average_duration_seconds: float | None = None
    longest_duration_seconds: int | None = None
    by_printer: list[dict[str, Any]] = Field(default_factory=list)
    by_date: list[dict[str, Any]] = Field(default_factory=list)
    by_failure_reason: list[dict[str, Any]] = Field(default_factory=list)
    by_hms: list[dict[str, Any]] = Field(default_factory=list)


class MaintenanceTypeRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    interval_type: str
    default_interval: float
    icon: str | None
    wiki_url: str | None
    is_system_default: bool

    model_config = ConfigDict(from_attributes=True)


class PrinterMaintenanceRead(BaseModel):
    id: int
    printer_id: int
    printer_name: str | None = None
    target_type: str = "printer"
    target_label: str | None = None
    maintenance_type: MaintenanceTypeRead
    enabled: bool
    custom_interval: float | None
    interval: float
    last_performed_at: datetime | None
    last_performed_print_hours: float
    current_print_hours: float
    hours_since_last: float
    hours_until_due: float
    due_status: str
    history_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceOverviewRead(BaseModel):
    total_items: int
    due_count: int
    soon_count: int
    ok_count: int
    printers: list[dict[str, Any]] = Field(default_factory=list)
    items: list[PrinterMaintenanceRead] = Field(default_factory=list)


class PrinterMaintenanceUpdate(BaseModel):
    enabled: bool | None = None
    custom_interval: float | None = Field(default=None, ge=0)
    last_performed_at: datetime | None = None
    last_performed_print_hours: float | None = Field(default=None, ge=0)


class MaintenancePerformRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    performed_at: datetime | None = None
    print_hours: float | None = Field(default=None, ge=0)


class MaintenanceHistoryRead(BaseModel):
    id: int
    maintenance_item_id: int
    performed_at: datetime
    print_hours: float
    note: str | None

    model_config = ConfigDict(from_attributes=True)


class SystemInfoRead(BaseModel):
    app_version: str
    uptime_seconds: float
    database_size_bytes: int
    storage_size_bytes: int
    cpu_percent: float | None = None
    memory: dict[str, Any]
    configured_printers: int
    online_printers: int


class SupportBundleRead(BaseModel):
    generated_at: datetime
    system: SystemInfoRead
    recent_events: list[dict[str, Any]]
    recent_mqtt: list[dict[str, Any]]
    recent_connection_events: list[dict[str, Any]] = Field(default_factory=list)
    recent_mqtt_errors: list[dict[str, Any]] = Field(default_factory=list)
    recent_storage_errors: list[dict[str, Any]] = Field(default_factory=list)
    config_summary: dict[str, Any]
    notification_summary: dict[str, Any] = Field(default_factory=dict)
    experimental_features: dict[str, Any] = Field(default_factory=dict)
    frontend: dict[str, Any] = Field(default_factory=dict)
    privacy: dict[str, Any]


class HmsCodeInfoRead(BaseModel):
    short_code: str
    module: str
    severity: str
    message_zh: str
    message_en: str
    suggestion_zh: str
    suggestion_en: str
    wiki_url: str | None = None
    known: bool = True
    actionable: bool = True


class HmsCodeStatsRead(BaseModel):
    short_code: str
    printer_id: int | None = None
    days: int
    recent_count: int
    active_count: int
    recovered_count: int
    affected_printers: list[int] = Field(default_factory=list)
    last_seen_at: datetime | None = None
    last_recovered_at: datetime | None = None
    high_frequency: bool = False
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class DeviceStatusSnapshotRead(BaseModel):
    id: int
    printer_id: int
    print_status: dict[str, Any]
    derived_status: dict[str, Any]
    temperatures: dict[str, Any]
    fans: dict[str, Any]
    network: dict[str, Any]
    hardware: dict[str, Any]
    nozzles: dict[str, Any]
    storage: dict[str, Any]
    camera: dict[str, Any]
    camera_options: dict[str, Any]
    lights: dict[str, Any]
    speed: dict[str, Any]
    calibration: dict[str, Any]
    ams_status: dict[str, Any]
    hms_errors: list[dict[str, Any]]
    firmware: dict[str, Any]
    accessories: dict[str, Any]
    external_slots: list[dict[str, Any]]
    unsupported_features: dict[str, Any]
    data_coverage: dict[str, Any]
    raw_refs: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrinterDashboardRead(BaseModel):
    printer: PrinterRead
    state: PrinterStateRead | None
    device_snapshot: DeviceStatusSnapshotRead | None
    ams_units: list[AmsUnitRead]
    ams_slots: list[AmsSlotRead]
    recent_events: list[PrinterEventRead]
    recent_print_logs: list[PrintLogEntryRead] = Field(default_factory=list)
    maintenance_due_count: int = 0


class PrinterCameraCapabilitiesRead(BaseModel):
    available: bool
    stream_path: str | None = None
    source: str | None = None
    ports: dict[str, bool] = Field(default_factory=dict)
    liveview_enabled: bool | None = None
    rtsp_advertised: bool = False
    detail: str | None = None


class DashboardSummaryItemRead(BaseModel):
    printer: PrinterRead
    state: PrinterStateRead | None
    device_snapshot: DeviceStatusSnapshotRead | None
    recent_print_logs: list[PrintLogEntryRead] = Field(default_factory=list)
    maintenance_due_count: int = 0


class DeviceMetricSampleRead(BaseModel):
    id: int
    printer_id: int
    metric: str
    value_float: float | None
    value_text: str | None
    unit: str | None
    raw_message_id: int | None
    details: dict[str, Any]
    sampled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrinterStorageFileRead(BaseModel):
    id: int
    printer_id: int
    path: str
    name: str
    size: int | None
    modified_at: datetime | None
    type: str | None
    source: str
    raw: dict[str, Any]
    last_scanned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StorageSummaryRead(BaseModel):
    printer_id: int
    file_count: int
    total_size: int
    by_type: dict[str, int]
    storage_usage: dict[str, Any] = Field(default_factory=dict)
    recent_files: list[PrinterStorageFileRead] = Field(default_factory=list)
    timelapse_files: list[PrinterStorageFileRead] = Field(default_factory=list)
    last_scan_event: UnifiedEventRead | None = None
    last_scan: dict[str, Any] | None = None


class StorageScanResultRead(BaseModel):
    success: bool
    error: str | None = None
    scanned_count: int = 0
    new_count: int = 0
    existing_count: int = 0
    failed_count: int = 0
    files: list[PrinterStorageFileRead] = Field(default_factory=list)


class TimelapseNoteRead(BaseModel):
    id: int
    printer_id: int
    path: str
    favorite: bool
    note: str | None
    cached_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelapseNoteUpdate(BaseModel):
    path: str = Field(min_length=1)
    favorite: bool | None = None
    note: str | None = Field(default=None, max_length=4000)
    cached_metadata: dict[str, Any] | None = None


class NotificationTargetCreate(BaseModel):
    channel: str = Field(pattern="^(webhook|ntfy)$")
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class NotificationTargetUpdate(BaseModel):
    channel: str | None = Field(default=None, pattern="^(webhook|ntfy)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class NotificationTargetRead(BaseModel):
    id: int
    channel: str
    name: str
    enabled: bool
    config: dict[str, Any]
    display_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationRuleCreate(BaseModel):
    name: str = Field(default="Notification rule", min_length=1, max_length=120)
    enabled: bool = True
    event_types: list[str] = Field(default_factory=list)
    printer_ids: list[int] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)
    quiet_policy: dict[str, Any] = Field(default_factory=dict)


class NotificationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    event_types: list[str] | None = None
    printer_ids: list[int] | None = None
    severities: list[str] | None = None
    quiet_policy: dict[str, Any] | None = None


class NotificationRuleRead(BaseModel):
    id: int
    name: str
    enabled: bool
    event_types: list[str]
    printer_ids: list[int]
    severities: list[str]
    quiet_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryRead(BaseModel):
    id: int
    target_id: int | None
    rule_id: int | None
    event_id: int | None
    printer_id: int | None
    event_type: str
    status: str
    error_summary: str | None
    response_status: int | None
    sent_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceCapabilitiesRead(BaseModel):
    model_family: str
    model_hint: str | None = None
    known: bool
    supports_ams: bool | None = None
    supports_ams_ht: bool | None = None
    supports_chamber_temperature: bool | None = None
    supports_aux_fan: bool | None = None
    supports_camera_fields: bool | None = None
    has_carbon_rods: bool | None = None
    xy_motion: str | None = None
    recommended_maintenance: list[str] = Field(default_factory=list)
    visible_fields: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class MqttPayloadIn(BaseModel):
    topic: str | None = None
    payload: dict[str, Any]


class DiscoveryCandidateRead(BaseModel):
    host: str
    hostname: str | None
    open_ports: list[int]
    confidence: float
    reason: str
    serial: str | None
    device_name: str | None
    model: str | None
    connection_mode: str | None
    bind_state: str | None
    secure_link: str | None
    firmware_version: str | None
    has_basic_info: bool
    validation_source: str | None
    validation_message: str | None
    ssdp: dict[str, str]
