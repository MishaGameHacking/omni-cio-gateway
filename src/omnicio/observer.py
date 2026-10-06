"""Daily read-only portfolio observer with durable restart and pagination state."""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from threading import BoundedSemaphore, Event, Thread
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from .broker import BrokerConnectionError, BrokerObservationBundle, BrokerService
from .config import load_settings
from .db import Database
from .intelligence import build_tbank_evidence
from .portfolio_store import BrokerSyncState, JobRunRecord, ObservationCancelled, PortfolioStore
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable

logger = logging.getLogger(__name__)

JOB_TYPE = "portfolio_daily"
MOSCOW = ZoneInfo("Europe/Moscow")
MAX_WORKERS = 2
MAX_HISTORY_PAGES_PER_RUN = 20
HISTORY_PAGE_SIZE = 1000
HISTORY_CORRECTION_OVERLAP = timedelta(days=7)
PROVIDER_READ_ATTEMPTS = 3


class PortfolioRefreshBusy(RuntimeError):
    """The bounded request admission slots are temporarily occupied."""


class ObservationInterrupted(RuntimeError):
    """Shutdown leaves a durable unfinished run for recovery after restart."""


def _checkpoint(should_stop: Callable[[], bool] | None) -> None:
    if should_stop is not None and should_stop():
        raise ObservationInterrupted("observer_stopping")


def _history_window(
    state: BrokerSyncState | None,
    account_opened_at: datetime | None,
    now: datetime,
) -> tuple[datetime, datetime, str] | Literal[
    "opened_date_missing",
    "opened_date_invalid",
]:
    if state is not None and state.pending_cursor:
        if state.history_window_from is None or state.history_window_to is None:
            raise RuntimeError("history cursor has no durable window")
        return state.history_window_from, state.history_window_to, state.pending_cursor

    if account_opened_at is None:
        return "opened_date_missing"
    opened_at = account_opened_at.astimezone(UTC)
    if opened_at > now:
        return "opened_date_invalid"

    window_from = opened_at
    if state is not None and state.last_complete_watermark is not None:
        window_from = max(
            opened_at,
            state.last_complete_watermark - HISTORY_CORRECTION_OVERLAP,
        )
    return window_from, now, ""


def provider_read[T](operation: Callable[[], T]) -> T:
    """Retry idempotent provider reads with bounded exponential jitter."""
    for attempt in range(PROVIDER_READ_ATTEMPTS):
        try:
            return operation()
        except TBankUnavailable:
            if attempt + 1 == PROVIDER_READ_ATTEMPTS:
                raise
            base = min(8.0, 2.0**attempt)
            jitter = secrets.randbelow(1001) / 1000
            delay = base * (0.75 + jitter * 0.5)
            time.sleep(delay)
    raise RuntimeError("provider read retry loop exhausted")


@dataclass(frozen=True, slots=True)
class UserObservationResult:
    user_id: UUID
    status: str
    snapshot_saved: bool
    history_pages: int
    history_items_inserted: int


def _confirmed_job_result(result: UserObservationResult, persisted: bool) -> UserObservationResult:
    if persisted:
        return result
    return UserObservationResult(result.user_id, "degraded", False, 0, 0)


@dataclass(frozen=True, slots=True)
class ObserverRunResult:
    total_users: int
    claimed_jobs: int
    succeeded: int
    degraded: int
    failed: int


class PortfolioObserver:
    def __init__(
        self,
        store: PortfolioStore,
        broker: BrokerService,
        *,
        legal_versions: dict[str, str],
    ) -> None:
        self.store = store
        self.broker = broker
        self.legal_versions = dict(legal_versions)

    def run(self, *, now: datetime | None = None) -> ObserverRunResult:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self.store.observer_lock() as locked:
            if not locked:
                logger.info("portfolio observer skipped because another run holds the lock")
                return ObserverRunResult(0, 0, 0, 0, 0)
            return self._run_locked(observed_at)

    def _run_locked(self, observed_at: datetime) -> ObserverRunResult:
        user_ids = self.store.observer_user_ids(self.legal_versions)
        if not user_ids:
            return ObserverRunResult(0, 0, 0, 0, 0)

        results: list[UserObservationResult] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as workers:
            futures = {
                workers.submit(
                    self.run_user,
                    user_id,
                    now=observed_at,
                    recover_running=True,
                ): user_id
                for user_id in user_ids
            }
            for future in as_completed(futures):
                user_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - job boundary records safe class only
                    logger.exception(
                        "portfolio observer failed user=%s error_type=%s",
                        user_id,
                        type(exc).__name__,
                        exc_info=None,
                    )
                    results.append(
                        UserObservationResult(
                            user_id=user_id,
                            status="failed",
                            snapshot_saved=False,
                            history_pages=0,
                            history_items_inserted=0,
                        )
                    )
                else:
                    if result is not None:
                        results.append(result)

        return ObserverRunResult(
            total_users=len(user_ids),
            claimed_jobs=len(results),
            succeeded=sum(item.status == "succeeded" for item in results),
            degraded=sum(item.status == "degraded" for item in results),
            failed=sum(item.status == "failed" for item in results),
        )

    def run_user(
        self,
        user_id: UUID,
        *,
        now: datetime,
        recover_running: bool = False,
    ) -> UserObservationResult | None:
        if now.tzinfo is None:
            raise ValueError("observer time must be timezone-aware")
        now = now.astimezone(UTC)
        scheduled_for = now.astimezone(MOSCOW).date()
        job = self.store.claim_daily_job(
            user_id,
            job_type=JOB_TYPE,
            scheduled_for=scheduled_for,
            recover_running=recover_running,
        )
        if job is None:
            return None
        return self.run_job(job, now=now)

    def run_job(
        self, job: JobRunRecord, *, now: datetime,
        should_stop: Callable[[], bool] | None = None,
    ) -> UserObservationResult:
        """Observe one already claimed daily or manual job; never execute orders."""
        if now.tzinfo is None:
            raise ValueError("observer time must be timezone-aware")
        now = now.astimezone(UTC)
        details: dict[str, object] = {
            "job": job.job_type,
            "scheduled_for": job.scheduled_for.isoformat(),
            "snapshot_saved": False,
            "history_pages": 0,
            "history_new_observations": 0,
        }
        status: Literal["succeeded", "degraded"] = "degraded"
        try:
            self._observe_job(job, now, details, should_stop)
            status = "degraded" if self._degraded(details) else "succeeded"
        except ObservationInterrupted:
            raise
        except ObservationCancelled:
            details.update(stage_error="ObservationCancelled", snapshot_saved=False,
                           history_pages=0, history_new_observations=0)
        except (
            BrokerConnectionError,
            TBankTokenRejected,
            TBankUnavailable,
            ValueError,
        ) as exc:
            details["stage_error"] = type(exc).__name__
        except Exception as exc:
            self._record_failure(job, details, exc)
            raise
        finished = self.store.finish_job(job.user_id, job.id, status=status, details=details)
        return _confirmed_job_result(UserObservationResult(
            user_id=job.user_id, status=status, snapshot_saved=bool(details["snapshot_saved"]),
            history_pages=cast(int, details["history_pages"]),
            history_items_inserted=cast(int, details["history_new_observations"]),
        ), finished)

    def _record_failure(
        self, job: JobRunRecord, details: dict[str, object], exc: Exception,
    ) -> None:
        details["stage_error"] = type(exc).__name__
        try:
            self.store.finish_job(job.user_id, job.id, status="failed", details=details)
        except Exception as finish_exc:  # noqa: BLE001 - retain original infrastructure failure
            # Provider/SQL exceptions may carry credentials; never attach a traceback.
            logger.exception(
                "portfolio observer could not persist failure user=%s error_type=%s",
                job.user_id, type(finish_exc).__name__, exc_info=None,
            )

    def _observe_job(
        self, job: JobRunRecord, now: datetime, details: dict[str, object],
        should_stop: Callable[[], bool] | None,
    ) -> None:
        _checkpoint(should_stop)
        bundle, snapshot_id, opened_at = self._snapshot(job, details)
        _checkpoint(should_stop)
        self._evidence(job, bundle, snapshot_id, now, details)
        _checkpoint(should_stop)
        profile = self.store.current_profile(job.user_id)
        details["profile_version"] = profile.version if profile else None
        pages, inserted, history_status = self._sync_history(
            job.user_id, job_run_id=job.id, account_id=bundle.account_id,
            environment=bundle.environment, account_opened_at=opened_at,
            now=max(now, bundle.refreshed_at), should_stop=should_stop,
        )
        details.update(history_pages=pages, history_new_observations=inserted,
                       history_status=history_status)

    def _snapshot(
        self, job: JobRunRecord, details: dict[str, object],
    ) -> tuple[BrokerObservationBundle, UUID, datetime | None]:
        user_id = job.user_id
        account = provider_read(lambda: self.broker.revalidate_account(user_id))
        details.update(account_access=account.access_level, account_status=account.status,
                       account_type=account.type)
        user_info = None
        try:
            user_info = provider_read(lambda: self.broker.user_info(user_id))
        except TBankUnavailable:
            details["broker_user_info_status"] = "unavailable"
        else:
            details.update(
                broker_user_info_status="received", broker_qualified=user_info.qualified,
                broker_qualified_for_work_with=list(user_info.qualified_for_work_with),
                broker_risk_level_code=user_info.risk_level_code, broker_tariff=user_info.tariff,
            )
        bundle = provider_read(lambda: self.broker.observation_bundle(user_id, full_catalog=True))
        snapshot_id = self.store.save_snapshot(
            user_id, job_run_id=job.id, bundle=bundle, account=account, user_info=user_info,
        )
        details.update(
            snapshot_saved=True, analysis_status=bundle.analysis.status,
            catalog_status=next((source.status for source in bundle.sources
                                 if source.id == "catalog"), "not_requested"),
        )
        return bundle, snapshot_id, account.opened_at

    def _evidence(
        self, job: JobRunRecord, bundle: BrokerObservationBundle, snapshot_id: UUID,
        now: datetime, details: dict[str, object],
    ) -> None:
        evidence = provider_read(lambda: self.broker.evidence(job.user_id, bundle, now=now))
        documents, assessments = build_tbank_evidence(bundle, evidence, assessed_at=now)
        new_documents, new_assessments = self.store.save_evidence(
            job.user_id, job_run_id=job.id, snapshot_id=snapshot_id, documents=documents,
            assessments=assessments, retrieved_at=evidence.refreshed_at,
        )
        details.update(
            evidence_documents_new=new_documents, risk_assessments_new=new_assessments,
            evidence_sources={source.id: source.status for source in evidence.sources},
            credit_rating_status="data_missing",
            risk_states={
                state: sum(item.state == state for item in assessments)
                for state in ("data_missing", "normal", "watch", "elevated", "critical",
                              "confirmed_default")
            },
        )

    @staticmethod
    def _degraded(details: dict[str, object]) -> bool:
        return (
            details["analysis_status"] != "observed"
            or details["catalog_status"] == "partial"
            or details["broker_user_info_status"] != "received"
            or details["history_status"] != "complete"
            or any(value != "received" for key, value in
                   cast(dict[str, str], details["evidence_sources"]).items()
                   if key != "credit_ratings")
        )

    def _sync_history(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        account_id: str,
        environment: str,
        account_opened_at: datetime | None,
        now: datetime,
        should_stop: Callable[[], bool] | None = None,
    ) -> tuple[int, int, str]:
        state = self.store.sync_state(user_id, account_id)
        window = _history_window(state, account_opened_at, now)
        if isinstance(window, str):
            return 0, 0, window
        window_from, window_to, cursor = window

        seen_cursors = {cursor} if cursor else set()
        inserted = 0
        for page_number in range(1, MAX_HISTORY_PAGES_PER_RUN + 1):
            _checkpoint(should_stop)
            page = provider_read(
                partial(
                    self.broker.history_page,
                    user_id,
                    from_at=window_from,
                    to_at=window_to,
                    cursor=cursor,
                    limit=HISTORY_PAGE_SIZE,
                )
            )
            if page.has_next and page.next_cursor in seen_cursors:
                raise RuntimeError("T-Invest operation pagination cursor repeated")

            inserted += self.store.save_history_page(
                user_id,
                job_run_id=job_run_id,
                account_id=account_id,
                environment=environment,
                window_from=window_from,
                window_to=window_to,
                page=page,
                observed_at=now,
            )
            if not page.has_next:
                if window_to >= now:
                    return page_number, inserted, "complete"
                # Finishing a resumed cursor only covers its original window.
                # Catch up to this snapshot without exceeding the shared page
                # budget; each completed watermark remains durable on failure.
                window_from = max(window_from, window_to - HISTORY_CORRECTION_OVERLAP)
                window_to, cursor = now, ""
                seen_cursors.clear()
            else:
                seen_cursors.add(page.next_cursor)
                cursor = page.next_cursor

        return MAX_HISTORY_PAGES_PER_RUN, inserted, "continuation_pending"


class PortfolioRefreshCoordinator:
    """One bounded worker per process, backed by durable owner-scoped job records."""

    def __init__(
        self, store: PortfolioStore, broker: BrokerService, *, legal_versions: dict[str, str],
    ) -> None:
        self.store = store
        self.observer = PortfolioObserver(store, broker, legal_versions=legal_versions)
        self.legal_versions = dict(legal_versions)
        self._requests = BoundedSemaphore(2)
        self._wake = Event()
        self._stopping = Event()
        self._worker: Thread | None = None
        self._last_user: UUID | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        worker = Thread(target=self._loop, name="portfolio-refresh", daemon=True)
        worker.start()
        self._worker = worker

    def close(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._worker is not None:
            # An in-flight provider request has its own timeout. An unfinished
            # durable job is recovered after restart; shutdown never marks it fresh.
            self._worker.join(timeout=5)

    def request(self, user_id: UUID) -> dict[str, object]:
        if self._stopping.is_set() or not self._requests.acquire(blocking=False):
            raise PortfolioRefreshBusy("portfolio_refresh_busy")
        try:
            result = self.store.request_refresh(user_id, self.legal_versions)
            self._wake.set()
            return result
        finally:
            self._requests.release()

    def status(self, user_id: UUID) -> dict[str, object]:
        return self.store.refresh_status(user_id)

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                self.run_pending()
            except Exception as exc:  # noqa: BLE001 - persistent worker boundary, safe class only
                logger.exception("portfolio refresh worker error_type=%s",
                                 type(exc).__name__, exc_info=None)
            self._wake.wait(timeout=2)
            self._wake.clear()

    def run_pending(self) -> bool:
        """Process at most one run; the daily observer shares the same lock."""
        if self._stopping.is_set():
            return False
        with self.store.observer_lock() as locked:
            if not locked:
                return False
            users = self.store.observer_user_ids(self.legal_versions)
            ordered = self._fair_order(users)
            for user_id in ordered:
                job = self.store.claim_refresh_job(user_id, self.legal_versions)
                if job is not None:
                    self._last_user = user_id
                    self._run_claimed(job)
                    return True
        return False

    def _fair_order(self, users: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if self._last_user not in users:
            return users
        offset = users.index(self._last_user) + 1
        return users[offset:] + users[:offset]

    def _run_claimed(self, job: JobRunRecord) -> None:
        try:
            self.observer.run_job(job, now=datetime.now(UTC), should_stop=self._stopping.is_set)
        except ObservationInterrupted:
            return
        finally:
            if not self._stopping.is_set():
                # Connection/consent changes can prevent finish_job from writing.
                # Settle only the remaining active job, never reopen a terminal one.
                self.store.fail_refresh_job(job.user_id, job.id, "observation_interrupted")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_settings()
    database = Database(cfg.database_url)
    database.open()
    try:
        store = PortfolioStore(database)
        broker = BrokerService(
            database,
            credential_key=cfg.broker_token_crypto_key,
            tbank=TBankInvestClient(),
        )
        result = PortfolioObserver(
            store,
            broker,
            legal_versions={
                "privacy_policy": cfg.privacy_version,
                "personal_data_consent": cfg.consent_version,
                "terms": cfg.terms_version,
            },
        ).run()
        logger.info(
            "portfolio observer complete users=%s claimed=%s succeeded=%s degraded=%s failed=%s",
            result.total_users,
            result.claimed_jobs,
            result.succeeded,
            result.degraded,
            result.failed,
        )
        return 1 if result.failed else 0
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
