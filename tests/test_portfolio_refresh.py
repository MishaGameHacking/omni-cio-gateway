"""The manual observation worker reuses read-only evidence and bounded history."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Event, Lock
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest
from test_observer import LEGAL_VERSIONS, USER_ID, FakeBroker, FakeStore

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

    @contextmanager
    def observer_lock(self) -> Iterator[bool]:
        self.locked = self.lock_available
        try:
            yield self.locked
        finally:
            self.locked = False

    def claim_refresh_job(self, user_id: UUID, versions: dict[str, str]):
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
    assert broker.seen_cursors == ["", "cursor-2"]
    status, details = store.finished[0]
    assert status == "succeeded"
    assert details["job"] == "portfolio_refresh"
    assert details["scheduled_for"] is None
    assert details["history_status"] == "complete"
    assert details["history_pages"] == 2
    assert not coordinator.run_pending()


def test_refresh_does_not_claim_or_read_broker_while_daily_observer_holds_global_lock() -> None:
    store = RefreshStore()
    store.lock_available = False
    broker = Mock()
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    assert not coordinator.run_pending()
    assert len(store.jobs) == 1
    assert broker.mock_calls == []


def test_refresh_history_limit_is_partial_and_retains_the_continuation_cursor() -> None:
    store, broker = RefreshStore(), FakeBroker()
    coordinator = PortfolioRefreshCoordinator(store, broker, legal_versions=LEGAL_VERSIONS)
    with patch("omnicio.observer.MAX_HISTORY_PAGES_PER_RUN", 1):
        assert coordinator.run_pending()
    assert broker.seen_cursors == [""]
    assert store.saved_pages == ["cursor-2"]
    status, details = store.finished[0]
    assert status == "degraded"
    assert details["history_status"] == "continuation_pending"
    assert details["snapshot_saved"] is True


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

    def enqueue(owner: UUID, versions: dict[str, str]) -> dict[str, object]:
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
    store.request_refresh.assert_called_with(USER_ID, LEGAL_VERSIONS)


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
