from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionEvidenceV1,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionOptionV1,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_journal import DecisionJournalAction
from omni_cio.contracts.v1.investment_policy import (
    InvestmentObjective,
    PolicyReferenceV1,
)
from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionAttemptV1,
    PlanExecutionInstrumentStateV1,
    PlanExecutionSessionV1,
    PlanExecutionStageV1,
)
from omni_cio.contracts.v1.portfolio_plan import PortfolioPlanV1
from omni_cio.contracts.v1.portfolio_risk import (
    ConcentrationSummaryV1,
    PortfolioRiskAssessmentV1,
    PortfolioRiskStateV1,
)
from omni_cio.decision_journal import (
    DecisionJournalRecorderError,
    InMemoryDecisionJournalV1,
    build_production_decision_record,
    record_production_decision,
)


NOW = datetime(2026, 8, 4, 19, 0, tzinfo=timezone.utc)
POLICY = PolicyReferenceV1(
    policy_id="ips_owner_v9",
    version="1",
    fingerprint_sha256="9" * 64,
)


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="decision_set",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***1234"),
        provenance=(
            SourceReference(
                provider="fixture",
                operation="decision",
                retrieved_at=NOW,
                source_id="decision-recorder-test",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _decision(*, change: bool = False) -> DecisionSetV1:
    evidence = DecisionEvidenceV1(
        evidence_id="fact.portfolio",
        kind=DecisionEvidenceKind.FACT,
        statement="Portfolio evidence is available.",
        source_schema="portfolio_risk_assessment",
    )
    no_action = DecisionOptionV1(
        option_id="no_action",
        kind=DecisionOptionKind.NO_ACTION,
        status=(
            DecisionOptionStatus.AVAILABLE
            if change
            else DecisionOptionStatus.PREFERRED
        ),
        action=DecisionAction.HOLD,
        title="Hold",
        rationale="No portfolio change is required.",
        confidence=DecisionConfidence.HIGH,
        evidence_ids=(evidence.evidence_id,),
    )
    limited = DecisionOptionV1(
        option_id="limited_change",
        kind=DecisionOptionKind.LIMITED_CHANGE,
        status=(
            DecisionOptionStatus.PREFERRED
            if change
            else DecisionOptionStatus.AVAILABLE
        ),
        action=DecisionAction.REVIEW_LIMITED_CHANGE,
        title="Review limited change",
        rationale="A bounded change can be reviewed.",
        confidence=DecisionConfidence.HIGH,
        evidence_ids=(evidence.evidence_id,),
    )
    strategic = DecisionOptionV1(
        option_id="strategic_rebalance",
        kind=DecisionOptionKind.STRATEGIC_REBALANCE,
        status=DecisionOptionStatus.AVAILABLE,
        action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
        title="Strategic review",
        rationale="Strategic rebalance remains review-only.",
        confidence=DecisionConfidence.MEDIUM,
        evidence_ids=(evidence.evidence_id,),
    )
    return DecisionSetV1(
        metadata=_metadata(),
        evidence=(evidence,),
        options=(no_action, limited, strategic),
        preferred_option_id=limited.option_id if change else no_action.option_id,
        abstain=False,
        recommendation_ready=True,
        confidence=DecisionConfidence.HIGH,
        global_blockers=(),
        accepted_news_count=1,
        context_news_count=1,
        rejected_news_count=0,
        required_market_count=1,
        market_coverage_count=1,
    )


def _state(*, top1: str, cash_weight: str) -> PortfolioRiskStateV1:
    return PortfolioRiskStateV1.model_construct(
        total_value_base=Decimal("1000000"),
        cash_base=Decimal("100000"),
        cash_weight=Decimal(cash_weight),
        concentration=ConcentrationSummaryV1.model_construct(
            top_1_weight=Decimal(top1),
            top_3_weight=Decimal(top1),
            top_5_weight=Decimal(top1),
            rows=(),
        ),
        liquidity=(),
        stress=(),
        vectors=(),
        blockers=(),
        policy_compliant=True,
    )


def _risk() -> PortfolioRiskAssessmentV1:
    return PortfolioRiskAssessmentV1.model_construct(
        assessed_at=NOW,
        portfolio_snapshot_sha256="a" * 64,
        policy_reference=POLICY,
        before=_state(top1="0.40", cash_weight="0.10"),
        after=_state(top1="0.30", cash_weight="0.15"),
        proposed_trade_ids=(),
        new_blockers=(),
        resolved_blockers=(),
        decision_ready=True,
        plan_eligible=True,
        assessment_sha256="b" * 64,
        trading_methods=False,
    )


def _plan(risk: PortfolioRiskAssessmentV1) -> PortfolioPlanV1:
    return PortfolioPlanV1.model_construct(
        policy_reference=POLICY,
        portfolio_snapshot_sha256=risk.portfolio_snapshot_sha256,
        current_risk_assessment_sha256=risk.assessment_sha256,
        strategy_selection_sha256="c" * 64,
        optimizer_sha256="d" * 64,
        plan_sha256="e" * 64,
        risk_before=risk.before,
        risk_after=risk.after,
        total_commission_base=Decimal("250"),
        execution_authorized=False,
        trading_methods=False,
    )


def _execution(
    plan: PortfolioPlanV1,
    *,
    owner_approved: bool,
    executed_lots: int = 0,
) -> PlanExecutionSessionV1:
    instrument_states: tuple[PlanExecutionInstrumentStateV1, ...] = ()
    if executed_lots:
        attempt = PlanExecutionAttemptV1.model_construct(lots_executed=executed_lots)
        stage = PlanExecutionStageV1.model_construct(attempts=(attempt,))
        instrument = PlanExecutionInstrumentStateV1.model_construct(stages=(stage,))
        instrument_states = (instrument,)
    return PlanExecutionSessionV1.model_construct(
        execution_id="f" * 64,
        plan_sha256=plan.plan_sha256,
        owner_approved=owner_approved,
        instrument_states=instrument_states,
        execution_authorized=False,
        trading_methods=False,
    )


def test_production_recorder_binds_decision_and_risk_deterministically() -> None:
    decision = _decision()
    risk = _risk()

    first = build_production_decision_record(
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
    )
    second = build_production_decision_record(
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
    )

    assert first == second
    assert first.selected_action is DecisionJournalAction.HOLD
    assert first.portfolio_snapshot_sha256 == risk.portfolio_snapshot_sha256
    assert first.risk_assessment_sha256 == risk.assessment_sha256
    assert first.starting_value_base == Decimal("1000000")
    assert first.baseline_top1_weight == Decimal("0.40")
    assert first.baseline_cash_weight == Decimal("0.10")
    assert first.research_items_expected == 3
    assert first.research_items_available == 3
    assert first.data_complete_at_decision is True
    assert first.full_account_identifier_present is False
    assert first.raw_private_payload_present is False
    assert first.execution_authorized is False
    assert first.trading_methods is False


def test_plan_and_owner_approved_execution_bind_exact_existing_sha_chain() -> None:
    decision = _decision(change=True)
    risk = _risk()
    plan = _plan(risk)
    execution = _execution(plan, owner_approved=True)

    record = build_production_decision_record(
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
        plan=plan,
        execution=execution,
    )

    assert record.selected_action is DecisionJournalAction.APPROVED_PLAN
    assert record.strategy_selection_sha256 == plan.strategy_selection_sha256
    assert record.optimizer_sha256 == plan.optimizer_sha256
    assert record.plan_sha256 == plan.plan_sha256
    assert record.execution_id == execution.execution_id
    assert record.target_top1_weight == Decimal("0.30")
    assert record.target_cash_weight == Decimal("0.15")
    assert record.expected_execution_cost_base == Decimal("250")


def test_executed_lots_are_recorded_only_with_owner_approval() -> None:
    decision = _decision(change=True)
    risk = _risk()
    plan = _plan(risk)

    executed = build_production_decision_record(
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
        plan=plan,
        execution=_execution(plan, owner_approved=True, executed_lots=1),
    )
    assert executed.selected_action is DecisionJournalAction.EXECUTED_PLAN

    with pytest.raises(
        DecisionJournalRecorderError,
        match="EXECUTED_LOTS_REQUIRE_OWNER_APPROVAL",
    ):
        build_production_decision_record(
            decision,
            risk,
            policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
            horizon_days=30,
            recorded_at=NOW,
            plan=plan,
            execution=_execution(plan, owner_approved=False, executed_lots=1),
        )


def test_recorder_fails_closed_on_cross_version_plan_binding() -> None:
    decision = _decision(change=True)
    risk = _risk()
    plan = _plan(risk).model_copy(
        update={"current_risk_assessment_sha256": "7" * 64}
    )

    with pytest.raises(DecisionJournalRecorderError, match="PLAN_RISK_BINDING_MISMATCH"):
        build_production_decision_record(
            decision,
            risk,
            policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
            horizon_days=30,
            recorded_at=NOW,
            plan=plan,
        )


def test_record_production_decision_is_append_only_and_idempotent() -> None:
    journal = InMemoryDecisionJournalV1()
    decision = _decision()
    risk = _risk()

    first = record_production_decision(
        journal,
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
    )
    second = record_production_decision(
        journal,
        decision,
        risk,
        policy_objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        horizon_days=30,
        recorded_at=NOW,
    )

    assert first == second
    assert journal.integrity_check() == (1, 0, 0)
