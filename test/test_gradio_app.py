from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import gradio as gr
import pytest


def _load_gradio_app() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "frontend" / "gradio" / "app.py"
    spec = importlib.util.spec_from_file_location("filament_manager_gradio_app", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_printer_id_parser_rejects_empty_gradio_value() -> None:
    app = _load_gradio_app()

    with pytest.raises(gr.Error):
        app._printer_id_or_error([], app.DEFAULT_LANGUAGE)


def test_printer_id_parser_accepts_dropdown_value_shapes() -> None:
    app = _load_gradio_app()

    assert app._printer_id_or_error(3, app.DEFAULT_LANGUAGE) == 3
    assert app._printer_id_or_error(3.0, app.DEFAULT_LANGUAGE) == 3
    assert app._printer_id_or_error("3: Printer", app.DEFAULT_LANGUAGE) == 3
    assert app._printer_id_or_error([3], app.DEFAULT_LANGUAGE) == 3


def test_refresh_printers_updates_dropdown_choices(monkeypatch) -> None:
    app = _load_gradio_app()

    monkeypatch.setattr(
        app,
        "_request",
        lambda method, path, language=None: [
            {
                "id": 3,
                "name": "Synthetic Printer",
                "host": "192.0.2.10",
                "port": 8883,
                "serial": "SYNTHETIC-SERIAL",
                "tls_enabled": True,
                "certificate_verify": False,
                "connection_status": "disconnected",
                "last_sync_at": None,
                "last_error": None,
            }
        ],
    )

    _rows, dropdown_update = app.refresh_printers(app.DEFAULT_LANGUAGE)

    assert dropdown_update["__type__"] == "update"
    assert dropdown_update["value"] == 3
    assert dropdown_update["choices"][0][1] == 3


def test_dashboard_rows_fall_back_to_state_payload(monkeypatch) -> None:
    app = _load_gradio_app()

    def fake_request(method, path, body=None, language=None):
        assert method == "GET"
        assert path == "/printers/3/dashboard"
        return {
            "printer": {"id": 3, "name": "Synthetic", "host": "printer.local", "serial": "SYNTHETIC"},
            "state": {
                "gcode_state": "IDLE",
                "payload": {
                    "wifi_signal": "-52dBm",
                    "print": {
                        "gcode_state": "IDLE",
                        "bed_temper": "27",
                        "nozzle_temper": "31",
                        "cooling_fan_speed": "8",
                        "wifi_signal": "-51dBm",
                        "nozzle_type": "HS01",
                        "nozzle_diameter": "0.4",
                        "device": {"extruder": {"info": [{"id": 0}]}}
                    },
                },
            },
            "device_snapshot": {},
            "ams_units": [],
            "ams_slots": [],
            "recent_events": [],
        }

    monkeypatch.setattr(app, "_request", fake_request)

    _overview, derived, thermal, network_hardware, camera, _ams, _hms, _coverage, _raw = app.load_dashboard(
        3,
        app.DEFAULT_LANGUAGE,
    )

    assert ["derived_status", "heating_bed", False] in derived
    assert ["temperatures", "bed", 27.0] in thermal
    assert ["fans", "cooling_fan_speed.percent", 53] in thermal
    assert ["network", "wifi_signal", -51] in network_hardware
    assert ["hardware", "nozzle_type", "HS01"] in network_hardware
    assert ["hardware", "extruder_count", 1] in network_hardware
    assert camera == []


def test_full_refresh_updates_dashboard_tables(monkeypatch) -> None:
    app = _load_gradio_app()
    calls: list[tuple[str, str]] = []

    def fake_request(method, path, body=None, language=None):
        calls.append((method, path))
        if method == "POST" and path == "/printers/3/refresh-full":
            return {"pushall": "p", "get_version": "v", "get_accessories": "a"}
        if method == "GET" and path == "/printers/3/dashboard":
            return {
                "printer": {"id": 3, "name": "Synthetic", "host": "printer.local", "serial": "SYNTHETIC"},
                "state": {"gcode_state": "IDLE"},
                "device_snapshot": {
                    "temperatures": {"bed": 26.0},
                    "fans": {"cooling_fan_speed": {"raw": "0", "percent": 0}},
                    "network": {"wifi_signal": -42},
                    "hardware": {"nozzle_type": "HS01"},
                    "firmware": {"printer_version": "01.02.03.04"},
                },
                "ams_units": [],
                "ams_slots": [],
                "recent_events": [],
            }
        raise AssertionError((method, path))

    monkeypatch.setattr(app, "_request", fake_request)

    (
        result,
        _overview,
        _derived,
        thermal,
        network_hardware,
        _camera,
        _ams,
        _hms,
        _coverage,
        _raw,
    ) = app.refresh_full_and_load_dashboard(
        3,
        app.DEFAULT_LANGUAGE,
    )

    assert '"pushall": "p"' in result
    assert ["temperatures", "bed", 26.0] in thermal
    assert ["fans", "cooling_fan_speed.percent", 0] in thermal
    assert ["network", "wifi_signal", -42] in network_hardware
    assert ("POST", "/printers/3/refresh-full") in calls


def test_metrics_rows_split_by_metric_group(monkeypatch) -> None:
    app = _load_gradio_app()

    def fake_request(method, path, body=None, language=None):
        assert method == "GET"
        assert path == "/printers/3/metrics?limit=500"
        return [
            {"sampled_at": "t1", "metric": "temperature.bed", "value_float": 60, "unit": "celsius", "details": {}},
            {"sampled_at": "t2", "metric": "fan.cooling_fan_speed.percent", "value_float": 53, "unit": "percent", "details": {}},
            {"sampled_at": "t3", "metric": "ams.0.humidity", "value_float": 4, "unit": "percent", "details": {"ams_id": "0"}},
            {"sampled_at": "t4", "metric": "print.progress", "value_float": 25, "unit": "percent", "details": {}},
        ]

    monkeypatch.setattr(app, "_request", fake_request)

    temperatures, fan_network, ams, progress = app.load_metrics(3, app.DEFAULT_LANGUAGE)

    assert temperatures[0][1] == "temperature.bed"
    assert fan_network[0][1] == "fan.cooling_fan_speed.percent"
    assert ams[0][1] == "ams.0.humidity"
    assert progress[0][1] == "print.progress"


def test_storage_rows_and_stats(monkeypatch) -> None:
    app = _load_gradio_app()

    def fake_request(method, path, body=None, language=None):
        assert method == "GET"
        assert path == "/printers/3/storage/files"
        return [
            {
                "path": "/timelapse/demo.mp4",
                "name": "demo.mp4",
                "size": 1024,
                "modified_at": None,
                "type": "timelapse",
                "source": "ftps",
            }
        ]

    monkeypatch.setattr(app, "_request", fake_request)

    rows, stats = app.load_storage(3, app.DEFAULT_LANGUAGE)

    assert rows[0][0] == "/timelapse/demo.mp4"
    assert ["file_count", 1] in stats
    assert ["total_size_bytes", 1024] in stats
    assert ["timelapse_count", 1] in stats
