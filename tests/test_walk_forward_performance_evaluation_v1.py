from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.performance import (
    WalkForwardAggregatePerformanceV1,
    WalkForwardOutcomeSetV1,
    WalkForwardOutcomeV1,
    WalkForwardPerformanceBlocker,
    WalkForwardPerformanceEvaluationV1,
    WalkForwardPerformancePolicyV1,
    WalkForwardPerformanceStatus,
    WalkForwardPerformanceWarning,
)
from omni_cio.contracts.v1.validation import (
    WalkForwardDatasetV1,
    WalkForwardObservationV1,
    WalkForwardValidationPolicyV1,
)
from omni_cio.validation.performance_v1 import (
    WalkForwardPerformanceError,
    evaluate_walk_forward_performance,
)
from omni_cio.validation.walk_forward_v1 import build_walk_forward_validation_plan


NOW = datetime(2026, 7, 29, 15, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=100)
KEY = "uid:performance-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-performance-source",
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="performance-source-v1",
    )


def _dataset(
    *,
    dataset_id: str = "performance-dataset-a",
    instrument_key: str = KEY,
    count: int = 70,
) -> WalkForwardDatasetV1:
    observations: list[WalkForwardObservationV1] = []
    for index in range(count):
        decision_at = START + timedelta(days=index)
        label_end = decision_at + timedelta(hours=12)
        observations.append(
            WalkForwardObservationV1(
                observation_id=f"observation-{index:03d}",
                instrument_key=instrument_key,
                feature_window_start=decision_at - timedelta(days=20),
                feature_window_end=decision_at - timedelta(minutes=1),
                feature_data_available_at=decision_at - timedelta(minutes=1),
                universe_snapshot_at=decision_at - timedelta(days=1),
                decision_at=decision_at,
                label_window_start=decision_at,
                label_window_end=label_end,
                label_data_available_at=label_end,
            )
        )
    return WalkForwardDatasetV1(
        dataset_id=dataset_id,
        instrument_key=instrument_key,
        source=_source(),
        observations=tuple(observations),
    )


def _plan(dataset: WalkForwardDatasetV1):
    return build_walk_forward_validation_plan(
        dataset,
        policy=WalkForwardValidationPolicyV1(minimum_folds=4),
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
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    source_retrieved_at: datetime = NOW,
    outcome_available_at: datetime | None = None,
) -> WalkForwardOutcomeV1:
    cost_rate = turnover * (
        commission_bps + spread_bps + slippage_bps
    ) / Decimal("10000")
    return WalkForwardOutcomeV1(
        observation_id=observation.observation_id,
        instrument_key=observation.instrument_key,
        outcome_available_at=(
            outcome_available_at or observation.label_data_available_at
        ),
        source=_source(
            authority=authority,
            retrieved_at=source_retrieved_at,
        ),
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
    plan,
    *,
    gross_returns: dict[str, Decimal] | None = None,
    benchmark_returns: dict[str, Decimal] | None = None,
    zero_costs: bool = False,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
) -> WalkForwardOutcomeSetV1:
    observations = {
        observation.observation_id: observation
        for observation in dataset.observations
    }
    expected_ids = tuple(
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    )
    outcomes = tuple(
        _outcome(
            observations[observation_id],
            gross_return=(gross_returns or {}).get(
                observation_id,
                Decimal("0.01"),
            ),
            benchmark_return=(benchmark_returns or {}).get(
                observation_id,
                Decimal("0.005"),
            ),
            commission_bps=Decimal("0") if zero_costs else Decimal("10"),
            spread_bps=Decimal("0") if zero_costs else Decimal("20"),
            slippage_bps=Decimal("0") if zero_costs else Decimal("5"),
            authority=authority,
        )
        for observation_id in expected_ids
    )
    return WalkForwardOutcomeSetV1(
        dataset_id=dataset.dataset_id,
        instrument_key=dataset.instrument_key,
        outcomes=outcomes,
    )


def test_ready_evaluation_compounds_oos_returns_costs_and_benchmark() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)

    result = evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
    )

    assert result.status is WalkForwardPerformanceStatus.READY
    assert result.evaluation_ready is True
    assert result.blockers == ()
    assert result.expected_outcome_count == 40
    assert result.evaluated_outcome_count == 40
    assert result.evaluated_fold_count == 4
    assert result.aggregate_performance is not None
    aggregate = result.aggregate_performance
    expected_gross = (Decimal("1.01") ** 40) - Decimal("1")
    expected_net = (Decimal("1.00825") ** 40) - Decimal("1")
    expected_benchmark = (Decimal("1.005") ** 40) - Decimal("1")
    assert aggregate.gross_total_return == expected_gross
    assert aggregate.net_total_return == expected_net
    assert aggregate.benchmark_total_return == expected_benchmark
    assert aggregate.active_total_return == expected_net - expected_benchmark
    assert aggregate.cost_drag == expected_gross - expected_net
    assert aggregate.total_turnover == Decimal("20")
    assert aggregate.average_turnover == Decimal("0.5")
    assert aggregate.positive_return_rate == Decimal("1")
    assert aggregate.benchmark_outperformance_rate == Decimal("1")
    assert aggregate.max_drawdown == Decimal("0")
    assert aggregate.profitable_fold_rate == Decimal("1")
    assert aggregate.benchmark_beating_fold_rate == Decimal("1")
    assert result.transaction_costs_evaluated is True
    assert result.historical_performance_not_forecast is True
    assert result.trading_methods is False


def test_negative_underperforming_sequence_reports_drawdown_and_warnings() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    expected_ids = [
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    ]
    gross_returns = {
        observation_id: (
            Decimal("-0.03") if index % 2 == 0 else Decimal("0.01")
        )
        for index, observation_id in enumerate(expected_ids)
    }
    benchmark_returns = {
        observation_id: Decimal("0.002") for observation_id in expected_ids
    }
    outcomes = _outcome_set(
        dataset,
        plan,
        gross_returns=gross_returns,
        benchmark_returns=benchmark_returns,
    )

    result = evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
    )

    assert result.aggregate_performance is not None
    assert result.aggregate_performance.net_total_return < 0
    assert result.aggregate_performance.max_drawdown > 0
    assert result.aggregate_performance.max_drawdown_duration_observations > 0
    assert WalkForwardPerformanceWarning.NEGATIVE_NET_RETURN in result.warnings
    assert WalkForwardPerformanceWarning.UNDERPERFORMS_BENCHMARK in result.warnings


def test_zero_cost_assumptions_block_readiness_without_hiding_metrics() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan, zero_costs=True)

    result = evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
    )

    assert result.status is WalkForwardPerformanceStatus.REJECTED
    assert result.aggregate_performance is not None
    assert result.transaction_costs_evaluated is False
    assert WalkForwardPerformanceBlocker.TRANSACTION_COST_MODEL_MISSING in result.blockers


def test_missing_or_extra_outcomes_disable_performance_metrics() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    complete = _outcome_set(dataset, plan)

    missing = WalkForwardOutcomeSetV1(
        dataset_id=complete.dataset_id,
        instrument_key=complete.instrument_key,
        outcomes=complete.outcomes[:-1],
    )
    missing_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        missing,
        assessed_at=NOW,
    )
    assert missing_result.aggregate_performance is None
    assert WalkForwardPerformanceBlocker.OUTCOME_COVERAGE_MISMATCH in missing_result.blockers

    train_observation = dataset.observations[0]
    extra = WalkForwardOutcomeSetV1(
        dataset_id=complete.dataset_id,
        instrument_key=complete.instrument_key,
        outcomes=complete.outcomes + (_outcome(train_observation),),
    )
    extra_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        extra,
        assessed_at=NOW,
    )
    assert extra_result.aggregate_performance is None
    assert WalkForwardPerformanceBlocker.OUTCOME_COVERAGE_MISMATCH in extra_result.blockers
    assert WalkForwardPerformanceBlocker.OUTCOME_NOT_OUT_OF_SAMPLE in extra_result.blockers


def test_outcome_timing_authority_and_future_source_block_readiness() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    complete = _outcome_set(dataset, plan)
    first_id = complete.outcomes[0].observation_id
    observation = next(
        item for item in dataset.observations if item.observation_id == first_id
    )

    rows = list(complete.outcomes)
    rows[0] = _outcome(
        observation,
        outcome_available_at=observation.label_data_available_at - timedelta(seconds=1),
    )
    early = WalkForwardOutcomeSetV1(
        dataset_id=complete.dataset_id,
        instrument_key=complete.instrument_key,
        outcomes=tuple(rows),
    )
    early_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        early,
        assessed_at=NOW,
    )
    assert early_result.aggregate_performance is None
    assert WalkForwardPerformanceBlocker.OUTCOME_AVAILABLE_BEFORE_LABEL in early_result.blockers

    untrusted = _outcome_set(
        dataset,
        plan,
        authority=SourceAuthority.SECONDARY,
    )
    untrusted_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        untrusted,
        assessed_at=NOW,
    )
    assert untrusted_result.aggregate_performance is not None
    assert WalkForwardPerformanceBlocker.UNTRUSTED_SOURCE in untrusted_result.blockers

    future_rows = list(complete.outcomes)
    future_rows[0] = _outcome(
        observation,
        source_retrieved_at=NOW + timedelta(minutes=10),
    )
    future = WalkForwardOutcomeSetV1(
        dataset_id=complete.dataset_id,
        instrument_key=complete.instrument_key,
        outcomes=tuple(future_rows),
    )
    future_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        future,
        assessed_at=NOW,
    )
    assert WalkForwardPerformanceBlocker.SOURCE_RETRIEVED_IN_FUTURE in future_result.blockers


def test_plan_dataset_and_instrument_mismatches_are_blocked() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)

    other_dataset = _dataset(dataset_id="other-dataset")
    dataset_result = evaluate_walk_forward_performance(
        plan,
        other_dataset,
        outcomes,
        assessed_at=NOW,
    )
    assert dataset_result.aggregate_performance is None
    assert WalkForwardPerformanceBlocker.PLAN_DATASET_MISMATCH in dataset_result.blockers

    other_outcomes_payload = outcomes.model_dump()
    other_outcomes_payload["instrument_key"] = "uid:other-instrument"
    other_outcomes_payload["outcomes"] = tuple(
        {
            **outcome,
            "instrument_key": "uid:other-instrument",
        }
        for outcome in other_outcomes_payload["outcomes"]
    )
    other_outcomes = WalkForwardOutcomeSetV1.model_validate(other_outcomes_payload)
    instrument_result = evaluate_walk_forward_performance(
        plan,
        dataset,
        other_outcomes,
        assessed_at=NOW,
    )
    assert instrument_result.aggregate_performance is None
    assert WalkForwardPerformanceBlocker.INSTRUMENT_MISMATCH in instrument_result.blockers


def test_policy_thresholds_surface_turnover_cost_and_fold_instability() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    expected_ids = [
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    ]
    gross_returns = {
        observation_id: (
            Decimal("0.20") if index < 10 else Decimal("-0.02")
        )
        for index, observation_id in enumerate(expected_ids)
    }
    observations = {
        observation.observation_id: observation
        for observation in dataset.observations
    }
    outcomes = WalkForwardOutcomeSetV1(
        dataset_id=dataset.dataset_id,
        instrument_key=dataset.instrument_key,
        outcomes=tuple(
            _outcome(
                observations[observation_id],
                gross_return=gross_returns[observation_id],
                turnover=Decimal("2"),
                commission_bps=Decimal("50"),
                spread_bps=Decimal("50"),
                slippage_bps=Decimal("50"),
            )
            for observation_id in expected_ids
        ),
    )

    result = evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
        policy=WalkForwardPerformancePolicyV1(
            high_average_turnover_threshold=Decimal("1"),
            high_cost_drag_threshold=Decimal("0.01"),
            unstable_fold_return_range_threshold=Decimal("0.10"),
        ),
    )

    assert WalkForwardPerformanceWarning.HIGH_AVERAGE_TURNOVER in result.warnings
    assert WalkForwardPerformanceWarning.HIGH_COST_DRAG in result.warnings
    assert WalkForwardPerformanceWarning.FOLD_RESULTS_UNSTABLE in result.warnings


def test_outcome_and_metric_reconciliation_reject_tampering() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)
    first = outcomes.outcomes[0]

    payload = first.model_dump()
    payload["transaction_cost_rate"] = Decimal("99")
    with pytest.raises(ValidationError, match="transaction cost"):
        WalkForwardOutcomeV1.model_validate(payload)

    payload = first.model_dump()
    payload["strategy_net_return"] = Decimal("0")
    with pytest.raises(ValidationError, match="net return"):
        WalkForwardOutcomeV1.model_validate(payload)

    result = evaluate_walk_forward_performance(
        plan,
        dataset,
        outcomes,
        assessed_at=NOW,
    )
    assert result.aggregate_performance is not None
    aggregate_payload = result.aggregate_performance.model_dump()
    aggregate_payload["active_total_return"] = Decimal("99")
    with pytest.raises(ValidationError, match="active return"):
        WalkForwardAggregatePerformanceV1.model_validate(aggregate_payload)

    result_payload = result.model_dump()
    result_payload["evaluated_outcome_count"] = 999
    with pytest.raises(ValidationError, match="evaluated outcome count"):
        WalkForwardPerformanceEvaluationV1.model_validate(result_payload)


def test_safety_flags_and_naive_assessment_timestamp_are_rejected() -> None:
    dataset = _dataset()
    plan = _plan(dataset)
    outcomes = _outcome_set(dataset, plan)

    payload = outcomes.model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        WalkForwardOutcomeSetV1.model_validate(payload)

    with pytest.raises(
        WalkForwardPerformanceError,
        match="WALK_FORWARD_PERFORMANCE_TIMESTAMP_MUST_BE_AWARE",
    ):
        evaluate_walk_forward_performance(
            plan,
            dataset,
            outcomes,
            assessed_at=datetime(2026, 7, 29, 15, 0),
        )
