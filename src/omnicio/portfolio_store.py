"""Persistence boundary for durable portfolio observation and user policy data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from .broker import BrokerObservationBundle
from .db import Database
from .intelligence import (
    EVIDENCE_RETRIEVAL_MAX_AGE,
    EvidenceDocument,
    InstrumentRiskAssessment,
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
class BalancingPolicyRecord:
    id: int
    user_id: UUID
    version: int
    max_instrument_percent: Decimal
    max_sector_percent: Decimal
    max_issuer_percent: Decimal
    max_group_percent: Decimal
    max_share_percent: Decimal
    max_bond_percent: Decimal
    max_etf_percent: Decimal
    max_below_grade_percent: Decimal
    max_unknown_percent: Decimal
    max_term_months: int
    turnover_budget_percent: Decimal
    max_daily_turnover_participation_percent: Decimal
    securities_tax_rate_percent: Decimal
    no_trade_band_percent: Decimal
    min_replace_benefit_rub: Decimal
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

    def current_balancing_policy(
        self,
        user_id: UUID,
    ) -> BalancingPolicyRecord | None:
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
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub,
                    created_at
                FROM balancing_policy_versions
                WHERE user_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _balancing_policy(cast(dict[str, Any], fetched))

    def save_balancing_policy(
        self,
        user_id: UUID,
        *,
        max_instrument_percent: Decimal,
        max_sector_percent: Decimal,
        max_issuer_percent: Decimal,
        max_group_percent: Decimal,
        max_share_percent: Decimal,
        max_bond_percent: Decimal,
        max_etf_percent: Decimal,
        max_below_grade_percent: Decimal,
        max_unknown_percent: Decimal,
        max_term_months: int,
        turnover_budget_percent: Decimal,
        max_daily_turnover_participation_percent: Decimal,
        securities_tax_rate_percent: Decimal,
        no_trade_band_percent: Decimal,
        min_replace_benefit_rub: Decimal,
    ) -> BalancingPolicyRecord:
        desired = (
            max_instrument_percent,
            max_sector_percent,
            max_issuer_percent,
            max_group_percent,
            max_share_percent,
            max_bond_percent,
            max_etf_percent,
            max_below_grade_percent,
            max_unknown_percent,
            max_term_months,
            turnover_budget_percent,
            max_daily_turnover_participation_percent,
            securities_tax_rate_percent,
            no_trade_band_percent,
            min_replace_benefit_rub,
        )
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"balancing-policy:{user_id}",),
            )
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    version,
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub,
                    created_at
                FROM balancing_policy_versions
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
                latest = _balancing_policy(cast(dict[str, Any], latest_row))
                current = (
                    latest.max_instrument_percent,
                    latest.max_sector_percent,
                    latest.max_issuer_percent,
                    latest.max_group_percent,
                    latest.max_share_percent,
                    latest.max_bond_percent,
                    latest.max_etf_percent,
                    latest.max_below_grade_percent,
                    latest.max_unknown_percent,
                    latest.max_term_months,
                    latest.turnover_budget_percent,
                    latest.max_daily_turnover_participation_percent,
                    latest.securities_tax_rate_percent,
                    latest.no_trade_band_percent,
                    latest.min_replace_benefit_rub,
                )
                if current == desired:
                    return latest
                version = latest.version + 1

            cur.execute(
                """
                INSERT INTO balancing_policy_versions (
                    user_id,
                    version,
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING
                    id,
                    user_id,
                    version,
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub,
                    created_at
                """,
                (user_id, version, *desired),
            )
            fetched = cur.fetchone()
            if fetched is None:
                raise RuntimeError("balancing policy insert returned no row")
            return _balancing_policy(cast(dict[str, Any], fetched))

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
                        _money_decimal(item.nominal),
                        item.nominal.currency if item.nominal else None,
                        item.maturity_date,
                        item.floating_coupon,
                        item.perpetual,
                        item.amortization,
                        item.subordinated,
                        item.liquidity,
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
                        nominal_value,
                        nominal_currency,
                        maturity_date,
                        floating_coupon,
                        perpetual,
                        amortization,
                        subordinated,
                        liquidity,
                        provider_retrieved_at
                    )
                    VALUES (
                        'tbank', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
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
                        nominal_value = EXCLUDED.nominal_value,
                        nominal_currency = EXCLUDED.nominal_currency,
                        maturity_date = EXCLUDED.maturity_date,
                        floating_coupon = EXCLUDED.floating_coupon,
                        perpetual = EXCLUDED.perpetual,
                        amortization = EXCLUDED.amortization,
                        subordinated = EXCLUDED.subordinated,
                        liquidity = EXCLUDED.liquidity,
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
                        quantity_lots,
                        current_price_value,
                        current_price_currency,
                        current_nkd_value,
                        current_nkd_currency,
                        average_price_fifo_value,
                        average_price_fifo_currency,
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
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
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
                        Decimal(position.quantity_lots),
                        _money_decimal(position.current_price),
                        position.current_price.currency if position.current_price else None,
                        _money_decimal(position.current_nkd),
                        position.current_nkd.currency if position.current_nkd else None,
                        _money_decimal(position.average_price_fifo),
                        (
                            position.average_price_fifo.currency
                            if position.average_price_fifo
                            else None
                        ),
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

    def save_evidence(
        self,
        user_id: UUID,
        *,
        snapshot_id: UUID,
        documents: tuple[EvidenceDocument, ...],
        assessments: tuple[InstrumentRiskAssessment, ...],
        retrieved_at: datetime,
    ) -> tuple[int, int]:
        if retrieved_at.tzinfo is None:
            raise ValueError("evidence retrieval time must be timezone-aware")
        documents_written = 0
        assessments_written = 0
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            for document in documents:
                content_hash = _hash_json(document.payload)
                cur.execute(
                    """
                    INSERT INTO source_documents (
                        provider,
                        document_type,
                        subject_uid,
                        provider_key,
                        source_url,
                        published_at,
                        effective_at,
                        first_retrieved_at,
                        content_hash,
                        payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (
                        provider,
                        document_type,
                        subject_uid,
                        provider_key,
                        content_hash
                    ) DO NOTHING
                    RETURNING id
                    """,
                    (
                        document.provider,
                        document.document_type,
                        document.subject_uid,
                        document.provider_key,
                        document.source_url,
                        document.published_at,
                        document.effective_at,
                        retrieved_at,
                        content_hash,
                        _json(document.payload),
                    ),
                )
                inserted = cur.fetchone()
                if inserted is None:
                    cur.execute(
                        """
                        SELECT id
                        FROM source_documents
                        WHERE provider = %s
                          AND document_type = %s
                          AND subject_uid = %s
                          AND provider_key = %s
                          AND content_hash = %s
                        """,
                        (
                            document.provider,
                            document.document_type,
                            document.subject_uid,
                            document.provider_key,
                            content_hash,
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted is None:
                        raise RuntimeError("evidence document conflict could not be resolved")
                else:
                    documents_written += 1
                document_id = cast(UUID, cast(dict[str, Any], inserted)["id"])

                cur.execute(
                    """
                    INSERT INTO source_retrievals (source_document_id, retrieved_at)
                    VALUES (%s, %s)
                    ON CONFLICT (source_document_id, retrieved_at) DO NOTHING
                    """,
                    (document_id, retrieved_at),
                )

                for fact in document.facts:
                    fact_payload = {
                        "subject_uid": fact.subject_uid,
                        "fact_type": fact.fact_type,
                        "fact_key": fact.fact_key,
                        "value_numeric": fact.value_numeric,
                        "value_text": fact.value_text,
                        "currency": fact.currency,
                        "unit": fact.unit,
                        "effective_at": fact.effective_at,
                        "published_at": fact.published_at,
                        "payload": fact.payload or {},
                    }
                    cur.execute(
                        """
                        INSERT INTO source_facts (
                            source_document_id,
                            subject_uid,
                            fact_type,
                            fact_key,
                            value_numeric,
                            value_text,
                            currency,
                            unit,
                            effective_at,
                            published_at,
                            payload,
                            semantic_hash
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                        )
                        ON CONFLICT (source_document_id, semantic_hash) DO NOTHING
                        """,
                        (
                            document_id,
                            fact.subject_uid,
                            fact.fact_type,
                            fact.fact_key,
                            fact.value_numeric,
                            fact.value_text,
                            fact.currency,
                            fact.unit,
                            fact.effective_at,
                            fact.published_at,
                            _json(fact.payload or {}),
                            _hash_json(fact_payload),
                        ),
                    )

                if document.payout is not None:
                    payout = document.payout
                    payout_payload = {
                        "provider": document.provider,
                        "instrument_uid": payout.instrument_uid,
                        "event_type": payout.event_type,
                        "provider_key": payout.provider_key,
                        "announced_at": payout.announced_at,
                        "record_at": payout.record_at,
                        "expected_at": payout.expected_at,
                        "actual_at": payout.actual_at,
                        "amount": payout.amount,
                        "currency": payout.currency,
                        "status": payout.status,
                        "payload": payout.payload,
                    }
                    cur.execute(
                        """
                        INSERT INTO payout_events (
                            source_document_id,
                            provider,
                            instrument_uid,
                            event_type,
                            provider_key,
                            announced_at,
                            record_at,
                            expected_at,
                            actual_at,
                            amount,
                            currency,
                            status,
                            payload,
                            semantic_hash
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                        )
                        ON CONFLICT (
                            provider,
                            instrument_uid,
                            event_type,
                            provider_key,
                            semantic_hash
                        ) DO NOTHING
                        """,
                        (
                            document_id,
                            document.provider,
                            payout.instrument_uid,
                            payout.event_type,
                            payout.provider_key,
                            payout.announced_at,
                            payout.record_at,
                            payout.expected_at,
                            payout.actual_at,
                            payout.amount,
                            payout.currency,
                            payout.status,
                            _json(payout.payload),
                            _hash_json(payout_payload),
                        ),
                    )

            for assessment in assessments:
                cur.execute(
                    """
                    INSERT INTO portfolio_risk_assessments (
                        user_id,
                        snapshot_id,
                        instrument_uid,
                        state,
                        rating_status,
                        fundamental_status,
                        source_status,
                        reasons,
                        evidence,
                        assessed_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT (snapshot_id, instrument_uid) DO NOTHING
                    RETURNING id
                    """,
                    (
                        user_id,
                        snapshot_id,
                        assessment.instrument_uid,
                        assessment.state,
                        assessment.rating_status,
                        assessment.fundamental_status,
                        assessment.source_status,
                        _json(list(assessment.reasons)),
                        _json(assessment.evidence),
                        retrieved_at,
                    ),
                )
                if cur.fetchone() is not None:
                    assessments_written += 1
        return documents_written, assessments_written

    def latest_balancing_context(
        self,
        user_id: UUID,
        *,
        candidate_limit: int = 100,
    ) -> dict[str, object] | None:
        if not 1 <= candidate_limit <= 500:
            raise ValueError("candidate_limit must be between 1 and 500")
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
                    account_id,
                    captured_at,
                    analysis_status,
                    nav_rub,
                    rub_cash_unblocked,
                    limits_loading_in_progress,
                    evidence
                FROM portfolio_snapshots
                WHERE user_id = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            snapshot = dict(cast(dict[str, Any], fetched))
            snapshot_id = cast(UUID, snapshot["id"])
            account_id = str(snapshot["account_id"])

            cur.execute(
                """
                SELECT
                    p.instrument_uid,
                    p.figi,
                    p.ticker,
                    p.instrument_type,
                    p.quantity,
                    p.quantity_lots,
                    p.average_price_fifo_value,
                    p.average_price_fifo_currency,
                    p.blocked,
                    p.blocked_lots,
                    p.value_rub,
                    p.sector,
                    COALESCE(c.lot, 0) AS lot,
                    COALESCE(c.currency, '') AS currency,
                    COALESCE(i.id::text, '') AS issuer_id,
                    COALESCE(i.group_id::text, '') AS group_id,
                    COALESCE(i.country_code, '') AS issuer_country_code,
                    COALESCE(i.source_url, '') AS issuer_source_url,
                    COALESCE(r.state, 'data_missing') AS risk_state,
                    COALESCE(r.rating_status, 'data_missing') AS rating_status
                FROM portfolio_snapshot_positions AS p
                LEFT JOIN instrument_catalog AS c
                  ON c.provider = 'tbank'
                 AND (
                     c.instrument_uid = p.instrument_uid
                     OR (p.figi <> '' AND c.figi = p.figi)
                 )
                LEFT JOIN instrument_issuer_map AS m
                  ON m.provider = 'tbank'
                 AND m.instrument_uid = c.instrument_uid
                LEFT JOIN issuers AS i
                  ON i.id = m.issuer_id
                LEFT JOIN portfolio_risk_assessments AS r
                  ON r.snapshot_id = p.snapshot_id
                 AND r.user_id = p.user_id
                 AND r.instrument_uid = p.instrument_uid
                WHERE p.snapshot_id = %s
                  AND p.user_id = %s
                ORDER BY p.value_rub DESC NULLS LAST, p.ticker
                """,
                (snapshot_id, user_id),
            )
            holdings = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    c.instrument_uid,
                    c.figi,
                    c.asset_uid,
                    c.ticker,
                    c.name,
                    c.isin,
                    c.instrument_type,
                    c.currency,
                    c.class_code,
                    c.lot,
                    c.sector,
                    c.country_of_risk,
                    c.for_qual_investor,
                    c.for_iis,
                    c.api_trade_available,
                    c.buy_available,
                    c.sell_available,
                    c.nominal_value,
                    c.nominal_currency,
                    c.maturity_date,
                    c.floating_coupon,
                    c.perpetual,
                    c.amortization,
                    c.subordinated,
                    c.liquidity,
                    c.provider_retrieved_at,
                    a.required_tests,
                    a.observed_at AS access_observed_at,
                    COALESCE(i.id::text, '') AS issuer_id,
                    COALESCE(i.group_id::text, '') AS group_id,
                    COALESCE(i.country_code, '') AS issuer_country_code,
                    COALESCE(i.source_url, '') AS issuer_source_url
                FROM instrument_catalog AS c
                JOIN account_instrument_access AS a
                  ON a.user_id = %s
                 AND a.account_id = %s
                 AND a.provider = c.provider
                 AND a.instrument_uid = c.instrument_uid
                LEFT JOIN instrument_issuer_map AS m
                  ON m.provider = c.provider
                 AND m.instrument_uid = c.instrument_uid
                LEFT JOIN issuers AS i
                  ON i.id = m.issuer_id
                WHERE c.provider = 'tbank'
                  AND c.instrument_type = ANY (ARRAY['share', 'bond', 'etf'])
                  AND c.currency = 'RUB'
                ORDER BY
                    CASE c.instrument_type
                        WHEN 'bond' THEN 0
                        WHEN 'share' THEN 1
                        ELSE 2
                    END,
                    c.ticker,
                    c.instrument_uid
                LIMIT %s
                """,
                (user_id, account_id, candidate_limit),
            )
            candidates = [dict(row) for row in cur.fetchall()]

        evidence = snapshot.get("evidence")
        broker_user: dict[str, object] = {}
        account: dict[str, object] = {}
        if isinstance(evidence, dict):
            broker_raw = evidence.get("broker_user")
            account_raw = evidence.get("account")
            if isinstance(broker_raw, dict):
                broker_user = dict(cast(dict[str, object], broker_raw))
            if isinstance(account_raw, dict):
                account = dict(cast(dict[str, object], account_raw))

        return {
            "snapshot_id": str(snapshot_id),
            "account_id": account_id,
            "captured_at": snapshot["captured_at"],
            "analysis_status": snapshot["analysis_status"],
            "nav_rub": snapshot["nav_rub"],
            "rub_cash_unblocked": snapshot["rub_cash_unblocked"],
            "limits_loading_in_progress": snapshot["limits_loading_in_progress"],
            "broker_user": broker_user,
            "account": account,
            "holdings": holdings,
            "candidates": candidates,
        }

    def latest_intelligence(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, object] | None:
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            raise ValueError("intelligence time must be timezone-aware")
        observed_at = observed_at.astimezone(UTC)
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT id, captured_at, analysis_status
                FROM portfolio_snapshots
                WHERE user_id = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            snapshot = cur.fetchone()
            if snapshot is None:
                return None
            snapshot_row = cast(dict[str, Any], snapshot)
            snapshot_id = cast(UUID, snapshot_row["id"])

            cur.execute(
                """
                SELECT
                    p.instrument_uid,
                    p.ticker,
                    p.instrument_type,
                    p.sector,
                    p.value_rub,
                    p.nav_percent,
                    r.state,
                    r.rating_status,
                    r.fundamental_status,
                    r.source_status,
                    r.reasons,
                    r.evidence,
                    r.assessed_at
                FROM portfolio_snapshot_positions AS p
                LEFT JOIN portfolio_risk_assessments AS r
                  ON r.snapshot_id = p.snapshot_id
                 AND r.user_id = p.user_id
                 AND r.instrument_uid = p.instrument_uid
                WHERE p.snapshot_id = %s
                  AND p.user_id = %s
                ORDER BY
                    CASE COALESCE(r.state, 'data_missing')
                        WHEN 'confirmed_default' THEN 0
                        WHEN 'critical' THEN 1
                        WHEN 'elevated' THEN 2
                        WHEN 'watch' THEN 3
                        WHEN 'data_missing' THEN 4
                        ELSE 5
                    END,
                    p.nav_percent DESC NULLS LAST,
                    p.ticker
                """,
                (snapshot_id, user_id),
            )
            risk_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                WITH held AS (
                    SELECT p.instrument_uid
                    FROM portfolio_snapshot_positions AS p
                    WHERE p.snapshot_id = %s
                      AND p.user_id = %s
                    UNION
                    SELECT c.instrument_uid
                    FROM portfolio_snapshot_positions AS p
                    JOIN instrument_catalog AS c
                      ON c.provider = 'tbank'
                     AND (
                         c.instrument_uid = p.instrument_uid
                         OR (p.figi <> '' AND c.figi = p.figi)
                     )
                    WHERE p.snapshot_id = %s
                      AND p.user_id = %s
                ),
                latest AS (
                    SELECT DISTINCT ON (
                        pe.provider,
                        pe.instrument_uid,
                        pe.event_type,
                        pe.provider_key
                    )
                        pe.provider,
                        pe.instrument_uid,
                        pe.event_type,
                        pe.provider_key,
                        pe.announced_at,
                        pe.record_at,
                        pe.expected_at,
                        pe.actual_at,
                        pe.amount,
                        pe.currency,
                        pe.status,
                        pe.payload,
                        sd.source_url,
                        sd.first_retrieved_at
                    FROM payout_events AS pe
                    JOIN source_documents AS sd
                      ON sd.id = pe.source_document_id
                    JOIN held
                      ON held.instrument_uid = pe.instrument_uid
                    ORDER BY
                        pe.provider,
                        pe.instrument_uid,
                        pe.event_type,
                        pe.provider_key,
                        sd.first_retrieved_at DESC,
                        pe.id DESC
                )
                SELECT *
                FROM latest
                WHERE COALESCE(actual_at, expected_at, announced_at)
                    >= now() - interval '45 days'
                ORDER BY
                    COALESCE(actual_at, expected_at, announced_at) ASC NULLS LAST,
                    instrument_uid
                LIMIT 200
                """,
                (snapshot_id, user_id, snapshot_id, user_id),
            )
            payout_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                WITH held_subjects AS (
                    SELECT p.instrument_uid AS subject_uid
                    FROM portfolio_snapshot_positions AS p
                    WHERE p.snapshot_id = %s
                      AND p.user_id = %s
                    UNION
                    SELECT c.instrument_uid
                    FROM portfolio_snapshot_positions AS p
                    JOIN instrument_catalog AS c
                      ON c.provider = 'tbank'
                     AND (
                         c.instrument_uid = p.instrument_uid
                         OR (p.figi <> '' AND c.figi = p.figi)
                     )
                    WHERE p.snapshot_id = %s
                      AND p.user_id = %s
                    UNION
                    SELECT c.asset_uid
                    FROM portfolio_snapshot_positions AS p
                    JOIN instrument_catalog AS c
                      ON c.provider = 'tbank'
                     AND (
                         c.instrument_uid = p.instrument_uid
                         OR (p.figi <> '' AND c.figi = p.figi)
                     )
                    WHERE p.snapshot_id = %s
                      AND p.user_id = %s
                      AND c.asset_uid <> ''
                )
                SELECT
                    sd.provider,
                    sd.document_type,
                    min(sd.source_url) AS source_url,
                    max(sr.retrieved_at) AS retrieved_at,
                    count(DISTINCT sd.id) AS versions
                FROM source_documents AS sd
                JOIN source_retrievals AS sr
                  ON sr.source_document_id = sd.id
                JOIN held_subjects AS hs
                  ON hs.subject_uid = sd.subject_uid
                GROUP BY sd.provider, sd.document_type
                ORDER BY sd.provider, sd.document_type
                """,
                (
                    snapshot_id,
                    user_id,
                    snapshot_id,
                    user_id,
                    snapshot_id,
                    user_id,
                ),
            )
            source_rows = [dict(row) for row in cur.fetchall()]

        captured_at = cast(datetime, snapshot_row["captured_at"]).astimezone(UTC)
        snapshot_age = _age_seconds(captured_at, now=observed_at)
        snapshot_freshness = _freshness_status(captured_at, now=observed_at)
        for row in risk_rows:
            assessed_at = cast(datetime | None, row.get("assessed_at"))
            row["assessment_freshness"] = _freshness_status(
                assessed_at,
                now=observed_at,
            )
        for row in source_rows:
            retrieved_at = cast(datetime | None, row.get("retrieved_at"))
            row["freshness_status"] = _freshness_status(
                retrieved_at,
                now=observed_at,
            )
            row["age_seconds"] = _age_seconds(retrieved_at, now=observed_at)

        return {
            "snapshot_id": str(snapshot_id),
            "captured_at": captured_at,
            "snapshot_age_seconds": snapshot_age,
            "snapshot_freshness": snapshot_freshness,
            "analysis_status": snapshot_row["analysis_status"],
            "execution_enabled": False,
            "rating_feed_status": "data_missing",
            "risks": risk_rows,
            "payouts": payout_rows,
            "sources": source_rows,
        }

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


def _age_seconds(value: datetime | None, *, now: datetime) -> int | None:
    if value is None or value.tzinfo is None or now.tzinfo is None:
        return None
    delta = now.astimezone(UTC) - value.astimezone(UTC)
    if delta.total_seconds() < 0:
        return None
    return int(delta.total_seconds())


def _freshness_status(
    value: datetime | None,
    *,
    now: datetime,
) -> Literal["fresh", "stale", "data_missing"]:
    if value is None:
        return "data_missing"
    age = _age_seconds(value, now=now)
    if age is None:
        return "stale"
    return (
        "stale"
        if age > int(EVIDENCE_RETRIEVAL_MAX_AGE.total_seconds())
        else "fresh"
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


def _balancing_policy(row: dict[str, Any]) -> BalancingPolicyRecord:
    return BalancingPolicyRecord(
        id=int(row["id"]),
        user_id=cast(UUID, row["user_id"]),
        version=int(row["version"]),
        max_instrument_percent=Decimal(row["max_instrument_percent"]),
        max_sector_percent=Decimal(row["max_sector_percent"]),
        max_issuer_percent=Decimal(row["max_issuer_percent"]),
        max_group_percent=Decimal(row["max_group_percent"]),
        max_share_percent=Decimal(row["max_share_percent"]),
        max_bond_percent=Decimal(row["max_bond_percent"]),
        max_etf_percent=Decimal(row["max_etf_percent"]),
        max_below_grade_percent=Decimal(row["max_below_grade_percent"]),
        max_unknown_percent=Decimal(row["max_unknown_percent"]),
        max_term_months=int(row["max_term_months"]),
        turnover_budget_percent=Decimal(row["turnover_budget_percent"]),
        max_daily_turnover_participation_percent=Decimal(
            row["max_daily_turnover_participation_percent"]
        ),
        securities_tax_rate_percent=Decimal(row["securities_tax_rate_percent"]),
        no_trade_band_percent=Decimal(row["no_trade_band_percent"]),
        min_replace_benefit_rub=Decimal(row["min_replace_benefit_rub"]),
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


def _hash_json(value: Mapping[str, object]) -> bytes:
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
