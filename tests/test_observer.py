from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.broker import AnalysisSource, BrokerEvidenceSnapshot, BrokerObservationBundle
from omnicio.db import BrokerConnectionConflict, Database
from omnicio.observer import PortfolioObserver, provider_read
from omnicio.portfolio import PortfolioAnalysis
from omnicio.portfolio_store import (
    BrokerSyncState,
    JobRunRecord,
    ObservationCancelled,
    PortfolioStore,
)
from omnicio.tbank import (
    TBankAccount,
    TBankMoney,
    TBankOperationsPage,
    TBankPortfolio,
    TBankPositions,
    TBankUnavailable,
    TBankUserInfo,
)

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
    def __init__(self, *, state: BrokerSyncState | None = None) -> None:
        self.state = state
        self.finished: list[tuple[str, dict[str, object]]] = []
        self.saved_snapshots = 0
        self.saved_pages: list[str] = []
        self.saved_evidence = 0
        self.claimed = False
        self.lock_available = True
        self.recover_running_values: list[bool] = []

    def observer_lock(self):
        return nullcontext(self.lock_available)

    def observer_user_ids(self, legal_versions: dict[str, str]) -> tuple[UUID, ...]:
        assert legal_versions == LEGAL_VERSIONS
        return (USER_ID,)

    def claim_daily_job(
        self,
        user_id: UUID,
        *,
        job_type: str,
        scheduled_for: date,
        recover_running: bool = False,
    ):
        assert user_id == USER_ID
        assert job_type == "portfolio_daily"
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

    def save_snapshot(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        bundle,
        account: TBankAccount,
        user_info: TBankUserInfo | None,
    ):
        assert user_id == USER_ID
        assert job_run_id
        assert bundle.account_id == "account-1"
        assert account.id == "account-1"
        if user_info is not None:
            assert user_info.risk_level_code == "CONSERVATIVE"
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
    ):
        assert user_id == USER_ID
        assert snapshot_id
        assert retrieved_at.tzinfo is not None
        self.saved_evidence += 1
        return len(documents), len(assessments)

    def sync_state(self, user_id: UUID, account_id: str):
        assert user_id == USER_ID
        assert account_id == "account-1"
        return self.state

    def save_history_page(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        account_id: str,
        environment: str,
        window_from: datetime,
        window_to: datetime,
        page: TBankOperationsPage,
        observed_at: datetime,
    ) -> int:
        assert user_id == USER_ID
        assert account_id == "account-1"
        assert window_from <= window_to <= observed_at
        self.saved_pages.append(page.next_cursor)
        return len(page.items)


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
        assert user_id == USER_ID
        if self.user_info_unavailable:
            raise TBankUnavailable("temporary")
        return TBankUserInfo(
            premium=False,
            qualified=False,
            qualified_for_work_with=("russian_shares",),
            tariff="Investor",
            risk_level_code="CONSERVATIVE",
        )

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
        assert user_id == USER_ID
        assert from_at <= to_at
        assert limit == 1000
        self.seen_cursors.append(cursor)
        return self.pages[cursor]


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


def test_full_observer_run_skips_when_another_process_holds_lock() -> None:
    store = FakeStore()
    store.lock_available = False
    observer = PortfolioObserver(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)

    result = observer.run(now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC))

    assert result == type(result)(0, 0, 0, 0, 0)
    assert store.recover_running_values == []


def test_daily_observer_pages_history_and_finishes_once() -> None:
    store = FakeStore()
    broker = FakeBroker()
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)

    result = observer.run_user(USER_ID, now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC))

    assert result is not None
    assert result.status == "succeeded"
    assert result.snapshot_saved is True
    assert result.history_pages == 2
    assert broker.seen_cursors == ["", "cursor-2"]
    assert store.saved_snapshots == 1
    assert store.saved_evidence == 1
    assert store.finished[0][0] == "succeeded"
    assert store.finished[0][1]["history_status"] == "complete"


def test_daily_observer_resumes_durable_cursor_window() -> None:
    state = BrokerSyncState(
        user_id=USER_ID,
        account_id="account-1",
        history_window_from=datetime(2026, 9, 1, tzinfo=UTC),
        history_window_to=datetime(2026, 10, 1, tzinfo=UTC),
        pending_cursor="resume-me",
        last_complete_watermark=datetime(2026, 8, 31, tzinfo=UTC),
        updated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    store = FakeStore(state=state)
    broker = FakeBroker(
        pages={"resume-me": TBankOperationsPage(False, "", ())},
    )

    result = PortfolioObserver(
        store,
        broker,
        legal_versions=LEGAL_VERSIONS,
    ).run_user(
        USER_ID,
        now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
    )

    assert result is not None
    assert result.status == "succeeded"
    assert broker.seen_cursors == ["resume-me"]


def test_user_info_outage_degrades_but_keeps_portfolio_snapshot() -> None:
    store = FakeStore()
    broker = FakeBroker(user_info_unavailable=True)

    with (
        patch("omnicio.observer.time.sleep"),
        patch("omnicio.observer.secrets.randbelow", return_value=0),
    ):
        result = PortfolioObserver(
            store,
            broker,
            legal_versions=LEGAL_VERSIONS,
        ).run_user(
            USER_ID,
            now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
        )

    assert result is not None
    assert result.status == "degraded"
    assert result.snapshot_saved is True
    assert store.saved_snapshots == 1
    assert store.finished[0][1]["broker_user_info_status"] == "unavailable"


def test_missing_account_open_date_degrades_without_inventing_history() -> None:
    store = FakeStore()
    broker = FakeBroker(opened_at=None)

    result = PortfolioObserver(
        store,
        broker,
        legal_versions=LEGAL_VERSIONS,
    ).run_user(
        USER_ID,
        now=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
    )

    assert result is not None
    assert result.status == "degraded"
    assert broker.seen_cursors == []
    assert store.finished[0][1]["history_status"] == "opened_date_missing"


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
    assert "ON CONFLICT DO NOTHING" in store
    assert "UNIQUE (job_run_id)" in migration
    assert "job_runs_finish_state_consistent" in migration
    assert "broker_sync_state_cursor_window_consistent" in migration
    assert "pg_try_advisory_lock" in store
    assert "pg_try_advisory_xact_lock" in store
    assert "recover_running" in store
    assert "ON CONFLICT (job_run_id) DO NOTHING" in store
    assert "pending_cursor" in store


def test_instrument_required_tests_are_tenant_account_evidence() -> None:
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
    assert "INSERT INTO account_instrument_access" in store


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
    job = store.claim_daily_job(user_id, job_type="portfolio_daily", scheduled_for=date.today())
    assert job is not None
    return job


def test_native_connection_lifecycle_keeps_tenants_and_discards_old_jobs(connected_database):
    database, store, admin = connected_database
    other = UUID(int=2)
    observation = bundle()
    wrong_account = replace(observation, account_id="old")
    observed_at = datetime.now(UTC)
    window_from = datetime(2026, 1, 1, tzinfo=UTC)
    empty_page = TBankOperationsPage(items=(), has_next=False, next_cursor="")
    assert store.claim_daily_job(
        USER_ID, job_type="portfolio_daily", scheduled_for=date.today(),
    ) is None
    current = connect_user(database)
    connect_user(database, other)
    job, other_job = claim_job(store), claim_job(store, other)
    snapshot = store.save_snapshot(USER_ID, job_run_id=job.id, bundle=observation)
    other_snapshot = store.save_snapshot(
        other, job_run_id=other_job.id,
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
            USER_ID, job_run_id=job.id, snapshot_id=other_snapshot,
            documents=(), assessments=(), retrieved_at=observed_at,
        )

    # Old account rows left by a previous version cannot become the selected account.
    admin.execute("UPDATE portfolio_snapshots SET account_id='legacy' WHERE id=%s", (snapshot,))
    assert store.portfolio_visualization(USER_ID)["status"] == "pending"
    assert store.latest_intelligence(USER_ID) is None
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
            USER_ID, job_run_id=job.id, snapshot_id=snapshot,
            documents=(), assessments=(), retrieved_at=observed_at,
        )
    with pytest.raises(ObservationCancelled):
        store.save_history_page(
            USER_ID, job_run_id=job.id, account_id="account-1", environment="prod",
            window_from=window_from, window_to=observed_at,
            page=empty_page,
            observed_at=observed_at,
        )
    assert not store.finish_job(USER_ID, job.id, status="succeeded", details={})
    assert store.sync_state(USER_ID, "account-1") is None
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
