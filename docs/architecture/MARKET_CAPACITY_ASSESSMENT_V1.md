# Market Capacity Assessment V1

## Purpose

This layer estimates whether a proposed order size can fit within conservative point-in-time liquidity limits. It complements affordability: sufficient cash does not prove that a market can absorb an order without excessive participation or impact.

The assessment is offline and read-only. It does not place, modify or cancel an order and does not predict an execution price.

## Inputs

The layer consumes:

- a reconciled order-size request;
- explicit notional liquidity evidence;
- an existing market-readiness assessment;
- a conservative capacity policy.

The order request fixes:

- instrument key;
- side;
- currency;
- lots and lot size;
- reference price;
- intended execution days;
- units and total notional.

The evidence fixes:

- evidence and source timestamps;
- trusted source authority;
- venue;
- reference price;
- spread in basis points;
- top-of-book depth in currency notional;
- average and median daily turnover in currency notional;
- turnover history length;
- daily return volatility.

Depth and turnover must explicitly be notional. Ambiguous quantity-based fields from a market adapter are not silently interpreted.

## Structural boundary

Instrument, currency, lot size and reference price must match exactly between the request and evidence. A mismatch raises a structural error before any capacity metric is produced.

Capacity is blocked when:

- existing market-readiness is false;
- evidence is stale or materially future-dated;
- source authority is not trusted;
- turnover history is too short;
- daily ADV participation exceeds policy;
- top-of-book participation exceeds policy;
- intended execution window is shorter than the minimum required window;
- estimated impact exceeds policy;
- safe notional is zero.

## Calculations

For `D` intended execution days:

`daily slice notional = total order notional / D`

`daily turnover participation = daily slice notional / average daily turnover`

`top-of-book participation = daily slice notional / top-of-book depth notional`

`minimum execution days = ceil(total order notional / (ADV × maximum daily participation))`

The impact proxy is:

`half spread bps = spread bps / 2`

`impact excluding spread bps = daily volatility × sqrt(daily turnover participation) × impact coefficient × 10,000`

`estimated impact bps = half spread bps + impact excluding spread bps`

This is a square-root impact proxy, not an execution-price forecast.

## Safe capacity envelope

The requested-window capacity is the minimum of three limits:

1. `ADV × maximum daily participation × D`;
2. `top-of-book depth × maximum top-of-book participation × D`;
3. the notional implied by the maximum permitted impact budget.

The result also floors the safe notional to whole lots. It never creates fractional lots.

If daily volatility is zero, the impact limit is not treated as infinite. It is capped at the ADV limit because zero measured volatility can reflect insufficient or unrepresentative data.

## Warnings

The assessment always states that:

- the model is a square-root proxy;
- impact is not an execution price;
- only top-of-book depth is represented;
- evidence covers one venue;
- capacity is point-in-time.

Additional warnings cover:

- order splitting;
- high spread;
- a large difference between average and median turnover.

## Deliberate limitations

V1 does not provide:

- full order-book simulation;
- hidden-liquidity estimation;
- intraday volume curves;
- auction or closing-cross modelling;
- queue-position modelling;
- venue routing;
- nonlinear impact calibration from proprietary executions;
- partial-fill probability;
- guaranteed execution price;
- broker order preview;
- execution or recommendation integration.

## Safety invariants

Every assessment retains:

- `impact_is_estimate=true`;
- `execution_price_predicted=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Compatibility

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

Revert the PR merge commit. Existing market-readiness, portfolio, OOS validation and all earlier read-only layers remain independently usable.
