from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.investment_policy import (
    AccountPolicyType,
    InvestmentObjective,
    InvestmentPolicyStatementV1,
    LiquidityReserveV1,
    PolicyField,
    PolicyFieldProvenanceV1,
    PolicyLifecycle,
    PolicySourceKind,
    RiskLevel,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyCandidateBlockerCode,
    StrategyComponentDirective,
    StrategyComponentKind,
    StrategyFrictionEvidenceV1,
    StrategyRegime,
    StrategyReviewAction,
    StrategyReviewCode,
    StrategySelectionBlockerCode,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_risk import (
    ConcentrationSummaryV1,
    PortfolioRiskAssessmentV1,
    PortfolioRiskStateV1,
    RiskBlockerCode,
    RiskSeverity,
    RiskVectorKind,
    RiskVectorV1,
    portfolio_risk_sha256,
)
from omni_cio.policy import assess_investment_policy
from omni_cio.strategy import select_meta_strategy


EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW_DUE = datetime(2026, 12, 31, tzinfo=timezone.utc)
ASSESS_AT = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
SNAPSHOT_SHA = "1" * 64

_REQUIRED_PROVENANCE_FIELDS = (
    PolicyField.OBJECTIVE,
    PolicyField.TIME_HORIZON,
    PolicyField.LIQUIDITY_RESERVE,
    PolicyField.RISK_WILLINGNESS,
    PolicyField.RISK_CAPACITY,
    PolicyField.MAX_DRAWDOWN,
    PolicyField.MAX_POSITION_WEIGHT,
    PolicyField.MAX_GROUP_WEIGHT,
    PolicyField.MAX_SECTOR_WEIGHT,
    PolicyField.MAX_CURRENCY_WEIGHT,
    PolicyField.MINIMUM_CREDIT_QUALITY,
    PolicyField.ALLOWED_MARKETS,
    PolicyField.ALLOWED_INSTRUMENT_TYPES,
    PolicyField.PROHIBITED_INSTRUMENT_TYPES,
    PolicyField.TAX_STATUS,
    PolicyField.ACCOUNT_TYPE,
    PolicyField.REBALANCE_BAND,
)


def _provenance() -> tuple[PolicyFieldProvenanceV1, ...]:
    rows: list[PolicyFieldProvenanceV1] = []
    for field in _REQUIRED_PROVENANCE_FIELDS:
        verified_account = field is PolicyField.ACCOUNT_TYPE
        rows.append(
            PolicyFieldProvenanceV1(
                field=field,
                source_kind=(
                    PolicySourceKind.VERIFIED_ACCOUNT_DATA
                    if verified_account
                    else PolicySourceKind.OWNER_INPUT
                ),
                owner_confirmed=not verified_account,
                confirmed_at=EFFECTIVE,
                source_id=(
                    "masked-account-fact"
                    if verified_account
                    else f"owner-{field.value}"
                ),
            )
        )
    return tuple(rows)


def _policy(**updates: object) -> InvestmentPolicyStatementV1:
    payload: dict[str, object] = {
        "policy_id": "ips_owner_strategy_v9",
        "version": "1",
        "lifecycle": PolicyLifecycle.ACTIVE,
        "created_at": EFFECTIVE,
        "effective_at": EFFECTIVE,
        "review_due_at": REVIEW_DUE,
        "base_currency": "RUB",
        "objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
        "time_horizon_years": Decimal("10"),
        "liquidity_reserve": LiquidityReserveV1(
            amount=Decimal("100000"),
            currency="RUB",
        ),
        "risk_willingness": RiskLevel.MODERATE,
        "risk_capacity": RiskLevel.MODERATE,
        "max_drawdown": Decimal("0.35"),
        "max_position_weight": Decimal("0.50"),
        "max_group_weight": Decimal("0.80"),
        "max_sector_weight": Decimal("0.80"),
        "max_currency_weight": Decimal("0.95"),
        "minimum_credit_rating": "A-",
        "credit_rating_scale": "AKRA_RU",
        "allowed_markets": ("MOEX",),
        "allowed_instrument_types": (
            InstrumentType.SHARE,
            InstrumentType.BOND,
            InstrumentType.ETF,
        ),
        "prohibited_instrument_types": (
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.STRUCTURED_PRODUCT,
        ),
        "tax_constraint_status": TaxConstraintStatus.REVIEWED,
        "account_type": AccountPolicyType.BROKERAGE,
        "rebalance_band_weight": Decimal("0.05"),
        "provenance": _provenance(),
    }
    payload.update(updates)
    return InvestmentPolicyStatementV1.model_validate(payload)


def _risk_state(
    *,
    hard_kind: RiskVectorKind | None = None,
    severity_overrides: dict[RiskVectorKind, RiskSeverity] | None = None,
) -> PortfolioRiskStateV1:
    overrides = severity_overrides or {}
    vectors: list[RiskVectorV1] = []
    for kind in RiskVectorKind:
        hard = kind is hard_kind
        severity = RiskSeverity.BREACH if hard else overrides.get(kind, RiskSeverity.LOW)
        vectors.append(
            RiskVectorV1(
                kind=kind,
                severity=severity,
                hard_breach=hard,
            )
        )
    blockers = (
        (RiskBlockerCode.ACTIVE_DEFAULT,)
        if hard_kind is RiskVectorKind.CREDIT
        else ()
    )
    return PortfolioRiskStateV1(
        total_value_base=Decimal("1000000"),
        cash_base=Decimal("300000"),
        cash_weight=Decimal("0.30"),
        concentration=ConcentrationSummaryV1(
            top_1_weight=Decimal("0.25"),
            top_3_weight=Decimal("0.60"),
            top_5_weight=Decimal("0.70"),
            rows=(),
        ),
        liquidity=(),
        stress=(),
        vectors=tuple(vectors),
        blockers=blockers,
        policy_compliant=hard_kind is None,
    )


def _risk(
    policy: InvestmentPolicyStatementV1,
    *,
    hard_kind: RiskVectorKind | None = None,
    decision_ready: bool = True,
    proposed_trade_ids: tuple[str, ...] = (),
    severity_overrides: dict[RiskVectorKind, RiskSeverity] | None = None,
) -> tuple[PortfolioRiskAssessmentV1, object]:
    policy_assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)
    state = _risk_state(
        hard_kind=hard_kind,
        severity_overrides=severity_overrides,
    )
    values = {
        "schema_version": "1.0",
        "assessed_at": ASSESS_AT,
        "portfolio_snapshot_sha256": SNAPSHOT_SHA,
        "policy_reference": policy_assessment.reference,
        "before": state,
        "after": state,
        "proposed_trade_ids": proposed_trade_ids,
        "new_blockers": (),
        "resolved_blockers": (),
        "decision_ready": decision_ready,
        "plan_eligible": decision_ready and state.policy_compliant,
        "assessment_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = PortfolioRiskAssessmentV1.model_construct(**values)
    values["assessment_sha256"] = portfolio_risk_sha256(provisional)
    return PortfolioRiskAssessmentV1.model_validate(values), policy_assessment


def _friction(
    *,
    as_of: datetime = ASSESS_AT,
    source_override: dict[StrategyRegime, str] | None = None,
) -> tuple[StrategyFrictionEvidenceV1, ...]:
    sources = source_override or {}
    defaults = {
        StrategyRegime.CAPITAL_PRESERVATION: "a" * 64,
        StrategyRegime.DEFENSIVE_BALANCED: "b" * 64,
        StrategyRegime.BALANCED_CORE: "c" * 64,
        StrategyRegime.GROWTH_CORE: "d" * 64,
    }
    costs = {
        StrategyRegime.CAPITAL_PRESERVATION: Decimal("0.002"),
        StrategyRegime.DEFENSIVE_BALANCED: Decimal("0.003"),
        StrategyRegime.BALANCED_CORE: Decimal("0.004"),
        StrategyRegime.GROWTH_CORE: Decimal("0.005"),
    }
    return tuple(
        StrategyFrictionEvidenceV1(
            regime=regime,
            transition_cost_weight=cost,
            tax_cost_weight=Decimal("0.001"),
            as_of=as_of,
            source_sha256s=(sources.get(regime, defaults[regime]),),
        )
        for regime, cost in costs.items()
    )


def _comparison(
    selection: MetaStrategySelectionV1,
    regime: StrategyRegime,
):
    return next(row for row in selection.comparisons if row.regime is regime)


def _component_row(
    selection: MetaStrategySelectionV1,
    kind: StrategyComponentKind,
):
    return next(row for row in selection.components if row.kind is kind)


def test_preserve_purchasing_power_selects_defensive_regime_deterministically() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    assert selection.decision_ready is True
    assert selection.selected_regime is StrategyRegime.DEFENSIVE_BALANCED
    assert selection.optimizer_eligible is True
    assert selection.remediation_required is False
    assert selection.policy_reference == policy_assessment.reference
    assert selection.risk_assessment_sha256 == risk.assessment_sha256
    assert selection.trading_methods is False
    assert len(selection.comparisons) == len(StrategyRegime)
    assert _comparison(selection, StrategyRegime.NO_ACTION).friction_weight == Decimal("0")
    assert (
        _component_row(selection, StrategyComponentKind.LIQUIDITY_RESERVE).directive
        is StrategyComponentDirective.REQUIRED
    )
    assert (
        _component_row(selection, StrategyComponentKind.BOUNDED_ACTIVE).directive
        is StrategyComponentDirective.FORBIDDEN
    )
    actions = {row.code: row.action for row in selection.review_conditions}
    assert actions[StrategyReviewCode.POLICY_CHANGED] is StrategyReviewAction.CANCEL
    assert actions[StrategyReviewCode.HARD_BREACH_APPEARED] is StrategyReviewAction.CANCEL


def test_growth_and_active_sleeve_require_high_willingness_and_capacity() -> None:
    policy = _policy(
        objective=InvestmentObjective.REAL_CAPITAL_GROWTH,
        risk_willingness=RiskLevel.HIGH,
        risk_capacity=RiskLevel.HIGH,
    )
    risk, policy_assessment = _risk(policy)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    assert selection.selected_regime is StrategyRegime.GROWTH_CORE
    assert (
        _component_row(selection, StrategyComponentKind.BOUNDED_ACTIVE).directive
        is StrategyComponentDirective.ALLOWED
    )


def test_current_hard_credit_breach_cannot_be_averaged_into_no_action() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy, hard_kind=RiskVectorKind.CREDIT)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    no_action = _comparison(selection, StrategyRegime.NO_ACTION)
    assert no_action.feasible is False
    assert StrategyCandidateBlockerCode.CURRENT_HARD_BREACH in no_action.blockers
    assert selection.remediation_required is True
    assert selection.selected_regime in {
        StrategyRegime.CAPITAL_PRESERVATION,
        StrategyRegime.DEFENSIVE_BALANCED,
    }
    assert selection.optimizer_eligible is True


def test_missing_friction_evidence_fails_closed_instead_of_assuming_zero_cost() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=(),
        selected_at=ASSESS_AT,
    )

    assert StrategySelectionBlockerCode.FRICTION_EVIDENCE_INCOMPLETE in selection.blockers
    assert selection.decision_ready is False
    assert selection.selected_regime is StrategyRegime.NO_ACTION
    assert selection.optimizer_eligible is False


def test_stale_friction_evidence_fails_closed() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(as_of=ASSESS_AT - timedelta(days=2)),
        selected_at=ASSESS_AT,
    )

    assert StrategySelectionBlockerCode.FRICTION_EVIDENCE_STALE in selection.blockers
    assert selection.decision_ready is False


def test_same_version_policy_mutation_breaks_exact_binding() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy)
    mutated = _policy(max_position_weight=Decimal("0.40"))

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=mutated,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    assert StrategySelectionBlockerCode.POLICY_BINDING_MISMATCH in selection.blockers
    assert selection.decision_ready is False
    assert selection.selected_regime is StrategyRegime.NO_ACTION


def test_hypothetical_wp8_assessment_cannot_impersonate_current_risk() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(
        policy,
        proposed_trade_ids=("trade_candidate_001",),
    )

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    assert StrategySelectionBlockerCode.HYPOTHETICAL_RISK_ASSESSMENT in selection.blockers
    assert selection.optimizer_eligible is False


def test_unknown_tax_context_preserves_wp2_and_wp9_fail_closed_semantics() -> None:
    policy = _policy(tax_constraint_status=TaxConstraintStatus.UNKNOWN)
    risk, policy_assessment = _risk(policy)

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    assert policy_assessment.ready_for_personal_sizing is False
    assert StrategySelectionBlockerCode.IPS_NOT_READY in selection.blockers
    assert StrategySelectionBlockerCode.TAX_CONTEXT_UNKNOWN in selection.blockers
    assert selection.decision_ready is False


def test_friction_order_is_invariant_but_evidence_source_mutation_changes_sha() -> None:
    policy = _policy()
    risk, policy_assessment = _risk(policy)
    evidence = _friction()

    first = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=evidence,
        selected_at=ASSESS_AT,
    )
    reordered = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=tuple(reversed(evidence)),
        selected_at=ASSESS_AT,
    )
    changed_source = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(
            source_override={StrategyRegime.DEFENSIVE_BALANCED: "f" * 64}
        ),
        selected_at=ASSESS_AT,
    )

    assert first.selection_sha256 == reordered.selection_sha256
    assert first.selection_sha256 != changed_source.selection_sha256
    defensive = _comparison(first, StrategyRegime.DEFENSIVE_BALANCED)
    assert defensive.friction_as_of == ASSESS_AT
    assert defensive.friction_source_sha256s == ("b" * 64,)


def test_no_action_cannot_carry_fake_friction_evidence() -> None:
    with pytest.raises(ValidationError, match="NO_ACTION"):
        StrategyFrictionEvidenceV1(
            regime=StrategyRegime.NO_ACTION,
            transition_cost_weight=Decimal("0"),
            tax_cost_weight=Decimal("0"),
            as_of=ASSESS_AT,
            source_sha256s=("a" * 64,),
        )


def test_high_or_unknown_liquidity_restricts_growth_before_comparison() -> None:
    policy = _policy(
        objective=InvestmentObjective.REAL_CAPITAL_GROWTH,
        risk_willingness=RiskLevel.HIGH,
        risk_capacity=RiskLevel.HIGH,
    )
    risk, policy_assessment = _risk(
        policy,
        severity_overrides={RiskVectorKind.LIQUIDITY: RiskSeverity.HIGH},
    )

    selection = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=_friction(),
        selected_at=ASSESS_AT,
    )

    growth = _comparison(selection, StrategyRegime.GROWTH_CORE)
    assert growth.feasible is False
    assert StrategyCandidateBlockerCode.LIQUIDITY_TOO_WEAK in growth.blockers
    assert selection.selected_regime is not StrategyRegime.GROWTH_CORE
