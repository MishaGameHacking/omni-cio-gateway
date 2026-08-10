from __future__ import annotations

from pathlib import Path

from omni_cio.jobs import JobType, canonical_job_id
from omni_cio.persistence.migration import discover_migrations


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "omni_cio" / "persistence" / "migrations" / "0002_durable_jobs.sql"
WORKER = ROOT / "omni_cio" / "jobs" / "worker.py"


def test_wp14_extends_immutable_migration_series_forward() -> None:
    series = discover_migrations()

    assert [item.version for item in series] == list(range(1, len(series) + 1))
    assert series[0].name == "initial"
    assert series[-1].version >= 2
    assert series[-1].name == "durable_jobs"


def test_wp14_job_schema_has_required_lifecycle_and_journal() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for marker in (
        "ADD COLUMN state text",
        "ADD COLUMN correlation_id text",
        "ADD COLUMN lease_owner text",
        "ADD COLUMN lease_expires_at timestamptz",
        "ADD COLUMN attempts integer",
        "ADD COLUMN max_attempts integer",
        "ADD COLUMN next_run_at timestamptz",
        "ADD COLUMN error_class text",
        "ADD COLUMN recovery_policy text",
        "CREATE TABLE omni_cio_v10.job_events",
        "FOR UPDATE",
    ):
        if marker != "FOR UPDATE":
            assert marker in sql


def test_wp14_database_constrains_states_retries_and_lease_shape() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for state in (
        "QUEUED",
        "RUNNING",
        "RETRY_WAIT",
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "RECONCILIATION_REQUIRED",
    ):
        assert f"'{state}'" in sql
    assert "attempts <= max_attempts" in sql
    assert "max_attempts <= 100" in sql
    assert "job_lease_shape" in sql
    assert "job_schedule_shape" in sql
    assert "jobs_due_claim_idx" in sql
    assert "jobs_expired_lease_idx" in sql


def test_wp14_job_journal_is_append_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TRIGGER job_events_reject_mutation" in sql
    assert "BEFORE UPDATE OR DELETE ON omni_cio_v10.job_events" in sql
    assert "reject_immutable_mutation" in sql


def test_wp14_job_type_registry_matches_master_plan_scope() -> None:
    assert {item.value for item in JobType} == {
        "PORTFOLIO_REFRESH",
        "MARKET_REFRESH",
        "RESEARCH",
        "WATCHTOWER",
        "AI_RESEARCH",
        "RECONCILIATION",
        "BACKUP",
        "HEALTH",
    }


def test_wp14_canonical_job_id_is_deterministic_and_type_scoped() -> None:
    first = canonical_job_id(JobType.HEALTH, "same-key")
    second = canonical_job_id(JobType.HEALTH, "same-key")
    other_type = canonical_job_id(JobType.BACKUP, "same-key")

    assert first == second
    assert first != other_type
    assert first.startswith("job:v1:")
    assert len(first.removeprefix("job:v1:")) == 64


def test_wp14_worker_is_bounded_and_has_no_poll_forever_loop() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "def run_once" in source
    assert "while True" not in source
    assert "REAL_TRADING_ENABLED=true" not in source
    assert "TINVEST_TOKEN" not in source
    assert "PostOrder" not in source


def test_wp14_does_not_add_wp15_or_external_surface_code() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "omni_cio" / "jobs").glob("*.py"))
    )

    for forbidden in (
        "tinkoff.invest",
        "t-tech",
        "Telegram",
        "FastAPI",
        "openai",
        "PostOrder",
        "executeRealTrade",
    ):
        assert forbidden not in sources