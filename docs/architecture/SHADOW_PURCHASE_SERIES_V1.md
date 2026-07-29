# Shadow Purchase Series v1

## Scope

PR-20 extends the single-observation shadow purchase evaluation into a bounded,
deterministic time-series ledger. It evaluates one filled or partially filled
paper purchase against between 1 and 256 strictly later market observations.

The ledger is offline. It does not fetch prices, call the broker, persist account
state or expose a FastAPI route.

## Inputs

- one validated `PaperPurchaseResultV1`;
- an ordered sequence of `ShadowMarketObservationV1` objects.

A rejected paper scenario is not evaluable because it created no hypothetical
position.

## Time safety

Every observation must:

- be strictly later than the paper-result timestamp;
- be strictly later than the previous observation;
- use an aware timestamp normalized to UTC.

Equal, earlier or unsorted timestamps fail closed. This prevents use of future
information at an earlier decision point and preserves `no_lookahead=true`.

## Identity and currency boundary

Every observation must use the paper result's exact stable instrument key and
currency. No ticker guessing, FX conversion or cross-currency aggregation is
performed.

## Per-point calculations

For every observation the existing single-point evaluator computes:

`entry security value = entry gross amount + accrued interest`

`gross value change = observed full market value - entry security value`

`net value change after entry costs = observed full market value - entry total cost`

`return on total cost = net value change after entry costs / entry total cost`

The series layer additionally computes:

`running peak = max(all observed values through the current point)`

`drawdown amount = running peak - current observed value`

`drawdown ratio = drawdown amount / running peak`

When the running peak is zero, drawdown ratio is defined as zero.

## Series summary

`ShadowPurchaseSeriesV1` records:

- first and last observation timestamps;
- total holding seconds;
- observation count;
- actual paper filled lots and units;
- entry security value, commission and total cost;
- every immutable series point;
- peak market value;
- maximum drawdown amount;
- maximum drawdown ratio;
- final market value;
- final cost-aware change, return and outcome.

All summary values must reconcile exactly with the contained points. The
contract rejects tampered observation counts, sequences, timestamps, peaks,
drawdowns or final values.

## Observation limit

A series contains at most 256 observations. This bounds payload size and
provenance growth while supporting daily observations for a substantial review
window. Larger histories require a separately reviewed aggregation or storage
architecture.

## Interpretation boundary

The ledger is not a strategy backtest and does not establish expected future
performance. It does not infer:

- exit commission;
- bid-ask spread or slippage;
- taxes;
- exchange queue priority;
- survivorship-bias controls;
- benchmark performance;
- portfolio-level cash reuse;
- repeated independent trade decisions.

For bonds, every observation must provide full market value including accrued
interest.

## Safety

Every output preserves:

- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`;
- `no_cross_currency_aggregation=true`.

The implementation imports no broker SDK, HTTP client or gRPC client. It adds no
route, Action, secret, Render setting or execution identifier.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, broker or GPT
Editor migration is required.
