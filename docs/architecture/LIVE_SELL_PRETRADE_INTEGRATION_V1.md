# Live Sell Pre-Trade Integration V1

## Purpose

PR-30 connects the live read-only sale-capacity collector to the strict typed
`SellPreTradePreviewV1` contract without adding a public route or enabling order
execution.

The integration is deliberately small:

1. call one supplied sale-capacity loader exactly once;
2. verify the returned payload is a mapping;
3. require `trading_methods=false` explicitly;
4. bind the response to the requested instrument UID, price basis, quantity and
   SELL direction;
5. pass a defensive copy to the existing sell pre-trade orchestrator;
6. require the resulting contract to retain `execution_ready=false` and
   `trading_methods=false`.

## Input binding

The following values must match the caller request exactly:

- `request.instrument_uid`;
- `request.price_basis`;
- `request.quantity_lots`;
- `request.direction`.

A mismatch is treated as source tampering or stale-response reuse and raises a
fail-closed `LiveSellPreTradeIntegrationError` before a typed preview is
constructed.

## Tax boundary

The PR-29 live collector does not contain verified tax-basis evidence. Its
output therefore remains technically complete as broker evidence while the
strict sell preview contains at least:

- `TAX_BASIS_UNAVAILABLE`;
- `ARITHMETIC_INTEGRITY_FAILED`.

The resulting contract has:

- `preview_ready=false`;
- `execution_ready=false`;
- `trading_methods=false`.

This is expected behavior. The integration must not replace an unavailable tax
amount with zero or infer tax data from market value, average price or broker
order totals.

## Account and portfolio checks

Account, position, open-order, currency, price freshness, lot, short-sale and
post-sale portfolio checks remain owned by `build_sell_pretrade_preview`.
The integration does not duplicate or weaken those gates.

An account mismatch is represented as the typed `ACCOUNT_MISMATCH` blocker.
Request-parameter mismatches are rejected before orchestration because they
indicate the wrong live response was bound to the requested preview.

## Broker and API boundary

This module does not import the broker SDK and does not call a network API
directly. A caller supplies a read-only loader. No FastAPI route, OpenAPI
operation, GPT Action or execution adapter is added.

The live collector remains restricted to:

- `GetPositions`;
- `GetOrders`;
- `GetMaxLots`;
- `GetOrderPrice`.

Order creation, replacement and cancellation remain outside the allowed
runtime surface.

## Safety invariants

- the collector is invoked at most once per integration call;
- invalid caller input is rejected before the collector is invoked;
- the source payload is defensively copied;
- `trading_methods` must be the boolean value `false`, not a string or missing
  marker;
- the typed preview can never report execution readiness;
- no public response contract changes;
- Render entrypoint remains `app:app`.

## Validation

Focused tests cover:

- one-call binding and payload immutability;
- expected tax and arithmetic blockers;
- account mismatch propagation;
- stale-price propagation;
- UID, price-basis, quantity and direction tampering;
- missing or enabled trading marker;
- non-mapping source responses;
- invalid input rejection before source access.

Regression Shield must pass lock verification, repository policy, compile,
Ruff, formatting, mypy, stable entrypoint, read-only release contract, full
pytest with coverage, dependency audit, Bandit and secret scanning.

## Rollback

Revert the PR merge commit. PR-29 live collection, PR-26 sell preview, public
API behavior, broker permissions and Render deployment remain unchanged.
