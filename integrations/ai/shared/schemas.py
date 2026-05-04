from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListPrintersParams(StrictParams):
    include_status: bool = True


class PrinterIdParams(StrictParams):
    printer_id: int = Field(gt=0)


class AmsOverviewParams(PrinterIdParams):
    include_empty_slots: bool = True


class ListFilamentSpoolsParams(StrictParams):
    status: Literal["active", "sealed", "empty", "archived", "needs_review"] | None = None
    material: str | None = Field(default=None, max_length=40)
    brand: str | None = Field(default=None, max_length=120)
    location: Literal["ams", "storage", "unknown"] | None = None
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("material", "brand")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FilamentAnomaliesParams(StrictParams):
    printer_id: int = Field(gt=0)
    include_low_stock: bool = True
    include_ams_mismatch: bool = True
    include_review_needed: bool = True


class PrintLogSummaryParams(StrictParams):
    printer_id: int | None = Field(default=None, gt=0)
    days: int = Field(default=7, ge=1, le=90)


class RecentPrintLogsParams(StrictParams):
    printer_id: int | None = Field(default=None, gt=0)
    status: Literal["running", "success", "failed", "cancelled"] | None = None
    limit: int = Field(default=20, ge=1, le=50)


class RecentEventsParams(StrictParams):
    printer_id: int | None = Field(default=None, gt=0)
    severity: Literal["info", "warning", "error"] | None = None
    limit: int = Field(default=30, ge=1, le=100)


class HmsCodeInfoParams(StrictParams):
    short_code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class MaintenanceOverviewParams(StrictParams):
    printer_id: int | None = Field(default=None, gt=0)
    include_ok: bool = False


class ToolResponse(BaseModel):
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    redaction_applied: bool = False
    error_code: str | None = None
    message: str | None = None
