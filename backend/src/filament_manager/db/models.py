from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class Printer(Base, TimestampMixin):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Printer")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=8883)
    serial: Mapped[str] = mapped_column(String(128))
    access_code: Mapped[str] = mapped_column(String(255))
    tls_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    certificate_verify: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    connection_status: Mapped[str] = mapped_column(String(40), default="disconnected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_hours_offset: Mapped[float] = mapped_column(Float, default=0.0)

    raw_messages: Mapped[list[RawMqttMessage]] = relationship(
        back_populates="printer",
        cascade="all, delete-orphan",
    )


class RawMqttMessage(Base):
    __tablename__ = "raw_mqtt_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    command: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    printer: Mapped[Printer] = relationship(back_populates="raw_messages")


class PrinterStateSnapshot(Base):
    __tablename__ = "printer_state_snapshots"
    __table_args__ = (UniqueConstraint("printer_id", name="uq_printer_state_snapshot_printer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    gcode_state: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    print_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mc_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mc_remaining_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gcode_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtask_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DeviceStatusSnapshot(Base):
    __tablename__ = "device_status_snapshots"
    __table_args__ = (UniqueConstraint("printer_id", name="uq_device_status_snapshot_printer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    print_status: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    derived_status: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    temperatures: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fans: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    network: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hardware: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    nozzles: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    storage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    camera: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    camera_options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    speed: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    calibration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ams_status: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hms_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    firmware: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    accessories: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    external_slots: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    unsupported_features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    data_coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_refs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DeviceMetricSample(Base):
    __tablename__ = "device_metric_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(120), index=True)
    value_float: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_mqtt_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PrinterStorageFile(Base):
    __tablename__ = "printer_storage_files"
    __table_args__ = (UniqueConstraint("printer_id", "path", name="uq_printer_storage_file_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(255))
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="ftps")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AmsUnit(Base):
    __tablename__ = "ams_units"
    __table_args__ = (UniqueConstraint("printer_id", "ams_id", name="uq_ams_unit_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    ams_id: Mapped[str] = mapped_column(String(40), index=True)
    humidity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def humidity_raw(self) -> Any:
        return _raw_get(self.raw, "humidity_raw", "humidity")

    @property
    def serial_number(self) -> Any:
        return _raw_get(self.raw, "serial_number", "sn")

    @property
    def sw_ver(self) -> Any:
        return _raw_get(self.raw, "sw_ver", "firmware_version")

    @property
    def module_type(self) -> Any:
        return _raw_get(self.raw, "module_type")

    @property
    def dry_time(self) -> Any:
        return _raw_get(self.raw, "dry_time")

    @property
    def dry_status(self) -> Any:
        return _raw_get(self.raw, "dry_status")

    @property
    def dry_sub_status(self) -> Any:
        return _raw_get(self.raw, "dry_sub_status")

    @property
    def dry_sf_reason(self) -> Any:
        return _raw_get(self.raw, "dry_sf_reason")

    @property
    def is_ams_ht(self) -> bool:
        module_type = str(self.module_type or "").lower()
        return module_type == "n3s" or module_type.endswith("ht")

    @property
    def ams_type_name(self) -> str:
        return _ams_type_name(self.raw)

    @property
    def dry_status_name(self) -> str | None:
        return _code_name(self.dry_status, AMS_DRY_STATUS_NAMES)

    @property
    def dry_sub_status_name(self) -> str | None:
        return _code_name(self.dry_sub_status, AMS_DRY_SUB_STATUS_NAMES)

    @property
    def dry_sf_reason_names(self) -> list[str]:
        value = self.dry_sf_reason
        if not isinstance(value, list):
            return []
        names: list[str] = []
        for item in value:
            names.append(_code_name(item, AMS_DRY_REASON_NAMES) or f"unknown:{item}")
        return names


class AmsLabel(Base, TimestampMixin):
    __tablename__ = "ams_labels"
    __table_args__ = (UniqueConstraint("printer_id", "ams_id", name="uq_ams_label_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    ams_id: Mapped[str] = mapped_column(String(40), index=True)
    display_name: Mapped[str] = mapped_column(String(120))


class AmsSlot(Base):
    __tablename__ = "ams_slots"
    __table_args__ = (UniqueConstraint("printer_id", "ams_id", "tray_id", name="uq_ams_slot_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    ams_id: Mapped[str] = mapped_column(String(40), index=True)
    tray_id: Mapped[str] = mapped_column(String(40), index=True)
    slot_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    series: Mapped[str | None] = mapped_column(String(120), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remain: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tray_uuid: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tag_uid: Mapped[str | None] = mapped_column(String(160), nullable=True)
    identity_key: Mapped[str | None] = mapped_column(String(220), nullable=True, index=True)
    identity_source: Mapped[str] = mapped_column(String(40), default="manual_required")
    identity_confidence: Mapped[float] = mapped_column(default=0.0)
    identity_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_transitioning: Mapped[bool] = mapped_column(Boolean, default=False)
    spool_id: Mapped[int | None] = mapped_column(ForeignKey("spools.id", ondelete="SET NULL"), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def tray_id_name(self) -> Any:
        return _raw_get(self.raw, "tray_id_name")

    @property
    def tray_info_idx(self) -> Any:
        return _raw_get(self.raw, "tray_info_idx")

    @property
    def nozzle_temp_min(self) -> Any:
        return _raw_get(self.raw, "nozzle_temp_min")

    @property
    def nozzle_temp_max(self) -> Any:
        return _raw_get(self.raw, "nozzle_temp_max")

    @property
    def drying_temp(self) -> Any:
        return _raw_get(self.raw, "drying_temp")

    @property
    def drying_time(self) -> Any:
        return _raw_get(self.raw, "drying_time")

    @property
    def cali_idx(self) -> Any:
        return _raw_get(self.raw, "cali_idx")

    @property
    def k(self) -> Any:
        return _raw_get(self.raw, "k")

    @property
    def state_code(self) -> Any:
        return _raw_get(self.raw, "state")

    @property
    def state_name(self) -> str | None:
        return _slot_state_name(self.state_code)

    @property
    def tray_state_name(self) -> str | None:
        raw_state = _raw_get(self.raw, "tray_state", "slot_state", "tray_status", "state")
        return _slot_state_name(raw_state)


class AmsSlotHistorySample(Base):
    __tablename__ = "ams_slot_history_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    ams_id: Mapped[str] = mapped_column(String(40), index=True)
    tray_id: Mapped[str] = mapped_column(String(40), index=True)
    state_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remain: Mapped[int | None] = mapped_column(Integer, nullable=True)
    k: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cali_idx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rfid_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    raw_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_mqtt_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class Spool(Base, TimestampMixin):
    __tablename__ = "spools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_key: Mapped[str | None] = mapped_column(String(220), unique=True, nullable=True, index=True)
    identity_source: Mapped[str] = mapped_column(String(40), default="manual")
    display_name: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    series: Mapped[str | None] = mapped_column(String(120), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="sealed")
    sealed_quantity: Mapped[int] = mapped_column(Integer, default=1)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id", ondelete="SET NULL"), nullable=True)
    current_ams_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_tray_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class SpoolLocation(Base):
    __tablename__ = "spool_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spool_id: Mapped[int] = mapped_column(ForeignKey("spools.id", ondelete="CASCADE"), index=True)
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id", ondelete="SET NULL"), nullable=True)
    ams_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tray_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), default="spool.location_changed")
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PrintLogEntry(Base):
    __tablename__ = "print_log_entries"
    __table_args__ = (UniqueConstraint("printer_id", "task_id", name="uq_print_log_printer_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    printer_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    print_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    gcode_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layer_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layer_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filament_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hms_summary: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_refs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MaintenanceType(Base, TimestampMixin):
    __tablename__ = "maintenance_types"
    __table_args__ = (UniqueConstraint("code", name="uq_maintenance_type_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_type: Mapped[str] = mapped_column(String(40), default="print_hours")
    default_interval: Mapped[float] = mapped_column(Float, default=100.0)
    icon: Mapped[str | None] = mapped_column(String(80), nullable=True)
    wiki_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system_default: Mapped[bool] = mapped_column(Boolean, default=True)


class PrinterMaintenance(Base, TimestampMixin):
    __tablename__ = "printer_maintenance"
    __table_args__ = (UniqueConstraint("printer_id", "maintenance_type_id", name="uq_printer_maintenance_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    maintenance_type_id: Mapped[int] = mapped_column(ForeignKey("maintenance_types.id", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_interval: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_performed_print_hours: Mapped[float] = mapped_column(Float, default=0.0)

    maintenance_type: Mapped[MaintenanceType] = relationship()


class MaintenanceHistory(Base):
    __tablename__ = "maintenance_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    maintenance_item_id: Mapped[int] = mapped_column(ForeignKey("printer_maintenance.id", ondelete="CASCADE"), index=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    print_hours: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    maintenance_item: Mapped[PrinterMaintenance] = relationship()


class PrinterEvent(Base):
    __tablename__ = "printer_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class NotificationTarget(Base, TimestampMixin):
    __tablename__ = "notification_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    display_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NotificationRule(Base, TimestampMixin):
    __tablename__ = "notification_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Notification rule")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    event_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    printer_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    severities: Mapped[list[str]] = mapped_column(JSON, default=list)
    quiet_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_targets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("printer_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    printer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class TimelapseNote(Base, TimestampMixin):
    __tablename__ = "timelapse_notes"
    __table_args__ = (UniqueConstraint("printer_id", "path", name="uq_timelapse_note_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spool_id: Mapped[int] = mapped_column(ForeignKey("spools.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    quantity_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


def _raw_get(raw: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(raw, dict):
        return None
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value
    return None


AMS_DRY_STATUS_NAMES = {
    "0": "idle",
    "1": "drying",
    "2": "cooling",
    "idle": "idle",
    "drying": "drying",
    "cooling": "cooling",
    "done": "done",
}
AMS_DRY_SUB_STATUS_NAMES = {
    "0": "none",
    "1": "preheating",
    "2": "holding",
    "3": "cooling",
    "4": "completed",
}
AMS_DRY_REASON_NAMES = {
    "2": "temperature_not_reached",
    "3": "humidity_sensor",
    "4": "door_or_cover_open",
    "6": "cooling",
    "9": "completed_or_stopped",
}
AMS_SLOT_STATE_NAMES = {
    "0": "empty",
    "1": "empty",
    "4": "loading",
    "5": "unloading",
    "9": "filament_present",
    "10": "filament_present",
    "11": "loaded",
    "17": "transitioning",
    "21": "transitioning",
    "25": "rfid_reading",
    "27": "rfid_reading_or_transitioning",
    "idle": "loaded",
    "loaded": "loaded",
    "reading": "rfid_reading",
    "loading": "loading",
    "unloading": "unloading",
}


def _code_name(value: Any, mapping: dict[str, str]) -> str | None:
    if value is None or value == "":
        return None
    return mapping.get(str(value).strip().lower()) or mapping.get(str(value).strip())


def _ams_type_name(raw: dict[str, Any] | None) -> str:
    if not isinstance(raw, dict):
        return "unknown"
    raw_type = str(
        raw.get("module_type")
        or raw.get("info")
        or raw.get("ams_type")
        or raw.get("type")
        or ""
    ).strip().lower()
    if raw_type in {"ams", "n3", "n1"} or raw_type.startswith("ams/"):
        return "AMS"
    if raw_type in {"n3f", "ams2", "ams_2_pro", "ams 2 pro"} or "2 pro" in raw_type:
        return "AMS 2 Pro"
    if raw_type in {"n3s", "ams_ht", "ams ht"} or raw_type.endswith("ht"):
        return "AMS HT"
    return "unknown"


def _slot_state_name(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    return AMS_SLOT_STATE_NAMES.get(text.lower()) or f"unknown:{text}"
