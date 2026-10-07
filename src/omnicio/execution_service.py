"""Recover existing execution records without creating or submitting orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from .broker import BrokerConnectionError, BrokerService
from .execution import (
    ExecutionLegStatus,
    ExecutionStateError,
    provider_leg_status,
)
from .execution_store import (
    ExecutionLegRecord,
    ExecutionRunRecord,
    ExecutionStore,
)
from .tbank import (
    TBankMoney,
    TBankNotFound,
    TBankOrderState,
    TBankUnavailable,
)


class ExecutionServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PortfolioExecutionService:
    def __init__(
        self,
        *,
        store: ExecutionStore,
        broker: BrokerService,
    ) -> None:
        self.store = store
        self.broker = broker

    def _execution_snapshot(
        self,
        user_id: UUID,
        run_id: UUID,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        snapshot = self.store.execution(user_id, run_id)
        if snapshot is None:
            raise ExecutionServiceError("execution_not_found")
        run, legs, _events = snapshot
        return run, legs

    def _require_execution_connection(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        if run.mode == "sandbox":
            self._require_sandbox_account(user_id, run)
            return
        if run.mode == "live":
            self._require_live_connection(user_id, run)
            return
        raise ExecutionServiceError("execution_mode_invalid")

    def reconcile(
        self, user_id: UUID, run_id: UUID, *, now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        """Read at most one previously submitted request; never submit or cancel.

        A durable submitting/reconciling status may represent an ambiguous old
        request whose provider response was lost. It is safe to query that exact
        request ID, but a pending leg must never cause a provider call here.
        """
        run, legs = self._execution_snapshot(user_id, run_id)
        if run.mode == "shadow" or run.status in {"succeeded", "cancelled", "failed"}:
            return run, legs
        current = next((leg for leg in legs if leg.status in {
            "submitting", "submitted", "partially_filled", "cancel_requested", "reconciling",
        }), None)
        if current is None:
            return run, legs
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        self._require_execution_connection(user_id, run)
        self._reconcile_leg(user_id, run, current, observed_at)
        self._require_execution_connection(user_id, run)
        return self._execution_snapshot(user_id, run_id)


    def cancel(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        snapshot = self.store.execution(user_id, run_id)
        if snapshot is None:
            raise ExecutionServiceError("execution_not_found")
        run, legs, _events = snapshot
        if run.mode == "shadow":
            raise ExecutionServiceError("shadow_execution_has_no_broker_order")
        if run.mode == "sandbox":
            self._require_sandbox_account(user_id, run)
        elif run.mode == "live":
            self._require_live_connection(user_id, run)
        else:
            raise ExecutionServiceError("execution_mode_invalid")
        current = _current_leg(legs)
        if current is None or current.status in {
            "cancelled",
            "rejected",
            "failed",
        }:
            raise ExecutionServiceError("execution_has_no_cancellable_leg")
        if current.status == "pending":
            self.store.transition_leg(
                user_id,
                run_id=run.id,
                leg_id=current.id,
                expected_statuses=("pending",),
                new_status="cancelled",
                event_type="cancelled_before_submission",
                details={"reason": "user_cancel"},
                now=observed_at,
            )
        else:
            self._request_cancel(user_id, run, current, observed_at)
        refreshed = self.store.execution(user_id, run_id)
        if refreshed is None:
            raise ExecutionServiceError("execution_not_found")
        return refreshed[0], refreshed[1]


    def _require_sandbox_account(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        status = self.broker.status(user_id)
        if (
            not status.connected
            or status.environment != "sandbox"
            or status.account_id != run.account_id
            or run.provider_environment != "sandbox"
        ):
            raise ExecutionServiceError("sandbox_account_mismatch")

    def _require_live_connection(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        status = self.broker.status(user_id)
        if (
            not status.connected
            or status.environment != "prod"
            or status.account_id != run.account_id
            or run.provider_environment != "prod"
            or run.live_mandate_id is None
        ):
            raise ExecutionServiceError("live_account_mismatch")


    def _reconcile_leg(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> ExecutionLegStatus:
        prefix = run.mode
        try:
            if run.mode == "live":
                state = self.broker.live_order_state(
                    user_id,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
            elif run.mode == "sandbox":
                state = self.broker.sandbox_order_state(
                    user_id,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
            else:
                raise ExecutionServiceError("provider_execution_mode_invalid")
        except TBankNotFound:
            code = f"{prefix}_order_not_found_yet"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return "reconciling"
        except (TBankUnavailable, BrokerConnectionError):
            code = f"{prefix}_reconcile_unavailable"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return "reconciling"

        self._require_execution_connection(user_id, run)
        return self._record_provider_state(
            user_id,
            run,
            leg,
            state,
            observed_at,
            expected_statuses=(
                "submitting",
                "submitted",
                "partially_filled",
                "cancel_requested",
                "reconciling",
            ),
            event_type=f"{prefix}_order_reconciled",
        )

    def _request_cancel(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> None:
        if leg.status not in {
            "submitting",
            "submitted",
            "partially_filled",
            "reconciling",
            "cancel_requested",
        }:
            raise ExecutionServiceError("execution_leg_not_cancellable")
        prefix = run.mode
        if leg.status != "cancel_requested":
            self.store.transition_leg(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                expected_statuses=(
                    "submitting",
                    "submitted",
                    "partially_filled",
                    "reconciling",
                ),
                new_status="cancel_requested",
                event_type=f"{prefix}_cancel_requested",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
        try:
            if run.mode == "live":
                result = self.broker.cancel_live_order(
                    user_id,
                    request_id=str(leg.request_id),
                )
            elif run.mode == "sandbox":
                result = self.broker.cancel_sandbox_order(
                    user_id,
                    request_id=str(leg.request_id),
                )
            else:
                raise ExecutionServiceError("provider_execution_mode_invalid")
        except TBankNotFound:
            code = f"{prefix}_cancel_order_not_found"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return
        except (TBankUnavailable, BrokerConnectionError):
            code = f"{prefix}_cancel_ambiguous"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return

        self.store.mark_run_reconciling(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            error_code=f"{prefix}_cancel_acknowledged",
            details={
                "request_id": str(leg.request_id),
                "cancelled_at": result.cancelled_at.isoformat(),
            },
            now=observed_at,
        )

    def _record_provider_state(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        state: TBankOrderState,
        observed_at: datetime,
        *,
        expected_statuses: tuple[ExecutionLegStatus, ...],
        event_type: str,
    ) -> ExecutionLegStatus:
        prefix = run.mode
        try:
            _validate_state_matches_leg(leg, state, prefix=prefix)
        except ExecutionServiceError as exc:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=exc.code,
                details={
                    "request_id": str(leg.request_id),
                    "provider_order_id": state.order_id,
                },
                now=observed_at,
            )
            return "reconciling"
        try:
            local_status = provider_leg_status(
                state.execution_report_status
            )
        except ExecutionStateError as exc:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=exc.code,
                details={
                    "provider_status": state.execution_report_status,
                    "request_id": str(leg.request_id),
                },
                now=observed_at,
            )
            return "reconciling"

        amount = _executed_amount(state)
        commission = _executed_commission(state)
        if (
            leg.action == "buy"
            and leg.max_spend_rub is not None
            and amount > leg.max_spend_rub
        ):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=f"{prefix}_provider_overspend_detected",
                details={
                    "request_id": str(leg.request_id),
                    "amount_rub": str(amount),
                    "commission_rub": str(commission),
                },
                now=observed_at,
            )
            return "reconciling"
        if (
            leg.action == "sell"
            and local_status == "filled"
            and leg.min_proceeds_rub is not None
            and amount < leg.min_proceeds_rub
        ):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=f"{prefix}_provider_min_proceeds_breach",
                details={
                    "request_id": str(leg.request_id),
                    "amount_rub": str(amount),
                    "min_proceeds_rub": str(leg.min_proceeds_rub),
                },
                now=observed_at,
            )
            return "reconciling"

        self.store.transition_leg(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            expected_statuses=expected_statuses,
            new_status=local_status,
            event_type=event_type,
            details={
                "request_id": str(leg.request_id),
                "provider_order_id": state.order_id,
                "provider_status": state.execution_report_status,
                "lots_requested": state.lots_requested,
                "lots_executed": state.lots_executed,
                "amount_rub": str(amount),
                "commission_rub": str(commission),
            },
            provider_order_id=state.order_id,
            provider_status=state.execution_report_status,
            lots_executed=state.lots_executed,
            executed_amount_rub=amount,
            executed_commission_rub=commission,
            now=observed_at,
        )
        return local_status


def _current_leg(
    legs: tuple[ExecutionLegRecord, ...],
) -> ExecutionLegRecord | None:
    for leg in legs:
        if leg.status in {"filled", "shadow_filled"}:
            continue
        return leg
    return None


def _validate_state_matches_leg(
    leg: ExecutionLegRecord,
    state: TBankOrderState,
    *,
    prefix: str,
) -> None:
    if state.order_request_id != str(leg.request_id):
        raise ExecutionServiceError(f"{prefix}_request_id_mismatch")
    if state.instrument_uid != leg.instrument_uid:
        raise ExecutionServiceError(f"{prefix}_instrument_mismatch")
    if state.lots_requested != leg.lots_requested:
        raise ExecutionServiceError(f"{prefix}_lot_count_mismatch")
    expected_direction = {
        "buy": "ORDER_DIRECTION_BUY",
        "sell": "ORDER_DIRECTION_SELL",
    }[leg.action]
    if state.direction and state.direction != expected_direction:
        raise ExecutionServiceError(f"{prefix}_direction_mismatch")
    if state.order_type and state.order_type != "ORDER_TYPE_LIMIT":
        raise ExecutionServiceError(f"{prefix}_order_type_mismatch")


def _executed_amount(state: TBankOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.total_order_amount is None:
        raise ExecutionServiceError("provider_executed_amount_missing")
    return _rub(state.total_order_amount)


def _executed_commission(state: TBankOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.executed_commission is None:
        raise ExecutionServiceError("provider_executed_commission_missing")
    return _rub(state.executed_commission)


def _rub(value: TBankMoney) -> Decimal:
    if value.currency.upper() != "RUB":
        raise ExecutionServiceError("provider_money_not_rub")
    amount = Decimal(value.value)
    if not amount.is_finite() or amount < 0:
        raise ExecutionServiceError("provider_money_invalid")
    return amount
