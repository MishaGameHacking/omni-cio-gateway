from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import hashlib
import hmac
from typing import TypeVar
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from omni_cio.contracts.v1.plan_execution import (
    BrokerExecutionStatus,
    PlanExecutionAdvanceAction,
    PlanExecutionAdvanceResultV1,
    PlanExecutionAttemptState,
    PlanExecutionAttemptV1,
    PlanExecutionCurrentStateV1,
    PlanExecutionHaltCode,
    PlanExecutionInstrumentBindingV1,
    PlanExecutionInstrumentStateV1,
    PlanExecutionLegEvidenceV1,
    PlanExecutionSessionState,
    PlanExecutionSessionV1,
    PlanExecutionSettingsV1,
    PlanExecutionSide,
    PlanExecutionStageState,
    PlanExecutionStageV1,
)
from omni_cio.contracts.v1.portfolio_plan import (
    PlanMarketBaselineV1,
    PortfolioPlanAction,
    PortfolioPlanReviewInputV1,
    PortfolioPlanV1,
    portfolio_plan_sha256,
)
from omni_cio.plans import review_portfolio_plan
from omni_cio.real_trading.client_v1 import RealTradingApiFailure
from omni_cio.real_trading.models_v1 import RealTradingPolicyV1

from .adapter_v1 import SingleOrderExecutionPrimitiveV1
from .broker_reconciliation_v1 import (
    PlanExecutionBrokerStateError,
    broker_snapshot_from_proposal,
)
from .journal_v1 import (
    PlanExecutionJournalConflict,
    PlanExecutionJournalV1,
)


MOSCOW = ZoneInfo("Europe/Moscow")
_T = TypeVar("_T")

InstrumentBindingProviderV1 = Callable[
    [str, datetime],
    PlanExecutionInstrumentBindingV1,
]
CurrentStateProviderV1 = Callable[
    [PortfolioPlanV1, datetime],
    PlanExecutionCurrentStateV1,
]
LegEvidenceProviderV1 = Callable[
    [PlanMarketBaselineV1, PlanExecutionInstrumentBindingV1, datetime],
    PlanExecutionLegEvidenceV1,
]


class SafePlanExecutionError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        halt_code: PlanExecutionHaltCode | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.halt_code = halt_code


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_TIME_INVALID",
            "Plan execution timestamps must be timezone-aware.",
        )
    return result.astimezone(timezone.utc)


def _moscow_date(value: datetime) -> date:
    return value.astimezone(MOSCOW).date()


def _sha(*parts: object) -> str:
    payload = "\n".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ceil_ratio(numerator: int, denominator: int) -> int:
    if numerator <= 0 or denominator <= 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_RATIO_INVALID",
            "Stage ratio inputs must be positive.",
        )
    return (numerator + denominator - 1) // denominator


def _floor_decimal_ratio(numerator: Decimal, denominator: Decimal) -> int:
    if denominator <= 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_RATIO_INVALID",
            "Stage monetary denominator must be positive.",
        )
    return int((numerator / denominator).to_integral_value(rounding=ROUND_FLOOR))


def _signed_lots(side: PlanExecutionSide, lots: int) -> int:
    return lots if side is PlanExecutionSide.BUY else -lots


def _direction(action: PortfolioPlanAction) -> PlanExecutionSide:
    if action is PortfolioPlanAction.BUY:
        return PlanExecutionSide.BUY
    if action is PortfolioPlanAction.SELL:
        return PlanExecutionSide.SELL
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_NO_ACTION",
        "NO_ACTION plan has no real-money execution leg.",
    )


def _canonical_plan(plan: PortfolioPlanV1) -> PortfolioPlanV1:
    try:
        result = PortfolioPlanV1.model_validate(plan.model_dump(mode="python"))
    except (AttributeError, ValidationError) as exc:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PLAN_TAMPERED",
            "Immutable portfolio plan failed canonical validation.",
            halt_code=PlanExecutionHaltCode.PLAN_INVALID,
        ) from exc
    if result.plan_sha256 != portfolio_plan_sha256(result):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PLAN_HASH_MISMATCH",
            "Immutable portfolio plan hash does not match its payload.",
            halt_code=PlanExecutionHaltCode.PLAN_INVALID,
        )
    return result


def _baseline_map(plan: PortfolioPlanV1) -> dict[str, PlanMarketBaselineV1]:
    return {row.stable_key: row for row in plan.market_baselines}


def _position_map(state: PlanExecutionCurrentStateV1) -> dict[str, int]:
    return {row.stable_key: row.lots for row in state.positions}


def _target_current_lots(plan: PortfolioPlanV1) -> dict[str, int]:
    return {row.stable_key: row.current_lots for row in plan.targets}


def _actionable_plan_legs(plan: PortfolioPlanV1):
    return tuple(row for row in plan.legs if row.optimizer_leg is not None)


def _all_stages(session: PlanExecutionSessionV1) -> tuple[PlanExecutionStageV1, ...]:
    return tuple(
        stage
        for instrument in session.instrument_states
        for stage in instrument.stages
    )


def _stage_by_id(
    session: PlanExecutionSessionV1,
    stage_id: str,
) -> PlanExecutionStageV1:
    for stage in _all_stages(session):
        if stage.stage_id == stage_id:
            return stage
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_STAGE_NOT_FOUND",
        "Plan execution stage was not found.",
    )


def _instrument_for_stage(
    session: PlanExecutionSessionV1,
    stage: PlanExecutionStageV1,
) -> PlanExecutionInstrumentStateV1:
    for item in session.instrument_states:
        if item.binding.stable_key == stage.stable_key:
            return item
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_INSTRUMENT_NOT_FOUND",
        "Plan execution instrument state was not found.",
    )


def _replace_stage(
    session: PlanExecutionSessionV1,
    updated_stage: PlanExecutionStageV1,
    *,
    **session_updates: object,
) -> PlanExecutionSessionV1:
    instruments: list[PlanExecutionInstrumentStateV1] = []
    found = False
    for item in session.instrument_states:
        stages: list[PlanExecutionStageV1] = []
        for stage in item.stages:
            if stage.stage_id == updated_stage.stage_id:
                stages.append(updated_stage)
                found = True
            else:
                stages.append(stage)
        instruments.append(item.model_copy(update={"stages": tuple(stages)}))
    if not found:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_STAGE_NOT_FOUND",
            "Cannot update unknown plan execution stage.",
        )
    values = {
        "instrument_states": tuple(instruments),
        "revision": session.revision + 1,
        **session_updates,
    }
    return PlanExecutionSessionV1.model_validate(
        session.model_copy(update=values).model_dump(mode="python")
    )


def _replace_session(
    session: PlanExecutionSessionV1,
    **updates: object,
) -> PlanExecutionSessionV1:
    return PlanExecutionSessionV1.model_validate(
        session.model_copy(
            update={"revision": session.revision + 1, **updates}
        ).model_dump(mode="python")
    )


def _next_stage(session: PlanExecutionSessionV1) -> PlanExecutionStageV1 | None:
    candidates = sorted(
        (
            stage
            for stage in _all_stages(session)
            if stage.state is not PlanExecutionStageState.FILLED
        ),
        key=lambda row: (row.leg_sequence, row.stage_index, row.stage_id),
    )
    return candidates[0] if candidates else None


def _stage_slice_sizes(total_lots: int, count: int) -> tuple[int, ...]:
    base, extra = divmod(total_lots, count)
    sizes = tuple(base + (1 if index < extra else 0) for index in range(count))
    if not sizes or min(sizes) <= 0 or sum(sizes) != total_lots:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_STAGE_SIZING_INVALID",
            "Cannot divide plan leg into positive deterministic stages.",
        )
    return sizes


def _limit_price_step_ok(price: Decimal, step: Decimal) -> bool:
    return step > 0 and price % step == 0


def _drift_bps(current: Decimal, baseline: Decimal) -> Decimal:
    return abs(current - baseline) / baseline * Decimal("10000")


def _evidence_guard(
    *,
    baseline: PlanMarketBaselineV1,
    binding: PlanExecutionInstrumentBindingV1,
    evidence: PlanExecutionLegEvidenceV1,
    side: PlanExecutionSide,
    plan: PortfolioPlanV1,
    settings: PlanExecutionSettingsV1,
    now: datetime,
) -> Decimal:
    observation = evidence.observation
    quote = evidence.quote
    if binding.stable_key != baseline.stable_key:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_INSTRUMENT_BINDING_MISMATCH",
            "Instrument binding stable key does not match plan baseline.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
        )
    if quote.stable_key != binding.stable_key or quote.instrument_uid != binding.instrument_uid:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_QUOTE_IDENTITY_MISMATCH",
            "Execution quote does not match bound instrument identity.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
        )
    if quote.lot_size != binding.lot_size or binding.lot_size != baseline.lot_size:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_LOT_BINDING_MISMATCH",
            "Execution lot size changed from the immutable plan.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
        )
    if binding.instrument_type not in {"share", "etf"}:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_INSTRUMENT_TYPE_NOT_SUPPORTED",
            "WP12 real execution is restricted to the proven share/ETF surface.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_TYPE_NOT_SUPPORTED,
        )

    quote_age = (now - quote.as_of).total_seconds()
    if quote_age > settings.quote_max_age_seconds or (
        quote_age < -settings.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_QUOTE_STALE",
            "Fresh execution quote is required immediately before stage action.",
            halt_code=PlanExecutionHaltCode.EXECUTION_QUOTE_STALE,
        )

    tolerance = plan.drift_tolerance
    observation_age = (now - observation.observed_at).total_seconds()
    if observation_age > tolerance.market_max_age_seconds or (
        observation_age < -tolerance.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_MARKET_EVIDENCE_STALE",
            "Plan market observation is stale or future-dated.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    friction_age = (now - observation.friction_as_of).total_seconds()
    if friction_age > tolerance.friction_max_age_seconds or (
        friction_age < -tolerance.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_FRICTION_EVIDENCE_STALE",
            "Plan friction evidence is stale or future-dated.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if _drift_bps(
        observation.clean_unit_price_base,
        baseline.clean_unit_price_base,
    ) > tolerance.max_clean_price_drift_bps:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_CLEAN_PRICE_DRIFT",
            "Clean market price drift exceeded immutable plan tolerance.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if baseline.accrued_interest_per_lot_base is not None:
        if observation.accrued_interest_per_lot_base is None:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ACCRUED_INTEREST_MISSING",
                "Bond accrued-interest evidence is missing.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
        clean_lot = baseline.clean_unit_price_base * Decimal(baseline.lot_size)
        accrued_drift = (
            abs(
                observation.accrued_interest_per_lot_base
                - baseline.accrued_interest_per_lot_base
            )
            / clean_lot
            * Decimal("10000")
        )
        if accrued_drift > tolerance.max_accrued_interest_drift_bps:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ACCRUED_INTEREST_DRIFT",
                "Accrued-interest drift exceeded immutable plan tolerance.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
    if observation.spread_bps - baseline.spread_bps > tolerance.max_spread_widening_bps:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_SPREAD_DRIFT",
            "Spread widened beyond immutable plan tolerance.",
            halt_code=PlanExecutionHaltCode.EXECUTION_SPREAD_TOO_WIDE,
        )
    if (
        observation.average_daily_turnover_base
        / baseline.average_daily_turnover_base
        < tolerance.minimum_turnover_ratio
        or observation.top_of_book_depth_base
        / baseline.top_of_book_depth_base
        < tolerance.minimum_top_of_book_depth_ratio
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_LIQUIDITY_DRIFT",
            "Market capacity deteriorated below immutable plan tolerance.",
            halt_code=PlanExecutionHaltCode.EXECUTION_LIQUIDITY_DROPPED,
        )
    if (
        observation.friction_source_sha256s != baseline.friction_source_sha256s
        or observation.commission_bps != baseline.commission_bps
        or observation.estimated_sell_tax_bps != baseline.estimated_sell_tax_bps
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_FRICTION_CHANGED",
            "Commission/tax evidence changed from the immutable plan.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if side is PlanExecutionSide.BUY and observation.account_eligible is not True:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_BUY_ELIGIBILITY_CHANGED",
            "BUY eligibility changed after immutable plan creation.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if baseline.fx_rate_to_base is not None:
        if observation.fx_rate_to_base is None or observation.fx_as_of is None:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_FX_EVIDENCE_MISSING",
                "Required FX evidence is missing.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
        fx_age = (now - observation.fx_as_of).total_seconds()
        if fx_age > tolerance.fx_max_age_seconds or (
            fx_age < -tolerance.future_tolerance_seconds
        ):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_FX_EVIDENCE_STALE",
                "FX evidence is stale or future-dated.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
        if _drift_bps(
            observation.fx_rate_to_base,
            baseline.fx_rate_to_base,
        ) > tolerance.max_fx_drift_bps:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_FX_DRIFT",
                "FX drift exceeded immutable plan tolerance.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )

    limit_price = quote.limit_price(side)
    if not _limit_price_step_ok(limit_price, quote.min_price_increment):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PRICE_STEP_MISMATCH",
            "Server-selected LIMIT price is not on the instrument price step.",
            halt_code=PlanExecutionHaltCode.EXECUTION_PRICE_STEP_MISMATCH,
        )
    if _drift_bps(
        limit_price,
        observation.clean_unit_price_base,
    ) > settings.max_execution_price_change_bps:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_BOOK_PRICE_CHANGED",
            "Executable side of book moved too far from the current clean price.",
            halt_code=PlanExecutionHaltCode.EXECUTION_PRICE_CHANGED,
        )
    return limit_price


def _review_input(
    *,
    plan: PortfolioPlanV1,
    state: PlanExecutionCurrentStateV1,
    evidences: Iterable[PlanExecutionLegEvidenceV1],
    now: datetime,
) -> PortfolioPlanReviewInputV1:
    return PortfolioPlanReviewInputV1(
        reviewed_at=now,
        portfolio_snapshot_sha256=state.portfolio_snapshot_sha256,
        policy_reference=state.policy_reference,
        current_risk_assessment_sha256=state.risk_assessment_sha256,
        strategy_selection_sha256=state.strategy_selection_sha256,
        optimizer_sha256=state.optimizer_sha256,
        target_risk_assessment_sha256=state.target_risk_assessment_sha256,
        market_observations=tuple(row.observation for row in evidences),
    )


def _expected_positions(
    plan: PortfolioPlanV1,
    session: PlanExecutionSessionV1,
) -> dict[str, int]:
    result = _target_current_lots(plan)
    for stage in _all_stages(session):
        if stage.broker_terminal_lots:
            result[stage.stable_key] = result.get(stage.stable_key, 0) + _signed_lots(
                stage.side,
                stage.broker_terminal_lots,
            )
    return result


def _progress_matches(
    *,
    plan: PortfolioPlanV1,
    session: PlanExecutionSessionV1,
    state: PlanExecutionCurrentStateV1,
    settings: PlanExecutionSettingsV1,
    now: datetime,
) -> tuple[bool, PlanExecutionHaltCode | None, str | None]:
    age = (now - state.observed_at).total_seconds()
    if age > settings.max_portfolio_reconciliation_age_seconds or age < 0:
        return (
            False,
            PlanExecutionHaltCode.PORTFOLIO_RECONCILIATION_TIMEOUT,
            "Current portfolio state is stale or future-dated.",
        )
    if state.policy_reference != plan.policy_reference:
        return False, PlanExecutionHaltCode.POLICY_CHANGED, "Owner policy changed."
    if not state.risk_decision_ready:
        return (
            False,
            PlanExecutionHaltCode.CURRENT_RISK_NOT_READY,
            "Current risk state is not decision-ready.",
        )
    if not state.risk_policy_compliant:
        return (
            False,
            PlanExecutionHaltCode.CURRENT_RISK_POLICY_BREACH,
            "Current risk state breached owner policy.",
        )

    expected = _expected_positions(plan, session)
    observed = _position_map(state)
    observed_complete = {key: observed.get(key, 0) for key in expected}
    unexpected = {key: lots for key, lots in observed.items() if key not in expected and lots}
    if observed_complete != expected or unexpected:
        return (
            False,
            PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            "Portfolio lots do not match broker-confirmed execution progress.",
        )

    expected_cash = plan.current_cash_base + session.confirmed_cash_delta_rub
    lower = (
        expected_cash
        - session.estimated_tax_allowance_rub
        - settings.cash_reconciliation_tolerance_rub
    )
    upper = expected_cash + settings.cash_reconciliation_tolerance_rub
    if not lower <= state.cash_base <= upper:
        return (
            False,
            PlanExecutionHaltCode.CASH_RECONCILIATION_MISMATCH,
            "Cash does not reconcile to broker-confirmed plan progress.",
        )
    return True, None, None


def _tax_allowance_for_fills(
    *,
    plan: PortfolioPlanV1,
    stage: PlanExecutionStageV1,
    filled_lots: int,
) -> Decimal:
    if stage.side is not PlanExecutionSide.SELL or filled_lots <= 0:
        return Decimal("0")
    plan_leg = next(
        row.optimizer_leg
        for row in plan.legs
        if row.optimizer_leg is not None
        and row.optimizer_leg.stable_key == stage.stable_key
    )
    assert plan_leg is not None
    if plan_leg.quantity_lots <= 0:
        return Decimal("0")
    return (
        plan_leg.estimated_tax_base
        * Decimal(filled_lots)
        / Decimal(plan_leg.quantity_lots)
    )


def _stage_quantity_for_cap(
    *,
    plan_leg,
    policy: RealTradingPolicyV1,
) -> tuple[int, int]:
    quantity = plan_leg.quantity_lots
    per_lot = (
        plan_leg.settlement_notional_base
        + plan_leg.commission_base
        + plan_leg.estimated_tax_base
    ) / Decimal(quantity)
    max_lots_by_cap = _floor_decimal_ratio(policy.max_order_rub, per_lot)
    if max_lots_by_cap <= 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_ORDER_CAP_TOO_SMALL",
            "One immutable plan lot exceeds the existing real-order cap.",
            halt_code=PlanExecutionHaltCode.PREPARE_REJECTED,
        )
    stage_count = max(
        plan_leg.required_execution_days,
        _ceil_ratio(quantity, max_lots_by_cap),
    )
    return stage_count, max_lots_by_cap


class SafePlanExecutionServiceV1:
    """Owner-confirmed, fail-closed orchestrator over v8.6.1 real orders."""

    def __init__(
        self,
        *,
        single_order: SingleOrderExecutionPrimitiveV1,
        real_policy: RealTradingPolicyV1,
        journal: PlanExecutionJournalV1,
        instrument_binding_provider: InstrumentBindingProviderV1,
        current_state_provider: CurrentStateProviderV1,
        leg_evidence_provider: LegEvidenceProviderV1,
        settings: PlanExecutionSettingsV1 | None = None,
        require_durable_journal: bool = True,
    ) -> None:
        try:
            real_policy.validate()
        except ValueError as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_REAL_POLICY_INVALID",
                str(exc),
            ) from exc
        if require_durable_journal and not journal.durable:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_DURABLE_JOURNAL_REQUIRED",
                "Real plan execution requires a durable plan-session journal.",
            )
        self._single_order = single_order
        self._real_policy = real_policy
        self._journal = journal
        self._binding_provider = instrument_binding_provider
        self._current_state_provider = current_state_provider
        self._evidence_provider = leg_evidence_provider
        self._settings = settings or PlanExecutionSettingsV1()

    def _commit(
        self,
        before: PlanExecutionSessionV1,
        after: PlanExecutionSessionV1,
    ) -> PlanExecutionSessionV1:
        try:
            return self._journal.compare_and_swap(
                before.execution_id,
                expected_revision=before.revision,
                updated=after,
            )
        except PlanExecutionJournalConflict as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_JOURNAL_CONFLICT",
                "Plan execution state changed concurrently.",
                halt_code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
            ) from exc

    def _result(
        self,
        *,
        action: PlanExecutionAdvanceAction,
        session: PlanExecutionSessionV1,
        message: str,
        stage_id: str | None = None,
        proposal_id: str | None = None,
        broker_snapshot=None,
    ) -> PlanExecutionAdvanceResultV1:
        active = session.owner_approved and session.state not in {
            PlanExecutionSessionState.HALTED,
            PlanExecutionSessionState.COMPLETED,
        }
        return PlanExecutionAdvanceResultV1(
            action=action,
            session=session,
            stage_id=stage_id,
            proposal_id=proposal_id,
            message=message,
            broker_snapshot=broker_snapshot,
            execution_authorized=active,
            trading_methods=True,
        )

    def _halt(
        self,
        session: PlanExecutionSessionV1,
        *,
        code: PlanExecutionHaltCode,
        message: str,
        stage: PlanExecutionStageV1 | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        if stage is not None:
            halted_stage = PlanExecutionStageV1.model_validate(
                stage.model_copy(update={"state": PlanExecutionStageState.HALTED}).model_dump(
                    mode="python"
                )
            )
            updated = _replace_stage(
                session,
                halted_stage,
                state=PlanExecutionSessionState.HALTED,
                halt_code=code,
                halt_message=message,
            )
        else:
            updated = _replace_session(
                session,
                state=PlanExecutionSessionState.HALTED,
                halt_code=code,
                halt_message=message,
            )
        committed = self._commit(session, updated)
        return self._result(
            action=PlanExecutionAdvanceAction.HALTED,
            session=committed,
            stage_id=stage.stage_id if stage else None,
            message=message,
        )

    def _current_state(
        self,
        plan: PortfolioPlanV1,
        now: datetime,
    ) -> PlanExecutionCurrentStateV1:
        try:
            return PlanExecutionCurrentStateV1.model_validate(
                self._current_state_provider(plan, now).model_dump(mode="python")
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_CURRENT_STATE_UNAVAILABLE",
                "Trusted read-only portfolio/risk state is unavailable.",
                halt_code=PlanExecutionHaltCode.CURRENT_RISK_NOT_READY,
            ) from exc

    def _binding(
        self,
        stable_key: str,
        now: datetime,
    ) -> PlanExecutionInstrumentBindingV1:
        try:
            binding = PlanExecutionInstrumentBindingV1.model_validate(
                self._binding_provider(stable_key, now).model_dump(mode="python")
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INSTRUMENT_BINDING_MISSING",
                "Trusted execution instrument binding is unavailable.",
                halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISSING,
            ) from exc
        if binding.stable_key != stable_key:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INSTRUMENT_BINDING_MISMATCH",
                "Trusted binding returned a different stable key.",
                halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
            )
        return binding

    def _evidence(
        self,
        *,
        baseline: PlanMarketBaselineV1,
        binding: PlanExecutionInstrumentBindingV1,
        now: datetime,
    ) -> PlanExecutionLegEvidenceV1:
        try:
            return PlanExecutionLegEvidenceV1.model_validate(
                self._evidence_provider(baseline, binding, now).model_dump(
                    mode="python"
                )
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_EVIDENCE_MISSING",
                "Trusted execution quote/evidence is unavailable.",
                halt_code=PlanExecutionHaltCode.EXECUTION_EVIDENCE_MISSING,
            ) from exc

    def prepare_plan(
        self,
        *,
        plan: PortfolioPlanV1,
        now: datetime | None = None,
    ) -> PlanExecutionSessionV1:
        current = _aware_utc(now)
        plan = _canonical_plan(plan)
        if not plan.approval_required or not _actionable_plan_legs(plan):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_NO_ACTION",
                "NO_ACTION plan does not create a real execution session.",
            )
        if current >= plan.expires_at:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_PLAN_EXPIRED",
                "Immutable portfolio plan expired before execution preparation.",
                halt_code=PlanExecutionHaltCode.PLAN_EXPIRED,
            )

        state = self._current_state(plan, current)
        initial_expected = _target_current_lots(plan)
        observed = _position_map(state)
        observed_complete = {key: observed.get(key, 0) for key in initial_expected}
        unexpected = {key: lots for key, lots in observed.items() if key not in initial_expected and lots}
        if observed_complete != initial_expected or unexpected:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_PORTFOLIO_MISMATCH",
                "Current portfolio lots differ from immutable plan start state.",
                halt_code=PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            )
        if abs(state.cash_base - plan.current_cash_base) > self._settings.cash_reconciliation_tolerance_rub:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_CASH_MISMATCH",
                "Current cash differs from immutable plan start state.",
                halt_code=PlanExecutionHaltCode.CASH_RECONCILIATION_MISMATCH,
            )
        if not state.risk_decision_ready or not state.risk_policy_compliant:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_RISK_NOT_READY",
                "Current risk state is not safe for plan execution.",
                halt_code=(
                    PlanExecutionHaltCode.CURRENT_RISK_POLICY_BREACH
                    if not state.risk_policy_compliant
                    else PlanExecutionHaltCode.CURRENT_RISK_NOT_READY
                ),
            )

        baselines = _baseline_map(plan)
        bindings: dict[str, PlanExecutionInstrumentBindingV1] = {}
        evidences: list[PlanExecutionLegEvidenceV1] = []
        for plan_leg in _actionable_plan_legs(plan):
            optimizer_leg = plan_leg.optimizer_leg
            assert optimizer_leg is not None
            binding = self._binding(optimizer_leg.stable_key, current)
            baseline = baselines[optimizer_leg.stable_key]
            evidence = self._evidence(
                baseline=baseline,
                binding=binding,
                now=current,
            )
            side = _direction(plan_leg.action)
            _evidence_guard(
                baseline=baseline,
                binding=binding,
                evidence=evidence,
                side=side,
                plan=plan,
                settings=self._settings,
                now=current,
            )
            if binding.lot_size != optimizer_leg.lot_size:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_LOT_BINDING_MISMATCH",
                    "Broker lot size differs from immutable plan leg.",
                    halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
                )
            if binding.instrument_type not in self._real_policy.allowed_instrument_types:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_REAL_POLICY_TYPE_BLOCKED",
                    "Instrument type is outside existing real-trading policy.",
                    halt_code=PlanExecutionHaltCode.INSTRUMENT_TYPE_NOT_SUPPORTED,
                )
            bindings[optimizer_leg.stable_key] = binding
            evidences.append(evidence)

        review = review_portfolio_plan(
            plan=plan,
            review_input=_review_input(
                plan=plan,
                state=state,
                evidences=evidences,
                now=current,
            ),
        )
        if not review.plan_valid or review.expected_owner_approval_phrase is None:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_REVIEW_INVALID",
                "Immutable plan failed final pre-execution review.",
                halt_code=PlanExecutionHaltCode.PLAN_INVALID,
            )

        instrument_states: list[PlanExecutionInstrumentStateV1] = []
        prepared_day = _moscow_date(current)
        for plan_leg in _actionable_plan_legs(plan):
            optimizer_leg = plan_leg.optimizer_leg
            assert optimizer_leg is not None
            side = _direction(plan_leg.action)
            stage_count, _ = _stage_quantity_for_cap(
                plan_leg=optimizer_leg,
                policy=self._real_policy,
            )
            sizes = _stage_slice_sizes(optimizer_leg.quantity_lots, stage_count)
            stages = tuple(
                PlanExecutionStageV1(
                    stage_id=_sha(
                        "plan-execution-stage-v1",
                        plan.plan_sha256,
                        plan_leg.sequence,
                        index,
                        optimizer_leg.stable_key,
                    ),
                    leg_sequence=plan_leg.sequence,
                    stable_key=optimizer_leg.stable_key,
                    side=side,
                    stage_index=index,
                    stage_count=stage_count,
                    planned_lots=size,
                    not_before_moscow_date=prepared_day + timedelta(days=index - 1),
                )
                for index, size in enumerate(sizes, start=1)
            )
            instrument_states.append(
                PlanExecutionInstrumentStateV1(
                    binding=bindings[optimizer_leg.stable_key],
                    stages=stages,
                )
            )

        execution_id = _sha("plan-execution-v1", plan.plan_sha256)
        session = PlanExecutionSessionV1(
            execution_id=execution_id,
            plan_sha256=plan.plan_sha256,
            initial_review_sha256=review.review_sha256,
            prepared_at=current,
            last_reviewed_at=current,
            last_review_sha256=review.review_sha256,
            state=PlanExecutionSessionState.PREPARED,
            instrument_states=tuple(instrument_states),
        )
        try:
            return self._journal.put(session)
        except PlanExecutionJournalConflict as exc:
            existing = self._journal.get(execution_id)
            if existing.plan_sha256 == plan.plan_sha256:
                return existing
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ID_CONFLICT",
                "Execution id already exists for a different plan payload.",
                halt_code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
            ) from exc

    def approve_plan(
        self,
        *,
        execution_id: str,
        plan: PortfolioPlanV1,
        owner_approval_phrase: str,
        now: datetime | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        current = _aware_utc(now)
        plan = _canonical_plan(plan)
        session = self._journal.get(execution_id)
        if session.plan_sha256 != plan.plan_sha256:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.PLAN_INVALID,
                message="Execution session does not match immutable plan SHA.",
            )
        if session.owner_approved:
            return self._result(
                action=PlanExecutionAdvanceAction.REPLAY,
                session=session,
                message="Exact plan approval was already recorded; no submit repeated.",
            )
        if current >= plan.expires_at:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.PLAN_EXPIRED,
                message="Immutable plan expired before owner approval.",
            )
        expected = plan.owner_approval_phrase or ""
        if not expected or not hmac.compare_digest(owner_approval_phrase, expected):
            return self._halt(
                session,
                code=PlanExecutionHaltCode.OWNER_APPROVAL_MISMATCH,
                message="Exact owner approval phrase for this plan is required.",
            )

        state = self._current_state(plan, current)
        matched, code, message = _progress_matches(
            plan=plan,
            session=session,
            state=state,
            settings=self._settings,
            now=current,
        )
        if not matched:
            return self._halt(
                session,
                code=code or PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                message=message or "Current state no longer matches plan start.",
            )

        evidence_hash = _sha(
            "plan-owner-approval-v1",
            execution_id,
            plan.plan_sha256,
            owner_approval_phrase,
        )
        updated = _replace_session(
            session,
            state=PlanExecutionSessionState.ACTIVE,
            owner_approved=True,
            owner_approved_at=current,
            owner_approval_evidence_sha256=evidence_hash,
        )
        committed = self._commit(session, updated)
        return self._result(
            action=PlanExecutionAdvanceAction.APPROVED,
            session=committed,
            message="Exact immutable plan approval recorded; no broker submit occurred.",
        )

    def _runtime_guard(
        self,
        *,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> tuple[
        PlanExecutionCurrentStateV1,
        PlanExecutionInstrumentBindingV1,
        PlanExecutionLegEvidenceV1,
        Decimal,
    ]:
        state = self._current_state(plan, now)
        matched, code, message = _progress_matches(
            plan=plan,
            session=session,
            state=state,
            settings=self._settings,
            now=now,
        )
        if not matched:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_PROGRESS_DRIFT",
                message or "Current portfolio progress does not reconcile.",
                halt_code=code or PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            )
        instrument = _instrument_for_stage(session, stage)
        binding = self._binding(stage.stable_key, now)
        if binding != instrument.binding:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INSTRUMENT_BINDING_CHANGED",
                "Trusted execution identity changed after session preparation.",
                halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
            )
        baseline = _baseline_map(plan)[stage.stable_key]
        evidence = self._evidence(baseline=baseline, binding=binding, now=now)
        limit_price = _evidence_guard(
            baseline=baseline,
            binding=binding,
            evidence=evidence,
            side=stage.side,
            plan=plan,
            settings=self._settings,
            now=now,
        )
        return state, binding, evidence, limit_price

    def _prepare_stage(
        self,
        *,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        today = _moscow_date(now)
        if today < stage.not_before_moscow_date:
            return self._result(
                action=PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                session=session,
                stage_id=stage.stage_id,
                message="Stage is intentionally deferred to a later Moscow date.",
            )
        if stage.last_submission_moscow_date == today:
            return self._result(
                action=PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                session=session,
                stage_id=stage.stage_id,
                message="No second staged submit is allowed on the same Moscow date.",
            )
        try:
            _, binding, _, limit_price = self._runtime_guard(
                plan=plan,
                session=session,
                stage=stage,
                now=now,
            )
        except SafePlanExecutionError as exc:
            return self._halt(
                session,
                code=exc.halt_code or PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
                message=exc.message,
                stage=stage,
            )

        quantity = stage.remaining_lots
        if quantity <= 0:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.BROKER_FILL_OVERFLOW,
                message="Pending stage has no remaining lots.",
                stage=stage,
            )
        try:
            proposal = self._single_order.prepare_trade(
                instrument_uid=binding.instrument_uid,
                direction=stage.side.value,
                quantity_lots=quantity,
                limit_price=format(limit_price, "f"),
                rationale=(
                    f"WP12 immutable plan {plan.plan_sha256[:12]} "
                    f"stage {stage.stage_index}/{stage.stage_count}"
                ),
                now=now,
            )
        except RealTradingApiFailure as exc:
            if exc.code == "REAL_DAILY_CAP_EXCEEDED":
                return self._result(
                    action=PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                    session=session,
                    stage_id=stage.stage_id,
                    message="Existing v8.6.1 daily real-money cap defers this stage.",
                )
            return self._halt(
                session,
                code=PlanExecutionHaltCode.PREPARE_REJECTED,
                message=f"Legacy real-trading preflight rejected stage: {exc.code}.",
                stage=stage,
            )

        if (
            proposal.instrument_uid != binding.instrument_uid
            or proposal.direction != stage.side.value
            or proposal.quantity_lots != quantity
            or proposal.limit_price != limit_price
            or proposal.ticker != binding.ticker
            or proposal.isin != binding.isin
        ):
            return self._halt(
                session,
                code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
                message="Prepared legacy proposal differs from server-bound plan stage.",
                stage=stage,
            )

        attempt = PlanExecutionAttemptV1(
            attempt_index=len(stage.attempts) + 1,
            quantity_lots=quantity,
            state=PlanExecutionAttemptState.PREPARED,
            proposal_id=proposal.proposal_id,
            order_request_id=proposal.order_id,
            limit_price=proposal.limit_price,
            prepared_at=now,
        )
        updated_stage = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.PREPARED,
                    "attempts": (*stage.attempts, attempt),
                }
            ).model_dump(mode="python")
        )
        updated = _replace_stage(
            session,
            updated_stage,
            state=PlanExecutionSessionState.ACTIVE,
        )
        committed = self._commit(session, updated)
        return self._result(
            action=PlanExecutionAdvanceAction.STAGE_PREPARED,
            session=committed,
            stage_id=stage.stage_id,
            proposal_id=proposal.proposal_id,
            message="Legacy immutable single-order proposal prepared; no submit occurred.",
        )

    def _submit_prepared_stage(
        self,
        *,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        if not stage.attempts:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
                message="Prepared stage has no execution attempt.",
                stage=stage,
            )
        attempt = stage.attempts[-1]
        if attempt.state is not PlanExecutionAttemptState.PREPARED or not attempt.proposal_id:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
                message="Prepared stage attempt state is inconsistent.",
                stage=stage,
            )
        try:
            _, _, _, fresh_limit = self._runtime_guard(
                plan=plan,
                session=session,
                stage=stage,
                now=now,
            )
        except SafePlanExecutionError as exc:
            return self._halt(
                session,
                code=exc.halt_code or PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
                message=exc.message,
                stage=stage,
            )
        if attempt.limit_price != fresh_limit:
            failed_attempt = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": PlanExecutionAttemptState.FAILED,
                        "failure_code": "PLAN_EXECUTION_REPREPARE_PRICE_CHANGED",
                    }
                ).model_dump(mode="python")
            )
            updated_stage = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={
                        "state": PlanExecutionStageState.PENDING,
                        "attempts": (*stage.attempts[:-1], failed_attempt),
                    }
                ).model_dump(mode="python")
            )
            updated = _replace_stage(session, updated_stage, state=PlanExecutionSessionState.ACTIVE)
            committed = self._commit(session, updated)
            return self._result(
                action=PlanExecutionAdvanceAction.REPLAY,
                session=committed,
                stage_id=stage.stage_id,
                message="Executable LIMIT price changed; stage must be safely re-prepared.",
            )

        proposal = self._single_order.get_proposal(attempt.proposal_id)
        if proposal.state != "prepared":
            if proposal.state in {"submitting", "unknown"}:
                return self._halt(
                    session,
                    code=PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION,
                    message="Underlying proposal is in uncertain submission state; do not resubmit.",
                    stage=stage,
                )
            if proposal.state == "submitted":
                submitted_attempt = PlanExecutionAttemptV1.model_validate(
                    attempt.model_copy(
                        update={
                            "state": PlanExecutionAttemptState.SUBMITTED,
                            "submitted_at": proposal.submitted_at or now,
                            "idempotent_replay": True,
                        }
                    ).model_dump(mode="python")
                )
                updated_stage = PlanExecutionStageV1.model_validate(
                    stage.model_copy(
                        update={
                            "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                            "attempts": (*stage.attempts[:-1], submitted_attempt),
                            "last_submission_moscow_date": _moscow_date(now),
                        }
                    ).model_dump(mode="python")
                )
                updated = _replace_stage(
                    session,
                    updated_stage,
                    state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                )
                committed = self._commit(session, updated)
                return self._result(
                    action=PlanExecutionAdvanceAction.REPLAY,
                    session=committed,
                    stage_id=stage.stage_id,
                    proposal_id=proposal.proposal_id,
                    message="Underlying proposal was already submitted; no second submit occurred.",
                )
            failed_attempt = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": (
                            PlanExecutionAttemptState.EXPIRED
                            if proposal.state == "expired"
                            else PlanExecutionAttemptState.FAILED
                        ),
                        "failure_code": proposal.failure_code or f"REAL_{proposal.state.upper()}",
                    }
                ).model_dump(mode="python")
            )
            updated_stage = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={
                        "state": PlanExecutionStageState.PENDING,
                        "attempts": (*stage.attempts[:-1], failed_attempt),
                    }
                ).model_dump(mode="python")
            )
            updated = _replace_stage(session, updated_stage, state=PlanExecutionSessionState.ACTIVE)
            committed = self._commit(session, updated)
            return self._result(
                action=PlanExecutionAdvanceAction.REPLAY,
                session=committed,
                stage_id=stage.stage_id,
                message="Underlying proposal is no longer prepared; stage may be safely re-prepared.",
            )

        try:
            completed, replay = self._single_order.execute_trade(
                proposal.proposal_id,
                proposal.confirmation_phrase,
                now=now,
            )
        except RealTradingApiFailure as exc:
            if exc.ambiguous_submission or exc.code == "REAL_ORDER_SUBMISSION_UNCERTAIN":
                unknown_attempt = PlanExecutionAttemptV1.model_validate(
                    attempt.model_copy(
                        update={
                            "state": PlanExecutionAttemptState.UNKNOWN,
                            "submitted_at": now,
                            "failure_code": exc.code,
                        }
                    ).model_dump(mode="python")
                )
                updated_stage = PlanExecutionStageV1.model_validate(
                    stage.model_copy(
                        update={
                            "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                            "attempts": (*stage.attempts[:-1], unknown_attempt),
                            "last_submission_moscow_date": _moscow_date(now),
                        }
                    ).model_dump(mode="python")
                )
                updated = _replace_stage(
                    session,
                    updated_stage,
                    state=PlanExecutionSessionState.HALTED,
                    halt_code=PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION,
                    halt_message=(
                        "Submit result is ambiguous; remaining plan execution is halted "
                        "until exact request-id reconciliation."
                    ),
                )
                committed = self._commit(session, updated)
                return self._result(
                    action=PlanExecutionAdvanceAction.HALTED,
                    session=committed,
                    stage_id=stage.stage_id,
                    proposal_id=proposal.proposal_id,
                    message="Ambiguous submit: do not resubmit this stage.",
                )
            if exc.code == "REAL_MARKET_REVALIDATION_REQUIRED":
                return self._result(
                    action=PlanExecutionAdvanceAction.REPLAY,
                    session=session,
                    stage_id=stage.stage_id,
                    proposal_id=proposal.proposal_id,
                    message="Legacy primitive requires a newer trusted market snapshot before submit.",
                )
            if exc.code in {
                "REAL_CONFIRMATION_EXPIRED",
                "REAL_PREFLIGHT_CHANGED",
                "REAL_DAILY_CAP_EXCEEDED",
            }:
                failed_attempt = PlanExecutionAttemptV1.model_validate(
                    attempt.model_copy(
                        update={
                            "state": (
                                PlanExecutionAttemptState.EXPIRED
                                if exc.code == "REAL_CONFIRMATION_EXPIRED"
                                else PlanExecutionAttemptState.FAILED
                            ),
                            "failure_code": exc.code,
                        }
                    ).model_dump(mode="python")
                )
                updated_stage = PlanExecutionStageV1.model_validate(
                    stage.model_copy(
                        update={
                            "state": PlanExecutionStageState.PENDING,
                            "attempts": (*stage.attempts[:-1], failed_attempt),
                        }
                    ).model_dump(mode="python")
                )
                updated = _replace_stage(session, updated_stage, state=PlanExecutionSessionState.ACTIVE)
                committed = self._commit(session, updated)
                return self._result(
                    action=(
                        PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY
                        if exc.code == "REAL_DAILY_CAP_EXCEEDED"
                        else PlanExecutionAdvanceAction.REPLAY
                    ),
                    session=committed,
                    stage_id=stage.stage_id,
                    message=f"Legacy submit preflight changed ({exc.code}); no unsafe retry occurred.",
                )
            return self._halt(
                session,
                code=PlanExecutionHaltCode.SUBMIT_PREFLIGHT_CHANGED,
                message=f"Legacy execution rejected stage: {exc.code}.",
                stage=stage,
            )

        submitted_attempt = PlanExecutionAttemptV1.model_validate(
            attempt.model_copy(
                update={
                    "state": PlanExecutionAttemptState.SUBMITTED,
                    "submitted_at": completed.submitted_at or now,
                    "idempotent_replay": replay,
                }
            ).model_dump(mode="python")
        )
        updated_stage = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                    "attempts": (*stage.attempts[:-1], submitted_attempt),
                    "last_submission_moscow_date": _moscow_date(now),
                }
            ).model_dump(mode="python")
        )
        updated = _replace_stage(
            session,
            updated_stage,
            state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
        )
        committed = self._commit(session, updated)
        return self._result(
            action=PlanExecutionAdvanceAction.STAGE_SUBMITTED,
            session=committed,
            stage_id=stage.stage_id,
            proposal_id=completed.proposal_id,
            message="Exactly one legacy LIMIT submit reserved; broker reconciliation is required.",
        )

    def _reconcile_broker(
        self,
        *,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        if not stage.attempts or not stage.attempts[-1].proposal_id:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
                message="Broker-reconciliation stage has no proposal identity.",
                stage=stage,
            )
        attempt = stage.attempts[-1]
        try:
            proposal = self._single_order.reconcile_proposal(attempt.proposal_id)
            snapshot = broker_snapshot_from_proposal(proposal)
        except RealTradingApiFailure as exc:
            return self._result(
                action=PlanExecutionAdvanceAction.REPLAY,
                session=session,
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
                message=f"Broker state is not yet reconcilable ({exc.code}); no resubmit occurred.",
            )
        except PlanExecutionBrokerStateError as exc:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.BROKER_RECONCILIATION_INCOMPLETE,
                message=str(exc),
                stage=stage,
            )

        if snapshot.status in {
            BrokerExecutionStatus.NEW,
            BrokerExecutionStatus.PARTIALLY_FILLED,
        }:
            active_attempt = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": PlanExecutionAttemptState.ACTIVE,
                        "broker_status": snapshot.status,
                        "lots_executed": snapshot.lots_executed,
                        "total_order_amount_rub": snapshot.total_order_amount_rub,
                        "executed_commission_rub": snapshot.executed_commission_rub,
                        "broker_response_sha256": snapshot.response_sha256,
                    }
                ).model_dump(mode="python")
            )
            updated_stage = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={"attempts": (*stage.attempts[:-1], active_attempt)}
                ).model_dump(mode="python")
            )
            updated = _replace_stage(
                session,
                updated_stage,
                state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
            )
            committed = self._commit(session, updated)
            return self._result(
                action=PlanExecutionAdvanceAction.BROKER_ACTIVE,
                session=committed,
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
                broker_snapshot=snapshot,
                message="Broker order remains active/partially filled; no remainder resubmit is allowed.",
            )

        if snapshot.status in {
            BrokerExecutionStatus.REJECTED,
            BrokerExecutionStatus.UNSPECIFIED,
        }:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.BROKER_REJECTED,
                message=f"Broker terminal status {snapshot.status.value} halts remaining plan legs.",
                stage=stage,
            )

        prior_terminal = sum(
            row.lots_executed
            for row in stage.attempts[:-1]
            if row.state is PlanExecutionAttemptState.TERMINAL
        )
        new_total_terminal = prior_terminal + snapshot.lots_executed
        if new_total_terminal > stage.planned_lots:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.BROKER_FILL_OVERFLOW,
                message="Broker fills exceed immutable stage quantity.",
                stage=stage,
            )

        terminal_attempt = PlanExecutionAttemptV1.model_validate(
            attempt.model_copy(
                update={
                    "state": PlanExecutionAttemptState.TERMINAL,
                    "reconciled_at": now,
                    "broker_status": snapshot.status,
                    "lots_executed": snapshot.lots_executed,
                    "total_order_amount_rub": snapshot.total_order_amount_rub,
                    "executed_commission_rub": snapshot.executed_commission_rub,
                    "broker_response_sha256": snapshot.response_sha256,
                }
            ).model_dump(mode="python")
        )
        updated_stage = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.BROKER_TERMINAL,
                    "broker_terminal_lots": new_total_terminal,
                    "attempts": (*stage.attempts[:-1], terminal_attempt),
                }
            ).model_dump(mode="python")
        )
        signed_cash = (
            -snapshot.total_order_amount_rub
            if stage.side is PlanExecutionSide.BUY
            else snapshot.total_order_amount_rub
        )
        updated = _replace_stage(
            session,
            updated_stage,
            state=PlanExecutionSessionState.AWAITING_PORTFOLIO_RECONCILIATION,
            confirmed_cash_delta_rub=session.confirmed_cash_delta_rub + signed_cash,
            estimated_tax_allowance_rub=(
                session.estimated_tax_allowance_rub
                + _tax_allowance_for_fills(
                    plan=plan,
                    stage=stage,
                    filled_lots=snapshot.lots_executed,
                )
            ),
        )
        committed = self._commit(session, updated)
        return self._result(
            action=PlanExecutionAdvanceAction.BROKER_TERMINAL,
            session=committed,
            stage_id=stage.stage_id,
            proposal_id=attempt.proposal_id,
            broker_snapshot=snapshot,
            message="Broker terminal state recorded; independent portfolio reconciliation is required.",
        )

    def _reconcile_portfolio(
        self,
        *,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        state = self._current_state(plan, now)
        matched, code, message = _progress_matches(
            plan=plan,
            session=session,
            state=state,
            settings=self._settings,
            now=now,
        )
        if not matched:
            terminal_times = [
                row.reconciled_at
                for row in stage.attempts
                if row.state is PlanExecutionAttemptState.TERMINAL
                and row.reconciled_at is not None
            ]
            latest_terminal = max(terminal_times) if terminal_times else now
            if (
                code in {
                    PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                    PlanExecutionHaltCode.CASH_RECONCILIATION_MISMATCH,
                }
                and (now - latest_terminal).total_seconds()
                <= self._settings.max_portfolio_reconciliation_age_seconds
            ):
                return self._result(
                    action=PlanExecutionAdvanceAction.REPLAY,
                    session=session,
                    stage_id=stage.stage_id,
                    message="Waiting for read-only portfolio/cash state to reflect broker-terminal fill.",
                )
            return self._halt(
                session,
                code=code or PlanExecutionHaltCode.PORTFOLIO_RECONCILIATION_TIMEOUT,
                message=message or "Portfolio reconciliation failed.",
                stage=stage,
            )

        remaining = stage.remaining_lots
        if remaining == 0:
            next_state = PlanExecutionStageState.FILLED
            not_before = stage.not_before_moscow_date
        else:
            next_state = PlanExecutionStageState.PENDING
            not_before = max(
                stage.not_before_moscow_date,
                _moscow_date(now) + timedelta(days=1),
            )
        updated_stage = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": next_state,
                    "portfolio_reconciled_lots": stage.broker_terminal_lots,
                    "not_before_moscow_date": not_before,
                }
            ).model_dump(mode="python")
        )
        updated = _replace_stage(
            session,
            updated_stage,
            state=PlanExecutionSessionState.ACTIVE,
        )
        if all(
            candidate.stage_id == stage.stage_id
            or candidate.state is PlanExecutionStageState.FILLED
            for candidate in _all_stages(session)
        ) and next_state is PlanExecutionStageState.FILLED:
            updated = PlanExecutionSessionV1.model_validate(
                updated.model_copy(
                    update={"state": PlanExecutionSessionState.COMPLETED}
                ).model_dump(mode="python")
            )
        committed = self._commit(session, updated)
        action = (
            PlanExecutionAdvanceAction.COMPLETED
            if committed.state is PlanExecutionSessionState.COMPLETED
            else PlanExecutionAdvanceAction.PORTFOLIO_RECONCILED
        )
        return self._result(
            action=action,
            session=committed,
            stage_id=stage.stage_id,
            message=(
                "Plan execution completed and reconciled."
                if action is PlanExecutionAdvanceAction.COMPLETED
                else "Broker fill reconciled to read-only portfolio; next stage may proceed."
            ),
        )

    def advance_execution(
        self,
        *,
        execution_id: str,
        plan: PortfolioPlanV1,
        now: datetime | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        current = _aware_utc(now)
        plan = _canonical_plan(plan)
        session = self._journal.get(execution_id)
        if session.plan_sha256 != plan.plan_sha256:
            return self._halt(
                session,
                code=PlanExecutionHaltCode.PLAN_INVALID,
                message="Execution session no longer matches immutable plan.",
            )
        if session.state is PlanExecutionSessionState.COMPLETED:
            return self._result(
                action=PlanExecutionAdvanceAction.REPLAY,
                session=session,
                message="Plan execution already completed; replay performed no submit.",
            )
        if not session.owner_approved:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_OWNER_APPROVAL_REQUIRED",
                "Exact immutable plan approval is required before any stage preparation.",
            )
        if session.state is PlanExecutionSessionState.HALTED:
            if session.halt_code is not PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION:
                return self._result(
                    action=PlanExecutionAdvanceAction.HALTED,
                    session=session,
                    message=session.halt_message or "Plan execution is halted.",
                )
            ambiguous = next(
                (
                    stage
                    for stage in _all_stages(session)
                    if stage.attempts
                    and stage.attempts[-1].state is PlanExecutionAttemptState.UNKNOWN
                ),
                None,
            )
            if ambiguous is None:
                return self._result(
                    action=PlanExecutionAdvanceAction.HALTED,
                    session=session,
                    message="Ambiguous session has no recoverable request id; manual stop remains.",
                )
            recovered = _replace_session(
                session,
                state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                halt_code=None,
                halt_message=None,
            )
            committed = self._commit(session, recovered)
            return self._reconcile_broker(
                plan=plan,
                session=committed,
                stage=_stage_by_id(committed, ambiguous.stage_id),
                now=current,
            )

        stage = _next_stage(session)
        if stage is None:
            completed = _replace_session(
                session,
                state=PlanExecutionSessionState.COMPLETED,
            )
            committed = self._commit(session, completed)
            return self._result(
                action=PlanExecutionAdvanceAction.COMPLETED,
                session=committed,
                message="All immutable plan stages are completed.",
            )
        if stage.state is PlanExecutionStageState.PENDING:
            return self._prepare_stage(
                plan=plan,
                session=session,
                stage=stage,
                now=current,
            )
        if stage.state is PlanExecutionStageState.PREPARED:
            return self._submit_prepared_stage(
                plan=plan,
                session=session,
                stage=stage,
                now=current,
            )
        if stage.state is PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION:
            return self._reconcile_broker(
                plan=plan,
                session=session,
                stage=stage,
                now=current,
            )
        if stage.state is PlanExecutionStageState.BROKER_TERMINAL:
            return self._reconcile_portfolio(
                plan=plan,
                session=session,
                stage=stage,
                now=current,
            )
        if stage.state is PlanExecutionStageState.HALTED:
            return self._result(
                action=PlanExecutionAdvanceAction.HALTED,
                session=session,
                stage_id=stage.stage_id,
                message="Current immutable plan stage is halted.",
            )
        return self._result(
            action=PlanExecutionAdvanceAction.REPLAY,
            session=session,
            stage_id=stage.stage_id,
            message="Stage state does not require a new submit.",
        )

    def status(self, execution_id: str) -> PlanExecutionSessionV1:
        return self._journal.get(execution_id)
