from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

import psycopg

from omni_cio.adapters.tinvest_read_v1 import BrokerAccountBindingV1
from omni_cio.contracts.v1.domain import BrokerProvider, canonical_broker_account_id
from omni_cio.persistence import apply_migrations
from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.persistence_v1 import (
    PostgresBrokerConnectionRepositoryV1,
    PostgresWebSessionRegistryV1,
)
from omni_cio.web.product_identity_v1 import (
    PostgresProductIdentityRepositoryV1,
    ProductAccountScopeV1,
    ProductIdentityServiceV1,
    protected_identity_binding_hmac_sha256,
)


DSN_ENV = "OMNI_CIO_WP22A_PHASE2_DSN"
NOW = datetime(2026, 8, 19, 4, 0, tzinfo=timezone.utc)
BINDING_KEY = b"wp22a-synthetic-binding-key-0001!!"
SCOPE_A = ProductAccountScopeV1(
    user_id="user:v1:product_a",
    tenant_id="tenant:v1:product_a",
)
SCOPE_B = ProductAccountScopeV1(
    user_id="user:v1:product_b",
    tenant_id="tenant:v1:product_b",
)
PROBE_ROLE = "wp22a_phase2_rls_probe"


def _dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        raise RuntimeError(f"{DSN_ENV} is required")
    return value


def _identity(provider: IdentityProviderV1, subject: str) -> VerifiedExternalIdentityV1:
    return VerifiedExternalIdentityV1(provider=provider, subject=subject)


def _binding(character: str, suffix: str) -> BrokerAccountBindingV1:
    fingerprint = character * 64
    return BrokerAccountBindingV1(
        broker_account_id=canonical_broker_account_id(
            BrokerProvider.T_INVEST,
            fingerprint,
        ),
        account_fingerprint_sha256=fingerprint,
        masked_label=f"****{suffix}",
        access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
    )


def _expect_database_error(connection: psycopg.Connection[Any], action: Any) -> bool:
    try:
        with connection.transaction():
            action()
    except psycopg.Error:
        return True
    raise AssertionError("database operation unexpectedly crossed tenant boundary")


def _set_probe_role_and_scope(
    connection: psycopg.Connection[Any],
    tenant_id: str | None,
) -> None:
    connection.execute(f"SET LOCAL ROLE {PROBE_ROLE}")
    if tenant_id is not None:
        connection.execute(
            "SELECT set_config('omni_cio.tenant_id', %s, true)",
            (tenant_id,),
        )


def _exercise(connection: psycopg.Connection[Any]) -> dict[str, object]:
    apply_migrations(connection)

    scopes = iter((SCOPE_A, SCOPE_B))
    identities = PostgresProductIdentityRepositoryV1(
        connection,
        binding_key=BINDING_KEY,
        scope_factory=lambda: next(scopes),
    )
    service = ProductIdentityServiceV1(identities, registration_enabled=True)
    telegram_a = _identity(IdentityProviderV1.TELEGRAM, "synthetic-telegram-a")
    telegram_b = _identity(IdentityProviderV1.TELEGRAM, "synthetic-telegram-b")
    vk_a = _identity(IdentityProviderV1.VK_ID, "synthetic-vk-a")

    if service.authenticate(telegram_a, now=NOW) != SCOPE_A:
        raise AssertionError("Telegram A did not bind to product account A")
    if service.authenticate(telegram_b, now=NOW + timedelta(seconds=1)) != SCOPE_B:
        raise AssertionError("Telegram B did not bind to product account B")
    service.link_authenticated_identity(
        SCOPE_A,
        vk_a,
        now=NOW + timedelta(seconds=2),
    )
    if service.authenticate(vk_a, now=NOW + timedelta(seconds=3)) != SCOPE_A:
        raise AssertionError("VK link did not resolve to existing account A")

    account_rows = connection.execute(
        "SELECT user_id, tenant_id, role FROM omni_cio_v10.users "
        "WHERE tenant_id IN (%s, %s) ORDER BY tenant_id",
        (SCOPE_A.tenant_id, SCOPE_B.tenant_id),
    ).fetchall()
    if account_rows != [
        (SCOPE_A.user_id, SCOPE_A.tenant_id, "user"),
        (SCOPE_B.user_id, SCOPE_B.tenant_id, "user"),
    ]:
        raise AssertionError(f"product account rows are invalid: {account_rows!r}")

    binding_columns = {
        str(row[0])
        for row in connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'omni_cio_v10' "
            "AND table_name = 'external_identity_bindings'"
        ).fetchall()
    }
    if "subject" in binding_columns or "subject_binding_sha256" in binding_columns:
        raise AssertionError("raw/enumerable provider subject storage is present")
    if "subject_binding_hmac_sha256" not in binding_columns:
        raise AssertionError("protected provider binding column is missing")
    expected_hmac = protected_identity_binding_hmac_sha256(
        telegram_a,
        binding_key=BINDING_KEY,
    )
    binding_row = connection.execute(
        "SELECT subject_binding_hmac_sha256 FROM omni_cio_v10.external_identity_bindings "
        "WHERE provider = 'telegram' AND user_id = %s",
        (SCOPE_A.user_id,),
    ).fetchone()
    if binding_row is None or str(binding_row[0]) != expected_hmac:
        raise AssertionError("protected provider binding did not round-trip")
    if str(binding_row[0]) == telegram_a.binding_fingerprint_sha256():
        raise AssertionError("provider binding regressed to unkeyed SHA-256")

    sessions = PostgresWebSessionRegistryV1(connection)
    token_a, session_a = sessions.create(
        user_id=SCOPE_A.user_id,
        tenant_id=SCOPE_A.tenant_id,
        now=NOW,
    )
    token_b, session_b = sessions.create(
        user_id=SCOPE_B.user_id,
        tenant_id=SCOPE_B.tenant_id,
        now=NOW,
    )
    if session_a.tenant_id != SCOPE_A.tenant_id or session_b.tenant_id != SCOPE_B.tenant_id:
        raise AssertionError("server-side session scope changed tenant")
    if sessions.resolve(token_a, now=NOW + timedelta(seconds=1)) != session_a.model_copy() if False else False:
        raise AssertionError("unreachable")
    resolved_a = sessions.resolve(token_a, now=NOW + timedelta(seconds=1))
    resolved_b = sessions.resolve(token_b, now=NOW + timedelta(seconds=1))
    if resolved_a is None or resolved_a.tenant_id != SCOPE_A.tenant_id:
        raise AssertionError("session A did not resolve account tenant A")
    if resolved_b is None or resolved_b.tenant_id != SCOPE_B.tenant_id:
        raise AssertionError("session B did not resolve account tenant B")
    persisted_session_values = {
        str(row[0])
        for row in connection.execute(
            "SELECT token_sha256 FROM omni_cio_v10.web_sessions"
        ).fetchall()
    }
    if token_a in persisted_session_values or token_b in persisted_session_values:
        raise AssertionError("plaintext session token reached PostgreSQL")

    broker_repository = PostgresBrokerConnectionRepositoryV1(connection)
    binding_a = _binding("a", "1001")
    binding_b = _binding("b", "2002")
    connection_a = "broker-connection:v1:" + "1" * 64
    connection_b = "broker-connection:v1:" + "2" * 64
    secret_a = "read-connection:v1:" + "3" * 64
    secret_b = "read-connection:v1:" + "4" * 64
    broker_repository.create_read_connection(
        tenant_id=SCOPE_A.tenant_id,
        connection_id=connection_a,
        secret_ref=secret_a,
        bindings=(binding_a,),
        now=NOW,
    )
    broker_repository.create_read_connection(
        tenant_id=SCOPE_B.tenant_id,
        connection_id=connection_b,
        secret_ref=secret_b,
        bindings=(binding_b,),
        now=NOW + timedelta(seconds=1),
    )
    rows_a = broker_repository.list_read_connections(tenant_id=SCOPE_A.tenant_id)
    rows_b = broker_repository.list_read_connections(tenant_id=SCOPE_B.tenant_id)
    if len(rows_a) != 1 or rows_a[0].connection_id != connection_a:
        raise AssertionError("application broker scope leaked into tenant A")
    if len(rows_b) != 1 or rows_b[0].connection_id != connection_b:
        raise AssertionError("application broker scope leaked into tenant B")
    if (
        broker_repository.revoke_read_connection(
            tenant_id=SCOPE_A.tenant_id,
            connection_id=connection_b,
            now=NOW + timedelta(seconds=2),
        )
        is not None
    ):
        raise AssertionError("cross-tenant broker object ID authorized mutation")

    rls_rows = connection.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname IN ('broker_accounts','broker_connections','broker_connection_accounts') "
        "ORDER BY c.relname"
    ).fetchall()
    if len(rls_rows) != 3 or not all(bool(row[1]) and bool(row[2]) for row in rls_rows):
        raise AssertionError(f"broker RLS/FORCE policy is not enabled: {rls_rows!r}")

    connection.execute(f"CREATE ROLE {PROBE_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    connection.execute(f"GRANT USAGE ON SCHEMA omni_cio_v10 TO {PROBE_ROLE}")
    connection.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "omni_cio_v10.broker_accounts, "
        "omni_cio_v10.broker_connections, "
        f"omni_cio_v10.broker_connection_accounts TO {PROBE_ROLE}"
    )

    with connection.transaction():
        _set_probe_role_and_scope(connection, None)
        unscoped = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections"
        ).fetchall()
        if unscoped:
            raise AssertionError("RLS default-deny failed without tenant context")

    with connection.transaction():
        _set_probe_role_and_scope(connection, SCOPE_A.tenant_id)
        visible_a = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections"
        ).fetchall()
        hidden_b = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections "
            "WHERE connection_id = %s",
            (connection_b,),
        ).fetchall()
        if visible_a != [(connection_a,)] or hidden_b:
            raise AssertionError("RLS SELECT leaked a cross-tenant broker connection")

    with connection.transaction():
        _set_probe_role_and_scope(connection, SCOPE_B.tenant_id)
        visible_b = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections"
        ).fetchall()
        if visible_b != [(connection_b,)]:
            raise AssertionError("RLS tenant B view is not exact")

    cross_insert_rejected = _expect_database_error(
        connection,
        lambda: (
            _set_probe_role_and_scope(connection, SCOPE_A.tenant_id),
            connection.execute(
                "INSERT INTO omni_cio_v10.broker_connections "
                "(connection_id, tenant_id, provider, credential_role, state, secret_ref, "
                "created_at, last_verified_at) "
                "VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, %s, %s)",
                (
                    "broker-connection:v1:" + "5" * 64,
                    SCOPE_B.tenant_id,
                    "read-connection:v1:" + "6" * 64,
                    NOW,
                    NOW,
                ),
            ),
        ),
    )

    legacy_owner_guards = {
        str(row[0])
        for row in connection.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE connamespace = 'omni_cio_v10'::regnamespace"
        ).fetchall()
    }
    for required in (
        "portfolio_owner_only",
        "decision_owner_only",
        "job_owner_only",
        "content_blob_owner_only",
    ):
        if required not in legacy_owner_guards:
            raise AssertionError(f"Phase 2 widened unrelated private state: {required}")
    for removed in (
        "web_session_owner_only",
        "broker_account_owner_only",
        "broker_connection_owner_only",
        "broker_connection_accounts_owner_only",
    ):
        if removed in legacy_owner_guards:
            raise AssertionError(f"Phase 2 required boundary stayed OWNER-only: {removed}")

    return {
        "status": "PASS",
        "product_accounts_isolated": True,
        "provider_binding_hmac": True,
        "raw_provider_subject_persisted": False,
        "plaintext_session_token_persisted": False,
        "server_session_tenant_scope": True,
        "broker_application_tenant_scope": True,
        "broker_rls_enabled": True,
        "broker_rls_force_enabled": True,
        "rls_default_deny_without_scope": True,
        "cross_tenant_object_id_denied": True,
        "cross_tenant_insert_rejected": cross_insert_rejected,
        "unrelated_private_state_still_owner_locked": True,
        "real_secrets_used": False,
        "private_portfolio_data_used": False,
    }


def main() -> int:
    try:
        with psycopg.connect(_dsn()) as connection:
            result = _exercise(connection)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
