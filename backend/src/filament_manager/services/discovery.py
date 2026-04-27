from __future__ import annotations

import ipaddress
import math
import socket
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass, field
from typing import Any

MQTT_TLS_PORT = 8883
FTPS_PORT = 990
BAMBU_FEATURE_PORTS = (MQTT_TLS_PORT, FTPS_PORT)
MAX_SCAN_WORKERS = 128
MAX_VALIDATION_WORKERS = 32
SSDP_ADDRESS = ("239.255.255.250", 2021)
SSDP_ST = "urn:bambulab-com:device:3dprinter:1"

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class DiscoveryCandidate:
    host: str
    open_ports: list[int]
    confidence: float
    reason: str
    hostname: str | None = None
    serial: str | None = None
    device_name: str | None = None
    model: str | None = None
    connection_mode: str | None = None
    bind_state: str | None = None
    secure_link: str | None = None
    firmware_version: str | None = None
    has_basic_info: bool = False
    validation_source: str | None = None
    validation_message: str | None = None
    ssdp: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "hostname": self.hostname,
            "open_ports": self.open_ports,
            "confidence": self.confidence,
            "reason": self.reason,
            "serial": self.serial,
            "device_name": self.device_name,
            "model": self.model,
            "connection_mode": self.connection_mode,
            "bind_state": self.bind_state,
            "secure_link": self.secure_link,
            "firmware_version": self.firmware_version,
            "has_basic_info": self.has_basic_info,
            "validation_source": self.validation_source,
            "validation_message": self.validation_message,
            "ssdp": self.ssdp,
        }


def scan_lan_devices(
    *,
    cidr: str | None = None,
    timeout: float = 0.25,
    validation_timeout: float | None = None,
    max_hosts: int = 512,
    progress_callback: ProgressCallback | None = None,
) -> list[DiscoveryCandidate]:
    _report(progress_callback, 0.02, "Resolving local scan range")
    networks = _resolve_networks(cidr)
    hosts = _hosts_from_networks(networks, max_hosts=max_hosts)
    if not hosts:
        return []

    _report(progress_callback, 0.08, "Querying Bambu SSDP device information")
    ssdp_timeout = _bounded_timeout(timeout * 2, minimum=0.2, maximum=1.0)
    validation_probe_timeout = _bounded_timeout(
        validation_timeout if validation_timeout is not None else timeout * 2,
        minimum=0.05,
        maximum=2.0,
    )
    ssdp_by_host = discover_bambu_ssdp(timeout=ssdp_timeout)
    port_hits: list[tuple[str, list[int]]] = []

    _report(progress_callback, 0.15, f"Scanning {len(hosts)} hosts for Bambu feature ports")
    worker_count = min(MAX_SCAN_WORKERS, max(4, len(hosts)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_scan_host, host, timeout): host for host in hosts}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            open_ports = future.result()
            if set(open_ports) == set(BAMBU_FEATURE_PORTS):
                port_hits.append((futures[future], open_ports))
            if completed == len(hosts) or completed % 8 == 0:
                _report(
                    progress_callback,
                    0.15 + 0.55 * (completed / len(hosts)),
                    f"Scanned {completed}/{len(hosts)} hosts",
                )

    candidates: list[DiscoveryCandidate] = []
    _report(progress_callback, 0.72, f"Validating {len(port_hits)} feature-port candidates")
    if port_hits:
        validation_workers = min(MAX_VALIDATION_WORKERS, len(port_hits))
        executor = ThreadPoolExecutor(max_workers=validation_workers)
        futures: set[Future[DiscoveryCandidate | None]] = {
            executor.submit(
                _validate_port_hit,
                host,
                open_ports,
                ssdp_by_host,
                validation_probe_timeout,
            )
            for host, open_ports in port_hits
        }
        completed = 0
        validation_deadline = time.monotonic() + _validation_budget(
            len(port_hits),
            validation_workers,
            validation_probe_timeout,
        )
        try:
            while futures:
                remaining = validation_deadline - time.monotonic()
                if remaining <= 0:
                    break
                done, futures = wait(
                    futures,
                    timeout=min(0.1, remaining),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    completed += 1
                    candidate = future.result()
                    if candidate is not None:
                        candidates.append(candidate)
                    _report(
                        progress_callback,
                        0.72 + 0.25 * (completed / len(port_hits)),
                        f"Validated {completed}/{len(port_hits)} candidates",
                    )
            if futures:
                skipped = len(futures)
                for future in futures:
                    future.cancel()
                completed += skipped
                _report(
                    progress_callback,
                    0.97,
                    f"Skipped {skipped} candidate validations after timeout",
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    _report(progress_callback, 1.0, "Discovery scan completed")
    return sorted(candidates, key=lambda item: (-item.confidence, item.host))


def discover_bambu_ssdp(timeout: float = 1.0) -> dict[str, dict[str, str]]:
    message = "\r\n".join(
        [
            "M-SEARCH * HTTP/1.1",
            f"HOST: {SSDP_ADDRESS[0]}:{SSDP_ADDRESS[1]}",
            'MAN: "ssdp:discover"',
            "MX: 1",
            f"ST: {SSDP_ST}",
            "",
            "",
        ]
    ).encode("ascii")
    responses: dict[str, dict[str, str]] = {}
    deadline = time.monotonic() + timeout

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", 0))
            sock.settimeout(timeout)
            sock.sendto(message, SSDP_ADDRESS)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    payload, address = sock.recvfrom(4096)
                except socket.timeout:
                    break
                headers = parse_ssdp_response(payload)
                if headers:
                    responses[address[0]] = headers
    except OSError:
        return responses

    return responses


def query_bambu_ssdp(host: str, timeout: float = 1.0) -> dict[str, str]:
    message = "\r\n".join(
        [
            "M-SEARCH * HTTP/1.1",
            f"HOST: {host}:{SSDP_ADDRESS[1]}",
            'MAN: "ssdp:discover"',
            "MX: 1",
            f"ST: {SSDP_ST}",
            "",
            "",
        ]
    ).encode("ascii")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            sock.sendto(message, (host, SSDP_ADDRESS[1]))
            payload, _address = sock.recvfrom(4096)
    except OSError:
        return {}
    return parse_ssdp_response(payload)


def parse_ssdp_response(payload: bytes | str) -> dict[str, str]:
    text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else payload
    headers: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def _resolve_networks(cidr: str | None) -> list[ipaddress.IPv4Network]:
    if cidr:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError("Invalid CIDR") from exc
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError("Only IPv4 CIDR is supported")
        return [network]

    networks: list[ipaddress.IPv4Network] = []
    for address in _local_ipv4_addresses():
        networks.append(ipaddress.ip_network(f"{address}/24", strict=False))
    return sorted(set(networks), key=str)


def _hosts_from_networks(networks: list[ipaddress.IPv4Network], *, max_hosts: int) -> list[str]:
    hosts: list[str] = []
    for network in networks:
        host_count = network.num_addresses - 2 if network.prefixlen < 31 else network.num_addresses
        if host_count > max_hosts:
            raise ValueError(f"Scan range is too large: {network}")
        hosts.extend(str(host) for host in network.hosts())
    return hosts


def _local_ipv4_addresses() -> list[ipaddress.IPv4Address]:
    addresses: set[ipaddress.IPv4Address] = set()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(ipaddress.ip_address(sock.getsockname()[0]))
    except OSError:
        pass

    try:
        host_name = socket.gethostname()
        for item in socket.getaddrinfo(host_name, None, socket.AF_INET):
            addresses.add(ipaddress.ip_address(item[4][0]))
    except OSError:
        pass

    return sorted(
        address
        for address in addresses
        if not address.is_loopback and not address.is_link_local and not address.is_multicast
    )


def _scan_host(host: str, timeout: float) -> list[int]:
    if not _is_port_open(host, FTPS_PORT, timeout):
        return []
    if not _is_port_open(host, MQTT_TLS_PORT, timeout):
        return [FTPS_PORT]
    return [MQTT_TLS_PORT, FTPS_PORT]


def _is_port_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _validate_port_hit(
    host: str,
    open_ports: list[int],
    ssdp_by_host: dict[str, dict[str, str]],
    validation_timeout: float,
) -> DiscoveryCandidate | None:
    ssdp = ssdp_by_host.get(host) or query_bambu_ssdp(host, timeout=validation_timeout)
    if not _has_expected_ssdp_basic_info(ssdp):
        return None
    return _build_candidate(host, open_ports, ssdp)


def _has_expected_ssdp_basic_info(ssdp: dict[str, str]) -> bool:
    if not ssdp:
        return False
    st = ssdp.get("st") or ssdp.get("nt")
    if st != SSDP_ST:
        return False
    if not _serial_from_ssdp(ssdp):
        return False
    return bool(ssdp.get("devname.bambu.com") or ssdp.get("devmodel.bambu.com"))


def _build_candidate(host: str, open_ports: list[int], ssdp: dict[str, str] | None) -> DiscoveryCandidate:
    ssdp = ssdp or {}
    confidence = _confidence(open_ports, ssdp)
    reason = _reason(open_ports, bool(ssdp))
    return DiscoveryCandidate(
        host=host,
        hostname=None,
        open_ports=open_ports,
        confidence=confidence,
        reason=reason,
        serial=_serial_from_ssdp(ssdp),
        device_name=ssdp.get("devname.bambu.com"),
        model=ssdp.get("devmodel.bambu.com"),
        connection_mode=ssdp.get("devconnect.bambu.com"),
        bind_state=ssdp.get("devbind.bambu.com"),
        secure_link=ssdp.get("devseclink.bambu.com"),
        firmware_version=ssdp.get("devversion.bambu.com"),
        has_basic_info=_has_expected_ssdp_basic_info(ssdp),
        validation_source="ssdp",
        validation_message="Feature ports matched and SSDP basic device information is valid",
        ssdp=ssdp,
    )


def _confidence(open_ports: list[int], ssdp: dict[str, str]) -> float:
    ports = set(open_ports)
    if ports == set(BAMBU_FEATURE_PORTS):
        score = 0.9
    elif ports:
        score = 0.6
    else:
        score = 0.0
    if ssdp:
        score += 0.1
    return min(score, 1.0)


def _reason(open_ports: list[int], has_ssdp: bool) -> str:
    ports = set(open_ports)
    if ports == set(BAMBU_FEATURE_PORTS):
        base = "Both Bambu feature ports are open"
    elif 8883 in ports:
        base = "MQTT TLS feature port is open"
    elif 990 in ports:
        base = "FTPS feature port is open"
    else:
        base = "No Bambu feature port is open"
    if has_ssdp:
        return f"{base}; SSDP device information found"
    return base


def _serial_from_ssdp(ssdp: dict[str, str]) -> str | None:
    usn = ssdp.get("usn")
    if not usn:
        return None
    serial = usn.split("::", 1)[0]
    if serial.lower().startswith("uuid:"):
        serial = serial[5:]
    return serial or None


def _reverse_dns(host: str) -> str | None:
    try:
        name = socket.gethostbyaddr(host)[0]
    except OSError:
        return None
    return name


def _bounded_timeout(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _validation_budget(candidate_count: int, worker_count: int, validation_timeout: float) -> float:
    batches = max(1, math.ceil(candidate_count / max(1, worker_count)))
    return batches * (validation_timeout + 0.1)


def _report(progress_callback: ProgressCallback | None, value: float, message: str) -> None:
    if progress_callback is None:
        return
    progress_callback(max(0.0, min(value, 1.0)), message)
