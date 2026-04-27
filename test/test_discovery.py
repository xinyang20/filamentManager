from __future__ import annotations

import threading

from filament_manager.services.discovery import DiscoveryCandidate, parse_ssdp_response, scan_lan_devices


def test_parse_ssdp_response_extracts_bambu_device_info() -> None:
    payload = "\r\n".join(
        [
            "HTTP/1.1 200 OK",
            "ST: urn:bambulab-com:device:3dprinter:1",
            "USN: SYNTHETIC-SERIAL::urn:bambulab-com:device:3dprinter:1",
            "DevModel.bambu.com: P1S",
            "DevName.bambu.com: Workshop Printer",
            "DevConnect.bambu.com: local",
            "DevBind.bambu.com: bound",
            "Devseclink.bambu.com: secure",
            "DevVersion.bambu.com: 01.00.00.00",
            "",
        ]
    )

    headers = parse_ssdp_response(payload)

    assert headers["st"] == "urn:bambulab-com:device:3dprinter:1"
    assert headers["usn"] == "SYNTHETIC-SERIAL::urn:bambulab-com:device:3dprinter:1"
    assert headers["devmodel.bambu.com"] == "P1S"
    assert headers["devname.bambu.com"] == "Workshop Printer"


def test_discovery_scan_api_returns_candidates(api_client, monkeypatch) -> None:
    from filament_manager.api import routes

    captured = {}

    def fake_scan_lan_devices(*, cidr=None, timeout=0.25, validation_timeout=None, max_hosts=512):
        captured["validation_timeout"] = validation_timeout
        return [
            DiscoveryCandidate(
                host="192.0.2.10",
                open_ports=[8883, 990],
                confidence=1.0,
                reason="Both Bambu feature ports are open; SSDP device information found",
                serial="SYNTHETIC-SERIAL",
                device_name="Workshop Printer",
                model="P1S",
                connection_mode="local",
                bind_state="bound",
                secure_link="secure",
                firmware_version="01.00.00.00",
                ssdp={"usn": "SYNTHETIC-SERIAL"},
            )
        ]

    monkeypatch.setattr(routes, "scan_lan_devices", fake_scan_lan_devices)

    response = api_client.get("/api/discovery/scan?validation_timeout=0.3")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["host"] == "192.0.2.10"
    assert body[0]["open_ports"] == [8883, 990]
    assert body[0]["serial"] == "SYNTHETIC-SERIAL"
    assert body[0]["device_name"] == "Workshop Printer"
    assert captured["validation_timeout"] == 0.3


def test_scan_filters_port_hits_without_valid_basic_info(monkeypatch) -> None:
    from filament_manager.services import discovery

    monkeypatch.setattr(discovery, "_resolve_networks", lambda cidr: ["synthetic-network"])
    monkeypatch.setattr(discovery, "_hosts_from_networks", lambda networks, max_hosts: ["192.0.2.10", "192.0.2.11"])
    monkeypatch.setattr(
        discovery,
        "discover_bambu_ssdp",
        lambda timeout=1.0: {
            "192.0.2.10": {
                "st": "urn:bambulab-com:device:3dprinter:1",
                "usn": "SYNTHETIC-SERIAL::urn:bambulab-com:device:3dprinter:1",
                "devname.bambu.com": "Workshop Printer",
                "devmodel.bambu.com": "P1S",
            },
            "192.0.2.11": {
                "st": "urn:bambulab-com:device:3dprinter:1",
            },
        },
    )
    monkeypatch.setattr(discovery, "_scan_host", lambda host, timeout: [8883, 990])

    candidates = scan_lan_devices()

    assert len(candidates) == 1
    assert candidates[0].host == "192.0.2.10"
    assert candidates[0].has_basic_info is True


def test_scan_uses_unicast_ssdp_when_multicast_misses_candidate(monkeypatch) -> None:
    from filament_manager.services import discovery

    monkeypatch.setattr(discovery, "_resolve_networks", lambda cidr: ["synthetic-network"])
    monkeypatch.setattr(discovery, "_hosts_from_networks", lambda networks, max_hosts: ["192.0.2.10"])
    monkeypatch.setattr(discovery, "discover_bambu_ssdp", lambda timeout=1.0: {})
    monkeypatch.setattr(discovery, "_scan_host", lambda host, timeout: [8883, 990])
    monkeypatch.setattr(
        discovery,
        "query_bambu_ssdp",
        lambda host, timeout=1.0: {
            "st": "urn:bambulab-com:device:3dprinter:1",
            "usn": "SYNTHETIC-SERIAL::urn:bambulab-com:device:3dprinter:1",
            "devname.bambu.com": "Workshop Printer",
            "devmodel.bambu.com": "P1S",
        },
    )

    candidates = scan_lan_devices()

    assert len(candidates) == 1
    assert candidates[0].host == "192.0.2.10"
    assert candidates[0].serial == "SYNTHETIC-SERIAL"


def test_candidate_validation_runs_in_parallel(monkeypatch) -> None:
    from filament_manager.services import discovery

    hosts = ["192.0.2.10", "192.0.2.11"]
    started: list[str] = []
    lock = threading.Lock()
    both_started = threading.Event()

    def fake_query(host, timeout=1.0):
        with lock:
            started.append(host)
            if len(started) == len(hosts):
                both_started.set()
        assert both_started.wait(0.5)
        return {
            "st": "urn:bambulab-com:device:3dprinter:1",
            "usn": f"SYNTHETIC-{host}::urn:bambulab-com:device:3dprinter:1",
            "devname.bambu.com": f"Printer {host}",
            "devmodel.bambu.com": "P1S",
        }

    monkeypatch.setattr(discovery, "_resolve_networks", lambda cidr: ["synthetic-network"])
    monkeypatch.setattr(discovery, "_hosts_from_networks", lambda networks, max_hosts: hosts)
    monkeypatch.setattr(discovery, "discover_bambu_ssdp", lambda timeout=1.0: {})
    monkeypatch.setattr(discovery, "_scan_host", lambda host, timeout: [8883, 990])
    monkeypatch.setattr(discovery, "query_bambu_ssdp", fake_query)

    candidates = scan_lan_devices(validation_timeout=0.1)

    assert len(candidates) == 2
    assert sorted(candidate.host for candidate in candidates) == hosts


def test_scan_host_skips_mqtt_probe_when_ftps_port_is_closed(monkeypatch) -> None:
    from filament_manager.services import discovery

    calls: list[int] = []

    def fake_is_port_open(host, port, timeout):
        calls.append(port)
        return False

    monkeypatch.setattr(discovery, "_is_port_open", fake_is_port_open)

    assert discovery._scan_host("192.0.2.10", 0.1) == []
    assert calls == [990]
