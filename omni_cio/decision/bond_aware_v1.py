from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import AdvancedPortfolioAnalyticsV1
from omni_cio.contracts.v1.bond_credit import (
    BondCreditRiskAssessmentV1,
    BondCreditWarning,
)
from omni_cio.contracts.v1.bond_decision import (
    BondAwareDecisionSetV1,
    BondDecisionBlocker,
    BondDecisionEvidenceV1,
    BondDecisionOptionV1,
    BondDecisionWarning,
)
from omni_cio.contracts.v1.bond_portfolio_rate_stress import (
    BondPortfolioRateStressV1,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionOptionKind,
    DecisionOptionStatus,
    InstrumentMarketReadinessV1,
)
from omni_cio.contracts.v1.market import MarketAssessmentStatus
from omni_cio.contracts.v1.news import SanitizedNewsDocumentV1
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.decision.engine_v1 import DecisionEngineError, build_decision_set


_WARNING_MAP = {
    BondCreditWarning.RECENT_DOWNGRADE: BondDecisionWarning.RECENT_DOWNGRADE,
    BondCreditWarning.RATING_LABELS_DIVERGE: BondDecisionWarning.RATING_LABELS_DIVERGE,
    BondCreditWarning.SINGLE_AGENCY_COVERAGE: BondDecisionWarning.SINGLE_AGENCY_COVERAGE,
    BondCreditWarning.CROSS_AGENCY_SCALE_NOT_NORMALIZED: (
        BondDecisionWarning.CROSS_AGENCY_SCALE_NOT_NORMALIZED
    ),
    BondCreditWarning.INACTIVE_RATING_PRESENT: (
        BondDecisionWarning.INACTIVE_RATING_PRESENT
    ),
}


class BondAwareDecisionError(DecisionEngineError):
    """Bond evidence cannot be combined with the base decision safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise BondAwareDecisionError("BOND_DECISION_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _bond_positions(
    analytics: AdvancedPortfolioAnalyticsV1,
) -> dict[str, tuple[str, Decimal]]:
    positions: dict[str, tuple[str, Decimal]] = {}
    for currency in analytics.by_currency:
        for position in currency.positions:
            if position.instrument_type != InstrumentType.BOND:
                continue
            if position.stable_key in positions:
                raise BondAwareDecisionError("DUPLICATE_BOND_POSITION")
            positions[position.stable_key] = (
                position.currency,
                position.full_market_value,
            )
    return positions


def _credit_map(
    assessments: tuple[BondCreditRiskAssessmentV1, ...],
) -> dict[str, BondCreditRiskAssessmentV1]:
    result: dict[str, BondCreditRiskAssessmentV1] = {}
    for assessment in assessments:
        if assessment.instrument_key in result:
            raise BondAwareDecisionError("DUPLICATE_BOND_CREDIT_ASSESSMENT")
        result[assessment.instrument_key] = assessment
    return result


def _stress_map(
    assessments: tuple[BondPortfolioRateStressV1, ...],
) -> dict[str, BondPortfolioRateStressV1]:
    result: dict[str, BondPortfolioRateStressV1] = {}
    for assessment in assessments:
        if assessment.currency in result:
            raise BondAwareDecisionError("DUPLICATE_BOND_STRESS_CURRENCY")
        result[assessment.currency] = assessment
    return result


def _blocker_statement(blocker: BondDecisionBlocker) -> str:
    return {
        BondDecisionBlocker.CREDIT_COVERAGE_INCOMPLETE: (
            "Current issuer and issue credit assessment is missing for at least one bond."
        ),
        BondDecisionBlocker.CREDIT_NOT_READY: (
            "At least one bond credit assessment is stale, incomplete or contradictory."
        ),
        BondDecisionBlocker.DURATION_POLICY_BREACH: (
            "At least one bond duration exceeds the active conservative risk policy."
        ),
        BondDecisionBlocker.STRESS_COVERAGE_INCOMPLETE: (
            "A currency-local portfolio rate stress is missing for at least one bond currency."
        ),
        BondDecisionBlocker.STRESS_INSTRUMENT_COVERAGE_MISMATCH: (
            "A portfolio rate stress does not cover exactly the bonds held in its currency."
        ),
        BondDecisionBlocker.STRESS_CURRENT_VALUE_MISMATCH: (
            "A portfolio rate stress current value does not match verified portfolio analytics."
        ),
        BondDecisionBlocker.STRESS_POLICY_BREACH: (
            "The modeled bond rate-stress loss exceeds the active risk-policy limit."
        ),
    }[blocker]


def _build_effective_options(
    *,
    base_decision,
    bond_blockers: tuple[BondDecisionBlocker, ...],
    confidence: DecisionConfidence,
) -> tuple[BondDecisionOptionV1, ...]:
    blocked = base_decision.abstain or bool(bond_blockers)
    options: list[BondDecisionOptionV1] = []
    for source in base_decision.options:
        if blocked and source.kind == DecisionOptionKind.NO_ACTION:
            options.append(
                BondDecisionOptionV1(
                    option_id=source.option_id,
                    source_option_id=source.option_id,
                    kind=source.kind,
                    status=DecisionOptionStatus.PREFERRED,
                    action=DecisionAction.WAIT_FOR_DATA,
                    title="Do nothing and wait for verified bond evidence",
                    rationale=(
                        "The base decision or a bond-specific credit, duration or rate-stress "
                        "gate is open. Portfolio changes remain blocked."
                    ),
                    confidence=DecisionConfidence.LOW,
                    base_status=source.status,
                    base_action=source.action,
                    review_conditions=tuple(
                        _blocker_statement(item) for item in bond_blockers
                    ),
                    execution_ready=False,
                    trading_methods=False,
                )
            )
            continue
        if blocked:
            options.append(
                BondDecisionOptionV1(
                    option_id=source.option_id,
                    source_option_id=source.option_id,
                    kind=source.kind,
                    status=DecisionOptionStatus.BLOCKED,
                    action=source.action,
                    title=source.title,
                    rationale=(
                        "This change is blocked until all base and bond-specific gates close."
                    ),
                    confidence=DecisionConfidence.LOW,
                    base_status=source.status,
                    base_action=source.action,
                    base_blockers=base_decision.global_blockers,
                    bond_blockers=bond_blockers,
                    review_conditions=source.review_conditions,
                    execution_ready=False,
                    trading_methods=False,
                )
            )
            continue
        options.append(
            BondDecisionOptionV1(
                option_id=source.option_id,
                source_option_id=source.option_id,
                kind=source.kind,
                status=source.status,
                action=source.action,
                title=source.title,
                rationale=source.rationale,
                confidence=confidence,
                base_status=source.status,
                base_action=source.action,
                review_conditions=source.review_conditions,
                execution_ready=False,
                trading_methods=False,
            )
        )
    return tuple(options)


def build_bond_aware_decision_set(
    analytics: AdvancedPortfolioAnalyticsV1,
    risk_evaluation: RiskPolicyEvaluationV1,
    *,
    market_states: Iterable[InstrumentMarketReadinessV1] = (),
    news_documents: Iterable[SanitizedNewsDocumentV1] = (),
    credit_assessments: Iterable[BondCreditRiskAssessmentV1] = (),
    portfolio_rate_stresses: Iterable[BondPortfolioRateStressV1] = (),
    decided_at: datetime | None = None,
) -> BondAwareDecisionSetV1:
    """Apply credit, duration and rate-stress gates to the base decision set."""

    evaluation_time = _aware_utc(decided_at)
    base_decision = build_decision_set(
        analytics,
        risk_evaluation,
        market_states=market_states,
        news_documents=news_documents,
        decided_at=evaluation_time,
    )
    credits = tuple(credit_assessments)
    stresses = tuple(portfolio_rate_stresses)
    bonds = _bond_positions(analytics)
    required_keys = set(bonds)

    if not bonds:
        if credits or stresses:
            raise BondAwareDecisionError("UNEXPECTED_BOND_EVIDENCE")
        options = _build_effective_options(
            base_decision=base_decision,
            bond_blockers=(),
            confidence=base_decision.confidence,
        )
        preferred = next(
            option for option in options if option.status == DecisionOptionStatus.PREFERRED
        )
        return BondAwareDecisionSetV1(
            evaluated_at=evaluation_time,
            base_decision=base_decision,
            required_bond_count=0,
            credit_present_count=0,
            credit_ready_count=0,
            required_stress_currency_count=0,
            stress_currency_coverage_count=0,
            stress_covered_bond_count=0,
            evidence=(),
            options=options,
            preferred_option_id=preferred.option_id,
            base_blockers=base_decision.global_blockers,
            bond_blockers=(),
            warnings=(),
            max_observed_stress_loss_ratio=None,
            stress_loss_limit=risk_evaluation.policy.max_stress_loss_ratio,
            abstain=base_decision.abstain,
            recommendation_ready=base_decision.recommendation_ready,
            confidence=base_decision.confidence,
            no_cross_currency_aggregation=True,
            execution_ready=False,
            trading_methods=False,
        )

    credit_by_key = _credit_map(credits)
    stress_by_currency = _stress_map(stresses)
    extra_credit = set(credit_by_key) - required_keys
    if extra_credit:
        raise BondAwareDecisionError("CREDIT_ASSESSMENT_NOT_IN_PORTFOLIO")

    expected_by_currency: dict[str, set[str]] = {}
    value_by_currency: dict[str, Decimal] = {}
    for key, (currency, value) in bonds.items():
        expected_by_currency.setdefault(currency, set()).add(key)
        value_by_currency[currency] = value_by_currency.get(currency, Decimal("0")) + value
    extra_stress = set(stress_by_currency) - set(expected_by_currency)
    if extra_stress:
        raise BondAwareDecisionError("STRESS_CURRENCY_NOT_IN_PORTFOLIO")

    blockers: list[BondDecisionBlocker] = []
    warnings: list[BondDecisionWarning] = []
    evidence: list[BondDecisionEvidenceV1] = []

    missing_credit = required_keys - set(credit_by_key)
    if missing_credit:
        _append_unique(blockers, BondDecisionBlocker.CREDIT_COVERAGE_INCOMPLETE)

    credit_ready_count = 0
    for index, key in enumerate(sorted(required_keys), start=1):
        assessment = credit_by_key.get(key)
        if assessment is None:
            continue
        ready = (
            assessment.decision_ready
            and assessment.status == MarketAssessmentStatus.READY
            and not assessment.blockers
        )
        if ready:
            credit_ready_count += 1
        else:
            _append_unique(blockers, BondDecisionBlocker.CREDIT_NOT_READY)
        duration = assessment.duration_years
        if duration is None or duration > risk_evaluation.policy.max_duration_years:
            _append_unique(blockers, BondDecisionBlocker.DURATION_POLICY_BREACH)
        evidence.append(
            BondDecisionEvidenceV1(
                evidence_id=f"bond.credit.{index}",
                kind=(
                    DecisionEvidenceKind.FACT
                    if ready
                    else DecisionEvidenceKind.MISSING_DATA
                ),
                statement=(
                    f"Bond credit assessment ready={ready}; issuer_ratings="
                    f"{assessment.current_issuer_rating_count}; issue_ratings="
                    f"{assessment.current_issue_rating_count}; duration={duration}."
                ),
                source_schema="bond_credit_risk_assessment",
                source_id=key,
                observed_value=duration,
                limit_value=risk_evaluation.policy.max_duration_years,
                instrument_key=key,
            )
        )
        for warning in assessment.warnings:
            mapped = _WARNING_MAP.get(warning)
            if mapped is None:
                continue
            _append_unique(warnings, mapped)
            evidence.append(
                BondDecisionEvidenceV1(
                    evidence_id=f"bond.credit_warning.{index}.{mapped.value}",
                    kind=DecisionEvidenceKind.WARNING,
                    statement=f"Bond credit warning: {mapped.value}.",
                    source_schema="bond_credit_risk_assessment",
                    source_id=key,
                    instrument_key=key,
                )
            )

    missing_stress_currencies = set(expected_by_currency) - set(stress_by_currency)
    if missing_stress_currencies:
        _append_unique(blockers, BondDecisionBlocker.STRESS_COVERAGE_INCOMPLETE)

    stress_currency_coverage_count = 0
    stress_covered_bond_count = 0
    observed_stress_ratios: list[Decimal] = []
    for index, currency in enumerate(sorted(expected_by_currency), start=1):
        stress = stress_by_currency.get(currency)
        if stress is None:
            continue
        exact_keys = set(stress.instrument_keys) == expected_by_currency[currency]
        if not exact_keys:
            _append_unique(
                blockers,
                BondDecisionBlocker.STRESS_INSTRUMENT_COVERAGE_MISMATCH,
            )
        exact_value = (
            stress.current_full_value.currency == currency
            and stress.current_full_value.amount == value_by_currency[currency]
        )
        if not exact_value:
            _append_unique(
                blockers,
                BondDecisionBlocker.STRESS_CURRENT_VALUE_MISMATCH,
            )
        if exact_keys and exact_value:
            stress_currency_coverage_count += 1
            stress_covered_bond_count += len(expected_by_currency[currency])
        observed_stress_ratios.append(stress.worst_loss_ratio)
        if stress.worst_loss_ratio > risk_evaluation.policy.max_stress_loss_ratio:
            _append_unique(blockers, BondDecisionBlocker.STRESS_POLICY_BREACH)
        evidence.append(
            BondDecisionEvidenceV1(
                evidence_id=f"bond.stress.{index}",
                kind=(
                    DecisionEvidenceKind.SCENARIO
                    if exact_keys and exact_value
                    else DecisionEvidenceKind.MISSING_DATA
                ),
                statement=(
                    f"Currency-local bond stress worst loss ratio is "
                    f"{stress.worst_loss_ratio} at {stress.worst_shock_basis_points} bp."
                ),
                source_schema="bond_portfolio_rate_stress",
                source_id=currency,
                observed_value=stress.worst_loss_ratio,
                limit_value=risk_evaluation.policy.max_stress_loss_ratio,
                currency=currency,
            )
        )

    blocker_tuple = tuple(blockers)
    warning_tuple = tuple(warnings)
    for blocker in blocker_tuple:
        evidence.append(
            BondDecisionEvidenceV1(
                evidence_id=f"bond.blocker.{blocker.value}",
                kind=DecisionEvidenceKind.MISSING_DATA,
                statement=_blocker_statement(blocker),
                source_schema="bond_aware_decision_gate",
                source_id=blocker.value,
            )
        )

    if base_decision.abstain or blocker_tuple:
        confidence = DecisionConfidence.LOW
    elif warning_tuple and base_decision.confidence == DecisionConfidence.HIGH:
        confidence = DecisionConfidence.MEDIUM
    else:
        confidence = base_decision.confidence
    options = _build_effective_options(
        base_decision=base_decision,
        bond_blockers=blocker_tuple,
        confidence=confidence,
    )
    preferred = next(
        option for option in options if option.status == DecisionOptionStatus.PREFERRED
    )
    abstain = base_decision.abstain or bool(blocker_tuple)

    return BondAwareDecisionSetV1(
        evaluated_at=evaluation_time,
        base_decision=base_decision,
        required_bond_count=len(required_keys),
        credit_present_count=len(credit_by_key),
        credit_ready_count=credit_ready_count,
        required_stress_currency_count=len(expected_by_currency),
        stress_currency_coverage_count=stress_currency_coverage_count,
        stress_covered_bond_count=stress_covered_bond_count,
        evidence=tuple(evidence),
        options=options,
        preferred_option_id=preferred.option_id,
        base_blockers=base_decision.global_blockers,
        bond_blockers=blocker_tuple,
        warnings=warning_tuple,
        max_observed_stress_loss_ratio=(
            max(observed_stress_ratios) if observed_stress_ratios else None
        ),
        stress_loss_limit=risk_evaluation.policy.max_stress_loss_ratio,
        abstain=abstain,
        recommendation_ready=not abstain,
        confidence=confidence,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
