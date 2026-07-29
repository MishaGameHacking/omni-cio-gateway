# Paper Sale Simulator V1

## Purpose

`simulate_paper_sale` applies a ready `SellPreTradePreviewV1` to an explicit simulated cash balance and position-lot state. It records filled, partially filled or rejected outcomes without broker or network interaction.

The simulator is the sell-side counterpart to the existing paper purchase simulator. The contracts remain separate because a sale increases cash, decreases a position and allocates an estimated tax.

## Inputs

The simulator requires:

- one sell preview;
- a stable scenario ID;
- requested paper fill lots;
- simulated cash before the sale;
- simulated position lots before the sale;
- an aware simulation timestamp.

The supplied paper position must equal the position-lot state used by the sell preview. A mismatch indicates stale simulated state and rejects the scenario.

## Outcomes

### Filled

All preview lots are simulated as filled.

### Partially filled

A positive subset of preview lots is simulated as filled. Security proceeds, accrued interest, commission and estimated tax are allocated proportionally using exact Decimal arithmetic and half-even rounding to nine decimal places.

### Rejected

A scenario is rejected when:

- the preview is not ready;
- fill lots are zero, negative or boolean;
- fill lots exceed the preview request;
- simulated position lots are insufficient;
- simulated position state differs from the preview state.

A rejected scenario records zero allocated proceeds and leaves cash and position unchanged.

## Arithmetic

For a partial fill:

`allocation ratio = filled lots / requested lots`

`allocated security proceeds = preview security proceeds × allocation ratio`

`allocated accrued interest = preview accrued interest × allocation ratio`

`allocated commission = preview commission × allocation ratio`

`allocated estimated tax = preview estimated tax × allocation ratio`

`gross proceeds = security proceeds + accrued interest`

`net proceeds = gross proceeds − commission − estimated tax`

`paper cash after = paper cash before + net proceeds`

`paper position lots after = paper position lots before − filled lots`

The result contract independently recomputes every formula.

## Journal

A successful simulated fill contains two contiguous events:

1. accepted;
2. fill.

A rejected scenario contains exactly one rejection event.

## State boundary

PR-27 does not persist a paper account. Callers must provide the current paper cash and position state explicitly. This makes the transition deterministic and reviewable but leaves multi-event state storage for a later ledger PR.

## Safety

Every output retains:

- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The simulator imports no broker SDK, gRPC client, HTTP client or execution adapter. It does not contain an order identifier, confirmation token or idempotency key for real trading.

## Limitations

- Fill quantity is caller-selected and does not model queue priority.
- No additional slippage beyond the source preview is invented.
- Estimated tax is inherited proportionally from the preview and remains provisional.
- The simulator does not yet combine purchase and sale events into a persistent account ledger.
- Corporate actions, tax-lot selection and realized-P&L accounting remain later work.

## Rollback

Revert the PR-27 merge commit. Existing purchase paper simulation, preview contracts, public API and production runtime remain unchanged.
