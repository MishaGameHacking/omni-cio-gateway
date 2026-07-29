from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority


ReturnValue = Annotated[
    Decimal,
    Field(gt=Decimal("-1"), allow_inf_nan=False),
]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
ObservationId = Annotated[str, Field(min_length=1, max_length=128)]


class WalkForwardPerformanceStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class WalkForwardPerformanceBlocker(StrEnum):
    VALIDATION_PLAN_NOT_READY = "validation_plan_not_ready"
    PLAN_DATASET_MISMATCH = "plan_dataset_mismatch"
    INSTRUMENT_MISMATCH = "instrument_mismatch"
    OUTCOME_COVERAGE_MISMATCH = "outcome_coverage_mismatch"
    OUTCOME_NOT_OUT_OF_SAMPLE = "outcome_not_out_of_sample"
    OUTCOME_AVAILABLE_BEFORE_LABEL = "outcome_available_before_label"
    UNTRUSTED_SOURCE = "untrusted_source"
    SOURCE_RETRIEVED_IN_FUTURE = "source_retrieved_in_future"
    INSUFFICIENT_OUT_OF_SAMPLE_OBSERVATIONS = (
        "insufficient_out_of_sample_observations"
    )
    INSUFFICIENT_EVALUATED_FOLDS = "insufficient_evaluated_folds"
    TRANSACTION_COST_MODEL_MISSING = "transaction_cost_model_missing"


class WalkForwardPerformanceWarning(StrEnum):
    NEGATIVE_NET_RETURN = "negative_net_return"
    UNDERPERFORMS_BENCHMARK = "underperforms_benchmark"
    HIGH_AVERAGE_TURNOVER = "high_average_turnover"
    HIGH_COST_DRAG = "high_cost_drag"
    FOLD_RESULTS_UNSTABLE = "fold_results_unstable"
    NO_STATISTICAL_SIGNIFICANCE_TEST = "no_statistical_significance_test"
    NO_CAPACITY_ANALYSIS = "no_capacity_analysis"
    SINGLE_INSTRUMENT_EVALUATION = "single_instrument_evaluation"
    PERFORMANCE_IS_HISTORICAL_NOT_FORECAST = "performance_is_historical_not_forecast"


class WalkForwardPerformancePolicyV1(ContractModel):
    minimum_out_of_sample_observations: PositiveInt = 30
    minimum_evaluated_folds: PositiveInt = 3
    future_tolerance_seconds: NonNegativeInt = 60
    require_positive_transaction_cost_model: bool = True
    high_average_turnover_threshold: NonNegativeDecimal = Decimal("1")
    high_cost_drag_threshold: NonNegativeDecimal = Decimal("0.05")
    unstable_fold_return_range_threshold: NonNegativeDecimal = Decimal("0.20")
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )

    @model_validator(mode="after")
    def validate_policy(self) -> WalkForwardPerformancePolicyV1:
        if not self.trusted_authorities:
            raise ValueError("performance policy requires trusted authorities")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("performance trusted authorities must be unique")
        return self


class WalkForwardOutcomeV1(ContractModel):
    observation_id: ObservationId
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    outcome_available_at: datetime
    source: MarketSourceV1
    strategy_gross_return: ReturnValue
    benchmark_return: ReturnValue
    turnover: NonNegativeDecimal
    commission_bps: NonNegativeDecimal
    spread_bps: NonNegativeDecimal
    slippage_bps: NonNegativeDecimal
    transaction_cost_rate: NonNegativeDecimal
    strategy_net_return: ReturnValue

    @field_validator("outcome_available_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("walk-forward outcome timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_outcome(self) -> WalkForwardOutcomeV1:
        expected_cost = self.turnover * (
            self.commission_bps + self.spread_bps + self.slippage_bps
        ) / Decimal("10000")
        if self.transaction_cost_rate != expected_cost:
            raise ValueError("walk-forward transaction cost does not reconcile")
        expected_net = self.strategy_gross_return - self.transaction_cost_rate
        if self.strategy_net_return != expected_net:
            raise ValueError("walk-forward net return does not reconcile")
        if self.source.retrieved_at < self.outcome_available_at:
            raise ValueError("outcome source was retrieved before outcome availability")
        return self


class WalkForwardOutcomeSetV1(ContractModel):
    schema_name: Literal["walk_forward_outcome_set"] = "walk_forward_outcome_set"
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    outcomes: tuple[WalkForwardOutcomeV1, ...]
    complete: Literal[True] = True
    truncated: Literal[False] = False
    benchmark_included: Literal[True] = True
    transaction_cost_components_explicit: Literal[True] = True
    test_observations_only: Literal[True] = True
    hyperparameters_optimized_on_test: Literal[False] = False
    forecast_data_included: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_set(self) -> WalkForwardOutcomeSetV1:
        if not self.outcomes:
            raise ValueError("walk-forward outcome set requires outcomes")
        if any(
            outcome.instrument_key != self.instrument_key
            for outcome in self.outcomes
        ):
            raise ValueError("walk-forward outcome instrument mismatch")
        observation_ids = [outcome.observation_id for outcome in self.outcomes]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("walk-forward outcome IDs must be unique")
        return self


class WalkForwardFoldPerformanceV1(ContractModel):
    fold_number: PositiveInt
    observation_count: PositiveInt
    gross_total_return: ReturnValue
    net_total_return: ReturnValue
    benchmark_total_return: ReturnValue
    active_total_return: FiniteDecimal
    cost_drag: NonNegativeDecimal
    total_turnover: NonNegativeDecimal
    average_turnover: NonNegativeDecimal
    positive_return_rate: UnitInterval
    benchmark_outperformance_rate: UnitInterval
    max_drawdown: UnitInterval
    max_drawdown_duration_observations: NonNegativeInt

    @model_validator(mode="after")
    def validate_fold_metrics(self) -> WalkForwardFoldPerformanceV1:
        if self.active_total_return != (
            self.net_total_return - self.benchmark_total_return
        ):
            raise ValueError("fold active return does not reconcile")
        if self.cost_drag != self.gross_total_return - self.net_total_return:
            raise ValueError("fold cost drag does not reconcile")
        if self.average_turnover != self.total_turnover / Decimal(
            self.observation_count
        ):
            raise ValueError("fold average turnover does not reconcile")
        return self


class WalkForwardAggregatePerformanceV1(ContractModel):
    observation_count: PositiveInt
    fold_count: PositiveInt
    gross_total_return: ReturnValue
    net_total_return: ReturnValue
    benchmark_total_return: ReturnValue
    active_total_return: FiniteDecimal
    cost_drag: NonNegativeDecimal
    total_turnover: NonNegativeDecimal
    average_turnover: NonNegativeDecimal
    mean_net_return: FiniteDecimal
    realized_volatility: NonNegativeDecimal
    positive_return_rate: UnitInterval
    benchmark_outperformance_rate: UnitInterval
    max_drawdown: UnitInterval
    max_drawdown_duration_observations: NonNegativeInt
    minimum_fold_net_return: ReturnValue
    maximum_fold_net_return: ReturnValue
    fold_net_return_range: NonNegativeDecimal
    profitable_fold_rate: UnitInterval
    benchmark_beating_fold_rate: UnitInterval

    @model_validator(mode="after")
    def validate_aggregate_metrics(self) -> WalkForwardAggregatePerformanceV1:
        if self.active_total_return != (
            self.net_total_return - self.benchmark_total_return
        ):
            raise ValueError("aggregate active return does not reconcile")
        if self.cost_drag != self.gross_total_return - self.net_total_return:
            raise ValueError("aggregate cost drag does not reconcile")
        if self.average_turnover != self.total_turnover / Decimal(
            self.observation_count
        ):
            raise ValueError("aggregate average turnover does not reconcile")
        if self.fold_net_return_range != (
            self.maximum_fold_net_return - self.minimum_fold_net_return
        ):
            raise ValueError("fold return range does not reconcile")
        return self


class WalkForwardPerformanceEvaluationV1(ContractModel):
    schema_name: Literal["walk_forward_performance_evaluation"] = (
        "walk_forward_performance_evaluation"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: WalkForwardPerformanceStatus
    evaluation_ready: bool
    dataset_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    policy: WalkForwardPerformancePolicyV1
    expected_outcome_count: NonNegativeInt
    provided_outcome_count: PositiveInt
    evaluated_outcome_count: NonNegativeInt
    evaluated_fold_count: NonNegativeInt
    fold_performance: tuple[WalkForwardFoldPerformanceV1, ...]
    aggregate_performance: WalkForwardAggregatePerformanceV1 | None = None
    blockers: tuple[WalkForwardPerformanceBlocker, ...] = ()
    warnings: tuple[WalkForwardPerformanceWarning, ...] = ()
    out_of_sample_only: Literal[True] = True
    benchmark_included: Literal[True] = True
    transaction_costs_evaluated: bool
    performance_metrics_computed: bool
    hyperparameters_optimized: Literal[False] = False
    statistical_significance_tested: Literal[False] = False
    capacity_analyzed: Literal[False] = False
    historical_performance_not_forecast: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("performance assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> WalkForwardPerformanceEvaluationV1:
        if self.evaluated_fold_count != len(self.fold_performance):
            raise ValueError("evaluated fold count does not reconcile")
        fold_observations = sum(
            fold.observation_count for fold in self.fold_performance
        )
        if self.evaluated_outcome_count != fold_observations:
            raise ValueError("evaluated outcome count does not reconcile")
        aggregate = self.aggregate_performance
        metrics_present = aggregate is not None
        if self.performance_metrics_computed is not metrics_present:
            raise ValueError("performance metric status is inconsistent")
        if aggregate is not None:
            if aggregate.observation_count != self.evaluated_outcome_count:
                raise ValueError("aggregate observation count does not reconcile")
            if aggregate.fold_count != self.evaluated_fold_count:
                raise ValueError("aggregate fold count does not reconcile")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("performance blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("performance warnings must be unique")
        expected_ready = not self.blockers and metrics_present
        if self.evaluation_ready is not expected_ready:
            raise ValueError("performance evaluation readiness is inconsistent")
        expected_status = (
            WalkForwardPerformanceStatus.READY
            if expected_ready
            else WalkForwardPerformanceStatus.REJECTED
        )
        if self.status is not expected_status:
            raise ValueError("performance evaluation status is inconsistent")
        return self
