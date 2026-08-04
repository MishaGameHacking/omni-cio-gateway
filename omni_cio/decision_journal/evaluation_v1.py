from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from omni_cio.contracts.v1.decision_journal import (
    BenchmarkAvailability,
    DecisionEvaluationRecordV1,
    DecisionJournalRecordV1,
    DecisionOutcomeRecordV1,
    EvaluationCompleteness,
    decision_evaluation_record_id,
    decision_evaluation_record_sha256,
    decision_journal_record_id,
    decision_journal_record_sha256,
    decision_outcome_record_id,
    decision_outcome_record_sha256,
)


class DecisionEvaluationError(ValueError):
    """WP14 decision/outcome evidence cannot be evaluated deterministically."""


def _aware_utc(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise DecisionEvaluationError("DECISION_EVALUATION_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _required_utc(value: object, *, code: str) -> datetime:
    if not isinstance(value, datetime):
        raise DecisionEvaluationError(code)
    if value.tzinfo is None or value.utcoffset() is None:
        raise DecisionEvaluationError(code)
    return value.astimezone(timezone.utc)


def _canonical_hashes(value: object, *, code: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise DecisionEvaluationError(code)
    result = tuple(sorted(set(value)))
    if not result:
        raise DecisionEvaluationError(code)
    return result


def finalize_decision_record(values: Mapping[str, object]) -> DecisionJournalRecordV1:
    """Create one immutable decision record with canonical identity and digest."""

    payload = dict(values)
    payload["recorded_at"] = _required_utc(
        payload.get("recorded_at"),
        code="DECISION_JOURNAL_TIMESTAMP_MUST_BE_AWARE",
    )
    payload["evidence_sha256s"] = _canonical_hashes(
        payload.get("evidence_sha256s"),
        code="DECISION_JOURNAL_EVIDENCE_REQUIRED",
    )
    payload["decision_id"] = "0" * 64
    payload["record_sha256"] = "0" * 64
    provisional = DecisionJournalRecordV1.model_construct(**payload)
    payload["decision_id"] = decision_journal_record_id(provisional)
    with_identity = DecisionJournalRecordV1.model_construct(**payload)
    payload["record_sha256"] = decision_journal_record_sha256(with_identity)
    return DecisionJournalRecordV1.model_validate(payload)


def finalize_outcome_record(values: Mapping[str, object]) -> DecisionOutcomeRecordV1:
    """Create one immutable realized-outcome record without touching the decision."""

    payload = dict(values)
    payload["observed_at"] = _required_utc(
        payload.get("observed_at"),
        code="DECISION_OUTCOME_TIMESTAMP_MUST_BE_AWARE",
    )
    payload["source_sha256s"] = _canonical_hashes(
        payload.get("source_sha256s"),
        code="DECISION_OUTCOME_SOURCES_REQUIRED",
    )
    payload["outcome_id"] = "0" * 64
    payload["outcome_sha256"] = "0" * 64
    provisional = DecisionOutcomeRecordV1.model_construct(**payload)
    payload["outcome_id"] = decision_outcome_record_id(provisional)
    with_identity = DecisionOutcomeRecordV1.model_construct(**payload)
    payload["outcome_sha256"] = decision_outcome_record_sha256(with_identity)
    return DecisionOutcomeRecordV1.model_validate(payload)


def _research_coverage(
    decision: DecisionJournalRecordV1,
    outcome: DecisionOutcomeRecordV1,
) -> Decimal:
    expected = decision.research_items_expected
    if expected == 0:
        return Decimal("1")
    covered = min(outcome.research_items_covered, expected)
    return Decimal(covered) / Decimal(expected)


def _bps_delta(after: Decimal, before: Decimal) -> Decimal:
    return (after - before) * Decimal("10000")


def evaluate_decision(
    decision: DecisionJournalRecordV1,
    outcome: DecisionOutcomeRecordV1,
    *,
    evaluated_at: datetime | None = None,
) -> DecisionEvaluationRecordV1:
    """Compare frozen decision-time state with a separately recorded outcome.

    This function cannot mutate the source decision and does not invent a
    counterfactual. NO_ACTION and policy benchmarks are evaluated only when the
    outcome record contains an evidence-bound benchmark value.
    """

    if outcome.decision_id != decision.decision_id:
        raise DecisionEvaluationError("DECISION_OUTCOME_IDENTITY_MISMATCH")
    if outcome.horizon_days != decision.horizon_days:
        raise DecisionEvaluationError("DECISION_OUTCOME_HORIZON_MISMATCH")
    if outcome.observed_at < decision.recorded_at:
        raise DecisionEvaluationError("DECISION_OUTCOME_PRECEDES_DECISION")

    evaluated = _aware_utc(evaluated_at)
    if evaluated < outcome.observed_at:
        raise DecisionEvaluationError("DECISION_EVALUATION_PRECEDES_OUTCOME")

    external_flow = outcome.net_external_flow_base
    realized = outcome.ending_value_base - decision.starting_value_base - external_flow

    no_action_result: Decimal | None = None
    no_action_excess: Decimal | None = None
    no_action_availability = BenchmarkAvailability.UNAVAILABLE
    if outcome.no_action_ending_value_base is not None:
        no_action_result = (
            outcome.no_action_ending_value_base
            - decision.starting_value_base
            - external_flow
        )
        no_action_excess = realized - no_action_result
        no_action_availability = BenchmarkAvailability.AVAILABLE

    policy_result: Decimal | None = None
    policy_excess: Decimal | None = None
    policy_availability = BenchmarkAvailability.UNAVAILABLE
    if outcome.policy_benchmark_ending_value_base is not None:
        policy_result = (
            outcome.policy_benchmark_ending_value_base
            - decision.starting_value_base
            - external_flow
        )
        policy_excess = realized - policy_result
        policy_availability = BenchmarkAvailability.AVAILABLE

    concentration_reduction: Decimal | None = None
    if (
        decision.baseline_top1_weight is not None
        and outcome.ending_top1_weight is not None
    ):
        concentration_reduction = _bps_delta(
            decision.baseline_top1_weight,
            outcome.ending_top1_weight,
        )

    cash_delta: Decimal | None = None
    if decision.baseline_cash_weight is not None and outcome.ending_cash_weight is not None:
        cash_delta = _bps_delta(
            outcome.ending_cash_weight,
            decision.baseline_cash_weight,
        )

    execution_variance: Decimal | None = None
    if (
        decision.expected_execution_cost_base is not None
        and outcome.execution_cost_base is not None
    ):
        execution_variance = (
            outcome.execution_cost_base - decision.expected_execution_cost_base
        )

    completeness = (
        EvaluationCompleteness.COMPLETE
        if decision.data_complete_at_decision
        and outcome.data_completeness_ratio == Decimal("1")
        else EvaluationCompleteness.PARTIAL
    )

    values: dict[str, object] = {
        "schema_version": "1.0",
        "object_type": "DECISION_EVALUATION_RECORD",
        "evaluation_id": "0" * 64,
        "decision_id": decision.decision_id,
        "decision_record_sha256": decision.record_sha256,
        "outcome_record_sha256": outcome.outcome_sha256,
        "evaluated_at": evaluated,
        "completeness": completeness,
        "realized_period_result_base": realized,
        "no_action_availability": no_action_availability,
        "no_action_period_result_base": no_action_result,
        "excess_vs_no_action_base": no_action_excess,
        "policy_benchmark_availability": policy_availability,
        "policy_benchmark_period_result_base": policy_result,
        "excess_vs_policy_benchmark_base": policy_excess,
        "data_completeness_ratio": outcome.data_completeness_ratio,
        "research_coverage_ratio": _research_coverage(decision, outcome),
        "concentration_reduction_bps": concentration_reduction,
        "cash_weight_delta_bps": cash_delta,
        "execution_cost_variance_base": execution_variance,
        "execution_slippage_bps": outcome.execution_slippage_bps,
        "evaluation_sha256": "0" * 64,
        "expectations_rewritten": False,
        "counterfactual_fabricated": False,
        "production_rules_modified": False,
        "execution_authorized": False,
        "trading_methods": False,
    }
    provisional = DecisionEvaluationRecordV1.model_construct(**values)
    values["evaluation_id"] = decision_evaluation_record_id(provisional)
    with_identity = DecisionEvaluationRecordV1.model_construct(**values)
    values["evaluation_sha256"] = decision_evaluation_record_sha256(with_identity)
    return DecisionEvaluationRecordV1.model_validate(values)
