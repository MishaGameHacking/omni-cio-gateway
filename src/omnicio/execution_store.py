"""Read and recover existing execution and mandate ledgers in PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from .db import Database
from .execution import (
    ExecutionLegStatus,
    ExecutionMode,
    ExecutionRunStatus,
    run_status_for_legs,
)

_TERMINAL_RUNS = {"succeeded", "cancelled", "failed"}
_TERMINAL_LEGS = {"filled", "cancelled", "rejected", "failed", "shadow_filled"}


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


def _validate_leg_transition_request(
    expected_statuses: tuple[ExecutionLegStatus, ...],
    event_type: str,
) -> None:
    if not expected_statuses:
        raise ValueError("execution transition requires expected status")
    if not event_type or len(event_type) > 128:
        raise ValueError("execution event type is invalid")


def _require_live_transition_mandate(
    cur: Any,
    *,
    user_id: UUID,
    run: ExecutionRunRecord,
    new_status: ExecutionLegStatus,
    observed_at: datetime,
) -> None:
    if run.mode != "live" or new_status != "submitting":
        return
    if run.live_mandate_id is None:
        raise ExecutionLedgerError("live_mandate_inactive")
    cur.execute(
        """
        SELECT 1
        FROM portfolio_live_execution_mandates
        WHERE id = %s
          AND user_id = %s
          AND account_id = %s
          AND revoked_at IS NULL
          AND expires_at > %s
        FOR SHARE
        """,
        (
            run.live_mandate_id,
            user_id,
            run.account_id,
            observed_at,
        ),
    )
    if cur.fetchone() is None:
        raise ExecutionLedgerError("live_mandate_inactive")


def _transition_values(
    leg: ExecutionLegRecord,
    *,
    lots_executed: int | None,
    executed_amount_rub: Decimal | None,
    executed_commission_rub: Decimal | None,
) -> tuple[int, Decimal, Decimal]:
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
    return next_lots, next_amount, next_commission


class ExecutionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

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
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE user_id = %s
                ORDER BY (status IN ('created', 'running', 'reconciling')) DESC,
                         created_at DESC, id DESC
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
        _validate_leg_transition_request(expected_statuses, event_type)
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

            _require_live_transition_mandate(
                cur,
                user_id=user_id,
                run=run,
                new_status=new_status,
                observed_at=observed_at,
            )

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

            next_lots, next_amount, next_commission = _transition_values(
                leg,
                lots_executed=lots_executed,
                executed_amount_rub=executed_amount_rub,
                executed_commission_rub=executed_commission_rub,
            )

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
