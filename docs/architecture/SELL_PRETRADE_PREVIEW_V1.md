# Sell Pre-Trade Preview V1

## Purpose

`build_sell_pretrade_preview` creates a strict analytical preview for reducing an existing position. It is the sell-side counterpart to the existing purchase preview, but it is intentionally a separate contract because proceeds, position availability, taxes and post-sale portfolio risk are different from purchase affordability.

The builder is data-only. It imports no broker SDK, HTTP client or execution adapter and does not expose a FastAPI route.

## Official API basis

T-Invest documents that:

- `GetMaxLots` returns `sell_limits.sell_max_lots` for sales from the investor's own position;
- when the price is omitted, `GetMaxLots` uses the best bid for a sale;
- `GetOrderPrice` accepts `ORDER_DIRECTION_SELL` and returns preliminary order amount, commission and bond accrued interest;
- `GetOrders` provides active orders that must be considered before a sale;
- actual order placement is a separate `PostOrder` method.

PR-26 models only normalized evidence from the read-only calculation methods. It does not call or expose `PostOrder`.

## Inputs

The builder accepts:

- a normalized read-only sale-capacity payload;
- a currency-local `ThresholdRebalancePlanV1`;
- the stable key of one position marked `REDUCE`;
- an evaluation timestamp and a price-freshness limit.

The normalized payload must retain provenance from:

- best bid or last price;
- `GetMaxLots` own-position sale limits;
- `GetOrderPrice` with sell direction;
- active-order inspection;
- separate tax-basis evidence.

## Required gates

A ready preview requires all of the following:

1. the rebalancing plan is decision-ready;
2. the selected line is above its upper band and requires reduction;
3. the full-threshold alternative represents a sale and has no blocker other than the expected live-preview and tax-basis requirements;
4. the masked account matches exactly;
5. the source explicitly reports read-only behavior and `trading_methods=false`;
6. direction is sell;
7. the instrument is resolved;
8. price basis is best bid or last price, never manual;
9. the price timestamp is known, not future and within the freshness threshold;
10. lot size and requested lots are positive;
11. own-position lots and `sell_max_lots` are available;
12. requested lots do not exceed the position, own-position sale limit or position remaining after active sell orders;
13. active orders were checked;
14. current position value matches the verified rebalance line;
15. commission is available with double-count protection;
16. tax basis is confirmed and an estimated tax amount is supplied, including an explicit zero when appropriate;
17. every money field uses one currency;
18. source and recomputed arithmetic agree;
19. the reduction does not exceed the value required to reach the target;
20. estimated post-sale weight does not fall below the lower target band.

Any open gate produces `preview_ready=false`.

## Financial calculations

### Position-side valuation

The sold fraction is valued from the verified current portfolio position:

`position fraction sold = requested lots / current position lots`

`sold position value = current position value × position fraction sold`

`estimated remaining position value = current position value − sold position value`

This value is used for portfolio-weight reconciliation. It is not assumed to equal the expected exchange proceeds.

### Sale proceeds

`gross proceeds = preliminary security proceeds + accrued-interest proceeds`

`net proceeds = gross proceeds − canonical commission − estimated tax`

The broker's generic `total_order_amount` is not used as a substitute for this explicit calculation because the sign and sale-side presentation can be ambiguous across adapters. The normalized payload may supply explicit gross and net proceeds, but they must reconcile with the formula.

### Post-sale portfolio estimate

`portfolio value before = current position value / current position weight`

`portfolio value after = portfolio value before − sold position value + net proceeds`

`post-sale position weight = remaining position value / portfolio value after`

This captures spread, price-basis difference, commission and the supplied tax estimate without mixing currencies.

## Tax boundary

`GetOrderPrice` does not provide the investor's complete tax basis. PR-26 therefore requires separate confirmed tax evidence. A missing tax basis is a hard blocker, not a zero-tax assumption.

The estimated tax remains provisional and must be refreshed in any future confirmation workflow.

## Active-order boundary

`GetMaxLots` is not treated as proof that no conflicting order exists. The preview separately requires active-order inspection and conservatively verifies:

`requested lots <= current position lots − conflicting open sell lots`

Short sales are always forbidden.

## Contract integrity

`SellPreTradePreviewV1` independently rechecks:

- price age;
- quantity units;
- remaining position lots;
- active-order availability;
- sold and remaining position values;
- gross and net proceeds;
- before/after portfolio totals;
- post-sale weight;
- target-reduction overshoot;
- lower-band undershoot;
- single-currency arithmetic;
- readiness and blocker consistency.

## Safety boundary

Every result retains:

- `no_short_sale=true`;
- `no_cross_currency_aggregation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

PR-26 adds no order ID, confirmation token, idempotency key, order-submission method, cancellation method or broker write permission.

## Limitations

- The current PR consumes normalized payload data but does not add a public live sell-preview Action.
- Exact realized tax remains dependent on broker/account tax records.
- Slippage beyond the supplied price, partial execution and queue priority are not predicted.
- A later paper-sell simulator may consume this contract, but no portfolio state is changed here.

## Rollback

Revert the PR-26 merge commit. The purchase preview, public OpenAPI, production runtime and broker permissions remain unchanged.
