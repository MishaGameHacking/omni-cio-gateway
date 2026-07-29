# Threshold Rebalancing v1

## Scope

PR-13 adds a read-only, currency-local threshold rebalancing layer over
`AdvancedPortfolioAnalyticsV1` and a recommendation-ready `DecisionSetV1`.

It does not request market prices, calculate lots, estimate actual commission,
create a broker preview, ask for confirmation or submit an order.

## Target bands

Each current position receives a target range:

- lower weight;
- target weight;
- upper weight.

The engine classifies a position as:

- `below` — current weight is below the lower boundary;
- `inside` — current weight remains within the permitted range;
- `above` — current weight exceeds the upper boundary.

A difference from the exact target does not trigger an action while the position
remains inside its permitted range.

## Currency boundary

One plan is built for exactly one currency. Cash, current values, deviations and
potential changes are never summed across currencies. A multi-currency portfolio
must be evaluated through separate plans for each currency.

Target bands using another currency fail closed.

## Alternatives

Every plan contains exactly three alternatives.

### No action

The portfolio remains unchanged. This is preferred when:

- no band is breached;
- cash cannot repair an underweight position;
- a source or coverage gate is open.

### Cash first

Deployable cash is directed toward positions below their lower boundary without
selling current holdings. This becomes preferred when:

- the source Decision Set is ready;
- target-band coverage is complete;
- at least one position is outside its lower boundary;
- deployable cash is greater than zero.

The engine reports only aggregate analytical value. Instrument selection, lots,
live price and commission remain PR-14 responsibilities.

### Full threshold

This scenario considers reductions of positions above their bands and additions
to positions below their bands. It is always blocked in PR-13 because:

- live preview is required;
- sales may require tax-basis data.

It is never execution-ready.

## Data gates

The plan is decision-ready only when:

- `DecisionSetV1.recommendation_ready=true`;
- `DecisionSetV1.abstain=false`;
- decision and analytics refer to the same masked account;
- every current position in the selected currency has exactly one target band;
- deployable cash is finite, non-negative and does not exceed current cash;
- every target band uses the selected currency.

Unknown bands, duplicate bands and absent positions fail closed.

## Arithmetic

For a position below its band:

`value_to_nearest_band = lower_weight × currency_total − current_value`

For a position above its band:

`value_to_nearest_band = current_value − upper_weight × currency_total`

The value to the target is:

`abs(target_weight × currency_total − current_value)`

Alternative funding reconciles as:

`residual_cash = available_cash + planned_reduce_value − planned_add_value`

All calculations use `Decimal`.

## Safety boundary

Every line, alternative and plan has:

- `execution_ready=false`;
- `trading_methods=false`.

The contracts do not contain:

- lots;
- units or order quantity;
- live or limit price;
- order ID;
- idempotency key;
- confirmation ID;
- broker execution method.

PR-13 does not change FastAPI routes, OpenAPI, GPT Actions, broker SDK access,
Gateway version `3.9.1` or Render entrypoint `app:app`.

## External design rationale

Investor-education guidance describes rebalancing through sales and purchases,
additional investments, or redirecting ongoing contributions toward underweight
assets. It also advises considering transaction fees and tax consequences before
rebalancing. PR-13 therefore keeps a no-action alternative, prefers cash-first
repair when possible and blocks sale-based repair until cost and tax inputs are
available.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
