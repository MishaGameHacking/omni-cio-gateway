from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_intelligence import _bundle as instrument_bundle
from test_intelligence import news_item

from omnicio.broker import AnalysisSource, BrokerEvidenceSnapshot, BrokerObservationBundle
from omnicio.db import BrokerConnectionConflict, Database
from omnicio.monitoring import (
    DAILY_MAX_ATTEMPTS,
    DAILY_RETRY_BASE_SECONDS,
    NEWS_MAX_COMPLETED_CURSORS,
    NEWS_MAX_CONTINUATIONS,
    NEWS_MAX_PATH_PROOFS,
)
from omnicio.observer import (
    ObservationInterrupted,
    PortfolioObserver,
    PortfolioRefreshCoordinator,
    _scheduled_day,
    provider_read,
)
from omnicio.portfolio import PortfolioAnalysis, analyze_portfolio
from omnicio.portfolio_store import (
    JobRunRecord,
    ObservationCancelled,
    PortfolioStore,
)
from omnicio.tbank import (
    TBankAccount,
    TBankInstrumentMetadata,
    TBankMoney,
    TBankOperationsPage,
    TBankPortfolio,
    TBankPortfolioPosition,
    TBankPositions,
    TBankUnavailable,
    TBankUserInfo,
)
from omnicio.workspace_store import WorkspaceStore

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
LEGAL_VERSIONS = {
    "privacy_policy": "2026-10-02-v6",
    "personal_data_consent": "2026-10-02-v6",
    "terms": "2026-10-02-v6",
}


def analysis(status: str = "observed") -> PortfolioAnalysis:
    return PortfolioAnalysis(
        status=status,
        nav_rub="1000",
        rub_cash_total="100",
        rub_cash_blocked="0",
        rub_cash_unblocked="100",
        security_count=0,
        valued_security_count=0,
        sector_coverage_percent=None,
        classes=(),
        sectors=(),
        securities=(),
        observations=(),
        valuation_status="complete" if status == "observed" else "unknown",
    )


def bundle(status: str = "observed") -> BrokerObservationBundle:
    refreshed = datetime(2026, 10, 2, 5, 0, tzinfo=UTC)
    return BrokerObservationBundle(
        account_id="account-1",
        account_name="Основной",
        environment="prod",
        refreshed_at=refreshed,
        portfolio=TBankPortfolio(
            total=TBankMoney("RUB", "1000"),
            expected_yield_percent="0",
            daily_yield=None,
            daily_yield_percent="0",
            asset_totals=(),
            positions=(),
        ),
        positions=TBankPositions(
            money=(TBankMoney("RUB", "100"),),
            blocked_money=(),
            limits_loading_in_progress=False,
        ),
        metadata=(),
        analysis=analysis(status),
        sources=(
            AnalysisSource(
                id="catalog",
                name="catalog",
                url="https://developer.tbank.ru/invest/api/instruments-service",
                methods=(),
                retrieved_at=refreshed,
                status="received",
            ),
        ),
    )


class FakeStore:
    def __init__(self) -> None:
        self.finished: list[tuple[str, dict[str, object]]] = []
        self.saved_snapshots = 0
        self.saved_pages: list[str] = []
        self.saved_windows: list[tuple[datetime, datetime]] = []
        self.saved_evidence = 0
        self.saved_news = []
        self.news_checkpoint = {}
        self.claimed = False
        self.lock_available = True
        self.recover_running_values: list[bool] = []
        self.database = Mock(spec=Database)
        self.scheduled: list[date] = []

    def observer_lock(self, user_id=None):
        return nullcontext(self.lock_available)

    def observer_user_ids(self) -> tuple[UUID, ...]:
        return (USER_ID,)

    def schedule_daily_job(self, user_id, *, scheduled_for, legal_versions):
        assert user_id == USER_ID
        assert legal_versions == LEGAL_VERSIONS
        if scheduled_for not in self.scheduled:
            self.scheduled.append(scheduled_for)
            return True
        return False

    def claim_pending_daily_job(self, user_id, legal_versions):
        if not self.scheduled:
            return None
        return self.claim_daily_job(user_id, job_type="portfolio_daily",
                                    scheduled_for=self.scheduled[-1],
                                    legal_versions=legal_versions, recover_running=True)

    def claim_daily_job(
        self,
        user_id: UUID,
        *,
        job_type: str,
        scheduled_for: date,
        legal_versions: dict[str, str],
        recover_running: bool = False,
    ):
        assert user_id == USER_ID
        assert job_type == "portfolio_daily"
        assert legal_versions == LEGAL_VERSIONS
        self.recover_running_values.append(recover_running)
        if self.claimed:
            return None
        self.claimed = True
        now = datetime(2026, 10, 2, 5, 0, tzinfo=UTC)
        return JobRunRecord(
            id=uuid4(),
            user_id=user_id,
            job_type=job_type,
            scheduled_for=scheduled_for,
            status="running",
            attempt=1,
            started_at=now,
            finished_at=None,
        )

    def finish_job(self, user_id: UUID, job_run_id: UUID, *, status: str, details):
        assert user_id == USER_ID
        assert job_run_id
        self.finished.append((status, details))
        return True

    def current_profile(self, user_id: UUID):
        assert user_id == USER_ID
        return None

    def reuse_snapshot_metadata(self, user_id: UUID, *, job_run_id: UUID, bundle):
        assert user_id == USER_ID
        assert job_run_id
        return bundle

    def save_snapshot(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        bundle,
        account: TBankAccount,
        user_info: TBankUserInfo | None = None,
    ):
        assert user_id == USER_ID
        assert job_run_id
        assert bundle.account_id == "account-1"
        assert account.id == "account-1"
        assert user_info is None
        self.saved_snapshots += 1
        return uuid4()

    def save_evidence(
        self,
        user_id: UUID,
        *,
        job_run_id,
        snapshot_id,
        documents,
        assessments,
        retrieved_at: datetime,
        news_checkpoint=None,
    ):
        assert user_id == USER_ID
        assert snapshot_id
        assert retrieved_at.tzinfo is not None
        if news_checkpoint is None:
            self.saved_evidence += 1
        else:
            self.saved_news.extend(documents)
            self.news_checkpoint = {
                **news_checkpoint,
                "documents_new": news_checkpoint["documents_new"] + len(documents),
            }
        return len(documents), len(assessments)

    def news_state(self, user_id: UUID, *, job_run_id: UUID):
        assert user_id == USER_ID
        assert job_run_id
        return dict(self.news_checkpoint)




class FakeBroker:
    def __init__(
        self,
        *,
        pages: dict[str, TBankOperationsPage] | None = None,
        opened_at: datetime | None = datetime(2024, 1, 1, tzinfo=UTC),
        analysis_status: str = "observed",
        user_info_unavailable: bool = False,
    ) -> None:
        self.pages = pages or {
            "": TBankOperationsPage(True, "cursor-2", ()),
            "cursor-2": TBankOperationsPage(False, "", ()),
        }
        self.opened_at = opened_at
        self.analysis_status = analysis_status
        self.user_info_unavailable = user_info_unavailable
        self.seen_cursors: list[str] = []

    def instrument_news(self, user_id, *, cursor=None, limit=50):
        assert user_id == USER_ID
        assert limit == 50
        return {"items": [], "next_cursor": None, "scanned_items": 0,
                "observed_at": datetime.now(UTC).isoformat(), "status": "available"}

    def revalidate_account(self, user_id: UUID) -> TBankAccount:
        assert user_id == USER_ID
        return TBankAccount(
            id="account-1",
            name="Основной",
            type="ACCOUNT_TYPE_TINKOFF",
            status="ACCOUNT_STATUS_OPEN",
            opened_at=self.opened_at,
            access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        )

    def user_info(self, user_id: UUID) -> TBankUserInfo:
        raise AssertionError("forbidden private broker data read")

    def observation_bundle(
        self,
        user_id: UUID,
        *,
        full_catalog: bool = False,
    ) -> BrokerObservationBundle:
        assert user_id == USER_ID
        assert full_catalog is True
        return bundle(self.analysis_status)

    def evidence(
        self,
        user_id: UUID,
        bundle: BrokerObservationBundle,
        *,
        now: datetime | None = None,
    ) -> BrokerEvidenceSnapshot:
        assert user_id == USER_ID
        assert bundle.account_id == "account-1"
        observed = now or datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
        return BrokerEvidenceSnapshot(
            refreshed_at=observed,
            dividends=(),
            coupons=(),
            bond_events=(),
            reports=(),
            fundamentals=(),
            sources=(
                AnalysisSource(
                    id="payout_calendar",
                    name="payouts",
                    url="https://developer.tbank.ru/invest/services/instruments/methods",
                    methods=(),
                    retrieved_at=observed,
                    status="received",
                ),
                AnalysisSource(
                    id="issuer_events",
                    name="events",
                    url="https://developer.tbank.ru/invest/services/instruments/methods",
                    methods=(),
                    retrieved_at=observed,
                    status="received",
                ),
                AnalysisSource(
                    id="fundamentals",
                    name="fundamentals",
                    url="https://developer.tbank.ru/invest/services/instruments/methods",
                    methods=(),
                    retrieved_at=observed,
                    status="received",
                ),
                AnalysisSource(
                    id="credit_ratings",
                    name="ratings",
                    url="https://www.cbr.ru/finm_infrastructure/ra/",
                    methods=(),
                    retrieved_at=observed,
                    status="not_requested",
                ),
            ),
        )

    def history_page(
        self,
        user_id: UUID,
        *,
        from_at: datetime,
        to_at: datetime,
        cursor: str = "",
        limit: int = 1000,
    ) -> TBankOperationsPage:
        raise AssertionError("forbidden private broker data read")


def test_provider_read_retries_unavailable_reads_with_bounded_jitter() -> None:
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TBankUnavailable("temporary")
        return "ok"

    with (
        patch("omnicio.observer.secrets.randbelow", side_effect=[0, 1000]),
        patch("omnicio.observer.time.sleep") as sleep,
    ):
        assert provider_read(operation) == "ok"

    assert attempts == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.75, 2.5]


def test_full_observer_run_uses_process_lock_and_recovers_running_jobs() -> None:
    store = FakeStore()
    broker = FakeBroker()
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)

    result = observer.run(now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC))

    assert result.total_users == 1
    assert result.claimed_jobs == 1
    assert store.recover_running_values == [True]


def test_full_observer_run_defers_durably_when_another_process_holds_lock() -> None:
    store = FakeStore()
    store.lock_available = False
    observer = PortfolioObserver(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)

    result = observer.run(now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC))

    assert result == type(result)(1, 0, 0, 0, 0, deferred=True)
    assert store.scheduled == [date(2026, 10, 2)]
    assert store.recover_running_values == []
    assert not store.claimed


def test_daily_observer_reads_current_positions_and_never_history_or_profile() -> None:
    store = FakeStore()
    broker = FakeBroker()
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)

    result = observer.run_user(USER_ID, now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC))

    assert result is not None
    assert result.status == "succeeded"
    assert result.snapshot_saved is True
    assert result.history_pages == 0
    assert broker.seen_cursors == []
    assert store.saved_snapshots == 1
    assert store.saved_evidence == 1
    assert store.finished[0][0] == "succeeded"
    assert store.finished[0][1]["history_status"] == "not_collected"
    assert store.finished[0][1]["broker_user_info_status"] == "not_collected"


def test_observer_schema_has_tenant_rls_dedup_and_restart_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text(encoding="utf-8")
    store = (root / "src" / "omnicio" / "portfolio_store.py").read_text(encoding="utf-8")

    for table in (
        "account_instrument_access",
        "investment_profile_versions",
        "job_runs",
        "portfolio_snapshots",
        "portfolio_snapshot_positions",
        "operation_observations",
        "broker_sync_state",
    ):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in migration
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in migration

    assert "UNIQUE (user_id, job_type, scheduled_for)" in migration
    assert "UNIQUE (user_id, account_id, observation_hash)" in migration
    assert "operation_observations_semantic_unique_idx" in migration
    assert "ON CONFLICT (job_run_id) DO NOTHING" in store
    assert "UNIQUE (job_run_id)" in migration
    assert "job_runs_finish_state_consistent" in migration
    assert "broker_sync_state_cursor_window_consistent" in migration
    assert "pg_try_advisory_lock" in store
    assert "pg_advisory_xact_lock" in store
    assert "retry_of" in store
    assert "recover_running" in store
    assert "ON CONFLICT (job_run_id) DO NOTHING" in store
    assert "FROM broker_sync_state" not in store
    assert "operation_observations" not in store


def test_daily_retry_policy_controls_durable_delay_and_terminal_attempt() -> None:
    now = datetime(2026, 10, 6, 10, tzinfo=UTC)
    cursor, connection, database = Mock(), Mock(), Mock()
    cursor.fetchone.return_value = {"id": UUID(int=50)}
    connection.transaction.return_value = nullcontext()
    connection.cursor.return_value = nullcontext(cursor)
    database.pool.connection.return_value = nullcontext(connection)
    store = PortfolioStore(database)
    with patch.object(store, "_tenant"), patch("omnicio.portfolio_store._require_observation_job"):
        assert store.finish_job(USER_ID, UUID(int=50), status="failed", details={"retryable": True})
    statement, params = cursor.execute.call_args.args
    assert statement.count("%s") == len(params)
    assert params[1:3] == (DAILY_RETRY_BASE_SECONDS, DAILY_MAX_ATTEMPTS)
    assert "LEAST(attempt, %s) - 1" in statement
    assert params[-2:] == (UUID(int=50), USER_ID)
    row = {"status": "failed", "details": {"retryable": True}, "next_attempt_at": now,
           "attempt": DAILY_MAX_ATTEMPTS - 1}
    assert store._settle_daily_retry(
        cursor, USER_ID, row, now, context_matches=True, recover_running=False,
    )
    assert not store._settle_daily_retry(
        cursor, USER_ID, {**row, "attempt": DAILY_MAX_ATTEMPTS}, now,
        context_matches=True, recover_running=False,
    )


def test_shared_catalog_does_not_claim_personal_instrument_access() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text(encoding="utf-8")
    store = (root / "src" / "omnicio" / "portfolio_store.py").read_text(encoding="utf-8")

    catalog_block = migration.split(
        "CREATE TABLE IF NOT EXISTS instrument_catalog",
        1,
    )[1].split("CREATE INDEX IF NOT EXISTS instrument_catalog_isin_idx", 1)[0]

    assert "required_tests" not in catalog_block
    assert "CREATE TABLE IF NOT EXISTS account_instrument_access" in migration
    assert "required_tests jsonb NOT NULL" in migration
    assert "account_instrument_access_tenant" in migration
    assert "INSERT INTO account_instrument_access" not in store


def test_issuer_mapping_foundation_never_guesses_unverified_relationships() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS issuer_groups" in migration
    assert "CREATE TABLE IF NOT EXISTS issuers" in migration
    assert "CREATE TABLE IF NOT EXISTS instrument_issuer_map" in migration
    assert "source_url text NOT NULL" in migration
    assert "verified_at timestamptz NOT NULL" in migration
    assert "INSERT INTO issuers" not in migration


@pytest.fixture
def connected_database():
    """Disposable native database: never accept a production host or database."""
    base = os.environ.get("OMNICIO_TEST_DATABASE_URL")
    if not base:
        pytest.skip("disposable PostgreSQL is required for connection race coverage")
    options = conninfo_to_dict(base)
    assert options["host"] == "127.0.0.1"
    assert options["dbname"] == "omnicio_test"
    identity = uuid4().hex
    name, role = f"lifecycle_{identity}", f"lifecycle_role_{identity}"
    password = uuid4().hex
    with psycopg.connect(base, autocommit=True) as control:
        control.execute(sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(sql.Identifier(role), sql.Literal(password)))
        created = False
        try:
            control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
            admin_dsn = make_conninfo(base, dbname=name)
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                for migration in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
                    admin.execute(migration.read_text(encoding="utf-8"))
                admin.execute("INSERT INTO users (id) VALUES (%s), (%s)", (USER_ID, UUID(int=2)))
                admin.execute(
                    "INSERT INTO vkid_identities (user_id,vk_user_id,verified_at) "
                    "VALUES (%s,'synthetic-a',now()),(%s,'synthetic-b',now())",
                    (USER_ID, UUID(int=2)),
                )
                for tenant in (USER_ID, UUID(int=2)):
                    for document, version in LEGAL_VERSIONS.items():
                        admin.execute(
                            "INSERT INTO legal_acceptances (user_id, document_type, "
                            "document_version, client_ip_hash) VALUES (%s, %s, %s, %s)",
                            (tenant, document, version, b"test-only"),
                        )
                admin.execute(sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(sql.Identifier(role)))
                admin.execute(sql.SQL(
                    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}"
                ).format(sql.Identifier(role)))
                database = Database(make_conninfo(admin_dsn, user=role, password=password))
                database.open()
                try:
                    yield database, PortfolioStore(database), admin
                finally:
                    database.close()
        finally:
            if created:
                control.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
                )
            control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def connect_user(database, user_id=USER_ID, *, account_id="account-1", environment="prod"):
    return database.upsert_tbank_connection(
        user_id=user_id, environment=environment, account_id=account_id,
        account_name="Synthetic", encrypted_credential=b"synthetic-encrypted-token",
        terms_version="test",
    )


def claim_job(store, user_id=USER_ID):
    job = store.claim_daily_job(user_id, job_type="portfolio_daily", scheduled_for=date.today(),
                                legal_versions=LEGAL_VERSIONS)
    assert job is not None
    return job


def test_native_connection_lifecycle_keeps_tenants_and_discards_old_jobs(connected_database):
    database, store, admin = connected_database
    other = UUID(int=2)
    observation = bundle()
    wrong_account = replace(observation, account_id="old")
    observed_at = datetime.now(UTC)
    assert (
        store.claim_daily_job(
            USER_ID,
            job_type="portfolio_daily",
            scheduled_for=date.today(),
            legal_versions=LEGAL_VERSIONS,
        )
        is None
    )
    current = connect_user(database)
    connect_user(database, other)
    job, other_job = claim_job(store), claim_job(store, other)
    snapshot = store.save_snapshot(USER_ID, job_run_id=job.id, bundle=observation)
    other_snapshot = store.save_snapshot(
        other,
        job_run_id=other_job.id,
        bundle=replace(bundle(), analysis=replace(analysis(), nav_rub="2000")),
    )
    assert store.portfolio_visualization(USER_ID)["latest"]["nav_rub"] == 1000
    assert store.portfolio_visualization(other)["latest"]["nav_rub"] == 2000

    for fields in ({"account_id": "different"}, {"environment": "sandbox"}):
        with pytest.raises(BrokerConnectionConflict, match="broker_disconnect_required"):
            connect_user(database, **fields)
        assert database.tbank_connection(USER_ID) == current
    renewed = connect_user(database)
    assert renewed.account_id == current.account_id
    assert store.portfolio_visualization(USER_ID)["latest"]["snapshot_id"] == str(snapshot)
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(USER_ID, job_run_id=other_job.id, bundle=observation)
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(USER_ID, job_run_id=job.id, bundle=wrong_account)
    with pytest.raises(ObservationCancelled):
        store.save_evidence(
            USER_ID,
            job_run_id=job.id,
            snapshot_id=other_snapshot,
            documents=(),
            assessments=(),
            retrieved_at=observed_at,
        )

    # Old account rows left by a previous version cannot become the selected account.
    admin.execute("UPDATE portfolio_snapshots SET account_id='legacy' WHERE id=%s", (snapshot,))
    assert store.portfolio_visualization(USER_ID)["status"] == "pending"
    assert store.latest_balancing_context(USER_ID) is None
    assert store.instrument_visualization(USER_ID, "not-held") is None
    assert store.portfolio_visualization(other)["status"] == "observed"

    assert database.delete_tbank_connection(USER_ID)
    connect_user(database)  # Even an identical reconnection has a different job lineage.
    new_job = claim_job(store)
    assert new_job.id != job.id
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(USER_ID, job_run_id=job.id, bundle=observation)
    with pytest.raises(ObservationCancelled):
        store.save_evidence(
            USER_ID,
            job_run_id=job.id,
            snapshot_id=snapshot,
            documents=(),
            assessments=(),
            retrieved_at=observed_at,
        )
    assert not store.finish_job(USER_ID, job.id, status="succeeded", details={})
    assert store.portfolio_visualization(USER_ID)["status"] == "pending"
    assert store.portfolio_visualization(other)["latest"]["snapshot_id"] == str(other_snapshot)
    store.save_snapshot(USER_ID, job_run_id=new_job.id, bundle=observation)
    assert database.delete_user_account(USER_ID)
    with pytest.raises(ObservationCancelled):
        store.save_snapshot(USER_ID, job_run_id=new_job.id, bundle=observation)
    assert store.portfolio_visualization(other)["status"] == "observed"


def test_native_disconnect_waits_for_write_then_removes_every_derived_row(connected_database):
    database, store, admin = connected_database
    connect_user(database)
    job = claim_job(store)
    writing, resume = Event(), Event()
    original = store._save_snapshot_positions

    def paused(*args):
        writing.set()
        assert resume.wait(timeout=10)
        return original(*args)

    with (
        patch.object(store, "_save_snapshot_positions", side_effect=paused),
        ThreadPoolExecutor(max_workers=2) as threads,
    ):
        save = threads.submit(store.save_snapshot, USER_ID, job_run_id=job.id, bundle=bundle())
        try:
            assert writing.wait(timeout=5)
            disconnect = threads.submit(database.delete_tbank_connection, USER_ID)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                blocked = admin.execute(
                    "SELECT 1 FROM pg_stat_activity "
                    "WHERE datname=current_database() AND wait_event='advisory'"
                ).fetchone()
                if blocked:
                    break
                time.sleep(0.01)
            assert blocked, "disconnect did not wait on the lifecycle lock"
            assert not disconnect.done()
        finally:
            resume.set()
        assert save.result(timeout=5)
        assert disconnect.result(timeout=5)
    for table in (
        "portfolio_snapshots", "account_instrument_access", "broker_sync_state", "job_runs",
    ):
        assert admin.execute(sql.SQL("SELECT count(*) FROM {} WHERE user_id=%s").format(
            sql.Identifier(table)
        ), (USER_ID,)).fetchone()[0] == 0
    assert database.tbank_connection(USER_ID) is None


def test_daily_scheduler_keeps_the_last_due_day_before_the_moscow_0615_boundary() -> None:
    assert _scheduled_day(datetime(2026, 10, 7, 3, 14, tzinfo=UTC)) == date(2026, 10, 6)
    assert _scheduled_day(datetime(2026, 10, 7, 3, 15, tzinfo=UTC)) == date(2026, 10, 7)


def test_native_daily_queue_survives_manual_lock_and_is_consumed_after_release(connected_database):
    database, store, admin = connected_database
    connect_user(database)
    observer = PortfolioObserver(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)
    with store.observer_lock() as locked:
        assert locked
        result = observer.run(now=datetime.now(UTC))
        assert result.deferred
        row = admin.execute("SELECT id, status FROM job_runs WHERE user_id = %s",
                            (USER_ID,)).fetchone()
        assert row[1] == "queued"
        assert admin.execute("SELECT count(*) FROM portfolio_snapshots").fetchone()[0] == 0
    coordinator = PortfolioRefreshCoordinator(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)
    assert coordinator.run_pending()
    assert not coordinator.run_pending()
    assert admin.execute("SELECT count(*) FROM portfolio_snapshots").fetchone()[0] == 1
    assert admin.execute("SELECT status FROM job_runs WHERE id = %s", (row[0],)).fetchone()[0] \
        == "succeeded"


def test_native_daily_restart_uses_new_immutable_snapshot_and_owner_bound_retry(connected_database):
    database, store, admin = connected_database
    connect_user(database)
    connect_user(database, UUID(int=2), account_id="account-2")
    first = claim_job(store)
    old = replace(bundle(), refreshed_at=datetime.now(UTC) - timedelta(minutes=10))
    old_snapshot = store.save_snapshot(USER_ID, job_run_id=first.id, bundle=old)
    # Once the old process releases its session lock, a new process can resume.
    with store.observer_lock() as locked:
        assert locked
        retry = store.claim_pending_daily_job(USER_ID, LEGAL_VERSIONS)
        assert retry is not None
        assert retry.id != first.id
        assert retry.scheduled_for == first.scheduled_for
        fresh = replace(old, refreshed_at=datetime.now(UTC))
        fresh_snapshot = store.save_snapshot(USER_ID, job_run_id=retry.id, bundle=fresh)
        assert fresh_snapshot != old_snapshot
        assert store.finish_job(USER_ID, retry.id, status="succeeded", details={})
        assert store.claim_pending_daily_job(USER_ID, LEGAL_VERSIONS) is None
    rows = admin.execute("SELECT job_run_id, captured_at FROM portfolio_snapshots "
                         "WHERE user_id = %s ORDER BY captured_at", (USER_ID,)).fetchall()
    assert rows == [(first.id, old.refreshed_at), (retry.id, fresh.refreshed_at)]
    attempts = admin.execute("SELECT id, retry_of, status, attempt FROM job_runs "
                             "WHERE user_id = %s ORDER BY attempt", (USER_ID,)).fetchall()
    assert attempts == [(first.id, None, "failed", 1), (retry.id, first.id, "succeeded", 2)]
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(UUID(int=2)),))
        retry_values = (UUID(int=2), first.id)
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, retry_of, status) "
                "VALUES (%s, 'portfolio_daily', NULL, %s, 'queued')", retry_values,
            )
        conn.rollback()
    # Reapplying the new additive schema cannot rewrite an accepted observation.
    path = Path(__file__).parents[1] / "migrations/0024_background_reliability.sql"
    migration = path.read_text(encoding="utf-8")
    admin.execute(migration)
    admin.execute(migration)
    assert admin.execute("SELECT count(*) FROM portfolio_snapshots").fetchone()[0] == 2


def test_native_daily_retry_waits_for_backoff_and_stops_at_the_daily_budget(connected_database):
    database, store, admin = connected_database
    connect_user(database)
    first = claim_job(store)
    with store.observer_lock() as locked:
        assert locked
        current = first
        for attempt in range(1, 4):
            assert current.attempt == attempt
            assert store.finish_job(USER_ID, current.id, status="degraded", details={
                "stage_error": "TBankUnavailable", "retryable": True, "snapshot_saved": False,
            })
            assert store.claim_pending_daily_job(USER_ID, LEGAL_VERSIONS) is None
            admin.execute("UPDATE job_runs SET next_attempt_at = now() - interval '1 second' "
                          "WHERE id = %s", (current.id,))
            retry = store.claim_pending_daily_job(USER_ID, LEGAL_VERSIONS)
            if attempt < 3:
                assert retry is not None
                assert retry.id != current.id
                current = retry
            else:
                assert retry is None
    count = admin.execute("SELECT count(*) FROM job_runs WHERE user_id = %s",
                          (USER_ID,)).fetchone()[0]
    assert count == 3
    assert database.collect_operational_metrics()["status"] == "attention"


def test_native_daily_queue_rechecks_consent_and_finishes_cancelled_attempt(connected_database):
    database, store, admin = connected_database
    connect_user(database)
    first = claim_job(store)
    admin.execute("DELETE FROM legal_acceptances WHERE user_id = %s AND document_type = 'terms'",
                  (USER_ID,))
    assert not store.finish_job(USER_ID, first.id, status="succeeded", details={})
    row = admin.execute("SELECT status, details FROM job_runs WHERE id = %s",
                        (first.id,)).fetchone()
    assert row[0] == "failed"
    assert row[1]["stage_error"] == "observation_context_changed"
    with store.observer_lock() as locked:
        assert locked
        assert store.claim_pending_daily_job(USER_ID, LEGAL_VERSIONS) is None
    assert admin.execute("SELECT count(*) FROM portfolio_snapshots").fetchone()[0] == 0


def test_observer_treats_disconnected_job_as_degraded_without_recreating_it():
    store = FakeStore()
    observer = PortfolioObserver(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)
    with patch.object(store, "save_snapshot", side_effect=ObservationCancelled("disconnected")):
        result = observer.run_user(USER_ID, now=datetime(2026, 10, 2, tzinfo=UTC))
    assert result.status == "degraded"
    assert not result.snapshot_saved
    assert store.saved_pages == []
    assert store.saved_evidence == 0


@pytest.mark.parametrize("failure_in_storage", [False, True])
def test_observer_does_not_log_provider_or_sql_exception_text(caplog, failure_in_storage):
    store = FakeStore()
    broker = FakeBroker()
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
    storage_patch = (
        patch.object(store, "finish_job", side_effect=RuntimeError("sensitive-sql-value"))
        if failure_in_storage else nullcontext()
    )
    with (
        patch.object(
            broker, "revalidate_account", side_effect=RuntimeError("sensitive-provider-value"),
        ),
        storage_patch,
    ):
        result = observer.run(now=datetime(2026, 10, 2, tzinfo=UTC))
    assert result.failed == 1
    assert "error_type=RuntimeError" in caplog.text
    assert "sensitive-provider-value" not in caplog.text
    assert "sensitive-sql-value" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_native_observer_owner_locks_allow_parallel_accounts_and_exclude_legacy_worker(
    connected_database,
):
    database, store, _ = connected_database
    another = uuid4()
    with store.observer_lock(USER_ID) as first:
        assert first
        with PortfolioStore(database).observer_lock(USER_ID) as same:
            assert not same
        with PortfolioStore(database).observer_lock(another) as independent:
            assert independent
        with PortfolioStore(database).observer_lock() as legacy:
            assert not legacy
    with store.observer_lock() as legacy:
        assert legacy
        with PortfolioStore(database).observer_lock(USER_ID) as blocked:
            assert not blocked
    with store.observer_lock(USER_ID) as released:
        assert released


def test_native_quick_refresh_restores_shared_metadata_without_reusing_broker_profile(
    connected_database,
):
    database, store, admin = connected_database
    connect_user(database)
    job = claim_job(store)
    now, original = datetime.now(UTC), datetime.now(UTC) - timedelta(days=3)
    metadata = tuple(
        TBankInstrumentMetadata(
            uid=uid,
            name=f"Verified {uid}",
            ticker=uid.upper(),
            isin="",
            instrument_type=kind,
            sector="financial",
            country_of_risk="RU",
            for_qual_investor=False,
        )
        for uid, kind in (("share", "share"), ("fund", "etf"))
    )
    positions = tuple(
        TBankPortfolioPosition(
            ticker=item.ticker,
            figi="",
            instrument_uid=item.uid,
            instrument_type=item.instrument_type,
            quantity="1",
            current_price=TBankMoney("RUB", "100"),
            average_price=None,
            expected_yield_amount=None,
            daily_yield=None,
            blocked=False,
        )
        for item in metadata
    )
    base = bundle()
    portfolio = replace(base.portfolio, positions=positions)
    observed = replace(
        base,
        refreshed_at=original,
        portfolio=portfolio,
        metadata=metadata,
        analysis=analyze_portfolio(portfolio, base.positions, metadata),
        sources=tuple(replace(source, retrieved_at=original) for source in base.sources),
    )
    store.save_snapshot(USER_ID, job_run_id=job.id, bundle=observed)
    store.finish_job(USER_ID, job.id, status="succeeded", details={})
    store.request_refresh(USER_ID, LEGAL_VERSIONS, scope="quick")
    quick_job = store.claim_refresh_job(USER_ID, LEGAL_VERSIONS)
    assert quick_job is not None
    quick = replace(
        observed,
        refreshed_at=now,
        metadata=(),
        analysis=analyze_portfolio(portfolio, base.positions, ()),
        sources=tuple(
            replace(source, retrieved_at=now, status="not_requested") for source in observed.sources
        ),
    )
    restored = PortfolioStore(database).reuse_snapshot_metadata(
        USER_ID,
        job_run_id=quick_job.id,
        bundle=quick,
    )
    assert {item.name for item in restored.analysis.securities} == {
        "Verified share",
        "Verified fund",
    }
    assert {item.uid: item.sector for item in restored.analysis.securities} == {
        "share": "financial",
        "fund": "",
    }
    assert restored.sources[0].retrieved_at == original
    assert restored.sources[0].status == "cached"
    store.save_snapshot(USER_ID, job_run_id=quick_job.id, bundle=restored)
    context = store.latest_balancing_context(USER_ID)
    assert context["broker_user"] == {}
    assert context["broker_user_as_of"] is None
    assert context["broker_user_time_basis"] == "not_collected"
    rows = store.portfolio_visualization(USER_ID, now=now)["latest"]["positions"]
    assert {row["instrument_uid"]: row["sector"] for row in rows} == {
        "share": "financial",
        "fund": "",
    }
    catalog_times = admin.execute(
        "SELECT provider_retrieved_at FROM instrument_catalog WHERE provider='tbank'"
    ).fetchall()
    assert all(row[0] == original for row in catalog_times)
    with pytest.raises(ObservationCancelled):
        store.reuse_snapshot_metadata(UUID(int=2), job_run_id=quick_job.id, bundle=quick)


def test_native_snapshots_discard_purchase_statistics_and_keep_catalog_matches_unique(
    connected_database,
):
    database, store, admin = connected_database
    connect_user(database)
    job = claim_job(store)
    observed_at = datetime.now(UTC) - timedelta(days=3)
    original = TBankInstrumentMetadata(
        uid="held-share",
        name="Verified share",
        ticker="HOLD",
        figi="same-figi",
        isin="",
        instrument_type="share",
        sector="financial",
        country_of_risk="RU",
        for_qual_investor=False,
    )
    duplicate_figi = replace(original, uid="other-uid", name="Different instrument")
    position = TBankPortfolioPosition(
        ticker="HOLD",
        figi=original.figi,
        instrument_uid=original.uid,
        instrument_type="share",
        quantity="2",
        current_price=TBankMoney("RUB", "125.19"),
        average_price=TBankMoney("RUB", "120.03"),
        average_price_fifo=TBankMoney("RUB", "119.07"),
        expected_yield_amount="10.32",
        daily_yield=TBankMoney("RUB", "-0.42"),
        blocked=False,
    )
    base = bundle()
    portfolio = replace(
        base.portfolio,
        expected_yield_percent="1.04267726",
        daily_yield=TBankMoney("RUB", "-0.42"),
        daily_yield_percent="-0.042",
        positions=(position,),
    )
    observed = replace(
        base,
        refreshed_at=observed_at,
        portfolio=portfolio,
        metadata=(original, duplicate_figi),
        analysis=analyze_portfolio(portfolio, base.positions, (original, duplicate_figi)),
    )
    snapshot = store.save_snapshot(USER_ID, job_run_id=job.id, bundle=observed)
    latest = store.portfolio_visualization(USER_ID)["latest"]
    assert len(latest["positions"]) == 1
    assert latest["positions"][0]["name"] == "Verified share"
    strategy = store.latest_balancing_context(USER_ID)
    assert len(strategy["holdings"]) == 1
    assert strategy["holdings"][0]["name"] == "Verified share"
    assert "broker_statistics" not in latest
    assert latest["snapshot_freshness"] == "stale"
    holding = latest["positions"][0]
    assert not {"expected_yield_amount", "expected_yield_currency", "average_price",
                "average_price_fifo_value"} & holding.keys()
    asset = store.instrument_visualization(USER_ID, original.uid)
    assert len(asset["history"]) == 1
    assert "expected_yield_amount" not in asset["latest"]
    overview = WorkspaceStore(database).dashboard(USER_ID)["overview"]
    assert "broker_statistics" not in overview
    assert overview["status"] == "stale"
    assert store.portfolio_visualization(UUID(int=2))["latest"] is None
    stored = admin.execute(
        "SELECT average_price_fifo_value, average_price_fifo_currency FROM "
        "portfolio_snapshot_positions WHERE snapshot_id=%s", (snapshot,),
    ).fetchone()
    assert stored == (None, None)

    # A legacy row whose only known identity is FIGI must not borrow an
    # arbitrary catalog UID when two different instruments match that FIGI.
    admin.execute(
        "UPDATE portfolio_snapshot_positions SET instrument_uid=figi WHERE snapshot_id=%s",
        (snapshot,),
    )
    ambiguous = store.portfolio_visualization(USER_ID)["latest"]["positions"]
    assert len(ambiguous) == 1
    assert ambiguous[0]["catalog_instrument_uid"] == ""
    legacy = store.instrument_visualization(USER_ID, original.figi)
    assert len(legacy["history"]) == 1
    assert legacy["latest"]["catalog_instrument_uid"] == ""
    strategy = store.latest_balancing_context(USER_ID)
    assert len(strategy["holdings"]) == 1
    assert strategy["holdings"][0]["name"] == ""
    admin.execute(
        "DELETE FROM instrument_catalog WHERE provider='tbank' AND instrument_uid=%s",
        (duplicate_figi.uid,),
    )
    unique = store.portfolio_visualization(USER_ID)["latest"]["positions"]
    assert len(unique) == 1
    assert unique[0]["catalog_instrument_uid"] == original.uid
    strategy = store.latest_balancing_context(USER_ID)
    assert len(strategy["holdings"]) == 1
    assert strategy["holdings"][0]["name"] == "Verified share"

    admin.execute(
        "UPDATE portfolio_snapshots SET evidence=evidence-'broker_statistics' WHERE id=%s",
        (snapshot,),
    )
    assert "broker_statistics" not in WorkspaceStore(database).dashboard(USER_ID)["overview"]
    old = store.portfolio_visualization(USER_ID)["latest"]
    assert "broker_statistics" not in old
    assert "expected_yield_amount" not in old["positions"][0]


@pytest.fixture
def news_observer():
    store, broker = FakeStore(), FakeBroker(pages={"": TBankOperationsPage(False, "", ())})
    held = instrument_bundle()
    observed = replace(bundle(), portfolio=held.portfolio, metadata=held.metadata,
                       analysis=replace(analysis(), security_count=1),
                       refreshed_at=datetime.now(UTC))
    broker.observation_bundle = Mock(return_value=observed)
    return store, broker, PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)


def news_page(ident: str, next_cursor: str | None = None) -> dict[str, object]:
    return {"items": [news_item(ident)], "next_cursor": next_cursor, "scanned_items": 1,
            "observed_at": datetime.now(UTC).isoformat(), "status": "available"}


def pending_news_cursors(state: dict[str, object]) -> list[str]:
    return [path["cursor"] for path in state["continuations"]]


def test_news_polling_always_reads_newest_before_durable_bounded_backlog(news_observer) -> None:
    store, broker, observer = news_observer
    pages = {None: news_page("101", "10"), "10": news_page("102", "20"),
             "20": news_page("103", "30"), "30": news_page("104", "40"),
             "40": news_page("105")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    result = observer.run_user(USER_ID, now=datetime.now(UTC))
    assert result.status == "succeeded"
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list] \
        == [None, "10", "20"]
    assert pending_news_cursors(store.news_checkpoint) == ["30"]
    assert store.finished[-1][1]["news"]["status"] == "partial"
    assert store.news_checkpoint["documents_new"] == 3
    store.claimed = False
    restarted = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
    restarted.run_user(USER_ID, now=datetime.now(UTC))
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][3:] \
        == [None, "30", "40"]
    assert pending_news_cursors(store.news_checkpoint) == []
    assert store.finished[-1][1]["news"]["status"] == "received"
    assert {document.provider_key for document in store.saved_news} == {
        "101", "102", "103", "104", "105",
    }


def test_news_outage_keeps_committed_cursor_and_valid_portfolio_available(news_observer) -> None:
    store, broker, observer = news_observer
    head = news_page("101", "10")
    broker.instrument_news = Mock(side_effect=[head, TBankUnavailable("synthetic outage")])
    result = observer.run_user(USER_ID, now=datetime.now(UTC))
    assert result.status == "succeeded"
    assert result.snapshot_saved is True
    partial = store.finished[-1][1]["news"]
    assert partial["status"] == "partial"
    assert pending_news_cursors(partial) == ["10"]
    assert partial["observed_at"] == head["observed_at"]
    assert pending_news_cursors(store.news_checkpoint) == ["10"]
    store.claimed = False
    broker.instrument_news = Mock(side_effect=TBankUnavailable("still unavailable"))
    observer.run_user(USER_ID, now=datetime.now(UTC))
    unavailable = store.finished[-1][1]["news"]
    assert unavailable["status"] == "unavailable"
    assert unavailable["observed_at"] == head["observed_at"]
    assert pending_news_cursors(unavailable) == ["10"]


def test_news_cursor_cannot_advance_past_a_rolled_back_evidence_page(news_observer) -> None:
    store, broker, observer = news_observer
    broker.instrument_news = Mock(side_effect=[news_page("101", "10"), news_page("102", "20")])
    save = store.save_evidence

    def fail_second_news_page(*args, **kwargs):
        if kwargs.get("news_checkpoint") is not None and store.saved_news:
            raise RuntimeError("synthetic transaction rollback")
        return save(*args, **kwargs)

    store.save_evidence = Mock(side_effect=fail_second_news_page)
    now = datetime.now(UTC)
    with pytest.raises(RuntimeError, match="transaction rollback"):
        observer.run_user(USER_ID, now=now)
    assert pending_news_cursors(store.news_checkpoint) == ["10"]
    assert pending_news_cursors(store.finished[-1][1]["news"]) == ["10"]
    assert [document.provider_key for document in store.saved_news] == ["101"]
    store.save_evidence = save
    store.claimed = False
    broker.instrument_news = Mock(side_effect=[news_page("101", "10"), news_page("102")])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list] == [None, "10"]
    assert store.news_checkpoint["status"] == "received"


def test_news_shutdown_and_restart_resume_committed_page_without_claiming_completion(
    news_observer,
) -> None:
    store, broker, observer = news_observer
    broker.instrument_news = Mock(return_value=news_page("101", "10"))
    now = datetime.now(UTC)
    job = store.claim_daily_job(USER_ID, job_type="portfolio_daily", scheduled_for=now.date(),
                                legal_versions=LEGAL_VERSIONS)
    def should_stop():
        return bool(store.saved_news)
    with pytest.raises(ObservationInterrupted):
        observer.run_job(job, now=now, should_stop=should_stop)
    assert store.finished == []
    assert store.news_checkpoint["status"] == "partial"
    assert pending_news_cursors(store.news_checkpoint) == ["10"]
    assert store.news_checkpoint["documents_new"] == 1
    broker.instrument_news = Mock(side_effect=[news_page("101", "10"), news_page("102")])
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_job(job, now=now)
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list] == [None, "10"]
    assert store.finished[-1][1]["news"]["status"] == "received"


def test_repeated_news_cursor_across_restarts_remains_partial_and_recovers_from_head(
    news_observer,
) -> None:
    store, broker, observer = news_observer
    pages = {None: news_page("101", "10"), "10": news_page("102", "20"),
             "20": news_page("103", "30"), "30": news_page("104", "10")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    for _attempt in range(3):
        store.claimed = False
        observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
        observer.run_user(USER_ID, now=datetime.now(UTC))
        assert store.finished[-1][1]["news"]["status"] == "partial"
        assert pending_news_cursors(store.news_checkpoint)
    pages["30"] = news_page("104")
    for _attempt in range(2):
        store.claimed = False
        PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
            USER_ID, now=datetime.now(UTC),
        )
    assert store.news_checkpoint["status"] == "received"
    assert store.news_checkpoint["recovery_required"] is False


def test_new_head_continuation_cannot_disappear_behind_an_older_backlog(news_observer) -> None:
    store, broker, observer = news_observer
    pages = {None: news_page("500", "450"), "450": news_page("449", "400"),
             "400": news_page("399", "350"), "350": news_page("349", "300"),
             "300": news_page("299")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert pending_news_cursors(store.news_checkpoint) == ["350"]
    pages.update({None: news_page("700", "650"), "650": news_page("649", "600"),
                  "600": news_page("599", "450")})
    store.claimed = False
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
        USER_ID, now=datetime.now(UTC),
    )
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][3:] \
        == [None, "350", "650"]
    assert pending_news_cursors(store.news_checkpoint) == ["300", "600"]
    assert store.news_checkpoint["status"] == "partial"
    store.claimed = False
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
        USER_ID, now=datetime.now(UTC),
    )
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][6:] \
        == [None, "300", "600"]
    assert {"649", "599"} <= {document.provider_key for document in store.saved_news}
    assert pending_news_cursors(store.news_checkpoint) == []
    assert store.news_checkpoint["status"] == "received"


def test_news_complete_pass_is_rechecked_for_corrections_under_the_same_cursors(
    news_observer,
) -> None:
    store, broker, observer = news_observer
    pages = {None: news_page("501", "450"), "450": news_page("449", "400"),
             "400": news_page("399")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert store.news_checkpoint["status"] == "received"
    pages["400"] = {**news_page("399"), "items": [news_item(
        "399", title="Уточнение старой публикации", priority=False,
    )]}
    store.claimed = False
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
        USER_ID, now=datetime.now(UTC),
    )
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][3:] \
        == [None, "450", "400"]
    assert store.saved_news[-1].payload["title"] == "Уточнение старой публикации"
    assert store.saved_news[-1].payload["priority"] is False
    assert store.news_checkpoint["status"] == "received"


def test_news_old_page_proofs_cannot_hide_publications_for_a_new_holding(news_observer) -> None:
    store, broker, observer = news_observer
    pages = {None: news_page("501", "450"), "450": news_page("449", "400"),
             "400": news_page("399", "350"), "350": news_page("349")}
    pages["450"]["items"] = [news_item("449", uid="new-held")]
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert "449" not in {document.provider_key for document in store.saved_news}
    observed = broker.observation_bundle.return_value
    position = replace(observed.portfolio.positions[0], instrument_uid="new-held")
    broker.observation_bundle.return_value = replace(
        observed, portfolio=replace(observed.portfolio, positions=(position,)),
    )
    store.claimed = False
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
        USER_ID, now=datetime.now(UTC),
    )
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][3:] \
        == [None, "350", "450"]
    assert "449" in {document.provider_key for document in store.saved_news}
    assert store.news_checkpoint["status"] == "partial"


def test_news_queue_overflow_requires_a_complete_fresh_recovery(news_observer) -> None:
    store, broker, observer = news_observer
    store.news_checkpoint = {
        "continuations": [{"cursor": str(1000 + index), "seen_cursors": []}
                          for index in range(NEWS_MAX_CONTINUATIONS)],
    }
    pages = {None: news_page("101", "10"), "10": news_page("102", "20"),
             "20": news_page("103")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list] \
        == [None, "10", "20"]
    assert store.news_checkpoint["status"] == "partial"
    assert store.news_checkpoint["recovery_required"] is True
    assert store.news_checkpoint["coverage_reset_at"] == pages[None]["observed_at"]
    store.claimed = False
    PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
        USER_ID, now=datetime.now(UTC),
    )
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list][3:] \
        == [None, "10", "20"]
    assert store.news_checkpoint["status"] == "received"
    assert store.news_checkpoint["recovery_required"] is False


def test_news_durable_metadata_has_a_total_bound_during_a_long_unfinished_traversal(
    news_observer,
) -> None:
    store, broker, observer = news_observer

    def endless_feed(_user, *, cursor, limit):
        value = int(cursor or "1000000000000000000")
        return news_page(str(value), str(value + 1))

    broker.instrument_news = Mock(side_effect=endless_feed)
    for _attempt in range(NEWS_MAX_PATH_PROOFS // 2 + 5):
        store.claimed = False
        PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS).run_user(
            USER_ID, now=datetime.now(UTC),
        )
        checkpoint = store.news_checkpoint
        paths = checkpoint["continuations"]
        assert len(paths) <= NEWS_MAX_CONTINUATIONS
        assert sum(len(path["seen_cursors"]) for path in paths) <= NEWS_MAX_PATH_PROOFS
        assert len(checkpoint["completed_cursors"]) <= NEWS_MAX_COMPLETED_CURSORS
        assert len(json.dumps(checkpoint).encode("utf-8")) < 10_000
        assert checkpoint["status"] == "partial"
    # Retain the known head relation while evicting other old proof markers.
    assert len(store.news_checkpoint["continuations"]) == 1
    assert len(broker.instrument_news.call_args_list) == (NEWS_MAX_PATH_PROOFS // 2 + 5) * 3


def test_news_legacy_single_cursor_checkpoint_is_resumed_without_skipping_new_head(
    news_observer,
) -> None:
    store, broker, observer = news_observer
    store.news_checkpoint = {"cursor": "20", "seen_cursors": ["10"], "status": "partial"}
    pages = {None: news_page("501", "450"), "20": news_page("19"),
             "450": news_page("449")}
    broker.instrument_news = Mock(side_effect=lambda _user, *, cursor, limit: pages[cursor])
    observer.run_user(USER_ID, now=datetime.now(UTC))
    assert [call.kwargs["cursor"] for call in broker.instrument_news.call_args_list] \
        == [None, "20", "450"]
    assert "cursor" not in store.news_checkpoint
    assert store.news_checkpoint["status"] == "received"
