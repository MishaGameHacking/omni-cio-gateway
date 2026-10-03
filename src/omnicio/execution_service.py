"""R6 shadow/sandbox execution orchestration.

Only T-Invest Sandbox mutations are permitted here.  Production order submission is
not exposed by this service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from .broker import (
    BrokerConnectionError,
    BrokerSandboxRequired,
    BrokerService,
)
from .execution import (
    ExecutionLegStatus,
    ExecutionMode,
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
    TBankSandboxOrderState,
    TBankUnavailable,
)

SANDBOX_ORDER_TIMEOUT = timedelta(minutes=2)


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

    def start(
        self,
        user_id: UUID,
        *,
        proposal_id: UUID,
        proposal_version: int,
        proposal_hash: bytes,
        mode: ExecutionMode,
        session_digest: bytes,
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        run, legs = self.store.create_run(
            user_id,
            proposal_id=proposal_id,
            expected_version=proposal_version,
            expected_hash=proposal_hash,
            mode=mode,
            session_digest=session_digest,
        )
        if mode == "shadow" and run.status not in {
            "succeeded",
            "cancelled",
            "failed",
        }:
            self._complete_shadow(user_id, run.id, now=now)
            snapshot = self.store.execution(user_id, run.id)
            if snapshot is None:
                raise ExecutionServiceError("execution_not_found")
            run, legs, _events = snapshot
        return run, legs

    def advance(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[
        ExecutionRunRecord,
        tuple[ExecutionLegRecord, ...],
    ]:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        snapshot = self.store.execution(user_id, run_id)
        if snapshot is None:
            raise ExecutionServiceError("execution_not_found")
        run, legs, _events = snapshot
        if run.mode == "shadow":
            if run.status not in {"succeeded", "cancelled", "failed"}:
                self._complete_shadow(user_id, run_id, now=observed_at)
                refreshed = self.store.execution(user_id, run_id)
                if refreshed is None:
                    raise ExecutionServiceError("execution_not_found")
                run, legs, _events = refreshed
            return run, legs

        self._require_sandbox_account(user_id, run)
        if run.status in {"succeeded", "cancelled", "failed"}:
            return run, legs

        for _ in range(len(legs) + 1):
            snapshot = self.store.execution(user_id, run_id)
            if snapshot is None:
                raise ExecutionServiceError("execution_not_found")
            run, legs, _events = snapshot
            current = _current_leg(legs)
            if current is None or run.status in {
                "succeeded",
                "cancelled",
                "failed",
            }:
                return run, legs

            if current.status == "pending":
                result = self._submit_pending(
                    user_id,
                    run,
                    current,
                    observed_at,
                )
                if result in {"submitted", "partially_filled", "reconciling"}:
                    refreshed = self.store.execution(user_id, run_id)
                    if refreshed is None:
                        raise ExecutionServiceError("execution_not_found")
                    return refreshed[0], refreshed[1]
                continue

            if current.status in {
                "submitting",
                "submitted",
                "partially_filled",
                "cancel_requested",
                "reconciling",
            }:
                if _timed_out(current, observed_at):
                    self._request_cancel(
                        user_id,
                        run,
                        current,
                        observed_at,
                    )
                else:
                    self._reconcile_leg(
                        user_id,
                        run,
                        current,
                        observed_at,
                    )
                refreshed = self.store.execution(user_id, run_id)
                if refreshed is None:
                    raise ExecutionServiceError("execution_not_found")
                next_run, next_legs, _events = refreshed
                next_current = _current_leg(next_legs)
                if (
                    next_current is None
                    or next_current.id != current.id
                    or next_current.status in {"filled", "shadow_filled"}
                ):
                    continue
                return next_run, next_legs

            return run, legs

        raise ExecutionServiceError("execution_advance_limit_reached")

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
        if run.mode != "sandbox":
            raise ExecutionServiceError("shadow_execution_has_no_broker_order")
        self._require_sandbox_account(user_id, run)
        current = _current_leg(legs)
        if current is None or current.status in {
            "filled",
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

    def _complete_shadow(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        now: datetime | None,
    ) -> None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        while True:
            snapshot = self.store.execution(user_id, run_id)
            if snapshot is None:
                raise ExecutionServiceError("execution_not_found")
            run, legs, _events = snapshot
            if run.mode != "shadow":
                raise ExecutionServiceError("shadow_mode_required")
            current = _current_leg(legs)
            if current is None:
                return
            if current.status != "pending":
                if current.status == "shadow_filled":
                    continue
                raise ExecutionServiceError("shadow_leg_state_invalid")
            self.store.transition_leg(
                user_id,
                run_id=run_id,
                leg_id=current.id,
                expected_statuses=("pending",),
                new_status="shadow_filled",
                event_type="shadow_leg_rehearsed",
                details={
                    "action": current.action,
                    "instrument_uid": current.instrument_uid,
                    "lots": current.lots_requested,
                    "limit_price": str(current.limit_price),
                    "limit_price_type": current.limit_price_type,
                    "provider_mutation": False,
                },
                lots_executed=current.lots_requested,
                now=observed_at,
            )

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

    def _submit_pending(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> ExecutionLegStatus:
        self._sandbox_preflight(user_id, leg)
        self.store.transition_leg(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            expected_statuses=("pending",),
            new_status="submitting",
            event_type="sandbox_preflight_passed",
            details={
                "request_id": str(leg.request_id),
                "margin": False,
                "order_type": "limit",
            },
            now=observed_at,
        )
        try:
            state = self.broker.post_sandbox_order(
                user_id,
                leg.instrument_uid,
                quantity_lots=leg.lots_requested,
                price=str(leg.limit_price),
                direction=leg.action,
                request_id=str(leg.request_id),
                price_type=leg.limit_price_type,
            )
        except (BrokerSandboxRequired, BrokerConnectionError) as exc:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_connection_changed",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            raise ExecutionServiceError("sandbox_connection_changed") from exc
        except TBankUnavailable:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_submit_ambiguous",
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return "reconciling"

        status = self._record_provider_state(
            user_id,
            run,
            leg,
            state,
            observed_at,
            expected_statuses=("submitting",),
            event_type="sandbox_order_submitted",
        )
        return status

    def _sandbox_preflight(
        self,
        user_id: UUID,
        leg: ExecutionLegRecord,
    ) -> None:
        max_lots = self.broker.sandbox_max_lots(
            user_id,
            leg.instrument_uid,
            price=str(leg.limit_price),
        )
        if max_lots.currency not in {"", "RUB"}:
            raise ExecutionServiceError("sandbox_max_lots_currency_invalid")
        if leg.action == "buy":
            if max_lots.buy_max_lots < leg.lots_requested:
                raise ExecutionServiceError("sandbox_buy_lots_exceed_available")
        elif max_lots.sell_max_lots < leg.lots_requested:
            raise ExecutionServiceError("sandbox_sell_lots_exceed_available")

        estimate = self.broker.sandbox_order_price(
            user_id,
            leg.instrument_uid,
            price=str(leg.limit_price),
            direction=leg.action,
            quantity_lots=leg.lots_requested,
        )
        total = _rub(estimate.total_order_amount)
        if leg.action == "buy":
            if leg.max_spend_rub is None or total > leg.max_spend_rub:
                raise ExecutionServiceError("sandbox_buy_would_overspend")
        elif (
            leg.min_proceeds_rub is None
            or total < leg.min_proceeds_rub
        ):
            raise ExecutionServiceError("sandbox_sell_below_min_proceeds")

    def _reconcile_leg(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> ExecutionLegStatus:
        try:
            state = self.broker.sandbox_order_state(
                user_id,
                request_id=str(leg.request_id),
                price_type=leg.limit_price_type,
            )
        except TBankNotFound:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_order_not_found_yet",
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return "reconciling"
        except (TBankUnavailable, BrokerConnectionError):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_reconcile_unavailable",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return "reconciling"

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
            event_type="sandbox_order_reconciled",
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
                event_type="sandbox_cancel_requested",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
        try:
            result = self.broker.cancel_sandbox_order(
                user_id,
                request_id=str(leg.request_id),
            )
        except TBankNotFound:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_cancel_order_not_found",
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return
        except (TBankUnavailable, BrokerConnectionError):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code="sandbox_cancel_ambiguous",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return

        self.store.mark_run_reconciling(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            error_code="sandbox_cancel_acknowledged",
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
        state: TBankSandboxOrderState,
        observed_at: datetime,
        *,
        expected_statuses: tuple[ExecutionLegStatus, ...],
        event_type: str,
    ) -> ExecutionLegStatus:
        try:
            _validate_state_matches_leg(leg, state)
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
                error_code="sandbox_provider_overspend_detected",
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
                error_code="sandbox_provider_min_proceeds_breach",
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


def _timed_out(leg: ExecutionLegRecord, now: datetime) -> bool:
    if leg.status not in {"submitted", "partially_filled"}:
        return False
    if leg.submitted_at is None:
        return False
    return now - leg.submitted_at.astimezone(UTC) >= SANDBOX_ORDER_TIMEOUT


def _validate_state_matches_leg(
    leg: ExecutionLegRecord,
    state: TBankSandboxOrderState,
) -> None:
    if state.order_request_id != str(leg.request_id):
        raise ExecutionServiceError("sandbox_request_id_mismatch")
    if state.instrument_uid != leg.instrument_uid:
        raise ExecutionServiceError("sandbox_instrument_mismatch")
    if state.lots_requested != leg.lots_requested:
        raise ExecutionServiceError("sandbox_lot_count_mismatch")
    expected_direction = {
        "buy": "ORDER_DIRECTION_BUY",
        "sell": "ORDER_DIRECTION_SELL",
    }[leg.action]
    if state.direction and state.direction != expected_direction:
        raise ExecutionServiceError("sandbox_direction_mismatch")
    if state.order_type and state.order_type != "ORDER_TYPE_LIMIT":
        raise ExecutionServiceError("sandbox_order_type_mismatch")


def _executed_amount(state: TBankSandboxOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.total_order_amount is None:
        raise ExecutionServiceError("sandbox_executed_amount_missing")
    return _rub(state.total_order_amount)


def _executed_commission(state: TBankSandboxOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.executed_commission is None:
        raise ExecutionServiceError("sandbox_executed_commission_missing")
    return _rub(state.executed_commission)


def _rub(value: TBankMoney) -> Decimal:
    if value.currency.upper() != "RUB":
        raise ExecutionServiceError("sandbox_money_not_rub")
    amount = Decimal(value.value)
    if not amount.is_finite() or amount < 0:
        raise ExecutionServiceError("sandbox_money_invalid")
    return amount
