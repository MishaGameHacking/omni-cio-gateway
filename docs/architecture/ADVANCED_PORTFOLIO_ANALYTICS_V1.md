# Advanced Portfolio Analytics v1

## Purpose

PR-08 adds a deterministic analytics layer over a verified
`PortfolioSnapshotV1`. It calculates only metrics supported by the normalized
snapshot and explicitly reports unavailable inputs instead of inventing values.

This package is not connected to a public FastAPI route in PR-08. Existing GPT
Actions and OpenAPI schemas remain unchanged.

## Source gate

The engine accepts only a portfolio snapshot that is:

- `quality=verified`;
- `completeness=complete`;
- free of warning/error `DataIssue` records;
- valued using `last_price` with a timestamp;
- fully reconciled by currency;
- consistent between instrument and valuation currency.

A partial, degraded, unvalued, negative-value or currency-inconsistent position
fails closed.

## Calculations

All calculations use `Decimal` and are performed separately for each currency.
No implicit FX conversion or cross-currency portfolio total is produced.

For every currency the engine calculates:

- cash value and weight;
- clean securities value;
- accrued interest;
- invested value and weight;
- full position value, including bond accrued interest;
- position weights within total portfolio value and invested value;
- allocation by instrument type;
- top-1 and top-5 concentration;
- Herfindahl-Hirschman Index (HHI) over invested positions;
- effective position count, `1 / HHI`;
- deterministic stress sensitivities for configured negative shocks.

## Stress semantics

The default shocks are `-10%`, `-20%` and `-30%` applied uniformly to the
invested portion of one currency portfolio. Cash is unchanged.

These scenarios answer: “What would the arithmetic portfolio effect be if all
currently valued investments in this currency moved by the same percentage?”

They are not:

- a forecast;
- a probability estimate;
- Value at Risk;
- a substitute for historical volatility, correlation or liquidity analysis.

## Missing data

The result contains explicit `missing_data` records for metrics not supported by
portfolio contract v1:

- issuer and sector allocation;
- order-book liquidity, spread and market capacity;
- historical returns, volatility, drawdown and correlation;
- tax lots and acquisition cost basis;
- bond duration, maturity/offer schedule and current credit ratings when bonds
  are present.

The engine never substitutes a guessed value for these inputs.

## Privacy and compatibility

The analytics contract reuses the masked account reference and source
provenance. It adds no token, full account number, broker error payload or
private document content.

PR-08 does not change:

- public routes or HTTP methods;
- Action operation IDs or OpenAPI schemas;
- broker SDK calls or permissions;
- `trading_methods=false`;
- Render entrypoint `app:app`;
- Gateway API component version `3.9.1`.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
