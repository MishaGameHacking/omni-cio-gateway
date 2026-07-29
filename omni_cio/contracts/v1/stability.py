from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel


FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
ReturnValue = Annotated[
    Decimal,
    Field(ge=Decimal("-1"), allow_inf_nan=False),
]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
ConfidenceLevel = Annotated[
    Decimal,
    Field(gt=Decimal("0.50"), lt=Decimal("1"), allow_inf_nan=False),
]
CostMultiplier = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("10"), allow_inf_nan=False),
]
AdditionalSlippageBps = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1000"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class StatisticalStabilityStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class SignFlipMethod(StrEnum):
    EXACT = "exact"
    DETERMINISTIC_MONTE_CARLO = "deterministic_monte_carlo"


class StatisticalStabilityBlocker(StrEnum):
    PERFORMANCE_EVALUATION_NOT_READY = "performance_evaluation_not_ready"
    DATASET_MISMATCH = "dataset_mismatch"
    INSTRUMENT_MISMATCH = "instrument_mismatch"
    OUTCOME_COVERAGE_MISMATCH = "outcome_coverage_mismatch"
    BASELINE_PERFORMANCE_MISMATCH = "baseline_performance_mismatch"
    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"
    INSUFFICIENT_FOLDS = "insufficient_folds"
    INVALID_COST_STRESS_SCENARIO = "invalid_cost_stress_scenario"


class StatisticalStabilityWarning(StrEnum):
    LIMITED_FOLD_COUNT = "limited_fold_count"
    CONFIDENCE_INTERVAL_INCLUDES_ZERO = "confidence_interval_includes_zero"
    SIGN_FLIP_NOT_SIGNIFICANT = "sign_flip_not_significant"
    COST_STRESS_SIGN_REVERSAL = "cost_stress_sign_reversal"
    LEAVE_ONE_FOLD_OUT_SIGN_REVERSAL = "leave_one_fold_out_sign_reversal"
    COST_ASSUMPTION_SENSITIVE = "cost_assumption_sensitive"
    DETERMINISTIC_RESAMPLING = "deterministic_resampling"
    NO_HYPERPARAMETER_SEARCH = "no_hyperparameter_search"
    SINGLE_INSTRUMENT_EVALUATION = "single_instrument_evaluation"
    NO_CAPACITY_ANALYSIS = "no_capacity_analysis"
    HISTORICAL_PERFORMANCE_NOT_FORECAST = "historical_performance_not_forecast"


class StatisticalStabilityPolicyV1(ContractModel):
    minimum_observations: PositiveInt = 30
    minimum_folds: Annotated[int, Field(ge=3, le=100)] = 4
    bootstrap_samples: Annotated[int, Field(ge=200, le=20_000)] = 2_000
    confidence_level: ConfidenceLevel = Decimal("0.95")
    deterministic_seed: Annotated[int, Field(ge=1, le=2_147_483_647)] = 20260729
    exact_sign_flip_max_folds: Annotated[int, Field(ge=1, le=20)] = 16
    sign_flip_samples: Annotated[int, Field(ge=1_000, le=200_000)] = 20_000
    limited_fold_warning_below: Annotated[int, Field(ge=3, le=100)] = 8
    cost_multipliers: tuple[CostMultiplier, ...] = (
        Decimal("0.5"),
        Decimal("1"),
        Decimal("1.5"),
        Decimal("2"),
    )
    additional_slippage_bps: tuple[AdditionalSlippageBps, ...] = (
        Decimal("0"),
        Decimal("5"),
        Decimal("10"),
        Decimal("25"),
    )
    high_cost_sensitivity_range_threshold: NonNegativeDecimal = Decimal("0.10")

    @model_validator(mode="after")
    def validate_policy(self) -> StatisticalStabilityPolicyV1:
        if not self.cost_multipliers:
            raise ValueError("statistical stability policy requires cost multipliers")
        if tuple(sorted(self.cost_multipliers)) != self.cost_multipliers:
            raise ValueError("cost multipliers must be sorted")
        if len(set(self.cost_multipliers)) != len(self.cost_multipliers):
            raise ValueError("cost multipliers must be unique")
        if Decimal("1") not in self.cost_multipliers:
            raise ValueError("cost multipliers must include the baseline multiplier")
        if not self.additional_slippage_bps:
            raise ValueError("statistical stability policy requires slippage scenarios")
        if tuple(sorted(self.additional_slippage_bps)) != self.additional_slippage_bps:
            raise ValueError("additional slippage scenarios must be sorted")
        if len(set(self.additional_slippage_bps)) != len(
            self.additional_slippage_bps
        ):
            raise ValueError("additional slippage scenarios must be unique")
        if Decimal("0") not in self.additional_slippage_bps:
            raise ValueError("additional slippage scenarios must include zero")
        return self


class BootstrapIntervalV1(ContractModel):
    method: Literal["fold_cluster_bootstrap"] = "fold_cluster_bootstrap"
    statistic: Literal["mean_fold_active_return"] = "mean_fold_active_return"
    fold_count: PositiveInt
    sample_count: PositiveInt
    confidence_level: ConfidenceLevel
    deterministic_seed: PositiveInt
    observed_value: FiniteDecimal
    lower_bound: FiniteDecimal
    median: FiniteDecimal
    upper_bound: FiniteDecimal
    probability_positive: UnitInterval

    @model_validator(mode="after")
    def validate_interval(self) -> BootstrapIntervalV1:
        if not self.lower_bound <= self.median <= self.upper_bound:
            raise ValueError("bootstrap interval bounds are inconsistent")
        return self


class SignFlipTestV1(ContractModel):
    test_type: Literal["two_sided_paired_fold_sign_flip"] = (
        "two_sided_paired_fold_sign_flip"
    )
    method: SignFlipMethod
    fold_count: PositiveInt
    permutations_evaluated: PositiveInt
    deterministic_seed: PositiveInt
    observed_mean_active_return: FiniteDecimal
    p_value: UnitInterval
    significance_level: UnitInterval
    statistically_significant: bool

    @model_validator(mode="after")
    def validate_test(self) -> SignFlipTestV1:
        expected = self.p_value <= self.significance_level
        if self.statistically_significant is not expected:
            raise ValueError("sign-flip significance status is inconsistent")
        if self.method is SignFlipMethod.EXACT:
            expected_permutations = 2**self.fold_count
            if self.permutations_evaluated != expected_permutations:
                raise ValueError("exact sign-flip permutation count is inconsistent")
        return self


class CostSensitivityScenarioV1(ContractModel):
    scenario_id: Annotated[str, Field(min_length=1, max_length=128)]
    cost_multiplier: CostMultiplier
    additional_slippage_bps: AdditionalSlippageBps
    observation_count: PositiveInt
    invalid_observation_count: NonNegativeInt
    metrics_computed: bool
    net_total_return: ReturnValue | None = None
    benchmark_total_return: ReturnValue | None = None
    active_total_return: FiniteDecimal | None = None
    active_positive: bool | None = None
    sign_reversal_from_baseline: bool | None = None

    @model_validator(mode="after")
    def validate_scenario(self) -> CostSensitivityScenarioV1:
        metrics = (
            self.net_total_return,
            self.benchmark_total_return,
            self.active_total_return,
            self.active_positive,
            self.sign_reversal_from_baseline,
        )
        if self.metrics_computed:
            if self.invalid_observation_count != 0 or any(value is None for value in metrics):
                raise ValueError("valid cost sensitivity scenario is incomplete")
            assert self.net_total_return is not None
            assert self.benchmark_total_return is not None
            assert self.active_total_return is not None
            assert self.active_positive is not None
            if self.active_total_return != (
                self.net_total_return - self.benchmark_total_return
            ):
                raise ValueError("cost sensitivity active return does not reconcile")
            if self.active_positive is not (self.active_total_return > 0):
                raise ValueError("cost sensitivity active sign is inconsistent")
        elif self.invalid_observation_count == 0 or any(value is not None for value in metrics):
            raise ValueError("invalid cost sensitivity scenario carries metrics")
        return self


class LeaveOneFoldOutScenarioV1(ContractModel):
    omitted_fold_number: PositiveInt
    observation_count: PositiveInt
    net_total_return: ReturnValue
    benchmark_total_return: ReturnValue
    active_total_return: FiniteDecimal
    active_positive: bool
    sign_reversal_from_baseline: bool

    @model_validator(mode="after")
    def validate_scenario(self) -> LeaveOneFoldOutScenarioV1:
        if self.active_total_return != (
            self.net_total_return - self.benchmark_total_return
        ):
            raise ValueError("leave-one-fold-out active return does not reconcile")
        if self.active_positive is not (self.active_total_return > 0):
            raise ValueError("leave-one-fold-out active sign is inconsistent")
        return self


class SensitivitySummaryV1(ContractModel):
    cost_scenario_count: PositiveInt
    valid_cost_scenario_count: PositiveInt
    invalid_cost_scenario_count: NonNegativeInt
    cost_active_return_minimum: FiniteDecimal
    cost_active_return_maximum: FiniteDecimal
    cost_active_return_range: NonNegativeDecimal
    cost_sign_reversal_count: NonNegativeInt
    leave_one_fold_out_count: PositiveInt
    leave_one_fold_out_active_minimum: FiniteDecimal
    leave_one_fold_out_active_maximum: FiniteDecimal
    leave_one_fold_out_active_range: NonNegativeDecimal
    leave_one_fold_out_sign_reversal_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_summary(self) -> SensitivitySummaryV1:
        if self.valid_cost_scenario_count + self.invalid_cost_scenario_count != (
            self.cost_scenario_count
        ):
            raise ValueError("cost sensitivity scenario counts do not reconcile")
        if self.cost_active_return_minimum > self.cost_active_return_maximum:
            raise ValueError("cost sensitivity extrema are inconsistent")
        if self.cost_active_return_range != (
            self.cost_active_return_maximum - self.cost_active_return_minimum
        ):
            raise ValueError("cost sensitivity range does not reconcile")
        if (
            self.leave_one_fold_out_active_minimum
            > self.leave_one_fold_out_active_maximum
        ):
            raise ValueError("leave-one-fold-out extrema are inconsistent")
        if self.leave_one_fold_out_active_range != (
            self.leave_one_fold_out_active_maximum
            - self.leave_one_fold_out_active_minimum
        ):
            raise ValueError("leave-one-fold-out range does not reconcile")
        if self.cost_sign_reversal_count > self.valid_cost_scenario_count:
            raise ValueError("cost sensitivity sign reversals exceed valid scenarios")
        if self.leave_one_fold_out_sign_reversal_count > self.leave_one_fold_out_count:
            raise ValueError("leave-one-fold-out sign reversals exceed scenarios")
        return self


class StatisticalStabilityAssessmentV1(ContractModel):
    schema_name: Literal["statistical_stability_assessment"] = (
        "statistical_stability_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: StatisticalStabilityStatus
    stability_ready: bool
    dataset_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    policy: StatisticalStabilityPolicyV1
    observation_count: NonNegativeInt
    fold_count: NonNegativeInt
    baseline_active_total_return: FiniteDecimal | None = None
    bootstrap_interval: BootstrapIntervalV1 | None = None
    sign_flip_test: SignFlipTestV1 | None = None
    cost_scenarios: tuple[CostSensitivityScenarioV1, ...] = ()
    leave_one_fold_out: tuple[LeaveOneFoldOutScenarioV1, ...] = ()
    sensitivity_summary: SensitivitySummaryV1 | None = None
    blockers: tuple[StatisticalStabilityBlocker, ...] = ()
    warnings: tuple[StatisticalStabilityWarning, ...] = ()
    statistical_inference_computed: bool
    statistical_significance_confirmed: bool
    assumption_sensitivity_computed: bool
    out_of_sample_only: Literal[True] = True
    fold_clustered_resampling: Literal[True] = True
    deterministic_resampling: Literal[True] = True
    test_data_used_for_selection: Literal[False] = False
    hyperparameters_optimized: Literal[False] = False
    capacity_analyzed: Literal[False] = False
    historical_performance_not_forecast: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("statistical stability timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_assessment(self) -> StatisticalStabilityAssessmentV1:
        if (self.bootstrap_interval is None) != (self.sign_flip_test is None):
            raise ValueError("statistical inference bundle is partial")
        sensitivity_parts = (
            self.sensitivity_summary is not None,
            bool(self.cost_scenarios),
            bool(self.leave_one_fold_out),
        )
        if len(set(sensitivity_parts)) != 1:
            raise ValueError("assumption sensitivity bundle is partial")
        inference_present = (
            self.bootstrap_interval is not None and self.sign_flip_test is not None
        )
        sensitivity_present = all(sensitivity_parts)
        if (inference_present or sensitivity_present) and (
            self.baseline_active_total_return is None
        ):
            raise ValueError("computed stability assessment requires a baseline")
        if self.statistical_inference_computed is not inference_present:
            raise ValueError("statistical inference status is inconsistent")
        if self.assumption_sensitivity_computed is not sensitivity_present:
            raise ValueError("assumption sensitivity status is inconsistent")
        if inference_present:
            assert self.bootstrap_interval is not None
            assert self.sign_flip_test is not None
            if self.bootstrap_interval.fold_count != self.fold_count:
                raise ValueError("bootstrap fold count does not reconcile")
            if self.sign_flip_test.fold_count != self.fold_count:
                raise ValueError("sign-flip fold count does not reconcile")
            interval_excludes_zero = (
                self.bootstrap_interval.lower_bound > 0
                or self.bootstrap_interval.upper_bound < 0
            )
            expected_significance = (
                interval_excludes_zero
                and self.sign_flip_test.statistically_significant
            )
        else:
            expected_significance = False
        if self.statistical_significance_confirmed is not expected_significance:
            raise ValueError("statistical significance status is inconsistent")
        if sensitivity_present:
            assert self.sensitivity_summary is not None
            if self.sensitivity_summary.cost_scenario_count != len(
                self.cost_scenarios
            ):
                raise ValueError("cost sensitivity scenario count does not reconcile")
            if self.sensitivity_summary.leave_one_fold_out_count != len(
                self.leave_one_fold_out
            ):
                raise ValueError("leave-one-fold-out count does not reconcile")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("statistical stability blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("statistical stability warnings must be unique")
        expected_ready = not self.blockers and inference_present and sensitivity_present
        if self.stability_ready is not expected_ready:
            raise ValueError("statistical stability readiness is inconsistent")
        expected_status = (
            StatisticalStabilityStatus.READY
            if expected_ready
            else StatisticalStabilityStatus.REJECTED
        )
        if self.status is not expected_status:
            raise ValueError("statistical stability status is inconsistent")
        return self
