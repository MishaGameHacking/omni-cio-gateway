# Portfolio Shadow Validation v1

## Purpose

PR-06 connects the existing `getPortfolioMarketSnapshot` runtime payload to the
versioned `PortfolioSnapshotV1` contract in observation-only mode.

The public Action response is unchanged. The shadow layer validates a copy-free
view of the same dictionary, emits only bounded aggregate diagnostics, and
returns the original dictionary object to the established route handlers.

## Runtime flow

```text
T-Invest read-only calls
        │
        ▼
legacy portfolio market dictionary
        │
        ├── returned unchanged to the current GET Action
        │
        └── PortfolioSnapshotV1 adapter
                 │
                 ├── ready
                 ├── partial
                 └── rejected
```

The wrapper is installed in `app.py` after the stable `app:app` wrapper stack is
loaded. Existing route handlers resolve the `portfolio_market` module function
at request time, so both `/portfolio/market-snapshot` and analytics that reuse
that source receive the same shadow observation without route duplication.

## Status semantics

- `ready`: the contract is verified, complete, reconciled and contains no
  warning/error quality issue. It is eligible for a future decision workflow.
- `partial`: the contract is valid but incomplete or degraded. It remains useful
  for display, but the decision gate blocks recommendation or execution logic.
- `rejected`: the source dictionary cannot safely satisfy contract v1. The
  current read-only response remains available during shadow rollout, while the
  decision gate fails closed.

## Privacy and logging

Logs contain only:

- schema name and version;
- ready/partial/rejected status;
- quality and completeness labels;
- counts of issues, warnings, positions, cash balances and currencies;
- a fixed error code and exception class for rejected data.

The validator never logs:

- masked or full account identifiers;
- instrument names, tickers, FIGI, UID or position UID;
- holdings, prices, cash, totals or other monetary values;
- raw validation messages or payload fragments.

Python logging filters and handlers can transform records before emission, but
PR-06 avoids relying on downstream redaction by never placing sensitive values
in the record in the first place.

## Fail-closed gate

`require_portfolio_decision_ready()` is deliberately not attached to the
existing read-only route. It is a reusable mandatory gate for future Decision
Engine, rebalancing, preview orchestration and execution workflows.

A non-ready result raises `PortfolioDataQualityGateError` with a fixed code and
no portfolio data.

## Compatibility

PR-06 does not change:

- FastAPI paths, methods or OpenAPI schemas;
- Action operation IDs;
- legacy response fields or values;
- `trading_methods=false`;
- broker SDK permissions;
- Render entrypoint `app:app`;
- Gateway API component version `3.9.1`.

## Rollout and rollback

Shadow validation is intentionally non-blocking for the current read-only
Action. After production observations demonstrate contract stability, a future
Decision Engine may call the fail-closed gate before producing actionable
recommendations.

Rollback is a revert of the PR merge. No API, database, secret or broker-side
migration is required.
