from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.investment_policy import (
    InvestmentObjective,
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
    RiskLevel,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    MetaStrategySettingsV1,
    StrategyCandidateBlockerCode,
    StrategyComparisonV1,
    StrategyComponentDirective,
    StrategyComponentKind,
    StrategyComponentV1,
    StrategyFrictionEvidenceV1,
    StrategyRegime,
    StrategyReviewAction,
    StrategyReviewCode,
    StrategyReviewConditionV1,
    StrategySelectionBlockerCode,
    meta_strategy_sha256,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_risk import (
    PortfolioRiskAssessmentV1,
    RiskSeverity,
    RiskVectorKind,
)
from omni_cio.policy import policy_fingerprint_sha256


class MetaStrategyError(ValueError):
    """Strategy inputs cannot be compared safely or deterministically."""


_REGIME_RANK = {
    StrategyRegime.CAPITAL_PRESERVATION: 0,
    StrategyRegime.DEFENSIVE_BALANCED: 1,
    StrategyRegime.BALANCED_CORE: 2,
    StrategyRegime.GROWTH_CORE: 3,
}

_RISK_LEVEL_RANK = {
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.HIGH: 3,
}

_OBJECTIVE_BASE_RANK = {
    InvestmentObjective.CAPITAL_PRESERVATION: 0,
    InvestmentObjective.PRESERVE_PURCHASING_POWER: 1,
    InvestmentObjective.INCOME: 1,
    InvestmentObjective.BALANCED_GROWTH_INCOME: 2,
    InvestmentObjective.REAL_CAPITAL_GROWTH: 3,
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise MetaStrategyError("STRATEGY_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique(target: list[object], value: object) -> None:
    if value not in target:
        target.append(value)


def _instrument_allowed(
    policy: InvestmentPolicyStatementV1,
    instrument_type: InstrumentType,
) -> bool:
    if instrument_type in policy.prohibited_instrument_types:
        return False
    if policy.allowed_instrument_types:
        return instrument_type in policy.allowed_instrument_types
    return True


def _diversified_core_available(policy: InvestmentPolicyStatementV1) -> bool:
    return _instrument_allowed(policy, InstrumentType.ETF) or _instrument_allowed(
        policy,
        InstrumentType.SHARE,
    )


def _quality_debt_available(policy: InvestmentPolicyStatementV1) -> bool:
    return _instrument_allowed(policy, InstrumentType.BOND) or _instrument_allowed(
        policy,
        InstrumentType.ETF,
    )


def _policy_risk_cap(policy: InvestmentPolicyStatementV1) -> int:
    levels = [policy.risk_willingness, policy.risk_capacity]
    if any(level is None for level in levels):
        return 0
    return min(_RISK_LEVEL_RANK[level] for level in levels if level is not None)


def _horizon_cap(policy: InvestmentPolicyStatementV1) -> int:
    horizon = policy.time_horizon_years
    if horizon is None:
        return 0
    if horizon < Decimal("3"):
        return 1
    if horizon < Decimal("5"):
        return 2
    return 3


def _vectors(risk: PortfolioRiskAssessmentV1) -> dict[RiskVectorKind, RiskSeverity]:
    return {row.kind: row.severity for row in risk.after.vectors}


def _risk_state_cap(risk: PortfolioRiskAssessmentV1) -> int:
    vectors = _vectors(risk)
    hard_kinds = {
        row.kind for row in risk.after.vectors if row.hard_breach
    }
    if hard_kinds & {
        RiskVectorKind.PERMANENT_LOSS,
        RiskVectorKind.MARKET,
        RiskVectorKind.LIQUIDITY,
        RiskVectorKind.CREDIT,
    }:
        return 1
    if hard_kinds:
        return 2
    if any(
        severity in {RiskSeverity.HIGH, RiskSeverity.UNKNOWN}
        for severity in vectors.values()
    ):
        return 2
    return 3


def _objective_ideal_rank(
    policy: InvestmentPolicyStatementV1,
    *,
    max_rank: int,
) -> int:
    if policy.objective is None:
        return 0
    return min(_OBJECTIVE_BASE_RANK[policy.objective], max_rank)


def _objective_fit(regime_rank: int, ideal_rank: int) -> int:
    return max(0, 4 - abs(regime_rank - ideal_rank) * 2)


def _liquidity_fit(severity: RiskSeverity, regime_rank: int) -> int:
    table = {
        RiskSeverity.LOW: (4, 4, 4, 4),
        RiskSeverity.MODERATE: (4, 4, 3, 2),
        RiskSeverity.HIGH: (4, 3, 2, 1),
        RiskSeverity.UNKNOWN: (4, 3, 1, 0),
        RiskSeverity.BREACH: (4, 3, 1, 0),
    }
    return table[severity][regime_rank]


def _no_action_fit(risk: PortfolioRiskAssessmentV1) -> int:
    if not risk.after.policy_compliant:
        return 0
    severities = {row.severity for row in risk.after.vectors}
    if RiskSeverity.UNKNOWN in severities or RiskSeverity.HIGH in severities:
        return 1
    if RiskSeverity.MODERATE in severities:
        return 2
    return 3


def _candidate_blockers(
    regime: StrategyRegime,
    *,
    policy: InvestmentPolicyStatementV1,
    risk: PortfolioRiskAssessmentV1,
    max_rank: int,
    horizon_cap: int,
    liquidity_severity: RiskSeverity,
) -> tuple[StrategyCandidateBlockerCode, ...]:
    blockers: list[StrategyCandidateBlockerCode] = []
    if regime is StrategyRegime.NO_ACTION:
        if not risk.after.policy_compliant:
            blockers.append(StrategyCandidateBlockerCode.CURRENT_HARD_BREACH)
        return tuple(blockers)

    rank = _REGIME_RANK[regime]
    if rank > max_rank:
        blockers.append(StrategyCandidateBlockerCode.RISK_BUDGET_EXCEEDED)
    if rank > horizon_cap:
        blockers.append(StrategyCandidateBlockerCode.HORIZON_TOO_SHORT)

    if regime in {
        StrategyRegime.DEFENSIVE_BALANCED,
        StrategyRegime.BALANCED_CORE,
        StrategyRegime.GROWTH_CORE,
    } and not _diversified_core_available(policy):
        blockers.append(StrategyCandidateBlockerCode.DIVERSIFIED_CORE_UNAVAILABLE)

    if (
        policy.objective is InvestmentObjective.INCOME
        and regime
        in {
            StrategyRegime.CAPITAL_PRESERVATION,
            StrategyRegime.DEFENSIVE_BALANCED,
        }
        and not _quality_debt_available(policy)
    ):
        blockers.append(StrategyCandidateBlockerCode.QUALITY_DEBT_UNAVAILABLE)

    if regime is StrategyRegime.GROWTH_CORE and liquidity_severity in {
        RiskSeverity.HIGH,
        RiskSeverity.UNKNOWN,
        RiskSeverity.BREACH,
    }:
        blockers.append(StrategyCandidateBlockerCode.LIQUIDITY_TOO_WEAK)
    if (
        regime is StrategyRegime.BALANCED_CORE
        and liquidity_severity is RiskSeverity.BREACH
    ):
        blockers.append(StrategyCandidateBlockerCode.LIQUIDITY_TOO_WEAK)

    return tuple(sorted(set(blockers), key=str))


def _friction_map(
    evidence: Iterable[StrategyFrictionEvidenceV1],
) -> dict[StrategyRegime, StrategyFrictionEvidenceV1]:
    result: dict[StrategyRegime, StrategyFrictionEvidenceV1] = {}
    for row in evidence:
        if row.regime in result:
            raise MetaStrategyError("STRATEGY_FRICTION_REGIMES_MUST_BE_UNIQUE")
        result[row.regime] = row
    return result


def _comparison_sort_key(row: StrategyComparisonV1) -> tuple[object, ...]:
    return (
        0 if row.feasible else 1,
        -row.risk_fit,
        -row.objective_fit,
        -row.liquidity_fit,
        Decimal("99") if row.friction_weight is None else row.friction_weight,
        0 if row.regime is StrategyRegime.NO_ACTION else 1,
        row.regime.value,
    )


def _component(
    kind: StrategyComponentKind,
    directive: StrategyComponentDirective,
    rationale: str,
) -> StrategyComponentV1:
    return StrategyComponentV1(
        kind=kind,
        directive=directive,
        rationale_code=rationale,
    )


def _components(
    regime: StrategyRegime,
    *,
    policy: InvestmentPolicyStatementV1,
    risk: PortfolioRiskAssessmentV1,
) -> tuple[StrategyComponentV1, ...]:
    if regime is StrategyRegime.NO_ACTION:
        return tuple(
            _component(
                kind,
                StrategyComponentDirective.FORBIDDEN,
                "NO_ACTION_NO_NEW_ALLOCATION",
            )
            for kind in StrategyComponentKind
        )

    debt_available = _quality_debt_available(policy)
    core_available = _diversified_core_available(policy)
    rows = [
        _component(
            StrategyComponentKind.LIQUIDITY_RESERVE,
            StrategyComponentDirective.REQUIRED,
            "OWNER_LIQUIDITY_POLICY_PRESERVED",
        )
    ]

    if debt_available and regime in {
        StrategyRegime.CAPITAL_PRESERVATION,
        StrategyRegime.DEFENSIVE_BALANCED,
    }:
        rows.append(
            _component(
                StrategyComponentKind.QUALITY_DEBT,
                StrategyComponentDirective.REQUIRED,
                "QUALITY_DEBT_DEFENSIVE_ANCHOR",
            )
        )
    elif debt_available:
        rows.append(
            _component(
                StrategyComponentKind.QUALITY_DEBT,
                StrategyComponentDirective.ALLOWED,
                "QUALITY_DEBT_POLICY_ALLOWED",
            )
        )
    else:
        rows.append(
            _component(
                StrategyComponentKind.QUALITY_DEBT,
                StrategyComponentDirective.FORBIDDEN,
                "QUALITY_DEBT_NOT_POLICY_AVAILABLE",
            )
        )

    if core_available and regime in {
        StrategyRegime.DEFENSIVE_BALANCED,
        StrategyRegime.BALANCED_CORE,
        StrategyRegime.GROWTH_CORE,
    }:
        rows.append(
            _component(
                StrategyComponentKind.DIVERSIFIED_CORE,
                StrategyComponentDirective.REQUIRED,
                "DIVERSIFIED_CORE_REQUIRED",
            )
        )
    elif core_available:
        rows.append(
            _component(
                StrategyComponentKind.DIVERSIFIED_CORE,
                StrategyComponentDirective.ALLOWED,
                "DIVERSIFIED_CORE_POLICY_ALLOWED",
            )
        )
    else:
        rows.append(
            _component(
                StrategyComponentKind.DIVERSIFIED_CORE,
                StrategyComponentDirective.FORBIDDEN,
                "DIVERSIFIED_CORE_NOT_POLICY_AVAILABLE",
            )
        )

    active_allowed = (
        regime is StrategyRegime.GROWTH_CORE
        and policy.risk_willingness is RiskLevel.HIGH
        and policy.risk_capacity is RiskLevel.HIGH
        and risk.after.policy_compliant
    )
    rows.append(
        _component(
            StrategyComponentKind.BOUNDED_ACTIVE,
            (
                StrategyComponentDirective.ALLOWED
                if active_allowed
                else StrategyComponentDirective.FORBIDDEN
            ),
            (
                "BOUNDED_ACTIVE_HIGH_RISK_BUDGET_ONLY"
                if active_allowed
                else "BOUNDED_ACTIVE_NOT_JUSTIFIED"
            ),
        )
    )
    return tuple(rows)


def _review_conditions() -> tuple[StrategyReviewConditionV1, ...]:
    return (
        StrategyReviewConditionV1(
            code=StrategyReviewCode.POLICY_CHANGED,
            action=StrategyReviewAction.CANCEL,
        ),
        StrategyReviewConditionV1(
            code=StrategyReviewCode.PORTFOLIO_CHANGED,
            action=StrategyReviewAction.REVIEW,
        ),
        StrategyReviewConditionV1(
            code=StrategyReviewCode.RISK_STATE_CHANGED,
            action=StrategyReviewAction.REVIEW,
        ),
        StrategyReviewConditionV1(
            code=StrategyReviewCode.HARD_BREACH_APPEARED,
            action=StrategyReviewAction.CANCEL,
        ),
        StrategyReviewConditionV1(
            code=StrategyReviewCode.FRICTION_EVIDENCE_STALE,
            action=StrategyReviewAction.REVIEW,
        ),
        StrategyReviewConditionV1(
            code=StrategyReviewCode.TAX_CONTEXT_CHANGED,
            action=StrategyReviewAction.REVIEW,
        ),
    )


def select_meta_strategy(
    *,
    portfolio_snapshot_sha256: str,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    risk: PortfolioRiskAssessmentV1,
    friction_evidence: Iterable[StrategyFrictionEvidenceV1] = (),
    settings: MetaStrategySettingsV1 | None = None,
    selected_at: datetime | None = None,
) -> MetaStrategySelectionV1:
    """Select a bounded portfolio regime without market prediction or broker writes."""
    evaluation_time = _aware_utc(selected_at)
    settings_value = settings or MetaStrategySettingsV1()
    friction = _friction_map(friction_evidence)
    global_blockers: list[StrategySelectionBlockerCode] = []

    if not policy_assessment.ready_for_personal_sizing:
        global_blockers.append(StrategySelectionBlockerCode.IPS_NOT_READY)
    if (
        policy_assessment.reference.policy_id != policy.policy_id
        or policy_assessment.reference.version != policy.version
        or policy_assessment.reference.fingerprint_sha256
        != policy_fingerprint_sha256(policy)
    ):
        global_blockers.append(StrategySelectionBlockerCode.POLICY_BINDING_MISMATCH)
    if (
        risk.portfolio_snapshot_sha256 != portfolio_snapshot_sha256
        or risk.policy_reference != policy_assessment.reference
    ):
        global_blockers.append(StrategySelectionBlockerCode.RISK_BINDING_MISMATCH)
    if risk.proposed_trade_ids or risk.before != risk.after:
        global_blockers.append(
            StrategySelectionBlockerCode.HYPOTHETICAL_RISK_ASSESSMENT
        )
    if not risk.decision_ready:
        global_blockers.append(StrategySelectionBlockerCode.RISK_NOT_READY)
    if policy.tax_constraint_status is TaxConstraintStatus.UNKNOWN:
        global_blockers.append(StrategySelectionBlockerCode.TAX_CONTEXT_UNKNOWN)

    policy_cap = _policy_risk_cap(policy)
    horizon_cap = _horizon_cap(policy)
    max_rank = min(policy_cap, horizon_cap, _risk_state_cap(risk))
    ideal_rank = _objective_ideal_rank(policy, max_rank=max_rank)
    liquidity_severity = _vectors(risk)[RiskVectorKind.LIQUIDITY]

    structural: dict[StrategyRegime, tuple[StrategyCandidateBlockerCode, ...]] = {}
    for regime in StrategyRegime:
        structural[regime] = _candidate_blockers(
            regime,
            policy=policy,
            risk=risk,
            max_rank=max_rank,
            horizon_cap=horizon_cap,
            liquidity_severity=liquidity_severity,
        )

    feasible_action_regimes = tuple(
        regime
        for regime in StrategyRegime
        if regime is not StrategyRegime.NO_ACTION and not structural[regime]
    )
    for regime in feasible_action_regimes:
        evidence = friction.get(regime)
        if evidence is None:
            _append_unique(
                global_blockers,
                StrategySelectionBlockerCode.FRICTION_EVIDENCE_INCOMPLETE,
            )
            continue
        age = (evaluation_time - evidence.as_of).total_seconds()
        if age > settings_value.friction_max_age_seconds:
            _append_unique(
                global_blockers,
                StrategySelectionBlockerCode.FRICTION_EVIDENCE_STALE,
            )
        if age < -settings_value.future_tolerance_seconds:
            _append_unique(
                global_blockers,
                StrategySelectionBlockerCode.FRICTION_EVIDENCE_FUTURE,
            )

    comparisons: list[StrategyComparisonV1] = []
    no_action_fit = _no_action_fit(risk)
    for regime in StrategyRegime:
        candidate_blockers = structural[regime]
        feasible = not candidate_blockers
        if regime is StrategyRegime.NO_ACTION:
            comparison = StrategyComparisonV1(
                regime=regime,
                feasible=feasible,
                objective_fit=no_action_fit,
                risk_fit=no_action_fit,
                liquidity_fit=_liquidity_fit(liquidity_severity, 0),
                friction_weight=Decimal("0"),
                blockers=candidate_blockers,
                rationale_codes=(
                    "CURRENT_POSTURE_BASELINE",
                    "NO_EXPECTED_RETURN_ASSUMPTION",
                ),
            )
        else:
            rank = _REGIME_RANK[regime]
            friction_row = friction.get(regime)
            comparison = StrategyComparisonV1(
                regime=regime,
                feasible=feasible,
                objective_fit=_objective_fit(rank, ideal_rank),
                risk_fit=4 if rank <= max_rank else 0,
                liquidity_fit=_liquidity_fit(liquidity_severity, rank),
                friction_weight=(
                    friction_row.total_friction_weight
                    if friction_row is not None
                    else None
                ),
                blockers=candidate_blockers,
                rationale_codes=(
                    f"OBJECTIVE_{policy.objective.value.upper() if policy.objective else 'UNKNOWN'}",
                    f"REGIME_RISK_RANK_{rank}",
                    "COST_TAX_EVIDENCE_REQUIRED",
                    "NO_EXPECTED_RETURN_ASSUMPTION",
                ),
            )
        comparisons.append(comparison)

    ordered = tuple(sorted(comparisons, key=_comparison_sort_key))
    if not any(row.feasible for row in ordered):
        _append_unique(
            global_blockers,
            StrategySelectionBlockerCode.NO_FEASIBLE_STRATEGY,
        )

    canonical_blockers = tuple(sorted(set(global_blockers), key=str))
    decision_ready = not canonical_blockers
    selected_regime = (
        next(row.regime for row in ordered if row.feasible)
        if decision_ready
        else StrategyRegime.NO_ACTION
    )
    remediation_required = not risk.after.policy_compliant
    optimizer_eligible = decision_ready and selected_regime is not StrategyRegime.NO_ACTION

    values = {
        "schema_version": "1.0",
        "selected_at": evaluation_time,
        "portfolio_snapshot_sha256": portfolio_snapshot_sha256,
        "policy_reference": policy_assessment.reference,
        "risk_assessment_sha256": risk.assessment_sha256,
        "selected_regime": selected_regime,
        "components": _components(selected_regime, policy=policy, risk=risk),
        "comparisons": ordered,
        "blockers": canonical_blockers,
        "review_conditions": _review_conditions(),
        "remediation_required": remediation_required,
        "decision_ready": decision_ready,
        "optimizer_eligible": optimizer_eligible,
        "selection_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = MetaStrategySelectionV1.model_construct(**values)
    values["selection_sha256"] = meta_strategy_sha256(provisional)
    return MetaStrategySelectionV1.model_validate(values)
