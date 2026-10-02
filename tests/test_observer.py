from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from omnicio.broker import AnalysisSource, BrokerObservationBundle
from omnicio.observer import PortfolioObserver, provider_read
from omnicio.portfolio import PortfolioAnalysis
from omnicio.portfolio_store import BrokerSyncState, JobRunRecord
from omnicio.tbank import (
    TBankAccount,
    TBankMoney,
    TBankOperationsPage,
    TBankPortfolio,
    TBankPositions,
    TBankUnavailable,
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
        self.claimed = False

    def observer_user_ids(self, legal_versions: dict[str, str]) -> tuple[UUID, ...]:
        assert legal_versions == LEGAL_VERSIONS
        return (USER_ID,)

    def claim_daily_job(self, user_id: UUID, *, job_type: str, scheduled_for: date):
        assert user_id == USER_ID
        assert job_type == "portfolio_daily"
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

    def current_profile(self, user_id: UUID):
        assert user_id == USER_ID
        return None

    def save_snapshot(self, user_id: UUID, *, job_run_id: UUID, bundle):
        assert user_id == USER_ID
        assert job_run_id
        assert bundle.account_id == "account-1"
        self.saved_snapshots += 1
        return uuid4()

    def sync_state(self, user_id: UUID, account_id: str):
        assert user_id == USER_ID
        assert account_id == "account-1"
        return self.state

    def save_history_page(
        self,
        user_id: UUID,
        *,
        account_id: str,
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
    ) -> None:
        self.pages = pages or {
            "": TBankOperationsPage(True, "cursor-2", ()),
            "cursor-2": TBankOperationsPage(False, "", ()),
        }
        self.opened_at = opened_at
        self.analysis_status = analysis_status
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

    def observation_bundle(
        self,
        user_id: UUID,
        *,
        full_catalog: bool = False,
    ) -> BrokerObservationBundle:
        assert user_id == USER_ID
        assert full_catalog is True
        return bundle(self.analysis_status)

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
        patch("omnicio.observer.random.random", side_effect=[0.0, 1.0]),
        patch("omnicio.observer.time.sleep") as sleep,
    ):
        assert provider_read(operation) == "ok"

    assert attempts == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.75, 2.5]


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
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text()
    store = (root / "src" / "omnicio" / "portfolio_store.py").read_text()

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
    assert "UNIQUE (job_run_id)" in migration
    assert "job_runs_finish_state_consistent" in migration
    assert "broker_sync_state_cursor_window_consistent" in migration
    assert "pg_try_advisory_xact_lock" in store
    assert "ON CONFLICT (job_run_id) DO NOTHING" in store
    assert "pending_cursor" in store


def test_account_specific_required_tests_are_not_global_catalog_metadata() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text()
    store = (root / "src" / "omnicio" / "portfolio_store.py").read_text()

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
    migration = (root / "migrations" / "0006_portfolio_observer.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS issuer_groups" in migration
    assert "CREATE TABLE IF NOT EXISTS issuers" in migration
    assert "CREATE TABLE IF NOT EXISTS instrument_issuer_map" in migration
    assert "source_url text NOT NULL" in migration
    assert "verified_at timestamptz NOT NULL" in migration
    assert "INSERT INTO issuers" not in migration
