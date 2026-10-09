"""The observation worker refreshes holdings without reading personal history."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event, Lock
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest
from test_observer import LEGAL_VERSIONS, USER_ID, FakeBroker, FakeStore, bundle

from omnicio.observer import (
    ObservationInterrupted,
    PortfolioObserver,
    PortfolioRefreshBusy,
    PortfolioRefreshCoordinator,
)
from omnicio.portfolio_store import JobRunRecord, PortfolioStore

NOW = datetime(2026, 10, 6, 10, tzinfo=UTC)


def manual_job(owner: UUID = USER_ID) -> JobRunRecord:
    return JobRunRecord(uuid4(), owner, "portfolio_refresh", None, "running", 1, NOW, None)


class RefreshStore(FakeStore):
    def __init__(self) -> None:
        super().__init__()
        self.jobs = [manual_job()]
        self.locked = False
        self.completed = Event()
        self.mutex = Lock()

    @contextmanager
    def observer_lock(self, user_id: UUID | None = None) -> Iterator[bool]:
        acquired = self.lock_available and self.mutex.acquire(blocking=False)
        if acquired:
            self.locked = True
        try:
            yield acquired
        finally:
            if acquired:
                self.locked = False
                self.mutex.release()

    def claim_refresh_job(
        self, user_id: UUID, versions: dict[str, str], *, schedule_if_due: bool = False,
    ):
        assert self.locked
        assert versions == LEGAL_VERSIONS
        assert user_id == USER_ID
        return self.jobs.pop(0) if self.jobs else None

    def fail_refresh_job(self, user_id: UUID, job_id: UUID, reason: str) -> None:
        assert self.locked
        assert reason == "observation_interrupted"
        self.completed.set()


def test_refresh_reuses_full_read_only_observation_and_keeps_daily_identity_separate() -> None:
    store, broker = RefreshStore(), FakeBroker()
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert coordinator.run_pending()
    assert not store.claimed  # Manual refresh does not claim/relabel a daily result.
    assert store.saved_snapshots == 1
    assert store.saved_evidence == 1
    assert broker.seen_cursors == []
    status, details = store.finished[0]
    assert status == "succeeded"
    assert details["job"] == "portfolio_refresh"
    assert details["scheduled_for"] is None
    assert details["history_status"] == "not_collected"
    assert details["history_pages"] == 0
    assert details["broker_user_info_status"] == "not_collected"
    assert not coordinator.run_pending()


def test_refresh_does_not_claim_or_read_broker_while_daily_observer_holds_global_lock() -> None:
    store = RefreshStore()
    store.lock_available = False
    broker = Mock()
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert not coordinator.run_pending()
    assert len(store.jobs) == 1
    assert broker.mock_calls == []


def test_worker_prioritizes_existing_other_owner_request_before_automatic_observation() -> None:
    other = UUID(int=2)
    store = Mock(spec=PortfolioStore)
    store.database = Mock()
    store.observer_user_ids.return_value = (USER_ID, other)
    store.observer_lock.side_effect = lambda owner: nullcontext(True)
    store.claim_pending_daily_job.return_value = None
    manual = manual_job(other)
    automatic = replace(manual_job(), refresh_scope="quick")
    pending = [manual]

    def claim(owner, versions, *, schedule_if_due=False):
        assert versions == LEGAL_VERSIONS
        if owner == other and pending:
            return pending.pop()
        return automatic if owner == USER_ID and schedule_if_due else None

    store.claim_refresh_job.side_effect = claim
    coordinator = PortfolioRefreshCoordinator(store, Mock(), legal_versions=LEGAL_VERSIONS)
    coordinator.observer.run_job = Mock()
    assert coordinator.run_pending()
    assert coordinator.observer.run_job.call_args.args[0] == manual
    assert not any(call.kwargs.get("schedule_if_due")
                   for call in store.claim_refresh_job.call_args_list)
    # With no browser request left, the same running worker admits automatic work.
    assert coordinator.run_pending()
    assert coordinator.observer.run_job.call_args.args[0] == automatic


def test_manual_worker_completes_dated_request_after_daily_lock_contention() -> None:
    store, broker = RefreshStore(), FakeBroker()
    store.jobs.clear()
    store.lock_available = False
    daily = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
    result = daily.run(now=NOW)
    assert result.deferred
    assert store.scheduled == [NOW.date()]
    assert store.saved_snapshots == 0
    store.lock_available = True
    worker = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert worker.run_pending()
    assert store.saved_snapshots == 1
    assert store.finished[0][1]["job"] == "portfolio_daily"
    assert not worker.run_pending()
    assert store.saved_snapshots == 1


@pytest.mark.parametrize("scope", ["full", "quick"])
def test_refresh_never_reads_or_persists_personal_profile_or_operations(scope: str) -> None:
    store, broker = RefreshStore(), FakeBroker()
    store.jobs = [replace(store.jobs[0], refresh_scope=scope)]
    broker.observation_bundle = Mock(return_value=bundle("observed"))
    broker.user_info = Mock(side_effect=AssertionError("personal profile read is forbidden"))
    broker.history_page = Mock(side_effect=AssertionError("operation history read is forbidden"))
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert coordinator.run_pending()
    broker.user_info.assert_not_called()
    broker.history_page.assert_not_called()
    assert store.saved_pages == []
    assert store.saved_windows == []
    _, details = store.finished[0]
    assert details["history_status"] == "not_collected"
    assert details["history_pages"] == 0
    assert details["history_new_observations"] == 0
    assert details["broker_user_info_status"] == "not_collected"
    assert details["snapshot_saved"] is True


def test_quick_refresh_saves_nav_without_history_or_full_enrichment() -> None:
    store, broker = RefreshStore(), FakeBroker()
    store.jobs = [replace(store.jobs[0], refresh_scope="quick")]
    observed = bundle("partial")
    observed = replace(observed, analysis=replace(observed.analysis, valuation_status="complete"))
    broker.observation_bundle = Mock(return_value=observed)
    broker.evidence = Mock(side_effect=AssertionError("quick refresh must defer fundamentals"))
    broker.user_info = Mock(side_effect=AssertionError("quick refresh must not read user profile"))
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert coordinator.run_pending()
    broker.observation_bundle.assert_called_once_with(USER_ID, quick=True)
    assert store.saved_snapshots == 1
    assert store.saved_evidence == 0
    assert broker.seen_cursors == []
    status, details = store.finished[0]
    assert status == "succeeded"
    assert details["analysis_status"] == "partial"
    assert details["valuation_status"] == "complete"
    assert details["history_status"] == "not_collected"
    assert details["evidence_status"] == "deferred_to_full_refresh"


def test_quick_refresh_never_retries_a_failed_provider_read_or_marks_it_fresh() -> None:
    from omnicio.tbank import TBankUnavailable

    store, broker = RefreshStore(), FakeBroker()
    store.jobs = [replace(store.jobs[0], refresh_scope="quick")]
    broker.revalidate_account = Mock(side_effect=TBankUnavailable("provider unavailable"))
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    with patch("omnicio.observer.time.sleep") as sleep:
        assert coordinator.run_pending()
    broker.revalidate_account.assert_called_once()
    sleep.assert_not_called()
    assert store.saved_snapshots == 0
    assert store.finished[0][0] == "degraded"
    assert store.finished[0][1]["snapshot_saved"] is False


def test_refresh_with_incomplete_portfolio_never_reports_complete_success() -> None:
    store, broker = RefreshStore(), FakeBroker(analysis_status="partial")
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert coordinator.run_pending()
    status, details = store.finished[0]
    assert status == "degraded"
    assert details["analysis_status"] == "partial"
    assert details["snapshot_saved"] is True


def test_shutdown_after_snapshot_leaves_job_unfinished_for_durable_recovery() -> None:
    store, broker = RefreshStore(), FakeBroker()
    observer = PortfolioObserver(store, broker, legal_versions=LEGAL_VERSIONS)
    with pytest.raises(ObservationInterrupted):
        observer.run_job(store.jobs[0], now=NOW, should_stop=lambda: store.saved_snapshots == 1)
    assert store.saved_snapshots == 1
    assert store.saved_evidence == 0
    assert broker.seen_cursors == []
    assert store.finished == []


def test_refresh_enqueue_admission_is_bounded_and_released_after_failure() -> None:
    store = Mock(spec=PortfolioStore)
    coordinator = PortfolioRefreshCoordinator(store, Mock(), legal_versions=LEGAL_VERSIONS)
    ready, release, mutex = Event(), Event(), Lock()
    admitted = 0

    def enqueue(owner: UUID, versions: dict[str, str], *, scope: str) -> dict[str, object]:
        assert scope == "full"
        nonlocal admitted
        with mutex:
            admitted += 1
            if admitted == 2:
                ready.set()
        assert release.wait(timeout=5)
        raise RuntimeError("synthetic storage failure")

    store.request_refresh.side_effect = enqueue
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(coordinator.request, USER_ID) for _ in range(2)]
        try:
            assert ready.wait(timeout=5)
            with pytest.raises(PortfolioRefreshBusy):
                coordinator.request(USER_ID)
            assert store.request_refresh.call_count == 2
        finally:
            release.set()
        for future in futures:
            with pytest.raises(RuntimeError, match="synthetic storage"):
                future.result(timeout=5)
    store.request_refresh.side_effect = None
    store.request_refresh.return_value = {"status": "queued", "job_id": "server-job"}
    assert coordinator.request(USER_ID) == {"status": "queued", "job_id": "server-job"}
    store.request_refresh.assert_called_with(USER_ID, LEGAL_VERSIONS, scope="full")


def test_worker_start_recovers_existing_queue_and_shutdown_rejects_new_work() -> None:
    store = RefreshStore()
    coordinator = PortfolioRefreshCoordinator(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)
    coordinator.start()
    worker = coordinator._worker
    try:
        coordinator.start()
        assert coordinator._worker is worker
        assert store.completed.wait(timeout=5)
    finally:
        coordinator.close()
    assert worker is not None
    assert not worker.is_alive()
    assert store.finished[0][0] == "succeeded"
    with pytest.raises(PortfolioRefreshBusy):
        coordinator.request(USER_ID)


def test_provider_exception_is_settled_without_leaking_its_text_or_traceback(caplog) -> None:
    store = RefreshStore()
    coordinator = PortfolioRefreshCoordinator(store, FakeBroker(), legal_versions=LEGAL_VERSIONS)
    attempted = Event()

    def fail() -> bool:
        attempted.set()
        raise RuntimeError("private-token-value")

    with patch.object(coordinator, "run_pending", side_effect=fail):
        coordinator.start()
        try:
            assert attempted.wait(timeout=5)
        finally:
            coordinator.close()
    assert "error_type=RuntimeError" in caplog.text
    assert "private-token-value" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
