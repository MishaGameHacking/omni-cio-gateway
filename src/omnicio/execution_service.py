"""R6/R7 execution orchestration with fail-closed production canary authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from .broker import BrokerConnectionError, BrokerService
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
    TBankMaxLots,
    TBankMoney,
    TBankNotFound,
    TBankOrderState,
    TBankUnavailable,
)

ORDER_TIMEOUT = timedelta(minutes=2)
SANDBOX_ORDER_TIMEOUT = ORDER_TIMEOUT
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


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
        live_execution_enabled: bool = False,
        live_max_order_rub: int = 10_000,
        live_max_daily_rub: int = 20_000,
    ) -> None:
        if live_max_order_rub <= 0 or live_max_daily_rub < live_max_order_rub:
            raise ValueError("live execution operator caps are invalid")
        self.store = store
        self.broker = broker
        self.live_execution_enabled = live_execution_enabled
        self.live_max_order_rub = Decimal(live_max_order_rub)
        self.live_max_daily_rub = Decimal(live_max_daily_rub)

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
        if mode == "live":
            if not self.live_execution_enabled:
                raise ExecutionServiceError("live_execution_disabled")
            try:
                self.broker.live_account(user_id)
            except BrokerConnectionError as exc:
                raise ExecutionServiceError("live_account_mismatch") from exc
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

        if run.mode == "sandbox":
            self._require_sandbox_account(user_id, run)
        elif run.mode == "live":
            self._require_live_connection(user_id, run)
        else:
            raise ExecutionServiceError("execution_mode_invalid")
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

    def _live_submit_authority(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        if not self.live_execution_enabled:
            raise ExecutionServiceError("live_execution_disabled")
        mandate = self.store.live_mandate(
            user_id,
            account_id=run.account_id,
        )
        if (
            mandate is None
            or run.live_mandate_id is None
            or mandate.id != run.live_mandate_id
        ):
            raise ExecutionServiceError("live_mandate_inactive")
        self.broker.live_account(user_id)

    def _submit_pending(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> ExecutionLegStatus:
        if run.mode == "sandbox":
            self._sandbox_preflight(user_id, leg)
        elif run.mode == "live":
            self._live_submit_authority(user_id, run)
            self._live_preflight(user_id, run, leg, observed_at)
        else:
            raise ExecutionServiceError("provider_execution_mode_invalid")

        prefix = run.mode
        self.store.transition_leg(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            expected_statuses=("pending",),
            new_status="submitting",
            event_type=f"{prefix}_preflight_passed",
            details={
                "request_id": str(leg.request_id),
                "margin": False,
                "order_type": "limit",
                "time_in_force": (
                    "fill_and_kill" if run.mode == "live" else "day"
                ),
            },
            now=observed_at,
        )
        try:
            if run.mode == "live":
                state = self.broker.post_live_order(
                    user_id,
                    leg.instrument_uid,
                    quantity_lots=leg.lots_requested,
                    price=str(leg.limit_price),
                    direction=leg.action,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
            else:
                state = self.broker.post_sandbox_order(
                    user_id,
                    leg.instrument_uid,
                    quantity_lots=leg.lots_requested,
                    price=str(leg.limit_price),
                    direction=leg.action,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
        except BrokerConnectionError as exc:
            code = f"{prefix}_connection_changed"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            raise ExecutionServiceError(code) from exc
        except TBankUnavailable:
            code = f"{prefix}_submit_ambiguous"
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

        return self._record_provider_state(
            user_id,
            run,
            leg,
            state,
            observed_at,
            expected_statuses=("submitting",),
            event_type=f"{prefix}_order_submitted",
        )

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
        self._validate_lot_limits("sandbox", leg, max_lots)
        estimate = self.broker.sandbox_order_price(
            user_id,
            leg.instrument_uid,
            price=str(leg.limit_price),
            direction=leg.action,
            quantity_lots=leg.lots_requested,
        )
        self._validate_proposal_money_bound("sandbox", leg, _rub(estimate.total_order_amount))

    def _live_preflight(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> None:
        mandate = self.store.live_mandate(
            user_id,
            account_id=run.account_id,
            now=observed_at,
        )
        if (
            mandate is None
            or run.live_mandate_id is None
            or mandate.id != run.live_mandate_id
        ):
            raise ExecutionServiceError("live_mandate_inactive")
        if leg.action != "buy":
            raise ExecutionServiceError("live_canary_buy_only")

        max_lots = self.broker.live_max_lots(
            user_id,
            leg.instrument_uid,
            price=str(leg.limit_price),
        )
        self._validate_lot_limits("live", leg, max_lots)
        estimate = self.broker.live_order_price(
            user_id,
            leg.instrument_uid,
            price=str(leg.limit_price),
            direction=leg.action,
            quantity_lots=leg.lots_requested,
        )
        total = _rub(estimate.total_order_amount)
        self._validate_proposal_money_bound("live", leg, total)

        order_cap = min(
            mandate.max_order_notional_rub,
            self.live_max_order_rub,
        )
        daily_cap = min(
            mandate.max_daily_notional_rub,
            self.live_max_daily_rub,
        )
        if total > order_cap:
            raise ExecutionServiceError("live_order_notional_cap_exceeded")
        local_now = observed_at.astimezone(MOSCOW_TZ)
        day_start = local_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        used = self.store.live_daily_notional(
            user_id,
            account_id=run.account_id,
            day_start=day_start,
        )
        if used + total > daily_cap:
            raise ExecutionServiceError("live_daily_notional_cap_exceeded")

    @staticmethod
    def _validate_lot_limits(
        prefix: str,
        leg: ExecutionLegRecord,
        max_lots: TBankMaxLots,
    ) -> None:
        currency = max_lots.currency
        buy_max = max_lots.buy_max_lots
        sell_max = max_lots.sell_max_lots
        if currency not in {"", "RUB"}:
            raise ExecutionServiceError(f"{prefix}_max_lots_currency_invalid")
        if leg.action == "buy":
            if buy_max < leg.lots_requested:
                raise ExecutionServiceError(f"{prefix}_buy_lots_exceed_available")
        elif sell_max < leg.lots_requested:
            raise ExecutionServiceError(f"{prefix}_sell_lots_exceed_available")

    @staticmethod
    def _validate_proposal_money_bound(
        prefix: str,
        leg: ExecutionLegRecord,
        total: Decimal,
    ) -> None:
        if leg.action == "buy":
            if leg.max_spend_rub is None or total > leg.max_spend_rub:
                raise ExecutionServiceError(f"{prefix}_buy_would_overspend")
        elif leg.min_proceeds_rub is None or total < leg.min_proceeds_rub:
            raise ExecutionServiceError(f"{prefix}_sell_below_min_proceeds")

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


def _timed_out(leg: ExecutionLegRecord, now: datetime) -> bool:
    if leg.status not in {"submitted", "partially_filled"}:
        return False
    if leg.submitted_at is None:
        return False
    return now - leg.submitted_at.astimezone(UTC) >= ORDER_TIMEOUT


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
