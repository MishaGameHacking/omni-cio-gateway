from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1 import (
    AccountReference,
    AdvancedPortfolioAnalyticsV1,
    AssetClassAllocationV1,
    Completeness,
    ConcentrationMetricsV1,
    ContractMetadata,
    CurrencyPortfolioAnalyticsV1,
    DataQuality,
    DecisionAction,
    DecisionBlocker,
    DecisionConfidence,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionSetV1,
    EntityResolutionStatus,
    InstrumentMarketReadinessV1,
    InstrumentType,
    MarketAssessmentStatus,
    MarketReadinessAssessmentV1,
    NewsContentFormat,
    NewsContentKind,
    NewsDocumentInputV1,
    PositionWeightV1,
    QualityMetadata,
    RiskCheckCode,
    RiskCheckStatus,
    RiskCheckV1,
    RiskMissingInputCode,
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
    RiskSeverity,
    SourceAuthority,
    SourceReference,
)
from omni_cio.decision import DecisionEngineError, build_decision_set
from omni_cio.news import sanitize_news_document
from omni_cio.risk import default_conservative_risk_policy


NOW = datetime(2026, 7, 28, 21, 30, tzinfo=timezone.utc)
POSITION_KEY = "uid:synthetic-share"


def _metadata(schema_name: str, *, verified: bool = True) -> ContractMetadata:
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
            quality=(DataQuality.VERIFIED if verified else DataQuality.PARTIAL),
            completeness=(
                Completeness.COMPLETE if verified else Completeness.PARTIAL
            ),
        ),
    )


def _analytics(*, with_position: bool = False) -> AdvancedPortfolioAnalyticsV1:
    if not with_position:
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
            stable_key=POSITION_KEY,
            name="Synthetic share",
            ticker="SYNTH",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            full_market_value=Decimal("100"),
            portfolio_weight=Decimal("0.1"),
            invested_weight=Decimal("1"),
        )
        currency = CurrencyPortfolioAnalyticsV1(
            currency="RUB",
            cash=Decimal("900"),
            clean_securities=Decimal("100"),
            accrued_interest=Decimal("0"),
            invested_value=Decimal("100"),
            total=Decimal("1000"),
            cash_weight=Decimal("0.9"),
            invested_weight=Decimal("0.1"),
            position_count=1,
            valued_position_count=1,
            positions=(position,),
            asset_classes=(
                AssetClassAllocationV1(
                    instrument_type=InstrumentType.SHARE,
                    full_market_value=Decimal("100"),
                    position_count=1,
                    portfolio_weight=Decimal("0.1"),
                    invested_weight=Decimal("1"),
                ),
            ),
            concentration=ConcentrationMetricsV1(
                top_1_portfolio_weight=Decimal("0.1"),
                top_5_portfolio_weight=Decimal("0.1"),
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


def _risk(*, warning: bool = False, ready: bool = True) -> RiskPolicyEvaluationV1:
    policy = default_conservative_risk_policy()
    if ready and warning:
        checks = (
            RiskCheckV1(
                check_id="currency.rub.top5",
                code=RiskCheckCode.TOP5_CONCENTRATION,
                status=RiskCheckStatus.WARNING,
                severity=RiskSeverity.WARNING,
                message="Top-five invested concentration is elevated.",
                currency="RUB",
                observed_value=Decimal("0.9"),
                limit_value=Decimal("0.8"),
            ),
        )
        return RiskPolicyEvaluationV1(
            metadata=_metadata("risk_policy_evaluation"),
            policy=policy,
            overall_status=RiskOverallStatus.WARNING,
            decision_ready=True,
            checks=checks,
            breach_count=0,
            warning_count=1,
            unknown_count=0,
            no_cross_currency_aggregation=True,
        )
    if ready:
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

    checks = (
        RiskCheckV1(
            check_id="missing_inputs.issuer",
            code=RiskCheckCode.ISSUER_WEIGHT,
            status=RiskCheckStatus.UNKNOWN,
            severity=RiskSeverity.BLOCK,
            message="Issuer identity is unavailable.",
            missing_data=(RiskMissingInputCode.ISSUER,),
        ),
    )
    return RiskPolicyEvaluationV1(
        metadata=_metadata("risk_policy_evaluation", verified=False),
        policy=policy,
        overall_status=RiskOverallStatus.UNKNOWN,
        decision_ready=False,
        checks=checks,
        breach_count=0,
        warning_count=0,
        unknown_count=1,
        no_cross_currency_aggregation=True,
    )


def _market(*, ready: bool = True) -> InstrumentMarketReadinessV1:
    assessment = MarketReadinessAssessmentV1(
        assessed_at=NOW,
        status=(
            MarketAssessmentStatus.READY
            if ready
            else MarketAssessmentStatus.PARTIAL
        ),
        decision_ready=ready,
        stale_components=(() if ready else ("quote",)),
        missing_components=(),
        untrusted_components=(),
    )
    return InstrumentMarketReadinessV1(
        instrument_key=POSITION_KEY,
        assessment=assessment,
    )


def _news(
    *,
    document_id: str,
    authority: SourceAuthority = SourceAuthority.PRIMARY,
    body: str = "The issuer published verified operating results.",
    title: str = "Operating results",
):
    return sanitize_news_document(
        NewsDocumentInputV1(
            document_id=document_id,
            publisher="Synthetic publisher",
            authority=authority,
            published_at=NOW,
            retrieved_at=NOW,
            event_at=NOW,
            title=title,
            raw_content=body,
            content_format=NewsContentFormat.PLAIN_TEXT,
            content_kind=NewsContentKind.FACT,
            entity_resolution=EntityResolutionStatus.RESOLVED,
            instrument_key=POSITION_KEY,
            source_record_id=document_id,
        )
    )


def _option(result: DecisionSetV1, kind: DecisionOptionKind):
    return next(option for option in result.options if option.kind == kind)


def test_cash_only_clean_state_prefers_hold_and_keeps_three_options() -> None:
    result = build_decision_set(
        _analytics(),
        _risk(),
        decided_at=NOW,
    )

    assert result.abstain is False
    assert result.recommendation_ready is True
    assert result.confidence == DecisionConfidence.MEDIUM
    assert len(result.options) == 3
    preferred = _option(result, DecisionOptionKind.NO_ACTION)
    assert preferred.status == DecisionOptionStatus.PREFERRED
    assert preferred.action == DecisionAction.HOLD
    assert result.preferred_option_id == preferred.option_id
    assert _option(
        result,
        DecisionOptionKind.STRATEGIC_REBALANCE,
    ).status == DecisionOptionStatus.REVIEW_ONLY
    assert result.trading_methods is False


def test_verified_risk_warning_prefers_limited_review() -> None:
    result = build_decision_set(
        _analytics(with_position=True),
        _risk(warning=True),
        market_states=(_market(),),
        news_documents=(_news(document_id="issuer-fact"),),
        decided_at=NOW,
    )

    assert result.abstain is False
    assert result.confidence == DecisionConfidence.MEDIUM
    limited = _option(result, DecisionOptionKind.LIMITED_CHANGE)
    assert limited.status == DecisionOptionStatus.PREFERRED
    assert limited.action == DecisionAction.REVIEW_LIMITED_CHANGE
    assert any(row.evidence_id == "risk.currency.rub.top5" for row in result.evidence)
    assert result.accepted_news_count == 1
    assert result.market_coverage_count == 1


def test_risk_unknown_forces_wait_for_data() -> None:
    result = build_decision_set(
        _analytics(),
        _risk(ready=False),
        decided_at=NOW,
    )

    assert result.abstain is True
    assert result.recommendation_ready is False
    assert result.confidence == DecisionConfidence.LOW
    assert DecisionBlocker.RISK_NOT_READY in result.global_blockers
    preferred = _option(result, DecisionOptionKind.NO_ACTION)
    assert preferred.status == DecisionOptionStatus.PREFERRED
    assert preferred.action == DecisionAction.WAIT_FOR_DATA
    assert _option(result, DecisionOptionKind.LIMITED_CHANGE).status == (
        DecisionOptionStatus.BLOCKED
    )


def test_missing_or_stale_market_blocks_position_decision() -> None:
    missing = build_decision_set(
        _analytics(with_position=True),
        _risk(),
        decided_at=NOW,
    )
    assert DecisionBlocker.MARKET_COVERAGE_INCOMPLETE in missing.global_blockers
    assert missing.required_market_count == 1
    assert missing.market_coverage_count == 0

    stale = build_decision_set(
        _analytics(with_position=True),
        _risk(),
        market_states=(_market(ready=False),),
        decided_at=NOW,
    )
    assert DecisionBlocker.MARKET_NOT_READY in stale.global_blockers
    assert stale.market_coverage_count == 0


def test_context_only_news_cannot_be_sole_news_evidence() -> None:
    result = build_decision_set(
        _analytics(),
        _risk(),
        news_documents=(
            _news(
                document_id="secondary-copy",
                authority=SourceAuthority.SECONDARY,
            ),
        ),
        decided_at=NOW,
    )

    assert result.abstain is True
    assert DecisionBlocker.NEWS_EVIDENCE_UNUSABLE in result.global_blockers
    assert result.accepted_news_count == 0
    assert result.context_news_count == 1


def test_accepted_and_context_news_can_coexist() -> None:
    result = build_decision_set(
        _analytics(),
        _risk(),
        news_documents=(
            _news(document_id="official-fact"),
            _news(
                document_id="secondary-copy",
                authority=SourceAuthority.SECONDARY,
            ),
        ),
        decided_at=NOW,
    )

    assert result.abstain is False
    assert result.confidence == DecisionConfidence.HIGH
    assert result.accepted_news_count == 1
    assert result.context_news_count == 1


def test_contradictory_accepted_news_for_same_event_forces_abstain() -> None:
    first = _news(
        document_id="event-a",
        body="The issuer reported revenue growth.",
    )
    second = _news(
        document_id="event-b",
        body="The issuer reported a revenue decline.",
    )
    assert first.event_cluster_id == second.event_cluster_id
    assert first.content_fingerprint != second.content_fingerprint

    result = build_decision_set(
        _analytics(),
        _risk(),
        news_documents=(first, second),
        decided_at=NOW,
    )

    assert result.abstain is True
    assert DecisionBlocker.NEWS_CONTRADICTION in result.global_blockers


def test_duplicate_market_keys_fail_closed() -> None:
    with pytest.raises(
        DecisionEngineError,
        match="DUPLICATE_MARKET_READINESS_INSTRUMENT",
    ):
        build_decision_set(
            _analytics(with_position=True),
            _risk(),
            market_states=(_market(), _market()),
            decided_at=NOW,
        )


def test_naive_decision_timestamp_is_rejected() -> None:
    with pytest.raises(
        DecisionEngineError,
        match="DECISION_TIMESTAMP_MUST_BE_AWARE",
    ):
        build_decision_set(
            _analytics(),
            _risk(),
            decided_at=datetime(2026, 7, 28, 21, 30),
        )


def test_bypassed_unready_portfolio_is_still_blocked() -> None:
    analytics = _analytics().model_copy(update={"decision_ready": False})

    result = build_decision_set(analytics, _risk(), decided_at=NOW)

    assert DecisionBlocker.PORTFOLIO_NOT_READY in result.global_blockers
    assert result.abstain is True


def test_decision_contract_rejects_strategic_preference() -> None:
    valid = build_decision_set(_analytics(), _risk(), decided_at=NOW)
    payload = valid.model_dump()
    for option in payload["options"]:
        option["status"] = (
            DecisionOptionStatus.PREFERRED
            if option["kind"] == DecisionOptionKind.STRATEGIC_REBALANCE
            else DecisionOptionStatus.AVAILABLE
        )
    payload["preferred_option_id"] = "option.strategic_rebalance"

    with pytest.raises(
        ValidationError,
        match="strategic rebalance cannot be preferred",
    ):
        DecisionSetV1.model_validate(payload)


def test_decision_output_contains_no_execution_parameters() -> None:
    result = build_decision_set(
        _analytics(with_position=True),
        _risk(warning=True),
        market_states=(_market(),),
        news_documents=(_news(document_id="safe-fact"),),
        decided_at=NOW,
    )
    serialized = result.model_dump(mode="json")

    forbidden = {
        "quantity",
        "lots",
        "price",
        "order_id",
        "idempotency_key",
        "confirmation_id",
    }
    serialized_text = str(serialized).lower()
    assert all(field not in serialized_text for field in forbidden)
    assert all(option.execution_ready is False for option in result.options)
