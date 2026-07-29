# Walk-Forward Performance Evaluation V1

## Purpose

`WalkForwardOutcomeSetV1` and `evaluate_walk_forward_performance` evaluate immutable out-of-sample outcomes produced for the purged and embargoed folds from `WalkForwardValidationPlanV1`.

The module is an evaluation layer, not a strategy optimizer and not an execution engine.

## Required inputs

V1 consumes:

1. a ready walk-forward validation plan;
2. the exact point-in-time dataset used to build that plan;
3. one complete outcome for every test observation and no training-only observations.

Plan, dataset and outcome-set IDs and instrument identities must agree.

## Outcome contract

Every OOS outcome includes:

- observation ID;
- instrument key;
- label/outcome availability time;
- trusted source and retrieval time;
- strategy gross return;
- benchmark return;
- turnover;
- commission, spread and slippage in basis points;
- transaction-cost rate;
- strategy net return.

The contract reconciles:

`cost rate = turnover × (commission bps + spread bps + slippage bps) / 10,000`

`net return = gross return - cost rate`

The outcome source cannot be retrieved before the outcome becomes available.

## Exact OOS coverage

The evaluator constructs the expected observation IDs only from fold test sets. It rejects:

- missing test outcomes;
- extra training or non-plan outcomes;
- dataset/plan mismatch;
- instrument mismatch;
- outcome availability before the original label availability.

Structural coverage failures disable performance metrics rather than silently evaluating a subset.

## Fold metrics

For every fold V1 calculates:

- compounded gross return;
- compounded net return;
- compounded benchmark return;
- active return;
- realized cost drag;
- total and average turnover;
- positive-return rate;
- benchmark-outperformance rate;
- maximum drawdown;
- maximum drawdown duration in observations.

## Aggregate metrics

Across all folds in original test order V1 calculates:

- compounded gross, net and benchmark returns;
- active return and cost drag;
- total and average turnover;
- mean net return;
- population volatility of OOS net returns;
- positive and benchmark-outperformance rates;
- maximum drawdown and drawdown duration;
- minimum and maximum fold returns;
- fold return range;
- profitable-fold and benchmark-beating-fold rates.

No annualization is inferred because observation spacing and horizon may vary.

## Cost-model boundary

Commission, spread and slippage are explicit components. By default, an all-zero cost model blocks readiness even though arithmetic metrics remain visible for diagnostics.

This avoids presenting a frictionless simulation as a decision-ready backtest.

## Warning boundary

Configurable warnings cover:

- negative total net return;
- benchmark underperformance;
- high average turnover;
- high cost drag;
- unstable fold results.

Every result also states that statistical significance and capacity were not assessed and that historical performance is not a forecast.

## Scope limitations

V1 does not:

- optimize hyperparameters;
- use test data for training;
- calculate p-values or confidence intervals;
- model market impact or portfolio capacity;
- evaluate a multi-instrument portfolio;
- fetch prices or broker data;
- create recommendations or orders.

Every evaluation retains:

- `out_of_sample_only=true`;
- `benchmark_included=true`;
- `hyperparameters_optimized=false`;
- `statistical_significance_tested=false`;
- `capacity_analyzed=false`;
- `historical_performance_not_forecast=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Compatibility and security

The module adds no broker call, real order method, transfer/withdrawal surface, FastAPI route, OpenAPI operation or GPT Action. Gateway version remains `3.9.1`; Render entrypoint remains `app:app`.

## Tests

Focused tests cover positive compounded OOS performance, benchmark and costs, negative/drawdown scenarios, zero-cost rejection, missing/extra outcomes, label timing, source trust and future retrieval, ID mismatches, warning thresholds, exact cost/net reconciliation, aggregate tampering and immutable safety flags.

## Next validation stage

A later stage may add statistical confidence, parameter sensitivity, multi-asset capacity and realistic market-impact models. Those additions must consume immutable OOS results and must not alter prior test folds.

## Rollback

Revert the PR merge commit. Existing walk-forward split planning, news, market, technical, equity, fund, bond, paper, public API and broker layers remain independent.
