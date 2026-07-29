from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.performance import (
    WalkForwardOutcomeSetV1,
    WalkForwardOutcomeV1,
)
from omni_cio.contracts.v1.stability import (
    SignFlipMethod,
    StatisticalStabilityAssessmentV1,
    StatisticalStabilityBlocker,
    StatisticalStabilityPolicyV1,
    StatisticalStabilityStatus,
    StatisticalStabilityWarning,
)
from omni_cio.contracts.v1.validation import (
    WalkForwardDatasetV1,
    WalkForwardObservationV1,
    WalkForwardValidationPlanV1,
    WalkForwardValidationPolicyV1,
)
from omni_cio.validation.performance_v1 import evaluate_walk_forward_performance
from omni_cio.validation.stability_v1 import (
    StatisticalStabilityError,
    assess_walk_forward_statistical_stability,
)
from omni_cio.validation.walk_forward_v1 import build_walk_forward_validation_plan


NOW = datetime(2026, 7, 29, 15, 30, tzinfo=timezone.utc)
START = NOW - timedelta(days=140)
KEY = "uid:stability-a"


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-stability-source",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="stability-source-v1",
    )


def _dataset(*, count: int = 90, dataset_id: str = "stability-dataset-a") -> WalkForwardDatasetV1:
    observations: list[WalkForwardObservationV1] = []
    for index in range(count):
        decision_at = START + timedelta(days=index)
        label_end = decision_at + timedelta(hours=12)
        observations.append(
            WalkForwardObservationV1(
                observation_id=f"observation-{index:03d}",
                instrument_key=KEY,
                feature_window_start=decision_at - timedelta(days=20),
                feature_window_end=decision_at - timedelta(minutes=1),
                feature_data_available_at=decision_at - timedelta(minutes=1),
                universe_snapshot_at=decision_at - timedelta(days=1),
                decision_at=decision_at,
                label_window_start=decision_at,
                label_window_end=label_end,
                label_data_available_at=label_end,
                source_record_id=f"stability-row-{index:03d}",
            )
        )
    return WalkForwardDatasetV1(
        dataset_id=dataset_id,
        instrument_key=KEY,
        source=_source(),
        observations=tuple(observations),
    )


def _plan(
    dataset: WalkForwardDatasetV1,
    *,
    minimum_folds: int = 6,
) -> WalkForwardValidationPlanV1:
    return build_walk_forward_validation_plan(
        dataset,
        policy=WalkForwardValidationPolicyV1(minimum_folds=minimum_folds),
        assessed_at=NOW,
    )


def _outcome(
    observation: WalkForwardObservationV1,
    *,
    gross_return: Decimal = Decimal("0.01"),
    benchmark_return: Decimal = Decimal("0.005"),
    turnover: Decimal = Decimal("0.5"),
    commission_bps: Decimal = Decimal("10"),
    spread_bps: Decimal = Decimal("20"),
    slippage_bps: Decimal = Decimal("5"),
) -> WalkForwardOutcomeV1:
    cost_rate = turnover * (
        commission_bps + spread_bps + slippage_bps
    ) / Decimal("10000")
    return WalkForwardOutcomeV1(
        observation_id=observation.observation_id,
        instrument_key=observation.instrument_key,
        outcome_available_at=observation.label_data_available_at,
        source=_source(),
        strategy_gross_return=gross_return,
        benchmark_return=benchmark_return,
        turnover=turnover,
        commission_bps=commission_bps,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        transaction_cost_rate=cost_rate,
        strategy_net_return=gross_return - cost_rate,
    )


def _outcome_set(
    dataset: WalkForwardDatasetV1,
    plan: WalkForwardValidationPlanV1,
    *,
    gross_returns: dict[str, Decimal] | None = None,
    benchmark_return: Decimal = Decimal("0.005"),
    default_gross_return: Decimal = Decimal("0.01"),
    turnover: Decimal = Decimal("0.5"),
    commission_bps: Decimal = Decimal("10"),
    spread_bps: Decimal = Decimal("20"),
    slippage_bps: Decimal = Decimal("5"),
) -> WalkForwardOutcomeSetV1:
    by_id = {
        observation.observation_id: observation
        for observation in dataset.observations
    }
    expected_ids = tuple(
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    )
    return WalkForwardOutcomeSetV1(
        dataset_id=dataset.dataset_id,
        instrument_key=dataset.instrument_key,
        outcomes=tuple(
            _outcome(
                by_id[observation_id],
                gross_return=(gross_returns or {}).get(
                    observation_id,
                    default_gross_return,
                ),
                benchmark_return=benchmark_return,
                turnover=turnover,
                commission_bps=commission_bps,
                spread_bps=spread_bps,
                slippage_bps=slippage_bps,
            )
            for observation_id in expected_ids
        ),
    )


def _performance(
    dataset: WalkForwardDatasetV1,
    plan: WalkForwardValidationPlanV1,
    outcomes: WalkForwardOutcomeSetV1,
):
    return evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
    )


def _assessment(
    dataset: WalkForwardDatasetV1,
    plan: WalkForwardValidationPlanV1,
    outcomes: WalkForwardOutcomeSetV1,
    *,
    policy: StatisticalStabilityPolicyV1 | None = None,
):
    return assess_walk_forward_statistical_stability(
        plan,
        outcomes,
        _performance(dataset, plan, outcomes),
        policy=policy,
        assessed_at=NOW,
    )


def test_constant_positive_six_fold_result_confirms_exact_significance() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)
    policy = StatisticalStabilityPolicyV1(
        bootstrap_samples=400,
        minimum_folds=6,
    )

    result = _assessment(dataset, plan, outcomes, policy=policy)

    assert result.status is StatisticalStabilityStatus.READY
    assert result.stability_ready is True
    assert result.blockers == ()
    assert result.observation_count == 60
    assert result.fold_count == 6
    assert result.bootstrap_interval is not None
    assert result.bootstrap_interval.lower_bound > 0
    assert result.bootstrap_interval.upper_bound > 0
    assert result.sign_flip_test is not None
    assert result.sign_flip_test.method is SignFlipMethod.EXACT
    assert result.sign_flip_test.permutations_evaluated == 64
    assert result.sign_flip_test.p_value == Decimal("0.03125")
    assert result.statistical_significance_confirmed is True
    assert len(result.cost_scenarios) == 16
    assert len(result.leave_one_fold_out) == 6
    assert result.sensitivity_summary is not None
    assert result.sensitivity_summary.cost_sign_reversal_count == 0
    assert result.sensitivity_summary.leave_one_fold_out_sign_reversal_count == 0
    assert result.trading_methods is False
    assert result.execution_ready is False


def test_deterministic_bootstrap_reproduces_identical_interval() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)
    policy = StatisticalStabilityPolicyV1(
        bootstrap_samples=300,
        minimum_folds=6,
        deterministic_seed=12345,
    )

    first = _assessment(dataset, plan, outcomes, policy=policy)
    second = _assessment(dataset, plan, outcomes, policy=policy)

    assert first.bootstrap_interval == second.bootstrap_interval
    assert first.sign_flip_test == second.sign_flip_test
    assert StatisticalStabilityWarning.DETERMINISTIC_RESAMPLING in first.warnings


def test_mixed_fold_results_report_uncertainty_without_false_significance() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    gross_returns: dict[str, Decimal] = {}
    for index, fold in enumerate(plan.folds):
        gross = Decimal("0.02") if index % 2 == 0 else Decimal("-0.01")
        for observation_id in fold.test_observation_ids:
            gross_returns[observation_id] = gross
    outcomes = _outcome_set(dataset, plan, gross_returns=gross_returns)

    result = _assessment(
        dataset,
        plan,
        outcomes,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=500,
            minimum_folds=6,
        ),
    )

    assert result.stability_ready is True
    assert result.statistical_significance_confirmed is False
    assert result.bootstrap_interval is not None
    assert result.bootstrap_interval.lower_bound <= 0 <= result.bootstrap_interval.upper_bound
    assert StatisticalStabilityWarning.CONFIDENCE_INTERVAL_INCLUDES_ZERO in result.warnings
    assert StatisticalStabilityWarning.SIGN_FLIP_NOT_SIGNIFICANT in result.warnings


def test_cost_stress_can_reverse_a_small_positive_baseline() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(
        dataset,
        plan,
        default_gross_return=Decimal("0.007"),
    )

    result = _assessment(
        dataset,
        plan,
        outcomes,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=300,
            minimum_folds=6,
            high_cost_sensitivity_range_threshold=Decimal("0.01"),
        ),
    )

    assert result.baseline_active_total_return is not None
    assert result.baseline_active_total_return > 0
    assert result.sensitivity_summary is not None
    assert result.sensitivity_summary.cost_sign_reversal_count > 0
    assert StatisticalStabilityWarning.COST_STRESS_SIGN_REVERSAL in result.warnings
    assert StatisticalStabilityWarning.COST_ASSUMPTION_SENSITIVE in result.warnings


def test_leave_one_fold_out_detects_dependence_on_one_strong_fold() -> None:
    dataset = _dataset(count=70)
    plan = _plan(dataset, minimum_folds=4)
    gross_returns: dict[str, Decimal] = {}
    for index, fold in enumerate(plan.folds):
        gross = Decimal("0.10") if index == 0 else Decimal("0.003")
        for observation_id in fold.test_observation_ids:
            gross_returns[observation_id] = gross
    outcomes = _outcome_set(dataset, plan, gross_returns=gross_returns)

    result = _assessment(
        dataset,
        plan,
        outcomes,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=300,
            minimum_folds=4,
        ),
    )

    assert result.baseline_active_total_return is not None
    assert result.baseline_active_total_return > 0
    assert result.sensitivity_summary is not None
    assert result.sensitivity_summary.leave_one_fold_out_sign_reversal_count > 0
    assert StatisticalStabilityWarning.LEAVE_ONE_FOLD_OUT_SIGN_REVERSAL in result.warnings
    assert StatisticalStabilityWarning.LIMITED_FOLD_COUNT in result.warnings


def test_changed_outcomes_are_rejected_against_frozen_performance_baseline() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    original = _outcome_set(dataset, plan)
    performance = _performance(dataset, plan, original)
    changed_rows = list(original.outcomes)
    first_observation = next(
        observation
        for observation in dataset.observations
        if observation.observation_id == changed_rows[0].observation_id
    )
    changed_rows[0] = _outcome(first_observation, gross_return=Decimal("0.03"))
    changed = WalkForwardOutcomeSetV1(
        dataset_id=original.dataset_id,
        instrument_key=original.instrument_key,
        outcomes=tuple(changed_rows),
    )

    result = assess_walk_forward_statistical_stability(
        plan,
        changed,
        performance,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=300,
            minimum_folds=6,
        ),
        assessed_at=NOW,
    )

    assert result.status is StatisticalStabilityStatus.REJECTED
    assert StatisticalStabilityBlocker.BASELINE_PERFORMANCE_MISMATCH in result.blockers
    assert result.bootstrap_interval is None
    assert result.assumption_sensitivity_computed is False


def test_missing_oos_outcome_blocks_all_statistical_metrics() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    complete = _outcome_set(dataset, plan)
    incomplete = WalkForwardOutcomeSetV1(
        dataset_id=complete.dataset_id,
        instrument_key=complete.instrument_key,
        outcomes=complete.outcomes[:-1],
    )
    performance = _performance(dataset, plan, complete)

    result = assess_walk_forward_statistical_stability(
        plan,
        incomplete,
        performance,
        assessed_at=NOW,
    )

    assert result.status is StatisticalStabilityStatus.REJECTED
    assert StatisticalStabilityBlocker.OUTCOME_COVERAGE_MISMATCH in result.blockers
    assert result.bootstrap_interval is None
    assert result.sensitivity_summary is None


def test_not_ready_performance_and_insufficient_folds_are_blocked() -> None:
    dataset = _dataset(count=50)
    plan = _plan(dataset, minimum_folds=3)
    outcomes = _outcome_set(
        dataset,
        plan,
        commission_bps=Decimal("0"),
        spread_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    performance = _performance(dataset, plan, outcomes)

    result = assess_walk_forward_statistical_stability(
        plan,
        outcomes,
        performance,
        assessed_at=NOW,
    )

    assert result.status is StatisticalStabilityStatus.REJECTED
    assert StatisticalStabilityBlocker.PERFORMANCE_EVALUATION_NOT_READY in result.blockers
    assert StatisticalStabilityBlocker.INSUFFICIENT_OBSERVATIONS in result.blockers
    assert StatisticalStabilityBlocker.INSUFFICIENT_FOLDS in result.blockers


def test_economically_invalid_cost_stress_is_explicit_blocker() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(
        dataset,
        plan,
        turnover=Decimal("1000"),
        commission_bps=Decimal("1"),
        spread_bps=Decimal("1"),
        slippage_bps=Decimal("1"),
    )

    result = _assessment(
        dataset,
        plan,
        outcomes,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=300,
            minimum_folds=6,
        ),
    )

    assert result.status is StatisticalStabilityStatus.REJECTED
    assert StatisticalStabilityBlocker.INVALID_COST_STRESS_SCENARIO in result.blockers
    assert result.sensitivity_summary is not None
    assert result.sensitivity_summary.invalid_cost_scenario_count > 0
    assert any(not scenario.metrics_computed for scenario in result.cost_scenarios)


def test_policy_and_result_tampering_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must include the baseline"):
        StatisticalStabilityPolicyV1(
            cost_multipliers=(Decimal("0.5"), Decimal("2")),
        )
    with pytest.raises(ValidationError, match="must be sorted"):
        StatisticalStabilityPolicyV1(
            additional_slippage_bps=(Decimal("5"), Decimal("0")),
        )

    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)
    result = _assessment(
        dataset,
        plan,
        outcomes,
        policy=StatisticalStabilityPolicyV1(
            bootstrap_samples=300,
            minimum_folds=6,
        ),
    )

    payload = result.model_dump()
    payload["statistical_significance_confirmed"] = False
    with pytest.raises(ValidationError, match="significance status"):
        StatisticalStabilityAssessmentV1.model_validate(payload)

    payload = result.model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        StatisticalStabilityAssessmentV1.model_validate(payload)


def test_naive_assessment_timestamp_is_rejected() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)
    performance = _performance(dataset, plan, outcomes)

    with pytest.raises(
        StatisticalStabilityError,
        match="STATISTICAL_STABILITY_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_walk_forward_statistical_stability(
            plan,
            outcomes,
            performance,
            assessed_at=datetime(2026, 7, 29, 15, 30),
        )
