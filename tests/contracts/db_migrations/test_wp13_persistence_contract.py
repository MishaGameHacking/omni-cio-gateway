from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import re

import pytest

from omni_cio.contracts.v1.domain import (
    InstrumentPrimaryIdentityKind,
    PositionRecordV1,
    canonical_instrument_id,
    canonical_position_id,
)
from omni_cio.persistence.migration import (
    MIGRATION_LOCK_KEY,
    POSTGRES_MAJOR,
    MigrationSeriesError,
    discover_migrations,
    migration_series_digest,
)
from omni_cio.persistence.repository import model_record_sha256


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "omni_cio" / "persistence" / "migrations" / "0001_initial.sql"


def _sha256_fixture(*chunks: str) -> str:
    value = "".join(chunks)
    assert re.fullmatch(r"[a-f0-9]{64}", value)
    return value



def test_wp13_migration_series_is_contiguous_and_checksum_locked() -> None:
    series = discover_migrations()
    versions = [item.version for item in series]

    assert versions == list(range(1, len(series) + 1))
    assert series[0].name == "initial"
    assert re.fullmatch(r"[a-f0-9]{64}", series[0].sha256)
    assert re.fullmatch(r"[a-f0-9]{64}", migration_series_digest(series))
    assert MIGRATION_LOCK_KEY == 132013
    assert POSTGRES_MAJOR == 18


def test_wp13_migration_checksum_is_line_ending_invariant(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    path = migration_dir / "0001_example.sql"

    source_lf = "CREATE TABLE example (id integer);\nSELECT 1;\n"
    path.write_bytes(source_lf.encode("utf-8"))
    lf_checksum = discover_migrations(migration_dir)[0].sha256

    path.write_bytes(source_lf.replace("\n", "\r\n").encode("utf-8"))
    crlf_checksum = discover_migrations(migration_dir)[0].sha256

    assert lf_checksum == crlf_checksum


def test_wp13_migration_checksum_preserves_historical_crlf_identity(
    tmp_path: Path,
) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    path = migration_dir / "0001_example.sql"
    source_lf = "CREATE TABLE example (id integer);\n"
    historical_bytes = source_lf.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(source_lf.encode("utf-8"))

    assert discover_migrations(migration_dir)[0].sha256 == hashlib.sha256(
        historical_bytes
    ).hexdigest()


def test_wp13_migration_checksum_rejects_bare_cr(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    path = migration_dir / "0001_example.sql"
    path.write_bytes(b"CREATE TABLE example (id integer);\rSELECT 1;\r")

    with pytest.raises(MigrationSeriesError, match="unsupported bare CR"):
        discover_migrations(migration_dir)


def test_wp13_migration_checksum_changes_for_semantic_change(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    path = migration_dir / "0001_example.sql"
    path.write_text("SELECT 1;\n", encoding="utf-8")
    first = discover_migrations(migration_dir)[0].sha256

    path.write_text("SELECT 2;\n", encoding="utf-8")
    second = discover_migrations(migration_dir)[0].sha256

    assert first != second


def test_wp13_accepted_migration_hashes_remain_backward_compatible() -> None:
    expected = {
        1: _sha256_fixture(
            "9beeff50",
            "333e0bc9",
            "13272081",
            "3c31dd50",
            "098c23b9",
            "889ade68",
            "d8dfc8ab",
            "ee1a133e",
        ),
        2: _sha256_fixture(
            "2cafb754",
            "67392b82",
            "320b7958",
            "2a3769a0",
            "477089c3",
            "c0d47f4b",
            "f8a7fbfb",
            "1847f431",
        ),
        3: _sha256_fixture(
            "42517d65",
            "677fafe7",
            "80f7dc4f",
            "e28498ea",
            "dc15276f",
            "6a758269",
            "6846eff2",
            "cebc7206",
        ),
        4: _sha256_fixture(
            "1087fb3b",
            "789fa90c",
            "eafe11d0",
            "82fa6d4e",
            "2679e4de",
            "abff1a0c",
            "48cd76ec",
            "d11a4c18",
        ),
        5: _sha256_fixture(
            "aff449e3",
            "e17dd339",
            "1e6a4788",
            "7ca8717b",
            "ce36f216",
            "e5e7a753",
            "21f6eb22",
            "0eb5b0bc",
        ),
    }

    series = discover_migrations()

    assert {item.version: item.sha256 for item in series} == expected


def test_wp13_migration_working_tree_eol_is_repository_pinned() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "omni_cio/persistence/migrations/*.sql text eol=lf" in attributes


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
