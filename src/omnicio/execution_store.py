"""PostgreSQL persistence for R6/R7 execution and live-mandate ledgers."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from .db import Database
from .execution import (
    ExecutionLegStatus,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRunStatus,
    ExecutionStateError,
    build_execution_plan,
    run_status_for_legs,
)
from .portfolio_store import PortfolioProposalRecord, PortfolioStore

_TERMINAL_RUNS = {"succeeded", "cancelled", "failed"}
_TERMINAL_LEGS = {"filled", "cancelled", "rejected", "failed", "shadow_filled"}
_ADVISORY_XACT_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"
_PROVIDER_ENVIRONMENT: dict[ExecutionMode, str | None] = {
    "shadow": None,
    "sandbox": "sandbox",
    "live": "prod",
}


class ExecutionLedgerError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionRunRecord:
    id: UUID
    user_id: UUID
    proposal_id: UUID
    confirmed_action_id: int
    proposal_version: int
    proposal_hash: bytes
    account_id: str
    mode: ExecutionMode
    provider_environment: str | None
    live_mandate_id: UUID | None
    created_session_digest: bytes
    status: ExecutionRunStatus
    error_code: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class LiveExecutionMandateRecord:
    id: UUID
    user_id: UUID
    account_id: str
    max_order_notional_rub: Decimal
    max_daily_notional_rub: Decimal
    created_session_digest: bytes
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExecutionLegRecord:
    id: UUID
    run_id: UUID
    user_id: UUID
    leg_index: int
    action: str
    instrument_uid: str
    lots_requested: int
    lots_executed: int
    limit_price: Decimal
    limit_price_type: str
    max_spend_rub: Decimal | None
    min_proceeds_rub: Decimal | None
    request_id: UUID
    provider_order_id: str | None
    provider_status: str
    status: ExecutionLegStatus
    executed_amount_rub: Decimal
    executed_commission_rub: Decimal
    submitted_at: datetime | None
    last_checked_at: datetime | None
    terminal_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExecutionEventRecord:
    id: int
    run_id: UUID
    leg_id: UUID | None
    user_id: UUID
    event_type: str
    details: dict[str, Any]
    created_at: datetime


class ExecutionStore:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.proposals = PortfolioStore(database)

    @staticmethod
    def _tenant(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "SELECT set_config('omnicio.user_id', %s, true)",
            (str(user_id),),
        )

    def live_mandate(
        self,
        user_id: UUID,
        *,
        account_id: str | None = None,
        now: datetime | None = None,
    ) -> LiveExecutionMandateRecord | None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            select_sql = """
                SELECT
                    id,
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at,
                    revoked_at
                FROM portfolio_live_execution_mandates
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND expires_at > %s
            """
            if account_id is None:
                cur.execute(
                    select_sql + " ORDER BY created_at DESC LIMIT 1",
                    (user_id, observed_at),
                )
            else:
                cur.execute(
                    select_sql
                    + " AND account_id = %s ORDER BY created_at DESC LIMIT 1",
                    (user_id, observed_at, account_id),
                )
            row = cur.fetchone()
            return (
                _mandate_record(cast(dict[str, Any], row))
                if row is not None
                else None
            )

    def create_live_mandate(
        self,
        user_id: UUID,
        *,
        account_id: str,
        max_order_notional_rub: Decimal,
        max_daily_notional_rub: Decimal,
        session_digest: bytes,
        expires_at: datetime,
        now: datetime | None = None,
    ) -> LiveExecutionMandateRecord:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        if len(session_digest) != 32:
            raise ValueError("live mandate session digest must be SHA-256")
        if not account_id or len(account_id) > 128:
            raise ValueError("live mandate account id is invalid")
        if (
            not max_order_notional_rub.is_finite()
            or max_order_notional_rub <= 0
            or not max_daily_notional_rub.is_finite()
            or max_daily_notional_rub < max_order_notional_rub
        ):
            raise ValueError("live mandate notional caps are invalid")
        kopeck = Decimal("0.01")
        if (
            max_order_notional_rub.quantize(kopeck) != max_order_notional_rub
            or max_daily_notional_rub.quantize(kopeck) != max_daily_notional_rub
        ):
            raise ValueError("live mandate caps require kopeck precision")
        if expires_at.tzinfo is None:
            raise ValueError("live mandate expiry must be timezone-aware")
        expiry = expires_at.astimezone(UTC)
        if expiry <= observed_at or expiry > observed_at + timedelta(hours=24):
            raise ValueError("live mandate expiry must be within the next 24 hours")

        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                _ADVISORY_XACT_LOCK_SQL,
                (f"portfolio-live-mandate:{user_id}",),
            )
            cur.execute(
                """
                UPDATE portfolio_live_execution_mandates
                SET revoked_at = %s
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND expires_at <= %s
                """,
                (observed_at, user_id, observed_at),
            )
            cur.execute(
                """
                SELECT id
                FROM portfolio_live_execution_mandates
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND expires_at > %s
                LIMIT 1
                """,
                (user_id, observed_at),
            )
            if cur.fetchone() is not None:
                raise ExecutionLedgerError("live_mandate_already_active")
            cur.execute(
                """
                INSERT INTO portfolio_live_execution_mandates (
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at,
                    revoked_at
                """,
                (
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    session_digest,
                    observed_at,
                    expiry,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("live mandate insert returned no row")
            return _mandate_record(cast(dict[str, Any], row))

    def revoke_live_mandate(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> LiveExecutionMandateRecord | None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                """
                UPDATE portfolio_live_execution_mandates
                SET revoked_at = %s
                WHERE user_id = %s
                  AND revoked_at IS NULL
                RETURNING
                    id,
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at,
                    revoked_at
                """,
                (observed_at, user_id),
            )
            row = cur.fetchone()
            return (
                _mandate_record(cast(dict[str, Any], row))
                if row is not None
                else None
            )

    def live_daily_notional(
        self,
        user_id: UUID,
        *,
        account_id: str,
        day_start: datetime,
    ) -> Decimal:
        if day_start.tzinfo is None:
            raise ValueError("live notional day boundary must be timezone-aware")
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT COALESCE(SUM(l.executed_amount_rub), 0) AS total
                FROM portfolio_execution_runs AS r
                JOIN portfolio_execution_legs AS l
                  ON l.run_id = r.id
                 AND l.user_id = r.user_id
                WHERE r.user_id = %s
                  AND r.account_id = %s
                  AND r.mode = 'live'
                  AND COALESCE(l.last_checked_at, l.submitted_at, r.created_at) >= %s
                """,
                (user_id, account_id, day_start.astimezone(UTC)),
            )
            row = cur.fetchone()
            if row is None:
                return Decimal("0")
            return Decimal(cast(dict[str, Any], row)["total"])

    def has_active_live_execution(self, user_id: UUID) -> bool:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT 1
                FROM portfolio_execution_runs
                WHERE user_id = %s
                  AND mode = 'live'
                  AND status IN ('created', 'running', 'reconciling')
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone() is not None

    @staticmethod
    def _execution_plan(
        proposal: PortfolioProposalRecord,
        *,
        expected_version: int,
        expected_hash: bytes,
        mode: ExecutionMode,
    ) -> ExecutionPlan:
        if proposal.version != expected_version:
            raise ExecutionLedgerError("proposal_version_mismatch")
        if proposal.proposal_hash != expected_hash:
            raise ExecutionLedgerError("proposal_hash_mismatch")
        try:
            plan = build_execution_plan(proposal)
        except ExecutionStateError as exc:
            raise ExecutionLedgerError(exc.code) from exc
        if mode != "live":
            return plan
        if proposal.scenario_kind != "deploy_cash":
            raise ExecutionLedgerError("live_canary_deploy_cash_only")
        if any(trade.action != "buy" for trade in plan.trades):
            raise ExecutionLedgerError("live_canary_buy_only")
        return plan

    @staticmethod
    def _existing_run(
        cur: Any,
        *,
        user_id: UUID,
        proposal_id: UUID,
        mode: ExecutionMode,
        expected_version: int,
        expected_hash: bytes,
        session_digest: bytes,
    ) -> ExecutionRunRecord | None:
        cur.execute(
            """
            SELECT
                id,
                user_id,
                proposal_id,
                confirmed_action_id,
                proposal_version,
                proposal_hash,
                account_id,
                mode,
                provider_environment,
                live_mandate_id,
                created_session_digest,
                status,
                error_code,
                created_at,
                updated_at,
                finished_at
            FROM portfolio_execution_runs
            WHERE user_id = %s
              AND proposal_id = %s
              AND mode = %s
            """,
            (user_id, proposal_id, mode),
        )
        row = cur.fetchone()
        if row is None:
            return None
        run = _run_record(cast(dict[str, Any], row))
        if (
            run.proposal_version != expected_version
            or run.proposal_hash != expected_hash
        ):
            raise ExecutionLedgerError("execution_run_source_mismatch")
        if mode == "live" and not hmac.compare_digest(
            run.created_session_digest,
            session_digest,
        ):
            raise ExecutionLedgerError("live_execution_session_mismatch")
        return run

    @staticmethod
    def _confirmed_action_id(
        cur: Any,
        *,
        proposal_id: UUID,
        user_id: UUID,
        expected_version: int,
        expected_hash: bytes,
    ) -> int:
        cur.execute(
            """
            SELECT id
            FROM portfolio_proposal_actions
            WHERE proposal_id = %s
              AND user_id = %s
              AND action = 'confirmed'
              AND proposal_version = %s
              AND proposal_hash = %s
            """,
            (
                proposal_id,
                user_id,
                expected_version,
                expected_hash,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise ExecutionLedgerError("proposal_not_confirmed")
        return int(cast(dict[str, Any], row)["id"])

    @staticmethod
    def _active_live_mandate_id(
        cur: Any,
        *,
        user_id: UUID,
        account_id: str,
        session_digest: bytes,
    ) -> UUID:
        cur.execute(
            """
            SELECT id, created_session_digest
            FROM portfolio_live_execution_mandates
            WHERE user_id = %s
              AND account_id = %s
              AND revoked_at IS NULL
              AND expires_at > now()
            FOR SHARE
            """,
            (user_id, account_id),
        )
        row = cur.fetchone()
        if row is None:
            raise ExecutionLedgerError("live_mandate_required")
        mandate = cast(dict[str, Any], row)
        if not hmac.compare_digest(
            bytes(mandate["created_session_digest"]),
            session_digest,
        ):
            raise ExecutionLedgerError("live_mandate_session_mismatch")
        return cast(UUID, mandate["id"])

    def create_run(
        self,
        user_id: UUID,
        *,
        proposal_id: UUID,
        expected_version: int,
        expected_hash: bytes,
        mode: ExecutionMode,
        session_digest: bytes,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        if len(expected_hash) != 32:
            raise ValueError("execution proposal hash must be SHA-256")
        if len(session_digest) != 32:
            raise ValueError("execution session digest must be SHA-256")
        if mode not in _PROVIDER_ENVIRONMENT:
            raise ValueError("execution mode is invalid")

        proposal = self.proposals.proposal(user_id, proposal_id)
        if proposal is None:
            raise ExecutionLedgerError("proposal_not_found")
        plan = self._execution_plan(
            proposal,
            expected_version=expected_version,
            expected_hash=expected_hash,
            mode=mode,
        )

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                _ADVISORY_XACT_LOCK_SQL,
                (f"portfolio-execution:{user_id}:{proposal_id}:{mode}",),
            )
            if mode == "live":
                cur.execute(
                    _ADVISORY_XACT_LOCK_SQL,
                    (f"portfolio-live-execution:{user_id}:{plan.account_id}",),
                )

            existing = self._existing_run(
                cur,
                user_id=user_id,
                proposal_id=proposal_id,
                mode=mode,
                expected_version=expected_version,
                expected_hash=expected_hash,
                session_digest=session_digest,
            )
            if existing is not None:
                return existing, self._legs(cur, user_id, existing.id)

            _require_current_execution_source(
                cur,
                user_id=user_id,
                proposal_id=proposal.id,
                snapshot_id=proposal.source_snapshot_id,
                account_id=proposal.account_id,
                profile_version=proposal.profile_version,
                policy_version=proposal.policy_version,
            )
            confirmed_action_id = self._confirmed_action_id(
                cur,
                proposal_id=proposal_id,
                user_id=user_id,
                expected_version=expected_version,
                expected_hash=expected_hash,
            )
            live_mandate_id = None
            if mode == "live":
                live_mandate_id = self._active_live_mandate_id(
                    cur,
                    user_id=user_id,
                    account_id=plan.account_id,
                    session_digest=session_digest,
                )

            cur.execute(
                """
                INSERT INTO portfolio_execution_runs (
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                """,
                (
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    expected_version,
                    expected_hash,
                    plan.account_id,
                    mode,
                    _PROVIDER_ENVIRONMENT[mode],
                    live_mandate_id,
                    session_digest,
                ),
            )
            run_row = cur.fetchone()
            if run_row is None:
                raise RuntimeError("execution run insert returned no row")
            run = _run_record(cast(dict[str, Any], run_row))

            for trade in plan.trades:
                cur.execute(
                    """
                    INSERT INTO portfolio_execution_legs (
                        run_id,
                        user_id,
                        leg_index,
                        action,
                        instrument_uid,
                        lots_requested,
                        limit_price,
                        limit_price_type,
                        max_spend_rub,
                        min_proceeds_rub,
                        request_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run.id,
                        user_id,
                        trade.leg_index,
                        trade.action,
                        trade.instrument_uid,
                        trade.lots,
                        trade.limit_price,
                        trade.limit_price_type,
                        trade.max_spend_rub,
                        trade.min_proceeds_rub,
                        uuid4(),
                    ),
                )

            self._append_event(
                cur,
                user_id=user_id,
                run_id=run.id,
                leg_id=None,
                event_type="run_created",
                details={
                    "mode": mode,
                    "proposal_version": expected_version,
                    "leg_count": len(plan.trades),
                },
            )
            return run, self._legs(cur, user_id, run.id)

    def execution(
        self,
        user_id: UUID,
        run_id: UUID,
    ) -> tuple[
        ExecutionRunRecord,
        tuple[ExecutionLegRecord, ...],
        tuple[ExecutionEventRecord, ...],
    ] | None:
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
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE id = %s
                  AND user_id = %s
                """,
                (run_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            run = _run_record(cast(dict[str, Any], row))
            legs = self._legs(cur, user_id, run.id)
            cur.execute(
                """
                SELECT
                    id,
                    run_id,
                    leg_id,
                    user_id,
                    event_type,
                    details,
                    created_at
                FROM portfolio_execution_events
                WHERE run_id = %s
                  AND user_id = %s
                ORDER BY id
                """,
                (run_id, user_id),
            )
            events = tuple(
                _event_record(cast(dict[str, Any], item))
                for item in cur.fetchall()
            )
            return run, legs, events

    def executions(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
    ) -> tuple[ExecutionRunRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("execution limit must be between 1 and 100")
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
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return tuple(
                _run_record(cast(dict[str, Any], row))
                for row in cur.fetchall()
            )

    def transition_leg(
        self,
        user_id: UUID,
        *,
        run_id: UUID,
        leg_id: UUID,
        expected_statuses: tuple[ExecutionLegStatus, ...],
        new_status: ExecutionLegStatus,
        event_type: str,
        details: dict[str, object],
        provider_order_id: str | None = None,
        provider_status: str | None = None,
        lots_executed: int | None = None,
        executed_amount_rub: Decimal | None = None,
        executed_commission_rub: Decimal | None = None,
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, ExecutionLegRecord]:
        if not expected_statuses:
            raise ValueError("execution transition requires expected status")
        if not event_type or len(event_type) > 128:
            raise ValueError("execution event type is invalid")
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)

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
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (run_id, user_id),
            )
            run_row = cur.fetchone()
            if run_row is None:
                raise ExecutionLedgerError("execution_not_found")
            run = _run_record(cast(dict[str, Any], run_row))
            if run.status in _TERMINAL_RUNS:
                raise ExecutionLedgerError("execution_already_terminal")

            if run.mode == "live" and new_status == "submitting":
                if run.live_mandate_id is None:
                    raise ExecutionLedgerError("live_mandate_inactive")
                cur.execute(
                    """
                    SELECT 1
                    FROM portfolio_live_execution_mandates
                    WHERE id = %s
                      AND user_id = %s
                      AND account_id = %s
                      AND created_session_digest = %s
                      AND revoked_at IS NULL
                      AND expires_at > %s
                    FOR SHARE
                    """,
                    (
                        run.live_mandate_id,
                        user_id,
                        run.account_id,
                        run.created_session_digest,
                        observed_at,
                    ),
                )
                if cur.fetchone() is None:
                    raise ExecutionLedgerError("live_mandate_inactive")

            cur.execute(
                """
                SELECT
                    id,
                    run_id,
                    user_id,
                    leg_index,
                    action,
                    instrument_uid,
                    lots_requested,
                    lots_executed,
                    limit_price,
                    limit_price_type,
                    max_spend_rub,
                    min_proceeds_rub,
                    request_id,
                    provider_order_id,
                    provider_status,
                    status,
                    executed_amount_rub,
                    executed_commission_rub,
                    submitted_at,
                    last_checked_at,
                    terminal_at
                FROM portfolio_execution_legs
                WHERE id = %s
                  AND run_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (leg_id, run_id, user_id),
            )
            leg_row = cur.fetchone()
            if leg_row is None:
                raise ExecutionLedgerError("execution_leg_not_found")
            leg = _leg_record(cast(dict[str, Any], leg_row))
            if leg.status not in expected_statuses:
                raise ExecutionLedgerError("execution_leg_state_changed")

            next_lots = leg.lots_executed if lots_executed is None else lots_executed
            if next_lots < 0 or next_lots > leg.lots_requested:
                raise ValueError("executed lots are outside requested bounds")
            next_amount = (
                leg.executed_amount_rub
                if executed_amount_rub is None
                else executed_amount_rub
            )
            next_commission = (
                leg.executed_commission_rub
                if executed_commission_rub is None
                else executed_commission_rub
            )
            if next_amount < 0 or next_commission < 0:
                raise ValueError("execution money values must be non-negative")

            terminal_at = (
                observed_at
                if new_status in _TERMINAL_LEGS
                else None
            )
            cur.execute(
                """
                UPDATE portfolio_execution_legs
                SET
                    status = %s,
                    provider_order_id = COALESCE(%s, provider_order_id),
                    provider_status = COALESCE(%s, provider_status),
                    lots_executed = %s,
                    executed_amount_rub = %s,
                    executed_commission_rub = %s,
                    submitted_at = CASE
                        WHEN submitted_at IS NULL
                         AND %s IN (
                            'submitted',
                            'partially_filled',
                            'filled',
                            'reconciling'
                         )
                        THEN %s
                        ELSE submitted_at
                    END,
                    last_checked_at = CASE
                        WHEN %s::text IS NOT NULL THEN %s
                        ELSE last_checked_at
                    END,
                    terminal_at = COALESCE(%s, terminal_at)
                WHERE id = %s
                  AND run_id = %s
                  AND user_id = %s
                RETURNING
                    id,
                    run_id,
                    user_id,
                    leg_index,
                    action,
                    instrument_uid,
                    lots_requested,
                    lots_executed,
                    limit_price,
                    limit_price_type,
                    max_spend_rub,
                    min_proceeds_rub,
                    request_id,
                    provider_order_id,
                    provider_status,
                    status,
                    executed_amount_rub,
                    executed_commission_rub,
                    submitted_at,
                    last_checked_at,
                    terminal_at
                """,
                (
                    new_status,
                    provider_order_id,
                    provider_status,
                    next_lots,
                    next_amount,
                    next_commission,
                    new_status,
                    observed_at,
                    provider_status,
                    observed_at,
                    terminal_at,
                    leg_id,
                    run_id,
                    user_id,
                ),
            )
            updated_row = cur.fetchone()
            if updated_row is None:
                raise RuntimeError("execution leg update returned no row")
            updated_leg = _leg_record(cast(dict[str, Any], updated_row))

            self._append_event(
                cur,
                user_id=user_id,
                run_id=run_id,
                leg_id=leg_id,
                event_type=event_type,
                details=details,
            )

            legs = self._legs(cur, user_id, run_id)
            derived = run_status_for_legs(
                tuple(item.status for item in legs)
            )
            finished_at = (
                observed_at if derived in _TERMINAL_RUNS else None
            )
            cur.execute(
                """
                UPDATE portfolio_execution_runs
                SET
                    status = %s,
                    updated_at = %s,
                    finished_at = %s,
                    error_code = CASE
                        WHEN %s = 'failed' AND error_code = ''
                        THEN %s
                        ELSE error_code
                    END
                WHERE id = %s
                  AND user_id = %s
                RETURNING
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                """,
                (
                    derived,
                    observed_at,
                    finished_at,
                    derived,
                    event_type,
                    run_id,
                    user_id,
                ),
            )
            updated_run_row = cur.fetchone()
            if updated_run_row is None:
                raise RuntimeError("execution run update returned no row")
            return (
                _run_record(cast(dict[str, Any], updated_run_row)),
                updated_leg,
            )

    def mark_run_reconciling(
        self,
        user_id: UUID,
        *,
        run_id: UUID,
        leg_id: UUID,
        error_code: str,
        details: dict[str, object],
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, ExecutionLegRecord]:
        run, leg = self.transition_leg(
            user_id,
            run_id=run_id,
            leg_id=leg_id,
            expected_statuses=(
                "submitting",
                "submitted",
                "partially_filled",
                "cancel_requested",
                "reconciling",
            ),
            new_status="reconciling",
            event_type=error_code,
            details=details,
            now=now,
        )
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                UPDATE portfolio_execution_runs
                SET error_code = %s, updated_at = %s
                WHERE id = %s
                  AND user_id = %s
                  AND status = 'reconciling'
                RETURNING
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    created_session_digest,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                """,
                (
                    error_code[:128],
                    (now or datetime.now(UTC)).astimezone(UTC),
                    run_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            if row is not None:
                run = _run_record(cast(dict[str, Any], row))
        return run, leg

    @staticmethod
    def _append_event(
        cur: Any,
        *,
        user_id: UUID,
        run_id: UUID,
        leg_id: UUID | None,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        cur.execute(
            """
            INSERT INTO portfolio_execution_events (
                run_id,
                leg_id,
                user_id,
                event_type,
                details
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                run_id,
                leg_id,
                user_id,
                event_type,
                json.dumps(details, separators=(",", ":"), sort_keys=True),
            ),
        )

    @staticmethod
    def _legs(
        cur: Any,
        user_id: UUID,
        run_id: UUID,
    ) -> tuple[ExecutionLegRecord, ...]:
        cur.execute(
            """
            SELECT
                id,
                run_id,
                user_id,
                leg_index,
                action,
                instrument_uid,
                lots_requested,
                lots_executed,
                limit_price,
                limit_price_type,
                max_spend_rub,
                min_proceeds_rub,
                request_id,
                provider_order_id,
                provider_status,
                status,
                executed_amount_rub,
                executed_commission_rub,
                submitted_at,
                last_checked_at,
                terminal_at
            FROM portfolio_execution_legs
            WHERE run_id = %s
              AND user_id = %s
            ORDER BY leg_index
            """,
            (run_id, user_id),
        )
        return tuple(
            _leg_record(cast(dict[str, Any], row))
            for row in cur.fetchall()
        )


def _require_current_execution_source(
    cur: Any,
    *,
    user_id: UUID,
    proposal_id: UUID,
    snapshot_id: UUID,
    account_id: str,
    profile_version: int,
    policy_version: int,
) -> None:
    cur.execute(
        """
        SELECT
            p.expires_at > now() AS unexpired,
            (p.source_snapshot_id, p.account_id) = (
                SELECT s.id, s.account_id
                FROM portfolio_snapshots AS s
                WHERE s.user_id = p.user_id
                ORDER BY s.captured_at DESC, s.created_at DESC
                LIMIT 1
            ) AS snapshot_current,
            p.profile_version = (
                SELECT ip.version
                FROM investment_profile_versions AS ip
                WHERE ip.user_id = p.user_id
                ORDER BY ip.version DESC
                LIMIT 1
            ) AS profile_current,
            p.policy_version = (
                SELECT bp.version
                FROM balancing_policy_versions AS bp
                WHERE bp.user_id = p.user_id
                ORDER BY bp.version DESC
                LIMIT 1
            ) AS policy_current
        FROM portfolio_proposals AS p
        WHERE p.id = %s
          AND p.user_id = %s
          AND p.source_snapshot_id = %s
          AND p.account_id = %s
          AND p.profile_version = %s
          AND p.policy_version = %s
        FOR SHARE
        """,
        (
            proposal_id,
            user_id,
            snapshot_id,
            account_id,
            profile_version,
            policy_version,
        ),
    )
    row = cur.fetchone()
    if row is None:
        raise ExecutionLedgerError("execution_proposal_source_changed")
    checks = cast(dict[str, Any], row)
    if not bool(checks["unexpired"]):
        raise ExecutionLedgerError("proposal_expired")
    if not bool(checks["snapshot_current"]):
        raise ExecutionLedgerError("proposal_snapshot_stale")
    if not bool(checks["profile_current"]):
        raise ExecutionLedgerError("proposal_profile_stale")
    if not bool(checks["policy_current"]):
        raise ExecutionLedgerError("proposal_policy_stale")


def _run_record(row: dict[str, Any]) -> ExecutionRunRecord:
    return ExecutionRunRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        proposal_id=cast(UUID, row["proposal_id"]),
        confirmed_action_id=int(row["confirmed_action_id"]),
        proposal_version=int(row["proposal_version"]),
        proposal_hash=bytes(row["proposal_hash"]),
        account_id=str(row["account_id"]),
        mode=cast(ExecutionMode, row["mode"]),
        provider_environment=cast(str | None, row["provider_environment"]),
        live_mandate_id=cast(UUID | None, row["live_mandate_id"]),
        created_session_digest=bytes(row["created_session_digest"]),
        status=cast(ExecutionRunStatus, row["status"]),
        error_code=str(row["error_code"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
    )


def _mandate_record(row: dict[str, Any]) -> LiveExecutionMandateRecord:
    return LiveExecutionMandateRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        account_id=str(row["account_id"]),
        max_order_notional_rub=Decimal(row["max_order_notional_rub"]),
        max_daily_notional_rub=Decimal(row["max_daily_notional_rub"]),
        created_session_digest=bytes(row["created_session_digest"]),
        created_at=cast(datetime, row["created_at"]),
        expires_at=cast(datetime, row["expires_at"]),
        revoked_at=cast(datetime | None, row["revoked_at"]),
    )


def _leg_record(row: dict[str, Any]) -> ExecutionLegRecord:
    return ExecutionLegRecord(
        id=cast(UUID, row["id"]),
        run_id=cast(UUID, row["run_id"]),
        user_id=cast(UUID, row["user_id"]),
        leg_index=int(row["leg_index"]),
        action=str(row["action"]),
        instrument_uid=str(row["instrument_uid"]),
        lots_requested=int(row["lots_requested"]),
        lots_executed=int(row["lots_executed"]),
        limit_price=Decimal(row["limit_price"]),
        limit_price_type=str(row["limit_price_type"]),
        max_spend_rub=(
            Decimal(row["max_spend_rub"])
            if row["max_spend_rub"] is not None
            else None
        ),
        min_proceeds_rub=(
            Decimal(row["min_proceeds_rub"])
            if row["min_proceeds_rub"] is not None
            else None
        ),
        request_id=cast(UUID, row["request_id"]),
        provider_order_id=cast(str | None, row["provider_order_id"]),
        provider_status=str(row["provider_status"]),
        status=cast(ExecutionLegStatus, row["status"]),
        executed_amount_rub=Decimal(row["executed_amount_rub"]),
        executed_commission_rub=Decimal(row["executed_commission_rub"]),
        submitted_at=cast(datetime | None, row["submitted_at"]),
        last_checked_at=cast(datetime | None, row["last_checked_at"]),
        terminal_at=cast(datetime | None, row["terminal_at"]),
    )


def _event_record(row: dict[str, Any]) -> ExecutionEventRecord:
    return ExecutionEventRecord(
        id=int(row["id"]),
        run_id=cast(UUID, row["run_id"]),
        leg_id=cast(UUID | None, row["leg_id"]),
        user_id=cast(UUID, row["user_id"]),
        event_type=str(row["event_type"]),
        details=dict(cast(dict[str, Any], row["details"])),
        created_at=cast(datetime, row["created_at"]),
    )
