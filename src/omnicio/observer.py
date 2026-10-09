"""Daily read-only portfolio observer with durable restart and pagination state."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from threading import BoundedSemaphore, Event, Thread
from typing import Literal, TypedDict, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from .broker import BrokerConnectionError, BrokerObservationBundle, BrokerService
from .config import load_settings
from .db import Database
from .intelligence import build_news_evidence, build_tbank_evidence, held_news_instrument_uids
from .monitoring import (
    HISTORY_CORRECTION_OVERLAP,
    MAX_HISTORY_PAGES_PER_RUN,
    MAX_WORKERS,
    NEWS_BUDGET_SECONDS,
    NEWS_MAX_COMPLETED_CURSORS,
    NEWS_MAX_CONTINUATIONS,
    NEWS_MAX_PAGES_PER_RUN,
    NEWS_MAX_PATH_PROOFS,
    PROVIDER_READ_ATTEMPTS,
    QUICK_REFRESH_BUDGET_SECONDS,
    REFRESH_ADMISSION_SLOTS,
    WORKER_POLL_SECONDS,
    WORKER_SHUTDOWN_SECONDS,
)
from .portfolio_store import BrokerSyncState, JobRunRecord, ObservationCancelled, PortfolioStore
from .tbank import (
    NEWS_MAX_PAGE_SIZE,
    OPERATIONS_MAX_PAGE_SIZE,
    TBankInvestClient,
    TBankTokenRejected,
    TBankUnavailable,
)

logger = logging.getLogger(__name__)

JOB_TYPE = "portfolio_daily"
MOSCOW = ZoneInfo("Europe/Moscow")
_AWARE_OBSERVER_TIME_REQUIRED = "observer time must be timezone-aware"


class PortfolioRefreshBusy(RuntimeError):
    """The bounded request admission slots are temporarily occupied."""


class ObservationInterrupted(RuntimeError):
    """Shutdown leaves a durable unfinished run for recovery after restart."""


def _checkpoint(should_stop: Callable[[], bool] | None) -> None:
    if should_stop is not None and should_stop():
        raise ObservationInterrupted("observer_stopping")


class NewsContinuation(TypedDict):
    cursor: str
    seen_cursors: list[str]


def _bound_news_proofs(state: dict[str, object]) -> None:
    paths = cast(list[NewsContinuation], state["continuations"])
    per_path = max(1, NEWS_MAX_PATH_PROOFS // max(1, len(paths)))
    for path in paths:
        path["seen_cursors"] = list(dict.fromkeys(path["seen_cursors"]))[-per_path:]
    completed = cast(list[str], state["completed_cursors"])
    state["completed_cursors"] = list(dict.fromkeys(completed))[-NEWS_MAX_COMPLETED_CURSORS:]


def _news_state(previous: dict[str, object], held_uids: frozenset[str]) -> dict[str, object]:
    paths = deepcopy(cast(list[NewsContinuation], previous.get("continuations", [])))
    if "continuations" not in previous and previous.get("cursor") is not None:
        paths = [{"cursor": cast(str, previous["cursor"]),
                  "seen_cursors": list(cast(list[str], previous.get("seen_cursors", [])))}]
    holdings = hashlib.sha256(json.dumps(sorted(held_uids)).encode("utf-8")).hexdigest()
    same_holdings = previous.get("holdings") == holdings
    if not same_holdings:
        # Previously read pages were filtered against a different set of holdings.
        for path in paths:
            path["seen_cursors"] = []
    state: dict[str, object] = {
        "continuations": paths,
        # A finished traversal never suppresses the next scan for source corrections.
        "completed_cursors": previous.get("completed_cursors", [])
        if paths and same_holdings else [],
        "holdings": holdings, "recovery_required": previous.get("recovery_required", False),
        "coverage_reset_at": previous.get("coverage_reset_at"), "reset_in_run": False,
        "status": "partial", "observed_at": previous.get("observed_at"),
        "pages": 0, "scanned_items": 0, "documents_new": 0, "scope": "held_instrument_links",
    }
    _bound_news_proofs(state)
    return state


def _news_path_for(paths: list[NewsContinuation], cursor: str) -> NewsContinuation | None:
    return next((path for path in paths
                 if cursor == path["cursor"] or cursor in path["seen_cursors"]), None)


def _enqueue_news_head(state: dict[str, object], cursor: str | None, observed_at: str) -> None:
    if cursor is None or cursor in cast(list[str], state["completed_cursors"]):
        return
    paths = cast(list[NewsContinuation], state["continuations"])
    existing = _news_path_for(paths, cursor)
    if existing is not None:
        # Keep the head's proof while a long static continuation advances behind it.
        if cursor in existing["seen_cursors"]:
            existing["seen_cursors"].remove(cursor)
            existing["seen_cursors"].append(cursor)
        return
    if len(paths) >= NEWS_MAX_CONTINUATIONS:
        # The bounded queue cannot promise its old coverage. Restart from this
        # successfully received head, retaining a visible partial recovery state.
        paths.clear()
        state.update(completed_cursors=[], recovery_required=True,
                     coverage_reset_at=observed_at, reset_in_run=True)
    paths.append({"cursor": cursor, "seen_cursors": []})


def _advance_news_path(state: dict[str, object], cursor: str, next_cursor: str | None) -> None:
    paths = cast(list[NewsContinuation], state["continuations"])
    path = paths.pop(0)
    if path["cursor"] != cursor:
        raise ValueError("news continuation changed before commit")
    visited = [*path["seen_cursors"], cursor]
    if next_cursor in visited:
        # A cycle is unfinished work. Forgetting its proof permits a later fixed
        # provider response to recover without ever declaring the loop complete.
        paths.append({"cursor": next_cursor, "seen_cursors": []})
        state["recovery_required"] = True
        return
    completed = cast(list[str], state["completed_cursors"])
    if next_cursor is None or next_cursor in completed:
        completed.extend(visited)
        return
    existing = _news_path_for(paths, next_cursor)
    if existing is not None:
        existing["seen_cursors"].extend(visited)
    else:
        paths.append({"cursor": next_cursor, "seen_cursors": visited})


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


def provider_read[T](operation: Callable[[], T], *, retry: bool = True) -> T:
    """Retry idempotent provider reads with bounded exponential jitter."""
    if not retry:
        return operation()
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
    deferred: bool = False


def _scheduled_day(now: datetime) -> date:
    # The recurring recovery timer may also run before today's scheduled time.
    # In that case it resumes the latest already-due day instead of collecting
    # tomorrow's daily slot at midnight.
    return (now.astimezone(MOSCOW) - timedelta(hours=6, minutes=15)).date()


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
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError(_AWARE_OBSERVER_TIME_REQUIRED)
        observed_at = now.astimezone(UTC)
        user_ids = self.store.observer_user_ids()
        for user_id in user_ids:
            self.store.schedule_daily_job(user_id, scheduled_for=_scheduled_day(observed_at),
                                          legal_versions=self.legal_versions)
        self.store.database.record_worker_heartbeat("portfolio_daily", status="running")
        result = self._run_users(observed_at)
        self.store.database.record_worker_heartbeat(
            "portfolio_daily", status="attention" if result.failed or result.degraded else "ok",
        )
        return result

    def _run_users(self, observed_at: datetime) -> ObserverRunResult:
        user_ids = self.store.observer_user_ids()
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
                except Exception as exc:
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
            claimed_jobs=sum(item.status != "deferred" for item in results),
            succeeded=sum(item.status == "succeeded" for item in results),
            degraded=sum(item.status == "degraded" for item in results),
            failed=sum(item.status == "failed" for item in results),
            deferred=any(item.status == "deferred" for item in results),
        )

    def run_user(
        self,
        user_id: UUID,
        *,
        now: datetime,
        recover_running: bool = False,
    ) -> UserObservationResult | None:
        if now.tzinfo is None:
            raise ValueError(_AWARE_OBSERVER_TIME_REQUIRED)
        now = now.astimezone(UTC)
        scheduled_for = _scheduled_day(now)
        with self.store.observer_lock(user_id) as locked:
            if not locked:
                return UserObservationResult(user_id, "deferred", False, 0, 0)
            job = self.store.claim_daily_job(
                user_id, job_type=JOB_TYPE, scheduled_for=scheduled_for,
                legal_versions=self.legal_versions, recover_running=recover_running,
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
            raise ValueError(_AWARE_OBSERVER_TIME_REQUIRED)
        now = now.astimezone(UTC)
        details: dict[str, object] = {
            "job": job.job_type,
            "scheduled_for": job.scheduled_for.isoformat() if job.scheduled_for else None,
            "snapshot_saved": False,
            "history_pages": 0,
            "history_new_observations": 0,
            "refresh_scope": job.refresh_scope,
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
        details["retryable"] = status == "degraded" and details.get("stage_error") not in {
            "ObservationCancelled", "BrokerConnectionError", "TBankTokenRejected", "ValueError",
        } and details.get("history_status") not in {"opened_date_missing", "opened_date_invalid"}
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
        details["retryable"] = True
        try:
            self.store.finish_job(job.user_id, job.id, status="failed", details=details)
        except Exception as finish_exc:
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
        quick = job.refresh_scope == "quick"
        deadline = time.monotonic() + QUICK_REFRESH_BUDGET_SECONDS if quick else None
        bundle, snapshot_id, opened_at = self._snapshot(job, details)
        _checkpoint(should_stop)
        if quick:
            details["evidence_sources"] = {}
            details["evidence_status"] = "deferred_to_full_refresh"
        else:
            try:
                self._evidence(job, bundle, snapshot_id, now, details)
            except TBankUnavailable:
                # NAV and the ledger remain usable if an enrichment provider fails.
                details["evidence_sources"] = {"provider": "unavailable"}
        _checkpoint(should_stop)
        profile = self.store.current_profile(job.user_id)
        details["profile_version"] = profile.version if profile else None
        pages, inserted, history_status = self._sync_history(
            job.user_id, job_run_id=job.id, account_id=bundle.account_id,
            environment=bundle.environment, account_opened_at=opened_at,
            now=max(now, bundle.refreshed_at), should_stop=should_stop,
            max_pages=1 if quick else None, retry=not quick, deadline=deadline,
        )
        details.update(history_pages=pages, history_new_observations=inserted,
                       history_status=history_status)
        _checkpoint(should_stop)
        self._news(job, bundle, snapshot_id, details, should_stop)

    def _news(
        self, job: JobRunRecord, bundle: BrokerObservationBundle, snapshot_id: UUID,
        details: dict[str, object], should_stop: Callable[[], bool] | None,
    ) -> None:
        held_uids = held_news_instrument_uids(bundle)
        state = _news_state({}, held_uids)
        details["news"] = state
        if not held_uids:
            state["status"] = (
                "not_applicable" if bundle.analysis.security_count == 0 else "unavailable"
            )
            return
        previous = self.store.news_state(job.user_id, job_run_id=job.id)
        state.update(_news_state(previous, held_uids))
        deadline = time.monotonic() + NEWS_BUDGET_SECONDS
        cursor = None
        try:
            for _page_number in range(NEWS_MAX_PAGES_PER_RUN):
                _checkpoint(should_stop)
                if time.monotonic() >= deadline:
                    break
                if not self._news_page(job, snapshot_id, held_uids, state, cursor=cursor):
                    break
                cursor = cast(list[NewsContinuation], state["continuations"])[0]["cursor"]
        except ObservationCancelled:
            raise
        except (TBankUnavailable, ValueError) as exc:
            # News cannot turn a valid NAV or ledger into unavailable financial data.
            # Keep the last committed queue and observation time for restart/readback.
            state.update(status="partial" if state["pages"] else "unavailable",
                         error=type(exc).__name__)

    def _news_page(
        self, job: JobRunRecord, snapshot_id: UUID, held_uids: frozenset[str],
        state: dict[str, object], *, cursor: str | None,
    ) -> bool:
        """Commit a source page and its continuation together before advancing in memory."""
        page = self.broker.instrument_news(job.user_id, cursor=cursor, limit=NEWS_MAX_PAGE_SIZE)
        observed = datetime.fromisoformat(page["observed_at"])
        documents = build_news_evidence(held_uids, page["items"], observed_at=observed)
        # Queue mutations must also roll back in memory when persistence fails.
        checkpoint = deepcopy(state)
        if cursor is None:
            _enqueue_news_head(checkpoint, page["next_cursor"], observed.isoformat())
        else:
            _advance_news_path(checkpoint, cursor, page["next_cursor"])
        _bound_news_proofs(checkpoint)
        pending = bool(checkpoint["continuations"])
        complete = not pending and not checkpoint["reset_in_run"]
        checkpoint.update(
            status="received" if complete else "partial",
            recovery_required=False if complete else checkpoint["recovery_required"],
            observed_at=observed.isoformat(), pages=cast(int, state["pages"]) + 1,
            scanned_items=cast(int, state["scanned_items"]) + page["scanned_items"],
        )
        written, _ = self.store.save_evidence(
            job.user_id, job_run_id=job.id, snapshot_id=snapshot_id,
            documents=documents, assessments=(), retrieved_at=observed,
            news_checkpoint=checkpoint,
        )
        state.update(checkpoint, documents_new=cast(int, state["documents_new"]) + written)
        return pending

    def _snapshot(
        self, job: JobRunRecord, details: dict[str, object],
    ) -> tuple[BrokerObservationBundle, UUID, datetime | None]:
        user_id = job.user_id
        quick = job.refresh_scope == "quick"
        account = (self.broker.revalidate_account(user_id) if quick
                   else provider_read(lambda: self.broker.revalidate_account(user_id)))
        details.update(account_access=account.access_level, account_status=account.status,
                       account_type=account.type)
        user_info = None
        details["broker_user_info_status"] = "not_requested"
        if not quick:
            try:
                user_info = provider_read(lambda: self.broker.user_info(user_id))
            except TBankUnavailable:
                details["broker_user_info_status"] = "unavailable"
            else:
                details.update(
                    broker_user_info_status="received", broker_qualified=user_info.qualified,
                    broker_qualified_for_work_with=list(user_info.qualified_for_work_with),
                    broker_risk_level_code=user_info.risk_level_code,
                    broker_tariff=user_info.tariff,
                )
        bundle = (self.broker.observation_bundle(user_id, quick=True) if quick else
                  provider_read(lambda: self.broker.observation_bundle(user_id, full_catalog=True)))
        if quick:
            bundle = self.store.reuse_snapshot_metadata(user_id, job_run_id=job.id, bundle=bundle)
        snapshot_id = self.store.save_snapshot(
            user_id, job_run_id=job.id, bundle=bundle, account=account, user_info=user_info,
        )
        details.update(
            snapshot_saved=True, analysis_status=bundle.analysis.status,
            valuation_status=bundle.analysis.valuation_status,
            catalog_status=next((source.status for source in bundle.sources
                                 if source.id == "catalog"), "not_requested"),
        )
        return bundle, snapshot_id, account.opened_at

    def _evidence(
        self, job: JobRunRecord, bundle: BrokerObservationBundle, snapshot_id: UUID,
        now: datetime, details: dict[str, object],
    ) -> None:
        evidence = provider_read(lambda: self.broker.evidence(job.user_id, bundle, now=now))
        documents, assessments = build_tbank_evidence(
            bundle, evidence, assessed_at=max(now, evidence.refreshed_at),
        )
        new_documents, new_assessments = self.store.save_evidence(
            job.user_id, job_run_id=job.id, snapshot_id=snapshot_id, documents=documents,
            assessments=assessments, retrieved_at=evidence.refreshed_at,
        )
        details.update(
            evidence_documents_new=new_documents, risk_assessments_new=new_assessments,
            evidence_sources={source.id: source.status for source in evidence.sources},
            credit_rating_status="received" if evidence.ratings else "data_missing",
            credit_rating_coverage={
                "held_bonds": sum(
                    item.instrument_type == "bond" for item in bundle.analysis.securities
                ),
                "instruments_read": len(evidence.ratings),
                "instruments_with_ratings": sum(
                    bool(values) for values in evidence.ratings.values()
                ),
            },
            risk_states={
                state: sum(item.state == state for item in assessments)
                for state in ("data_missing", "normal", "watch", "elevated", "critical",
                              "confirmed_default")
            },
        )

    @staticmethod
    def _degraded(details: dict[str, object]) -> bool:
        if details.get("refresh_scope") == "quick":
            return (details.get("valuation_status") != "complete"
                    or details.get("history_status") != "complete")
        return (
            (details.get("valuation_status") != "complete"
             and details["analysis_status"] != "observed")
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
        max_pages: int | None = None,
        retry: bool = True,
        deadline: float | None = None,
    ) -> tuple[int, int, str]:
        state = self.store.sync_state(user_id, account_id)
        window = _history_window(state, account_opened_at, now)
        if isinstance(window, str):
            return 0, 0, window
        window_from, window_to, cursor = window

        seen_cursors = {cursor} if cursor else set()
        inserted = 0
        page_limit = max_pages if max_pages is not None else MAX_HISTORY_PAGES_PER_RUN
        for page_number in range(1, page_limit + 1):
            _checkpoint(should_stop)
            if deadline is not None and time.monotonic() >= deadline:
                return page_number - 1, inserted, "continuation_pending"
            read = partial(
                    self.broker.history_page,
                    user_id,
                    from_at=window_from,
                    to_at=window_to,
                    cursor=cursor,
                    limit=OPERATIONS_MAX_PAGE_SIZE,
            )
            page = provider_read(read, retry=retry)
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
            if page.has_next:
                seen_cursors.add(page.next_cursor)
                cursor = page.next_cursor
                continue
            if window_to >= now:
                return page_number, inserted, "complete"
            # Finishing a resumed cursor only covers its original window.
            # Catch up to this snapshot without exceeding the shared page
            # budget; each completed watermark remains durable on failure.
            window_from = max(window_from, window_to - HISTORY_CORRECTION_OVERLAP)
            window_to, cursor = now, ""
            seen_cursors.clear()

        return page_limit, inserted, "continuation_pending"


class PortfolioRefreshCoordinator:
    """Two bounded workers per process, backed by durable owner-scoped job records."""

    def __init__(
        self, store: PortfolioStore, broker: BrokerService, *, legal_versions: dict[str, str],
    ) -> None:
        self.store = store
        self.observer = PortfolioObserver(store, broker, legal_versions=legal_versions)
        self.legal_versions = dict(legal_versions)
        self._requests = BoundedSemaphore(REFRESH_ADMISSION_SLOTS)
        self._wake = Event()
        self._stopping = Event()
        self._worker: Thread | None = None
        self._second_worker: Thread | None = None
        self._last_user: UUID | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        worker = Thread(target=self._loop, name="portfolio-refresh", daemon=True)
        worker.start()
        self._worker = worker
        self._second_worker = Thread(target=self._loop, name="portfolio-refresh-2", daemon=True)
        self._second_worker.start()

    def close(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._worker is not None:
            # An in-flight provider request has its own timeout. An unfinished
            # durable job is recovered after restart; shutdown never marks it fresh.
            self._worker.join(timeout=WORKER_SHUTDOWN_SECONDS)
        if self._second_worker is not None:
            self._second_worker.join(timeout=WORKER_SHUTDOWN_SECONDS)

    def request(self, user_id: UUID, *, scope: str = "full") -> dict[str, object]:
        if self._stopping.is_set() or not self._requests.acquire(blocking=False):
            raise PortfolioRefreshBusy("portfolio_refresh_busy")
        try:
            result = self.store.request_refresh(user_id, self.legal_versions, scope=scope)
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
            except Exception as exc:
                logger.exception("portfolio refresh worker error_type=%s",
                                 type(exc).__name__, exc_info=None)
                try:
                    self.store.database.record_worker_heartbeat("portfolio_refresh",
                                                                 status="attention")
                except Exception as heartbeat_error:
                    logger.exception("portfolio refresh heartbeat error_type=%s",
                                     type(heartbeat_error).__name__, exc_info=None)
            self._wake.wait(timeout=WORKER_POLL_SECONDS)
            self._wake.clear()

    def run_pending(self) -> bool:
        """Process one owner; a slow account never holds another owner's lock."""
        if self._stopping.is_set():
            return False
        self.store.database.record_worker_heartbeat("portfolio_refresh", status="running")
        users = self.store.observer_user_ids()
        ordered = self._fair_order(users)
        # Existing user requests and daily recovery take priority for every
        # owner. The second pass schedules bounded observation even with no
        # browser open; the database enforces cadence across processes/restarts.
        for schedule_if_due in (False, True):
            for user_id in ordered:
                if self._run_pending_user(user_id, schedule_if_due=schedule_if_due):
                    self.store.database.record_worker_heartbeat("portfolio_refresh")
                    return True
        self.store.database.record_worker_heartbeat("portfolio_refresh")
        return False

    def _run_pending_user(self, user_id: UUID, *, schedule_if_due: bool) -> bool:
        with self.store.observer_lock(user_id) as locked:
            if not locked:
                return False
            if schedule_if_due:
                job = self.store.claim_refresh_job(
                    user_id, self.legal_versions, schedule_if_due=True,
                )
            else:
                job = self.store.claim_refresh_job(user_id, self.legal_versions)
                if job is None:
                    job = self.store.claim_pending_daily_job(user_id, self.legal_versions)
            if job is None:
                return False
            self._last_user = user_id
            self._run_claimed(job)
            return True

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
            if not self._stopping.is_set() and job.job_type == "portfolio_refresh":
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
            "portfolio observer complete users=%s claimed=%s succeeded=%s degraded=%s failed=%s "
            "deferred=%s",
            result.total_users,
            result.claimed_jobs,
            result.succeeded,
            result.degraded,
            result.failed,
            result.deferred,
        )
        return 75 if result.deferred else int(bool(result.failed))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
