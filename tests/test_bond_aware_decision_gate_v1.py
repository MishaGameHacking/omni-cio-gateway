from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.analytics import (
    AdvancedPortfolioAnalyticsV1,
    AssetClassAllocationV1,
    ConcentrationMetricsV1,
    CurrencyPortfolioAnalyticsV1,
    PositionWeightV1,
)
from omni_cio.contracts.v1.bond_credit import (
    BondCreditBlocker,
    BondCreditRiskAssessmentV1,
    BondCreditRiskPolicyV1,
    BondCreditWarning,
    BondYieldBasis,
)
from omni_cio.contracts.v1.bond_decision import (
    BondAwareDecisionSetV1,
    BondDecisionBlocker,
    BondDecisionWarning,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionConfidence,
    DecisionOptionKind,
    DecisionOptionStatus,
    InstrumentMarketReadinessV1,
)
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    MarketReadinessAssessmentV1,
    SourceAuthority,
)
from omni_cio.contracts.v1.news import (
    EntityResolutionStatus,
    NewsContentFormat,
    NewsContentKind,
    NewsDocumentInputV1,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.risk import (
    RiskCheckCode,
    RiskCheckStatus,
    RiskCheckV1,
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
    RiskSeverity,
)
from omni_cio.decision import (
    BondAwareDecisionError,
    build_bond_aware_decision_set,
)
from omni_cio.market import (
    aggregate_bond_portfolio_rate_stress,
    assess_bond_rate_stress,
)
from omni_cio.news import sanitize_news_document
from omni_cio.risk import default_conservative_risk_policy


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
MATURITY = date(2029, 7, 29)
BOND_KEY = "uid:bond-a"


def _metadata(schema_name: str) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=NOW,
        account=AccountReference(masked_id="***3118", account_type="ИИС"),
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation=schema_name,
                retrieved_at=NOW,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _analytics(*, with_bond: bool = True) -> AdvancedPortfolioAnalyticsV1:
    if not with_bond:
        currency = CurrencyPortfolioAnalyticsV1(
            currency="RUB",
            cash=Decimal("1000"),
            clean_securities=Decimal("0"),
            accrued_interest=Decimal("0"),
            invested_value=Decimal("0"),
            total=Decimal("1000"),
            cash_weight=Decimal("1"),
            invested_weight=Decimal("0"),
            position_count=0,
            valued_position_count=0,
            positions=(),
            asset_classes=(),
            concentration=ConcentrationMetricsV1(
                top_1_portfolio_weight=Decimal("0"),
                top_5_portfolio_weight=Decimal("0"),
                top_1_invested_weight=Decimal("0"),
                top_5_invested_weight=Decimal("0"),
                hhi_invested=Decimal("0"),
                effective_position_count=Decimal("0"),
            ),
            stress_scenarios=(),
        )
    else:
        position = PositionWeightV1(
            stable_key=BOND_KEY,
            name="Тестовая облигация",
            ticker="BOND1",
            instrument_type=InstrumentType.BOND,
            currency="RUB",
            full_market_value=Decimal("1000"),
            portfolio_weight=Decimal("0.6666666666666666666666666667"),
            invested_weight=Decimal("1"),
        )
        currency = CurrencyPortfolioAnalyticsV1(
            currency="RUB",
            cash=Decimal("500"),
            clean_securities=Decimal("988"),
            accrued_interest=Decimal("12"),
            invested_value=Decimal("1000"),
            total=Decimal("1500"),
            cash_weight=Decimal("0.3333333333333333333333333333"),
            invested_weight=Decimal("0.6666666666666666666666666667"),
            position_count=1,
            valued_position_count=1,
            positions=(position,),
            asset_classes=(
                AssetClassAllocationV1(
                    instrument_type=InstrumentType.BOND,
                    full_market_value=Decimal("1000"),
                    position_count=1,
                    portfolio_weight=Decimal("0.6666666666666666666666666667"),
                    invested_weight=Decimal("1"),
                ),
            ),
            concentration=ConcentrationMetricsV1(
                top_1_portfolio_weight=Decimal("0.6666666666666666666666666667"),
                top_5_portfolio_weight=Decimal("0.6666666666666666666666666667"),
                top_1_invested_weight=Decimal("1"),
                top_5_invested_weight=Decimal("1"),
                hhi_invested=Decimal("1"),
                effective_position_count=Decimal("1"),
            ),
            stress_scenarios=(),
        )
    return AdvancedPortfolioAnalyticsV1(
        metadata=_metadata("advanced_portfolio_analytics"),
        source_snapshot_retrieved_at=NOW,
        by_currency=(currency,),
        missing_data=(),
        no_cross_currency_aggregation=True,
        decision_ready=True,
    )


def _risk() -> RiskPolicyEvaluationV1:
    policy = default_conservative_risk_policy()
    checks = (
        RiskCheckV1(
            check_id="source.data_quality",
            code=RiskCheckCode.DATA_QUALITY,
            status=RiskCheckStatus.PASS,
            severity=RiskSeverity.BLOCK,
            message="Source quality passed.",
            observed_value=Decimal("1"),
            limit_value=Decimal("1"),
        ),
    )
    return RiskPolicyEvaluationV1(
        metadata=_metadata("risk_policy_evaluation"),
        policy=policy,
        overall_status=RiskOverallStatus.PASS,
        decision_ready=True,
        checks=checks,
        breach_count=0,
        warning_count=0,
        unknown_count=0,
        no_cross_currency_aggregation=True,
    )


def _market() -> InstrumentMarketReadinessV1:
    return InstrumentMarketReadinessV1(
        instrument_key=BOND_KEY,
        assessment=MarketReadinessAssessmentV1(
            assessed_at=NOW,
            status=MarketAssessmentStatus.READY,
            decision_ready=True,
            stale_components=(),
            missing_components=(),
            untrusted_components=(),
        ),
    )


def _news():
    return sanitize_news_document(
        NewsDocumentInputV1(
            document_id="official-bond-fact",
            publisher="Synthetic issuer",
            authority=SourceAuthority.PRIMARY,
            published_at=NOW,
            retrieved_at=NOW,
            event_at=NOW,
            title="Issuer disclosure",
            raw_content="The issuer published verified operating results.",
            content_format=NewsContentFormat.PLAIN_TEXT,
            content_kind=NewsContentKind.FACT,
            entity_resolution=EntityResolutionStatus.RESOLVED,
            instrument_key=BOND_KEY,
            source_record_id="official-bond-fact",
        )
    )


def _credit(
    *,
    key: str = BOND_KEY,
    duration: str = "3",
    ready: bool = True,
    warnings: tuple[BondCreditWarning, ...] = (),
) -> BondCreditRiskAssessmentV1:
    blockers = () if ready else (BondCreditBlocker.ISSUE_RATING_STALE,)
    return BondCreditRiskAssessmentV1(
        assessed_at=NOW,
        instrument_key=key,
        status=(
            MarketAssessmentStatus.READY
            if ready
            else MarketAssessmentStatus.PARTIAL
        ),
        decision_ready=ready,
        policy=BondCreditRiskPolicyV1(
            max_duration_years=Decimal("10"),
            require_issuer_rating=False,
            require_issue_rating=False,
        ),
        selected_ratings=(),
        agencies=(),
        current_issuer_rating_count=0,
        current_issue_rating_count=0,
        stale_rating_count=0,
        noncurrent_rating_count=0,
        divergent_scopes=(),
        maturity_date=MATURITY,
        effective_exit_date=MATURITY,
        days_to_maturity=(MATURITY - NOW.date()).days,
        duration_years=Decimal(duration),
        yield_basis=BondYieldBasis.TO_MATURITY,
        selected_yield=Decimal("0.14"),
        blockers=blockers,
        warnings=warnings,
        cross_agency_scale_normalized=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )


def _portfolio_stress(
    *,
    credit: BondCreditRiskAssessmentV1 | None = None,
    key: str = BOND_KEY,
    value: str = "1000",
    shocks: tuple[int, ...] = (-200, -100, 100, 200),
):
    active_credit = credit or _credit(key=key)
    instrument_stress = assess_bond_rate_stress(
        active_credit,
        Money(amount=Decimal(value), currency="RUB"),
        currency="RUB",
        shock_basis_points=shocks,
        assessed_at=NOW,
    )
    return aggregate_bond_portfolio_rate_stress(
        (instrument_stress,),
        currency="RUB",
        assessed_at=NOW,
    )


def _option(result: BondAwareDecisionSetV1, kind: DecisionOptionKind):
    return next(option for option in result.options if option.kind == kind)


def test_ready_bond_evidence_preserves_base_decision() -> None:
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(),),
        portfolio_rate_stresses=(_portfolio_stress(),),
        decided_at=NOW,
    )

    assert result.abstain is False
    assert result.recommendation_ready is True
    assert result.required_bond_count == 1
    assert result.credit_ready_count == 1
    assert result.stress_covered_bond_count == 1
    assert result.bond_blockers == ()
    assert result.max_observed_stress_loss_ratio == Decimal("0.06")
    assert _option(result, DecisionOptionKind.NO_ACTION).status == (
        DecisionOptionStatus.PREFERRED
    )
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_missing_and_stale_credit_force_wait_for_data() -> None:
    missing = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        portfolio_rate_stresses=(_portfolio_stress(),),
        decided_at=NOW,
    )
    assert BondDecisionBlocker.CREDIT_COVERAGE_INCOMPLETE in missing.bond_blockers
    assert missing.abstain is True

    stale = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(ready=False),),
        portfolio_rate_stresses=(_portfolio_stress(),),
        decided_at=NOW,
    )
    assert BondDecisionBlocker.CREDIT_NOT_READY in stale.bond_blockers
    assert _option(stale, DecisionOptionKind.NO_ACTION).action == (
        DecisionAction.WAIT_FOR_DATA
    )
    assert _option(stale, DecisionOptionKind.LIMITED_CHANGE).status == (
        DecisionOptionStatus.BLOCKED
    )


def test_duration_policy_breach_blocks_even_when_credit_policy_is_looser() -> None:
    credit = _credit(duration="6")
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(credit,),
        portfolio_rate_stresses=(_portfolio_stress(credit=credit),),
        decided_at=NOW,
    )

    assert BondDecisionBlocker.DURATION_POLICY_BREACH in result.bond_blockers
    assert result.abstain is True


def test_rate_stress_above_policy_limit_blocks_recommendation() -> None:
    credit = _credit(duration="2")
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(credit,),
        portfolio_rate_stresses=(
            _portfolio_stress(credit=credit, shocks=(-1000, 1000)),
        ),
        decided_at=NOW,
    )

    assert result.max_observed_stress_loss_ratio == Decimal("0.2")
    assert result.stress_loss_limit == Decimal("0.15")
    assert BondDecisionBlocker.STRESS_POLICY_BREACH in result.bond_blockers
    assert result.confidence == DecisionConfidence.LOW


def test_missing_or_mismatched_stress_coverage_fails_closed() -> None:
    missing = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(),),
        decided_at=NOW,
    )
    assert BondDecisionBlocker.STRESS_COVERAGE_INCOMPLETE in missing.bond_blockers

    wrong_key = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(),),
        portfolio_rate_stresses=(
            _portfolio_stress(key="uid:other-bond"),
        ),
        decided_at=NOW,
    )
    assert (
        BondDecisionBlocker.STRESS_INSTRUMENT_COVERAGE_MISMATCH
        in wrong_key.bond_blockers
    )


def test_stress_current_value_must_match_verified_portfolio_value() -> None:
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(),),
        portfolio_rate_stresses=(_portfolio_stress(value="900"),),
        decided_at=NOW,
    )

    assert BondDecisionBlocker.STRESS_CURRENT_VALUE_MISMATCH in result.bond_blockers
    assert result.stress_currency_coverage_count == 0


def test_credit_warning_reduces_high_confidence_without_blocking() -> None:
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        news_documents=(_news(),),
        credit_assessments=(
            _credit(warnings=(BondCreditWarning.RECENT_DOWNGRADE,)),
        ),
        portfolio_rate_stresses=(_portfolio_stress(),),
        decided_at=NOW,
    )

    assert result.base_decision.confidence == DecisionConfidence.HIGH
    assert result.confidence == DecisionConfidence.MEDIUM
    assert result.abstain is False
    assert BondDecisionWarning.RECENT_DOWNGRADE in result.warnings


def test_duplicate_or_extra_evidence_is_rejected() -> None:
    credit = _credit()
    with pytest.raises(BondAwareDecisionError, match="DUPLICATE_BOND_CREDIT"):
        build_bond_aware_decision_set(
            _analytics(),
            _risk(),
            market_states=(_market(),),
            credit_assessments=(credit, credit),
            decided_at=NOW,
        )

    with pytest.raises(BondAwareDecisionError, match="CREDIT_ASSESSMENT_NOT_IN_PORTFOLIO"):
        build_bond_aware_decision_set(
            _analytics(),
            _risk(),
            market_states=(_market(),),
            credit_assessments=(_credit(key="uid:extra-bond"),),
            decided_at=NOW,
        )


def test_non_bond_portfolio_mirrors_base_and_rejects_unexpected_evidence() -> None:
    result = build_bond_aware_decision_set(
        _analytics(with_bond=False),
        _risk(),
        decided_at=NOW,
    )
    assert result.required_bond_count == 0
    assert result.bond_blockers == ()
    assert result.abstain == result.base_decision.abstain
    assert result.preferred_option_id == result.base_decision.preferred_option_id

    with pytest.raises(BondAwareDecisionError, match="UNEXPECTED_BOND_EVIDENCE"):
        build_bond_aware_decision_set(
            _analytics(with_bond=False),
            _risk(),
            credit_assessments=(_credit(),),
            decided_at=NOW,
        )


def test_contract_rejects_tampered_effective_state() -> None:
    result = build_bond_aware_decision_set(
        _analytics(),
        _risk(),
        market_states=(_market(),),
        credit_assessments=(_credit(),),
        decided_at=NOW,
    )
    assert result.abstain is True

    payload = result.model_dump(mode="python")
    payload["abstain"] = False
    payload["recommendation_ready"] = True
    with pytest.raises(ValidationError, match="abstain state"):
        BondAwareDecisionSetV1.model_validate(payload)


def test_bond_aware_layer_has_no_network_or_execution_surface() -> None:
    source = Path("omni_cio/decision/bond_aware_v1.py").read_text(encoding="utf-8")
    lowered = source.casefold()
    assert "requests" not in lowered
    assert "httpx" not in lowered
    assert "grpc" not in lowered
    assert "broker_order_created=true" not in lowered
    assert "trading_methods=true" not in lowered
