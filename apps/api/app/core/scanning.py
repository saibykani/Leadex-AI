"""Upload virus scanning via ClamAV (clamd INSTREAM protocol over TCP). Free and self-hosted.

* CLAMAV_HOST set      -> every upload is streamed to clamd; infected => 422 `upload_infected`;
                          scanner unreachable/error => 503 `scanner_unavailable` (fail closed).
* CLAMAV_HOST not set  -> production: 503 `scanner_not_configured` (uploads refused);
                          development: upload allowed and logged as unscanned.
Set CLAMAV_REQUIRED=false to explicitly accept unscanned uploads in production (not recommended).
"""
import logging
import os
import socket
import struct

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("leadex.scanning")
CHUNK = 64 * 1024


def _required() -> bool:
    v = (os.getenv("CLAMAV_REQUIRED") or "").strip().lower()
    if v in {"false", "0", "no"}:
        return False
    return get_settings().is_production or v in {"true", "1", "yes"}


def clamd_scan(data: bytes, host: str, port: int, timeout: float = 30.0) -> str:
    """Returns clamd's reply, e.g. 'stream: OK' or 'stream: Eicar-Signature FOUND'."""
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(b"zINSTREAM\0")
        for i in range(0, len(data), CHUNK):
            part = data[i:i + CHUNK]
            s.sendall(struct.pack("!L", len(part)) + part)
        s.sendall(struct.pack("!L", 0))
        reply = b""
        while not reply.endswith(b"\0"):
            got = s.recv(4096)
            if not got:
                break
            reply += got
    return reply.rstrip(b"\0").decode(errors="replace")


def scan_bytes(data: bytes, filename: str = "upload") -> str:
    """Raises AppError unless the file is clean (or scanning is explicitly not required). Returns a status."""
    host = os.getenv("CLAMAV_HOST")
    if not host:
        if _required():
            raise AppError(503, "scanner_not_configured", "Uploads are disabled until virus scanning is configured")
        log.warning("UNSCANNED upload accepted (CLAMAV_HOST not set, non-production): %s", filename)
        return "unscanned"
    try:
        reply = clamd_scan(data, host, int(os.getenv("CLAMAV_PORT") or 3310))
    except OSError as e:
        log.error("ClamAV unreachable: %s", type(e).__name__)
        raise AppError(503, "scanner_unavailable", "Virus scanner is unavailable; try again shortly") from e
    if reply.endswith("OK"):
        return "clean"
    if "FOUND" in reply:
        log.warning("Infected upload rejected: %s (%s)", filename, reply)
        raise AppError(422, "upload_infected", "The file failed the virus scan and was rejected")
    raise AppError(503, "scanner_error", f"Virus scanner error: {reply[:120]}")
