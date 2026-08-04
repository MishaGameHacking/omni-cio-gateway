from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Mapping

from omni_cio.contracts.v1.decision_journal import (
    BenchmarkAvailability,
    DecisionEvaluationRecordV1,
    DecisionJournalRecordV1,
    DecisionOutcomeRecordV1,
    DecisionReplayCaseV1,
    DecisionReplayDatasetV1,
    RegressionArtifactKind,
    RegressionEvaluationResultV1,
    RegressionPredictionV1,
    ReplaySourceKind,
    decision_replay_case_id,
    decision_replay_case_sha256,
    decision_replay_dataset_id,
    decision_replay_dataset_sha256,
    regression_evaluation_result_sha256,
)


class DecisionReplayError(ValueError):
    """Offline decision replay inputs are incomplete or unsafe."""


def _aware_utc(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise DecisionReplayError("REPLAY_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def build_replay_case(
    decision: DecisionJournalRecordV1,
    outcome: DecisionOutcomeRecordV1,
    evaluation: DecisionEvaluationRecordV1,
) -> DecisionReplayCaseV1:
    if outcome.decision_id != decision.decision_id:
        raise DecisionReplayError("REPLAY_OUTCOME_DECISION_MISMATCH")
    if evaluation.decision_id != decision.decision_id:
        raise DecisionReplayError("REPLAY_EVALUATION_DECISION_MISMATCH")
    if evaluation.decision_record_sha256 != decision.record_sha256:
        raise DecisionReplayError("REPLAY_DECISION_HASH_MISMATCH")
    if evaluation.outcome_record_sha256 != outcome.outcome_sha256:
        raise DecisionReplayError("REPLAY_OUTCOME_HASH_MISMATCH")

    no_action_outperformance: bool | None = None
    if evaluation.no_action_availability is BenchmarkAvailability.AVAILABLE:
        assert evaluation.excess_vs_no_action_base is not None
        no_action_outperformance = evaluation.excess_vs_no_action_base > 0

    values: dict[str, object] = {
        "case_id": "0" * 64,
        "decision_record_sha256": decision.record_sha256,
        "outcome_record_sha256": outcome.outcome_sha256,
        "evaluation_record_sha256": evaluation.evaluation_sha256,
        "expected_action": decision.selected_action,
        "expected_completeness": evaluation.completeness,
        "expected_no_action_outperformance": no_action_outperformance,
        "case_sha256": "0" * 64,
        "full_account_identifier_present": False,
        "raw_private_payload_present": False,
    }
    provisional = DecisionReplayCaseV1.model_construct(**values)
    values["case_id"] = decision_replay_case_id(provisional)
    with_identity = DecisionReplayCaseV1.model_construct(**values)
    values["case_sha256"] = decision_replay_case_sha256(with_identity)
    return DecisionReplayCaseV1.model_validate(values)


def build_replay_dataset(
    cases: Iterable[DecisionReplayCaseV1],
    *,
    source_kind: ReplaySourceKind,
    sanitization_confirmed: bool = False,
    generated_at: datetime | None = None,
) -> DecisionReplayDatasetV1:
    rows = tuple(sorted(cases, key=lambda row: row.case_id))
    if not rows:
        raise DecisionReplayError("REPLAY_DATASET_CASES_REQUIRED")
    values: dict[str, object] = {
        "schema_version": "1.0",
        "object_type": "DECISION_REPLAY_DATASET",
        "dataset_id": "0" * 64,
        "generated_at": _aware_utc(generated_at),
        "source_kind": source_kind,
        "sanitization_confirmed": sanitization_confirmed,
        "cases": rows,
        "dataset_sha256": "0" * 64,
        "full_account_identifier_present": False,
        "raw_private_payload_present": False,
        "secrets_present": False,
        "production_write_capable": False,
    }
    provisional = DecisionReplayDatasetV1.model_construct(**values)
    values["dataset_id"] = decision_replay_dataset_id(provisional)
    with_identity = DecisionReplayDatasetV1.model_construct(**values)
    values["dataset_sha256"] = decision_replay_dataset_sha256(with_identity)
    return DecisionReplayDatasetV1.model_validate(values)


def _prediction_map(
    rows: Iterable[RegressionPredictionV1],
    *,
    expected_case_ids: set[str],
    label: str,
) -> dict[str, RegressionPredictionV1]:
    result: dict[str, RegressionPredictionV1] = {}
    for row in rows:
        if row.case_id in result:
            raise DecisionReplayError(f"{label}_PREDICTION_CASE_DUPLICATE")
        result[row.case_id] = row
    if set(result) != expected_case_ids:
        raise DecisionReplayError(f"{label}_PREDICTION_CASE_COVERAGE_MISMATCH")
    return result


def evaluate_regression_candidate(
    dataset: DecisionReplayDatasetV1,
    *,
    artifact_kind: RegressionArtifactKind,
    baseline_artifact_sha256: str,
    candidate_artifact_sha256: str,
    baseline_predictions: Iterable[RegressionPredictionV1],
    candidate_predictions: Iterable[RegressionPredictionV1],
    evaluated_at: datetime | None = None,
) -> RegressionEvaluationResultV1:
    case_map = {row.case_id: row for row in dataset.cases}
    expected_ids = set(case_map)
    baseline = _prediction_map(
        baseline_predictions,
        expected_case_ids=expected_ids,
        label="BASELINE",
    )
    candidate = _prediction_map(
        candidate_predictions,
        expected_case_ids=expected_ids,
        label="CANDIDATE",
    )

    def matches(case_id: str, prediction: RegressionPredictionV1) -> bool:
        case = case_map[case_id]
        expected_abstain = case.expected_action.value == "wait_for_data"
        return (
            prediction.action is case.expected_action
            and prediction.abstain is expected_abstain
        )

    baseline_matches = {
        case_id for case_id, row in baseline.items() if matches(case_id, row)
    }
    candidate_matches = {
        case_id for case_id, row in candidate.items() if matches(case_id, row)
    }
    regressions = tuple(sorted(baseline_matches - candidate_matches))
    candidate_ready = not regressions and len(candidate_matches) >= len(baseline_matches)

    values: dict[str, object] = {
        "schema_version": "1.0",
        "object_type": "REGRESSION_EVALUATION_RESULT",
        "artifact_kind": artifact_kind,
        "baseline_artifact_sha256": baseline_artifact_sha256,
        "candidate_artifact_sha256": candidate_artifact_sha256,
        "dataset_sha256": dataset.dataset_sha256,
        "evaluated_at": _aware_utc(evaluated_at),
        "case_count": len(dataset.cases),
        "baseline_match_count": len(baseline_matches),
        "candidate_match_count": len(candidate_matches),
        "regression_case_ids": regressions,
        "candidate_ready_for_review": candidate_ready,
        "result_sha256": "0" * 64,
        "production_change_applied": False,
        "self_modification_authorized": False,
    }
    provisional = RegressionEvaluationResultV1.model_construct(**values)
    values["result_sha256"] = regression_evaluation_result_sha256(provisional)
    return RegressionEvaluationResultV1.model_validate(values)
