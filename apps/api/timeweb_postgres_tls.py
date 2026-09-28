from __future__ import annotations

import errno
import hashlib
import ipaddress
import os
import re
import socket
import ssl
import struct
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
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
_TLS_DNS_RESOLUTION_FAILED = "TIMEWEB_PG_TLS_DNS_RESOLUTION_FAILED"
_TLS_TCP_FAILED = "TIMEWEB_PG_TLS_TCP_FAILED"
_TLS_TCP_REFUSED = "TIMEWEB_PG_TLS_TCP_REFUSED"
_TLS_TCP_TIMEOUT = "TIMEWEB_PG_TLS_TCP_TIMEOUT"
_TLS_ROUTE_UNREACHABLE = "TIMEWEB_PG_TLS_ROUTE_UNREACHABLE"
_TLS_VERIFIED_HOSTADDR_INVALID = "TIMEWEB_PG_TLS_VERIFIED_HOSTADDR_INVALID"
_TLS_CA_FETCH_FAILED = "TIMEWEB_PG_TLS_CA_FETCH_FAILED"
_TLS_CA_INVALID = "TIMEWEB_PG_TLS_CA_INVALID"
_TLS_CA_PATH_UNSAFE = "TIMEWEB_PG_TLS_CA_PATH_UNSAFE"
_SSLROOTCERT_KEY = "sslrootcert"
_GSSENCMODE_KEY = "gssencmode"
_SSLCERTMODE_KEY = "sslcertmode"
_SSL_MIN_PROTOCOL_VERSION_KEY = "ssl_min_protocol_version"
_PREPARED_GSSENCMODE = "disable"
_PREPARED_SSLCERTMODE = "disable"
_PREPARED_SSL_MIN_PROTOCOL_VERSION = "TLSv1.2"
_CONNECT_FAILURE_PREFIX_INVALID = "TIMEWEB_PG_CONNECT_FAILURE_PREFIX_INVALID"
_SUFFIX_AUTHENTICATION_REJECTED = "AUTHENTICATION_REJECTED"
_SUFFIX_DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
_SUFFIX_DNS_RESOLUTION_FAILED = "DNS_RESOLUTION_FAILED"
_SUFFIX_ROUTE_UNREACHABLE = "ROUTE_UNREACHABLE"
_SUFFIX_TCP_REFUSED = "TCP_REFUSED"
_SUFFIX_TIMEOUT = "TIMEOUT"
_SUFFIX_TLS_FAILED = "TLS_FAILED"
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_TRANSIENT_TRANSPORT_CODES = frozenset(
    {
        _TLS_DNS_RESOLUTION_FAILED,
        _TLS_TCP_FAILED,
        _TLS_TCP_REFUSED,
        _TLS_TCP_TIMEOUT,
        _TLS_ROUTE_UNREACHABLE,
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
_RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network((0x0A000000, 8)),
    ipaddress.IPv4Network((0xAC100000, 12)),
    ipaddress.IPv4Network((0xC0A80000, 16)),
)
_TIMEWEB_RESERVED_PRIVATE_HOST_OCTETS = frozenset({1, 2, 3})
_ALLOWED_EXTERNAL_DSN_PARAMETERS = frozenset(
    {
        "dbname",
        "host",
        "password",
        "port",
        "sslmode",
        _SSLROOTCERT_KEY,
        "user",
    }
)
_PREPARED_DSN_PARAMETERS = _ALLOWED_EXTERNAL_DSN_PARAMETERS | frozenset(
    {
        "hostaddr",
        _GSSENCMODE_KEY,
        _SSLCERTMODE_KEY,
        _SSL_MIN_PROTOCOL_VERSION_KEY,
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
_CONNECT_MESSAGE_RULES = (
    (("role ", "does not exist"), False, "ROLE_NOT_FOUND"),
    (("database ", "does not exist"), False, _SUFFIX_DATABASE_NOT_FOUND),
    (("authentication failed",), False, _SUFFIX_AUTHENTICATION_REJECTED),
    (("no pg_hba.conf entry",), False, "HOST_POLICY_REJECTED"),
    (("certificate verify failed",), False, _SUFFIX_TLS_FAILED),
    (("root certificate",), False, _SUFFIX_TLS_FAILED),
    (("ssl error",), False, _SUFFIX_TLS_FAILED),
    (("could not translate host name",), True, _SUFFIX_DNS_RESOLUTION_FAILED),
    (("name or service not known",), True, _SUFFIX_DNS_RESOLUTION_FAILED),
    (("timed out",), True, _SUFFIX_TIMEOUT),
    (("timeout expired",), True, _SUFFIX_TIMEOUT),
    (("actively refused",), True, _SUFFIX_TCP_REFUSED),
    (("connection refused",), True, _SUFFIX_TCP_REFUSED),
    (("network is unreachable",), True, _SUFFIX_ROUTE_UNREACHABLE),
    (("no route to host",), True, _SUFFIX_ROUTE_UNREACHABLE),
    (("server closed the connection unexpectedly",), True, "CONNECTION_DROPPED"),
)
_CONNECT_SQLSTATE_RULES = {
    "08004": (False, "SERVER_REJECTED"),
    "08P01": (False, "PROTOCOL_FAILED"),
    "28000": (False, _SUFFIX_AUTHENTICATION_REJECTED),
    "28P01": (False, _SUFFIX_AUTHENTICATION_REJECTED),
    "3D000": (False, _SUFFIX_DATABASE_NOT_FOUND),
}
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
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_AMBIENT_LIBPQ_ENV_FORBIDDEN")


def _parse_conninfo(dsn: str) -> dict[str, str]:
    try:
        raw = conninfo_to_dict(dsn)
    except psycopg.Error:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_INVALID") from None
    return {str(key): str(value) for key, value in raw.items()}


def _validate_provider_identity(params: dict[str, str]) -> str:
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
    return host


def _connection_params(dsn: str) -> dict[str, str]:
    params = _parse_conninfo(dsn)
    if set(params) - _ALLOWED_EXTERNAL_DSN_PARAMETERS:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_PARAMETER_FORBIDDEN")
    _validate_provider_identity(params)
    if params.get(_SSLROOTCERT_KEY, "").strip() != TIMEWEB_POSTGRES_SSLROOTCERT:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_ROOT_CERT_PATH_INVALID")
    return params


def timeweb_postgres_binding_sha256(dsn: str) -> str:
    """Return a non-secret target/user binding digest for a strict external DSN."""

    params = _connection_params(dsn)
    identity = (
        "omni-cio.v10.timeweb-postgres-binding.v1",
        f"host={_validate_provider_identity(params)}",
        f"port={params['port'].strip()}",
        f"dbname={params['dbname'].strip()}",
        f"user={params['user'].strip()}",
        f"sslmode={params['sslmode'].strip().lower()}",
        f"sslrootcert={params[_SSLROOTCERT_KEY].strip()}",
    )
    return hashlib.sha256("\n".join(identity).encode("utf-8")).hexdigest()


def _private_ipv4_network(cidr: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=True)
    except ValueError:
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_PRIVATE_NETWORK_INVALID"
        ) from None
    if not isinstance(network, ipaddress.IPv4Network) or not any(
        network.subnet_of(parent) for parent in _RFC1918_NETWORKS
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PRIVATE_NETWORK_INVALID")
    return network


def _private_ipv4_address(
    value: str,
    network: ipaddress.IPv4Network,
) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_PRIVATE_HOSTADDR_INVALID"
        ) from None
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or address not in network
        or address in {network.network_address, network.broadcast_address}
        or (int(address) & 0xFF) in _TIMEWEB_RESERVED_PRIVATE_HOST_OCTETS
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PRIVATE_HOSTADDR_INVALID")
    return address


def _public_ipv4_address(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        raise TimewebPostgresTlsError(_TLS_VERIFIED_HOSTADDR_INVALID) from None
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise TimewebPostgresTlsError(_TLS_VERIFIED_HOSTADDR_INVALID)
    return address


def _prepared_hostaddr(
    raw_hostaddr: str,
    *,
    private_network_cidr: str | None,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(raw_hostaddr)
    except ValueError:
        raise TimewebPostgresTlsError(_TLS_VERIFIED_HOSTADDR_INVALID) from None
    if private_network_cidr is None:
        if not address.is_global:
            raise TimewebPostgresTlsError(_TLS_VERIFIED_HOSTADDR_INVALID)
        return address
    network = _private_ipv4_network(private_network_cidr)
    return _private_ipv4_address(raw_hostaddr, network)


def _prepared_connection_params(
    dsn: str,
    *,
    private_network_cidr: str | None = None,
) -> dict[str, str]:
    params = _parse_conninfo(dsn)
    if set(params) - _PREPARED_DSN_PARAMETERS:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PREPARED_DSN_PARAMETER_FORBIDDEN")
    _validate_provider_identity(params)

    raw_hostaddr = params.get("hostaddr", "").strip()
    if not raw_hostaddr:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PREPARED_HOSTADDR_REQUIRED")
    _prepared_hostaddr(
        raw_hostaddr,
        private_network_cidr=private_network_cidr,
    )

    root_certificate = Path(params.get(_SSLROOTCERT_KEY, "").strip())
    if not root_certificate.is_absolute():
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PREPARED_ROOT_CERT_PATH_INVALID")
    if params.get(_GSSENCMODE_KEY, "").strip().lower() != _PREPARED_GSSENCMODE:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PREPARED_GSS_ENCRYPTION_INVALID")
    if params.get(_SSLCERTMODE_KEY, "").strip().lower() != _PREPARED_SSLCERTMODE:
        raise TimewebPostgresTlsError(
            "TIMEWEB_PG_TLS_PREPARED_CLIENT_CERT_MODE_INVALID"
        )
    if (
        params.get(_SSL_MIN_PROTOCOL_VERSION_KEY, "").strip()
        != _PREPARED_SSL_MIN_PROTOCOL_VERSION
    ):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_PREPARED_TLS_MIN_VERSION_INVALID")
    return params


def _ca_target(base_dir: Path | None = None) -> Path:
    base = Path.cwd() if base_dir is None else Path(base_dir)
    directory = base / ".omni-cio"
    try:
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise TimewebPostgresTlsError(_TLS_CA_PATH_UNSAFE)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink():
            raise TimewebPostgresTlsError(_TLS_CA_PATH_UNSAFE)
        directory.chmod(0o700)
    except TimewebPostgresTlsError:
        raise
    except OSError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNAVAILABLE") from None
    target = directory / "timeweb-postgres-root.crt"
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise TimewebPostgresTlsError(_TLS_CA_PATH_UNSAFE)
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
        raise TimewebPostgresTlsError(_TLS_CA_FETCH_FAILED) from None
    except OSError:
        return None
    if status in _TRANSIENT_HTTP_STATUSES:
        return None
    if status != 200 or len(raw) > _MAX_CA_BYTES:
        raise TimewebPostgresTlsError(_TLS_CA_FETCH_FAILED)
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
    raise TimewebPostgresTlsError(_TLS_CA_FETCH_FAILED)


def _validate_ca(raw: bytes) -> None:
    if not raw or len(raw) > _MAX_CA_BYTES:
        raise TimewebPostgresTlsError(_TLS_CA_INVALID)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise TimewebPostgresTlsError(_TLS_CA_INVALID) from None
    begin = text.find("-----BEGIN CERTIFICATE-----")
    end_marker = "-----END CERTIFICATE-----"
    end = text.find(end_marker, begin + 1)
    if begin < 0 or end < 0:
        raise TimewebPostgresTlsError(_TLS_CA_INVALID)
    certificate = text[begin : end + len(end_marker)]
    try:
        ssl.PEM_cert_to_DER_cert(certificate)
    except ValueError:
        raise TimewebPostgresTlsError(_TLS_CA_INVALID) from None


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
    except OSError:
        raise TimewebPostgresTlsError(_TLS_CA_INVALID) from None
    return context


def _socket_record_address(
    record: Any,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not isinstance(record, tuple) or len(record) < 5:
        return None
    socket_address = record[4]
    if not isinstance(socket_address, tuple) or not socket_address:
        return None
    try:
        return ipaddress.ip_address(str(socket_address[0]).strip())
    except ValueError:
        return None


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
        raise TimewebPostgresTlsError(_TLS_DNS_RESOLUTION_FAILED) from None

    addresses: set[str] = set()
    non_public_seen = False
    for record in records:
        address = _socket_record_address(record)
        if address is None:
            continue
        if not address.is_global:
            non_public_seen = True
            continue
        addresses.add(address.compressed)

    if non_public_seen or not addresses:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC")
    return tuple(sorted(addresses))


def _transport_socket_failure_code(exc: OSError) -> str:
    code = _TLS_TCP_FAILED
    if isinstance(exc, ssl.SSLCertVerificationError):
        code = "TIMEWEB_PG_TLS_CERT_VERIFY_FAILED"
    elif isinstance(exc, ssl.SSLError):
        code = "TIMEWEB_PG_TLS_HANDSHAKE_FAILED"
    elif isinstance(exc, TimeoutError):
        code = _TLS_TCP_TIMEOUT
    elif isinstance(exc, ConnectionRefusedError) or exc.errno == errno.ECONNREFUSED:
        code = _TLS_TCP_REFUSED
    elif exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
        code = _TLS_ROUTE_UNREACHABLE
    return code


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
    except OSError as exc:
        raise TimewebPostgresTlsError(_transport_socket_failure_code(exc)) from None
    finally:
        if raw_socket is not None:
            with suppress(OSError):
                raw_socket.close()


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
    raise TimewebPostgresTlsError(_TLS_TCP_FAILED)


def _probe_bound_public_transport_with_retry(
    hostname: str,
    address: str,
    context: Any,
    *,
    connector: Any,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> str:
    attempts = len(delays) + 1
    for attempt in range(attempts):
        try:
            _probe_postgres_tls_endpoint(
                hostname,
                address,
                context,
                connector=connector,
            )
        except TimewebPostgresTlsError as exc:
            if exc.code not in _TRANSIENT_TRANSPORT_CODES or attempt + 1 >= attempts:
                raise
            _emit(
                "TIMEWEB_PG_TLS_BOUND_PUBLIC_TRANSPORT_RETRY "
                f"code={exc.code} attempt={attempt + 2}/{attempts}"
            )
            sleeper(delays[attempt])
            continue
        _emit(
            "TIMEWEB_PG_TLS_BOUND_PUBLIC_TRANSPORT=READY "
            "tcp=5432 tls=verify-full route=provider-bound"
        )
        return address
    raise AssertionError("bounded Timeweb PostgreSQL public transport retry exhausted")


def _probe_private_transport_with_retry(
    hostname: str,
    address: str,
    context: Any,
    *,
    connector: Any,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> str:
    attempts = len(delays) + 1
    for attempt in range(attempts):
        try:
            _probe_postgres_tls_endpoint(
                hostname,
                address,
                context,
                connector=connector,
            )
        except TimewebPostgresTlsError as exc:
            if exc.code not in _TRANSIENT_TRANSPORT_CODES or attempt + 1 >= attempts:
                raise
            _emit(
                "TIMEWEB_PG_TLS_PRIVATE_TRANSPORT_RETRY "
                f"code={exc.code} attempt={attempt + 2}/{attempts}"
            )
            sleeper(delays[attempt])
            continue
        _emit(
            "TIMEWEB_PG_TLS_PRIVATE_TRANSPORT=READY "
            "tcp=5432 tls=verify-full route=private"
        )
        return address
    raise AssertionError("bounded Timeweb PostgreSQL private transport retry exhausted")


def _validate_probe_ca(ca_path: Path) -> None:
    try:
        if ca_path.is_symlink() or not ca_path.is_file():
            raise TimewebPostgresTlsError(_TLS_CA_PATH_UNSAFE)
        raw = ca_path.read_bytes()
    except TimewebPostgresTlsError:
        raise
    except OSError:
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_CA_PATH_UNAVAILABLE") from None
    _validate_ca(raw)


def _probe_transport_with_retry(
    hostname: str,
    context: Any,
    *,
    resolver: Any,
    connector: Any,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> str:
    attempts = len(delays) + 1
    for attempt in range(attempts):
        try:
            verified_address = _probe_transport_once(
                hostname,
                context,
                resolver=resolver,
                connector=connector,
            )
        except TimewebPostgresTlsError as exc:
            if exc.code not in _TRANSIENT_TRANSPORT_CODES or attempt + 1 >= attempts:
                raise
            _emit(
                "TIMEWEB_PG_TLS_TRANSPORT_RETRY "
                f"code={exc.code} attempt={attempt + 2}/{attempts}"
            )
            sleeper(delays[attempt])
            continue
        _emit("TIMEWEB_PG_TLS_TRANSPORT=READY dns=public tcp=5432 tls=verify-full")
        return verified_address
    raise AssertionError("bounded Timeweb PostgreSQL transport retry exhausted")


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
    _validate_probe_ca(ca_path)
    context = context_factory(ca_path)
    hostname = params["host"].strip().lower().rstrip(".")
    return _probe_transport_with_retry(
        hostname,
        context,
        resolver=resolver,
        connector=connector,
        sleeper=sleeper,
        delays=delays,
    )


def probe_timeweb_postgres_bound_public_transport(
    dsn: str,
    ca_path: Path,
    *,
    public_hostaddr: str,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
) -> str:
    _reject_ambient_libpq_environment()
    params = _connection_params(dsn)
    address = _public_ipv4_address(public_hostaddr)
    _validate_probe_ca(ca_path)
    context = context_factory(ca_path)
    hostname = params["host"].strip().lower().rstrip(".")
    return _probe_bound_public_transport_with_retry(
        hostname,
        address.compressed,
        context,
        connector=connector,
        sleeper=sleeper,
        delays=delays,
    )


def probe_timeweb_postgres_private_transport(
    dsn: str,
    ca_path: Path,
    *,
    private_hostaddr: str,
    private_network_cidr: str,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
) -> str:
    _reject_ambient_libpq_environment()
    params = _connection_params(dsn)
    network = _private_ipv4_network(private_network_cidr)
    address = _private_ipv4_address(private_hostaddr, network)
    _validate_probe_ca(ca_path)
    context = context_factory(ca_path)
    hostname = params["host"].strip().lower().rstrip(".")
    return _probe_private_transport_with_retry(
        hostname,
        address.compressed,
        context,
        connector=connector,
        sleeper=sleeper,
        delays=delays,
    )


def resolve_timeweb_postgres_dsn(
    dsn: str,
    ca_path: Path,
    *,
    hostaddr: str | None = None,
    private_network_cidr: str | None = None,
) -> str:
    _connection_params(dsn)
    try:
        if ca_path.is_symlink() or not ca_path.is_file():
            raise TimewebPostgresTlsError(_TLS_CA_PATH_UNSAFE)
        _validate_ca(ca_path.read_bytes())
        absolute_ca = ca_path.resolve(strict=True)
        prepared_options = {
            _SSLROOTCERT_KEY: str(absolute_ca),
            _GSSENCMODE_KEY: _PREPARED_GSSENCMODE,
            _SSLCERTMODE_KEY: _PREPARED_SSLCERTMODE,
            _SSL_MIN_PROTOCOL_VERSION_KEY: _PREPARED_SSL_MIN_PROTOCOL_VERSION,
        }
        if hostaddr is None:
            return make_conninfo(dsn, **prepared_options)
        address = _prepared_hostaddr(
            hostaddr,
            private_network_cidr=private_network_cidr,
        )
        prepared_dsn = make_conninfo(
            dsn,
            hostaddr=address.compressed,
            **prepared_options,
        )
        _prepared_connection_params(
            prepared_dsn,
            private_network_cidr=private_network_cidr,
        )
        return prepared_dsn
    except TimewebPostgresTlsError:
        raise
    except (OSError, psycopg.Error):
        raise TimewebPostgresTlsError("TIMEWEB_PG_TLS_DSN_PREPARE_FAILED") from None


def _failure_code(failure_prefix: str, suffix: str) -> str:
    return f"{failure_prefix}_{suffix}"


def _connect_timeout_failure(exc: psycopg.Error) -> tuple[bool, str] | None:
    if isinstance(exc, psycopg.errors.ConnectionTimeout):
        return True, _SUFFIX_TIMEOUT
    return None


def _message_connect_failure(message: str) -> tuple[bool, str] | None:
    for fragments, retryable, suffix in _CONNECT_MESSAGE_RULES:
        if all(fragment in message for fragment in fragments):
            return retryable, suffix
    return None


def _password_metadata_connect_failure(
    exc: psycopg.Error,
) -> tuple[bool, str] | None:
    pgconn = getattr(exc, "pgconn", None)
    if pgconn is None:
        return None
    try:
        needs_credential = bool(pgconn.needs_password) and not bool(
            pgconn.used_password
        )
    except (AttributeError, RuntimeError, psycopg.Error):
        return None
    if needs_credential:
        return False, "PASSWORD_REQUIRED"
    return None


def _sqlstate_connect_failure(exc: psycopg.Error) -> tuple[bool, str] | None:
    sqlstate = (exc.sqlstate or "").strip().upper()
    result = _CONNECT_SQLSTATE_RULES.get(sqlstate)
    if result is None and sqlstate in _TRANSIENT_POSTGRES_SQLSTATES:
        result = (True, "TRANSIENT_CONNECTIVITY")
    elif result is None and sqlstate:
        result = (False, "SERVER_ERROR")
    return result


def _postgres_connect_failure(
    exc: psycopg.Error,
    failure_prefix: str,
) -> tuple[bool, str]:
    if _FAILURE_PREFIX_RE.fullmatch(failure_prefix) is None:
        return False, _CONNECT_FAILURE_PREFIX_INVALID

    candidates = (
        _connect_timeout_failure(exc),
        _message_connect_failure(str(exc).lower()),
        _password_metadata_connect_failure(exc),
        _sqlstate_connect_failure(exc),
    )
    match = next((item for item in candidates if item is not None), None)
    if match is None:
        match = (False, "UNCLASSIFIED_CLIENT_FAILURE")
    retryable, suffix = match
    return retryable, _failure_code(failure_prefix, suffix)


def connect_prepared_timeweb_postgres(
    dsn: str,
    *,
    failure_prefix: str,
    connect_timeout: int = 15,
    private_network_cidr: str | None = None,
    retry_delays: tuple[float, ...] = _CONNECT_RETRY_DELAYS_SECONDS,
    sleeper: Sleep = time.sleep,
    connector: Any = psycopg.connect,
    autocommit: bool | None = None,
) -> Any:
    _reject_ambient_libpq_environment()
    _prepared_connection_params(
        dsn,
        private_network_cidr=private_network_cidr,
    )
    if _FAILURE_PREFIX_RE.fullmatch(failure_prefix) is None:
        raise TimewebPostgresTlsError(_CONNECT_FAILURE_PREFIX_INVALID)
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
            raise TimewebPostgresTlsError(f"{failure_prefix}_CLIENT_FAILURE") from None
    raise AssertionError("bounded Timeweb PostgreSQL connection retry exhausted")


def prepare_timeweb_postgres_private_target(
    dsn: str,
    ca_path: Path,
    *,
    private_hostaddr: str,
    private_network_cidr: str,
    sleeper: Sleep = time.sleep,
    transport_delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
) -> str:
    _connection_params(dsn)
    verified_address = probe_timeweb_postgres_private_transport(
        dsn,
        ca_path,
        private_hostaddr=private_hostaddr,
        private_network_cidr=private_network_cidr,
        connector=connector,
        context_factory=context_factory,
        sleeper=sleeper,
        delays=transport_delays,
    )
    return resolve_timeweb_postgres_dsn(
        dsn,
        ca_path,
        hostaddr=verified_address,
        private_network_cidr=private_network_cidr,
    )


def prepare_timeweb_postgres_target(
    dsn: str,
    ca_path: Path,
    *,
    sleeper: Sleep = time.sleep,
    transport_delays: tuple[float, ...] = _TRANSPORT_RETRY_DELAYS_SECONDS,
    resolver: Any = socket.getaddrinfo,
    connector: Any = socket.create_connection,
    context_factory: Any = _tls_client_context,
) -> str:
    _connection_params(dsn)
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
