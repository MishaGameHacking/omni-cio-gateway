"""Durable refresh concurrency/recovery against isolated native PostgreSQL."""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_intelligence import news_item
from test_observer import LEGAL_VERSIONS, USER_ID, FakeBroker, bundle
from test_workspace_postgres import user, workspace_database_context
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.broker import BrokerService
from omnicio.db import Database
from omnicio.intelligence import build_news_evidence
from omnicio.observer import PortfolioObserver, PortfolioRefreshCoordinator
from omnicio.portfolio import analyze_portfolio, value_current_positions
from omnicio.portfolio_store import ObservationCancelled, PortfolioStore
from omnicio.tbank import TBankInvestClient, TBankUnavailable
from omnicio.workspace_store import WorkspaceStore

pytestmark = pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required",
)
REFRESH_MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "0016_portfolio_refresh.sql"
)


@pytest.fixture
def isolated_workspace_database() -> Iterator[tuple[Database, str, str]]:
    # Replaying an older migration changes its then-current constraints. Keep
    # that historical-schema exercise separate from latest-schema runtime tests.
    with workspace_database_context() as database:
        yield database


@pytest.fixture
def populated_migration_owner() -> Iterator[psycopg.Connection[Any]]:
    """Migrate as the restricted table owner, not the fixture administrator."""
    admin_url = os.environ["OMNICIO_TEST_DATABASE_URL"]
    config = conninfo_to_dict(admin_url)
    assert config.get("host") in {"127.0.0.1", "localhost", "::1"}
    database_name = config.get("dbname")
    assert isinstance(database_name, str)
    assert database_name.endswith("_test")
    schema = "refresh_owner_" + secrets.token_hex(6)
    role, password = schema + "_role", secrets.token_urlsafe(32)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
        admin.execute(sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        ).format(sql.Identifier(role), sql.Literal(password)))
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
            sql.Identifier(schema), sql.Identifier(role),
        ))
    config.update(user=role, password=password, options=f"-c search_path={schema},public")
    try:
        with psycopg.connect(make_conninfo("", **config), autocommit=True) as connection:
            for path in sorted(REFRESH_MIGRATION.parent.glob("*.sql")):
                if path < REFRESH_MIGRATION:
                    connection.execute(path.read_text(encoding="utf-8"))
            yield connection
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def _seed_migration_history(connection: psycopg.Connection[Any], *, candidate: bool) -> list[UUID]:
    tenants = [uuid4(), uuid4()]
    if candidate:
        connection.execute("ALTER TABLE job_runs ADD COLUMN requested_at timestamptz")
        connection.execute(
            "ALTER TABLE job_runs DROP CONSTRAINT job_runs_user_id_job_type_scheduled_for_key"
        )
        connection.execute(
            "CREATE UNIQUE INDEX job_runs_daily_identity_idx "
            "ON job_runs (user_id, job_type, scheduled_for) WHERE job_type <> 'portfolio_refresh'"
        )
    for tenant, status in zip(tenants, ("active", "blocked"), strict=True):
        with connection.transaction():
            connection.execute("INSERT INTO users (id, status) VALUES (%s, %s)", (tenant, status))
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(tenant),))
            job = connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, attempt, "
                "started_at, finished_at, details) VALUES (%s, 'portfolio_daily', '2026-10-01', "
                "'succeeded', 2, '2026-10-01 03:15:00+00', '2026-10-01 03:16:00+00', "
                "'{\"history_status\":\"complete\"}'::jsonb) RETURNING id", (tenant,),
            ).fetchone()
            assert job is not None
            connection.execute(
                "INSERT INTO portfolio_snapshots (user_id, job_run_id, account_id, environment, "
                "captured_at, analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, "
                "limits_loading_in_progress, evidence) VALUES (%s, %s, 'old-account', 'prod', "
                "'2026-10-01 03:16:00+00', 'observed', 123, 23, 0, false, '{}'::jsonb)",
                (tenant, job[0]),
            )
            if candidate:
                connection.execute(
                    "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, "
                    "started_at, requested_at) VALUES (%s, 'portfolio_refresh', '2026-10-02', "
                    "'running', '2026-10-02 10:01:00+00', '2026-10-02 10:00:00+00')", (tenant,),
                )
    return tenants


def _migration_history(connection: psycopg.Connection[Any], tenants: list[UUID]) -> list[Any]:
    rows = []
    for tenant in tenants:
        with connection.transaction():
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(tenant),))
            rows.extend(connection.execute(
                "SELECT job.id, job.user_id, job.job_type, job.status, job.attempt, "
                "job.started_at, job.finished_at, job.details, snapshot.id, snapshot.nav_rub "
                "FROM job_runs job LEFT JOIN portfolio_snapshots snapshot "
                "ON snapshot.job_run_id = job.id ORDER BY job.id"
            ).fetchall())
    return rows


def _assert_owner_rls(connection: psycopg.Connection[Any]) -> None:
    properties = connection.execute(
        "SELECT role.rolsuper, role.rolbypassrls, table_info.relowner = role.oid, "
        "table_info.relrowsecurity, table_info.relforcerowsecurity "
        "FROM pg_roles role JOIN pg_class table_info ON table_info.oid = 'job_runs'::regclass "
        "WHERE role.rolname = current_user"
    ).fetchone()
    assert properties == (False, False, True, True, True)


@pytest.mark.parametrize("candidate", [False, True], ids=["accepted_daily", "early_refresh"])
@pytest.mark.parametrize("prior_tenant", [False, True], ids=["empty_context", "existing_context"])
def test_native_refresh_backfills_populated_restricted_owner_and_preserves_context(
    populated_migration_owner: psycopg.Connection[Any], candidate: bool, prior_tenant: bool,
) -> None:
    connection = populated_migration_owner
    tenants = _seed_migration_history(connection, candidate=candidate)
    original = _migration_history(connection, tenants)
    context = str(tenants[0]) if prior_tenant else ""
    connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (context,))
    _assert_owner_rls(connection)
    migration = REFRESH_MIGRATION.read_text(encoding="utf-8")
    before_commit, suffix = migration.rsplit("COMMIT;", 1)
    assert not suffix.strip()
    # Check inside the real migration transaction: COMMIT itself resets SET LOCAL
    # and would otherwise hide a missing restoration at the end of the tenant loop.
    for _attempt in range(2):
        connection.execute(before_commit)
        restored_context = connection.execute(
            "SELECT current_setting('omnicio.user_id', true)"
        ).fetchone()
        assert restored_context == (context,)
        _assert_owner_rls(connection)
        connection.execute("COMMIT")
        assert _migration_history(connection, tenants) == original
    for tenant in tenants:
        with connection.transaction():
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(tenant),))
            daily = connection.execute(
                "SELECT scheduled_for, requested_at, started_at FROM job_runs "
                "WHERE job_type = 'portfolio_daily'"
            ).fetchall()
            assert len(daily) == 1
            assert daily[0][0] == date(2026, 10, 1)
            assert daily[0][1] == daily[0][2]
            assert connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status) "
                "VALUES (%s, 'portfolio_daily', '2026-10-01', 'running') "
                "ON CONFLICT (user_id, job_type, scheduled_for) DO NOTHING RETURNING id",
                (tenant,),
            ).fetchone() is None
            refresh = connection.execute(
                "SELECT scheduled_for, requested_at FROM job_runs "
                "WHERE job_type = 'portfolio_refresh'"
            ).fetchall()
            expected = [(None, datetime(2026, 10, 2, 10, tzinfo=UTC))] if candidate else []
            assert refresh == expected
    connection.execute("SELECT set_config('omnicio.user_id', '', false)")
    assert connection.execute("SELECT id FROM job_runs").fetchall() == []
    _assert_owner_rls(connection)


def test_native_refresh_backfill_failure_rolls_back_schema_rows_and_tenant_context(
    populated_migration_owner: psycopg.Connection[Any],
) -> None:
    connection = populated_migration_owner
    tenants = _seed_migration_history(connection, candidate=False)
    original = _migration_history(connection, tenants)
    context = str(tenants[0])
    connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (context,))
    connection.execute("ALTER TABLE job_runs ADD COLUMN requested_at timestamptz")
    connection.execute(
        "ALTER TABLE job_runs ADD CONSTRAINT fixture_reject_backfill CHECK (requested_at IS NULL)"
    )
    migration = REFRESH_MIGRATION.read_text(encoding="utf-8")
    with pytest.raises(psycopg.errors.CheckViolation, match="fixture_reject_backfill"):
        connection.execute(migration)
    connection.execute("ROLLBACK")
    restored_context = connection.execute(
        "SELECT current_setting('omnicio.user_id', true)"
    ).fetchone()
    assert restored_context == (context,)
    original_not_null = connection.execute(
        "SELECT attnotnull FROM pg_attribute "
        "WHERE attrelid = 'job_runs'::regclass AND attname = 'scheduled_for'"
    ).fetchone()
    assert original_not_null == (True,)
    assert _migration_history(connection, tenants) == original
    _assert_owner_rls(connection)
    connection.execute("ALTER TABLE job_runs DROP CONSTRAINT fixture_reject_backfill")
    connection.execute(migration)
    assert _migration_history(connection, tenants) == original


def test_background_migration_preserves_populated_owner_rows_context_and_older_writers(
    populated_migration_owner: psycopg.Connection[Any],
) -> None:
    connection = populated_migration_owner
    background = REFRESH_MIGRATION.parent / "0024_background_reliability.sql"
    for path in sorted(REFRESH_MIGRATION.parent.glob("*.sql")):
        if REFRESH_MIGRATION <= path < background:
            connection.execute(path.read_text(encoding="utf-8"))
    tenants = (uuid4(), uuid4())
    created = datetime(2026, 10, 1, 3, tzinfo=UTC)
    accepted = created + timedelta(hours=1)
    finished = created + timedelta(hours=2)
    for tenant, status in zip(tenants, ("active", "blocked"), strict=True):
        with connection.transaction():
            connection.execute("INSERT INTO users (id, status) VALUES (%s, %s)", (tenant, status))
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(tenant),))
            channel = connection.execute(
                "INSERT INTO notification_channels (user_id, kind, destination_hash, "
                "destination_ciphertext, label, status, verified_at, digest_period) "
                "VALUES (%s, 'email', %s, %s, 'Synthetic', 'active', %s, %s) RETURNING id",
                (tenant, "a" * 64, b"synthetic encrypted destination", created,
                 "daily:2026-10-02T00:00:00+00:00"),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO notification_outbox (user_id, channel_id, message_key, kind, "
                "payload_ciphertext, status, created_at, accepted_at) "
                "VALUES (%s, %s, 'historical', 'digest', %s, 'accepted', %s, %s)",
                (tenant, channel, b"synthetic encrypted payload", created, accepted),
            )
            connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, started_at, "
                "finished_at) VALUES (%s, 'portfolio_daily', '2026-10-01', 'degraded', %s, %s)",
                (tenant, created, finished),
            )
    previous = str(tenants[0])
    connection.execute("SELECT set_config('omnicio.user_id', %s, false)", (previous,))
    migration = background.read_text(encoding="utf-8")
    connection.execute(migration)
    connection.execute(migration)
    assert connection.execute("SELECT current_setting('omnicio.user_id', true)").fetchone() \
        == (previous,)
    protection = connection.execute(
        "SELECT r.rolsuper, r.rolbypassrls, t.relrowsecurity, t.relforcerowsecurity "
        "FROM pg_roles r JOIN pg_class t ON t.relowner = r.oid "
        "WHERE r.rolname = current_user AND t.oid = 'notification_outbox_events'::regclass"
    ).fetchone()
    assert protection == (False, False, True, True)
    for tenant in tenants:
        with connection.transaction():
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(tenant),))
            row = connection.execute(
                "SELECT o.updated_at, o.status, c.digest_period, c.digest_cursor_at "
                "FROM notification_outbox o JOIN notification_channels c "
                "ON c.user_id = o.user_id AND c.id = o.channel_id WHERE o.user_id = %s",
                (tenant,),
            ).fetchone()
            assert row == (accepted, "accepted", "daily:2026-10-02T00:00:00+00:00", None)
            assert connection.execute(
                "SELECT next_attempt_at FROM job_runs WHERE user_id = %s", (tenant,),
            ).fetchone() == (finished + timedelta(minutes=5),)
            assert connection.execute("SELECT count(*) FROM notification_outbox_events") \
                .fetchone() == (0,)
            # Accepted 1.1.0 writers omit both new timestamp columns. Defaults
            # must keep those inserts valid during deploy overlap or rollback.
            outbox = connection.execute(
                "INSERT INTO notification_outbox (user_id, channel_id, message_key, kind, "
                "payload_ciphertext) SELECT user_id, id, 'older-writer', 'event', %s "
                "FROM notification_channels WHERE user_id = %s RETURNING updated_at",
                (b"synthetic encrypted payload", tenant),
            ).fetchone()
            assert outbox[0] is not None
            job = connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status) "
                "VALUES (%s, 'portfolio_daily', '2026-10-02', 'running') "
                "ON CONFLICT (user_id, job_type, scheduled_for) DO NOTHING "
                "RETURNING next_attempt_at", (tenant,),
            ).fetchone()
            assert job[0] is not None


def owner(database: Database) -> UUID:
    ident = user(database, account=True)
    with database.pool.connection() as connection:
        connection.execute(
            "INSERT INTO vkid_identities (user_id, vk_user_id) VALUES (%s, %s)",
            (ident, str(ident.int)),
        )
        for document, version in LEGAL_VERSIONS.items():
            connection.execute(
                "INSERT INTO legal_acceptances "
                "(user_id, document_type, document_version, client_ip_hash) VALUES (%s,%s,%s,%s)",
                (ident, document, version, b"i" * 32),
            )
    return ident


def age_request(database: Database, ident: UUID) -> None:
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        connection.execute(
            "UPDATE job_runs SET requested_at = requested_at - interval '121 seconds' "
            "WHERE user_id = %s AND job_type = 'portfolio_refresh'", (ident,),
        )


def _accepted_daily_insert(database: Database, ident: UUID, day: date) -> dict[str, Any] | None:
    """Keep the accepted 5457ecb daily INSERT conflict target without a predicate."""
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        return connection.execute(
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, status) "
            "VALUES (%s, %s, %s, 'running') "
            "ON CONFLICT (user_id, job_type, scheduled_for) DO NOTHING "
            "RETURNING id, user_id, job_type, scheduled_for, status, attempt, "
            "started_at, finished_at",
            (ident, "portfolio_daily", day),
        ).fetchone()


def test_native_refresh_preserves_accepted_daily_insert_and_reader_during_rollback(
    isolated_workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_url, schema = isolated_workspace_database
    ident, store, day = owner(database), PortfolioStore(database), date.today()
    daily = _accepted_daily_insert(database, ident, day)
    assert daily is not None
    assert daily["scheduled_for"].isoformat() == day.isoformat()
    assert _accepted_daily_insert(database, ident, day) is None
    assert store.finish_job(ident, daily["id"], status="succeeded", details={})

    queued = store.request_refresh(ident, LEGAL_VERSIONS)
    with store.observer_lock() as locked:
        assert locked
        manual = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert manual is not None
        assert manual.scheduled_for is None
        assert store.finish_job(ident, manual.id, status="degraded", details={})
    alert = next(item for item in WorkspaceStore(database).events(ident)["items"]
                 if item["kind"] == "synchronization")
    assert alert["source"]["scheduled_for"] is None
    assert alert["source"]["requested_at"] == queued["requested_at"]

    age_request(database, ident)
    next_request = store.request_refresh(ident, LEGAL_VERSIONS)
    assert next_request["job_id"] != str(manual.id)
    with store.observer_lock() as locked:
        assert locked
        following = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert following is not None
        assert following.scheduled_for is None
        assert store.finish_job(ident, following.id, status="succeeded", details={})
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        admin.execute(REFRESH_MIGRATION.read_text(encoding="utf-8"))
    assert _accepted_daily_insert(database, ident, day) is None
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        legacy = connection.execute(
            "SELECT id, scheduled_for FROM job_runs WHERE user_id = %s "
            "AND job_type = 'portfolio_daily' AND scheduled_for = %s", (ident, day),
        ).fetchall()
        manual_dates = connection.execute(
            "SELECT scheduled_for FROM job_runs "
            "WHERE user_id = %s AND job_type = 'portfolio_refresh'", (ident,),
        ).fetchall()
    assert [row["id"] for row in legacy] == [daily["id"]]
    assert legacy[0]["scheduled_for"].isoformat() == day.isoformat()
    assert [row["scheduled_for"] for row in manual_dates] == [None, None]


@pytest.mark.parametrize("job_type, scheduled_for", [
    ("portfolio_daily", None), ("portfolio_refresh", date.today()),
])
def test_native_job_schedule_check_preserves_daily_dates_and_unscheduled_refreshes(
    workspace_database: tuple[Database, str, str], job_type: str, scheduled_for: date | None,
) -> None:
    database = workspace_database[0]
    ident = owner(database)
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        with pytest.raises(
            psycopg.errors.CheckViolation, match="job_runs_schedule_kind_consistent",
        ), connection.transaction():
            connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status) "
                "VALUES (%s, %s, %s, 'running')", (ident, job_type, scheduled_for),
            )


def test_native_active_refresh_guard_applies_when_scheduled_dates_are_null(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    ident = owner(database)
    PortfolioStore(database).request_refresh(ident, LEGAL_VERSIONS)
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        with pytest.raises(
            psycopg.errors.UniqueViolation, match="job_runs_refresh_active_idx",
        ), connection.transaction():
            connection.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status) "
                "VALUES (%s, 'portfolio_refresh', NULL, 'queued')", (ident,),
            )


def test_native_refresh_migration_recovers_earlier_candidate_without_losing_job_lineage(
    isolated_workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_url, schema = isolated_workspace_database
    ident, store = owner(database), PortfolioStore(database)
    day = date.today()
    daily = _accepted_daily_insert(database, ident, day)
    assert daily is not None
    queued = store.request_refresh(ident, LEGAL_VERSIONS)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        original = admin.execute(
            "SELECT id, job_type, status, requested_at, started_at, details FROM job_runs "
            "WHERE user_id = %s ORDER BY id", (ident,),
        ).fetchall()
        # Reproduce the unreleased candidate's schema using only synthetic rows.
        admin.execute("ALTER TABLE job_runs DROP CONSTRAINT job_runs_schedule_kind_consistent")
        admin.execute(
            "ALTER TABLE job_runs DROP CONSTRAINT job_runs_user_id_job_type_scheduled_for_key"
        )
        admin.execute(
            "UPDATE job_runs SET scheduled_for = "
            "(requested_at AT TIME ZONE 'Europe/Moscow')::date "
            "WHERE job_type = 'portfolio_refresh'"
        )
        admin.execute("ALTER TABLE job_runs ALTER COLUMN scheduled_for SET NOT NULL")
        admin.execute(
            "CREATE UNIQUE INDEX job_runs_daily_identity_idx "
            "ON job_runs (user_id, job_type, scheduled_for) WHERE job_type <> 'portfolio_refresh'"
        )
        admin.execute(REFRESH_MIGRATION.read_text(encoding="utf-8"))
        restored = admin.execute(
            "SELECT id, job_type, status, requested_at, started_at, details FROM job_runs "
            "WHERE user_id = %s ORDER BY id", (ident,),
        ).fetchall()
    assert restored == original
    assert _accepted_daily_insert(database, ident, day) is None
    state = store.refresh_status(ident)
    assert state["job_id"] == queued["job_id"]
    assert state["requested_at"] == queued["requested_at"]
    with store.observer_lock() as locked:
        assert locked
        manual = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert manual is not None
        assert manual.scheduled_for is None


def test_native_manual_refresh_is_not_daily_success_and_cooldown_is_durable(
    isolated_workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_url, schema = isolated_workspace_database
    store, ident = PortfolioStore(database), owner(database)
    earlier = datetime.now(UTC) - timedelta(hours=1)
    observation = replace(bundle(), account_id=str(ident), refreshed_at=earlier)
    daily = store.claim_daily_job(ident, job_type="portfolio_daily", scheduled_for=date.today(),
                                  legal_versions=LEGAL_VERSIONS)
    assert daily is not None
    old_snapshot = store.save_snapshot(ident, job_run_id=daily.id, bundle=observation)
    assert store.finish_job(ident, daily.id, status="succeeded", details={})
    initial = store.refresh_status(ident)
    assert initial["status"] == "idle"
    assert initial["snapshot_saved"] is False
    queued = store.request_refresh(ident, LEGAL_VERSIONS)
    assert queued["status"] == "queued"
    assert queued["job_id"] != str(daily.id)
    assert queued["started_at"] is None
    assert store.request_refresh(ident, LEGAL_VERSIONS)["job_id"] == queued["job_id"]
    # Reapplying the additive migration preserves old snapshots and queued work.
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        admin.execute(REFRESH_MIGRATION.read_text(encoding="utf-8"))
    with store.observer_lock() as locked:
        assert locked
        manual = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert manual is not None
        now = datetime.now(UTC)
        fresh = store.save_snapshot(
            ident, job_run_id=manual.id, bundle=replace(observation, refreshed_at=now),
        )
        assert fresh != old_snapshot
        assert store.finish_job(
            ident, manual.id, status="succeeded", details={"history_status": "complete"},
        )
    state = store.refresh_status(ident)
    assert state["status"] == "succeeded"
    assert state["snapshot_saved"] is True
    assert datetime.fromisoformat(state["observed_at"]) == now
    assert state["history_status"] == "complete"
    assert state["can_refresh"] is False
    assert store.request_refresh(ident, LEGAL_VERSIONS)["reason"] == "refresh_cooldown"
    age_request(database, ident)
    assert store.refresh_status(ident)["can_refresh"] is True
    assert store.request_refresh(ident, LEGAL_VERSIONS)["job_id"] != str(manual.id)
    assert store.claim_daily_job(
        ident, job_type="portfolio_daily", scheduled_for=date.today(),
        legal_versions=LEGAL_VERSIONS,
    ) is None


def test_native_refresh_concurrency_and_rls_allow_only_one_pending_owner_job(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident, other = PortfolioStore(database), owner(database), owner(database)
    with ThreadPoolExecutor(max_workers=4) as workers:
        queued = list(workers.map(lambda _: store.request_refresh(ident, LEGAL_VERSIONS), range(4)))
    assert len({row["job_id"] for row in queued}) == 1
    assert store.refresh_status(other)["status"] == "idle"
    with store.observer_lock() as locked:
        assert locked
        assert store.claim_refresh_job(other, LEGAL_VERSIONS) is None
        claimed = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert claimed is not None
        observation = replace(bundle(), account_id=str(ident))
        with pytest.raises(ObservationCancelled):
            store.save_snapshot(other, job_run_id=claimed.id, bundle=observation)
        with PortfolioStore(database).observer_lock() as competing:
            assert not competing
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        hidden = connection.execute(
            "SELECT id FROM job_runs WHERE id = %s", (claimed.id,),
        ).fetchone()
        assert hidden is None



def test_native_unknown_valuation_preserves_real_quantity_sql_nulls_and_tenant_isolation(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident, other = PortfolioStore(database), owner(database), owner(database)
    # A real current-position response can precede both price discovery and
    # completion of the broker's cash limits; that is not an empty portfolio.
    payload = {
        "accountId": str(ident),
        "limitsLoadingInProgress": True,
        "money": [],
        "blocked": [],
        "securities": [{
            "instrumentUid": "native-unpriced-share", "instrumentType": "share",
            "balance": "17", "blocked": "3", "exchangeBlocked": False,
        }],
    }
    with patch.object(TBankInvestClient, "_post", return_value=payload):
        positions = TBankInvestClient().get_positions("synthetic-token", "prod", str(ident))
    portfolio = value_current_positions(positions, (), ())
    observation = replace(
        bundle(), account_id=str(ident), refreshed_at=datetime.now(UTC),
        portfolio=portfolio, positions=positions,
        analysis=analyze_portfolio(portfolio, positions, ()), metadata=(), sources=(),
    )
    job = store.claim_daily_job(
        ident, job_type="portfolio_daily", scheduled_for=date.today(),
        legal_versions=LEGAL_VERSIONS,
    )
    assert job is not None
    snapshot_id = store.save_snapshot(ident, job_run_id=job.id, bundle=observation)
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(other, job_run_id=job.id, bundle=observation)
    assert store.finish_job(ident, job.id, status="degraded", details={})

    with database.pool.connection() as connection, connection.transaction():
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        row = connection.execute(
            "SELECT s.nav_rub, s.rub_cash_total, s.rub_cash_blocked, s.rub_cash_unblocked, "
            "p.quantity, p.quantity_lots, p.blocked_lots, p.current_price_value, p.value_rub "
            "FROM portfolio_snapshots s JOIN portfolio_snapshot_positions p "
            "ON p.snapshot_id = s.id WHERE s.id = %s", (snapshot_id,),
        ).fetchone()
        assert row is not None
        assert row["quantity"] == Decimal("20")
        assert row["blocked_lots"] == Decimal("3")
        assert all(row[key] is None for key in (
            "nav_rub", "rub_cash_total", "rub_cash_blocked", "rub_cash_unblocked",
            "quantity_lots", "current_price_value", "value_rub",
        ))
        # Use the same restricted runtime connection, without a user_id WHERE
        # clause, so these reads demonstrate PostgreSQL RLS itself.
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        assert connection.execute(
            "SELECT id FROM portfolio_snapshots WHERE id = %s", (snapshot_id,),
        ).fetchall() == []
        assert connection.execute(
            "SELECT quantity FROM portfolio_snapshot_positions WHERE snapshot_id = %s",
            (snapshot_id,),
        ).fetchall() == []

    latest = store.portfolio_visualization(ident)["latest"]
    assert latest is not None
    assert latest["nav_rub"] is None
    assert latest["rub_cash_unblocked"] is None
    assert latest["positions"][0]["quantity"] == Decimal("20")
    assert latest["positions"][0]["value_rub"] is None
    assert store.portfolio_visualization(other) == {
        "status": "pending", "history": [], "latest": None,
    }


def test_native_restart_uses_new_snapshot_lineage_without_broker_history(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    requested = store.request_refresh(ident, LEGAL_VERSIONS)
    now = datetime.now(UTC)
    observation = replace(bundle(), account_id=str(ident), refreshed_at=now)
    with store.observer_lock() as locked:
        assert locked
        first = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert first is not None
        old_snapshot = store.save_snapshot(ident, job_run_id=first.id, bundle=observation)
    # Simulate process loss after persisted facts but before finish_job.
    restarted = PortfolioStore(database)
    with restarted.observer_lock() as locked:
        assert locked
        second = restarted.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert second is not None
        assert second.id != first.id
        assert second.attempt == 2
        new_snapshot = restarted.save_snapshot(
            ident,
            job_run_id=second.id,
            bundle=replace(observation, refreshed_at=now + timedelta(seconds=1)),
        )
        assert new_snapshot != old_snapshot
        third = restarted.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert third is not None
        assert third.attempt == 3
        assert restarted.claim_refresh_job(ident, LEGAL_VERSIONS) is None
    state = restarted.refresh_status(ident)
    assert state["requested_at"] == requested["requested_at"]
    assert state["status"] == "failed"
    assert state["reason"] == "worker_interrupted"
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        snapshots = connection.execute(
            "SELECT id FROM portfolio_snapshots WHERE user_id = %s",
            (ident,),
        ).fetchall()
    assert {row["id"] for row in snapshots} == {old_snapshot, new_snapshot}


def _monitoring_broker(ident: UUID) -> Mock:
    fake, broker = FakeBroker(), Mock(spec=BrokerService)
    broker.revalidate_account.return_value = replace(
        fake.revalidate_account(USER_ID),
        id=str(ident),
    )
    broker.user_info.side_effect = AssertionError("broker profile is outside read scope")
    broker.observation_bundle.side_effect = lambda *_args, **_kwargs: replace(
        bundle(),
        account_id=str(ident),
        refreshed_at=datetime.now(UTC),
    )
    broker.evidence.side_effect = lambda _user, value, **kwargs: fake.evidence(
        USER_ID,
        replace(value, account_id="account-1"),
        **kwargs,
    )
    broker.history_page.side_effect = AssertionError("broker history is outside read scope")
    return broker


def _age_monitoring_attempts(database: Database, ident: UUID, minutes: int) -> None:
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        connection.execute(
            "UPDATE job_runs SET requested_at = requested_at - make_interval(mins => %s), "
            "started_at = started_at - make_interval(mins => %s), "
            "finished_at = finished_at - make_interval(mins => %s) WHERE user_id = %s",
            (minutes, minutes, minutes, ident),
        )


def test_native_continuous_worker_refreshes_without_browser_and_keeps_durable_cadence(
    isolated_workspace_database: tuple[Database, str, str],
) -> None:
    database = isolated_workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    broker = _monitoring_broker(ident)
    worker = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert worker.run_pending()
    first = store.refresh_status(ident)
    assert first["status"] == "succeeded"
    assert first["scope"] == "full"
    assert first["snapshot_saved"] is True
    restarted = PortfolioRefreshCoordinator(
        PortfolioStore(database), broker, legal_versions=LEGAL_VERSIONS,
    )
    assert not restarted.run_pending()
    assert broker.observation_bundle.call_count == 1

    _age_monitoring_attempts(database, ident, 6)
    assert restarted.run_pending()
    quick = store.refresh_status(ident)
    assert quick["scope"] == "quick"
    assert quick["status"] == "succeeded"
    assert quick["job_id"] != first["job_id"]
    assert broker.evidence.call_count == 1
    assert broker.observation_bundle.call_args.kwargs == {"quick": True}
    assert not restarted.run_pending()

    _age_monitoring_attempts(database, ident, 61)
    assert restarted.run_pending()
    assert store.refresh_status(ident)["scope"] == "full"
    assert broker.evidence.call_count == 2
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        jobs = connection.execute(
            "SELECT details->>'trigger' AS trigger FROM job_runs WHERE user_id = %s", (ident,),
        ).fetchall()
    assert len(jobs) == 3
    assert all(row["trigger"] == "automatic" for row in jobs)


def test_native_automatic_provider_failure_is_throttled_across_restart(
    isolated_workspace_database: tuple[Database, str, str],
) -> None:
    database = isolated_workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    broker = _monitoring_broker(ident)
    broker.revalidate_account.side_effect = TBankUnavailable("synthetic outage")
    worker = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    with patch("omnicio.observer.time.sleep"):
        assert worker.run_pending()
    failed = store.refresh_status(ident)
    assert failed["status"] == "degraded"
    assert failed["snapshot_saved"] is False
    assert failed["observed_at"] is None
    attempts = broker.revalidate_account.call_count
    assert not PortfolioRefreshCoordinator(
        PortfolioStore(database), broker, legal_versions=LEGAL_VERSIONS,
    ).run_pending()
    assert broker.revalidate_account.call_count == attempts
    _age_monitoring_attempts(database, ident, 6)
    assert worker.run_pending()
    assert store.refresh_status(ident)["scope"] == "quick"
    assert broker.revalidate_account.call_count == attempts + 1


@pytest.mark.parametrize("revocation", ["consent", "blocked", "disconnect"])
def test_native_automatic_admission_requires_current_owner_connection_and_consent(
    workspace_database: tuple[Database, str, str], revocation: str,
) -> None:
    database = workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    if revocation == "disconnect":
        assert database.delete_tbank_connection(ident)
    else:
        with database.pool.connection() as connection:
            if revocation == "consent":
                connection.execute("DELETE FROM legal_acceptances WHERE user_id = %s", (ident,))
            else:
                connection.execute("UPDATE users SET status = 'blocked' WHERE id = %s", (ident,))
    with store.observer_lock(ident) as locked:
        assert locked
        assert store.claim_refresh_job(ident, LEGAL_VERSIONS, schedule_if_due=True) is None
    with database.pool.connection() as connection:
        connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        assert connection.execute(
            "SELECT id FROM job_runs WHERE user_id = %s", (ident,),
        ).fetchall() == []


def test_native_explicit_full_refresh_upgrades_queued_quick_without_duplicate_job(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    queued = store.request_refresh(ident, LEGAL_VERSIONS, scope="quick")
    upgraded = store.request_refresh(ident, LEGAL_VERSIONS, scope="full")
    assert upgraded["job_id"] == queued["job_id"]
    assert upgraded["scope"] == "full"
    with store.observer_lock(ident) as locked:
        assert locked
        claimed = store.claim_refresh_job(ident, LEGAL_VERSIONS, schedule_if_due=True)
        assert claimed is not None
        assert claimed.refresh_scope == "full"
        with PortfolioStore(database).observer_lock(ident) as competing:
            assert not competing


def test_native_refresh_never_resumes_legacy_broker_history(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    captured = datetime.now(UTC) - timedelta(seconds=1)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        conn.execute(
            "INSERT INTO broker_sync_state (user_id, account_id, pending_cursor, "
            "history_window_from, history_window_to) VALUES (%s, %s, 'legacy-cursor', %s, %s)",
            (ident, str(ident), captured - timedelta(days=1), captured),
        )
    broker = _monitoring_broker(ident)
    broker.observation_bundle.side_effect = lambda *_args, **_kwargs: replace(
        bundle(), account_id=str(ident), refreshed_at=captured
    )
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
    store.request_refresh(ident, LEGAL_VERSIONS)
    with store.observer_lock() as locked:
        assert locked
        job = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert job is not None
        outcome = observer.run_job(job, now=datetime.now(UTC))
    assert outcome.snapshot_saved
    broker.user_info.assert_not_called()
    broker.history_page.assert_not_called()
    assert store.refresh_status(ident)["history_status"] == "not_collected"
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(ident),))
        assert (
            conn.execute(
                "SELECT pending_cursor FROM broker_sync_state WHERE user_id=%s", (ident,)
            ).fetchone()["pending_cursor"]
            == "legacy-cursor"
        )


@pytest.mark.parametrize("change", ["credential", "consent", "disconnect", "delete"])
def test_native_refresh_cannot_persist_after_authority_or_connection_revocation(
    workspace_database: tuple[Database, str, str], change: str,
) -> None:
    database = workspace_database[0]
    store, ident = PortfolioStore(database), owner(database)
    store.request_refresh(ident, LEGAL_VERSIONS)
    with store.observer_lock() as locked:
        assert locked
        job = store.claim_refresh_job(ident, LEGAL_VERSIONS)
        assert job is not None
    if change == "credential":
        database.upsert_tbank_connection(
            user_id=ident, account_id=str(ident), account_name="Synthetic", environment="prod",
            encrypted_credential=b"synthetic-replacement", terms_version="test",
        )
    elif change == "consent":
        with database.pool.connection() as connection:
            connection.execute(
                "DELETE FROM legal_acceptances WHERE user_id = %s AND document_type = 'terms'",
                (ident,),
            )
    elif change == "disconnect":
        assert database.delete_tbank_connection(ident)
    else:
        # This fixture has a synthetic VK identity and uses the real deletion boundary.
        assert database.delete_user_account(ident)
    observation = replace(bundle(), account_id=str(ident))
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(ident, job_run_id=job.id, bundle=observation)
    assert not store.finish_job(ident, job.id, status="succeeded", details={})
    store.fail_refresh_job(ident, job.id, "observation_interrupted")
    state = store.refresh_status(ident)
    assert state["snapshot_saved"] is False
    if change in {"disconnect", "delete"}:
        assert state["status"] == "not_connected"
        assert state["job_id"] is None
    if change == "consent":
        denied = store.request_refresh(ident, LEGAL_VERSIONS)
        assert denied["can_refresh"] is False
        assert denied["reason"] == "consent_required"
    if change == "credential":
        replacement = store.request_refresh(ident, LEGAL_VERSIONS)
        assert replacement["status"] == "queued"
        assert replacement["job_id"] != str(job.id)


def test_native_news_page_checkpoint_is_atomic_resumable_and_connection_bound(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store, ident, other = PortfolioStore(database), owner(database), owner(database)
    store.request_refresh(ident, LEGAL_VERSIONS)
    job = store.claim_refresh_job(ident, LEGAL_VERSIONS)
    assert job is not None
    now = datetime.now(UTC)
    observation = replace(bundle(), account_id=str(ident), refreshed_at=now)
    snapshot = store.save_snapshot(ident, job_run_id=job.id, bundle=observation)
    news_id = str(uuid4().int % 10**18 + 1)
    documents = build_news_evidence(frozenset({"bond-uid"}), [news_item(news_id)], observed_at=now)
    continuations = [{"cursor": "10", "seen_cursors": []},
                     {"cursor": "20", "seen_cursors": ["30"]}]
    checkpoint = {"continuations": continuations, "completed_cursors": [], "status": "partial",
                  "observed_at": now.isoformat(), "pages": 1, "scanned_items": 1,
                  "documents_new": 0, "scope": "held_instrument_links"}
    arguments = {"job_run_id": job.id, "snapshot_id": snapshot, "documents": documents,
                 "assessments": (), "retrieved_at": now, "news_checkpoint": checkpoint}
    with (
        patch("omnicio.portfolio_store._save_source_retrieval",
              side_effect=RuntimeError("synthetic failed transaction")),
        pytest.raises(RuntimeError, match="failed transaction"),
    ):
        store.save_evidence(ident, **arguments)
    assert store.news_state(ident, job_run_id=job.id) == {}
    with database.pool.connection() as connection:
        assert connection.execute(
            "SELECT count(*) AS total FROM source_documents WHERE provider_key = %s", (news_id,),
        ).fetchone()["total"] == 0
    assert store.save_evidence(ident, **arguments) == (1, 0)
    saved = PortfolioStore(database).news_state(ident, job_run_id=job.id)
    assert saved["continuations"] == continuations
    assert saved["documents_new"] == 1
    visible = store.refresh_status(ident)["news"]
    assert visible["status"] == "partial"
    assert visible["documents_new"] == 1
    assert "cursor" not in visible
    assert "seen_cursors" not in visible
    assert "continuations" not in visible
    assert "completed_cursors" not in visible
    with pytest.raises(ObservationCancelled):
        store.news_state(other, job_run_id=job.id)
    assert store.finish_job(ident, job.id, status="succeeded", details={})
    age_request(database, ident)
    store.request_refresh(ident, LEGAL_VERSIONS)
    resumed = PortfolioStore(database).claim_refresh_job(ident, LEGAL_VERSIONS)
    assert resumed is not None
    assert store.news_state(ident, job_run_id=resumed.id)["continuations"] == continuations
    assert database.delete_tbank_connection(ident)
    with pytest.raises(ObservationCancelled):
        store.news_state(ident, job_run_id=resumed.id)
