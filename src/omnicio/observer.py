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
from typing import Literal
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
from .portfolio import PortfolioAnalysisError
from .portfolio_store import PortfolioStore
from .risk import (
    FundamentalEvidence,
    InstrumentRiskEvidence,
    PayoutEvidence,
    ReportEvidence,
    SourceEvidenceStatus,
    assess_instrument,
)
from .security import SecurityValueError
from .tbank import (
    TBankBondEvent,
    TBankCoupon,
    TBankDividend,
    TBankInvestClient,
    TBankTokenRejected,
    TBankUnavailable,
)

logger = logging.getLogger(__name__)

JOB_TYPE = "portfolio_daily"
MOSCOW = ZoneInfo("Europe/Moscow")
MAX_WORKERS = 2
MAX_HISTORY_PAGES_PER_RUN = 20
HISTORY_PAGE_SIZE = 1000
HISTORY_CORRECTION_OVERLAP = timedelta(days=7)
PROVIDER_READ_ATTEMPTS = 3
RISK_LOOKBACK = timedelta(days=550)
RISK_LOOKAHEAD = timedelta(days=400)
INSTRUMENT_SERVICE_MIN_INTERVAL_SECONDS = 0.35

TBANK_FUNDAMENTALS_URL = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals"
)
TBANK_REPORTS_URL = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-asset-reports"
)
TBANK_DIVIDENDS_URL = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-dividends"
)
TBANK_COUPONS_URL = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-bond-coupons"
)
TBANK_BOND_EVENTS_URL = (
    "https://developer.tbank.ru/invest/api/instruments-service-get-bond-events"
)
CBR_RATING_REPOSITORY_URL = "https://ratings.cbr.ru/"

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


def _dividend_evidence(item: TBankDividend) -> PayoutEvidence:
    cancelled = item.dividend_type.strip().casefold() == "cancelled"
    event_key = (
        f"dividend:{item.record_date.date().isoformat()}:"
        f"{item.dividend_type.strip().casefold() or 'unspecified'}"
    )
    return PayoutEvidence(
        instrument_uid=item.instrument_uid,
        kind="dividend",
        event_key=event_key,
        event_date=item.payment_date,
        record_date=item.record_date,
        declared_at=item.declared_date,
        provider_payment_at=item.payment_date,
        amount_value=item.amount.value,
        amount_currency=item.amount.currency,
        status="cancelled" if cancelled else "scheduled",
        source_id="tbank_dividends",
        source_url=TBANK_DIVIDENDS_URL,
        details={
            "last_buy_date": item.last_buy_date,
            "dividend_type": item.dividend_type,
            "regularity": item.regularity,
            "provider_created_at": item.created_at,
        },
    )


def _coupon_evidence(item: TBankCoupon) -> PayoutEvidence:
    return PayoutEvidence(
        instrument_uid=item.instrument_uid,
        kind="coupon",
        event_key=(
            f"coupon:{item.coupon_number}:{item.coupon_date.date().isoformat()}"
        ),
        event_date=item.coupon_date,
        record_date=item.fix_date,
        declared_at=None,
        provider_payment_at=item.coupon_date,
        amount_value=item.amount.value,
        amount_currency=item.amount.currency,
        status="scheduled",
        source_id="tbank_bond_coupons",
        source_url=TBANK_COUPONS_URL,
        details={
            "figi": item.figi,
            "coupon_number": item.coupon_number,
            "coupon_type": item.coupon_type,
            "coupon_start_date": item.coupon_start_date,
            "coupon_end_date": item.coupon_end_date,
            "coupon_period_days": item.coupon_period_days,
        },
    )


def _bond_event_evidence(item: TBankBondEvent) -> PayoutEvidence:
    status = "default_reported" if item.default_date is not None else (
        item.execution or item.event_type or "scheduled"
    )
    return PayoutEvidence(
        instrument_uid=item.instrument_uid,
        kind="bond_event",
        event_key=(
            f"bond-event:{item.event_type}:{item.event_number}:"
            f"{item.event_date.date().isoformat()}"
        ),
        event_date=item.event_date,
        record_date=item.fix_date,
        declared_at=item.rate_date,
        provider_payment_at=item.real_pay_date or item.pay_date,
        amount_value=item.pay_one_bond.value if item.pay_one_bond is not None else None,
        amount_currency=(
            item.pay_one_bond.currency if item.pay_one_bond is not None else None
        ),
        status=status,
        source_id="tbank_bond_events",
        source_url=TBANK_BOND_EVENTS_URL,
        details={
            "event_number": item.event_number,
            "event_type": item.event_type,
            "default_date": item.default_date,
            "real_pay_date": item.real_pay_date,
            "pay_date": item.pay_date,
            "execution": item.execution,
            "operation_type": item.operation_type,
            "note": item.note,
        },
    )


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

            profile = self.store.current_profile(user_id)
            details["profile_version"] = profile.version if profile else None

            risk_result = self._sync_risk_evidence(
                user_id,
                snapshot_id=snapshot_id,
                bundle=bundle,
                now=now,
            )
            details["risk_assessments"] = risk_result[0]
            details["risk_unavailable_sources"] = risk_result[1]
            details["risk_states"] = risk_result[2]

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
                or int(details["risk_unavailable_sources"]) > 0
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

    def _sync_risk_evidence(
        self,
        user_id: UUID,
        *,
        snapshot_id: UUID,
        bundle: object,
        now: datetime,
    ) -> tuple[int, int, dict[str, int]]:
        # The observer only deep-reads current holdings. Candidate research is a
        # separate bounded stage; broad catalog metadata must not trigger N×API calls.
        securities = tuple(getattr(bundle.analysis, "securities"))
        metadata_by_uid = {item.uid: item for item in getattr(bundle, "metadata")}
        if not securities:
            self.store.save_risk_evidence(
                user_id,
                snapshot_id=snapshot_id,
                evidences=(),
                assessments=(),
            )
            return 0, 0, {}

        next_instrument_call_at = 0.0

        def paced_read[T](operation: Callable[[], T]) -> T:
            nonlocal next_instrument_call_at
            now_monotonic = time.monotonic()
            delay = next_instrument_call_at - now_monotonic
            if delay > 0:
                time.sleep(delay)
            result = provider_read(operation)
            next_instrument_call_at = (
                time.monotonic() + INSTRUMENT_SERVICE_MIN_INTERVAL_SECONDS
            )
            return result

        asset_uids = tuple(
            dict.fromkeys(
                item.asset_uid
                for security in securities
                if (item := metadata_by_uid.get(security.uid)) is not None
                and item.asset_uid
            )
        )
        fundamentals_by_asset: dict[str, object] = {}
        fundamental_failed_assets: set[str] = set()
        for offset in range(0, len(asset_uids), 100):
            batch = asset_uids[offset : offset + 100]
            try:
                rows = paced_read(lambda batch=batch: self.broker.asset_fundamentals(
                    user_id,
                    batch,
                ))
            except TBankUnavailable:
                fundamental_failed_assets.update(batch)
            else:
                fundamentals_by_asset.update({item.asset_uid: item for item in rows})

        window_from = now - RISK_LOOKBACK
        window_to = now + RISK_LOOKAHEAD
        evidences: list[InstrumentRiskEvidence] = []
        assessments = []
        unavailable_count = 0

        for security in securities:
            metadata = metadata_by_uid.get(security.uid)
            asset_uid = metadata.asset_uid if metadata is not None else ""
            source_rows: list[SourceEvidenceStatus] = []
            payout_rows: list[PayoutEvidence] = []
            report_rows: tuple[ReportEvidence, ...] = ()
            fundamental = None
            confirmed_default_at = None

            fundamental_row = fundamentals_by_asset.get(asset_uid) if asset_uid else None
            if fundamental_row is not None:
                fundamental = FundamentalEvidence(
                    instrument_uid=security.uid,
                    asset_uid=asset_uid,
                    currency=fundamental_row.currency,
                    retrieved_at=now,
                    fiscal_period_end=fundamental_row.fiscal_period_end_date,
                    metrics={
                        "revenue_ttm": fundamental_row.revenue_ttm,
                        "ebitda_ttm": fundamental_row.ebitda_ttm,
                        "net_income_ttm": fundamental_row.net_income_ttm,
                        "free_cash_flow_ttm": fundamental_row.free_cash_flow_ttm,
                        "total_debt_mrq": fundamental_row.total_debt_mrq,
                        "total_debt_to_equity_mrq": (
                            fundamental_row.total_debt_to_equity_mrq
                        ),
                        "total_debt_to_ebitda_mrq": (
                            fundamental_row.total_debt_to_ebitda_mrq
                        ),
                        "net_debt_to_ebitda": fundamental_row.net_debt_to_ebitda,
                        "current_ratio_mrq": fundamental_row.current_ratio_mrq,
                        "fixed_charge_coverage_ratio_fy": (
                            fundamental_row.fixed_charge_coverage_ratio_fy
                        ),
                        "net_interest_margin_mrq": fundamental_row.net_interest_margin_mrq,
                        "roe": fundamental_row.roe,
                        "roa": fundamental_row.roa,
                        "total_debt_change_five_years": (
                            fundamental_row.total_debt_change_five_years
                        ),
                    },
                )
                fundamental_status: Literal["received", "partial", "unavailable"] = "received"
            elif asset_uid in fundamental_failed_assets:
                fundamental_status = "unavailable"
                unavailable_count += 1
            else:
                fundamental_status = "partial"
            source_rows.append(
                SourceEvidenceStatus(
                    source_id="tbank_fundamentals",
                    scope_key=security.uid,
                    status=fundamental_status,
                    retrieved_at=now,
                    source_url=TBANK_FUNDAMENTALS_URL,
                )
            )

            try:
                reports = paced_read(
                    lambda uid=security.uid: self.broker.asset_reports(
                        user_id,
                        uid,
                        from_at=window_from,
                        to_at=window_to,
                    )
                )
            except TBankUnavailable:
                source_rows.append(
                    SourceEvidenceStatus(
                        source_id="tbank_reports",
                        scope_key=security.uid,
                        status="unavailable",
                        retrieved_at=now,
                        source_url=TBANK_REPORTS_URL,
                    )
                )
                unavailable_count += 1
            else:
                report_rows = tuple(
                    ReportEvidence(
                        instrument_uid=security.uid,
                        report_date=item.report_date,
                        period_year=item.period_year,
                        period_num=item.period_num,
                        period_type=item.period_type,
                        created_at=item.created_at,
                    )
                    for item in reports
                )
                source_rows.append(
                    SourceEvidenceStatus(
                        source_id="tbank_reports",
                        scope_key=security.uid,
                        status="received",
                        retrieved_at=now,
                        source_url=TBANK_REPORTS_URL,
                    )
                )

            if security.instrument_type in {"share", "etf"}:
                try:
                    dividends = paced_read(
                        lambda uid=security.uid: self.broker.dividends(
                            user_id,
                            uid,
                            from_at=window_from,
                            to_at=window_to,
                        )
                    )
                except TBankUnavailable:
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_dividends",
                            scope_key=security.uid,
                            status="unavailable",
                            retrieved_at=now,
                            source_url=TBANK_DIVIDENDS_URL,
                        )
                    )
                    unavailable_count += 1
                else:
                    payout_rows.extend(_dividend_evidence(item) for item in dividends)
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_dividends",
                            scope_key=security.uid,
                            status="received",
                            retrieved_at=now,
                            source_url=TBANK_DIVIDENDS_URL,
                        )
                    )

            if security.instrument_type == "bond":
                try:
                    coupons = paced_read(
                        lambda uid=security.uid: self.broker.bond_coupons(
                            user_id,
                            uid,
                            from_at=window_from,
                            to_at=window_to,
                        )
                    )
                except TBankUnavailable:
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_bond_coupons",
                            scope_key=security.uid,
                            status="unavailable",
                            retrieved_at=now,
                            source_url=TBANK_COUPONS_URL,
                        )
                    )
                    unavailable_count += 1
                else:
                    payout_rows.extend(_coupon_evidence(item) for item in coupons)
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_bond_coupons",
                            scope_key=security.uid,
                            status="received",
                            retrieved_at=now,
                            source_url=TBANK_COUPONS_URL,
                        )
                    )

                try:
                    bond_events = paced_read(
                        lambda uid=security.uid: self.broker.bond_events(
                            user_id,
                            uid,
                            from_at=window_from,
                            to_at=window_to,
                        )
                    )
                except TBankUnavailable:
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_bond_events",
                            scope_key=security.uid,
                            status="unavailable",
                            retrieved_at=now,
                            source_url=TBANK_BOND_EVENTS_URL,
                        )
                    )
                    unavailable_count += 1
                else:
                    payout_rows.extend(_bond_event_evidence(item) for item in bond_events)
                    default_dates = [
                        item.default_date
                        for item in bond_events
                        if item.default_date is not None
                    ]
                    if default_dates:
                        confirmed_default_at = min(default_dates)
                    source_rows.append(
                        SourceEvidenceStatus(
                            source_id="tbank_bond_events",
                            scope_key=security.uid,
                            status="received",
                            retrieved_at=now,
                            source_url=TBANK_BOND_EVENTS_URL,
                        )
                    )

            # The CBR rating repository is an official public reference, but this
            # release does not scrape undocumented HTML nor assume agency feed rights.
            source_rows.append(
                SourceEvidenceStatus(
                    source_id="cbr_cra_registry",
                    scope_key=security.uid,
                    status="not_configured",
                    retrieved_at=now,
                    source_url=CBR_RATING_REPOSITORY_URL,
                )
            )

            evidence = InstrumentRiskEvidence(
                instrument_uid=security.uid,
                ticker=security.ticker,
                instrument_type=security.instrument_type,
                sector=security.sector,
                fundamental=fundamental,
                reports=report_rows,
                payouts=tuple(payout_rows),
                confirmed_default_at=confirmed_default_at,
                sources=tuple(source_rows),
            )
            evidences.append(evidence)
            assessments.append(assess_instrument(evidence, now=now))

        assessment_tuple = tuple(assessments)
        self.store.save_risk_evidence(
            user_id,
            snapshot_id=snapshot_id,
            evidences=tuple(evidences),
            assessments=assessment_tuple,
        )
        state_counts: dict[str, int] = {}
        for assessment in assessment_tuple:
            state_counts[assessment.state] = state_counts.get(assessment.state, 0) + 1
        return len(assessment_tuple), unavailable_count, state_counts

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
