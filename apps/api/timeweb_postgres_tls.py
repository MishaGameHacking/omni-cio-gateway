from __future__ import annotations

import os
import re
import ssl
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo


TIMEWEB_POSTGRES_CA_URL = "https://st.timeweb.com/cloud-static/ca.crt"
TIMEWEB_POSTGRES_SSLROOTCERT = ".omni-cio/timeweb-postgres-root.crt"
_MAX_CA_BYTES = 128 * 1024
_CA_RETRY_DELAYS_SECONDS = (1.0, 2.0, 5.0)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
_RETIRED_HOST_MARKERS = ("neon.tech", "cloudflare", "render.com", "cloud.ru")
Sleep = Callable[[float], None]


class TimewebPostgresTlsError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


def _connection_params(dsn: str) -> dict[str, str]:
    try:
        raw = conninfo_to_dict(dsn)
    except psycopg.Error:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_INVALID") from None
    params = {str(key): str(value) for key, value in raw.items()}
    host = params.get("host", "").strip().lower().rstrip(".")
    if (
        not host
        or not params.get("dbname", "").strip()
        or not params.get("user", "").strip()
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_IDENTITY_REQUIRED")
    if _DOMAIN_RE.fullmatch(host) is None or any(
        marker in host for marker in _RETIRED_HOST_MARKERS
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED")
    if params.get("port", "").strip() != "5432":
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PORT_INVALID")
    if params.get("sslmode", "").strip().lower() != "verify-full":
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_VERIFY_FULL_REQUIRED")
    if params.get("sslrootcert", "").strip() != TIMEWEB_POSTGRES_SSLROOTCERT:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_ROOT_CERT_PATH_INVALID")
    return params


def _ca_target(base_dir: Path | None = None) -> Path:
    base = Path.cwd() if base_dir is None else Path(base_dir)
    directory = base / ".omni-cio"
    try:
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink():
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
        directory.chmod(0o700)
    except TimewebPostgresTlsError:
        raise
    except OSError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNAVAILABLE") from None
    target = directory / "timeweb-postgres-root.crt"
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
    return target


def _read_ca_once(opener: Any) -> bytes | None:
    request = Request(
        TIMEWEB_POSTGRES_CA_URL,
        headers={
            "Accept": "application/x-pem-file,text/plain",
            "User-Agent": "omni-cio-v10-timeweb-postgres-ca",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=20.0) as response:
            status = int(response.status)
            raw = response.read(_MAX_CA_BYTES + 1)
    except HTTPError as exc:
        if int(exc.code) in _TRANSIENT_HTTP_STATUSES:
            return None
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_FETCH_FAILED") from None
    except OSError:
        return None
    if status in _TRANSIENT_HTTP_STATUSES:
        return None
    if status != 200 or len(raw) > _MAX_CA_BYTES:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_FETCH_FAILED")
    return raw


def _fetch_ca(
    opener: Any,
    *,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> bytes:
    for attempt in range(len(delays) + 1):
        raw = _read_ca_once(opener)
        if raw is not None:
            return raw
        if attempt < len(delays):
            sleeper(delays[attempt])
    raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_FETCH_FAILED")


def _validate_ca(raw: bytes) -> None:
    if not raw or len(raw) > _MAX_CA_BYTES:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_INVALID")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_INVALID") from None
    begin = text.find("-----BEGIN CERTIFICATE-----")
    end_marker = "-----END CERTIFICATE-----"
    end = text.find(end_marker, begin + 1)
    if begin < 0 or end < 0:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_INVALID")
    certificate = text[begin : end + len(end_marker)]
    try:
        ssl.PEM_cert_to_DER_cert(certificate)
    except ValueError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_INVALID") from None


def _write_ca(target: Path, raw: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".timeweb-ca-",
            suffix=".crt",
            dir=target.parent,
            delete=False,
        ) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.chmod(0o600)
        os.replace(temporary, target)
        temporary = None
        target.chmod(0o600)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_WRITE_FAILED") from None


def install_timeweb_postgres_ca(
    *,
    base_dir: Path | None = None,
    opener: Any | None = None,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _CA_RETRY_DELAYS_SECONDS,
) -> Path:
    target = _ca_target(base_dir)
    client = opener or build_opener(_NoRedirectHandler())
    raw = _fetch_ca(client, sleeper=sleeper, delays=delays)
    _validate_ca(raw)
    _write_ca(target, raw)
    return target


def resolve_timeweb_postgres_dsn(dsn: str, ca_path: Path) -> str:
    _connection_params(dsn)
    try:
        if ca_path.is_symlink() or not ca_path.is_file():
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
        _validate_ca(ca_path.read_bytes())
        absolute_ca = ca_path.resolve(strict=True)
        return make_conninfo(dsn, sslrootcert=str(absolute_ca))
    except TimewebPostgresTlsError:
        raise
    except (OSError, psycopg.Error):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_PREPARE_FAILED") from None


def prepare_timeweb_postgres_tls(
    dsn: str,
    *,
    base_dir: Path | None = None,
    opener: Any | None = None,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _CA_RETRY_DELAYS_SECONDS,
) -> str:
    _connection_params(dsn)
    ca_path = install_timeweb_postgres_ca(
        base_dir=base_dir,
        opener=opener,
        sleeper=sleeper,
        delays=delays,
    )
    return resolve_timeweb_postgres_dsn(dsn, ca_path)
