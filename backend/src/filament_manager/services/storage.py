from __future__ import annotations

import ftplib
import posixpath
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.db.models import Printer, PrinterEvent, PrinterStorageFile, utc_now
from filament_manager.services.notifications import dispatch_event_notifications

DEFAULT_STORAGE_DIRS = ("/timelapse", "/timelapse/video")
FTPS_USERNAME = "bblp"
FTPS_PORT = 990
FTPS_TIMEOUT = 8


@dataclass(frozen=True)
class StorageScanResult:
    success: bool
    error: str | None
    files: list[PrinterStorageFile]
    new_count: int = 0
    existing_count: int = 0
    failed_count: int = 0

    @property
    def scanned_count(self) -> int:
        return len(self.files)


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    def connect(
        self,
        host: str = "",
        port: int = 0,
        timeout: float | None = -999,
        source_address: tuple[str, int] | None = None,
    ) -> str:
        if host:
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if source_address is not None:
            self.source_address = source_address
        self.sock = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            source_address=self.source_address,
        )
        self.af = self.sock.family
        context = self.context or ssl.create_default_context()
        self.context = context
        self.sock = context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd: str, rest: str | None = None) -> tuple[socket.socket, int | None]:
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            wrap_kwargs: dict[str, Any] = {"server_hostname": self.host}
            control_session = getattr(self.sock, "session", None)
            if control_session is not None:
                wrap_kwargs["session"] = control_session
            conn = self.context.wrap_socket(conn, **wrap_kwargs)
        return conn, size


def scan_printer_storage(
    db: Session,
    *,
    printer: Printer,
    directories: tuple[str, ...] = DEFAULT_STORAGE_DIRS,
) -> StorageScanResult:
    try:
        records = _list_storage_files(printer, directories)
    except Exception as exc:
        message = _redact_access_code(f"FTPS storage scan failed: {exc}", printer.access_code)
        _record_storage_event(db, printer.id, message, severity="warning")
        db.flush()
        return StorageScanResult(success=False, error=message, files=[], failed_count=1)

    now = utc_now()
    files: list[PrinterStorageFile] = []
    existing_paths = set(
        db.scalars(select(PrinterStorageFile.path).where(PrinterStorageFile.printer_id == printer.id)).all()
    )
    new_count = 0
    existing_count = 0
    for record in records:
        if not is_timelapse_storage_record(record):
            continue
        model = db.scalars(
            select(PrinterStorageFile).where(
                PrinterStorageFile.printer_id == printer.id,
                PrinterStorageFile.path == record["path"],
            )
        ).first()
        if model is None:
            model = PrinterStorageFile(
                printer_id=printer.id,
                path=record["path"],
                name=record["name"],
                source="ftps",
            )
            db.add(model)
            new_count += 1
        elif model.path in existing_paths:
            existing_count += 1
        model.name = record["name"]
        model.size = record.get("size")
        model.modified_at = record.get("modified_at")
        model.type = record.get("type")
        model.source = "ftps"
        model.raw = record.get("raw") or {}
        model.last_scanned_at = now
        files.append(model)
    _record_storage_event(
        db,
        printer.id,
        f"FTPS storage scan completed: {len(files)} files",
        severity="info",
        data={
            "file_count": len(files),
            "directories": list(directories),
            "new_count": new_count,
            "existing_count": existing_count,
            "failed_count": 0,
        },
    )
    db.flush()
    return StorageScanResult(success=True, error=None, files=files, new_count=new_count, existing_count=existing_count)


def _list_storage_files(printer: Printer, directories: tuple[str, ...]) -> list[dict[str, Any]]:
    with _connect_storage_ftp(printer) as ftp:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for directory in directories:
            for record in _list_directory(ftp, directory):
                path = record["path"]
                if path in seen:
                    continue
                seen.add(path)
                records.append(record)
        return records


def stream_printer_storage_file(
    printer: Printer,
    path: str,
    *,
    start: int | None = None,
    end: int | None = None,
    chunk_size: int = 1024 * 256,
) -> Iterator[bytes]:
    if "\r" in path or "\n" in path:
        raise ValueError("Invalid storage path")
    offset = max(0, start or 0)
    remaining = None if end is None else max(0, end - offset + 1)
    with _connect_storage_ftp(printer) as ftp:
        ftp.voidcmd("TYPE I")
        conn = ftp.transfercmd(f"RETR {path}", rest=offset if offset else None)
        try:
            while True:
                if remaining is not None and remaining <= 0:
                    break
                read_size = chunk_size if remaining is None else min(chunk_size, remaining)
                chunk = conn.recv(read_size)
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk
        finally:
            conn.close()
        ftp.voidresp()


def _connect_storage_ftp(printer: Printer) -> ImplicitFTP_TLS:
    context = ssl.create_default_context()
    if not printer.certificate_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    ftp = ImplicitFTP_TLS(context=context, timeout=FTPS_TIMEOUT)
    ftp.connect(printer.host, FTPS_PORT)
    ftp.login(FTPS_USERNAME, printer.access_code)
    ftp.prot_p()
    return ftp


def _list_directory(ftp: ftplib.FTP, directory: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    normalized_dir = _normalize_dir(directory)
    try:
        entries = list(ftp.mlsd(normalized_dir))
    except Exception:
        entries = _nlst_entries(ftp, normalized_dir)
    for name, facts in entries:
        if name in {"", ".", ".."}:
            continue
        path = posixpath.join(normalized_dir, name)
        entry_type = str(facts.get("type") or "").lower() if isinstance(facts, dict) else ""
        if entry_type in {"dir", "cdir", "pdir"}:
            continue
        size = _as_int(facts.get("size")) if isinstance(facts, dict) else None
        modified_at = _parse_modified_at(facts.get("modify")) if isinstance(facts, dict) else None
        records.append(
            {
                "path": path,
                "name": name,
                "size": size,
                "modified_at": modified_at,
                "type": _file_type(name, path),
                "raw": facts if isinstance(facts, dict) else {},
            }
        )
    return records


def _nlst_entries(ftp: ftplib.FTP, directory: str) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    for item in ftp.nlst(directory):
        name = posixpath.basename(item.rstrip("/"))
        path = posixpath.join(directory, name)
        facts: dict[str, Any] = {}
        try:
            size = ftp.size(path)
        except Exception:
            size = None
        if size is None:
            continue
        facts["size"] = str(size)
        try:
            modified = ftp.sendcmd(f"MDTM {path}").split(maxsplit=1)[1]
            facts["modify"] = modified
        except Exception:
            pass
        entries.append((name, facts))
    return entries


def _record_storage_event(
    db: Session,
    printer_id: int,
    message: str,
    *,
    severity: str,
    data: dict[str, Any] | None = None,
) -> None:
    event = PrinterEvent(
        printer_id=printer_id,
        event_type="storage.scan" if severity == "info" else "storage.scan_failed",
        severity=severity,
        message=message,
        data=data,
    )
    db.add(event)
    db.flush()
    dispatch_event_notifications(db, event)


def _normalize_dir(value: str) -> str:
    text = "/" + value.strip("/")
    return "/" if text == "/" else text


def _file_type(name: str, path: str | None = None) -> str:
    lower = name.lower()
    lower_path = (path or name).lower()
    if "/record/" in lower_path or "/recording/" in lower_path:
        if lower.endswith((".mp4", ".avi", ".mov", ".mkv")):
            return "recording"
    if lower.endswith((".mp4", ".avi", ".mov")):
        return "timelapse"
    if lower.endswith(".3mf") and not lower.endswith(".gcode.3mf"):
        return "model"
    if lower.endswith((".gcode", ".gcode.3mf")):
        return "gcode"
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
        return "image"
    if lower.endswith((".log", ".txt")):
        return "log"
    return "other"


def is_timelapse_storage_record(record: dict[str, Any]) -> bool:
    return _is_timelapse_path(record.get("path")) or str(record.get("type") or "").lower() == "timelapse"


def is_timelapse_storage_file(file: PrinterStorageFile) -> bool:
    return _is_timelapse_path(file.path) or str(file.type or "").lower() == "timelapse"


def _is_timelapse_path(value: Any) -> bool:
    path = str(value or "").lower()
    return path == "/timelapse" or path.startswith("/timelapse/")


def _parse_modified_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value)
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M%S.%f"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _redact_access_code(message: str, access_code: str) -> str:
    if not access_code:
        return message
    return message.replace(access_code, "****")
