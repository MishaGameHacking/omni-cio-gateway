from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import hashlib
import hmac
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
from .journal_v1 import PlanExecutionJournalConflict, PlanExecutionJournalV1


MOSCOW = ZoneInfo("Europe/Moscow")

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


def _floor_money_ratio(numerator: Decimal, denominator: Decimal) -> int:
    if denominator <= 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_RATIO_INVALID",
            "Stage monetary denominator must be positive.",
        )
    return int((numerator / denominator).to_integral_value(rounding=ROUND_FLOOR))


def _signed_lots(side: PlanExecutionSide, lots: int) -> int:
    return lots if side is PlanExecutionSide.BUY else -lots


def _side(action: PortfolioPlanAction) -> PlanExecutionSide:
    if action is PortfolioPlanAction.BUY:
        return PlanExecutionSide.BUY
    if action is PortfolioPlanAction.SELL:
        return PlanExecutionSide.SELL
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_NO_ACTION",
        "NO_ACTION plan has no real execution leg.",
    )


def _canonical_plan(plan: PortfolioPlanV1) -> PortfolioPlanV1:
    try:
        canonical = PortfolioPlanV1.model_validate(plan.model_dump(mode="python"))
    except (AttributeError, ValidationError) as exc:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PLAN_TAMPERED",
            "Immutable plan failed canonical validation.",
            halt_code=PlanExecutionHaltCode.PLAN_INVALID,
        ) from exc
    if canonical.plan_sha256 != portfolio_plan_sha256(canonical):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PLAN_HASH_MISMATCH",
            "Immutable plan hash does not match its payload.",
            halt_code=PlanExecutionHaltCode.PLAN_INVALID,
        )
    return canonical


def _actionable_legs(plan: PortfolioPlanV1):
    return tuple(row for row in plan.legs if row.optimizer_leg is not None)


def _baselines(plan: PortfolioPlanV1) -> dict[str, PlanMarketBaselineV1]:
    return {row.stable_key: row for row in plan.market_baselines}


def _positions(state: PlanExecutionCurrentStateV1) -> dict[str, int]:
    return {row.stable_key: row.lots for row in state.positions}


def _all_stages(session: PlanExecutionSessionV1) -> tuple[PlanExecutionStageV1, ...]:
    return tuple(
        stage
        for instrument in session.instrument_states
        for stage in instrument.stages
    )


def _next_stage(session: PlanExecutionSessionV1) -> PlanExecutionStageV1 | None:
    remaining = sorted(
        (
            row
            for row in _all_stages(session)
            if row.state is not PlanExecutionStageState.FILLED
        ),
        key=lambda row: (row.leg_sequence, row.stage_index, row.stage_id),
    )
    return remaining[0] if remaining else None


def _stage(session: PlanExecutionSessionV1, stage_id: str) -> PlanExecutionStageV1:
    for row in _all_stages(session):
        if row.stage_id == stage_id:
            return row
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_STAGE_NOT_FOUND",
        "Execution stage was not found.",
    )


def _instrument(
    session: PlanExecutionSessionV1,
    stable_key: str,
) -> PlanExecutionInstrumentStateV1:
    for row in session.instrument_states:
        if row.binding.stable_key == stable_key:
            return row
    raise SafePlanExecutionError(
        "PLAN_EXECUTION_INSTRUMENT_NOT_FOUND",
        "Execution instrument state was not found.",
    )


def _session_update(
    session: PlanExecutionSessionV1,
    **updates: object,
) -> PlanExecutionSessionV1:
    payload = session.model_copy(
        update={"revision": session.revision + 1, **updates}
    ).model_dump(mode="python")
    return PlanExecutionSessionV1.model_validate(payload)


def _stage_update(
    session: PlanExecutionSessionV1,
    updated_stage: PlanExecutionStageV1,
    **session_updates: object,
) -> PlanExecutionSessionV1:
    found = False
    instruments: list[PlanExecutionInstrumentStateV1] = []
    for instrument in session.instrument_states:
        stages: list[PlanExecutionStageV1] = []
        for stage in instrument.stages:
            if stage.stage_id == updated_stage.stage_id:
                stages.append(updated_stage)
                found = True
            else:
                stages.append(stage)
        instruments.append(
            PlanExecutionInstrumentStateV1.model_validate(
                instrument.model_copy(update={"stages": tuple(stages)}).model_dump(
                    mode="python"
                )
            )
        )
    if not found:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_STAGE_NOT_FOUND",
            "Cannot update an unknown execution stage.",
        )
    return _session_update(
        session,
        instrument_states=tuple(instruments),
        **session_updates,
    )


def _stage_sizes(quantity: int, stage_count: int) -> tuple[int, ...]:
    base, extra = divmod(quantity, stage_count)
    values = tuple(
        base + (1 if index < extra else 0)
        for index in range(stage_count)
    )
    if not values or min(values) <= 0 or sum(values) != quantity:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_STAGE_SIZING_INVALID",
            "Cannot build positive deterministic stage quantities.",
        )
    return values


def _binding_same(
    left: PlanExecutionInstrumentBindingV1,
    right: PlanExecutionInstrumentBindingV1,
) -> bool:
    return (
        left.stable_key == right.stable_key
        and left.instrument_uid == right.instrument_uid
        and left.ticker == right.ticker
        and left.isin == right.isin
        and left.instrument_type == right.instrument_type
        and left.lot_size == right.lot_size
        and left.source_sha256 == right.source_sha256
    )


def _drift_bps(current: Decimal, baseline: Decimal) -> Decimal:
    return abs(current - baseline) / baseline * Decimal("10000")


def _market_guard(
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
    if (
        binding.stable_key != baseline.stable_key
        or quote.stable_key != binding.stable_key
        or quote.instrument_uid != binding.instrument_uid
        or quote.lot_size != binding.lot_size
        or binding.lot_size != baseline.lot_size
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_INSTRUMENT_BINDING_MISMATCH",
            "Current broker identity/lot binding differs from immutable plan.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
        )
    if binding.instrument_type not in {"share", "etf"}:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_INSTRUMENT_TYPE_NOT_SUPPORTED",
            "WP12 execution stays on the proven share/ETF real-money surface.",
            halt_code=PlanExecutionHaltCode.INSTRUMENT_TYPE_NOT_SUPPORTED,
        )

    quote_age = (now - quote.as_of).total_seconds()
    if (
        quote_age > settings.quote_max_age_seconds
        or quote_age < -settings.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_QUOTE_STALE",
            "Fresh executable quote is required immediately before stage action.",
            halt_code=PlanExecutionHaltCode.EXECUTION_QUOTE_STALE,
        )

    tolerance = plan.drift_tolerance
    market_age = (now - observation.observed_at).total_seconds()
    if (
        market_age > tolerance.market_max_age_seconds
        or market_age < -tolerance.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_MARKET_EVIDENCE_STALE",
            "Plan market evidence is stale or future-dated.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    friction_age = (now - observation.friction_as_of).total_seconds()
    if (
        friction_age > tolerance.friction_max_age_seconds
        or friction_age < -tolerance.future_tolerance_seconds
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_FRICTION_EVIDENCE_STALE",
            "Plan friction evidence is stale or future-dated.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if (
        _drift_bps(
            observation.clean_unit_price_base,
            baseline.clean_unit_price_base,
        )
        > tolerance.max_clean_price_drift_bps
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_CLEAN_PRICE_DRIFT",
            "Clean price moved beyond immutable plan tolerance.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if baseline.accrued_interest_per_lot_base is not None:
        current_aci = observation.accrued_interest_per_lot_base
        if current_aci is None:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ACCRUED_INTEREST_MISSING",
                "Required accrued-interest evidence is missing.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
        clean_lot = baseline.clean_unit_price_base * Decimal(baseline.lot_size)
        if (
            abs(current_aci - baseline.accrued_interest_per_lot_base)
            / clean_lot
            * Decimal("10000")
            > tolerance.max_accrued_interest_drift_bps
        ):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ACCRUED_INTEREST_DRIFT",
                "Accrued interest moved beyond immutable plan tolerance.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )
    if (
        observation.spread_bps - baseline.spread_bps
        > tolerance.max_spread_widening_bps
    ):
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
            "Liquidity capacity fell below immutable plan tolerance.",
            halt_code=PlanExecutionHaltCode.EXECUTION_LIQUIDITY_DROPPED,
        )
    if (
        observation.friction_source_sha256s != baseline.friction_source_sha256s
        or observation.commission_bps != baseline.commission_bps
        or observation.estimated_sell_tax_bps != baseline.estimated_sell_tax_bps
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_FRICTION_CHANGED",
            "Commission/tax evidence changed after plan creation.",
            halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
        )
    if side is PlanExecutionSide.BUY and observation.account_eligible is not True:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_BUY_ELIGIBILITY_CHANGED",
            "BUY eligibility changed after plan creation.",
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
        if (
            fx_age > tolerance.fx_max_age_seconds
            or fx_age < -tolerance.future_tolerance_seconds
            or _drift_bps(observation.fx_rate_to_base, baseline.fx_rate_to_base)
            > tolerance.max_fx_drift_bps
        ):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_FX_DRIFT",
                "FX evidence is stale or outside immutable plan tolerance.",
                halt_code=PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
            )

    limit_price = quote.limit_price(side)
    if quote.min_price_increment <= 0 or limit_price % quote.min_price_increment != 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_PRICE_STEP_MISMATCH",
            "Server-selected LIMIT price is not on the instrument price step.",
            halt_code=PlanExecutionHaltCode.EXECUTION_PRICE_STEP_MISMATCH,
        )
    if (
        _drift_bps(limit_price, observation.clean_unit_price_base)
        > settings.max_execution_price_change_bps
    ):
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_BOOK_PRICE_CHANGED",
            "Executable bid/ask moved too far from current clean price.",
            halt_code=PlanExecutionHaltCode.EXECUTION_PRICE_CHANGED,
        )
    return limit_price


def _expected_positions(
    plan: PortfolioPlanV1,
    session: PlanExecutionSessionV1,
) -> dict[str, int]:
    result = {row.stable_key: row.current_lots for row in plan.targets}
    for stage in _all_stages(session):
        result[stage.stable_key] = result.get(stage.stable_key, 0) + _signed_lots(
            stage.side,
            stage.broker_terminal_lots,
        )
    return result


def _progress_match(
    *,
    plan: PortfolioPlanV1,
    session: PlanExecutionSessionV1,
    state: PlanExecutionCurrentStateV1,
    settings: PlanExecutionSettingsV1,
    now: datetime,
) -> tuple[bool, PlanExecutionHaltCode | None, str | None]:
    age = (now - state.observed_at).total_seconds()
    if age < 0 or age > settings.max_portfolio_reconciliation_age_seconds:
        return (
            False,
            PlanExecutionHaltCode.PORTFOLIO_RECONCILIATION_TIMEOUT,
            "Read-only portfolio state is stale or future-dated.",
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
    observed = _positions(state)
    normalized = {key: observed.get(key, 0) for key in expected}
    unexpected = {
        key: lots for key, lots in observed.items() if key not in expected and lots
    }
    if normalized != expected or unexpected:
        return (
            False,
            PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            "Portfolio lots do not match broker-confirmed plan progress.",
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


def _tax_allowance(
    plan: PortfolioPlanV1,
    stage: PlanExecutionStageV1,
    lots: int,
) -> Decimal:
    if stage.side is not PlanExecutionSide.SELL or lots <= 0:
        return Decimal("0")
    leg = next(
        row.optimizer_leg
        for row in plan.legs
        if row.optimizer_leg is not None
        and row.optimizer_leg.stable_key == stage.stable_key
    )
    assert leg is not None
    return leg.estimated_tax_base * Decimal(lots) / Decimal(leg.quantity_lots)


def _stage_count(plan_leg, policy: RealTradingPolicyV1) -> int:
    per_lot = (
        plan_leg.settlement_notional_base
        + plan_leg.commission_base
        + plan_leg.estimated_tax_base
    ) / Decimal(plan_leg.quantity_lots)
    max_lots = _floor_money_ratio(policy.max_order_rub, per_lot)
    if max_lots <= 0:
        raise SafePlanExecutionError(
            "PLAN_EXECUTION_ORDER_CAP_TOO_SMALL",
            "One immutable plan lot exceeds the existing real-order cap.",
            halt_code=PlanExecutionHaltCode.PREPARE_REJECTED,
        )
    return max(plan_leg.required_execution_days, _ceil_ratio(plan_leg.quantity_lots, max_lots))


class SafePlanExecutionServiceV1:
    """Fail-closed plan orchestrator over the accepted v8.6.1 order primitive."""

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
                "Real plan execution requires a durable session journal.",
            )
        self._single_order = single_order
        self._real_policy = real_policy
        self._journal = journal
        self._binding_provider = instrument_binding_provider
        self._state_provider = current_state_provider
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
                "Execution session changed concurrently.",
                halt_code=PlanExecutionHaltCode.JOURNAL_CONFLICT,
            ) from exc

    def _result(
        self,
        action: PlanExecutionAdvanceAction,
        session: PlanExecutionSessionV1,
        message: str,
        *,
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
        code: PlanExecutionHaltCode,
        message: str,
        *,
        stage: PlanExecutionStageV1 | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        if stage is None:
            updated = _session_update(
                session,
                state=PlanExecutionSessionState.HALTED,
                halt_code=code,
                halt_message=message,
            )
        else:
            halted = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={"state": PlanExecutionStageState.HALTED}
                ).model_dump(mode="python")
            )
            updated = _stage_update(
                session,
                halted,
                state=PlanExecutionSessionState.HALTED,
                halt_code=code,
                halt_message=message,
            )
        committed = self._commit(session, updated)
        return self._result(
            PlanExecutionAdvanceAction.HALTED,
            committed,
            message,
            stage_id=stage.stage_id if stage else None,
        )

    def _state(self, plan: PortfolioPlanV1, now: datetime) -> PlanExecutionCurrentStateV1:
        try:
            supplied = self._state_provider(plan, now)
            return PlanExecutionCurrentStateV1.model_validate(
                supplied.model_dump(mode="python")
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_CURRENT_STATE_UNAVAILABLE",
                "Trusted read-only portfolio/risk state is unavailable.",
                halt_code=PlanExecutionHaltCode.CURRENT_RISK_NOT_READY,
            ) from exc

    def _binding(self, stable_key: str, now: datetime) -> PlanExecutionInstrumentBindingV1:
        try:
            supplied = self._binding_provider(stable_key, now)
            binding = PlanExecutionInstrumentBindingV1.model_validate(
                supplied.model_dump(mode="python")
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INSTRUMENT_BINDING_MISSING",
                "Trusted instrument binding is unavailable.",
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
        baseline: PlanMarketBaselineV1,
        binding: PlanExecutionInstrumentBindingV1,
        now: datetime,
    ) -> PlanExecutionLegEvidenceV1:
        try:
            supplied = self._evidence_provider(baseline, binding, now)
            return PlanExecutionLegEvidenceV1.model_validate(
                supplied.model_dump(mode="python")
            )
        except Exception as exc:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_EVIDENCE_MISSING",
                "Trusted market execution evidence is unavailable.",
                halt_code=PlanExecutionHaltCode.EXECUTION_EVIDENCE_MISSING,
            ) from exc

    def _initial_review(
        self,
        plan: PortfolioPlanV1,
        state: PlanExecutionCurrentStateV1,
        bindings: dict[str, PlanExecutionInstrumentBindingV1],
        now: datetime,
    ):
        evidence: list[PlanExecutionLegEvidenceV1] = []
        for baseline in plan.market_baselines:
            binding = bindings[baseline.stable_key]
            row = self._evidence(baseline, binding, now)
            plan_leg = next(
                item for item in plan.legs
                if item.optimizer_leg is not None
                and item.optimizer_leg.stable_key == baseline.stable_key
            )
            _market_guard(
                baseline=baseline,
                binding=binding,
                evidence=row,
                side=_side(plan_leg.action),
                plan=plan,
                settings=self._settings,
                now=now,
            )
            evidence.append(row)
        return review_portfolio_plan(
            plan=plan,
            review_input=PortfolioPlanReviewInputV1(
                reviewed_at=now,
                portfolio_snapshot_sha256=state.portfolio_snapshot_sha256,
                policy_reference=state.policy_reference,
                current_risk_assessment_sha256=state.risk_assessment_sha256,
                strategy_selection_sha256=state.strategy_selection_sha256,
                optimizer_sha256=state.optimizer_sha256,
                target_risk_assessment_sha256=state.target_risk_assessment_sha256,
                market_observations=tuple(row.observation for row in evidence),
            ),
        )

    def prepare_plan(
        self,
        *,
        plan: PortfolioPlanV1,
        now: datetime | None = None,
    ) -> PlanExecutionSessionV1:
        current = _aware_utc(now)
        plan = _canonical_plan(plan)
        if not plan.approval_required or not _actionable_legs(plan):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_NO_ACTION",
                "NO_ACTION plan does not create a real execution session.",
            )
        if current >= plan.expires_at:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_PLAN_EXPIRED",
                "Plan expired before execution preparation.",
                halt_code=PlanExecutionHaltCode.PLAN_EXPIRED,
            )

        state = self._state(plan, current)
        expected = {row.stable_key: row.current_lots for row in plan.targets}
        observed = _positions(state)
        normalized = {key: observed.get(key, 0) for key in expected}
        unexpected = {
            key: lots for key, lots in observed.items() if key not in expected and lots
        }
        if normalized != expected or unexpected:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_PORTFOLIO_MISMATCH",
                "Current positions differ from immutable plan start state.",
                halt_code=PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            )
        if (
            abs(state.cash_base - plan.current_cash_base)
            > self._settings.cash_reconciliation_tolerance_rub
        ):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_CASH_MISMATCH",
                "Current cash differs from immutable plan start state.",
                halt_code=PlanExecutionHaltCode.CASH_RECONCILIATION_MISMATCH,
            )
        if not state.risk_decision_ready or not state.risk_policy_compliant:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_RISK_NOT_READY",
                "Current risk state is not safe for execution.",
                halt_code=(
                    PlanExecutionHaltCode.CURRENT_RISK_POLICY_BREACH
                    if not state.risk_policy_compliant
                    else PlanExecutionHaltCode.CURRENT_RISK_NOT_READY
                ),
            )

        bindings: dict[str, PlanExecutionInstrumentBindingV1] = {}
        for plan_leg in _actionable_legs(plan):
            leg = plan_leg.optimizer_leg
            assert leg is not None
            binding = self._binding(leg.stable_key, current)
            if binding.lot_size != leg.lot_size:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_LOT_BINDING_MISMATCH",
                    "Current lot size differs from immutable plan leg.",
                    halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
                )
            if (
                binding.instrument_type not in {"share", "etf"}
                or binding.instrument_type not in self._real_policy.allowed_instrument_types
            ):
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_REAL_POLICY_TYPE_BLOCKED",
                    "Instrument is outside the proven v8.6.1 real-money surface.",
                    halt_code=PlanExecutionHaltCode.INSTRUMENT_TYPE_NOT_SUPPORTED,
                )
            bindings[leg.stable_key] = binding

        review = self._initial_review(plan, state, bindings, current)
        if not review.plan_valid or review.expected_owner_approval_phrase is None:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INITIAL_REVIEW_INVALID",
                "Immutable plan failed final pre-execution review.",
                halt_code=PlanExecutionHaltCode.PLAN_INVALID,
            )

        prepared_day = _moscow_date(current)
        instruments: list[PlanExecutionInstrumentStateV1] = []
        for plan_leg in _actionable_legs(plan):
            leg = plan_leg.optimizer_leg
            assert leg is not None
            count = _stage_count(leg, self._real_policy)
            sizes = _stage_sizes(leg.quantity_lots, count)
            stages = tuple(
                PlanExecutionStageV1(
                    stage_id=_sha(
                        "plan-execution-stage-v1",
                        plan.plan_sha256,
                        plan_leg.sequence,
                        index,
                        leg.stable_key,
                    ),
                    leg_sequence=plan_leg.sequence,
                    stable_key=leg.stable_key,
                    side=_side(plan_leg.action),
                    stage_index=index,
                    stage_count=count,
                    planned_lots=size,
                    not_before_moscow_date=prepared_day + timedelta(days=index - 1),
                )
                for index, size in enumerate(sizes, start=1)
            )
            instruments.append(
                PlanExecutionInstrumentStateV1(
                    binding=bindings[leg.stable_key],
                    stages=stages,
                )
            )

        session = PlanExecutionSessionV1(
            execution_id=_sha("plan-execution-v1", plan.plan_sha256),
            plan_sha256=plan.plan_sha256,
            initial_review_sha256=review.review_sha256,
            prepared_at=current,
            last_reviewed_at=current,
            last_review_sha256=review.review_sha256,
            state=PlanExecutionSessionState.PREPARED,
            instrument_states=tuple(instruments),
        )
        try:
            return self._journal.put(session)
        except PlanExecutionJournalConflict as exc:
            existing = self._journal.get(session.execution_id)
            if existing.plan_sha256 == plan.plan_sha256:
                return existing
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_ID_CONFLICT",
                "Execution id already belongs to another payload.",
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
                PlanExecutionHaltCode.PLAN_INVALID,
                "Execution session does not match immutable plan.",
            )
        if session.owner_approved:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                "Exact plan approval was already recorded; no submit repeated.",
            )
        if current >= plan.expires_at:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_EXPIRED,
                "Plan expired before owner approval.",
            )
        expected_phrase = plan.owner_approval_phrase or ""
        if not expected_phrase or not hmac.compare_digest(
            owner_approval_phrase,
            expected_phrase,
        ):
            return self._halt(
                session,
                PlanExecutionHaltCode.OWNER_APPROVAL_MISMATCH,
                "Exact owner approval phrase for this plan is required.",
            )

        state = self._state(plan, current)
        matched, code, message = _progress_match(
            plan=plan,
            session=session,
            state=state,
            settings=self._settings,
            now=current,
        )
        if not matched:
            return self._halt(
                session,
                code or PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                message or "Current state no longer matches plan start.",
            )
        bindings = {
            item.binding.stable_key: item.binding
            for item in session.instrument_states
        }
        review = self._initial_review(plan, state, bindings, current)
        if not review.plan_valid or review.expected_owner_approval_phrase != expected_phrase:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_INVALID,
                "Plan became invalid before owner approval.",
            )

        evidence_sha = _sha(
            "plan-owner-approval-v1",
            execution_id,
            plan.plan_sha256,
            owner_approval_phrase,
        )
        updated = _session_update(
            session,
            state=PlanExecutionSessionState.ACTIVE,
            last_reviewed_at=current,
            last_review_sha256=review.review_sha256,
            owner_approved=True,
            owner_approved_at=current,
            owner_approval_evidence_sha256=evidence_sha,
        )
        committed = self._commit(session, updated)
        return self._result(
            PlanExecutionAdvanceAction.APPROVED,
            committed,
            "Exact immutable plan approval recorded; no broker submit occurred.",
        )

    def _runtime_guard(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> tuple[PlanExecutionInstrumentBindingV1, Decimal]:
        state = self._state(plan, now)
        matched, code, message = _progress_match(
            plan=plan,
            session=session,
            state=state,
            settings=self._settings,
            now=now,
        )
        if not matched:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_PROGRESS_DRIFT",
                message or "Portfolio progress does not reconcile.",
                halt_code=code or PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
            )
        stored = _instrument(session, stage.stable_key).binding
        binding = self._binding(stage.stable_key, now)
        if not _binding_same(stored, binding):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_INSTRUMENT_BINDING_CHANGED",
                "Broker instrument identity changed after session preparation.",
                halt_code=PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
            )
        baseline = _baselines(plan)[stage.stable_key]
        evidence = self._evidence(baseline, binding, now)
        limit_price = _market_guard(
            baseline=baseline,
            binding=binding,
            evidence=evidence,
            side=stage.side,
            plan=plan,
            settings=self._settings,
            now=now,
        )
        return binding, limit_price

    def _prepare_stage(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        today = _moscow_date(now)
        if today < stage.not_before_moscow_date or stage.last_submission_moscow_date == today:
            return self._result(
                PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                session,
                "Stage is intentionally deferred; no same-day staged resubmit is allowed.",
                stage_id=stage.stage_id,
            )
        try:
            binding, limit_price = self._runtime_guard(plan, session, stage, now)
        except SafePlanExecutionError as exc:
            return self._halt(
                session,
                exc.halt_code or PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
                exc.message,
                stage=stage,
            )
        quantity = stage.remaining_lots
        if quantity <= 0:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_FILL_OVERFLOW,
                "Pending stage has no remaining lots.",
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
                    PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                    session,
                    "Existing v8.6.1 daily real-money cap deferred this stage.",
                    stage_id=stage.stage_id,
                )
            return self._halt(
                session,
                PlanExecutionHaltCode.PREPARE_REJECTED,
                f"Legacy real-trading preflight rejected stage: {exc.code}.",
                stage=stage,
            )
        if (
            proposal.instrument_uid != binding.instrument_uid
            or proposal.ticker != binding.ticker
            or proposal.isin != binding.isin
            or proposal.direction != stage.side.value
            or proposal.quantity_lots != quantity
            or proposal.limit_price != limit_price
        ):
            return self._halt(
                session,
                PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH,
                "Prepared legacy proposal differs from server-bound stage.",
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
        committed = self._commit(
            session,
            _stage_update(
                session,
                updated_stage,
                state=PlanExecutionSessionState.ACTIVE,
            ),
        )
        return self._result(
            PlanExecutionAdvanceAction.STAGE_PREPARED,
            committed,
            "Legacy immutable proposal prepared; no submit occurred.",
            stage_id=stage.stage_id,
            proposal_id=proposal.proposal_id,
        )

    def _submit_stage(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        if not stage.attempts:
            return self._halt(
                session,
                PlanExecutionHaltCode.JOURNAL_CONFLICT,
                "Prepared stage has no execution attempt.",
                stage=stage,
            )
        attempt = stage.attempts[-1]
        if attempt.state is not PlanExecutionAttemptState.PREPARED or not attempt.proposal_id:
            return self._halt(
                session,
                PlanExecutionHaltCode.JOURNAL_CONFLICT,
                "Prepared stage attempt is inconsistent.",
                stage=stage,
            )
        try:
            _, fresh_limit = self._runtime_guard(plan, session, stage, now)
        except SafePlanExecutionError as exc:
            return self._halt(
                session,
                exc.halt_code or PlanExecutionHaltCode.PLAN_MARKET_DRIFT,
                exc.message,
                stage=stage,
            )
        if attempt.limit_price != fresh_limit:
            failed = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": PlanExecutionAttemptState.FAILED,
                        "failure_code": "PLAN_EXECUTION_REPREPARE_PRICE_CHANGED",
                    }
                ).model_dump(mode="python")
            )
            pending = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={
                        "state": PlanExecutionStageState.PENDING,
                        "attempts": (*stage.attempts[:-1], failed),
                    }
                ).model_dump(mode="python")
            )
            committed = self._commit(session, _stage_update(session, pending))
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                committed,
                "Executable LIMIT price changed; stage was reset for fresh preparation.",
                stage_id=stage.stage_id,
            )

        proposal = self._single_order.get_proposal(attempt.proposal_id)
        if proposal.state in {"submitting", "unknown"}:
            return self._halt(
                session,
                PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION,
                "Underlying proposal is uncertain; do not resubmit.",
                stage=stage,
            )
        if proposal.state == "submitted":
            submitted = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": PlanExecutionAttemptState.SUBMITTED,
                        "submitted_at": proposal.submitted_at or now,
                        "idempotent_replay": True,
                    }
                ).model_dump(mode="python")
            )
            waiting = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={
                        "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                        "attempts": (*stage.attempts[:-1], submitted),
                        "last_submission_moscow_date": _moscow_date(now),
                    }
                ).model_dump(mode="python")
            )
            committed = self._commit(
                session,
                _stage_update(
                    session,
                    waiting,
                    state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                ),
            )
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                committed,
                "Underlying proposal was already submitted; no second submit occurred.",
                stage_id=stage.stage_id,
                proposal_id=proposal.proposal_id,
            )
        if proposal.state != "prepared":
            failed = PlanExecutionAttemptV1.model_validate(
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
            pending = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={
                        "state": PlanExecutionStageState.PENDING,
                        "attempts": (*stage.attempts[:-1], failed),
                    }
                ).model_dump(mode="python")
            )
            committed = self._commit(session, _stage_update(session, pending))
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                committed,
                "Underlying proposal is no longer prepared; fresh preparation is required.",
                stage_id=stage.stage_id,
            )
        try:
            completed, replay = self._single_order.execute_trade(
                proposal.proposal_id,
                proposal.confirmation_phrase,
                now=now,
            )
        except RealTradingApiFailure as exc:
            if exc.ambiguous_submission or exc.code == "REAL_ORDER_SUBMISSION_UNCERTAIN":
                unknown = PlanExecutionAttemptV1.model_validate(
                    attempt.model_copy(
                        update={
                            "state": PlanExecutionAttemptState.UNKNOWN,
                            "submitted_at": now,
                            "failure_code": exc.code,
                        }
                    ).model_dump(mode="python")
                )
                waiting = PlanExecutionStageV1.model_validate(
                    stage.model_copy(
                        update={
                            "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                            "attempts": (*stage.attempts[:-1], unknown),
                            "last_submission_moscow_date": _moscow_date(now),
                        }
                    ).model_dump(mode="python")
                )
                updated = _stage_update(
                    session,
                    waiting,
                    state=PlanExecutionSessionState.HALTED,
                    halt_code=PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION,
                    halt_message=(
                        "Submit result is ambiguous; all remaining legs are halted "
                        "until request-id reconciliation."
                    ),
                )
                committed = self._commit(session, updated)
                return self._result(
                    PlanExecutionAdvanceAction.HALTED,
                    committed,
                    "Ambiguous submit: do not resubmit this proposal.",
                    stage_id=stage.stage_id,
                    proposal_id=proposal.proposal_id,
                )
            if exc.code == "REAL_MARKET_REVALIDATION_REQUIRED":
                return self._result(
                    PlanExecutionAdvanceAction.REPLAY,
                    session,
                    "Legacy primitive requires a newer trusted market snapshot before submit.",
                    stage_id=stage.stage_id,
                    proposal_id=proposal.proposal_id,
                )
            if exc.code in {
                "REAL_CONFIRMATION_EXPIRED",
                "REAL_PREFLIGHT_CHANGED",
                "REAL_DAILY_CAP_EXCEEDED",
            }:
                failed = PlanExecutionAttemptV1.model_validate(
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
                pending = PlanExecutionStageV1.model_validate(
                    stage.model_copy(
                        update={
                            "state": PlanExecutionStageState.PENDING,
                            "attempts": (*stage.attempts[:-1], failed),
                        }
                    ).model_dump(mode="python")
                )
                committed = self._commit(session, _stage_update(session, pending))
                return self._result(
                    (
                        PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY
                        if exc.code == "REAL_DAILY_CAP_EXCEEDED"
                        else PlanExecutionAdvanceAction.REPLAY
                    ),
                    committed,
                    f"Legacy preflight changed ({exc.code}); no unsafe retry occurred.",
                    stage_id=stage.stage_id,
                )
            return self._halt(
                session,
                PlanExecutionHaltCode.SUBMIT_PREFLIGHT_CHANGED,
                f"Legacy execution rejected stage: {exc.code}.",
                stage=stage,
            )

        submitted = PlanExecutionAttemptV1.model_validate(
            attempt.model_copy(
                update={
                    "state": PlanExecutionAttemptState.SUBMITTED,
                    "submitted_at": completed.submitted_at or now,
                    "idempotent_replay": replay,
                }
            ).model_dump(mode="python")
        )
        waiting = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
                    "attempts": (*stage.attempts[:-1], submitted),
                    "last_submission_moscow_date": _moscow_date(now),
                }
            ).model_dump(mode="python")
        )
        committed = self._commit(
            session,
            _stage_update(
                session,
                waiting,
                state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
            ),
        )
        return self._result(
            PlanExecutionAdvanceAction.STAGE_SUBMITTED,
            committed,
            "Exactly one legacy LIMIT submit reserved; broker reconciliation is required.",
            stage_id=stage.stage_id,
            proposal_id=completed.proposal_id,
        )

    def _reconcile_broker(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        if not stage.attempts or not stage.attempts[-1].proposal_id:
            return self._halt(
                session,
                PlanExecutionHaltCode.JOURNAL_CONFLICT,
                "Broker-reconciliation stage has no proposal identity.",
                stage=stage,
            )
        attempt = stage.attempts[-1]
        assert attempt.proposal_id is not None
        try:
            proposal = self._single_order.reconcile_proposal(attempt.proposal_id)
            snapshot = broker_snapshot_from_proposal(proposal)
        except RealTradingApiFailure as exc:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                f"Broker state is not yet reconcilable ({exc.code}); no resubmit occurred.",
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
            )
        except PlanExecutionBrokerStateError as exc:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_RECONCILIATION_INCOMPLETE,
                str(exc),
                stage=stage,
            )

        if snapshot.status in {
            BrokerExecutionStatus.NEW,
            BrokerExecutionStatus.PARTIALLY_FILLED,
        }:
            active = PlanExecutionAttemptV1.model_validate(
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
                    update={"attempts": (*stage.attempts[:-1], active)}
                ).model_dump(mode="python")
            )
            committed = self._commit(
                session,
                _stage_update(
                    session,
                    updated_stage,
                    state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                ),
            )
            return self._result(
                PlanExecutionAdvanceAction.BROKER_ACTIVE,
                committed,
                "Broker order remains active/partially filled; remainder is not resubmitted.",
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
                broker_snapshot=snapshot,
            )

        if snapshot.status in {
            BrokerExecutionStatus.REJECTED,
            BrokerExecutionStatus.UNSPECIFIED,
        }:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_REJECTED,
                f"Broker status {snapshot.status.value} halted all remaining plan legs.",
                stage=stage,
            )

        prior_terminal = sum(
            row.lots_executed
            for row in stage.attempts[:-1]
            if row.state is PlanExecutionAttemptState.TERMINAL
        )
        terminal_lots = prior_terminal + snapshot.lots_executed
        if terminal_lots > stage.planned_lots:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_FILL_OVERFLOW,
                "Broker fills exceed immutable stage quantity.",
                stage=stage,
            )
        terminal = PlanExecutionAttemptV1.model_validate(
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
        broker_terminal = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.BROKER_TERMINAL,
                    "broker_terminal_lots": terminal_lots,
                    "attempts": (*stage.attempts[:-1], terminal),
                }
            ).model_dump(mode="python")
        )
        cash_delta = (
            -snapshot.total_order_amount_rub
            if stage.side is PlanExecutionSide.BUY
            else snapshot.total_order_amount_rub
        )
        updated = _stage_update(
            session,
            broker_terminal,
            state=PlanExecutionSessionState.AWAITING_PORTFOLIO_RECONCILIATION,
            confirmed_cash_delta_rub=session.confirmed_cash_delta_rub + cash_delta,
            estimated_tax_allowance_rub=(
                session.estimated_tax_allowance_rub
                + _tax_allowance(plan, stage, snapshot.lots_executed)
            ),
        )
        committed = self._commit(session, updated)
        return self._result(
            PlanExecutionAdvanceAction.BROKER_TERMINAL,
            committed,
            "Broker terminal state recorded; independent portfolio reconciliation is required.",
            stage_id=stage.stage_id,
            proposal_id=attempt.proposal_id,
            broker_snapshot=snapshot,
        )

    def _reconcile_portfolio(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        state = self._state(plan, now)
        matched, code, message = _progress_match(
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
            latest = max(terminal_times) if terminal_times else now
            if (
                code in {
                    PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                    PlanExecutionHaltCode.CASH_RECONCILIATION_MISMATCH,
                }
                and (now - latest).total_seconds()
                <= self._settings.max_portfolio_reconciliation_age_seconds
            ):
                return self._result(
                    PlanExecutionAdvanceAction.REPLAY,
                    session,
                    "Waiting for read-only portfolio/cash to reflect broker-terminal fill.",
                    stage_id=stage.stage_id,
                )
            return self._halt(
                session,
                code or PlanExecutionHaltCode.PORTFOLIO_RECONCILIATION_TIMEOUT,
                message or "Portfolio reconciliation failed.",
                stage=stage,
            )

        remaining = stage.remaining_lots
        filled = remaining == 0
        updated_stage = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": (
                        PlanExecutionStageState.FILLED
                        if filled
                        else PlanExecutionStageState.PENDING
                    ),
                    "portfolio_reconciled_lots": stage.broker_terminal_lots,
                    "not_before_moscow_date": (
                        stage.not_before_moscow_date
                        if filled
                        else _moscow_date(now) + timedelta(days=1)
                    ),
                }
            ).model_dump(mode="python")
        )
        updated = _stage_update(
            session,
            updated_stage,
            state=PlanExecutionSessionState.ACTIVE,
        )
        if filled and all(
            row.stage_id == stage.stage_id
            or row.state is PlanExecutionStageState.FILLED
            for row in _all_stages(session)
        ):
            updated = PlanExecutionSessionV1.model_validate(
                updated.model_copy(
                    update={"state": PlanExecutionSessionState.COMPLETED}
                ).model_dump(mode="python")
            )
        committed = self._commit(session, updated)
        if committed.state is PlanExecutionSessionState.COMPLETED:
            return self._result(
                PlanExecutionAdvanceAction.COMPLETED,
                committed,
                "Plan execution completed and independently reconciled.",
                stage_id=stage.stage_id,
            )
        return self._result(
            PlanExecutionAdvanceAction.PORTFOLIO_RECONCILED,
            committed,
            "Broker fill reconciled to read-only portfolio; next stage may proceed.",
            stage_id=stage.stage_id,
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
                PlanExecutionHaltCode.PLAN_INVALID,
                "Execution session no longer matches immutable plan.",
            )
        if session.state is PlanExecutionSessionState.COMPLETED:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                "Execution is already completed; replay performed no submit.",
            )
        if not session.owner_approved:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_OWNER_APPROVAL_REQUIRED",
                "Exact plan approval is required before stage preparation.",
            )
        if session.state is PlanExecutionSessionState.HALTED:
            if session.halt_code is not PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION:
                return self._result(
                    PlanExecutionAdvanceAction.HALTED,
                    session,
                    session.halt_message or "Execution is halted.",
                )
            ambiguous = next(
                (
                    row for row in _all_stages(session)
                    if row.attempts
                    and row.attempts[-1].state is PlanExecutionAttemptState.UNKNOWN
                ),
                None,
            )
            if ambiguous is None:
                return self._result(
                    PlanExecutionAdvanceAction.HALTED,
                    session,
                    "Ambiguous session has no recoverable request id.",
                )
            recovered = _session_update(
                session,
                state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                halt_code=None,
                halt_message=None,
            )
            committed = self._commit(session, recovered)
            return self._reconcile_broker(
                plan,
                committed,
                _stage(committed, ambiguous.stage_id),
                current,
            )

        current_stage = _next_stage(session)
        if current_stage is None:
            committed = self._commit(
                session,
                _session_update(session, state=PlanExecutionSessionState.COMPLETED),
            )
            return self._result(
                PlanExecutionAdvanceAction.COMPLETED,
                committed,
                "All immutable plan stages are complete.",
            )
        if current_stage.state is PlanExecutionStageState.PENDING:
            return self._prepare_stage(plan, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.PREPARED:
            return self._submit_stage(plan, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION:
            return self._reconcile_broker(plan, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.BROKER_TERMINAL:
            return self._reconcile_portfolio(plan, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.HALTED:
            return self._result(
                PlanExecutionAdvanceAction.HALTED,
                session,
                "Current immutable plan stage is halted.",
                stage_id=current_stage.stage_id,
            )
        return self._result(
            PlanExecutionAdvanceAction.REPLAY,
            session,
            "Stage state does not permit a new submit.",
            stage_id=current_stage.stage_id,
        )

    def status(self, execution_id: str) -> PlanExecutionSessionV1:
        return self._journal.get(execution_id)
