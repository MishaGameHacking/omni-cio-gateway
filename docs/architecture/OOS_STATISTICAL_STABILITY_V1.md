# OOS Statistical Stability V1

## Purpose

This layer evaluates whether an already completed, immutable out-of-sample performance result is statistically and economically stable enough to interpret. It does not forecast returns, select strategy parameters or create a recommendation.

The layer consumes:

- a ready purged walk-forward validation plan;
- the complete immutable OOS outcome set;
- the ready PR-42 performance evaluation built from those outcomes.

It independently recomputes fold and aggregate active returns before any statistical calculation. A mismatch between the frozen PR-42 result and the supplied outcomes blocks the assessment.

## Trust boundary

The assessment requires:

- identical dataset IDs across plan, outcomes and performance;
- identical instrument keys;
- exact OOS outcome coverage;
- a ready performance evaluation;
- a minimum number of observations and folds;
- exact agreement between recomputed and previously evaluated fold/aggregate performance.

Training observations are never used as statistical outcomes.

## Fold-cluster bootstrap

V1 bootstraps complete walk-forward folds rather than individual observations. This preserves the basic within-fold dependency structure and avoids presenting independent-observation precision that the data do not support.

The statistic is the mean fold active total return.

The result includes:

- observed mean fold active return;
- lower, median and upper nearest-rank bootstrap quantiles;
- probability that the bootstrapped statistic is positive;
- confidence level;
- sample count;
- deterministic seed.

Resampling uses a documented deterministic linear congruential generator so results are reproducible across runs. It is a validation primitive, not a cryptographic generator.

## Paired sign-flip test

The paired fold active returns are tested against a symmetric zero-active-return null.

- folds at or below the configured exact threshold use all `2^n` sign permutations;
- larger fold sets use deterministic Monte Carlo sign flips;
- the test is two-sided;
- ties are included in the extreme-count rule;
- the Monte Carlo path uses a plus-one p-value correction.

Statistical significance is confirmed only when both conditions hold:

1. the bootstrap interval excludes zero;
2. the sign-flip p-value is at or below `1 - confidence_level`.

A completed assessment can therefore be ready while statistical significance remains unconfirmed.

## Cost sensitivity

The engine recomputes sequential compounded net performance across a policy grid:

- multipliers applied to the original commission, spread and slippage assumptions;
- additional slippage in basis points.

For each outcome:

`stressed cost rate = turnover × ((base cost bps × multiplier) + extra slippage bps) / 10,000`

`stressed net return = gross return - stressed cost rate`

The benchmark is unchanged.

Every scenario reports:

- stressed net total return;
- benchmark total return;
- active total return;
- active sign;
- whether the sign differs from the baseline.

If a scenario produces an observation return at or below `-100%`, that scenario is explicit and invalid. Invalid requested stress scenarios block readiness rather than being silently dropped.

## Leave-one-fold-out sensitivity

Each completed fold is omitted once. The retained OOS outcomes are compounded in original fold order.

The result reports:

- omitted fold number;
- retained observation count;
- net and benchmark total return;
- active total return;
- active sign;
- sign reversal against the full OOS baseline.

This detects results dominated by one fold or one market regime.

## Warnings

V1 can emit warnings for:

- limited fold count;
- a bootstrap interval that includes zero;
- a non-significant sign-flip test;
- cost-stress sign reversal;
- leave-one-fold-out sign reversal;
- a wide cost sensitivity range;
- deterministic resampling;
- absence of hyperparameter search;
- single-instrument evaluation;
- absence of capacity analysis;
- historical performance not being a forecast.

Warnings do not become recommendations.

## Safety invariants

Every result retains:

- `out_of_sample_only=true`;
- `fold_clustered_resampling=true`;
- `deterministic_resampling=true`;
- `test_data_used_for_selection=false`;
- `hyperparameters_optimized=false`;
- `capacity_analyzed=false`;
- `historical_performance_not_forecast=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Deliberate limitations

V1 does not provide:

- a guarantee of future performance;
- model-selection or hyperparameter optimization;
- multiple-testing correction across strategy searches;
- market-impact or capacity analysis;
- cross-sectional multi-asset inference;
- regime-conditioned significance;
- Bayesian posterior inference;
- execution or public API integration.

A small fold count materially limits statistical power even when the exact sign-flip test is available.

## Compatibility

This layer is offline and internal:

- no broker SDK changes;
- no market-data fetcher;
- no FastAPI route;
- no OpenAPI operation;
- no GPT Action change;
- no order creation, replacement or cancellation;
- no transfer or withdrawal method;
- gateway version remains `3.9.1`;
- Render entrypoint remains `app:app`.

## Rollback

Revert the PR merge commit. PR-42 performance evaluation and all earlier read-only modules remain independently usable.
