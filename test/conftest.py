from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from filament_manager.main import create_app  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'filament_manager_test.db'}"
    app = create_app(database_url=database_url)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def printer_payload() -> dict[str, object]:
    return {
        "name": "Synthetic Printer",
        "host": "printer.local",
        "port": 8883,
        "serial": "SYNTHETIC123",
        "access_code": "secret-access-code",
        "tls_enabled": True,
        "certificate_verify": False,
    }
