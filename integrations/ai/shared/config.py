from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator


class AiIntegrationSettings(BaseModel):
    api_base_url: str = Field(default="http://127.0.0.1:8000/api")
    timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    max_items: int = Field(default=100, ge=1, le=100)

    @field_validator("api_base_url")
    @classmethod
    def normalize_api_base_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return "http://127.0.0.1:8000/api"
        return value.rstrip("/")

    @classmethod
    def from_env(cls) -> "AiIntegrationSettings":
        return cls(
            api_base_url=os.getenv("FILAMENT_MANAGER_API_BASE_URL", "http://127.0.0.1:8000/api"),
            timeout_seconds=float(os.getenv("FILAMENT_MANAGER_MCP_TIMEOUT_SECONDS", "5")),
            max_items=int(os.getenv("FILAMENT_MANAGER_MCP_MAX_ITEMS", "100")),
        )
