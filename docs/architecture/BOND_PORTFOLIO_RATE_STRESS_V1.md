# Bond Portfolio Rate Stress v1

## Scope

PR-24 aggregates multiple ready `BondRateStressAssessmentV1` objects into one
currency-local bond-portfolio interest-rate stress view.

It does not generate instrument scenarios itself. Every component bond must first
pass the PR-23 instrument-level stress layer.

## Fail-closed input gates

Aggregation requires:

- between 1 and 256 instrument assessments;
- every assessment is `ready` and has no blockers;
- unique stable instrument keys;
- one explicit currency for all assessments and values;
- positive current values;
- the same non-empty sorted shock grid for every bond.

Any violation rejects the complete aggregation. The engine does not return a
partial portfolio total and does not perform FX conversion.

## Aggregation

For each identical shock, the portfolio scenario sums:

- current full value;
- estimated value;
- estimated change;
- estimated loss.

Every instrument contribution is retained and sorted by stable key. The contract
requires the same instruments, current values and durations in every shock.

Portfolio weighted duration is:

`sum(current instrument value × instrument duration) / total current value`

Worst loss is the largest summed estimated loss across the shared shock grid.
The corresponding shock and loss ratio are reported.

## Evidence reconciliation

The contract independently verifies:

- instrument count and sorted unique keys;
- contribution count and shock identity;
- per-instrument change and loss;
- scenario sums;
- stable current values and durations across scenarios;
- weighted duration;
- shock grid;
- worst loss, ratio and shock.

A modified contribution or summary cannot validate silently.

## Modeling limitations

The aggregate inherits all PR-23 assumptions:

- linear duration approximation;
- no convexity;
- credit spreads held constant;
- no coupon reinvestment;
- no taxes, spread, slippage or default modeling;
- parallel yield shocks only.

Cross-instrument correlation is not modeled. The result is a mechanical scenario
view, not a forecast or recommendation.

## Safety

Every output preserves:

- `complete_scenario_coverage=true`;
- `no_cross_currency_aggregation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

The implementation imports no network client, broker SDK or execution method and
adds no FastAPI route, OpenAPI operation, Render setting or secret.

## Rollback

Revert the PR merge commit. No runtime, database, OpenAPI, Render, broker or GPT
Editor migration is required.
