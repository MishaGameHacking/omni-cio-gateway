from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

from omni_cio.contracts.v1.domain import (
    InstrumentPrimaryIdentityKind,
    PositionRecordV1,
    canonical_instrument_id,
    canonical_position_id,
)
from omni_cio.persistence.migration import (
    MIGRATION_LOCK_KEY,
    POSTGRES_MAJOR,
    discover_migrations,
    migration_series_digest,
)
from omni_cio.persistence.repository import model_record_sha256


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "omni_cio" / "persistence" / "migrations" / "0001_initial.sql"


def test_wp13_migration_series_is_contiguous_and_checksum_locked() -> None:
    series = discover_migrations()
    versions = [item.version for item in series]

    assert versions == list(range(1, len(series) + 1))
    assert series[0].name == "initial"
    assert re.fullmatch(r"[a-f0-9]{64}", series[0].sha256)
    assert re.fullmatch(r"[a-f0-9]{64}", migration_series_digest(series))
    assert MIGRATION_LOCK_KEY == 132013
    assert POSTGRES_MAJOR == 18


def test_wp13_initial_schema_covers_master_plan_persistence_families() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    required_relations = {
        "tenants",
        "users",
        "broker_accounts",
        "portfolios",
        "instruments",
        "policies",
        "portfolio_snapshots",
        "positions",
        "evidence",
        "research_cache",
        "incidents",
        "incident_revisions",
        "decisions",
        "plans",
        "executions",
        "journal",
        "jobs",
        "system_health",
        "content_blobs",
        "state_revisions",
    }

    for relation in required_relations:
        assert f"CREATE TABLE omni_cio_v10.{relation}" in sql


def test_wp13_financial_quantity_storage_is_exact_numeric_not_float() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "quantity numeric(38,18)" in sql
    assert "blocked_quantity numeric(38,18)" in sql
    assert re.search(r"\b(real|double precision|float4|float8|money)\b", sql) is None


def test_wp13_owner_scope_and_cross_scope_foreign_keys_are_database_enforced() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert sql.count("tenant_id = 'tenant:v1:owner'") >= 15
    assert "FOREIGN KEY (policy_id, tenant_id, portfolio_id)" in sql
    assert "FOREIGN KEY (snapshot_id, tenant_id, portfolio_id, policy_id)" in sql
    assert (
        "FOREIGN KEY (decision_id, tenant_id, portfolio_id, policy_id, snapshot_id)"
        in sql
    )
    assert (
        "FOREIGN KEY (plan_id, tenant_id, portfolio_id, policy_id, snapshot_id)"
        in sql
    )


def test_wp13_audit_relations_reject_update_and_delete() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "reject_immutable_mutation" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    for relation in (
        "portfolio_snapshots",
        "positions",
        "evidence",
        "incidents",
        "incident_revisions",
        "decisions",
        "plans",
        "executions",
        "journal",
        "state_revisions",
    ):
        assert f"'{relation}'" in sql


def test_wp13_jobs_are_persistence_shape_only_before_wp14() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    jobs = sql.split("CREATE TABLE omni_cio_v10.jobs (", maxsplit=1)[1].split(
        ");", maxsplit=1
    )[0]

    assert "idempotency_key" in jobs
    for wp14_runtime_field in (
        "lease_owner",
        "lease_expires",
        "retry_count",
        "next_attempt",
        "heartbeat",
        "worker_id",
    ):
        assert wp14_runtime_field not in jobs


def test_wp13_record_hash_is_stable_for_decimal_canonical_identity() -> None:
    instrument_id = canonical_instrument_id(
        InstrumentPrimaryIdentityKind.BROKER_UID,
        "wp13-synthetic-instrument",
    )
    snapshot_id = f"portfolio-snapshot:v1:{'4' * 64}"
    position = PositionRecordV1(
        position_id=canonical_position_id(snapshot_id, instrument_id),
        tenant_id="tenant:v1:owner",
        portfolio_id=f"portfolio:v1:{'2' * 64}",
        policy_id=f"policy:v1:{'3' * 64}",
        snapshot_id=snapshot_id,
        instrument_id=instrument_id,
        quantity=Decimal("10.125000000000000001"),
        blocked_quantity=Decimal("0"),
    )

    first = model_record_sha256(position)
    second = model_record_sha256(position.model_copy())
    assert first == second
    assert re.fullmatch(r"[a-f0-9]{64}", first)


def test_wp13_repository_source_contains_no_embedded_database_secret() -> None:
    source = (ROOT / "omni_cio" / "persistence" / "migration.py").read_text(
        encoding="utf-8"
    )
    forbidden = ("password=", "PGPASSWORD", "TINVEST_TOKEN", "REAL_TRADING_ENABLED=true")

    for marker in forbidden:
        assert marker not in source


def test_wp13_schema_uses_timezone_aware_persistent_instants() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "timestamptz" in sql
    assert "timestamp without time zone" not in sql
    assert datetime(2026, 8, 10, tzinfo=timezone.utc).utcoffset() is not None
