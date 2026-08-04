from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.decision_journal import (
    BenchmarkAvailability,
    DecisionJournalAction,
    EvaluationCompleteness,
    RegressionArtifactKind,
    RegressionPredictionV1,
    ReplaySourceKind,
)
from omni_cio.contracts.v1.investment_policy import (
    InvestmentObjective,
    PolicyReferenceV1,
)
from omni_cio.decision_journal import (
    DecisionJournalConflict,
    InMemoryDecisionJournalV1,
    build_replay_case,
    build_replay_dataset,
    evaluate_decision,
    evaluate_regression_candidate,
    finalize_decision_record,
    finalize_outcome_record,
)


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
POLICY = PolicyReferenceV1(
    policy_id="ips_owner_v9",
    version="1",
    fingerprint_sha256="1" * 64,
)


def _decision(*, action: DecisionJournalAction = DecisionJournalAction.HOLD):
    return finalize_decision_record(
        {
            "recorded_at": NOW,
            "horizon_days": 30,
            "policy_reference": POLICY,
            "policy_objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
            "portfolio_snapshot_sha256": "2" * 64,
            "decision_set_sha256": "3" * 64,
            "evidence_sha256s": ("5" * 64, "4" * 64, "5" * 64),
            "risk_assessment_sha256": "6" * 64,
            "strategy_selection_sha256": "7" * 64,
            "optimizer_sha256": "8" * 64,
            "selected_action": action,
            "starting_value_base": Decimal("1000000"),
            "baseline_top1_weight": Decimal("0.40"),
            "baseline_cash_weight": Decimal("0.10"),
            "target_top1_weight": Decimal("0.30"),
            "target_cash_weight": Decimal("0.15"),
            "expected_execution_cost_base": Decimal("1000"),
            "research_items_expected": 10,
            "research_items_available": 10,
            "data_complete_at_decision": True,
        }
    )


def _outcome(decision_id: str, *, include_benchmarks: bool = True):
    values: dict[str, object] = {
        "decision_id": decision_id,
        "observed_at": NOW + timedelta(days=30),
        "horizon_days": 30,
        "ending_value_base": Decimal("1050000"),
        "net_external_flow_base": Decimal("20000"),
        "ending_top1_weight": Decimal("0.30"),
        "ending_cash_weight": Decimal("0.15"),
        "execution_cost_base": Decimal("1200"),
        "execution_slippage_bps": Decimal("7.5"),
        "research_items_observed": 10,
        "research_items_covered": 8,
        "data_completeness_ratio": Decimal("1"),
        "source_sha256s": ("b" * 64, "a" * 64),
    }
    if include_benchmarks:
        values.update(
            {
                "no_action_ending_value_base": Decimal("1040000"),
                "no_action_source_sha256": "c" * 64,
                "policy_benchmark_ending_value_base": Decimal("1045000"),
                "policy_benchmark_source_sha256": "d" * 64,
            }
        )
    return finalize_outcome_record(values)


def test_immutable_journal_is_append_only_and_idempotent() -> None:
    decision = _decision()
    journal = InMemoryDecisionJournalV1()

    assert journal.put_decision(decision) == decision
    assert journal.put_decision(decision) == decision
    assert journal.get_decision(decision.decision_id) == decision

    conflicting = decision.model_copy(update={"starting_value_base": Decimal("999999")})
    with pytest.raises(DecisionJournalConflict, match="append-only"):
        journal.put_decision(conflicting)

    assert journal.integrity_check() == (1, 0, 0)


def test_outcome_and_evaluation_bind_exact_immutable_decision() -> None:
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    evaluation = evaluate_decision(
        decision,
        outcome,
        evaluated_at=outcome.observed_at,
    )

    assert evaluation.completeness is EvaluationCompleteness.COMPLETE
    assert evaluation.realized_period_result_base == Decimal("30000")
    assert evaluation.no_action_period_result_base == Decimal("20000")
    assert evaluation.excess_vs_no_action_base == Decimal("10000")
    assert evaluation.policy_benchmark_period_result_base == Decimal("25000")
    assert evaluation.excess_vs_policy_benchmark_base == Decimal("5000")
    assert evaluation.research_coverage_ratio == Decimal("0.8")
    assert evaluation.concentration_reduction_bps == Decimal("1000")
    assert evaluation.cash_weight_delta_bps == Decimal("500")
    assert evaluation.execution_cost_variance_base == Decimal("200")
    assert evaluation.execution_slippage_bps == Decimal("7.5")
    assert evaluation.expectations_rewritten is False
    assert evaluation.counterfactual_fabricated is False
    assert evaluation.production_rules_modified is False

    journal = InMemoryDecisionJournalV1()
    journal.put_decision(decision)
    journal.put_outcome(outcome)
    journal.put_evaluation(evaluation)
    assert journal.integrity_check() == (1, 1, 1)


def test_missing_counterfactuals_remain_explicitly_unavailable() -> None:
    decision = _decision()
    outcome = _outcome(decision.decision_id, include_benchmarks=False)
    evaluation = evaluate_decision(decision, outcome, evaluated_at=outcome.observed_at)

    assert evaluation.no_action_availability is BenchmarkAvailability.UNAVAILABLE
    assert evaluation.no_action_period_result_base is None
    assert evaluation.excess_vs_no_action_base is None
    assert evaluation.policy_benchmark_availability is BenchmarkAvailability.UNAVAILABLE
    assert evaluation.policy_benchmark_period_result_base is None
    assert evaluation.excess_vs_policy_benchmark_base is None
    assert evaluation.counterfactual_fabricated is False


def test_outcome_cannot_precede_immutable_decision_record() -> None:
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    journal = InMemoryDecisionJournalV1()

    with pytest.raises(DecisionJournalConflict, match="cannot precede"):
        journal.put_outcome(outcome)


def test_sanitized_replay_dataset_and_regression_gate_are_deterministic() -> None:
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    evaluation = evaluate_decision(decision, outcome, evaluated_at=outcome.observed_at)
    case = build_replay_case(decision, outcome, evaluation)

    dataset = build_replay_dataset(
        (case,),
        source_kind=ReplaySourceKind.SYNTHETIC,
        generated_at=NOW + timedelta(days=31),
    )
    assert dataset.full_account_identifier_present is False
    assert dataset.raw_private_payload_present is False
    assert dataset.secrets_present is False
    assert dataset.production_write_capable is False

    matching = RegressionPredictionV1(
        case_id=case.case_id,
        action=DecisionJournalAction.HOLD,
        abstain=False,
    )
    regressed = RegressionPredictionV1(
        case_id=case.case_id,
        action=DecisionJournalAction.NO_ACTION,
        abstain=False,
    )
    result = evaluate_regression_candidate(
        dataset,
        artifact_kind=RegressionArtifactKind.PROMPT,
        baseline_artifact_sha256="e" * 64,
        candidate_artifact_sha256="f" * 64,
        baseline_predictions=(matching,),
        candidate_predictions=(regressed,),
        evaluated_at=NOW + timedelta(days=32),
    )
    assert result.baseline_match_count == 1
    assert result.candidate_match_count == 0
    assert result.regression_case_ids == (case.case_id,)
    assert result.candidate_ready_for_review is False
    assert result.production_change_applied is False
    assert result.self_modification_authorized is False


def test_sanitized_production_replay_requires_explicit_sanitization() -> None:
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    evaluation = evaluate_decision(decision, outcome, evaluated_at=outcome.observed_at)
    case = build_replay_case(decision, outcome, evaluation)

    with pytest.raises(ValueError, match="explicit sanitization"):
        build_replay_dataset(
            (case,),
            source_kind=ReplaySourceKind.SANITIZED_PRODUCTION,
            sanitization_confirmed=False,
            generated_at=NOW + timedelta(days=31),
        )
