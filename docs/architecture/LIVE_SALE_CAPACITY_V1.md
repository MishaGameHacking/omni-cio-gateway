# Live Read-Only Sale Capacity V1

## Purpose

`sale_capacity.py` collects the live read-only evidence required by the strict sell pre-trade contract without exposing a public Action or calling any broker write method.

It is an internal data-collection layer. The result is normalized for `build_sell_pretrade_preview`, but remains fail-closed because verified tax-basis evidence is deliberately outside this collector.

## Official T-Invest basis

The collector uses only documented read-only methods:

- `GetPositions` for the investor's current securities balance and blocked units;
- `GetMaxLots` for own-position `sell_limits.sell_max_lots`;
- `GetOrders` for active orders that reserve part of the position;
- `GetOrderPrice` with `ORDER_DIRECTION_SELL` for preliminary security proceeds, commission and bond accrued interest;
- existing instrument and market-data readers for identity, lot size, best bid and last price.

Actual placement is a separate `PostOrder` method. PR-29 neither exposes nor calls it.

## Isolated SDK allowlist

The existing purchase proxy remains unchanged in capability:

- services: users, instruments, orders;
- order methods: `get_max_lots`, `get_order_price`.

PR-29 adds a separate sale proxy with only:

- services: users, instruments, orders, operations;
- order methods: `get_max_lots`, `get_order_price`, `get_orders`;
- operations methods: `get_positions`.

Order creation, replacement, cancellation, stop orders, sandbox, withdrawals and unrelated operation-history methods remain unavailable through the proxy.

## Price selection

Allowed bases:

- `best_bid` from the exchange order book;
- `last_price` from exchange last prices.

Manual sale prices are rejected. Source time, age and the existing 120-second freshness threshold are preserved.

## Position normalization

The collector selects exactly one `GetPositions.securities` row matching the requested instrument UID.

`position lots = balance units / instrument lot size`

`blocked lots = blocked units / instrument lot size`

Both conversions must be exact non-negative integers. Missing rows, duplicate rows, malformed rows or fractional lot conversion degrade position availability instead of rounding.

The collector does not invent current position market value. That value remains sourced from verified portfolio analytics in the downstream sell-preview plan.

## Active-order reservation

For matching active sell orders:

`conflicting lots = sum(max(0, lots requested − lots executed))`

Buy orders and orders for other instruments are ignored. Malformed matching rows make the active-order check incomplete rather than silently treating them as zero.

## Proceeds and commission

The preliminary sell response is normalized as:

`gross proceeds = initial order amount + bond accrued-interest proceeds`

Commission uses the existing canonicalization and double-count protection:

1. aggregate executed commission;
2. RUB aggregate only when the preview currency is RUB;
3. service plus deal components only as a fallback.

The generic broker `total_order_amount` is preserved but is not treated as verified net sale proceeds.

## Tax boundary

The collector always returns:

- `tax_basis.status=unavailable`;
- `tax_basis.confirmed=false`;
- `net_proceeds_confirmed=false`;
- `calculation_integrity_confirmed=false`.

This is intentional. `GetPositions`, `GetMaxLots`, `GetOrders` and `GetOrderPrice` do not provide a complete verified tax basis for the sale. The downstream strict sell preview therefore remains blocked until separate tax evidence is supplied.

A technically complete collection is not represented as a trade-ready preview.

## Output quality

`quality.complete=true` means all read-only broker and market components were collected consistently. It does not mean the sale is recommendation-ready or executable.

Separate fields preserve:

- instrument resolution;
- price availability;
- own-position availability;
- active-order check;
- order-price availability;
- canonical commission protection;
- currency consistency;
- tax-basis absence;
- calculation-integrity absence;
- component errors;
- `read_only=true`;
- `no_order_created=true`.

## Public API boundary

PR-29 adds no FastAPI route, operation ID or OpenAPI schema. A future migration may expose a public sale-preview Action only after response-contract and GPT Editor planning.

## Safety

Every payload contains `trading_methods=false`. The collector has no confirmation token, idempotency key, order ID or execution adapter.

Repository policy continues to reject any reference to broker write surfaces in runtime code.

## Limitations

- Tax basis remains unavailable.
- Position market value is not calculated by this layer.
- The active-order calculation assumes `GetOrders` returns the relevant active-order set.
- No queue priority, fill probability or additional slippage is predicted.
- No public endpoint is added in this version.

## Rollback

Revert the PR-29 merge commit. Purchase capacity, public Actions, Render deployment and broker permissions remain unchanged.
