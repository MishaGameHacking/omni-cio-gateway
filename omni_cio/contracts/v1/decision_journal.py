from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.investment_policy import (
    InvestmentObjective,
    PolicyReferenceV1,
)


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeMoney = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
FiniteMoney = Annotated[Decimal, Field(allow_inf_nan=False)]
Bps = Annotated[Decimal, Field(allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class DecisionJournalAction(StrEnum):
    NO_ACTION = "no_action"
    HOLD = "hold"
    WAIT_FOR_DATA = "wait_for_data"
    REVIEW_CHANGE = "review_change"
    APPROVED_PLAN = "approved_plan"
    EXECUTED_PLAN = "executed_plan"


class EvaluationCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class BenchmarkAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ReplaySourceKind(StrEnum):
    SYNTHETIC = "synthetic"
    FAKE_BROKER = "fake_broker"
    SANITIZED_PRODUCTION = "sanitized_production"


class RegressionArtifactKind(StrEnum):
    MODEL = "model"
    PROMPT = "prompt"
    RULES = "rules"
    CONFIG = "config"


class DecisionJournalRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["DECISION_JOURNAL_RECORD"] = "DECISION_JOURNAL_RECORD"
    decision_id: Sha256
    recorded_at: datetime
    horizon_days: Annotated[int, Field(ge=1, le=3650)]
    policy_reference: PolicyReferenceV1
    policy_objective: InvestmentObjective
    portfolio_snapshot_sha256: Sha256
    decision_set_sha256: Sha256
    evidence_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    risk_assessment_sha256: Sha256
    strategy_selection_sha256: Sha256 | None = None
    optimizer_sha256: Sha256 | None = None
    plan_sha256: Sha256 | None = None
    execution_id: Sha256 | None = None
    selected_action: DecisionJournalAction
    starting_value_base: NonNegativeMoney
    baseline_top1_weight: UnitInterval | None = None
    baseline_cash_weight: UnitInterval | None = None
    target_top1_weight: UnitInterval | None = None
    target_cash_weight: UnitInterval | None = None
    expected_execution_cost_base: NonNegativeMoney | None = None
    research_items_expected: NonNegativeInt = 0
    research_items_available: NonNegativeInt = 0
    data_complete_at_decision: bool
    record_sha256: Sha256
    full_account_identifier_present: Literal[False] = False
    raw_private_payload_present: Literal[False] = False
    expectations_rewritable: Literal[False] = False
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decision journal timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("evidence_sha256s", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("decision evidence hashes must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("decision evidence hashes cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_record(self) -> DecisionJournalRecordV1:
        if self.research_items_available > self.research_items_expected:
            raise ValueError("available research cannot exceed expected research")
        if self.execution_id is not None and self.plan_sha256 is None:
            raise ValueError("execution identity requires an immutable plan binding")
        if self.selected_action is DecisionJournalAction.EXECUTED_PLAN and (
            self.plan_sha256 is None or self.execution_id is None
        ):
            raise ValueError("executed-plan journal record requires plan and execution identity")
        if self.target_top1_weight is not None and self.baseline_top1_weight is None:
            raise ValueError("target concentration requires a baseline concentration")
        if self.target_cash_weight is not None and self.baseline_cash_weight is None:
            raise ValueError("target cash weight requires a baseline cash weight")
        if self.decision_id != decision_journal_record_id(self):
            raise ValueError("decision_id does not match canonical decision record")
        if self.record_sha256 != decision_journal_record_sha256(self):
            raise ValueError("record_sha256 does not match canonical decision record")
        return self


class DecisionOutcomeRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["DECISION_OUTCOME_RECORD"] = "DECISION_OUTCOME_RECORD"
    outcome_id: Sha256
    decision_id: Sha256
    observed_at: datetime
    horizon_days: Annotated[int, Field(ge=1, le=3650)]
    ending_value_base: NonNegativeMoney
    net_external_flow_base: FiniteMoney = Decimal("0")
    no_action_ending_value_base: NonNegativeMoney | None = None
    no_action_source_sha256: Sha256 | None = None
    policy_benchmark_ending_value_base: NonNegativeMoney | None = None
    policy_benchmark_source_sha256: Sha256 | None = None
    ending_top1_weight: UnitInterval | None = None
    ending_cash_weight: UnitInterval | None = None
    execution_cost_base: NonNegativeMoney | None = None
    execution_slippage_bps: Bps | None = None
    research_items_observed: NonNegativeInt = 0
    research_items_covered: NonNegativeInt = 0
    data_completeness_ratio: UnitInterval
    source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    outcome_sha256: Sha256
    full_account_identifier_present: Literal[False] = False
    raw_private_payload_present: Literal[False] = False
    counterfactual_fabricated: Literal[False] = False
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decision outcome timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("decision outcome sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("decision outcome sources cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_outcome(self) -> DecisionOutcomeRecordV1:
        if self.research_items_covered > self.research_items_observed:
            raise ValueError("covered research cannot exceed observed research")
        no_action_pair = (
            self.no_action_ending_value_base is not None,
            self.no_action_source_sha256 is not None,
        )
        if any(no_action_pair) and not all(no_action_pair):
            raise ValueError("NO_ACTION benchmark value and evidence must be complete or absent")
        policy_pair = (
            self.policy_benchmark_ending_value_base is not None,
            self.policy_benchmark_source_sha256 is not None,
        )
        if any(policy_pair) and not all(policy_pair):
            raise ValueError("policy benchmark value and evidence must be complete or absent")
        if self.outcome_id != decision_outcome_record_id(self):
            raise ValueError("outcome_id does not match canonical outcome record")
        if self.outcome_sha256 != decision_outcome_record_sha256(self):
            raise ValueError("outcome_sha256 does not match canonical outcome record")
        return self


class DecisionEvaluationRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["DECISION_EVALUATION_RECORD"] = "DECISION_EVALUATION_RECORD"
    evaluation_id: Sha256
    decision_id: Sha256
    decision_record_sha256: Sha256
    outcome_record_sha256: Sha256
    evaluated_at: datetime
    completeness: EvaluationCompleteness
    realized_period_result_base: FiniteMoney
    no_action_availability: BenchmarkAvailability
    no_action_period_result_base: FiniteMoney | None = None
    excess_vs_no_action_base: FiniteMoney | None = None
    policy_benchmark_availability: BenchmarkAvailability
    policy_benchmark_period_result_base: FiniteMoney | None = None
    excess_vs_policy_benchmark_base: FiniteMoney | None = None
    data_completeness_ratio: UnitInterval
    research_coverage_ratio: UnitInterval
    concentration_reduction_bps: Bps | None = None
    cash_weight_delta_bps: Bps | None = None
    execution_cost_variance_base: FiniteMoney | None = None
    execution_slippage_bps: Bps | None = None
    evaluation_sha256: Sha256
    expectations_rewritten: Literal[False] = False
    counterfactual_fabricated: Literal[False] = False
    production_rules_modified: Literal[False] = False
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decision evaluation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> DecisionEvaluationRecordV1:
        no_action_available = self.no_action_availability is BenchmarkAvailability.AVAILABLE
        if no_action_available != (
            self.no_action_period_result_base is not None
            and self.excess_vs_no_action_base is not None
        ):
            raise ValueError("NO_ACTION evaluation availability is inconsistent")
        policy_available = (
            self.policy_benchmark_availability is BenchmarkAvailability.AVAILABLE
        )
        if policy_available != (
            self.policy_benchmark_period_result_base is not None
            and self.excess_vs_policy_benchmark_base is not None
        ):
            raise ValueError("policy benchmark evaluation availability is inconsistent")
        if self.evaluation_id != decision_evaluation_record_id(self):
            raise ValueError("evaluation_id does not match canonical evaluation record")
        if self.evaluation_sha256 != decision_evaluation_record_sha256(self):
            raise ValueError("evaluation_sha256 does not match canonical evaluation record")
        return self


class DecisionReplayCaseV1(ContractModel):
    case_id: Sha256
    decision_record_sha256: Sha256
    outcome_record_sha256: Sha256
    evaluation_record_sha256: Sha256
    expected_action: DecisionJournalAction
    expected_completeness: EvaluationCompleteness
    expected_no_action_outperformance: bool | None = None
    case_sha256: Sha256
    full_account_identifier_present: Literal[False] = False
    raw_private_payload_present: Literal[False] = False

    @model_validator(mode="after")
    def validate_case(self) -> DecisionReplayCaseV1:
        if self.case_id != decision_replay_case_id(self):
            raise ValueError("case_id does not match canonical replay case")
        if self.case_sha256 != decision_replay_case_sha256(self):
            raise ValueError("case_sha256 does not match canonical replay case")
        return self


class DecisionReplayDatasetV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["DECISION_REPLAY_DATASET"] = "DECISION_REPLAY_DATASET"
    dataset_id: Sha256
    generated_at: datetime
    source_kind: ReplaySourceKind
    sanitization_confirmed: bool
    cases: Annotated[tuple[DecisionReplayCaseV1, ...], Field(min_length=1)]
    dataset_sha256: Sha256
    full_account_identifier_present: Literal[False] = False
    raw_private_payload_present: Literal[False] = False
    secrets_present: Literal[False] = False
    production_write_capable: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("replay dataset timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("cases", mode="before")
    @classmethod
    def normalize_cases(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("replay cases must be a collection")
        return tuple(sorted(value, key=lambda row: str(_value(row, "case_id"))))

    @model_validator(mode="after")
    def validate_dataset(self) -> DecisionReplayDatasetV1:
        ids = [row.case_id for row in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("replay dataset case IDs must be unique")
        if (
            self.source_kind is ReplaySourceKind.SANITIZED_PRODUCTION
            and not self.sanitization_confirmed
        ):
            raise ValueError("production replay export requires explicit sanitization")
        if self.dataset_id != decision_replay_dataset_id(self):
            raise ValueError("dataset_id does not match canonical replay dataset")
        if self.dataset_sha256 != decision_replay_dataset_sha256(self):
            raise ValueError("dataset_sha256 does not match canonical replay dataset")
        return self


class RegressionPredictionV1(ContractModel):
    case_id: Sha256
    action: DecisionJournalAction
    abstain: bool


class RegressionEvaluationResultV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["REGRESSION_EVALUATION_RESULT"] = (
        "REGRESSION_EVALUATION_RESULT"
    )
    artifact_kind: RegressionArtifactKind
    baseline_artifact_sha256: Sha256
    candidate_artifact_sha256: Sha256
    dataset_sha256: Sha256
    evaluated_at: datetime
    case_count: PositiveInt
    baseline_match_count: NonNegativeInt
    candidate_match_count: NonNegativeInt
    regression_case_ids: tuple[Sha256, ...]
    candidate_ready_for_review: bool
    result_sha256: Sha256
    production_change_applied: Literal[False] = False
    self_modification_authorized: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("regression evaluation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("regression_case_ids", mode="before")
    @classmethod
    def normalize_regressions(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("regression case IDs must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_result(self) -> RegressionEvaluationResultV1:
        if self.baseline_match_count > self.case_count:
            raise ValueError("baseline match count cannot exceed case count")
        if self.candidate_match_count > self.case_count:
            raise ValueError("candidate match count cannot exceed case count")
        expected_ready = not self.regression_case_ids and (
            self.candidate_match_count >= self.baseline_match_count
        )
        if self.candidate_ready_for_review is not expected_ready:
            raise ValueError("candidate review readiness is inconsistent")
        if self.result_sha256 != regression_evaluation_result_sha256(self):
            raise ValueError("result_sha256 does not match canonical regression result")
        return self


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _value(row: object, attribute: str) -> object:
    if isinstance(row, dict):
        return row.get(attribute)
    return getattr(row, attribute, None)


def decision_journal_record_id(value: DecisionJournalRecordV1) -> str:
    payload = value.model_dump(
        mode="json",
        exclude={"decision_id", "record_sha256"},
    )
    return _sha(payload)


def decision_journal_record_sha256(value: DecisionJournalRecordV1) -> str:
    payload = value.model_dump(mode="json", exclude={"record_sha256"})
    return _sha(payload)


def decision_outcome_record_id(value: DecisionOutcomeRecordV1) -> str:
    payload = value.model_dump(
        mode="json",
        exclude={"outcome_id", "outcome_sha256"},
    )
    return _sha(payload)


def decision_outcome_record_sha256(value: DecisionOutcomeRecordV1) -> str:
    payload = value.model_dump(mode="json", exclude={"outcome_sha256"})
    return _sha(payload)


def decision_evaluation_record_id(value: DecisionEvaluationRecordV1) -> str:
    payload = value.model_dump(
        mode="json",
        exclude={"evaluation_id", "evaluation_sha256"},
    )
    return _sha(payload)


def decision_evaluation_record_sha256(value: DecisionEvaluationRecordV1) -> str:
    payload = value.model_dump(mode="json", exclude={"evaluation_sha256"})
    return _sha(payload)


def decision_replay_case_id(value: DecisionReplayCaseV1) -> str:
    payload = value.model_dump(mode="json", exclude={"case_id", "case_sha256"})
    return _sha(payload)


def decision_replay_case_sha256(value: DecisionReplayCaseV1) -> str:
    payload = value.model_dump(mode="json", exclude={"case_sha256"})
    return _sha(payload)


def decision_replay_dataset_id(value: DecisionReplayDatasetV1) -> str:
    payload = value.model_dump(mode="json", exclude={"dataset_id", "dataset_sha256"})
    return _sha(payload)


def decision_replay_dataset_sha256(value: DecisionReplayDatasetV1) -> str:
    payload = value.model_dump(mode="json", exclude={"dataset_sha256"})
    return _sha(payload)


def regression_evaluation_result_sha256(value: RegressionEvaluationResultV1) -> str:
    payload = value.model_dump(mode="json", exclude={"result_sha256"})
    return _sha(payload)
