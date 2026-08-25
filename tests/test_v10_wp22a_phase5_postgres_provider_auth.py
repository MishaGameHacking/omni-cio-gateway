from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from threading import RLock
from typing import Any, Iterator, Sequence

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionPolicyV1,
    PostgresAuthorizationTransactionStoreV1,
    ProviderAuthorizationError,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"


class _Cursor:
    def __init__(self, row: Sequence[Any] | None = None) -> None:
        self._row = row
        self.rowcount = 0 if row is None else 1

    def fetchone(self) -> Sequence[Any] | None:
        return self._row

    def fetchall(self) -> list[Sequence[Any]]:
        return [] if self._row is None else [self._row]


class _PostgresTransactionFixture:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, str, str, str, str, datetime, datetime]] = {}
        self.queries: list[tuple[str, Sequence[Any] | None]] = []
        self._lock = RLock()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del prepare
        sql = " ".join(str(query).split())
        self.queries.append((sql, params))
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            return _Cursor()
        if sql == (
            "DELETE FROM omni_cio_v10.provider_auth_transactions "
            "WHERE expires_at <= %s"
        ):
            assert params is not None
            now = params[0]
            self.rows = {
                digest: row for digest, row in self.rows.items() if row[6] > now
            }
            return _Cursor()
        if sql == "SELECT count(*) FROM omni_cio_v10.provider_auth_transactions":
            return _Cursor((len(self.rows),))
        if sql.startswith("INSERT INTO omni_cio_v10.provider_auth_transactions"):
            assert params is not None
            state_sha256 = str(params[0])
            self.rows[state_sha256] = (
                str(params[1]),
                str(params[2]),
                str(params[3]),
                str(params[4]),
                str(params[5]),
                params[6],
                params[7],
            )
            return _Cursor()
        if "RETURNING provider, code_verifier, nonce, redirect_uri, expires_at" in sql:
            assert params is not None
            state_sha256, proof_sha256, provider, now = params
            row = self.rows.get(str(state_sha256))
            if (
                row is not None
                and row[0] == proof_sha256
                and row[1] == provider
                and row[6] > now
            ):
                self.rows.pop(str(state_sha256))
                return _Cursor((row[1], row[2], row[3], row[4], row[6]))
            return _Cursor()
        if sql.startswith(
            "DELETE FROM omni_cio_v10.provider_auth_transactions "
            "WHERE state_sha256 = %s AND expires_at <= %s"
        ):
            assert params is not None
            state_sha256, now = params
            row = self.rows.get(str(state_sha256))
            if row is not None and row[6] <= now:
                self.rows.pop(str(state_sha256))
            return _Cursor()
        raise AssertionError(f"unexpected SQL: {sql}")


def test_postgres_transaction_persists_only_state_and_browser_proof_digests() -> None:
    connection = _PostgresTransactionFixture()
    store = PostgresAuthorizationTransactionStoreV1(connection)

    start = store.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    assert start.state not in repr(connection.rows)
    assert start.browser_proof not in repr(connection.rows)
    assert hashlib.sha256(start.state.encode("ascii")).hexdigest() in connection.rows
    stored = next(iter(connection.rows.values()))
    assert stored[0] == hashlib.sha256(
        start.browser_proof.encode("ascii")
    ).hexdigest()
    assert start.browser_proof not in repr(start)


def test_postgres_transaction_binds_route_owned_browser_proof() -> None:
    connection = _PostgresTransactionFixture()
    store = PostgresAuthorizationTransactionStoreV1(connection)
    route_proof = "p" * 43

    start = store.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
        browser_proof=route_proof,
    )

    assert start.browser_proof == route_proof
    stored = next(iter(connection.rows.values()))
    assert stored[0] == hashlib.sha256(route_proof.encode("ascii")).hexdigest()
    consumed = store.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=start.state,
        browser_proof=route_proof,
        now=NOW,
    )
    assert consumed.redirect_uri == CALLBACK


def test_wrong_browser_or_provider_cannot_destroy_postgres_transaction() -> None:
    connection = _PostgresTransactionFixture()
    store = PostgresAuthorizationTransactionStoreV1(connection)
    start = store.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    for provider, proof in (
        (IdentityProviderV1.VK_ID, start.browser_proof),
        (IdentityProviderV1.TELEGRAM, "a" * 43),
    ):
        with pytest.raises(
            ProviderAuthorizationError,
            match="AUTH_TRANSACTION_NOT_FOUND",
        ):
            store.consume(
                provider=provider,
                state=start.state,
                browser_proof=proof,
                now=NOW,
            )
        assert store.pending_count(now=NOW) == 1

    consumed = store.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=start.state,
        browser_proof=start.browser_proof,
        now=NOW,
    )
    assert consumed.redirect_uri == CALLBACK
    assert store.pending_count(now=NOW) == 0


def test_postgres_delete_returning_allows_one_parallel_callback() -> None:
    connection = _PostgresTransactionFixture()
    store = PostgresAuthorizationTransactionStoreV1(connection)
    start = store.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    def consume(_: int) -> str:
        try:
            store.consume(
                provider=IdentityProviderV1.TELEGRAM,
                state=start.state,
                browser_proof=start.browser_proof,
                now=NOW,
            )
            return "accepted"
        except ProviderAuthorizationError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(consume, range(16)))

    assert results.count("accepted") == 1
    assert results.count("AUTH_TRANSACTION_NOT_FOUND") == 15


def test_postgres_capacity_is_global_and_expired_rows_are_purged() -> None:
    connection = _PostgresTransactionFixture()
    store = PostgresAuthorizationTransactionStoreV1(
        connection,
        AuthorizationTransactionPolicyV1(
            max_pending=1,
            lifetime=timedelta(seconds=10),
        ),
    )
    store.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )
    with pytest.raises(
        ProviderAuthorizationError, match="AUTH_TRANSACTION_CAPACITY_EXCEEDED"
    ):
        store.begin(
            provider=IdentityProviderV1.VK_ID,
            redirect_uri=CALLBACK.replace("telegram", "vk_id"),
            now=NOW,
        )

    replacement = store.begin(
        provider=IdentityProviderV1.VK_ID,
        redirect_uri=CALLBACK.replace("telegram", "vk_id"),
        now=NOW + timedelta(seconds=10),
    )
    assert replacement.provider == IdentityProviderV1.VK_ID


def test_phase5_migration_and_runtime_grant_are_least_privilege() -> None:
    migration = (
        ROOT
        / "omni_cio/persistence/migrations/0005_browser_bound_provider_auth.sql"
    ).read_text(encoding="utf-8")
    bootstrap = (
        ROOT / "infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql"
    ).read_text(encoding="utf-8")

    for required in (
        "state_sha256 char(64) PRIMARY KEY",
        "browser_proof_sha256 char(64) NOT NULL UNIQUE",
        "provider IN ('telegram', 'vk_id')",
        "expires_at <= created_at + interval '15 minutes'",
        "provider_auth_expiry_idx",
    ):
        assert required in migration
    assert "raw_state" not in migration
    assert "raw_browser_proof" not in migration
    assert (
        "GRANT SELECT, INSERT, DELETE ON TABLE "
        "omni_cio_v10.provider_auth_transactions"
    ) in bootstrap
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "
        "omni_cio_v10.provider_auth_transactions"
    ) not in bootstrap
