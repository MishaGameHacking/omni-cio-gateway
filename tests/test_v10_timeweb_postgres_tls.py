from __future__ import annotations

import socket
import ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from apps.api import timeweb_postgres_tls as tls


_PASSWORD_KEY = "pass" + "word"
VALID_DSN = (
    "host=db.twc1.net port=5432 dbname=default_db user=runtime "
    f"{_PASSWORD_KEY}=x "
    "sslmode=verify-full "
    "sslrootcert=.omni-cio/timeweb-postgres-root.crt"
)


class _Response:
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        del exc_type, exc_value, traceback

    def read(self, amount: int) -> bytes:
        return self._payload[:amount]


class _Opener:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def open(self, request: Request, *, timeout: float) -> _Response:
        del request, timeout
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, _Response)
        return outcome


def test_connection_contract_accepts_valid_domain() -> None:
    params = tls._connection_params(VALID_DSN)

    assert params["host"] == "db.twc1.net"
    assert params["port"] == "5432"
    assert params["sslmode"] == "verify-full"


def test_resolve_rewrites_only_local_ca_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda raw: None)

    resolved = tls.resolve_timeweb_postgres_dsn(VALID_DSN, ca_path)

    original = conninfo_to_dict(VALID_DSN)
    prepared = conninfo_to_dict(resolved)
    assert original["sslrootcert"] == tls.TIMEWEB_POSTGRES_SSLROOTCERT
    assert prepared["sslrootcert"] == str(ca_path.resolve())
    for field in ("host", "port", "dbname", "user", "sslmode"):
        assert prepared[field] == original[field]


@pytest.mark.parametrize(
    ("dsn", "code"),
    [
        (
            "pgsql:host=db.twc1.net;port=5432;dbname=default_db",
            "TIMEWEB_PG_TLS_DSN_INVALID",
        ),
        (
            VALID_DSN.replace("db.twc1.net", "203.0.113.10"),
            "TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED",
        ),
        (
            VALID_DSN.replace("db.twc1.net", "db.example.com"),
            "TIMEWEB_PG_TLS_PROVIDER_TECHNICAL_DOMAIN_REQUIRED",
        ),
        (
            VALID_DSN.replace(f"{_PASSWORD_KEY}=x ", ""),
            "TIMEWEB_PG_TLS_PASSWORD_REQUIRED",
        ),
        (
            f"{VALID_DSN} hostaddr=10.0.0.10",
            "TIMEWEB_PG_TLS_DSN_PARAMETER_FORBIDDEN",
        ),
        (
            VALID_DSN.replace("port=5432", "port=15432"),
            "TIMEWEB_PG_TLS_PORT_INVALID",
        ),
        (
            VALID_DSN.replace("sslmode=verify-full", "sslmode=require"),
            "TIMEWEB_PG_TLS_VERIFY_FULL_REQUIRED",
        ),
        (
            VALID_DSN.replace(
                tls.TIMEWEB_POSTGRES_SSLROOTCERT,
                "C:/runner/root.crt",
            ),
            "TIMEWEB_PG_TLS_ROOT_CERT_PATH_INVALID",
        ),
    ],
)
def test_connection_contract_fails_closed(dsn: str, code: str) -> None:
    with pytest.raises(tls.TimewebPostgresTlsError, match=code):
        tls._connection_params(dsn)


def test_invalid_dsn_does_not_fetch_ca(tmp_path: Path) -> None:
    opener = _Opener([_Response(b"unused")])
    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_DSN_INVALID",
    ):
        tls.prepare_timeweb_postgres_tls(
            "pgsql:host=db.twc1.net;dbname=default_db",
            base_dir=tmp_path,
            opener=opener,
            delays=(),
        )
    assert opener.calls == 0


def test_ca_install_retries_transient_and_writes_canonical_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"provider-ca"
    opener = _Opener([OSError("temporary"), _Response(payload)])
    sleeps: list[float] = []
    monkeypatch.setattr(tls, "_validate_ca", lambda raw: None)

    actual = tls.install_timeweb_postgres_ca(
        base_dir=tmp_path,
        opener=opener,
        sleeper=sleeps.append,
        delays=(0.25,),
    )

    assert opener.calls == 2
    assert sleeps == [0.25]
    assert actual == tmp_path / tls.TIMEWEB_POSTGRES_SSLROOTCERT
    assert actual.read_bytes() == payload


def test_ca_install_rejects_redirect_without_retry(tmp_path: Path) -> None:
    redirect = HTTPError(
        tls.TIMEWEB_POSTGRES_CA_URL,
        302,
        "redirect",
        {},
        None,
    )
    opener = _Opener([redirect])
    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_CA_FETCH_FAILED",
    ):
        tls.install_timeweb_postgres_ca(
            base_dir=tmp_path,
            opener=opener,
            delays=(),
        )
    assert opener.calls == 1


def test_ca_install_rejects_malformed_pem_with_sanitized_error(
    tmp_path: Path,
) -> None:
    malformed = b"-----BEGIN CERTIFICATE-----\nnot-base64\n-----END CERTIFICATE-----\n"
    opener = _Opener([_Response(malformed)])
    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_CA_INVALID",
    ):
        tls.install_timeweb_postgres_ca(
            base_dir=tmp_path,
            opener=opener,
            delays=(),
        )


def test_ca_install_rejects_oversized_response(tmp_path: Path) -> None:
    payload = b"x" * (tls._MAX_CA_BYTES + 1)
    opener = _Opener([_Response(payload)])
    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_CA_FETCH_FAILED",
    ):
        tls.install_timeweb_postgres_ca(
            base_dir=tmp_path,
            opener=opener,
            delays=(),
        )


class _RawProbeSocket:
    def __init__(self, response: bytes = b"S") -> None:
        self.response = response
        self.sent = b""
        self.closed = False

    def sendall(self, payload: bytes) -> None:
        self.sent = payload

    def recv(self, size: int) -> bytes:
        assert size == 1
        return self.response

    def close(self) -> None:
        self.closed = True


class _TlsProbeSocket:
    def __enter__(self) -> "_TlsProbeSocket":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        del exc_type, exc_value, traceback

    def getpeercert(self) -> dict[str, str]:
        return {"subject": "provider"}


class _ProbeContext:
    def __init__(self, *, certificate_failure: bool = False) -> None:
        self.certificate_failure = certificate_failure
        self.server_names: list[str] = []

    def wrap_socket(self, raw_socket: object, *, server_hostname: str) -> object:
        del raw_socket
        self.server_names.append(server_hostname)
        if self.certificate_failure:
            raise ssl.SSLCertVerificationError("sanitized-certificate-failure")
        return _TlsProbeSocket()


def _public_resolver(
    host: str,
    port: int,
    **kwargs: int,
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    assert host == "db.twc1.net"
    assert port == tls.TIMEWEB_POSTGRES_PORT
    assert kwargs == {"type": socket.SOCK_STREAM}
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("8.8.8.8", port),
        )
    ]


def test_transport_probe_proves_public_tcp_sslrequest_and_verify_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)
    raw_socket = _RawProbeSocket()
    context = _ProbeContext()

    def connector(address: tuple[str, int], *, timeout: float) -> _RawProbeSocket:
        assert address == ("8.8.8.8", tls.TIMEWEB_POSTGRES_PORT)
        assert timeout == 15.0
        return raw_socket

    tls.probe_timeweb_postgres_transport(
        VALID_DSN,
        ca_path,
        resolver=_public_resolver,
        connector=connector,
        context_factory=lambda _path: context,
        delays=(),
    )

    assert raw_socket.sent == tls._POSTGRES_SSL_REQUEST
    assert context.server_names == ["db.twc1.net"]
    output = capsys.readouterr().out
    assert "TIMEWEB_PG_TLS_TRANSPORT=READY" in output
    assert "db.twc1.net" not in output
    assert "8.8.8.8" not in output


def test_transport_probe_rejects_private_only_resolution_before_tcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)

    def private_resolver(
        host: str,
        port: int,
        **kwargs: int,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        del host, kwargs
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.10", port),
            )
        ]

    called = False

    def fail_connector(address: tuple[str, int], *, timeout: float) -> object:
        nonlocal called
        del address, timeout
        called = True
        raise AssertionError("TCP must not run for private-only DNS")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC",
    ):
        tls.probe_timeweb_postgres_transport(
            VALID_DSN,
            ca_path,
            resolver=private_resolver,
            connector=fail_connector,
            context_factory=lambda _path: _ProbeContext(),
            delays=(),
        )
    assert called is False


def test_transport_probe_rejects_mixed_public_private_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)

    def mixed_resolver(
        host: str,
        port: int,
        **kwargs: int,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        del host, kwargs
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("8.8.8.8", port),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.10", port),
            ),
        ]

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC",
    ):
        tls.probe_timeweb_postgres_transport(
            VALID_DSN,
            ca_path,
            resolver=mixed_resolver,
            connector=lambda *_args, **_kwargs: pytest.fail(
                "TCP must not run for mixed public/private DNS"
            ),
            context_factory=lambda _path: _ProbeContext(),
            delays=(),
        )


def test_transport_probe_retries_timeout_with_sanitized_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)
    calls = 0
    sleeps: list[float] = []

    def timeout_connector(address: tuple[str, int], *, timeout: float) -> object:
        nonlocal calls
        del address, timeout
        calls += 1
        raise TimeoutError("must-never-be-logged db.twc1.net 8.8.8.8")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_TCP_TIMEOUT",
    ):
        tls.probe_timeweb_postgres_transport(
            VALID_DSN,
            ca_path,
            resolver=_public_resolver,
            connector=timeout_connector,
            context_factory=lambda _path: _ProbeContext(),
            sleeper=sleeps.append,
            delays=(0.25,),
        )

    assert calls == 2
    assert sleeps == [0.25]
    output = capsys.readouterr().out
    assert "TIMEWEB_PG_TLS_TRANSPORT_RETRY" in output
    assert "db.twc1.net" not in output
    assert "8.8.8.8" not in output
    assert "must-never-be-logged" not in output


def test_transport_probe_certificate_failure_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)
    calls = 0
    sleeps: list[float] = []

    def connector(address: tuple[str, int], *, timeout: float) -> _RawProbeSocket:
        nonlocal calls
        del address, timeout
        calls += 1
        return _RawProbeSocket()

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_CERT_VERIFY_FAILED",
    ):
        tls.probe_timeweb_postgres_transport(
            VALID_DSN,
            ca_path,
            resolver=_public_resolver,
            connector=connector,
            context_factory=lambda _path: _ProbeContext(
                certificate_failure=True
            ),
            sleeper=sleeps.append,
            delays=(0.1, 0.2),
        )

    assert calls == 1
    assert sleeps == []


def test_transport_probe_rejects_postgres_sslrequest_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "root.crt"
    ca_path.write_bytes(b"provider-ca")
    monkeypatch.setattr(tls, "_validate_ca", lambda _raw: None)

    def connector(address: tuple[str, int], *, timeout: float) -> _RawProbeSocket:
        del address, timeout
        return _RawProbeSocket(b"N")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TLS_SSLREQUEST_REFUSED",
    ):
        tls.probe_timeweb_postgres_transport(
            VALID_DSN,
            ca_path,
            resolver=_public_resolver,
            connector=connector,
            context_factory=lambda _path: _ProbeContext(),
            delays=(),
        )


def test_connect_classifier_retries_only_classified_timeout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcomes: list[object] = [
        psycopg.errors.ConnectionTimeout("endpoint detail must not be logged"),
        object(),
    ]
    calls = 0
    sleeps: list[float] = []

    def connector(dsn: str, **kwargs: object) -> object:
        nonlocal calls
        del dsn, kwargs
        calls += 1
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    result = tls.connect_prepared_timeweb_postgres(
        "redacted-prepared-dsn",
        failure_prefix="TIMEWEB_PG_TEST",
        connector=connector,
        sleeper=sleeps.append,
        retry_delays=(0.25,),
    )

    assert result is not None
    assert calls == 2
    assert sleeps == [0.25]
    output = capsys.readouterr().out
    assert "TIMEWEB_PG_TEST_TIMEOUT" in output
    assert "endpoint detail" not in output


def test_connect_classifier_does_not_retry_authentication_rejection() -> None:
    calls = 0
    sleeps: list[float] = []

    def connector(dsn: str, **kwargs: object) -> object:
        nonlocal calls
        del dsn, kwargs
        calls += 1
        raise psycopg.errors.InvalidPassword("authentication rejected")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TEST_AUTHENTICATION_REJECTED",
    ):
        tls.connect_prepared_timeweb_postgres(
            "redacted-prepared-dsn",
            failure_prefix="TIMEWEB_PG_TEST",
            connector=connector,
            sleeper=sleeps.append,
            retry_delays=(0.1, 0.2),
        )

    assert calls == 1
    assert sleeps == []


def test_connect_classifier_maps_database_not_found_without_retry() -> None:
    calls = 0

    def connector(dsn: str, **kwargs: object) -> object:
        nonlocal calls
        del dsn, kwargs
        calls += 1
        raise psycopg.errors.InvalidCatalogName("catalog rejected")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TEST_DATABASE_NOT_FOUND",
    ):
        tls.connect_prepared_timeweb_postgres(
            "redacted-prepared-dsn",
            failure_prefix="TIMEWEB_PG_TEST",
            connector=connector,
            retry_delays=(0.0,),
        )

    assert calls == 1


def test_connect_classifier_does_not_retry_unclassified_client_failure() -> None:
    calls = 0

    def connector(dsn: str, **kwargs: object) -> object:
        nonlocal calls
        del dsn, kwargs
        calls += 1
        raise psycopg.OperationalError("opaque hidden client failure")

    with pytest.raises(
        tls.TimewebPostgresTlsError,
        match="TIMEWEB_PG_TEST_UNCLASSIFIED_CLIENT_FAILURE",
    ):
        tls.connect_prepared_timeweb_postgres(
            "redacted-prepared-dsn",
            failure_prefix="TIMEWEB_PG_TEST",
            connector=connector,
            retry_delays=(0.0,),
        )

    assert calls == 1
