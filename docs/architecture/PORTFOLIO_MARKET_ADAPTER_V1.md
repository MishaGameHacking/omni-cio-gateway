# Portfolio Market Adapter v1

PR-05 introduces a fail-closed adapter from the existing read-only
`getPortfolioMarketSnapshot` payload to `PortfolioSnapshotV1`.

## Boundary

The adapter lives in `omni_cio/adapters/portfolio_market_v1.py`. It does not
change FastAPI routes, GPT Actions, OpenAPI responses, broker calls or Render
runtime behavior. Existing dictionaries remain the public API.

## Mapping rules

- the source must explicitly report `trading_methods=false`;
- the account identifier must already be masked;
- timestamps must be timezone-aware and are normalized to UTC;
- money and quantities are parsed as finite `Decimal` values;
- currencies remain separate and are never converted or summed together;
- stable instrument identity and positive lot size are required;
- only the existing last-price valuation is selected as the canonical v1 value;
- bond clean value and accrued interest are stored separately;
- reported and blocked cash are preserved as distinct values;
- portfolio totals must reconcile with cash and securities;
- a complete source must also reconcile position valuations with currency totals;
- missing valuations, component errors, skipped instruments and missing identity
  downgrade contract quality instead of being hidden.

## Failure policy

Malformed, unmasked, trading-enabled or arithmetically inconsistent payloads
raise `PortfolioMarketAdapterError`. The adapter never repairs contradictory
financial data by guessing.

## Compatibility

`CashBalanceV1.blocked` is an optional backward-compatible v1 field. No existing
consumer is required to provide it. Breaking changes still require a new
contract package and migration plan.

## Safety

The adapter is data-only. It imports no broker SDK and contains no order,
cancellation, transfer or withdrawal behavior. `app:app`, GET-only Actions and
`trading_methods=false` remain unchanged.
