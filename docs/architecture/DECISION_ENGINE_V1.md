# Decision Engine v1

## Purpose

PR-12 adds a deterministic, abstain-first analytical decision layer over the
verified portfolio, risk, market-readiness and sanitized-news contracts.

The engine always considers three alternatives:

1. keep the current structure or wait for data;
2. review a limited change;
3. review a larger strategic rebalance.

It does not select an instrument to buy or sell, calculate lots, produce an
order preview, request confirmation or call a broker.

## Input gates

### Portfolio

The advanced portfolio analytics input must be:

- `decision_ready=true`;
- `quality=verified`;
- `completeness=complete`;
- free of warning/error data issues;
- explicitly free of cross-currency aggregation.

### Risk policy

The risk evaluation must be:

- `decision_ready=true`;
- overall `pass` or non-blocking `warning`;
- `quality=verified` and `completeness=complete`;
- free of blocking data issues;
- explicitly free of cross-currency aggregation.

A known blocking breach or an unknown critical input forces abstention.

### Market readiness

Every current portfolio instrument must have exactly one corresponding
`InstrumentMarketReadinessV1` row. Its assessment must be decision-ready.

Missing coverage, stale values, unavailable components or untrusted sources
force abstention. Duplicate market rows for one stable key fail closed.

A cash-only portfolio has zero required market instruments and therefore does
not invent a market-data requirement.

### News

News input is optional. When documents are supplied:

- at least one must be `accepted`;
- context-only or rejected documents cannot be the sole news evidence;
- rejected documents are ignored as analytical evidence;
- accepted records with the same instrument and event cluster but different
  exact content fingerprints are treated as a contradiction.

The Decision Engine never reads raw HTML. It consumes only PR-11 sanitized
contracts.

## Evidence model

Every decision contains typed evidence:

- `fact`;
- `calculation`;
- `inference`;
- `scenario`;
- `recommendation`;
- `warning`;
- `missing_data`.

PR-12 currently emits source facts, market-coverage calculations, verified risk
warnings and explicit missing-data blockers. Evidence IDs are unique and every
option may reference only evidence present in the same decision set.

## Options

### No action

When every gate is ready and no verified risk warning exists, `hold` is the
preferred option.

When any gate is open, the no-action option becomes `wait_for_data` and is the
only preferred option.

### Limited change

A verified non-blocking risk warning may make limited review preferred. The
option still contains no instrument, quantity, price or execution field.

Without a warning, limited review remains available but is not preferred.

### Strategic rebalance

Strategic rebalance is always considered but cannot be preferred in PR-12.
When global gates are ready it is `review_only`; when they are not ready it is
blocked. Target ranges and exact sizing are PR-13 scope.

## Abstention

`abstain=true` requires:

- low confidence;
- preferred `no_action` option;
- action `wait_for_data`;
- both change options blocked;
- at least one explicit global blocker;
- `recommendation_ready=false`.

Global blockers are:

- portfolio not ready;
- risk not ready;
- market not ready;
- market coverage incomplete;
- supplied news has no accepted fact;
- accepted news contradiction.

The absence of data is never converted into confidence.

## Confidence

- `low`: at least one blocking gate is open;
- `medium`: gates pass but risk warnings exist, or no accepted news evidence was
  supplied;
- `high`: all gates pass, risk has no warning and at least one accepted news fact
  is present.

Confidence is determined by structured evidence quality, not writing style.

## Execution boundary

`recommendation_ready=true` means only that the analytical option set is
internally consistent. It never means that a broker operation is ready.

Every option contains:

- `execution_ready=false`;
- `trading_methods=false`.

The decision contract contains no quantity, lot, price, order ID, idempotency
key or confirmation token.

PR-13 adds threshold rebalancing; PR-14 adds preview orchestration. Neither is
implemented by PR-12.

## Compatibility and safety

PR-12 does not change:

- FastAPI routes or HTTP methods;
- GPT Action operation IDs or OpenAPI schemas;
- broker SDK calls or permissions;
- Gateway version `3.9.1`;
- Render entrypoint `app:app`;
- `trading_methods=false`.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
