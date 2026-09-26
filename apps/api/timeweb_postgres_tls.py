from __future__ import annotations

import errno
import ipaddress
import os
import re
import socket
import ssl
import struct
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
TIMEWEB_POSTGRES_PORT = 5432
_MAX_CA_BYTES = 128 * 1024
_CA_RETRY_DELAYS_SECONDS = (1.0, 2.0, 5.0)
_TRANSPORT_RETRY_DELAYS_SECONDS = (1.0, 2.0, 5.0, 10.0)
_CONNECT_RETRY_DELAYS_SECONDS = (1.0, 2.0, 5.0)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_TRANSIENT_TRANSPORT_CODES = frozenset(
    {
        "TIMEWEB_PG_TLS_DNS_RESOLUTION_FAILED",
        "TIMEWEB_PG_TLS_TCP_FAILED",
        "TIMEWEB_PG_TLS_TCP_REFUSED",
        "TIMEWEB_PG_TLS_TCP_TIMEOUT",
        "TIMEWEB_PG_TLS_ROUTE_UNREACHABLE",
    }
)
_TRANSIENT_POSTGRES_SQLSTATES = frozenset(
    {
        "08000",
        "08001",
        "08003",
        "08006",
        "08007",
        "53300",
        "57P01",
        "57P02",
        "57P03",
    }
)
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
_FAILURE_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$", re.ASCII)
_TIMEWEB_TECHNICAL_DOMAIN_SUFFIXES = (
    ".tw1.ru",
    ".tw1.su",
    ".twc1.net",
    ".webtm.ru",
)
_ALLOWED_EXTERNAL_DSN_PARAMETERS = frozenset(
    {
        "dbname",
        "host",
        "password",
        "port",
        "sslmode",
        "sslrootcert",
        "user",
    }
)
_FORBIDDEN_LIBPQ_ENVIRONMENT = frozenset(
    {
        "PGAPPNAME",
        "PGCHANNELBINDING",
        "PGCLIENTENCODING",
        "PGCONNECT_TIMEOUT",
        "PGDATABASE",
        "PGGSSDELEGATION",
        "PGGSSENCMODE",
        "PGGSSLIB",
        "PGHOST",
        "PGHOSTADDR",
        "PGKRBSRVNAME",
        "PGLOADBALANCEHOSTS",
        "PGMAXPROTOCOLVERSION",
        "PGMINPROTOCOLVERSION",
        "PGOPTIONS",
        "PGPASSFILE",
        "PGPASSWORD",
        "PGPORT",
        "PGREQUIREAUTH",
        "PGREQUIREPEER",
        "PGREQUIRESSL",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSSLCERT",
        "PGSSLCERTMODE",
        "PGSSLCOMPRESSION",
        "PGSSLCRL",
        "PGSSLCRLDIR",
        "PGSSLKEY",
        "PGSSLMAXPROTOCOLVERSION",
        "PGSSLMINPROTOCOLVERSION",
        "PGSSLMODE",
        "PGSSLNEGOTIATION",
        "PGSSLROOTCERT",
        "PGSSLSNI",
        "PGSYSCONFDIR",
        "PGTARGETSESSIONATTRS",
        "PGUSER",
    }
)
_RETIRED_HOST_MARKERS = ("neon.tech", "cloudflare", "render.com", "cloud.ru")
_POSTGRES_SSL_REQUEST = struct.pack("!II", 8, 80877103)
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


def _emit(message: str) -> None:
    print(message, flush=True)


def _reject_ambient_libpq_environment(
    env: Any = os.environ,
) -> None:
    if any(name in env for name in _FORBIDDEN_LIBPQ_ENVIRONMENT):
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_AMBIENT_LIBPQ_ENV_FORBIDDEN"
        )


def _connection_params(dsn: str) -> dict[str, str]:
    try:
        raw = conninfo_to_dict(dsn)
    except psycopg.Error:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_INVALID") from None
    params = {str(key): str(value) for key, value in raw.items()}
    if set(params) - _ALLOWED_EXTERNAL_DSN_PARAMETERS:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_PARAMETER_FORBIDDEN")
    host = params.get("host", "").strip().lower().rstrip(".")
    if (
        not host
        or not params.get("dbname", "").strip()
        or not params.get("user", "").strip()
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_IDENTITY_REQUIRED")
    if not params.get("password", ""):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PASSWORD_REQUIRED")
    if _DOMAIN_RE.fullmatch(host) is None or any(
        marker in host for marker in _RETIRED_HOST_MARKERS
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED")
    if not host.endswith(_TIMEWEB_TECHNICAL_DOMAIN_SUFFIXES):
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_PROVIDER_TECHNICAL_DOMAIN_REQUIRED"
        )
    if params.get("port", "").strip() != str(TIMEWEB_POSTGRES_PORT):
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


def _tls_client_context(ca_path: Path) -> ssl.SSLContext:
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(ca_path))
    except (OSError, ssl.SSLError):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_INVALID") from None
    return context


def _resolve_public_addresses(
    hostname: str,
    *,
    resolver: Any = socket.getaddrinfo,
) -> tuple[str, ...]:
    try:
        records = resolver(
            hostname,
            TIMEWEB_POSTGRES_PORT,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_DNS_RESOLUTION_FAILED"
        ) from None

    addresses: set[str] = set()
    non_public_seen = False
    for record in records:
        if not isinstance(record, tuple) or len(record) < 5:
            continue
        socket_address = record[4]
        if not isinstance(socket_address, tuple) or not socket_address:
            continue
        raw_address = str(socket_address[0]).strip()
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            continue
        if address.is_global:
            addresses.add(address.compressed)
        else:
            non_public_seen = True

    if non_public_seen or not addresses:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC")
    return tuple(sorted(addresses))


def _probe_postgres_tls_endpoint(
    hostname: str,
    address: str,
    context: Any,
    *,
    connector: Any = socket.create_connection,
) -> None:
    raw_socket: Any | None = None
    try:
        raw_socket = connector(
            (address, TIMEWEB_POSTGRES_PORT),
            timeout=15.0,
        )
        raw_socket.sendall(_POSTGRES_SSL_REQUEST)
        response = raw_socket.recv(1)
        if response == b"N":
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_SSLREQUEST_REFUSED")
        if response != b"S":
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PROTOCOL_INVALID")
        with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
            raw_socket = None
            if not tls_socket.getpeercert():
                raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CERT_MISSING")
    except ssl.SSLCertVerificationError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CERT_VERIFY_FAILED") from None
    except ssl.SSLError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_HANDSHAKE_FAILED") from None
    except (TimeoutError, socket.timeout):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TCP_TIMEOUT") from None
    except ConnectionRefusedError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TCP_REFUSED") from None
    except OSError as exc:
        if exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            raise TimewebPostgresTlsError(
                "TIMEWEB_PG_TLS_ROUTE_UNREACHABLE"
            ) from None
        if exc.errno == errno.ECONNREFUSED:
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TCP_REFUSED") from None
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TCP_FAILED") from None
    finally:
        if raw_socket is not None:
            try:
                raw_socket.close()
            except OSError:
                pass


def _probe_transport_once(
    hostname: str,
    context: Any,
    *,
    resolver: Any,
    connector: Any,
) -> str:
    addresses = _resolve_public_addresses(hostname, resolver=resolver)
    last_transient: TimewebPostgresTlsError | None = None
    for address in addresses:
        try:
            _probe_postgres_tls_endpoint(
                hostname,
                address,
                context,
                connector=connector,
            )
            return address
        except TimewebPostgresTlsError as exc:
            if exc.code not in _TRANSIENT_TRANSPORT_CODES:
                raise
            last_transient = exc
    if last_transient is not None:
        raise last_transient
    raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_TCP_FAILED")


def probe_timeweb_postgres_transport(
    dsn: str,
    ca_path: Path,
    *,
    resolver: Any = socket.getaddrinfo,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
) -> str:
    _reject_ambient_libpq_environment()
    params = _connection_params(dsn)
    try:
        if ca_path.is_symlink() or not ca_path.is_file():
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
        _validate_ca(ca_path.read_bytes())
    except TimewebPostgresTlsError:
        raise
    except OSError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNAVAILABLE") from None

    context = context_factory(ca_path)
    hostname = params["host"].strip().lower().rstrip(".")
    attempts = len(delays) + 1
    for attempt in range(attempts):
        try:
            verified_address = _probe_transport_once(
                hostname,
                context,
                resolver=resolver,
                connector=connector,
            )
            _emit(
                "TIMEWEB_PG_TLS_TRANSPORT=READY "
                "dns=public tcp=5432 tls=verify-full"
            )
            return verified_address
        except TimewebPostgresTlsError as exc:
            if exc.code not in _TRANSIENT_TRANSPORT_CODES or attempt + 1 >= attempts:
                raise
            _emit(
                "TIMEWEB_PG_TLS_TRANSPORT_RETRY "
                f"code={exc.code} attempt={attempt + 2}/{attempts}"
            )
            sleeper(delays[attempt])
    raise AssertionError("bounded Timeweb PostgreSQL transport retry exhausted")


def resolve_timeweb_postgres_dsn(
    dsn: str,
    ca_path: Path,
    *,
    hostaddr: str | None = None,
) -> str:
    _connection_params(dsn)
    try:
        if ca_path.is_symlink() or not ca_path.is_file():
            raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNSAFE")
        _validate_ca(ca_path.read_bytes())
        absolute_ca = ca_path.resolve(strict=True)
        if hostaddr is None:
            return make_conninfo(dsn, sslrootcert=str(absolute_ca))
        address = ipaddress.ip_address(hostaddr)
        if not address.is_global:
            raise TimewebPostgresTlsError(
                "TIMEWEB_PG_TLS_VERIFIED_HOSTADDR_INVALID"
            )
        return make_conninfo(
            dsn,
            sslrootcert=str(absolute_ca),
            hostaddr=address.compressed,
        )
    except TimewebPostgresTlsError:
        raise
    except (OSError, psycopg.Error):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_PREPARE_FAILED") from None


def _postgres_connect_failure(
    exc: psycopg.Error,
    failure_prefix: str,
) -> tuple[bool, str]:
    if _FAILURE_PREFIX_RE.fullmatch(failure_prefix) is None:
        return False, "TIMEWEB_PG_CONNECT_FAILURE_PREFIX_INVALID"

    def code(suffix: str) -> str:
        return f"{failure_prefix}_{suffix}"

    if isinstance(exc, psycopg.errors.ConnectionTimeout):
        return True, code("TIMEOUT")

    sqlstate = (exc.sqlstate or "").strip().upper()
    message = str(exc).lower()

    if "role " in message and "does not exist" in message:
        return False, code("ROLE_NOT_FOUND")
    if "database " in message and "does not exist" in message:
        return False, code("DATABASE_NOT_FOUND")
    if "authentication failed" in message:
        return False, code("AUTHENTICATION_REJECTED")
    if "no pg_hba.conf entry" in message:
        return False, code("HOST_POLICY_REJECTED")
    if (
        "certificate verify failed" in message
        or "root certificate" in message
        or "ssl error" in message
    ):
        return False, code("TLS_FAILED")
    if (
        "could not translate host name" in message
        or "name or service not known" in message
    ):
        return True, code("DNS_RESOLUTION_FAILED")
    if "timed out" in message or "timeout expired" in message:
        return True, code("TIMEOUT")
    if "actively refused" in message or "connection refused" in message:
        return True, code("TCP_REFUSED")
    if "network is unreachable" in message or "no route to host" in message:
        return True, code("ROUTE_UNREACHABLE")
    if "server closed the connection unexpectedly" in message:
        return True, code("CONNECTION_DROPPED")

    pgconn = getattr(exc, "pgconn", None)
    if pgconn is not None:
        try:
            needs_password = bool(pgconn.needs_password)
            used_password = bool(pgconn.used_password)
        except (AttributeError, RuntimeError, psycopg.Error):
            needs_password = False
            used_password = False
        if needs_password and not used_password:
            return False, code("PASSWORD_REQUIRED")

    if sqlstate in {"28000", "28P01"}:
        return False, code("AUTHENTICATION_REJECTED")
    if sqlstate == "3D000":
        return False, code("DATABASE_NOT_FOUND")
    if sqlstate == "08004":
        return False, code("SERVER_REJECTED")
    if sqlstate == "08P01":
        return False, code("PROTOCOL_FAILED")
    if sqlstate in _TRANSIENT_POSTGRES_SQLSTATES:
        return True, code("TRANSIENT_CONNECTIVITY")
    if sqlstate:
        return False, code("SERVER_ERROR")
    return False, code("UNCLASSIFIED_CLIENT_FAILURE")


def connect_prepared_timeweb_postgres(
    dsn: str,
    *,
    failure_prefix: str,
    connect_timeout: int = 15,
    retry_delays: tuple[float, ...] = _CONNECT_RETRY_DELAYS_SECONDS,
    sleeper: Sleep = time.sleep,
    connector: Any = psycopg.connect,
    autocommit: bool | None = None,
) -> Any:
    _reject_ambient_libpq_environment()
    if _FAILURE_PREFIX_RE.fullmatch(failure_prefix) is None:
        raise TimewebPostgresTlsError("TIMEWEB_PG_CONNECT_FAILURE_PREFIX_INVALID")
    if connect_timeout <= 0:
        raise TimewebPostgresTlsError("TIMEWEB_PG_CONNECT_TIMEOUT_INVALID")

    attempts = len(retry_delays) + 1
    for attempt in range(attempts):
        try:
            kwargs: dict[str, object] = {"connect_timeout": connect_timeout}
            if autocommit is not None:
                kwargs["autocommit"] = autocommit
            return connector(dsn, **kwargs)
        except psycopg.Error as exc:
            retryable, failure_code = _postgres_connect_failure(
                exc,
                failure_prefix,
            )
            if not retryable or attempt + 1 >= attempts:
                raise TimewebPostgresTlsError(failure_code) from None
            _emit(
                "TIMEWEB_PG_CONNECT_RETRY "
                f"code={failure_code} attempt={attempt + 2}/{attempts}"
            )
            sleeper(retry_delays[attempt])
        except OSError:
            raise TimewebPostgresTlsError(
                f"{failure_prefix}_CLIENT_FAILURE"
            ) from None
    raise AssertionError("bounded Timeweb PostgreSQL connection retry exhausted")


def prepare_timeweb_postgres_tls(
    dsn: str,
    *,
    base_dir: Path | None = None,
    opener: Any | None = None,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _CA_RETRY_DELAYS_SECONDS,
    transport_delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
    resolver: Any = socket.getaddrinfo,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
) -> str:
    _connection_params(dsn)
    ca_path = install_timeweb_postgres_ca(
        base_dir=base_dir,
        opener=opener,
        sleeper=sleeper,
        delays=delays,
    )
    verified_address = probe_timeweb_postgres_transport(
        dsn,
        ca_path,
        resolver=resolver,
        connector=connector,
        context_factory=context_factory,
        sleeper=sleeper,
        delays=transport_delays,
    )
    return resolve_timeweb_postgres_dsn(
        dsn,
        ca_path,
        hostaddr=verified_address,
    )
