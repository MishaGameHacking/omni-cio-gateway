"""Persistence boundary for durable portfolio observation and user policy data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from .broker import BrokerObservationBundle
from .db import Database
from .tbank import TBankMoney, TBankOperation, TBankOperationsPage

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
                          (status = 'running' AND started_at < now() - interval '30 minutes')
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
                    (user_id, job_type, scheduled_for),
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
    ) -> UUID:
        evidence = {
            "analysis": asdict(bundle.analysis),
            "sources": [asdict(source) for source in bundle.sources],
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
            for item in bundle.metadata:
                cur.execute(
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
                    ),
                )
                cur.execute(
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
                    (
                        user_id,
                        bundle.account_id,
                        item.uid,
                        _json(list(item.required_tests)),
                        catalog_retrieved_at,
                    ),
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
                    ON CONFLICT (user_id, account_id, observation_hash) DO NOTHING
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


def _hash_json(value: dict[str, object]) -> bytes:
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
