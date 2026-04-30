from __future__ import annotations

import base64
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import contextlib
import hashlib
import logging
import queue
import socket
import ssl
import struct
import subprocess
import threading
import time
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

from filament_manager.db.models import DeviceStatusSnapshot, Printer

logger = logging.getLogger(__name__)

CAMERA_MJPEG_BOUNDARY = "filamentmanager-camera"
CAMERA_MJPEG_MEDIA_TYPE = f"multipart/x-mixed-replace; boundary={CAMERA_MJPEG_BOUNDARY}"

_BAMBU_VIDEO_USERNAME = "bblp"
_LOCAL_RTSP_PROXY_PASSWORD = "filamentmanager"
_BAMBU_JPEG_PORT = 6000
_BAMBU_RTSPS_PORT = 322
_JPEG_START = b"\xff\xd8"
_JPEG_END = b"\xff\xd9"
_MAX_JPEG_BUFFER_BYTES = 10 * 1024 * 1024
_RTSP_MAX_RECONNECTS = 30
_RTSP_RECONNECT_DELAY_SECONDS = 0.2


class CameraStreamError(RuntimeError):
    pass


@dataclass(frozen=True)
class CameraPrinterConfig:
    id: int
    name: str
    host: str
    access_code: str
    certificate_verify: bool


@dataclass(frozen=True)
class CameraSource:
    kind: str
    port: int
    url: str | None = None


def camera_config_from_printer(printer: Printer) -> CameraPrinterConfig:
    return CameraPrinterConfig(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        access_code=printer.access_code,
        certificate_verify=printer.certificate_verify,
    )


def camera_capabilities(
    printer: Printer,
    snapshot: DeviceStatusSnapshot | None = None,
    *,
    timeout: float = 0.45,
) -> dict[str, Any]:
    config = camera_config_from_printer(printer)
    ports = {
        "local_jpeg": _is_tcp_port_open(config.host, _BAMBU_JPEG_PORT, timeout=timeout),
        "rtsps": _is_tcp_port_open(config.host, _BAMBU_RTSPS_PORT, timeout=timeout),
    }
    source = _select_camera_source_from_port_status(config, snapshot, ports)
    camera = _snapshot_camera(snapshot)
    family = _camera_stream_family(config, snapshot)
    return {
        "available": source is not None,
        "stream_path": f"/printers/{config.id}/camera/mjpeg" if source is not None else None,
        "source": source.kind if source is not None else None,
        "ports": ports,
        "liveview_enabled": _boolish(camera.get("liveview_preview")),
        "rtsp_advertised": _enabled_rtsp_url(camera.get("rtsp_url")) is not None,
        "detail": None if source is not None else _camera_unavailable_detail(family, ports),
    }


def select_camera_source(
    printer: Printer,
    snapshot: DeviceStatusSnapshot | None = None,
    *,
    timeout: float = 0.7,
) -> CameraSource:
    sources = select_camera_sources(printer, snapshot, timeout=timeout)
    if not sources:
        raise CameraStreamError("No local camera stream endpoint is reachable")
    return sources[0]


def select_camera_sources(
    printer: Printer,
    snapshot: DeviceStatusSnapshot | None = None,
    *,
    timeout: float = 0.7,
) -> list[CameraSource]:
    config = camera_config_from_printer(printer)
    ports = {
        "local_jpeg": _is_tcp_port_open(config.host, _BAMBU_JPEG_PORT, timeout=timeout),
        "rtsps": _is_tcp_port_open(config.host, _BAMBU_RTSPS_PORT, timeout=timeout),
    }
    return _select_camera_sources_from_port_status(config, snapshot, ports)


def iter_camera_mjpeg(config: CameraPrinterConfig, source: CameraSource) -> Iterator[bytes]:
    if source.kind == "local_jpeg":
        yield from _iter_bambu_local_jpeg_mjpeg(config)
        return
    if source.kind == "rtsps":
        yield from _iter_rtsps_mjpeg(config, source)
        return
    raise CameraStreamError(f"Unsupported camera source: {source.kind}")


def iter_camera_mjpeg_auto(config: CameraPrinterConfig, sources: list[CameraSource]) -> Iterator[bytes]:
    last_error: Exception | None = None
    for source in sources:
        yielded = False
        try:
            for chunk in iter_camera_mjpeg(config, source):
                yielded = True
                yield chunk
            if yielded:
                return
        except Exception as exc:  # noqa: BLE001 - try the next camera source before giving up.
            last_error = exc
            logger.warning("Camera source %s failed for printer id %s: %s", source.kind, config.id, exc)
            continue
    if last_error is not None:
        raise CameraStreamError(str(last_error)) from last_error
    raise CameraStreamError("No local camera stream endpoint is reachable")


def _select_camera_source_from_port_status(
    config: CameraPrinterConfig,
    snapshot: DeviceStatusSnapshot | None,
    ports: dict[str, bool],
) -> CameraSource | None:
    sources = _select_camera_sources_from_port_status(config, snapshot, ports)
    return sources[0] if sources else None


def _select_camera_sources_from_port_status(
    config: CameraPrinterConfig,
    snapshot: DeviceStatusSnapshot | None,
    ports: dict[str, bool],
) -> list[CameraSource]:
    sources: list[CameraSource] = []
    for source in _camera_source_candidates(config, snapshot):
        if source.kind == "local_jpeg" and ports.get("local_jpeg"):
            sources.append(source)
        if source.kind == "rtsps" and ports.get("rtsps"):
            sources.append(source)
    return sources


def _camera_source_candidates(
    config: CameraPrinterConfig,
    snapshot: DeviceStatusSnapshot | None,
) -> list[CameraSource]:
    rtsp_url = _camera_rtsp_url(config, snapshot)
    rtsps = CameraSource(kind="rtsps", port=_BAMBU_RTSPS_PORT, url=rtsp_url)
    local_jpeg = CameraSource(kind="local_jpeg", port=_BAMBU_JPEG_PORT)
    family = _camera_stream_family(config, snapshot)
    if family == "rtsps":
        return [rtsps]
    if family == "local_jpeg":
        return [local_jpeg]
    return [rtsps, local_jpeg]


def _camera_stream_family(config: CameraPrinterConfig, snapshot: DeviceStatusSnapshot | None) -> str | None:
    camera = _snapshot_camera(snapshot)
    if _enabled_rtsp_url(camera.get("rtsp_url")) is not None:
        return "rtsps"
    haystack = " ".join(
        str(value or "")
        for value in (
            config.name,
            _snapshot_hardware(snapshot).get("model"),
            _snapshot_hardware(snapshot).get("model_name"),
            _snapshot_hardware(snapshot).get("machine_model"),
            _snapshot_hardware(snapshot).get("product_name"),
            _snapshot_hardware(snapshot).get("product"),
            _snapshot_hardware(snapshot).get("model_code"),
        )
    ).lower()
    if any(token in haystack for token in ("x1", "h2", "p2")):
        return "rtsps"
    if any(token in haystack for token in ("bl-p001", "c13", "n6", "o1d", "o1c", "o1c2", "o1s", "o1e", "o2d", "n7")):
        return "rtsps"
    if any(token in haystack for token in ("p1", "a1")):
        return "local_jpeg"
    return None


def _camera_unavailable_detail(family: str | None, ports: dict[str, bool]) -> str:
    if family == "rtsps" and not ports.get("rtsps"):
        return "LAN live view is not reachable on port 322"
    if family == "local_jpeg" and not ports.get("local_jpeg"):
        return "Local camera stream is not reachable on port 6000"
    return "No local camera stream endpoint is reachable"


def _camera_rtsp_url(config: CameraPrinterConfig, snapshot: DeviceStatusSnapshot | None) -> str:
    advertised = _enabled_rtsp_url(_snapshot_camera(snapshot).get("rtsp_url"))
    if advertised is not None:
        return _strip_url_userinfo(advertised)
    host = _url_host(config.host)
    return f"rtsps://{host}:{_BAMBU_RTSPS_PORT}/streaming/live/1"


def _iter_bambu_local_jpeg_mjpeg(config: CameraPrinterConfig) -> Iterator[bytes]:
    context = _camera_tls_context(config)
    with socket.create_connection((config.host, _BAMBU_JPEG_PORT), timeout=8.0) as sock:
        with context.wrap_socket(sock, server_hostname=config.host) as tls_sock:
            tls_sock.settimeout(12.0)
            tls_sock.sendall(_bambu_local_video_auth_packet(config.access_code))
            chunks = _socket_chunks(tls_sock)
            yielded = False
            for chunk in _mjpeg_parts_from_jpeg_chunks(chunks):
                yielded = True
                yield chunk
            if not yielded:
                raise CameraStreamError("Local camera endpoint did not return JPEG frames")


def _iter_rtsps_mjpeg(config: CameraPrinterConfig, source: CameraSource) -> Iterator[bytes]:
    ffmpeg_exe = _ffmpeg_executable()
    reconnect_count = 0
    yielded_any_frame = False
    last_error: str | None = None
    while reconnect_count <= _RTSP_MAX_RECONNECTS:
        if reconnect_count:
            time.sleep(_RTSP_RECONNECT_DELAY_SECONDS)
        try:
            proxy = _RtspTlsProxy(config, source)
            proxy.start()
        except OSError as exc:
            raise CameraStreamError(f"Failed to start local RTSP TLS proxy: {exc}") from exc
        process: subprocess.Popen[bytes] | None = None
        stderr_reader: _ProcessStderrReader | None = None
        try:
            url = _local_rtsp_proxy_url(config, proxy.port, source.url)
            command = _ffmpeg_rtsp_mjpeg_command(ffmpeg_exe, url)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stderr_reader = _ProcessStderrReader(process)
            stderr_reader.start()
            if process.stdout is None:
                raise CameraStreamError("Failed to open ffmpeg output stream")

            frame_count = 0
            for part in _mjpeg_parts_from_jpeg_chunks(_file_chunks(process.stdout)):
                frame_count += 1
                yielded_any_frame = True
                yield part

            last_error = stderr_reader.summary() if stderr_reader else None
            if frame_count == 0 and not yielded_any_frame:
                raise CameraStreamError(last_error or "RTSP camera stream ended before any frame was received")
            reconnect_count += 1
        except GeneratorExit:
            raise
        except CameraStreamError:
            raise
        except Exception as exc:  # noqa: BLE001 - streaming should reconnect on transient ffmpeg/proxy failures.
            last_error = str(exc)
            logger.warning(
                "RTSP camera stream failed for printer id %s, retrying (%s/%s): %s",
                config.id,
                reconnect_count + 1,
                _RTSP_MAX_RECONNECTS,
                exc,
            )
            reconnect_count += 1
        finally:
            if process is not None:
                _terminate_process(process)
            if stderr_reader is not None:
                stderr_reader.close()
            proxy.close()
    if not yielded_any_frame:
        raise CameraStreamError(last_error or "RTSP camera stream did not produce frames")


def _ffmpeg_rtsp_mjpeg_command(ffmpeg_exe: str, url: str, fps: int = 10) -> list[str]:
    return [
        ffmpeg_exe,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-rtsp_flags",
        "prefer_tcp",
        "-timeout",
        "30000000",
        "-buffer_size",
        "1024000",
        "-max_delay",
        "500000",
        "-probesize",
        "32",
        "-analyzeduration",
        "0",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-i",
        url,
        "-f",
        "mjpeg",
        "-q:v",
        "5",
        "-r",
        str(fps),
        "-an",
        "pipe:1",
    ]


def _local_rtsp_proxy_url(config: CameraPrinterConfig, proxy_port: int, source_url: str | None) -> str:
    path = "/streaming/live/1"
    if source_url:
        parsed = urlparse(source_url)
        if parsed.path:
            path = parsed.path
            if parsed.query:
                path = f"{path}?{parsed.query}"
    local_password = quote(_LOCAL_RTSP_PROXY_PASSWORD, safe="")
    return f"rtsp://{_BAMBU_VIDEO_USERNAME}:{local_password}@127.0.0.1:{proxy_port}{path}"


def _target_rtsp_proxy_base_url(config: CameraPrinterConfig, target_port: int) -> str:
    return f"rtsps://{_url_host(config.host)}:{target_port}"


def _rtsp_basic_auth_header(config: CameraPrinterConfig) -> bytes:
    token = base64.b64encode(f"{_BAMBU_VIDEO_USERNAME}:{config.access_code or ''}".encode("utf-8")).decode("ascii")
    return f"Authorization: Basic {token}".encode("ascii")


def _camera_tls_context(config: CameraPrinterConfig) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not config.certificate_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _strip_url_userinfo(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.hostname:
        return value
    host = _url_host(parsed.hostname)
    netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    return urlunparse((parsed.scheme, netloc, parsed.path, "", parsed.query, parsed.fragment))


class _RtspTlsProxy:
    def __init__(self, config: CameraPrinterConfig, source: CameraSource) -> None:
        self.config = config
        self.target_host = config.host
        self.target_port = source.port
        self.target_base_url = _target_rtsp_proxy_base_url(config, source.port).encode("ascii")
        self.port = 0
        self._server: socket.socket | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connections: list[socket.socket] = []

    def start(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(4)
        server.settimeout(0.5)
        self.port = int(server.getsockname()[1])
        self._server = server
        self._thread = threading.Thread(target=self._serve, name=f"camera-rtsp-tls-proxy-{self.port}", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._server is not None:
            with contextlib.suppress(OSError):
                self._server.close()
        for connection in list(self._connections):
            with contextlib.suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                connection.close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                client, _address = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._connections.append(client)
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        tls_sock: ssl.SSLSocket | None = None
        try:
            context = _camera_tls_context(self.config)
            raw_target = socket.create_connection((self.target_host, self.target_port), timeout=10.0)
            tls_sock = context.wrap_socket(raw_target, server_hostname=self.target_host)
            proxy_url = f"rtsp://127.0.0.1:{self.port}".encode("ascii")
            to_target = threading.Thread(
                target=self._forward,
                args=(client, tls_sock, proxy_url, self.target_base_url),
                daemon=True,
            )
            to_client = threading.Thread(target=self._forward, args=(tls_sock, client, None, None), daemon=True)
            to_target.start()
            to_client.start()
            while to_target.is_alive() and to_client.is_alive() and not self._stop.is_set():
                time.sleep(0.05)
            for connection in (client, tls_sock):
                with contextlib.suppress(OSError):
                    connection.shutdown(socket.SHUT_RDWR)
            to_target.join(timeout=1.0)
            to_client.join(timeout=1.0)
        except OSError as exc:
            logger.debug("RTSP TLS proxy connection failed for %s:%s: %s", self.target_host, self.target_port, exc)
        finally:
            if client in self._connections:
                self._connections.remove(client)
            for connection in (client, tls_sock):
                if connection is None:
                    continue
                with contextlib.suppress(OSError):
                    connection.shutdown(socket.SHUT_RDWR)
                with contextlib.suppress(OSError):
                    connection.close()

    def _forward(
        self,
        source: socket.socket,
        destination: socket.socket,
        proxy_url: bytes | None,
        real_url: bytes | None,
    ) -> None:
        try:
            while not self._stop.is_set():
                data = source.recv(65536)
                if not data:
                    return
                if proxy_url is not None and real_url is not None:
                    data = _rewrite_rtsp_client_request(data, proxy_url, real_url, self.config)
                destination.sendall(data)
        except OSError:
            return


def _rewrite_rtsp_client_request(
    data: bytes,
    proxy_url: bytes,
    real_url: bytes,
    config: CameraPrinterConfig,
) -> bytes:
    marker = b" RTSP/1.0"
    if marker not in data:
        return data
    data = data.replace(proxy_url, real_url)
    header, separator, body = data.partition(b"\r\n\r\n")
    if not separator:
        return data
    lines = header.split(b"\r\n")
    method, request_uri = _rtsp_request_line_parts(lines[0])
    for index, line in enumerate(lines[1:], start=1):
        if line.lower().startswith(b"authorization:"):
            lines[index] = _rewrite_rtsp_authorization(line, method, request_uri, config)
            break
    return b"\r\n".join(lines) + separator + body


def _rewrite_rtsp_authorization(
    line: bytes,
    method: str,
    request_uri: str,
    config: CameraPrinterConfig,
) -> bytes:
    _prefix, _separator, raw_value = line.partition(b":")
    value = raw_value.strip().decode("utf-8", errors="replace")
    scheme, _space, parameter_text = value.partition(" ")
    if scheme.lower() == "basic":
        return _rtsp_basic_auth_header(config)
    if scheme.lower() != "digest":
        return line
    fields, order = _parse_digest_authorization(parameter_text)
    response = _digest_auth_response(
        method=method,
        uri=request_uri,
        fields=fields,
        username=_BAMBU_VIDEO_USERNAME,
        password=config.access_code or "",
    )
    if response is None:
        return line
    fields["username"] = _BAMBU_VIDEO_USERNAME
    fields["uri"] = request_uri
    fields["response"] = response
    return b"Authorization: Digest " + _format_digest_authorization(fields, order).encode("ascii", errors="ignore")


def _rtsp_request_line_parts(line: bytes) -> tuple[str, str]:
    parts = line.decode("utf-8", errors="replace").split()
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def _digest_auth_response(
    *,
    method: str,
    uri: str,
    fields: dict[str, str],
    username: str,
    password: str,
) -> str | None:
    realm = fields.get("realm")
    nonce = fields.get("nonce")
    if not method or not uri or not realm or not nonce:
        return None
    algorithm = fields.get("algorithm", "MD5")
    algorithm_lower = algorithm.lower()
    if algorithm_lower not in {"md5", "md5-sess"}:
        return None
    ha1 = _md5_hex(f"{username}:{realm}:{password}")
    if algorithm_lower == "md5-sess":
        cnonce = fields.get("cnonce")
        if not cnonce:
            return None
        ha1 = _md5_hex(f"{ha1}:{nonce}:{cnonce}")
    ha2 = _md5_hex(f"{method}:{uri}")
    qop = fields.get("qop")
    if qop:
        qop_value = qop.lower()
        if qop_value != "auth":
            return None
        nc = fields.get("nc")
        cnonce = fields.get("cnonce")
        if not nc or not cnonce:
            return None
        return _md5_hex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop_value}:{ha2}")
    return _md5_hex(f"{ha1}:{nonce}:{ha2}")


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()  # noqa: S324 - required by RTSP Digest auth.


def _parse_digest_authorization(value: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    order: list[str] = []
    for part in _split_digest_fields(value):
        if "=" not in part:
            continue
        key, raw_field_value = part.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        fields[normalized_key] = _unquote_digest_value(raw_field_value.strip())
        order.append(normalized_key)
    return fields, order


def _split_digest_fields(value: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            current.append(char)
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            current.append(char)
            continue
        if char == "," and not in_quote:
            fields.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        fields.append("".join(current).strip())
    return fields


def _unquote_digest_value(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _format_digest_authorization(fields: dict[str, str], order: list[str]) -> str:
    token_fields = {"algorithm", "qop", "nc"}
    ordered_keys = list(dict.fromkeys([*order, "username", "realm", "nonce", "uri", "response"]))
    parts: list[str] = []
    for key in ordered_keys:
        if key not in fields:
            continue
        value = fields[key]
        if key.lower() in token_fields:
            parts.append(f"{key}={value}")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key}="{escaped}"')
    return ", ".join(parts)


class _ProcessStderrReader:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._lines: queue.Queue[str] = queue.Queue(maxsize=50)
        self._thread = threading.Thread(target=self._read, name="camera-ffmpeg-stderr", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def summary(self) -> str:
        lines: list[str] = []
        while True:
            try:
                lines.append(self._lines.get_nowait())
            except queue.Empty:
                break
        return _summarize_ffmpeg_stderr("\n".join(lines))

    def _read(self) -> None:
        if self._process.stderr is None:
            return
        for raw in self._process.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            if self._lines.full():
                with contextlib.suppress(queue.Empty):
                    self._lines.get_nowait()
            self._lines.put(line)


def _summarize_ffmpeg_stderr(text: str | None) -> str:
    if not text:
        return ""
    banner_prefixes = (
        "ffmpeg version ",
        "  built with ",
        "  configuration:",
        "  libavutil ",
        "  libavcodec ",
        "  libavformat ",
        "  libavdevice ",
        "  libavfilter ",
        "  libswscale ",
        "  libswresample ",
        "  libpostproc ",
    )
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith(banner_prefixes)]
    return "\n".join(lines[-10:])


def _ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - dependency is optional at import time.
        raise CameraStreamError("Bundled ffmpeg dependency is not installed") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def _bambu_local_video_auth_packet(access_code: str) -> bytes:
    return (
        struct.pack("<IIII", 0x40, 0x3000, 0, 0)
        + _fixed_ascii(_BAMBU_VIDEO_USERNAME, 32)
        + _fixed_ascii(access_code, 32)
    )


def _fixed_ascii(value: str, size: int) -> bytes:
    encoded = str(value or "").encode("ascii", errors="ignore")[:size]
    return encoded + (b"\x00" * (size - len(encoded)))


def _mjpeg_parts_from_jpeg_chunks(chunks: Iterable[bytes]) -> Iterator[bytes]:
    for image in _jpeg_images_from_chunks(chunks):
        yield _mjpeg_part(image)


def _jpeg_images_from_chunks(chunks: Iterable[bytes]) -> Iterator[bytes]:
    buffer = bytearray()
    for chunk in chunks:
        if not chunk:
            continue
        buffer.extend(chunk)
        while True:
            start = buffer.find(_JPEG_START)
            if start < 0:
                if len(buffer) > 1:
                    del buffer[:-1]
                break
            if start:
                del buffer[:start]
            end = buffer.find(_JPEG_END, len(_JPEG_START))
            if end < 0:
                if len(buffer) > _MAX_JPEG_BUFFER_BYTES:
                    logger.warning("Dropping oversized camera frame buffer without JPEG terminator")
                    del buffer[:-1]
                break
            end += len(_JPEG_END)
            image = bytes(buffer[:end])
            del buffer[:end]
            if image.startswith(_JPEG_START) and image.endswith(_JPEG_END):
                yield image


def _mjpeg_part(image: bytes) -> bytes:
    return (
        f"--{CAMERA_MJPEG_BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(image)}\r\n\r\n"
    ).encode("ascii") + image + b"\r\n"


def _socket_chunks(sock: ssl.SSLSocket, chunk_size: int = 4096) -> Iterator[bytes]:
    while True:
        chunk = sock.recv(chunk_size)
        if not chunk:
            return
        yield chunk


def _file_chunks(stream: Any, chunk_size: int = 4096) -> Iterator[bytes]:
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        yield chunk


def _is_tcp_port_open(host: str, port: int, *, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _enabled_rtsp_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.lower() in {"disable", "disabled", "none", "unknown", "null", "false"}:
        return None
    if not stripped.lower().startswith(("rtsp://", "rtsps://")):
        return None
    return stripped


def _snapshot_camera(snapshot: DeviceStatusSnapshot | None) -> dict[str, Any]:
    return snapshot.camera if snapshot is not None and isinstance(snapshot.camera, dict) else {}


def _snapshot_hardware(snapshot: DeviceStatusSnapshot | None) -> dict[str, Any]:
    return snapshot.hardware if snapshot is not None and isinstance(snapshot.hardware, dict) else {}


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return None


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(Exception):
        if process.stdout is not None:
            process.stdout.close()
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)
