from __future__ import annotations

from collections.abc import Sequence
from email.message import Message
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlunsplit

import pytest

from scripts import provision_v10_render_neon_preview as provisioner


class _HttpResponse:
    status = 200

    def __enter__(self) -> _HttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"result":"ok"}'


class _SequenceOpener:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.methods: list[str] = []

    def open(self, request: Any, *, timeout: float) -> Any:
        assert timeout == 30.0
        self.methods.append(request.get_method())
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_provider_get_network_failure_retries_with_sanitized_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opener = _SequenceOpener(
        [
            URLError("first-sensitive-network-detail"),
            TimeoutError("second-sensitive-network-detail"),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    api = provisioner.JsonApi(
        provisioner.RENDER_API_BASE,
        "provider-secret-marker",
        label="RENDER",
    )
    assert api.request("GET", "/owners?limit=100") == {"result": "ok"}

    assert opener.methods == ["GET", "GET", "GET"]
    assert delays == [1.0, 2.0]
    output = capsys.readouterr().out
    assert output.splitlines() == [
        "RENDER_API_NETWORK_RETRY attempt=2/3",
        "RENDER_API_NETWORK_RETRY attempt=3/3",
    ]
    assert "provider-secret-marker" not in output
    assert "sensitive-network-detail" not in output


def test_provider_mutation_network_failure_is_never_blindly_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _SequenceOpener(
        [
            URLError("ambiguous-provider-mutation"),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    api = provisioner.JsonApi(
        provisioner.NEON_API_BASE,
        "provider-secret-marker",
        label="NEON",
    )
    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_API_NETWORK_ERROR",
    ):
        api.request(
            "POST",
            "/projects",
            body={"project": {"name": "preview"}},
            expected=frozenset({201}),
        )

    assert opener.methods == ["POST"]
    assert delays == []


def test_provider_get_network_retry_is_bounded_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _SequenceOpener(
        [
            URLError("network-detail-1"),
            URLError("network-detail-2"),
            URLError("network-detail-3"),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)
    api = provisioner.JsonApi(
        provisioner.RENDER_API_BASE,
        "provider-secret-marker",
        label="RENDER",
    )

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="RENDER_API_NETWORK_ERROR",
    ):
        api.request("GET", "/owners?limit=100")

    assert opener.methods == ["GET", "GET", "GET"]
    assert delays == [1.0, 2.0]


@pytest.mark.parametrize("status", sorted(provisioner._TRANSIENT_GET_HTTP_STATUSES))
def test_provider_get_retries_only_allowlisted_transient_http_statuses(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: int,
) -> None:
    opener = _SequenceOpener(
        [
            HTTPError(
                "https://api.render.com/v1/owners",
                status,
                "sensitive-upstream-detail",
                Message(),
                None,
            ),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)
    api = provisioner.JsonApi(
        provisioner.RENDER_API_BASE,
        "provider-secret-marker",
        label="RENDER",
    )

    assert api.request("GET", "/owners") == {"result": "ok"}

    assert opener.methods == ["GET", "GET"]
    assert delays == [1.0]
    output = capsys.readouterr().out
    assert output.strip() == (f"RENDER_API_HTTP_RETRY status={status} attempt=2/3")
    assert "provider-secret-marker" not in output
    assert "sensitive-upstream-detail" not in output


@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_provider_mutation_transient_http_status_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    opener = _SequenceOpener(
        [
            HTTPError(
                "https://console.neon.tech/api/v2/projects",
                503,
                "ambiguous-provider-mutation",
                Message(),
                None,
            ),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)
    api = provisioner.JsonApi(
        provisioner.NEON_API_BASE,
        "provider-secret-marker",
        label="NEON",
    )

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_API_HTTP_ERROR status=503",
    ):
        api.request(
            method,
            "/projects",
            body={"project": {"name": "preview"}},
            expected=frozenset({200, 201}),
        )

    assert opener.methods == [method]
    assert delays == []


def test_provider_non_transient_get_http_status_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _SequenceOpener(
        [
            HTTPError(
                "https://api.render.com/v1/owners",
                500,
                "upstream-application-failure",
                Message(),
                None,
            ),
            _HttpResponse(),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner, "_NO_REDIRECT_OPENER", opener)
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)
    api = provisioner.JsonApi(
        provisioner.RENDER_API_BASE,
        "provider-secret-marker",
        label="RENDER",
    )

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="RENDER_API_HTTP_ERROR status=500",
    ):
        api.request("GET", "/owners")

    assert opener.methods == ["GET"]
    assert delays == []


class _OperationalError(Exception):
    pass


class _Rows:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows[0] if self.rows else None


class _DatabaseConnection:
    def __init__(
        self,
        *,
        stored: Sequence[tuple[object, ...]],
        fail_first_execute: bool = False,
        runtime_rows: bool = False,
    ) -> None:
        self.stored = list(stored)
        self.fail_first_execute = fail_first_execute
        self.runtime_rows = runtime_rows
        self.queries: list[str] = []

    def __enter__(self) -> _DatabaseConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(
        self,
        query: str,
        params: object | None = None,
        *,
        prepare: bool | None = None,
    ) -> _Rows:
        del params, prepare
        self.queries.append(query)
        if self.fail_first_execute:
            self.fail_first_execute = False
            raise _OperationalError("sensitive-database-network-detail")
        if self.runtime_rows:
            if query.startswith("SELECT rolname"):
                return _Rows(
                    [
                        (
                            provisioner.RUNTIME_ROLE,
                            True,
                            False,
                            False,
                            False,
                            False,
                            False,
                        )
                    ]
                )
            if query.startswith("SELECT count(*)"):
                return _Rows([(0,)])
            return _Rows(
                [
                    ("broker_accounts", True, True),
                    ("broker_connection_accounts", True, True),
                    ("broker_connections", True, True),
                ]
            )
        if query.startswith("SELECT tenant_id"):
            return _Rows(self.stored)
        return _Rows([])


class _Psycopg:
    OperationalError = _OperationalError

    def __init__(self, connections: list[_DatabaseConnection]) -> None:
        self.connections = list(connections)
        self.connect_calls: list[tuple[str, bool, int]] = []

    def connect(
        self,
        uri: str,
        *,
        autocommit: bool,
        connect_timeout: int,
    ) -> _DatabaseConnection:
        self.connect_calls.append((uri, autocommit, connect_timeout))
        return self.connections.pop(0)


def _preview_digests() -> tuple[str, str, list[tuple[str, str]]]:
    tenant, user = provisioner._preview_records()
    tenant_digest = provisioner._canonical_sha256(tenant)
    user_digest = provisioner._canonical_sha256(user)
    stored = sorted(
        [
            (provisioner.PREVIEW_TENANT_ID, tenant_digest),
            (provisioner.PREVIEW_USER_ID, user_digest),
        ]
    )
    return tenant_digest, user_digest, stored


def _database_uri(marker: str, *, user: str = "owner") -> str:
    return urlunsplit(
        (
            "postgresql",
            f"{user}:{marker}@preview.neon.tech",
            "/neondb",
            "sslmode=require",
            "",
        )
    )


def test_synthetic_seed_reconnects_and_converges_after_ambiguous_disconnect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tenant_digest, user_digest, stored = _preview_digests()
    database = _Psycopg(
        [
            _DatabaseConnection(stored=stored, fail_first_execute=True),
            _DatabaseConnection(stored=stored),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    provisioner._seed_preview_records_with_retry(
        database,
        _database_uri("database-secret"),
        tenant_digest,
        user_digest,
    )

    assert len(database.connect_calls) == 2
    assert all(
        autocommit and timeout == provisioner._DATABASE_CONNECT_TIMEOUT_SECONDS
        for _, autocommit, timeout in database.connect_calls
    )
    assert delays == [1.0]
    output = capsys.readouterr().out
    assert output.strip() == "DATABASE_SYNTHETIC_SEED_NETWORK_RETRY attempt=2/3"
    assert "database-secret" not in output
    assert "sensitive-database-network-detail" not in output


def test_synthetic_seed_security_drift_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_digest, user_digest, _stored = _preview_digests()
    database = _Psycopg([_DatabaseConnection(stored=[])])
    delays: list[float] = []
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="SYNTHETIC_PREVIEW_RECORD_DRIFT",
    ):
        provisioner._seed_preview_records_with_retry(
            database,
            _database_uri("marker"),
            tenant_digest,
            user_digest,
        )

    assert len(database.connect_calls) == 1
    assert delays == []


def test_synthetic_seed_network_retry_is_bounded_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_digest, user_digest, stored = _preview_digests()
    database = _Psycopg(
        [
            _DatabaseConnection(stored=stored, fail_first_execute=True),
            _DatabaseConnection(stored=stored, fail_first_execute=True),
            _DatabaseConnection(stored=stored, fail_first_execute=True),
            _DatabaseConnection(stored=stored),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="DATABASE_SYNTHETIC_SEED_NETWORK_ERROR",
    ):
        provisioner._seed_preview_records_with_retry(
            database,
            _database_uri("marker"),
            tenant_digest,
            user_digest,
        )

    assert len(database.connect_calls) == 3
    assert delays == [1.0, 2.0]


def test_runtime_read_only_verification_reconnects_after_transient_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = _Psycopg(
        [
            _DatabaseConnection(
                stored=[],
                fail_first_execute=True,
                runtime_rows=True,
            ),
            _DatabaseConnection(stored=[], runtime_rows=True),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr(provisioner.time, "sleep", delays.append)

    provisioner._verify_hosted_runtime_with_retry(
        database,
        _database_uri("database-secret", user="runtime"),
    )

    assert len(database.connect_calls) == 2
    assert delays == [1.0]
