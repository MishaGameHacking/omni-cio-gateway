# Walk-Forward Validation Plan V1

## Purpose

`WalkForwardDatasetV1` and `build_walk_forward_validation_plan` provide a strict time-series split plan before any strategy performance calculation or parameter optimization is allowed.

The module addresses structural validation risks:

- look-ahead bias;
- label leakage;
- overlapping train/test windows;
- survivorship-only universes;
- revised-data substitution;
- unadjusted corporate actions;
- repeated use of the same out-of-sample observation.

## Observation timeline

Every observation declares:

- feature window start and end;
- time at which feature data was actually available;
- point-in-time universe snapshot;
- decision timestamp;
- label window start and end;
- time at which the completed label became available.

The contract requires:

- feature window and feature availability no later than the decision;
- universe snapshot no later than the decision;
- label window not to begin before the decision;
- label completion before label availability.

This makes data availability explicit instead of inferring it from row order.

## Dataset integrity

V1 is intentionally strict. A dataset must declare:

- point-in-time universe history;
- retention of delisted instruments;
- corporate-action-adjusted data;
- original-vintage data;
- complete, non-truncated observations;
- no forecast data embedded as features.

Observation IDs and decision timestamps must be unique and chronological. All observations belong to one instrument in V1. Source retrieval cannot predate the latest label availability.

## Walk-forward modes

### Expanding

Each valid fold uses all eligible historical observations before its test window.

### Rolling

Each valid fold uses only the most recent configured number of eligible historical observations.

Both modes use non-overlapping test windows. `step_observations` cannot be smaller than `test_observations`.

## Purge and embargo

For each test window, a training observation is eligible only when:

`label_data_available_at + embargo <= first_test_decision_at`

Rows failing this condition are purged. The check uses label availability, not only label-period end, because delayed publication or reconciliation can make a completed label unavailable in practice.

## Out-of-sample integrity

The plan contract verifies:

- train, test and purged IDs are disjoint within every fold;
- fold numbers are contiguous;
- test observations do not repeat across folds;
- train decision timestamps precede the test period;
- training label availability respects embargo;
- out-of-sample count and coverage reconcile exactly.

## Readiness blockers

The plan is rejected when:

- the source authority is not trusted by policy;
- source retrieval is materially future-dated;
- observations cannot satisfy the minimum train/test requirement;
- fewer than the required number of valid folds survive purge and embargo.

A rejected plan may still expose valid folds for diagnostics, but it cannot claim validation readiness.

## Scope boundary

PR-41 produces split evidence only. It does not calculate:

- strategy return;
- benchmark-relative performance;
- drawdown;
- volatility;
- turnover;
- commissions, spread or slippage;
- parameter stability;
- statistical significance;
- portfolio capacity.

Every result therefore retains:

- `split_plan_only=true`;
- `performance_metrics_computed=false`;
- `hyperparameters_optimized=false`;
- `transaction_costs_evaluated=false`;
- `look_ahead_data_allowed=false`;
- `test_data_used_for_training=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Compatibility and security

The module adds no market-data fetcher, broker call, order method, transfer/withdrawal method, FastAPI route, OpenAPI operation or GPT Action. Gateway version remains `3.9.1`; Render entrypoint remains `app:app`.

## Tests

Focused tests cover expanding and rolling folds, unique out-of-sample windows, purge and embargo, insufficient history, untrusted/future sources, feature and label look-ahead, universe timing, duplicate/out-of-order observations, premature dataset retrieval, policy conflicts, fold/plan tampering and immutable safety flags.

## Next validation stage

A later PR can consume this split plan to evaluate deterministic strategy outputs with explicit benchmark, commissions, spread, slippage, turnover, drawdown and parameter-sensitivity metrics. Test folds must remain immutable and out-of-sample.

## Rollback

Revert the PR merge commit. Existing market, news, technical, equity, fund, bond, paper, public API and broker layers remain independent.
