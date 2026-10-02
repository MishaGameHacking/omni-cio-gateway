"""Persistence boundary for durable portfolio observation and user policy data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from .broker import BrokerObservationBundle
from .db import Database
from .risk import (
    FundamentalEvidence,
    InstrumentRiskEvidence,
    PayoutEvidence,
    ReportEvidence,
    RiskAssessment,
    RiskReason,
    RiskSnapshotSummary,
    SourceEvidenceStatus,
)
from .tbank import (
    TBankAccount,
    TBankMoney,
    TBankOperation,
    TBankOperationsPage,
    TBankUserInfo,
)

JobStatus = Literal["running", "succeeded", "degraded", "failed"]


@dataclass(frozen=True, slots=True)
class InvestmentProfileRecord:
    id: int
    user_id: UUID
    version: int
    reserve_rub: Decimal
    planned_withdrawal_rub: Decimal
    horizon_months: int
    max_drawdown_percent: Decimal
    liquidity_horizon_days: int
    allow_below_investment_grade: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobRunRecord:
    id: UUID
    user_id: UUID
    job_type: str
    scheduled_for: date
    status: JobStatus
    attempt: int
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class BrokerSyncState:
    user_id: UUID
    account_id: str
    history_window_from: datetime | None
    history_window_to: datetime | None
    pending_cursor: str
    last_complete_watermark: datetime | None
    updated_at: datetime


class PortfolioStore:
    """Store immutable observation facts behind explicit tenant context."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _tenant(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "SELECT set_config('omnicio.user_id', %s, true)",
            (str(user_id),),
        )

    @contextmanager
    def observer_lock(self) -> Iterator[bool]:
        lock_name = "omnicio-portfolio-observer"
        with self.database.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked",
                (lock_name,),
            )
            row = cur.fetchone()
            locked = row is not None and bool(cast(dict[str, Any], row)["locked"])
            if not locked:
                yield False
                return
            try:
                yield True
            finally:
                cur.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s, 0)) AS unlocked",
                    (lock_name,),
                )
                released = cur.fetchone()
                if released is None or not bool(cast(dict[str, Any], released)["unlocked"]):
                    raise RuntimeError("portfolio observer advisory lock was not released")

    def observer_user_ids(self, legal_versions: dict[str, str]) -> tuple[UUID, ...]:
        with self.database.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.user_id
                FROM tbank_connection AS t
                JOIN users AS u ON u.id = t.user_id
                WHERE u.status = 'active'
                ORDER BY t.user_id
                """
            )
            candidates = tuple(
                cast(UUID, cast(dict[str, Any], row)["user_id"])
                for row in cur.fetchall()
            )
        return tuple(
            user_id
            for user_id in candidates
            if self.database.has_legal_versions(user_id, legal_versions)
        )

    def current_profile(self, user_id: UUID) -> InvestmentProfileRecord | None:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade,
                    created_at
                FROM investment_profile_versions
                WHERE user_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _profile(cast(dict[str, Any], fetched))

    def save_profile(
        self,
        user_id: UUID,
        *,
        reserve_rub: Decimal,
        planned_withdrawal_rub: Decimal,
        horizon_months: int,
        max_drawdown_percent: Decimal,
        liquidity_horizon_days: int,
        allow_below_investment_grade: bool,
    ) -> InvestmentProfileRecord:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"investment-profile:{user_id}",),
            )
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade,
                    created_at
                FROM investment_profile_versions
                WHERE user_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id,),
            )
            latest_row = cur.fetchone()
            if latest_row is None:
                version = 1
            else:
                latest = _profile(cast(dict[str, Any], latest_row))
                if (
                    latest.reserve_rub == reserve_rub
                    and latest.planned_withdrawal_rub == planned_withdrawal_rub
                    and latest.horizon_months == horizon_months
                    and latest.max_drawdown_percent == max_drawdown_percent
                    and latest.liquidity_horizon_days == liquidity_horizon_days
                    and latest.allow_below_investment_grade == allow_below_investment_grade
                ):
                    return latest
                version = latest.version + 1
            cur.execute(
                """
                INSERT INTO investment_profile_versions (
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade,
                    created_at
                """,
                (
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade,
                ),
            )
            fetched = cur.fetchone()
            if fetched is None:
                raise RuntimeError("investment profile insert returned no row")
            return _profile(cast(dict[str, Any], fetched))

    def claim_daily_job(
        self,
        user_id: UUID,
        *,
        job_type: str,
        scheduled_for: date,
        recover_running: bool = False,
    ) -> JobRunRecord | None:
        if not job_type or len(job_type) > 128:
            raise ValueError("job_type must contain 1 to 128 characters")
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS locked",
                (f"daily-job:{user_id}:{job_type}:{scheduled_for.isoformat()}",),
            )
            lock_row = cur.fetchone()
            if lock_row is None or not bool(cast(dict[str, Any], lock_row)["locked"]):
                return None
            cur.execute(
                """
                INSERT INTO job_runs (
                    user_id,
                    job_type,
                    scheduled_for,
                    status
                )
                VALUES (%s, %s, %s, 'running')
                ON CONFLICT (user_id, job_type, scheduled_for) DO NOTHING
                RETURNING
                    id,
                    user_id,
                    job_type,
                    scheduled_for,
                    status,
                    attempt,
                    started_at,
                    finished_at
                """,
                (user_id, job_type, scheduled_for),
            )
            fetched = cur.fetchone()
            if fetched is None:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET
                        status = 'running',
                        attempt = attempt + 1,
                        started_at = now(),
                        finished_at = NULL,
                        details = '{}'::jsonb
                    WHERE user_id = %s
                      AND job_type = %s
                      AND scheduled_for = %s
                      AND attempt < 3
                      AND (
                          (
                              status = 'running'
                              AND (
                                  %s
                                  OR started_at < now() - interval '30 minutes'
                              )
                          )
                          OR (status = 'failed' AND finished_at < now() - interval '2 minutes')
                      )
                    RETURNING
                        id,
                        user_id,
                        job_type,
                        scheduled_for,
                        status,
                        attempt,
                        started_at,
                        finished_at
                    """,
                    (user_id, job_type, scheduled_for, recover_running),
                )
                fetched = cur.fetchone()
            if fetched is None:
                return None
            return _job_run(cast(dict[str, Any], fetched))

    def finish_job(
        self,
        user_id: UUID,
        job_run_id: UUID,
        *,
        status: Literal["succeeded", "degraded", "failed"],
        details: dict[str, object],
    ) -> None:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                UPDATE job_runs
                SET
                    status = %s,
                    finished_at = now(),
                    details = %s::jsonb
                WHERE id = %s
                  AND user_id = %s
                  AND status = 'running'
                RETURNING id
                """,
                (status, _json(details), job_run_id, user_id),
            )
            if cur.fetchone() is None:
                raise RuntimeError("daily job is no longer running")

    def sync_state(self, user_id: UUID, account_id: str) -> BrokerSyncState | None:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    user_id,
                    account_id,
                    history_window_from,
                    history_window_to,
                    COALESCE(pending_cursor, '') AS pending_cursor,
                    last_complete_watermark,
                    updated_at
                FROM broker_sync_state
                WHERE user_id = %s
                  AND account_id = %s
                """,
                (user_id, account_id),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _sync_state(cast(dict[str, Any], fetched))

    def save_snapshot(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        bundle: BrokerObservationBundle,
        account: TBankAccount | None = None,
        user_info: TBankUserInfo | None = None,
    ) -> UUID:
        evidence: dict[str, object] = {
            "analysis": asdict(bundle.analysis),
            "sources": [asdict(source) for source in bundle.sources],
        }
        if account is not None:
            evidence["account"] = {
                "type": account.type,
                "status": account.status,
                "access_level": account.access_level,
                "opened_at": account.opened_at,
            }
        if user_info is not None:
            evidence["broker_user"] = {
                "premium": user_info.premium,
                "qualified": user_info.qualified,
                "qualified_for_work_with": list(user_info.qualified_for_work_with),
                "tariff": user_info.tariff,
                "risk_level_code": user_info.risk_level_code,
            }
        securities = {item.uid: item for item in bundle.analysis.securities}
        metadata = {item.uid: item for item in bundle.metadata}
        catalog_retrieved_at = next(
            (
                source.retrieved_at
                for source in bundle.sources
                if source.id == "catalog"
            ),
            bundle.refreshed_at,
        )

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            if bundle.metadata:
                catalog_rows = [
                    (
                        item.uid,
                        item.figi,
                        item.asset_uid,
                        item.position_uid,
                        item.ticker,
                        item.name,
                        item.isin,
                        item.instrument_type,
                        item.currency,
                        item.class_code,
                        item.lot,
                        item.sector,
                        item.country_of_risk,
                        item.for_qual_investor,
                        item.for_iis,
                        item.api_trade_available,
                        item.buy_available,
                        item.sell_available,
                        catalog_retrieved_at,
                    )
                    for item in bundle.metadata
                ]
                cur.executemany(
                    """
                    INSERT INTO instrument_catalog (
                        provider,
                        instrument_uid,
                        figi,
                        asset_uid,
                        position_uid,
                        ticker,
                        name,
                        isin,
                        instrument_type,
                        currency,
                        class_code,
                        lot,
                        sector,
                        country_of_risk,
                        for_qual_investor,
                        for_iis,
                        api_trade_available,
                        buy_available,
                        sell_available,
                        provider_retrieved_at
                    )
                    VALUES (
                        'tbank', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (provider, instrument_uid) DO UPDATE SET
                        figi = EXCLUDED.figi,
                        asset_uid = EXCLUDED.asset_uid,
                        position_uid = EXCLUDED.position_uid,
                        ticker = EXCLUDED.ticker,
                        name = EXCLUDED.name,
                        isin = EXCLUDED.isin,
                        instrument_type = EXCLUDED.instrument_type,
                        currency = EXCLUDED.currency,
                        class_code = EXCLUDED.class_code,
                        lot = EXCLUDED.lot,
                        sector = EXCLUDED.sector,
                        country_of_risk = EXCLUDED.country_of_risk,
                        for_qual_investor = EXCLUDED.for_qual_investor,
                        for_iis = EXCLUDED.for_iis,
                        api_trade_available = EXCLUDED.api_trade_available,
                        buy_available = EXCLUDED.buy_available,
                        sell_available = EXCLUDED.sell_available,
                        last_seen_at = now(),
                        provider_retrieved_at = EXCLUDED.provider_retrieved_at
                    """,
                    catalog_rows,
                )

                access_rows = [
                    (
                        user_id,
                        bundle.account_id,
                        item.uid,
                        _json(list(item.required_tests)),
                        catalog_retrieved_at,
                    )
                    for item in bundle.metadata
                ]
                cur.executemany(
                    """
                    INSERT INTO account_instrument_access (
                        user_id,
                        account_id,
                        provider,
                        instrument_uid,
                        required_tests,
                        observed_at
                    )
                    VALUES (%s, %s, 'tbank', %s, %s::jsonb, %s)
                    ON CONFLICT (user_id, account_id, provider, instrument_uid)
                    DO UPDATE SET
                        required_tests = EXCLUDED.required_tests,
                        observed_at = EXCLUDED.observed_at
                    """,
                    access_rows,
                )

            cur.execute(
                """
                INSERT INTO portfolio_snapshots (
                    user_id,
                    job_run_id,
                    account_id,
                    environment,
                    captured_at,
                    analysis_status,
                    nav_rub,
                    rub_cash_total,
                    rub_cash_blocked,
                    rub_cash_unblocked,
                    limits_loading_in_progress,
                    evidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (job_run_id) DO NOTHING
                RETURNING id
                """,
                (
                    user_id,
                    job_run_id,
                    bundle.account_id,
                    bundle.environment,
                    bundle.refreshed_at,
                    bundle.analysis.status,
                    Decimal(bundle.analysis.nav_rub),
                    Decimal(bundle.analysis.rub_cash_total),
                    Decimal(bundle.analysis.rub_cash_blocked),
                    (
                        Decimal(bundle.analysis.rub_cash_unblocked)
                        if bundle.analysis.rub_cash_unblocked is not None
                        else None
                    ),
                    bundle.positions.limits_loading_in_progress,
                    _json(evidence),
                ),
            )
            snapshot_row = cur.fetchone()
            if snapshot_row is None:
                cur.execute(
                    """
                    SELECT id
                    FROM portfolio_snapshots
                    WHERE job_run_id = %s
                      AND user_id = %s
                    """,
                    (job_run_id, user_id),
                )
                existing = cur.fetchone()
                if existing is None:
                    raise RuntimeError("portfolio snapshot conflict could not be resolved")
                return cast(UUID, cast(dict[str, Any], existing)["id"])
            snapshot_id = cast(UUID, cast(dict[str, Any], snapshot_row)["id"])

            for position in bundle.portfolio.positions:
                if Decimal(position.quantity) == 0 or position.instrument_type == "currency":
                    continue
                uid = position.instrument_uid or position.figi
                exposure = securities.get(uid)
                info = metadata.get(position.instrument_uid)
                cur.execute(
                    """
                    INSERT INTO portfolio_snapshot_positions (
                        snapshot_id,
                        user_id,
                        instrument_uid,
                        figi,
                        ticker,
                        instrument_type,
                        quantity,
                        current_price_value,
                        current_price_currency,
                        current_nkd_value,
                        current_nkd_currency,
                        blocked,
                        blocked_lots,
                        value_rub,
                        nav_percent,
                        sector,
                        country_of_risk,
                        for_qual_investor
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        snapshot_id,
                        user_id,
                        uid,
                        position.figi,
                        position.ticker,
                        position.instrument_type,
                        Decimal(position.quantity),
                        _money_decimal(position.current_price),
                        position.current_price.currency if position.current_price else None,
                        _money_decimal(position.current_nkd),
                        position.current_nkd.currency if position.current_nkd else None,
                        position.blocked,
                        Decimal(position.blocked_lots),
                        (
                            Decimal(exposure.value_rub)
                            if exposure is not None and exposure.value_rub is not None
                            else None
                        ),
                        (
                            Decimal(exposure.nav_percent)
                            if exposure is not None and exposure.nav_percent is not None
                            else None
                        ),
                        info.sector if info else "",
                        info.country_of_risk if info else "",
                        info.for_qual_investor if info else None,
                    ),
                )
            return snapshot_id

    def latest_risk_summary(
        self,
        user_id: UUID,
        *,
        payout_from: datetime,
        payout_to: datetime,
    ) -> RiskSnapshotSummary | None:
        if payout_from.tzinfo is None or payout_to.tzinfo is None:
            raise ValueError("payout window must be timezone-aware")
        if payout_from > payout_to:
            raise ValueError("payout window start must not be after end")

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT ps.id, ps.captured_at
                FROM portfolio_snapshots AS ps
                WHERE ps.user_id = %s
                  AND EXISTS (
                      SELECT 1
                      FROM risk_assessments AS ra
                      WHERE ra.snapshot_id = ps.id
                        AND ra.user_id = %s
                  )
                ORDER BY ps.captured_at DESC, ps.created_at DESC
                LIMIT 1
                """,
                (user_id, user_id),
            )
            snapshot_row = cur.fetchone()
            if snapshot_row is None:
                return None
            snapshot = cast(dict[str, Any], snapshot_row)
            snapshot_id = cast(UUID, snapshot["id"])

            cur.execute(
                """
                SELECT
                    instrument_uid,
                    ticker,
                    state,
                    sector_model,
                    coverage,
                    reasons,
                    evaluated_at,
                    latest_fundamental_period_end,
                    latest_report_date
                FROM risk_assessments
                WHERE user_id = %s
                  AND snapshot_id = %s
                ORDER BY
                    CASE state
                        WHEN 'confirmed_default' THEN 0
                        WHEN 'critical' THEN 1
                        WHEN 'elevated' THEN 2
                        WHEN 'watch' THEN 3
                        WHEN 'data_missing' THEN 4
                        ELSE 5
                    END,
                    ticker,
                    instrument_uid
                """,
                (user_id, snapshot_id),
            )
            assessments = tuple(
                _risk_assessment(cast(dict[str, Any], row))
                for row in cur.fetchall()
            )

            cur.execute(
                """
                SELECT
                    source_id,
                    scope_key,
                    status,
                    retrieved_at,
                    source_url
                FROM risk_source_runs
                WHERE user_id = %s
                  AND snapshot_id = %s
                ORDER BY source_id, scope_key
                """,
                (user_id, snapshot_id),
            )
            sources = tuple(
                SourceEvidenceStatus(
                    source_id=str(cast(dict[str, Any], row)["source_id"]),
                    scope_key=str(cast(dict[str, Any], row)["scope_key"]),
                    status=cast(
                        Literal["received", "partial", "unavailable", "not_configured"],
                        str(cast(dict[str, Any], row)["status"]),
                    ),
                    retrieved_at=cast(datetime, cast(dict[str, Any], row)["retrieved_at"]),
                    source_url=str(cast(dict[str, Any], row)["source_url"]),
                )
                for row in cur.fetchall()
            )

            cur.execute(
                """
                SELECT DISTINCT ON (
                    instrument_uid,
                    event_kind,
                    event_key
                )
                    instrument_uid,
                    event_kind,
                    event_key,
                    event_date,
                    record_date,
                    declared_at,
                    provider_payment_at,
                    amount_value,
                    amount_currency,
                    status,
                    source_id,
                    source_url,
                    normalized
                FROM payout_observations
                WHERE user_id = %s
                  AND event_date BETWEEN %s AND %s
                ORDER BY
                    instrument_uid,
                    event_kind,
                    event_key,
                    observed_at DESC,
                    id DESC
                """,
                (user_id, payout_from, payout_to),
            )
            payouts = tuple(
                _payout_evidence(cast(dict[str, Any], row))
                for row in cur.fetchall()
            )
            payouts = tuple(sorted(payouts, key=lambda item: (item.event_date, item.event_key)))

            return RiskSnapshotSummary(
                snapshot_id=snapshot_id,
                captured_at=cast(datetime, snapshot["captured_at"]),
                assessments=assessments,
                payouts=payouts,
                sources=sources,
            )

    def save_risk_evidence(
        self,
        user_id: UUID,
        *,
        snapshot_id: UUID,
        evidences: tuple[InstrumentRiskEvidence, ...],
        assessments: tuple[RiskAssessment, ...],
    ) -> None:
        """Persist immutable source evidence plus the snapshot-scoped assessment."""
        assessment_by_uid = {item.instrument_uid: item for item in assessments}
        if len(assessment_by_uid) != len(assessments):
            raise ValueError("risk assessments contain duplicate instrument uid")

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT 1
                FROM portfolio_snapshots
                WHERE id = %s
                  AND user_id = %s
                """,
                (snapshot_id, user_id),
            )
            if cur.fetchone() is None:
                raise RuntimeError("risk evidence snapshot does not belong to tenant")

            if {item.instrument_uid for item in evidences} != set(assessment_by_uid):
                raise ValueError(
                    "risk evidence and assessments must cover the same instruments"
                )

            for evidence in evidences:
                assessment = assessment_by_uid.get(evidence.instrument_uid)
                if assessment is None:
                    raise ValueError("risk evidence has no matching assessment")

                sources = {item.source_id: item for item in evidence.sources}
                if len(sources) != len(evidence.sources):
                    raise ValueError("risk evidence contains duplicate source id")

                for source in evidence.sources:
                    cur.execute(
                        """
                        INSERT INTO risk_source_runs (
                            user_id,
                            snapshot_id,
                            source_id,
                            scope_key,
                            status,
                            source_url,
                            retrieved_at,
                            details
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (snapshot_id, source_id, scope_key)
                        DO UPDATE SET
                            status = EXCLUDED.status,
                            source_url = EXCLUDED.source_url,
                            retrieved_at = EXCLUDED.retrieved_at,
                            details = EXCLUDED.details
                        """,
                        (
                            user_id,
                            snapshot_id,
                            source.source_id,
                            source.scope_key,
                            source.status,
                            source.source_url,
                            source.retrieved_at,
                            _json({}),
                        ),
                    )

                if evidence.fundamental is not None:
                    source = sources.get("tbank_fundamentals")
                    if source is None:
                        raise ValueError("fundamental evidence has no source status")
                    fundamental_payload = {
                        "asset_uid": evidence.fundamental.asset_uid,
                        "currency": evidence.fundamental.currency,
                        "fiscal_period_start": evidence.fundamental.fiscal_period_start,
                        "fiscal_period_end": evidence.fundamental.fiscal_period_end,
                        "metrics": evidence.fundamental.metrics,
                    }
                    document_id = self._ensure_source_document(
                        cur,
                        user_id=user_id,
                        source_id=source.source_id,
                        scope_key=source.scope_key,
                        document_kind="asset_fundamentals",
                        source_url=source.source_url,
                        effective_at=evidence.fundamental.fiscal_period_end,
                        publication_at=None,
                        retrieved_at=source.retrieved_at,
                        payload=fundamental_payload,
                    )
                    for metric, value in sorted(evidence.fundamental.metrics.items()):
                        fact_payload = {
                            "value": value,
                            "currency": evidence.fundamental.currency,
                        }
                        cur.execute(
                            """
                            INSERT INTO source_facts (
                                user_id,
                                document_id,
                                instrument_uid,
                                asset_uid,
                                fact_kind,
                                fact_key,
                                effective_at,
                                publication_at,
                                value_json,
                                semantic_hash
                            )
                            VALUES (
                                %s, %s, %s, %s, 'fundamental_metric', %s,
                                %s, NULL, %s::jsonb, %s
                            )
                            ON CONFLICT (document_id, fact_key, semantic_hash) DO NOTHING
                            """,
                            (
                                user_id,
                                document_id,
                                evidence.instrument_uid,
                                evidence.fundamental.asset_uid,
                                metric,
                                evidence.fundamental.fiscal_period_end,
                                _json(fact_payload),
                                _hash_json(fact_payload),
                            ),
                        )

                reports_source = sources.get("tbank_reports")
                if reports_source is not None and reports_source.status == "received":
                    reports_payload = {
                        "events": [
                            {
                                "report_date": item.report_date,
                                "period_year": item.period_year,
                                "period_num": item.period_num,
                                "period_type": item.period_type,
                                "created_at": item.created_at,
                            }
                            for item in evidence.reports
                        ]
                    }
                    document_id = self._ensure_source_document(
                        cur,
                        user_id=user_id,
                        source_id=reports_source.source_id,
                        scope_key=reports_source.scope_key,
                        document_kind="asset_reports",
                        source_url=reports_source.source_url,
                        effective_at=max(
                            (item.report_date for item in evidence.reports),
                            default=None,
                        ),
                        publication_at=max(
                            (item.report_date for item in evidence.reports),
                            default=None,
                        ),
                        retrieved_at=reports_source.retrieved_at,
                        payload=reports_payload,
                    )
                    for item in evidence.reports:
                        fact_key = (
                            f"report:{item.period_year}:{item.period_num}:{item.period_type}"
                        )
                        fact_payload = {
                            "report_date": item.report_date,
                            "created_at": item.created_at,
                        }
                        cur.execute(
                            """
                            INSERT INTO source_facts (
                                user_id,
                                document_id,
                                instrument_uid,
                                fact_kind,
                                fact_key,
                                effective_at,
                                publication_at,
                                value_json,
                                semantic_hash
                            )
                            VALUES (
                                %s, %s, %s, 'report_event', %s, %s, %s,
                                %s::jsonb, %s
                            )
                            ON CONFLICT (document_id, fact_key, semantic_hash) DO NOTHING
                            """,
                            (
                                user_id,
                                document_id,
                                evidence.instrument_uid,
                                fact_key,
                                item.report_date,
                                item.report_date,
                                _json(fact_payload),
                                _hash_json(fact_payload),
                            ),
                        )

                payouts_by_source: dict[str, list[PayoutEvidence]] = {}
                for payout in evidence.payouts:
                    payouts_by_source.setdefault(payout.source_id, []).append(payout)

                for source_id in ("tbank_dividends", "tbank_bond_coupons", "tbank_bond_events"):
                    source = sources.get(source_id)
                    if source is None or source.status != "received":
                        continue
                    source_payouts = payouts_by_source.get(source_id, [])
                    document_payload = {
                        "events": [
                            {
                                "event_key": item.event_key,
                                "kind": item.kind,
                                "event_date": item.event_date,
                                "record_date": item.record_date,
                                "declared_at": item.declared_at,
                                "provider_payment_at": item.provider_payment_at,
                                "amount_value": item.amount_value,
                                "amount_currency": item.amount_currency,
                                "status": item.status,
                                "details": item.details,
                            }
                            for item in source_payouts
                        ]
                    }
                    document_id = self._ensure_source_document(
                        cur,
                        user_id=user_id,
                        source_id=source.source_id,
                        scope_key=source.scope_key,
                        document_kind=source_id.removeprefix("tbank_"),
                        source_url=source.source_url,
                        effective_at=max(
                            (item.event_date for item in source_payouts),
                            default=None,
                        ),
                        publication_at=max(
                            (
                                item.declared_at
                                for item in source_payouts
                                if item.declared_at is not None
                            ),
                            default=None,
                        ),
                        retrieved_at=source.retrieved_at,
                        payload=document_payload,
                    )
                    for payout in source_payouts:
                        normalized = {
                            "event_key": payout.event_key,
                            "kind": payout.kind,
                            "event_date": payout.event_date,
                            "record_date": payout.record_date,
                            "declared_at": payout.declared_at,
                            "provider_payment_at": payout.provider_payment_at,
                            "amount_value": payout.amount_value,
                            "amount_currency": payout.amount_currency,
                            "status": payout.status,
                            "details": payout.details,
                        }
                        semantic_hash = _hash_json(normalized)
                        cur.execute(
                            """
                            INSERT INTO payout_observations (
                                user_id,
                                snapshot_id,
                                source_document_id,
                                instrument_uid,
                                event_kind,
                                event_key,
                                event_date,
                                record_date,
                                declared_at,
                                provider_payment_at,
                                amount_value,
                                amount_currency,
                                status,
                                source_id,
                                source_url,
                                normalized,
                                semantic_hash,
                                observed_at
                            )
                            VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                            )
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                user_id,
                                snapshot_id,
                                document_id,
                                evidence.instrument_uid,
                                payout.kind,
                                payout.event_key,
                                payout.event_date,
                                payout.record_date,
                                payout.declared_at,
                                payout.provider_payment_at,
                                (
                                    Decimal(payout.amount_value)
                                    if payout.amount_value is not None
                                    else None
                                ),
                                payout.amount_currency,
                                payout.status,
                                payout.source_id,
                                payout.source_url,
                                _json(normalized),
                                semantic_hash,
                                assessment.evaluated_at,
                            ),
                        )

                cur.execute(
                    """
                    INSERT INTO risk_assessments (
                        user_id,
                        snapshot_id,
                        instrument_uid,
                        ticker,
                        state,
                        sector_model,
                        coverage,
                        reasons,
                        evaluated_at,
                        latest_fundamental_period_end,
                        latest_report_date
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s
                    )
                    ON CONFLICT (snapshot_id, instrument_uid)
                    DO UPDATE SET
                        ticker = EXCLUDED.ticker,
                        state = EXCLUDED.state,
                        sector_model = EXCLUDED.sector_model,
                        coverage = EXCLUDED.coverage,
                        reasons = EXCLUDED.reasons,
                        evaluated_at = EXCLUDED.evaluated_at,
                        latest_fundamental_period_end =
                            EXCLUDED.latest_fundamental_period_end,
                        latest_report_date = EXCLUDED.latest_report_date
                    """,
                    (
                        user_id,
                        snapshot_id,
                        assessment.instrument_uid,
                        assessment.ticker,
                        assessment.state,
                        assessment.sector_model,
                        assessment.coverage,
                        _json([asdict(reason) for reason in assessment.reasons]),
                        assessment.evaluated_at,
                        assessment.latest_fundamental_period_end,
                        assessment.latest_report_date,
                    ),
                )

    @staticmethod
    def _ensure_source_document(
        cur: Any,
        *,
        user_id: UUID,
        source_id: str,
        scope_key: str,
        document_kind: str,
        source_url: str,
        effective_at: datetime | None,
        publication_at: datetime | None,
        retrieved_at: datetime,
        payload: dict[str, object],
    ) -> UUID:
        content_hash = _hash_json(payload)
        cur.execute(
            """
            INSERT INTO source_documents (
                user_id,
                source_id,
                scope_key,
                document_kind,
                source_url,
                effective_at,
                publication_at,
                retrieved_at,
                content_hash,
                payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (
                user_id,
                source_id,
                scope_key,
                document_kind,
                content_hash
            )
            DO NOTHING
            RETURNING id
            """,
            (
                user_id,
                source_id,
                scope_key,
                document_kind,
                source_url,
                effective_at,
                publication_at,
                retrieved_at,
                content_hash,
                _json(payload),
            ),
        )
        row = cur.fetchone()
        if row is not None:
            return cast(UUID, cast(dict[str, Any], row)["id"])
        cur.execute(
            """
            SELECT id
            FROM source_documents
            WHERE user_id = %s
              AND source_id = %s
              AND scope_key = %s
              AND document_kind = %s
              AND content_hash = %s
            """,
            (user_id, source_id, scope_key, document_kind, content_hash),
        )
        existing = cur.fetchone()
        if existing is None:
            raise RuntimeError("source document conflict could not be resolved")
        return cast(UUID, cast(dict[str, Any], existing)["id"])

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
        if window_from.tzinfo is None or window_to.tzinfo is None:
            raise ValueError("history window must be timezone-aware")
        inserted = 0
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            for operation in page.items:
                normalized = _operation_payload(operation)
                semantic = _semantic_operation_payload(normalized)
                observation_hash = _hash_json(normalized)
                semantic_hash = _hash_json(semantic)
                cur.execute(
                    """
                    INSERT INTO operation_observations (
                        user_id,
                        account_id,
                        observation_hash,
                        semantic_hash,
                        provider_operation_id,
                        provider_cursor,
                        operation_date,
                        operation_type,
                        operation_state,
                        instrument_uid,
                        figi,
                        instrument_type,
                        payment_value,
                        payment_currency,
                        price_value,
                        price_currency,
                        commission_value,
                        commission_currency,
                        accrued_int_value,
                        accrued_int_currency,
                        quantity,
                        quantity_rest,
                        quantity_done,
                        normalized,
                        observed_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        user_id,
                        account_id,
                        observation_hash,
                        semantic_hash,
                        operation.id,
                        operation.cursor,
                        operation.date,
                        operation.operation_type,
                        operation.state,
                        operation.instrument_uid,
                        operation.figi,
                        operation.instrument_type,
                        _money_decimal(operation.payment),
                        operation.payment.currency if operation.payment else None,
                        _money_decimal(operation.price),
                        operation.price.currency if operation.price else None,
                        _money_decimal(operation.commission),
                        operation.commission.currency if operation.commission else None,
                        _money_decimal(operation.accrued_int),
                        operation.accrued_int.currency if operation.accrued_int else None,
                        Decimal(operation.quantity),
                        Decimal(operation.quantity_rest),
                        Decimal(operation.quantity_done),
                        _json(normalized),
                        observed_at,
                    ),
                )
                if cur.fetchone() is not None:
                    inserted += 1

            if page.has_next:
                if not page.next_cursor:
                    raise RuntimeError("history page has_next without a cursor")
                state_values: tuple[object, ...] = (
                    user_id,
                    account_id,
                    window_from,
                    window_to,
                    page.next_cursor,
                )
                cur.execute(
                    """
                    INSERT INTO broker_sync_state (
                        user_id,
                        account_id,
                        history_window_from,
                        history_window_to,
                        pending_cursor
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, account_id) DO UPDATE SET
                        history_window_from = EXCLUDED.history_window_from,
                        history_window_to = EXCLUDED.history_window_to,
                        pending_cursor = EXCLUDED.pending_cursor,
                        updated_at = now()
                    """,
                    state_values,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO broker_sync_state (
                        user_id,
                        account_id,
                        last_complete_watermark
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, account_id) DO UPDATE SET
                        history_window_from = NULL,
                        history_window_to = NULL,
                        pending_cursor = NULL,
                        last_complete_watermark = EXCLUDED.last_complete_watermark,
                        updated_at = now()
                    """,
                    (user_id, account_id, window_to),
                )
        return inserted


def _source_url(
    sources: tuple[SourceEvidenceStatus, ...],
    source_id: str,
) -> str:
    for source in sources:
        if source.source_id == source_id:
            return source.source_url
    raise ValueError(f"missing source evidence: {source_id}")


def _risk_assessment(row: dict[str, Any]) -> RiskAssessment:
    reasons_raw = row["reasons"]
    if not isinstance(reasons_raw, list):
        raise RuntimeError("stored risk reasons are malformed")
    reasons: list[RiskReason] = []
    for raw in reasons_raw:
        if not isinstance(raw, dict):
            raise RuntimeError("stored risk reason is malformed")
        source_ids = raw.get("source_ids", [])
        if not isinstance(source_ids, list) or not all(
            isinstance(value, str) for value in source_ids
        ):
            raise RuntimeError("stored risk reason sources are malformed")
        reasons.append(
            RiskReason(
                code=str(raw.get("code", "")),
                severity=cast(
                    Literal["info", "watch", "elevated", "critical"],
                    str(raw.get("severity", "")),
                ),
                title=str(raw.get("title", "")),
                detail=str(raw.get("detail", "")),
                source_ids=tuple(source_ids),
            )
        )
    return RiskAssessment(
        instrument_uid=str(row["instrument_uid"]),
        ticker=str(row["ticker"]),
        state=cast(
            Literal[
                "data_missing",
                "normal",
                "watch",
                "elevated",
                "critical",
                "confirmed_default",
            ],
            str(row["state"]),
        ),
        sector_model=str(row["sector_model"]),
        coverage=cast(
            Literal["complete", "partial", "missing"],
            str(row["coverage"]),
        ),
        reasons=tuple(reasons),
        evaluated_at=cast(datetime, row["evaluated_at"]),
        latest_fundamental_period_end=cast(
            datetime | None,
            row["latest_fundamental_period_end"],
        ),
        latest_report_date=cast(datetime | None, row["latest_report_date"]),
    )


def _payout_evidence(row: dict[str, Any]) -> PayoutEvidence:
    normalized = row["normalized"]
    if not isinstance(normalized, dict):
        raise RuntimeError("stored payout evidence is malformed")
    details = normalized.get("details", {})
    if not isinstance(details, dict):
        raise RuntimeError("stored payout details are malformed")
    amount = row["amount_value"]
    return PayoutEvidence(
        instrument_uid=str(row["instrument_uid"]),
        kind=cast(Literal["dividend", "coupon", "bond_event"], str(row["event_kind"])),
        event_key=str(row["event_key"]),
        event_date=cast(datetime, row["event_date"]),
        record_date=cast(datetime | None, row["record_date"]),
        declared_at=cast(datetime | None, row["declared_at"]),
        provider_payment_at=cast(datetime | None, row["provider_payment_at"]),
        amount_value=str(amount) if amount is not None else None,
        amount_currency=(
            str(row["amount_currency"])
            if row["amount_currency"] is not None
            else None
        ),
        status=str(row["status"]),
        source_id=str(row["source_id"]),
        source_url=str(row["source_url"]),
        details=cast(dict[str, object], details),
    )


def _profile(row: dict[str, Any]) -> InvestmentProfileRecord:
    return InvestmentProfileRecord(
        id=int(row["id"]),
        user_id=cast(UUID, row["user_id"]),
        version=int(row["version"]),
        reserve_rub=Decimal(row["reserve_rub"]),
        planned_withdrawal_rub=Decimal(row["planned_withdrawal_rub"]),
        horizon_months=int(row["horizon_months"]),
        max_drawdown_percent=Decimal(row["max_drawdown_percent"]),
        liquidity_horizon_days=int(row["liquidity_horizon_days"]),
        allow_below_investment_grade=bool(row["allow_below_investment_grade"]),
        created_at=cast(datetime, row["created_at"]),
    )


def _job_run(row: dict[str, Any]) -> JobRunRecord:
    return JobRunRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        job_type=str(row["job_type"]),
        scheduled_for=cast(date, row["scheduled_for"]),
        status=cast(JobStatus, str(row["status"])),
        attempt=int(row["attempt"]),
        started_at=cast(datetime, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
    )


def _sync_state(row: dict[str, Any]) -> BrokerSyncState:
    return BrokerSyncState(
        user_id=cast(UUID, row["user_id"]),
        account_id=str(row["account_id"]),
        history_window_from=cast(datetime | None, row["history_window_from"]),
        history_window_to=cast(datetime | None, row["history_window_to"]),
        pending_cursor=str(row["pending_cursor"]),
        last_complete_watermark=cast(datetime | None, row["last_complete_watermark"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _money_decimal(value: TBankMoney | None) -> Decimal | None:
    return Decimal(value.value) if value is not None else None


def _money_payload(value: TBankMoney | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"currency": value.currency, "value": value.value}


def _operation_payload(operation: TBankOperation) -> dict[str, object]:
    return {
        "provider_operation_id": operation.id,
        "parent_operation_id": operation.parent_operation_id,
        "broker_account_id": operation.broker_account_id,
        "name": operation.name,
        "date": operation.date.astimezone(UTC).isoformat(),
        "operation_type": operation.operation_type,
        "description": operation.description,
        "state": operation.state,
        "instrument_uid": operation.instrument_uid,
        "figi": operation.figi,
        "instrument_type": operation.instrument_type,
        "position_uid": operation.position_uid,
        "ticker": operation.ticker,
        "class_code": operation.class_code,
        "payment": _money_payload(operation.payment),
        "price": _money_payload(operation.price),
        "commission": _money_payload(operation.commission),
        "accrued_int": _money_payload(operation.accrued_int),
        "quantity": operation.quantity,
        "quantity_rest": operation.quantity_rest,
        "quantity_done": operation.quantity_done,
        "asset_uid": operation.asset_uid,
        "trades": [
            {
                "num": trade.num,
                "date": trade.date.astimezone(UTC).isoformat(),
                "quantity": trade.quantity,
                "price": _money_payload(trade.price),
            }
            for trade in operation.trades
        ],
    }


def _semantic_operation_payload(normalized: dict[str, object]) -> dict[str, object]:
    # T-Invest documents that operation IDs may change over time. The provider ID
    # is retained as provenance but excluded from this semantic lineage hash.
    return {
        key: value
        for key, value in normalized.items()
        if key not in {"provider_operation_id", "parent_operation_id"}
    }


def _hash_json(value: object) -> bytes:
    return hashlib.sha256(
        _json(value).encode("utf-8"),
        usedforsecurity=False,
    ).digest()


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    )


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")
