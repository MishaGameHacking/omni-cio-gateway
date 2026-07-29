from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority


UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
ObservationId = Annotated[str, Field(min_length=1, max_length=128)]


class WalkForwardMode(StrEnum):
    EXPANDING = "expanding"
    ROLLING = "rolling"


class WalkForwardValidationStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class WalkForwardValidationBlocker(StrEnum):
    UNTRUSTED_SOURCE = "untrusted_source"
    SOURCE_RETRIEVED_IN_FUTURE = "source_retrieved_in_future"
    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"
    INSUFFICIENT_VALID_FOLDS = "insufficient_valid_folds"


class WalkForwardValidationWarning(StrEnum):
    SPLIT_PLAN_ONLY_NO_PERFORMANCE = "split_plan_only_no_performance"
    TRANSACTION_COSTS_NOT_EVALUATED = "transaction_costs_not_evaluated"
    SINGLE_INSTRUMENT_DATASET = "single_instrument_dataset"
    EXPANDING_WINDOW = "expanding_window"
    ROLLING_WINDOW = "rolling_window"
    OVERLAPPING_LABELS_PURGED = "overlapping_labels_purged"
    PARAMETER_STABILITY_NOT_ASSESSED = "parameter_stability_not_assessed"


class WalkForwardObservationV1(ContractModel):
    observation_id: ObservationId
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    feature_window_start: datetime
    feature_window_end: datetime
    feature_data_available_at: datetime
    universe_snapshot_at: datetime
    decision_at: datetime
    label_window_start: datetime
    label_window_end: datetime
    label_data_available_at: datetime
    source_record_id: Annotated[str | None, Field(max_length=256)] = None

    @field_validator(
        "feature_window_start",
        "feature_window_end",
        "feature_data_available_at",
        "universe_snapshot_at",
        "decision_at",
        "label_window_start",
        "label_window_end",
        "label_data_available_at",
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("validation observation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_temporal_order(self) -> WalkForwardObservationV1:
        if self.feature_window_start > self.feature_window_end:
            raise ValueError("feature window is reversed")
        if self.feature_window_end > self.decision_at:
            raise ValueError("feature window extends beyond decision time")
        if self.feature_data_available_at > self.decision_at:
            raise ValueError("feature data was unavailable at decision time")
        if self.universe_snapshot_at > self.decision_at:
            raise ValueError("universe snapshot was unavailable at decision time")
        if self.label_window_start < self.decision_at:
            raise ValueError("label window starts before decision time")
        if self.label_window_end <= self.label_window_start:
            raise ValueError("label window must have positive duration")
        if self.label_data_available_at < self.label_window_end:
            raise ValueError("label data availability precedes label completion")
        return self


class WalkForwardDatasetV1(ContractModel):
    schema_name: Literal["walk_forward_dataset"] = "walk_forward_dataset"
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    source: MarketSourceV1
    observations: tuple[WalkForwardObservationV1, ...]
    point_in_time_universe: Literal[True] = True
    delisted_instruments_retained: Literal[True] = True
    corporate_actions_adjusted: Literal[True] = True
    original_vintage_data: Literal[True] = True
    truncated: Literal[False] = False
    complete: Literal[True] = True
    forecast_data_included: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_dataset(self) -> WalkForwardDatasetV1:
        if not self.observations:
            raise ValueError("walk-forward dataset requires observations")
        if any(
            observation.instrument_key != self.instrument_key
            for observation in self.observations
        ):
            raise ValueError("walk-forward observation instrument mismatch")
        observation_ids = [item.observation_id for item in self.observations]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("walk-forward observation IDs must be unique")
        decision_times = [item.decision_at for item in self.observations]
        if decision_times != sorted(decision_times):
            raise ValueError("walk-forward observations must be chronological")
        if len(set(decision_times)) != len(decision_times):
            raise ValueError("walk-forward decision timestamps must be unique")
        latest_available = max(
            item.label_data_available_at for item in self.observations
        )
        if self.source.retrieved_at < latest_available:
            raise ValueError("dataset source was retrieved before labels were available")
        return self


class WalkForwardValidationPolicyV1(ContractModel):
    mode: WalkForwardMode = WalkForwardMode.EXPANDING
    minimum_train_observations: PositiveInt = 30
    test_observations: PositiveInt = 10
    step_observations: PositiveInt = 10
    embargo_seconds: NonNegativeInt = 0
    minimum_folds: PositiveInt = 3
    rolling_train_observations: PositiveInt | None = None
    future_tolerance_seconds: NonNegativeInt = 60
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )
    purge_overlapping_labels: Literal[True] = True
    out_of_sample_only: Literal[True] = True
    overlapping_test_windows_forbidden: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> WalkForwardValidationPolicyV1:
        if self.step_observations < self.test_observations:
            raise ValueError("walk-forward test windows cannot overlap")
        if self.mode is WalkForwardMode.EXPANDING:
            if self.rolling_train_observations is not None:
                raise ValueError("expanding mode cannot set rolling train size")
        else:
            if self.rolling_train_observations is None:
                raise ValueError("rolling mode requires rolling train size")
            if self.rolling_train_observations < self.minimum_train_observations:
                raise ValueError("rolling train size is below minimum train size")
        if not self.trusted_authorities:
            raise ValueError("walk-forward policy requires trusted authorities")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("walk-forward trusted authorities must be unique")
        return self


class WalkForwardFoldV1(ContractModel):
    fold_number: PositiveInt
    train_observation_ids: tuple[ObservationId, ...]
    test_observation_ids: tuple[ObservationId, ...]
    purged_observation_ids: tuple[ObservationId, ...] = ()
    train_count: PositiveInt
    test_count: PositiveInt
    purged_count: NonNegativeInt
    train_decision_start: datetime
    train_decision_end: datetime
    test_decision_start: datetime
    test_decision_end: datetime
    latest_train_label_available_at: datetime
    embargo_seconds: NonNegativeInt

    @field_validator(
        "train_decision_start",
        "train_decision_end",
        "test_decision_start",
        "test_decision_end",
        "latest_train_label_available_at",
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("walk-forward fold timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_fold(self) -> WalkForwardFoldV1:
        if self.train_count != len(self.train_observation_ids):
            raise ValueError("walk-forward train count does not reconcile")
        if self.test_count != len(self.test_observation_ids):
            raise ValueError("walk-forward test count does not reconcile")
        if self.purged_count != len(self.purged_observation_ids):
            raise ValueError("walk-forward purged count does not reconcile")
        if len(set(self.train_observation_ids)) != self.train_count:
            raise ValueError("walk-forward train IDs must be unique")
        if len(set(self.test_observation_ids)) != self.test_count:
            raise ValueError("walk-forward test IDs must be unique")
        if len(set(self.purged_observation_ids)) != self.purged_count:
            raise ValueError("walk-forward purged IDs must be unique")
        train_ids = set(self.train_observation_ids)
        test_ids = set(self.test_observation_ids)
        purged_ids = set(self.purged_observation_ids)
        if train_ids & test_ids or train_ids & purged_ids or test_ids & purged_ids:
            raise ValueError("walk-forward fold sets must be disjoint")
        if self.train_decision_start > self.train_decision_end:
            raise ValueError("walk-forward train period is reversed")
        if self.test_decision_start > self.test_decision_end:
            raise ValueError("walk-forward test period is reversed")
        if self.train_decision_end >= self.test_decision_start:
            raise ValueError("walk-forward train decisions overlap test period")
        embargo_cutoff = self.latest_train_label_available_at + timedelta(
            seconds=self.embargo_seconds
        )
        if embargo_cutoff > self.test_decision_start:
            raise ValueError("walk-forward training labels violate embargo")
        return self


class WalkForwardValidationPlanV1(ContractModel):
    schema_name: Literal["walk_forward_validation_plan"] = (
        "walk_forward_validation_plan"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: WalkForwardValidationStatus
    validation_ready: bool
    dataset_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    policy: WalkForwardValidationPolicyV1
    observation_count: PositiveInt
    fold_count: NonNegativeInt
    out_of_sample_observation_count: NonNegativeInt
    out_of_sample_coverage: UnitInterval
    folds: tuple[WalkForwardFoldV1, ...]
    blockers: tuple[WalkForwardValidationBlocker, ...] = ()
    warnings: tuple[WalkForwardValidationWarning, ...] = ()
    split_plan_only: Literal[True] = True
    performance_metrics_computed: Literal[False] = False
    hyperparameters_optimized: Literal[False] = False
    transaction_costs_evaluated: Literal[False] = False
    look_ahead_data_allowed: Literal[False] = False
    test_data_used_for_training: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("walk-forward assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_plan(self) -> WalkForwardValidationPlanV1:
        if self.fold_count != len(self.folds):
            raise ValueError("walk-forward fold count does not reconcile")
        if tuple(fold.fold_number for fold in self.folds) != tuple(
            range(1, len(self.folds) + 1)
        ):
            raise ValueError("walk-forward fold numbers must be contiguous")
        test_ids = [
            observation_id
            for fold in self.folds
            for observation_id in fold.test_observation_ids
        ]
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("walk-forward test observations cannot repeat")
        if self.out_of_sample_observation_count != len(test_ids):
            raise ValueError("walk-forward out-of-sample count does not reconcile")
        expected_coverage = Decimal(len(test_ids)) / Decimal(self.observation_count)
        if self.out_of_sample_coverage != expected_coverage:
            raise ValueError("walk-forward out-of-sample coverage does not reconcile")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("walk-forward blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("walk-forward warnings must be unique")
        expected_ready = not self.blockers
        if self.validation_ready is not expected_ready:
            raise ValueError("walk-forward readiness is inconsistent")
        expected_status = (
            WalkForwardValidationStatus.READY
            if expected_ready
            else WalkForwardValidationStatus.REJECTED
        )
        if self.status is not expected_status:
            raise ValueError("walk-forward status is inconsistent")
        if self.validation_ready and self.fold_count < self.policy.minimum_folds:
            raise ValueError("ready walk-forward plan has too few folds")
        return self
