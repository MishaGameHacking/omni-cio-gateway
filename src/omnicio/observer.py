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
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from .broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .config import load_settings
from .db import Database
from .intelligence import build_tbank_evidence
from .portfolio import PortfolioAnalysisError
from .portfolio_store import PortfolioStore
from .security import SecurityValueError
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable

logger = logging.getLogger(__name__)

JOB_TYPE = "portfolio_daily"
MOSCOW = ZoneInfo("Europe/Moscow")
MAX_WORKERS = 2
MAX_HISTORY_PAGES_PER_RUN = 20
HISTORY_PAGE_SIZE = 1000
HISTORY_CORRECTION_OVERLAP = timedelta(days=7)
PROVIDER_READ_ATTEMPTS = 3

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
                    logger.error(
                        "portfolio observer failed user=%s error_type=%s",
                        user_id,
                        type(exc).__name__,
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

        snapshot_saved = False
        history_pages = 0
        history_items_inserted = 0
        details: dict[str, object] = {
            "job": JOB_TYPE,
            "scheduled_for": scheduled_for.isoformat(),
        }

        try:
            account = provider_read(lambda: self.broker.revalidate_account(user_id))
            details["account_access"] = account.access_level
            details["account_status"] = account.status
            details["account_type"] = account.type

            user_info = None
            try:
                user_info = provider_read(lambda: self.broker.user_info(user_id))
            except TBankUnavailable:
                details["broker_user_info_status"] = "unavailable"
            else:
                details["broker_user_info_status"] = "received"
                details["broker_qualified"] = user_info.qualified
                details["broker_qualified_for_work_with"] = list(
                    user_info.qualified_for_work_with
                )
                details["broker_risk_level_code"] = user_info.risk_level_code
                details["broker_tariff"] = user_info.tariff

            bundle = provider_read(
                lambda: self.broker.observation_bundle(user_id, full_catalog=True)
            )
            snapshot_id = self.store.save_snapshot(
                user_id,
                job_run_id=job.id,
                bundle=bundle,
                account=account,
                user_info=user_info,
            )
            snapshot_saved = True
            details["analysis_status"] = bundle.analysis.status
            details["catalog_status"] = next(
                (
                    source.status
                    for source in bundle.sources
                    if source.id == "catalog"
                ),
                "not_requested",
            )

            evidence = provider_read(
                lambda: self.broker.evidence(user_id, bundle, now=now)
            )
            documents, assessments = build_tbank_evidence(
                bundle,
                evidence,
                assessed_at=now,
            )
            evidence_documents, risk_assessments = self.store.save_evidence(
                user_id,
                snapshot_id=snapshot_id,
                documents=documents,
                assessments=assessments,
                retrieved_at=evidence.refreshed_at,
            )
            details["evidence_documents_new"] = evidence_documents
            details["risk_assessments_new"] = risk_assessments
            details["evidence_sources"] = {
                source.id: source.status for source in evidence.sources
            }
            details["credit_rating_status"] = "data_missing"
            details["risk_states"] = {
                state: sum(item.state == state for item in assessments)
                for state in (
                    "data_missing",
                    "normal",
                    "watch",
                    "elevated",
                    "critical",
                    "confirmed_default",
                )
            }

            profile = self.store.current_profile(user_id)
            details["profile_version"] = profile.version if profile else None

            history_result = self._sync_history(
                user_id,
                account_id=bundle.account_id,
                account_opened_at=account.opened_at,
                now=now,
            )
            history_pages = history_result[0]
            history_items_inserted = history_result[1]
            details["history_status"] = history_result[2]
            details["history_pages"] = history_pages
            details["history_new_observations"] = history_items_inserted

            degraded = (
                bundle.analysis.status == "needs_reconciliation"
                or details["catalog_status"] == "partial"
                or details["broker_user_info_status"] != "received"
                or details["history_status"] != "complete"
                or any(
                    status != "received"
                    for source_id, status in cast(
                        dict[str, str],
                        details["evidence_sources"],
                    ).items()
                    if source_id != "credit_ratings"
                )
            )
            final_status: Literal["succeeded", "degraded"] = (
                "degraded" if degraded else "succeeded"
            )
            self.store.finish_job(
                user_id,
                job.id,
                status=final_status,
                details=details,
            )
            return UserObservationResult(
                user_id=user_id,
                status=final_status,
                snapshot_saved=snapshot_saved,
                history_pages=history_pages,
                history_items_inserted=history_items_inserted,
            )
        except (
            BrokerAccountNotAccessible,
            BrokerNotConnected,
            BrokerConnectionError,
            TBankTokenRejected,
            TBankUnavailable,
            PortfolioAnalysisError,
            SecurityValueError,
            ValueError,
        ) as exc:
            details["stage_error"] = type(exc).__name__
            self.store.finish_job(
                user_id,
                job.id,
                status="degraded",
                details=details,
            )
            return UserObservationResult(
                user_id=user_id,
                status="degraded",
                snapshot_saved=snapshot_saved,
                history_pages=history_pages,
                history_items_inserted=history_items_inserted,
            )
        except Exception as exc:
            details["stage_error"] = type(exc).__name__
            try:
                self.store.finish_job(
                    user_id,
                    job.id,
                    status="failed",
                    details=details,
                )
            except Exception as finish_exc:  # noqa: BLE001 - retain original infrastructure failure
                logger.error(
                    "portfolio observer could not persist failure user=%s error_type=%s",
                    user_id,
                    type(finish_exc).__name__,
                )
            raise

    def _sync_history(
        self,
        user_id: UUID,
        *,
        account_id: str,
        account_opened_at: datetime | None,
        now: datetime,
    ) -> tuple[int, int, str]:
        state = self.store.sync_state(user_id, account_id)
        if state is not None and state.pending_cursor:
            if state.history_window_from is None or state.history_window_to is None:
                raise RuntimeError("history cursor has no durable window")
            window_from = state.history_window_from
            window_to = state.history_window_to
            cursor = state.pending_cursor
        else:
            if account_opened_at is None:
                return 0, 0, "opened_date_missing"
            opened_at = account_opened_at.astimezone(UTC)
            if opened_at > now:
                return 0, 0, "opened_date_invalid"
            window_from = opened_at
            if state is not None and state.last_complete_watermark is not None:
                window_from = max(
                    opened_at,
                    state.last_complete_watermark - HISTORY_CORRECTION_OVERLAP,
                )
            window_to = now
            cursor = ""

        seen_cursors = {cursor} if cursor else set()
        inserted = 0
        for page_number in range(1, MAX_HISTORY_PAGES_PER_RUN + 1):
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
                account_id=account_id,
                window_from=window_from,
                window_to=window_to,
                page=page,
                observed_at=now,
            )
            if not page.has_next:
                return page_number, inserted, "complete"

            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor

        return MAX_HISTORY_PAGES_PER_RUN, inserted, "continuation_pending"


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
