from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.analytics import (
    AdvancedPortfolioAnalyticsV1,
    AssetClassAllocationV1,
    ConcentrationMetricsV1,
    CurrencyPortfolioAnalyticsV1,
    PositionWeightV1,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import InstrumentMarketReadinessV1
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    MarketReadinessAssessmentV1,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceAlternativeStatus,
    RebalanceBandStatus,
    RebalanceDirection,
    RebalanceLineV1,
    TargetBandV1,
)
from omni_cio.contracts.v1.risk import (
    RiskCheckCode,
    RiskCheckStatus,
    RiskCheckV1,
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
    RiskSeverity,
)
from omni_cio.decision import build_decision_set
from omni_cio.rebalancing import (
    RebalancingEngineError,
    build_threshold_rebalance_plan,
)
from omni_cio.risk import default_conservative_risk_policy


NOW = datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY_A = "uid:asset-a"
KEY_B = "uid:asset-b"


def _metadata(schema_name: str) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=NOW,
        account=ACCOUNT,
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


def _analytics() -> AdvancedPortfolioAnalyticsV1:
    positions = (
        PositionWeightV1(
            stable_key=KEY_A,
            name="Asset A",
            ticker="AAA",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            full_market_value=Decimal("500"),
            portfolio_weight=Decimal("0.5"),
            invested_weight=Decimal("0.625"),
        ),
        PositionWeightV1(
            stable_key=KEY_B,
            name="Asset B",
            ticker="BBB",
            instrument_type=InstrumentType.BOND,
            currency="RUB",
            full_market_value=Decimal("300"),
            portfolio_weight=Decimal("0.3"),
            invested_weight=Decimal("0.375"),
        ),
    )
    currency = CurrencyPortfolioAnalyticsV1(
        currency="RUB",
        cash=Decimal("200"),
        clean_securities=Decimal("800"),
        accrued_interest=Decimal("0"),
        invested_value=Decimal("800"),
        total=Decimal("1000"),
        cash_weight=Decimal("0.2"),
        invested_weight=Decimal("0.8"),
        position_count=2,
        valued_position_count=2,
        positions=positions,
        asset_classes=(
            AssetClassAllocationV1(
                instrument_type=InstrumentType.SHARE,
                full_market_value=Decimal("500"),
                position_count=1,
                portfolio_weight=Decimal("0.5"),
                invested_weight=Decimal("0.625"),
            ),
            AssetClassAllocationV1(
                instrument_type=InstrumentType.BOND,
                full_market_value=Decimal("300"),
                position_count=1,
                portfolio_weight=Decimal("0.3"),
                invested_weight=Decimal("0.375"),
            ),
        ),
        concentration=ConcentrationMetricsV1(
            top_1_portfolio_weight=Decimal("0.5"),
            top_5_portfolio_weight=Decimal("0.8"),
            top_1_invested_weight=Decimal("0.625"),
            top_5_invested_weight=Decimal("1"),
            hhi_invested=Decimal("0.53125"),
            effective_position_count=Decimal("1.882352941176470588235294118"),
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


def _decision(analytics: AdvancedPortfolioAnalyticsV1):
    policy = default_conservative_risk_policy()
    risk = RiskPolicyEvaluationV1(
        metadata=_metadata("risk_policy_evaluation"),
        policy=policy,
        overall_status=RiskOverallStatus.PASS,
        decision_ready=True,
        checks=(
            RiskCheckV1(
                check_id="source.data_quality",
                code=RiskCheckCode.DATA_QUALITY,
                status=RiskCheckStatus.PASS,
                severity=RiskSeverity.BLOCK,
                message="Source quality passed.",
                observed_value=Decimal("1"),
                limit_value=Decimal("1"),
            ),
        ),
        breach_count=0,
        warning_count=0,
        unknown_count=0,
        no_cross_currency_aggregation=True,
    )
    markets = tuple(
        InstrumentMarketReadinessV1(
            instrument_key=key,
            assessment=MarketReadinessAssessmentV1(
                assessed_at=NOW,
                status=MarketAssessmentStatus.READY,
                decision_ready=True,
                stale_components=(),
                missing_components=(),
                untrusted_components=(),
            ),
        )
        for key in (KEY_A, KEY_B)
    )
    return build_decision_set(
        analytics,
        risk,
        market_states=markets,
        decided_at=NOW,
    )


def _bands() -> tuple[TargetBandV1, ...]:
    return (
        TargetBandV1(
            stable_key=KEY_A,
            currency="RUB",
            lower_weight=Decimal("0.35"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
        ),
        TargetBandV1(
            stable_key=KEY_B,
            currency="RUB",
            lower_weight=Decimal("0.35"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
        ),
    )


def _alternative(plan, kind: RebalanceAlternativeKind):
    return next(row for row in plan.alternatives if row.kind == kind)


def test_cash_first_is_preferred_for_underweight_position() -> None:
    analytics = _analytics()
    plan = build_threshold_rebalance_plan(
        analytics,
        _decision(analytics),
        _bands(),
        currency="RUB",
        deployable_cash=Decimal("80"),
        planned_at=NOW,
    )

    assert plan.decision_ready is True
    assert plan.breach_count == 2
    assert plan.below_count == 1
    assert plan.above_count == 1
    cash_first = _alternative(plan, RebalanceAlternativeKind.CASH_FIRST)
    assert cash_first.status == RebalanceAlternativeStatus.PREFERRED
    assert cash_first.uses_sales is False
    assert cash_first.planned_add_value == Decimal("80")
    assert cash_first.residual_cash == 0
    assert plan.preferred_alternative_id == cash_first.alternative_id


def test_lines_use_threshold_bands_not_exact_target_as_trigger() -> None:
    analytics = _analytics()
    inside_bands = (
        TargetBandV1(
            stable_key=KEY_A,
            currency="RUB",
            lower_weight=Decimal("0.45"),
            target_weight=Decimal("0.5"),
            upper_weight=Decimal("0.55"),
        ),
        TargetBandV1(
            stable_key=KEY_B,
            currency="RUB",
            lower_weight=Decimal("0.25"),
            target_weight=Decimal("0.3"),
            upper_weight=Decimal("0.35"),
        ),
    )
    plan = build_threshold_rebalance_plan(
        analytics,
        _decision(analytics),
        inside_bands,
        currency="RUB",
        deployable_cash=Decimal("80"),
        planned_at=NOW,
    )

    assert plan.breach_count == 0
    assert all(line.band_status == RebalanceBandStatus.INSIDE for line in plan.lines)
    assert _alternative(
        plan,
        RebalanceAlternativeKind.NO_ACTION,
    ).status == RebalanceAlternativeStatus.PREFERRED


def test_full_threshold_is_blocked_pending_preview_and_tax_basis() -> None:
    analytics = _analytics()
    plan = build_threshold_rebalance_plan(
        analytics,
        _decision(analytics),
        _bands(),
        currency="RUB",
        deployable_cash=Decimal("80"),
        tax_basis_available=False,
        planned_at=NOW,
    )

    full = _alternative(plan, RebalanceAlternativeKind.FULL_THRESHOLD)
    assert full.status == RebalanceAlternativeStatus.BLOCKED
    assert full.uses_sales is True
    assert full.planned_reduce_value == Decimal("100")
    assert full.planned_add_value == Decimal("100")
    assert full.residual_cash == Decimal("80")
    assert len(full.blockers) == 2
    assert full.execution_ready is False


def test_incomplete_target_coverage_forces_no_action() -> None:
    analytics = _analytics()
    plan = build_threshold_rebalance_plan(
        analytics,
        _decision(analytics),
        _bands()[:1],
        currency="RUB",
        deployable_cash=Decimal("80"),
        planned_at=NOW,
    )

    assert plan.decision_ready is False
    assert _alternative(
        plan,
        RebalanceAlternativeKind.NO_ACTION,
    ).status == RebalanceAlternativeStatus.PREFERRED
    assert _alternative(
        plan,
        RebalanceAlternativeKind.CASH_FIRST,
    ).status == RebalanceAlternativeStatus.BLOCKED


def test_abstaining_source_decision_blocks_rebalancing() -> None:
    analytics = _analytics()
    decision = _decision(analytics).model_copy(
        update={"abstain": True, "recommendation_ready": False}
    )
    plan = build_threshold_rebalance_plan(
        analytics,
        decision,
        _bands(),
        currency="RUB",
        planned_at=NOW,
    )

    assert plan.decision_ready is False
    assert plan.preferred_alternative_id == "rebalance.no_action"


def test_currency_mismatch_and_excess_cash_fail_closed() -> None:
    analytics = _analytics()
    with pytest.raises(
        RebalancingEngineError,
        match="TARGET_BAND_CURRENCY_MISMATCH",
    ):
        build_threshold_rebalance_plan(
            analytics,
            _decision(analytics),
            (
                _bands()[0].model_copy(update={"currency": "USD"}),
                _bands()[1],
            ),
            currency="RUB",
            planned_at=NOW,
        )

    with pytest.raises(
        RebalancingEngineError,
        match="DEPLOYABLE_CASH_EXCEEDS_PORTFOLIO_CASH",
    ):
        build_threshold_rebalance_plan(
            analytics,
            _decision(analytics),
            _bands(),
            currency="RUB",
            deployable_cash=Decimal("201"),
            planned_at=NOW,
        )


def test_target_band_rejects_invalid_range() -> None:
    with pytest.raises(ValidationError, match="target weight must be inside"):
        TargetBandV1(
            stable_key=KEY_A,
            currency="RUB",
            lower_weight=Decimal("0.5"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
        )


def test_rebalance_line_rejects_inconsistent_direction() -> None:
    with pytest.raises(ValidationError, match="below-band line must be add-only"):
        RebalanceLineV1(
            stable_key=KEY_A,
            currency="RUB",
            current_value=Decimal("300"),
            current_weight=Decimal("0.3"),
            lower_weight=Decimal("0.35"),
            target_weight=Decimal("0.4"),
            upper_weight=Decimal("0.45"),
            band_status=RebalanceBandStatus.BELOW,
            direction=RebalanceDirection.REDUCE,
            deviation_from_target=Decimal("-0.1"),
            value_to_nearest_band=Decimal("50"),
            value_to_target=Decimal("100"),
            sale_required=False,
        )


def test_output_has_no_execution_fields() -> None:
    analytics = _analytics()
    plan = build_threshold_rebalance_plan(
        analytics,
        _decision(analytics),
        _bands(),
        currency="RUB",
        deployable_cash=Decimal("80"),
        planned_at=NOW,
    )
    payload = plan.model_dump(mode="json")

    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()

    forbidden = {
        "lots",
        "quantity",
        "order_id",
        "confirmation_id",
        "idempotency_key",
        "limit_price",
    }
    assert not (keys(payload) & forbidden)
    assert plan.execution_ready is False
    assert plan.trading_methods is False
