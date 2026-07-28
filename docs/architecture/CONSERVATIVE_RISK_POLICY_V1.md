# Conservative Risk Policy v1

## Purpose

PR-09 adds a versioned, non-personalized capital-preservation policy and a pure
evaluation engine over `AdvancedPortfolioAnalyticsV1`.

The policy reports facts, known limit breaches and missing critical inputs. It
does not create a recommendation, preview or order and is not connected to a
public FastAPI route in PR-09.

## Default engineering baseline

The default values are conservative system guardrails, not personalized
investment advice:

| Control | Default |
|---|---:|
| Maximum one-position weight | 20% |
| Maximum one-issuer weight | 20% |
| Maximum one-sector weight | 35% |
| Maximum one asset-class weight | 70% |
| Top-five invested concentration warning | 80% |
| Invested HHI warning | 0.25 |
| Minimum cash reserve | 10% |
| Maximum high-risk exposure | 10% |
| Maximum illiquid exposure | 10% |
| Maximum non-base-currency exposure | 20% |
| Minimum credit rating placeholder | A- |
| Maximum duration | 5 years |
| Maximum historical drawdown | 20% |
| Stress shock | -20% |
| Maximum total stress loss | 15% |
| Maximum future order weight | 10% |
| Maximum future daily turnover | 20% |

Margin, short sales, derivatives and currency trading operations remain disabled.
The standard instrument-type allowlist contains shares, bonds, ETFs and funds.
Currencies, futures and unknown instrument types are prohibited as investment
instruments in standard mode; cash balances are evaluated separately.

## Check states

- `pass`: a known value satisfies the limit;
- `warning`: a known concentration indicator exceeds a warning threshold;
- `breach`: a known blocking limit is violated;
- `unknown`: a blocking limit cannot be verified because a required source is
  absent;
- `not_applicable`: the check requires a concrete future proposal or does not
  apply to the current portfolio.

Absence of data is never treated as a pass.

## Current evaluable checks

Using PR-08 analytics, PR-09 can evaluate:

- allowed currencies;
- minimum cash reserve per currency;
- position weight;
- instrument type allowlist;
- optional stable-key allowlist and denylist;
- asset-class weight;
- top-five invested concentration;
- invested HHI;
- uniform stress-loss ratio;
- disabled margin, short, derivative and currency-operation configuration.

## Current unknown checks

Until PR-10 supplies normalized market and reference contracts, the engine must
return blocking `unknown` checks for:

- issuer concentration;
- sector concentration;
- explicit high-risk classification;
- liquidity and illiquid exposure;
- current credit rating;
- bond duration;
- historical maximum drawdown;
- total non-base-currency weight when FX conversion would be required.

This intentionally means that a portfolio with investments is usually not yet
`decision_ready` after PR-09. PR-10 is required to resolve the missing market
inputs.

## Priority and readiness

Overall status precedence:

1. known blocking breach → `breach`;
2. blocking missing input → `unknown`;
3. non-blocking warning → `warning`;
4. otherwise → `pass`.

`decision_ready=true` only when there is no blocking breach and no blocking
unknown check.

## Currency boundary

Risk checks remain per currency. The engine does not sum RUB, USD, EUR or CNY
without an explicit FX contract. If non-base currency value is present, the
cross-currency allocation check remains `unknown` until rates and timestamps are
available.

## Compatibility and safety

PR-09 does not change:

- FastAPI paths or HTTP methods;
- GPT Action operation IDs or OpenAPI schemas;
- broker SDK calls or permissions;
- `trading_methods=false`;
- Render entrypoint `app:app`;
- Gateway API component version `3.9.1`.

The policy cannot enable margin, shorts, derivatives or currency operations.
The default policy model rejects attempts to mark it as personalized.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
