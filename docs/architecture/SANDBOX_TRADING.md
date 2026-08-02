# Sandbox trading architecture

Status: design/development only. Production remains read-only until explicit release acceptance.

## Goal

Add a controlled order-execution path to Omni-CIO in stages without changing the current production safety boundary until sandbox acceptance is complete.

Target user flow:

1. Analyze portfolio and market data.
2. Build an immutable `TradeProposal`.
3. Explain instrument, side, lots, price basis, estimated cost/commission, rationale, risks and expiry.
4. Ask the owner for explicit confirmation of that exact proposal.
5. Revalidate instrument identity, market status, fresh market data, affordability, limits and expiry.
6. Submit the approved sandbox order exactly once.
7. Return broker order status and record an audit event.

## Modes

- `READ_ONLY` — current production behavior. No broker writes.
- `SANDBOX` — write methods allowed only against T-Invest Sandbox using a dedicated sandbox token and sandbox account.
- `LIVE_LOCKED` — production trading code may exist but cannot submit real orders.
- `LIVE_CONFIRM_EACH_ORDER` — future mode; each real order requires explicit confirmation of one immutable proposal and a separate owner enablement step.

Default remains `READ_ONLY`.

## Credentials

Keep credentials separate:

- `TINVEST_TOKEN` — existing read-only production token.
- `TINVEST_SANDBOX_TOKEN` — dedicated Sandbox token; Render secret only.
- `TINVEST_TRADE_TOKEN` — future real trading token; must not exist or be required during sandbox development.

Never store token values in GitHub, GPT Knowledge, logs, tests or fixtures.

## T-Invest sandbox endpoint

Use the sandbox API endpoint for sandbox-mode broker calls:

- gRPC/gRPC-web: `sandbox-invest-public-api.tbank.ru:443`
- REST proxy: `https://sandbox-invest-public-api.tbank.ru/rest/`

Production broker reads continue to use the existing production endpoint.

## Initial execution scope

Sandbox v1 supports only ordinary buy/sell orders plus sandbox account lifecycle and order-state checks. Margin/leverage, shorts, derivatives, transfers, stop orders and autonomous execution are outside v1. Even if the T-Invest sandbox permits leverage/shorts, Omni-CIO must reject them in v1.

## Proposal contract

A proposal must contain at least `proposal_id`, account mode, masked account reference, instrument identity, side, lots, order type, price basis, market-data timestamp, expected amount, estimated fees when available, affordability result, rationale, risks, expiry, one-time idempotency key and proposal fingerprint/hash.

The proposal step must never submit an order.

## Confirmation contract

Order submission requires a second request referencing the exact proposal. Before submission the Gateway must revalidate proposal state, expiry, instrument identity, market status, market data, affordability and material price changes, then atomically consume the idempotency key. Any rejection requires a fresh proposal and new confirmation.

## Audit journal

Record safe metadata for proposal creation, confirmation, pre-submit revalidation, broker submission result, final order status and sandbox cleanup. Never log tokens, Authorization headers, full private account IDs or full broker payloads.

## Safety invariants

- Production mode remains read-only by default.
- Real-money order submission must remain unreachable during sandbox development.
- Sandbox and production tokens/accounts must never be interchangeable.
- Duplicate confirmation must never create duplicate orders.
- Stale proposal, stale market data, market-closed state or material price change must fail closed.
- Technical affordability must be distinguished from an investment recommendation.

## Development gates

1. Architecture/contracts and mocked tests.
2. Sandbox account lifecycle and virtual funding.
3. Sandbox buy proposal → confirmation → revalidation → order → status.
4. Sandbox sell with the same controls and explicit short-sale rejection.
5. Custom GPT sandbox-only Actions after backend acceptance.
6. Owner end-to-end sandbox acceptance.
7. Optional live design only after a separate explicit owner decision.

No real-money trading is part of the sandbox release.
