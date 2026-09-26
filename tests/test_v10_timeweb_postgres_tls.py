from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from psycopg.conninfo import conninfo_to_dict

from apps.api import timeweb_postgres_tls as tls


VALID_DSN = (
    "host=db.example.com port=5432 dbname=default_db user=runtime "
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
            "pgsql:host=db.example.com;port=5432;dbname=default_db",
            "TIMEWEB_PG_TLS_DSN_INVALID",
        ),
        (
            VALID_DSN.replace("db.example.com", "203.0.113.10"),
            "TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED",
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
            "pgsql:host=db.example.com;dbname=default_db",
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
