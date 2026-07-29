from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.performance import (
    WalkForwardAggregatePerformanceV1,
    WalkForwardFoldPerformanceV1,
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
    WalkForwardValidationPlanV1,
)


class WalkForwardPerformanceError(ValueError):
    """The supplied walk-forward performance request is invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise WalkForwardPerformanceError(
            "WALK_FORWARD_PERFORMANCE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _compound(returns: list[Decimal]) -> Decimal:
    wealth = Decimal("1")
    for value in returns:
        wealth *= Decimal("1") + value
    return wealth - Decimal("1")


def _drawdown(returns: list[Decimal]) -> tuple[Decimal, int]:
    wealth = Decimal("1")
    peak = Decimal("1")
    maximum_drawdown = Decimal("0")
    current_duration = 0
    maximum_duration = 0
    for value in returns:
        wealth *= Decimal("1") + value
        if wealth >= peak:
            peak = wealth
            current_duration = 0
        else:
            current_duration += 1
            maximum_duration = max(maximum_duration, current_duration)
            maximum_drawdown = max(
                maximum_drawdown,
                (peak - wealth) / peak,
            )
    return maximum_drawdown, maximum_duration


def _volatility(returns: list[Decimal]) -> Decimal:
    if len(returns) <= 1:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum(
        ((value - mean) * (value - mean) for value in returns),
        Decimal("0"),
    ) / Decimal(len(returns))
    return variance.sqrt()


def _rate(numerator: int, denominator: int) -> Decimal:
    return Decimal(numerator) / Decimal(denominator)


def _fold_metrics(
    fold_number: int,
    outcomes: list[WalkForwardOutcomeV1],
) -> WalkForwardFoldPerformanceV1:
    gross_returns = [outcome.strategy_gross_return for outcome in outcomes]
    net_returns = [outcome.strategy_net_return for outcome in outcomes]
    benchmark_returns = [outcome.benchmark_return for outcome in outcomes]
    gross_total = _compound(gross_returns)
    net_total = _compound(net_returns)
    benchmark_total = _compound(benchmark_returns)
    total_turnover = sum(
        (outcome.turnover for outcome in outcomes),
        Decimal("0"),
    )
    max_drawdown, max_duration = _drawdown(net_returns)
    return WalkForwardFoldPerformanceV1(
        fold_number=fold_number,
        observation_count=len(outcomes),
        gross_total_return=gross_total,
        net_total_return=net_total,
        benchmark_total_return=benchmark_total,
        active_total_return=net_total - benchmark_total,
        cost_drag=gross_total - net_total,
        total_turnover=total_turnover,
        average_turnover=total_turnover / Decimal(len(outcomes)),
        positive_return_rate=_rate(
            sum(value > 0 for value in net_returns),
            len(outcomes),
        ),
        benchmark_outperformance_rate=_rate(
            sum(
                net > benchmark
                for net, benchmark in zip(
                    net_returns,
                    benchmark_returns,
                    strict=True,
                )
            ),
            len(outcomes),
        ),
        max_drawdown=max_drawdown,
        max_drawdown_duration_observations=max_duration,
    )


def _aggregate_metrics(
    outcomes: list[WalkForwardOutcomeV1],
    folds: list[WalkForwardFoldPerformanceV1],
) -> WalkForwardAggregatePerformanceV1:
    gross_returns = [outcome.strategy_gross_return for outcome in outcomes]
    net_returns = [outcome.strategy_net_return for outcome in outcomes]
    benchmark_returns = [outcome.benchmark_return for outcome in outcomes]
    gross_total = _compound(gross_returns)
    net_total = _compound(net_returns)
    benchmark_total = _compound(benchmark_returns)
    total_turnover = sum(
        (outcome.turnover for outcome in outcomes),
        Decimal("0"),
    )
    max_drawdown, max_duration = _drawdown(net_returns)
    fold_returns = [fold.net_total_return for fold in folds]
    return WalkForwardAggregatePerformanceV1(
        observation_count=len(outcomes),
        fold_count=len(folds),
        gross_total_return=gross_total,
        net_total_return=net_total,
        benchmark_total_return=benchmark_total,
        active_total_return=net_total - benchmark_total,
        cost_drag=gross_total - net_total,
        total_turnover=total_turnover,
        average_turnover=total_turnover / Decimal(len(outcomes)),
        mean_net_return=sum(net_returns, Decimal("0")) / Decimal(len(outcomes)),
        realized_volatility=_volatility(net_returns),
        positive_return_rate=_rate(
            sum(value > 0 for value in net_returns),
            len(outcomes),
        ),
        benchmark_outperformance_rate=_rate(
            sum(
                net > benchmark
                for net, benchmark in zip(
                    net_returns,
                    benchmark_returns,
                    strict=True,
                )
            ),
            len(outcomes),
        ),
        max_drawdown=max_drawdown,
        max_drawdown_duration_observations=max_duration,
        minimum_fold_net_return=min(fold_returns),
        maximum_fold_net_return=max(fold_returns),
        fold_net_return_range=max(fold_returns) - min(fold_returns),
        profitable_fold_rate=_rate(
            sum(value > 0 for value in fold_returns),
            len(folds),
        ),
        benchmark_beating_fold_rate=_rate(
            sum(
                fold.net_total_return > fold.benchmark_total_return
                for fold in folds
            ),
            len(folds),
        ),
    )


def evaluate_walk_forward_performance(
    plan: WalkForwardValidationPlanV1,
    dataset: WalkForwardDatasetV1,
    outcome_set: WalkForwardOutcomeSetV1,
    *,
    policy: WalkForwardPerformancePolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> WalkForwardPerformanceEvaluationV1:
    """Evaluate immutable out-of-sample outcomes with explicit transaction costs."""

    active_policy = policy or WalkForwardPerformancePolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    blockers: list[WalkForwardPerformanceBlocker] = []
    warnings: list[WalkForwardPerformanceWarning] = [
        WalkForwardPerformanceWarning.NO_STATISTICAL_SIGNIFICANCE_TEST,
        WalkForwardPerformanceWarning.NO_CAPACITY_ANALYSIS,
        WalkForwardPerformanceWarning.SINGLE_INSTRUMENT_EVALUATION,
        WalkForwardPerformanceWarning.PERFORMANCE_IS_HISTORICAL_NOT_FORECAST,
    ]

    if not plan.validation_ready:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.VALIDATION_PLAN_NOT_READY,
        )
    if plan.dataset_id != dataset.dataset_id or plan.dataset_id != outcome_set.dataset_id:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.PLAN_DATASET_MISMATCH,
        )
    if (
        plan.instrument_key != dataset.instrument_key
        or plan.instrument_key != outcome_set.instrument_key
    ):
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.INSTRUMENT_MISMATCH,
        )

    expected_ids = tuple(
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    )
    expected_set = set(expected_ids)
    provided_by_id = {
        outcome.observation_id: outcome for outcome in outcome_set.outcomes
    }
    provided_set = set(provided_by_id)
    if provided_set != expected_set:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.OUTCOME_COVERAGE_MISMATCH,
        )
    if provided_set - expected_set:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.OUTCOME_NOT_OUT_OF_SAMPLE,
        )

    observations_by_id = {
        observation.observation_id: observation
        for observation in dataset.observations
    }
    for outcome in outcome_set.outcomes:
        observation = observations_by_id.get(outcome.observation_id)
        if observation is None or outcome.observation_id not in expected_set:
            continue
        if outcome.outcome_available_at < observation.label_data_available_at:
            _append_unique(
                blockers,
                WalkForwardPerformanceBlocker.OUTCOME_AVAILABLE_BEFORE_LABEL,
            )
        if outcome.source.authority not in active_policy.trusted_authorities:
            _append_unique(
                blockers,
                WalkForwardPerformanceBlocker.UNTRUSTED_SOURCE,
            )
        if (
            outcome.source.retrieved_at - evaluation_time
        ).total_seconds() > active_policy.future_tolerance_seconds:
            _append_unique(
                blockers,
                WalkForwardPerformanceBlocker.SOURCE_RETRIEVED_IN_FUTURE,
            )

    if len(expected_ids) < active_policy.minimum_out_of_sample_observations:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.INSUFFICIENT_OUT_OF_SAMPLE_OBSERVATIONS,
        )
    if len(plan.folds) < active_policy.minimum_evaluated_folds:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.INSUFFICIENT_EVALUATED_FOLDS,
        )

    positive_cost_model = any(
        outcome.commission_bps > 0
        or outcome.spread_bps > 0
        or outcome.slippage_bps > 0
        for outcome in outcome_set.outcomes
    )
    if active_policy.require_positive_transaction_cost_model and not positive_cost_model:
        _append_unique(
            blockers,
            WalkForwardPerformanceBlocker.TRANSACTION_COST_MODEL_MISSING,
        )

    structural_blockers = {
        WalkForwardPerformanceBlocker.VALIDATION_PLAN_NOT_READY,
        WalkForwardPerformanceBlocker.PLAN_DATASET_MISMATCH,
        WalkForwardPerformanceBlocker.INSTRUMENT_MISMATCH,
        WalkForwardPerformanceBlocker.OUTCOME_COVERAGE_MISMATCH,
        WalkForwardPerformanceBlocker.OUTCOME_NOT_OUT_OF_SAMPLE,
        WalkForwardPerformanceBlocker.OUTCOME_AVAILABLE_BEFORE_LABEL,
    }
    metrics_allowed = not any(blocker in structural_blockers for blocker in blockers)
    fold_performance: list[WalkForwardFoldPerformanceV1] = []
    ordered_outcomes: list[WalkForwardOutcomeV1] = []
    if metrics_allowed:
        for fold in plan.folds:
            fold_outcomes = [
                provided_by_id[observation_id]
                for observation_id in fold.test_observation_ids
            ]
            ordered_outcomes.extend(fold_outcomes)
            fold_performance.append(
                _fold_metrics(fold.fold_number, fold_outcomes)
            )

    aggregate = (
        _aggregate_metrics(ordered_outcomes, fold_performance)
        if ordered_outcomes and fold_performance
        else None
    )
    if aggregate is not None:
        if aggregate.net_total_return < 0:
            _append_unique(
                warnings,
                WalkForwardPerformanceWarning.NEGATIVE_NET_RETURN,
            )
        if aggregate.net_total_return < aggregate.benchmark_total_return:
            _append_unique(
                warnings,
                WalkForwardPerformanceWarning.UNDERPERFORMS_BENCHMARK,
            )
        if (
            aggregate.average_turnover
            > active_policy.high_average_turnover_threshold
        ):
            _append_unique(
                warnings,
                WalkForwardPerformanceWarning.HIGH_AVERAGE_TURNOVER,
            )
        if aggregate.cost_drag > active_policy.high_cost_drag_threshold:
            _append_unique(
                warnings,
                WalkForwardPerformanceWarning.HIGH_COST_DRAG,
            )
        if (
            aggregate.fold_net_return_range
            > active_policy.unstable_fold_return_range_threshold
        ):
            _append_unique(
                warnings,
                WalkForwardPerformanceWarning.FOLD_RESULTS_UNSTABLE,
            )

    evaluation_ready = not blockers and aggregate is not None
    status = (
        WalkForwardPerformanceStatus.READY
        if evaluation_ready
        else WalkForwardPerformanceStatus.REJECTED
    )
    return WalkForwardPerformanceEvaluationV1(
        assessed_at=evaluation_time,
        status=status,
        evaluation_ready=evaluation_ready,
        dataset_id=outcome_set.dataset_id,
        instrument_key=outcome_set.instrument_key,
        policy=active_policy,
        expected_outcome_count=len(expected_ids),
        provided_outcome_count=len(outcome_set.outcomes),
        evaluated_outcome_count=len(ordered_outcomes),
        evaluated_fold_count=len(fold_performance),
        fold_performance=tuple(fold_performance),
        aggregate_performance=aggregate,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        transaction_costs_evaluated=positive_cost_model,
        performance_metrics_computed=aggregate is not None,
    )
