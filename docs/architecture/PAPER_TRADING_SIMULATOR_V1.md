# Paper Trading Simulator v1

## Scope

PR-15 adds an offline, deterministic paper-purchase simulator over a strict
`PreTradePreviewV1`.

It does not add a FastAPI route, change OpenAPI, call a broker, create a real
order, reserve money or modify the real portfolio.

The first version models purchase outcomes because PR-14 currently provides a
strict purchase preview. A sale simulator must wait for a symmetric sell-preview
contract rather than inventing unavailable tax, position and broker inputs.

## Inputs

`simulate_paper_purchase` accepts:

- a `PreTradePreviewV1`;
- a caller-supplied paper scenario ID;
- requested simulated fill lots;
- paper cash before the scenario;
- paper position lots before the scenario;
- an aware simulation timestamp.

The function is pure with respect to the input preview and performs no network
or SDK operation.

## Outcomes

The result is one of:

- `filled` — all preview lots are simulated as filled;
- `partially_filled` — a positive subset is filled;
- `rejected` — no paper cash or position is changed.

Rejection reasons are explicit:

- source preview is not ready;
- simulated fill lots are invalid;
- simulated fill exceeds requested lots;
- paper cash is insufficient.

## Partial fills

For a partial fill, the preview's initial amount, canonical commission and bond
accrued interest are allocated in proportion to filled lots. Allocated amounts
are rounded with decimal half-even rounding to nine decimal places.

For a full fill, exact preview amounts are preserved.

The simulator does not pretend to model queue priority, real spread movement,
latency, hidden liquidity or exchange matching. Those belong to later shadow
and market-impact work.

## Financial invariants

The result enforces:

`filled lots + unfilled lots = requested lots`

`filled units = filled lots × lot size`

`gross amount + commission + accrued interest = total cost`

`paper cash after = paper cash before − total cost`

`paper position lots after = paper position lots before + filled lots`

Paper cash cannot become negative.

A rejected scenario must have zero fill and zero cost and must leave simulated
cash and position unchanged.

All monetary calculations use `Decimal` and remain within one currency.

## Journal

A filled or partially filled scenario has two contiguous events:

1. accepted by the offline simulator;
2. paper fill recorded.

A rejected scenario has one rejection event. Journal timestamps are aware and
normalized to UTC.

## Safety boundary

Every result has:

- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The contract contains no real order ID, confirmation ID, idempotency key or
broker execution method. The simulator module imports no broker or network
client.

## Known limitations

PR-15 does not yet model:

- sell orders;
- order-book queue position;
- time-varying slippage;
- exchange trading calendars;
- order cancellation or expiry;
- a persistent multi-order paper account;
- strategy backtests or walk-forward evaluation.

Those capabilities remain separate work so the first paper layer stays small,
auditable and unable to affect the real broker account.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
