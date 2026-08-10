from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import sys
import threading
from typing import Any

import psycopg

from omni_cio.contracts.v1.domain import (
    OWNER_TENANT_ID,
    BrokerAccountV1,
    BrokerProvider,
    CanonicalDomainCatalogV1,
    DecisionRecordV1,
    EvidenceRecordV1,
    EvidenceSourceKind,
    ExecutionRecordV1,
    IncidentRecordV1,
    IncidentStatus,
    InstrumentPrimaryIdentityKind,
    InstrumentV1,
    JournalRecordV1,
    PlanRecordV1,
    PolicyRecordV1,
    PortfolioSnapshotRecordV1,
    PortfolioV1,
    PositionRecordV1,
    TenantV1,
    UserV1,
    canonical_broker_account_id,
    canonical_instrument_id,
    canonical_position_id,
)
from omni_cio.persistence import (
    PersistenceConflictError,
    PostgresDomainRepository,
    apply_migrations,
    current_migration_state,
    migration_series_digest,
)


DSN_ENV = "OMNI_CIO_WP13_DSN"
NOW = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)


def _id(prefix: str, character: str) -> str:
    return f"{prefix}:v1:{character * 64}"


def _catalog() -> CanonicalDomainCatalogV1:
    fingerprint = "1" * 64
    account_id = canonical_broker_account_id(BrokerProvider.T_INVEST, fingerprint)
    portfolio_id = _id("portfolio", "2")
    policy_id = _id("policy", "3")
    snapshot_id = _id("portfolio-snapshot", "4")
    instrument_id = canonical_instrument_id(
        InstrumentPrimaryIdentityKind.BROKER_UID,
        "wp13-broker-uid-001",
    )
    evidence_id = _id("evidence", "5")
    incident_id = _id("incident", "6")
    decision_id = _id("decision", "7")
    plan_id = _id("plan", "8")
    execution_id = _id("execution", "9")
    journal_id = _id("journal", "a")

    return CanonicalDomainCatalogV1(
        generated_at=NOW,
        tenants=(TenantV1(created_at=NOW),),
        users=(UserV1(created_at=NOW),),
        broker_accounts=(
            BrokerAccountV1(
                broker_account_id=account_id,
                tenant_id=OWNER_TENANT_ID,
                provider=BrokerProvider.T_INVEST,
                account_fingerprint_sha256=fingerprint,
                masked_label="****0013",
                created_at=NOW,
            ),
        ),
        portfolios=(
            PortfolioV1(
                portfolio_id=portfolio_id,
                tenant_id=OWNER_TENANT_ID,
                broker_account_id=account_id,
                base_currency="RUB",
                created_at=NOW,
                label="WP13 synthetic portfolio",
            ),
        ),
        instruments=(
            InstrumentV1(
                instrument_id=instrument_id,
                primary_identity_kind=InstrumentPrimaryIdentityKind.BROKER_UID,
                broker_uid="wp13-broker-uid-001",
                figi="BBG000000013",
                class_code="TQBR",
                ticker="SYN13",
                name="WP13 Synthetic Instrument",
            ),
        ),
        policies=(
            PolicyRecordV1(
                policy_id=policy_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                source_policy_id="wp13_synthetic_policy",
                source_policy_sha256="b" * 64,
                effective_at=NOW,
            ),
        ),
        snapshots=(
            PortfolioSnapshotRecordV1(
                snapshot_id=snapshot_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                broker_account_id=account_id,
                source_payload_sha256="c" * 64,
                broker_server_at=NOW - timedelta(seconds=1),
                local_received_at=NOW,
            ),
        ),
        positions=(
            PositionRecordV1(
                position_id=canonical_position_id(snapshot_id, instrument_id),
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                instrument_id=instrument_id,
                quantity=Decimal("10.125000000000000001"),
                blocked_quantity=Decimal("0.125000000000000001"),
            ),
        ),
        evidence=(
            EvidenceRecordV1(
                evidence_id=evidence_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                instrument_id=instrument_id,
                source_kind=EvidenceSourceKind.EXCHANGE,
                payload_sha256="d" * 64,
                published_at=NOW - timedelta(minutes=5),
                retrieved_at=NOW - timedelta(seconds=2),
                broker_server_at=None,
                local_received_at=NOW,
            ),
        ),
        incidents=(
            IncidentRecordV1(
                incident_id=incident_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                status=IncidentStatus.OPEN,
                evidence_ids=(evidence_id,),
                opened_at=NOW,
            ),
        ),
        decisions=(
            DecisionRecordV1(
                decision_id=decision_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                evidence_ids=(evidence_id,),
                payload_sha256="e" * 64,
                decided_at=NOW,
            ),
        ),
        plans=(
            PlanRecordV1(
                plan_id=plan_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                decision_id=decision_id,
                payload_sha256="f" * 64,
                created_at=NOW,
            ),
        ),
        executions=(
            ExecutionRecordV1(
                execution_id=execution_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                plan_id=plan_id,
                payload_sha256="0" * 64,
                recorded_at=NOW,
            ),
        ),
        journal=(
            JournalRecordV1(
                journal_id=journal_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                decision_id=decision_id,
                plan_id=plan_id,
                execution_id=execution_id,
                incident_id=incident_id,
                payload_sha256="1" * 64,
                recorded_at=NOW,
            ),
        ),
    )


def _dsn() -> str:
    dsn = os.environ.get(DSN_ENV, "").strip()
    if not dsn:
        raise RuntimeError(f"{DSN_ENV} is required")
    return dsn


def _migration_race(dsn: str) -> bool:
    barrier = threading.Barrier(2)

    def worker() -> tuple[int, ...]:
        with psycopg.connect(dsn) as connection:
            barrier.wait(timeout=10)
            return apply_migrations(connection)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result(timeout=60) for future in futures]

    if sorted(results, key=len) != [(), (1,)]:
        raise AssertionError(f"migration race produced unexpected results: {results!r}")
    return True


def _expect_database_failure(connection: psycopg.Connection[Any], sql: str) -> None:
    failed = False
    try:
        with connection.transaction():
            connection.execute(sql)
    except psycopg.Error:
        failed = True
    if not failed:
        raise AssertionError("negative database operation unexpectedly succeeded")


def _exercise(connection: psycopg.Connection[Any], *, migration_race_pass: bool) -> dict[str, Any]:
    if apply_migrations(connection) != ():
        raise AssertionError("migration replay was not idempotent")

    catalog = _catalog()
    repository = PostgresDomainRepository(connection)
    first_revision = repository.persist_catalog(catalog)
    second_revision = repository.persist_catalog(catalog)
    if first_revision != second_revision:
        raise AssertionError("catalog replay created a second state revision")

    quantity_row = connection.execute(
        "SELECT quantity, blocked_quantity FROM omni_cio_v10.positions"
    ).fetchone()
    if quantity_row != (
        Decimal("10.125000000000000001"),
        Decimal("0.125000000000000001"),
    ):
        raise AssertionError("numeric Decimal round-trip changed canonical quantity")

    numeric_meta = connection.execute(
        "SELECT data_type, numeric_precision, numeric_scale "
        "FROM information_schema.columns "
        "WHERE table_schema = 'omni_cio_v10' AND table_name = 'positions' "
        "AND column_name = 'quantity'"
    ).fetchone()
    if numeric_meta != ("numeric", 38, 18):
        raise AssertionError(f"unexpected quantity storage metadata: {numeric_meta!r}")

    approximate_count = connection.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = 'omni_cio_v10' "
        "AND (data_type IN ('real', 'double precision') OR udt_name = 'money')"
    ).fetchone()
    if approximate_count is None or int(approximate_count[0]) != 0:
        raise AssertionError("approximate canonical financial column detected")

    _expect_database_failure(
        connection,
        "UPDATE omni_cio_v10.decisions SET payload_sha256 = repeat('a', 64)",
    )
    _expect_database_failure(connection, "DELETE FROM omni_cio_v10.journal")
    _expect_database_failure(
        connection,
        "INSERT INTO omni_cio_v10.tenants "
        "(tenant_id, schema_version, identity_version, mode, created_at, record_sha256) "
        "VALUES ('tenant:v1:foreign', '1.0', 1, 'owner_personal', now(), repeat('a', 64))",
    )

    conflicting_decision = catalog.decisions[0].model_copy(
        update={"payload_sha256": "a" * 64}
    )
    conflicting_catalog = CanonicalDomainCatalogV1.model_validate(
        {
            **catalog.model_dump(mode="python"),
            "decisions": (conflicting_decision,),
        }
    )
    conflict_rejected = False
    try:
        repository.persist_catalog(conflicting_catalog)
    except PersistenceConflictError:
        conflict_rejected = True
    if not conflict_rejected:
        raise AssertionError("conflicting immutable replay was not rejected")

    blob_payload = b"WP13 synthetic private durable payload"
    blob_hash = repository.put_content_blob(
        blob_payload,
        media_type="application/octet-stream",
        schema_ref="synthetic/wp13",
        created_at=NOW,
    )
    if (
        repository.put_content_blob(
            blob_payload,
            media_type="application/octet-stream",
            schema_ref="synthetic/wp13",
            created_at=NOW,
        )
        != blob_hash
    ):
        raise AssertionError("content-addressed blob replay changed identity")

    with connection.transaction():
        connection.execute(
            "INSERT INTO omni_cio_v10.research_cache "
            "(cache_key, tenant_id, source_identity, content_sha256, retrieved_at, expires_at) "
            "VALUES (%s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s)",
            (
                "expired",
                OWNER_TENANT_ID,
                "synthetic:expired",
                "2" * 64,
                NOW - timedelta(hours=2),
                NOW - timedelta(hours=1),
                "current",
                OWNER_TENANT_ID,
                "synthetic:current",
                "3" * 64,
                NOW,
                NOW + timedelta(hours=1),
            ),
        )
    if repository.prune_research_cache(expired_before=NOW) != 1:
        raise AssertionError("bounded research cache retention removed wrong row count")
    remaining_cache = connection.execute(
        "SELECT cache_key FROM omni_cio_v10.research_cache ORDER BY cache_key"
    ).fetchall()
    if remaining_cache != [("current",)]:
        raise AssertionError("research cache retention crossed expiry boundary")

    digest = repository.state_digest()
    if len(digest) != 64:
        raise AssertionError("state digest is not SHA-256")

    migrations = current_migration_state(connection)
    if len(migrations) != 1:
        raise AssertionError("unexpected applied migration count")

    return {
        "status": "PASS",
        "postgres_major": 18,
        "migration_race_serialized": migration_race_pass,
        "migration_count": len(migrations),
        "migration_series_sha256": migration_series_digest(),
        "state_revision": first_revision,
        "state_digest_sha256": digest,
        "decimal_roundtrip": True,
        "append_only_rejection": True,
        "conflicting_replay_rejected": True,
        "owner_scope_rejection": True,
        "bounded_cache_retention": True,
        "private_payload_logged": False,
        "real_secrets_used": False,
    }


def _digest(connection: psycopg.Connection[Any]) -> dict[str, Any]:
    repository = PostgresDomainRepository(connection)
    migrations = current_migration_state(connection)
    return {
        "status": "PASS",
        "migration_count": len(migrations),
        "migration_series_sha256": migration_series_digest(),
        "state_digest_sha256": repository.state_digest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WP13 PostgreSQL synthetic acceptance probe")
    parser.add_argument("command", choices=("exercise", "digest"))
    args = parser.parse_args()

    try:
        dsn = _dsn()
        migration_race_pass = args.command != "exercise" or _migration_race(dsn)
        with psycopg.connect(dsn) as connection:
            result = (
                _exercise(connection, migration_race_pass=migration_race_pass)
                if args.command == "exercise"
                else _digest(connection)
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": type(exc).__name__,
                    "private_payload_logged": False,
                    "real_secrets_used": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
