from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal

from omni_cio.contracts.v1.performance import (
    WalkForwardOutcomeSetV1,
    WalkForwardOutcomeV1,
    WalkForwardPerformanceEvaluationV1,
)
from omni_cio.contracts.v1.stability import (
    BootstrapIntervalV1,
    CostSensitivityScenarioV1,
    LeaveOneFoldOutScenarioV1,
    SensitivitySummaryV1,
    SignFlipMethod,
    SignFlipTestV1,
    StatisticalStabilityAssessmentV1,
    StatisticalStabilityBlocker,
    StatisticalStabilityPolicyV1,
    StatisticalStabilityStatus,
    StatisticalStabilityWarning,
)
from omni_cio.contracts.v1.validation import WalkForwardValidationPlanV1


class StatisticalStabilityError(ValueError):
    """The supplied OOS statistical stability request is invalid."""


_LCG_MODULUS = 2**32
_LCG_MULTIPLIER = 1_664_525
_LCG_INCREMENT = 1_013_904_223


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise StatisticalStabilityError(
            "STATISTICAL_STABILITY_TIMESTAMP_MUST_BE_AWARE"
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


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _next_state(state: int) -> int:
    return (_LCG_MULTIPLIER * state + _LCG_INCREMENT) % _LCG_MODULUS


def _nearest_rank(values: list[Decimal], probability: Decimal) -> Decimal:
    ordered = sorted(values)
    raw_rank = (probability * Decimal(len(ordered))).to_integral_value(
        rounding=ROUND_CEILING
    )
    rank = max(1, int(raw_rank))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _bootstrap_interval(
    fold_active_returns: list[Decimal],
    policy: StatisticalStabilityPolicyV1,
) -> BootstrapIntervalV1:
    state = policy.deterministic_seed
    samples: list[Decimal] = []
    fold_count = len(fold_active_returns)
    for _ in range(policy.bootstrap_samples):
        sampled_sum = Decimal("0")
        for _ in range(fold_count):
            state = _next_state(state)
            sampled_sum += fold_active_returns[state % fold_count]
        samples.append(sampled_sum / Decimal(fold_count))

    tail_probability = (Decimal("1") - policy.confidence_level) / Decimal("2")
    upper_probability = Decimal("1") - tail_probability
    return BootstrapIntervalV1(
        fold_count=fold_count,
        sample_count=policy.bootstrap_samples,
        confidence_level=policy.confidence_level,
        deterministic_seed=policy.deterministic_seed,
        observed_value=_mean(fold_active_returns),
        lower_bound=_nearest_rank(samples, tail_probability),
        median=_nearest_rank(samples, Decimal("0.5")),
        upper_bound=_nearest_rank(samples, upper_probability),
        probability_positive=Decimal(sum(value > 0 for value in samples))
        / Decimal(len(samples)),
    )


def _sign_flip_test(
    fold_active_returns: list[Decimal],
    policy: StatisticalStabilityPolicyV1,
) -> SignFlipTestV1:
    observed = _mean(fold_active_returns)
    observed_absolute = abs(observed)
    fold_count = len(fold_active_returns)
    significance_level = Decimal("1") - policy.confidence_level

    if fold_count <= policy.exact_sign_flip_max_folds:
        permutations = 2**fold_count
        extreme = 0
        for mask in range(permutations):
            signed_sum = Decimal("0")
            for index, value in enumerate(fold_active_returns):
                sign = Decimal("1") if mask & (1 << index) else Decimal("-1")
                signed_sum += sign * value
            permuted_mean = signed_sum / Decimal(fold_count)
            if abs(permuted_mean) >= observed_absolute:
                extreme += 1
        p_value = Decimal(extreme) / Decimal(permutations)
        method = SignFlipMethod.EXACT
        evaluated = permutations
    else:
        state = policy.deterministic_seed
        extreme = 0
        for _ in range(policy.sign_flip_samples):
            signed_sum = Decimal("0")
            for value in fold_active_returns:
                state = _next_state(state)
                sign = Decimal("1") if state & 1 else Decimal("-1")
                signed_sum += sign * value
            if abs(signed_sum / Decimal(fold_count)) >= observed_absolute:
                extreme += 1
        p_value = Decimal(extreme + 1) / Decimal(policy.sign_flip_samples + 1)
        method = SignFlipMethod.DETERMINISTIC_MONTE_CARLO
        evaluated = policy.sign_flip_samples

    return SignFlipTestV1(
        method=method,
        fold_count=fold_count,
        permutations_evaluated=evaluated,
        deterministic_seed=policy.deterministic_seed,
        observed_mean_active_return=observed,
        p_value=p_value,
        significance_level=significance_level,
        statistically_significant=p_value <= significance_level,
    )


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _sign_reversal(baseline: Decimal, candidate: Decimal) -> bool:
    return _sign(baseline) != _sign(candidate)


def _scenario_id(multiplier: Decimal, extra_slippage_bps: Decimal) -> str:
    multiplier_text = format(multiplier, "f").replace(".", "p")
    slippage_text = format(extra_slippage_bps, "f").replace(".", "p")
    return f"cost-x{multiplier_text}-extra-slippage-{slippage_text}bps"


def _cost_scenarios(
    ordered_outcomes: list[WalkForwardOutcomeV1],
    baseline_active_total_return: Decimal,
    policy: StatisticalStabilityPolicyV1,
) -> tuple[CostSensitivityScenarioV1, ...]:
    benchmark_returns = [outcome.benchmark_return for outcome in ordered_outcomes]
    benchmark_total = _compound(benchmark_returns)
    scenarios: list[CostSensitivityScenarioV1] = []
    for multiplier in policy.cost_multipliers:
        for extra_slippage_bps in policy.additional_slippage_bps:
            stressed_returns: list[Decimal] = []
            invalid_count = 0
            for outcome in ordered_outcomes:
                base_cost_bps = (
                    outcome.commission_bps
                    + outcome.spread_bps
                    + outcome.slippage_bps
                )
                stressed_cost_rate = outcome.turnover * (
                    base_cost_bps * multiplier + extra_slippage_bps
                ) / Decimal("10000")
                stressed_net = outcome.strategy_gross_return - stressed_cost_rate
                if stressed_net <= Decimal("-1"):
                    invalid_count += 1
                else:
                    stressed_returns.append(stressed_net)

            if invalid_count:
                scenarios.append(
                    CostSensitivityScenarioV1(
                        scenario_id=_scenario_id(multiplier, extra_slippage_bps),
                        cost_multiplier=multiplier,
                        additional_slippage_bps=extra_slippage_bps,
                        observation_count=len(ordered_outcomes),
                        invalid_observation_count=invalid_count,
                        metrics_computed=False,
                    )
                )
                continue

            net_total = _compound(stressed_returns)
            active_total = net_total - benchmark_total
            scenarios.append(
                CostSensitivityScenarioV1(
                    scenario_id=_scenario_id(multiplier, extra_slippage_bps),
                    cost_multiplier=multiplier,
                    additional_slippage_bps=extra_slippage_bps,
                    observation_count=len(ordered_outcomes),
                    invalid_observation_count=0,
                    metrics_computed=True,
                    net_total_return=net_total,
                    benchmark_total_return=benchmark_total,
                    active_total_return=active_total,
                    active_positive=active_total > 0,
                    sign_reversal_from_baseline=_sign_reversal(
                        baseline_active_total_return,
                        active_total,
                    ),
                )
            )
    return tuple(scenarios)


def _leave_one_fold_out(
    fold_outcomes: list[tuple[int, list[WalkForwardOutcomeV1]]],
    baseline_active_total_return: Decimal,
) -> tuple[LeaveOneFoldOutScenarioV1, ...]:
    scenarios: list[LeaveOneFoldOutScenarioV1] = []
    for omitted_fold_number, _ in fold_outcomes:
        retained = [
            outcome
            for fold_number, outcomes in fold_outcomes
            if fold_number != omitted_fold_number
            for outcome in outcomes
        ]
        net_total = _compound([outcome.strategy_net_return for outcome in retained])
        benchmark_total = _compound([outcome.benchmark_return for outcome in retained])
        active_total = net_total - benchmark_total
        scenarios.append(
            LeaveOneFoldOutScenarioV1(
                omitted_fold_number=omitted_fold_number,
                observation_count=len(retained),
                net_total_return=net_total,
                benchmark_total_return=benchmark_total,
                active_total_return=active_total,
                active_positive=active_total > 0,
                sign_reversal_from_baseline=_sign_reversal(
                    baseline_active_total_return,
                    active_total,
                ),
            )
        )
    return tuple(scenarios)


def _sensitivity_summary(
    cost_scenarios: tuple[CostSensitivityScenarioV1, ...],
    leave_one_fold_out: tuple[LeaveOneFoldOutScenarioV1, ...],
) -> SensitivitySummaryV1:
    valid_cost = [scenario for scenario in cost_scenarios if scenario.metrics_computed]
    cost_active = [
        scenario.active_total_return
        for scenario in valid_cost
        if scenario.active_total_return is not None
    ]
    leave_active = [scenario.active_total_return for scenario in leave_one_fold_out]
    cost_minimum = min(cost_active)
    cost_maximum = max(cost_active)
    leave_minimum = min(leave_active)
    leave_maximum = max(leave_active)
    return SensitivitySummaryV1(
        cost_scenario_count=len(cost_scenarios),
        valid_cost_scenario_count=len(valid_cost),
        invalid_cost_scenario_count=len(cost_scenarios) - len(valid_cost),
        cost_active_return_minimum=cost_minimum,
        cost_active_return_maximum=cost_maximum,
        cost_active_return_range=cost_maximum - cost_minimum,
        cost_sign_reversal_count=sum(
            scenario.sign_reversal_from_baseline is True for scenario in valid_cost
        ),
        leave_one_fold_out_count=len(leave_one_fold_out),
        leave_one_fold_out_active_minimum=leave_minimum,
        leave_one_fold_out_active_maximum=leave_maximum,
        leave_one_fold_out_active_range=leave_maximum - leave_minimum,
        leave_one_fold_out_sign_reversal_count=sum(
            scenario.sign_reversal_from_baseline for scenario in leave_one_fold_out
        ),
    )


def assess_walk_forward_statistical_stability(
    plan: WalkForwardValidationPlanV1,
    outcome_set: WalkForwardOutcomeSetV1,
    performance: WalkForwardPerformanceEvaluationV1,
    *,
    policy: StatisticalStabilityPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> StatisticalStabilityAssessmentV1:
    """Assess uncertainty and assumption sensitivity of immutable OOS outcomes."""

    active_policy = policy or StatisticalStabilityPolicyV1()
    assessment_time = _aware_utc(assessed_at)
    blockers: list[StatisticalStabilityBlocker] = []
    warnings: list[StatisticalStabilityWarning] = [
        StatisticalStabilityWarning.DETERMINISTIC_RESAMPLING,
        StatisticalStabilityWarning.NO_HYPERPARAMETER_SEARCH,
        StatisticalStabilityWarning.SINGLE_INSTRUMENT_EVALUATION,
        StatisticalStabilityWarning.NO_CAPACITY_ANALYSIS,
        StatisticalStabilityWarning.HISTORICAL_PERFORMANCE_NOT_FORECAST,
    ]

    if not performance.evaluation_ready or performance.aggregate_performance is None:
        _append_unique(
            blockers,
            StatisticalStabilityBlocker.PERFORMANCE_EVALUATION_NOT_READY,
        )
    if plan.dataset_id != outcome_set.dataset_id or plan.dataset_id != performance.dataset_id:
        _append_unique(blockers, StatisticalStabilityBlocker.DATASET_MISMATCH)
    if (
        plan.instrument_key != outcome_set.instrument_key
        or plan.instrument_key != performance.instrument_key
    ):
        _append_unique(blockers, StatisticalStabilityBlocker.INSTRUMENT_MISMATCH)

    expected_ids = tuple(
        observation_id
        for fold in plan.folds
        for observation_id in fold.test_observation_ids
    )
    provided_by_id = {
        outcome.observation_id: outcome for outcome in outcome_set.outcomes
    }
    if set(provided_by_id) != set(expected_ids):
        _append_unique(
            blockers,
            StatisticalStabilityBlocker.OUTCOME_COVERAGE_MISMATCH,
        )
    if len(expected_ids) < active_policy.minimum_observations:
        _append_unique(
            blockers,
            StatisticalStabilityBlocker.INSUFFICIENT_OBSERVATIONS,
        )
    if len(plan.folds) < active_policy.minimum_folds:
        _append_unique(blockers, StatisticalStabilityBlocker.INSUFFICIENT_FOLDS)
    if len(plan.folds) < active_policy.limited_fold_warning_below:
        _append_unique(warnings, StatisticalStabilityWarning.LIMITED_FOLD_COUNT)

    structural_blockers = {
        StatisticalStabilityBlocker.PERFORMANCE_EVALUATION_NOT_READY,
        StatisticalStabilityBlocker.DATASET_MISMATCH,
        StatisticalStabilityBlocker.INSTRUMENT_MISMATCH,
        StatisticalStabilityBlocker.OUTCOME_COVERAGE_MISMATCH,
        StatisticalStabilityBlocker.INSUFFICIENT_OBSERVATIONS,
        StatisticalStabilityBlocker.INSUFFICIENT_FOLDS,
    }
    metrics_allowed = not any(blocker in structural_blockers for blocker in blockers)

    ordered_outcomes: list[WalkForwardOutcomeV1] = []
    fold_outcomes: list[tuple[int, list[WalkForwardOutcomeV1]]] = []
    fold_active_returns: list[Decimal] = []
    baseline_active: Decimal | None = None
    if metrics_allowed:
        for fold in plan.folds:
            rows = [provided_by_id[item] for item in fold.test_observation_ids]
            fold_outcomes.append((fold.fold_number, rows))
            ordered_outcomes.extend(rows)
            net_total = _compound([row.strategy_net_return for row in rows])
            benchmark_total = _compound([row.benchmark_return for row in rows])
            fold_active_returns.append(net_total - benchmark_total)

        net_total = _compound(
            [outcome.strategy_net_return for outcome in ordered_outcomes]
        )
        benchmark_total = _compound(
            [outcome.benchmark_return for outcome in ordered_outcomes]
        )
        baseline_active = net_total - benchmark_total

        performance_fold_by_number = {
            fold.fold_number: fold for fold in performance.fold_performance
        }
        fold_mismatch = len(performance_fold_by_number) != len(fold_outcomes) or any(
            performance_fold_by_number.get(fold_number) is None
            or performance_fold_by_number[fold_number].active_total_return
            != fold_active_returns[index]
            for index, (fold_number, _) in enumerate(fold_outcomes)
        )
        aggregate = performance.aggregate_performance
        aggregate_mismatch = (
            aggregate is None
            or aggregate.net_total_return != net_total
            or aggregate.benchmark_total_return != benchmark_total
            or aggregate.active_total_return != baseline_active
        )
        if fold_mismatch or aggregate_mismatch:
            _append_unique(
                blockers,
                StatisticalStabilityBlocker.BASELINE_PERFORMANCE_MISMATCH,
            )
            metrics_allowed = False

    bootstrap: BootstrapIntervalV1 | None = None
    sign_flip: SignFlipTestV1 | None = None
    cost_scenarios: tuple[CostSensitivityScenarioV1, ...] = ()
    leave_one_fold_out: tuple[LeaveOneFoldOutScenarioV1, ...] = ()
    summary: SensitivitySummaryV1 | None = None
    if metrics_allowed and baseline_active is not None:
        bootstrap = _bootstrap_interval(fold_active_returns, active_policy)
        sign_flip = _sign_flip_test(fold_active_returns, active_policy)
        cost_scenarios = _cost_scenarios(
            ordered_outcomes,
            baseline_active,
            active_policy,
        )
        if any(not scenario.metrics_computed for scenario in cost_scenarios):
            _append_unique(
                blockers,
                StatisticalStabilityBlocker.INVALID_COST_STRESS_SCENARIO,
            )
        leave_one_fold_out = _leave_one_fold_out(fold_outcomes, baseline_active)
        summary = _sensitivity_summary(cost_scenarios, leave_one_fold_out)

        if bootstrap.lower_bound <= 0 <= bootstrap.upper_bound:
            _append_unique(
                warnings,
                StatisticalStabilityWarning.CONFIDENCE_INTERVAL_INCLUDES_ZERO,
            )
        if not sign_flip.statistically_significant:
            _append_unique(
                warnings,
                StatisticalStabilityWarning.SIGN_FLIP_NOT_SIGNIFICANT,
            )
        if summary.cost_sign_reversal_count:
            _append_unique(
                warnings,
                StatisticalStabilityWarning.COST_STRESS_SIGN_REVERSAL,
            )
        if summary.leave_one_fold_out_sign_reversal_count:
            _append_unique(
                warnings,
                StatisticalStabilityWarning.LEAVE_ONE_FOLD_OUT_SIGN_REVERSAL,
            )
        if (
            summary.cost_active_return_range
            > active_policy.high_cost_sensitivity_range_threshold
        ):
            _append_unique(
                warnings,
                StatisticalStabilityWarning.COST_ASSUMPTION_SENSITIVE,
            )

    inference_computed = bootstrap is not None and sign_flip is not None
    sensitivity_computed = summary is not None
    interval_excludes_zero = bool(
        bootstrap is not None
        and (bootstrap.lower_bound > 0 or bootstrap.upper_bound < 0)
    )
    significance_confirmed = bool(
        interval_excludes_zero
        and sign_flip is not None
        and sign_flip.statistically_significant
    )
    stability_ready = not blockers and inference_computed and sensitivity_computed
    status = (
        StatisticalStabilityStatus.READY
        if stability_ready
        else StatisticalStabilityStatus.REJECTED
    )
    return StatisticalStabilityAssessmentV1(
        assessed_at=assessment_time,
        status=status,
        stability_ready=stability_ready,
        dataset_id=outcome_set.dataset_id,
        instrument_key=outcome_set.instrument_key,
        policy=active_policy,
        observation_count=len(expected_ids),
        fold_count=len(plan.folds),
        baseline_active_total_return=baseline_active,
        bootstrap_interval=bootstrap,
        sign_flip_test=sign_flip,
        cost_scenarios=cost_scenarios,
        leave_one_fold_out=leave_one_fold_out,
        sensitivity_summary=summary,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        statistical_inference_computed=inference_computed,
        statistical_significance_confirmed=significance_confirmed,
        assumption_sensitivity_computed=sensitivity_computed,
    )
