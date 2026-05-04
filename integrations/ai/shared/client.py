from __future__ import annotations

import re
from typing import Any

import httpx

from .config import AiIntegrationSettings
from .redaction import clean_error_message


ALLOWED_GET_PATTERNS = (
    re.compile(r"^/health$"),
    re.compile(r"^/printers$"),
    re.compile(r"^/printers/[1-9]\d*/dashboard$"),
    re.compile(r"^/printers/[1-9]\d*/ams/overview$"),
    re.compile(r"^/filament/inventory/summary$"),
    re.compile(r"^/filament/spools$"),
    re.compile(r"^/print-log$"),
    re.compile(r"^/print-log/summary$"),
    re.compile(r"^/print-log/analytics$"),
    re.compile(r"^/events$"),
    re.compile(r"^/hms/codes/[A-Za-z0-9_-]{1,80}$"),
    re.compile(r"^/hms/codes/[A-Za-z0-9_-]{1,80}/stats$"),
    re.compile(r"^/maintenance/overview$"),
    re.compile(r"^/printers/[1-9]\d*/maintenance$"),
)


class ApiAccessError(ValueError):
    def __init__(self, message: str, *, code: str = "api_access_denied") -> None:
        super().__init__(message)
        self.code = code


class ApiClientError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_get_path(method: str, path: str) -> None:
    if method.upper() != "GET":
        raise ApiAccessError("Only GET requests are allowed", code="method_not_allowed")
    if "?" in path or "://" in path:
        raise ApiAccessError("Only fixed relative API paths are allowed")
    normalized = path if path.startswith("/") else f"/{path}"
    if normalized.startswith("/api/"):
        normalized = normalized[4:]
    if not any(pattern.fullmatch(normalized) for pattern in ALLOWED_GET_PATTERNS):
        raise ApiAccessError("The requested API path is not available to AI tools")


class FilamentManagerApiClient:
    def __init__(
        self,
        settings: AiIntegrationSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or AiIntegrationSettings.from_env()
        self._client = httpx.AsyncClient(
            base_url=self.settings.api_base_url,
            timeout=self.settings.timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> "FilamentManagerApiClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        normalized = path if path.startswith("/") else f"/{path}"
        validate_get_path("GET", normalized)
        try:
            response = await self._client.get(normalized, params={k: v for k, v in (params or {}).items() if v is not None})
        except httpx.TimeoutException as exc:
            raise ApiClientError("backend_timeout", "Backend request timed out") from exc
        except httpx.HTTPError as exc:
            raise ApiClientError("backend_unreachable", "Backend is not reachable") from exc

        if response.status_code >= 400:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            message, _ = clean_error_message(detail)
            raise ApiClientError("backend_error", f"Backend returned HTTP {response.status_code}: {message}")

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ApiClientError("invalid_backend_response", "Backend returned a non-JSON response") from exc
