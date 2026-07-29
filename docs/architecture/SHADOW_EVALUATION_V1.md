# Shadow Evaluation v1

## Scope

PR-16 adds an offline evaluator that measures a filled or partially filled
`PaperPurchaseResultV1` against one strictly later market observation.

It does not place an order, call a broker, fetch a quote, change OpenAPI or
modify the real portfolio.

## Purpose

Paper trading answers: "How would this hypothetical fill change simulated cash
and position state?"

Shadow evaluation answers: "After a later observed market value, how did that
hypothetical position compare with its entry security value and total entry
cost?"

This is the first shadow ledger slice. It is not yet a multi-period backtest,
strategy-performance claim or forecast.

## Inputs

`evaluate_paper_purchase` accepts:

- a filled or partially filled `PaperPurchaseResultV1`;
- a `ShadowMarketObservationV1` for the same stable instrument key and currency;
- an observation timestamp strictly later than the paper-result timestamp;
- a full observed market value supplied by a trusted caller.

For bonds, the observed full market value must include accrued interest. The
evaluator does not invent it from a clean quotation.

## Look-ahead protection

An observation with a timestamp equal to or earlier than the paper timestamp is
rejected. This prevents same-time or historical data from being presented as a
forward result.

The contract records:

- `no_lookahead=true`;
- evaluated-from timestamp;
- observation timestamp;
- exact holding seconds;
- observation source and source ID.

## Currency and identity

The evaluator requires the paper result and observation to use:

- the same stable instrument key;
- the same currency.

No FX conversion or cross-currency aggregation is performed.

## Metrics

Entry security value:

`entry gross amount + entry accrued interest`

Gross value change:

`observed full market value − entry security value`

Net value change after entry costs:

`observed full market value − entry total cost`

Return on total cost:

`net value change after entry costs ÷ entry total cost`

The outcome is `profit`, `loss` or `flat` based on the net value change.

This first version includes entry commission but not an assumed exit commission,
slippage or tax. Those values are not invented.

## Non-evaluable scenarios

A rejected paper result cannot form a shadow performance evaluation because no
hypothetical position was created.

Identity mismatch, currency mismatch and non-forward timestamps fail closed.

## Execution boundary

Every result has:

- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`;
- `no_cross_currency_aggregation=true`.

The evaluator imports no network or broker client and contains no real execution
identifier.

## Known limitations

PR-16 does not yet implement:

- repeated observations and time series;
- max drawdown or recovery duration;
- exit-cost and tax assumptions;
- benchmark/index comparison;
- user-action comparison;
- portfolio-level aggregation;
- walk-forward or out-of-sample testing;
- survivorship-bias controls;
- persistent shadow storage.

Those require explicit datasets, source timestamps and methodology rather than
invented values.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
