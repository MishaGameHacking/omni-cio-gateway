# Decision Engine v1 acceptance checklist

PR-12 is acceptable for merge only when all items below are confirmed by the
blocking Regression Shield workflow.

## Contract invariants

- every result contains exactly three option kinds;
- exactly one option is preferred;
- strategic rebalance is never preferred before PR-13;
- any global blocker forces `abstain=true`;
- abstention prefers `NO_ACTION / WAIT_FOR_DATA`;
- abstention blocks both change options;
- recommendation readiness requires complete market coverage;
- ready decisions cannot have low confidence;
- option evidence references resolve inside the same decision set;
- all monetary and threshold evidence values are finite Decimal values.

## Data gates

- portfolio analytics is verified and complete;
- risk evaluation is verified, complete and decision-ready;
- every current position has one decision-ready market assessment;
- duplicate market-assessment keys fail closed;
- supplied news contains at least one accepted fact;
- context-only or rejected news cannot be the sole news evidence;
- contradictory accepted records for one event cluster force abstention.

## Execution boundary

- no broker SDK import or call;
- no HTTP or socket client;
- no quantity, lot, price or order identifier in the decision contract;
- no confirmation or idempotency token;
- every option has `execution_ready=false`;
- every option and decision set retain `trading_methods=false`;
- public FastAPI routes and OpenAPI schemas remain unchanged;
- Render entrypoint remains `app:app`;
- Gateway API component remains `3.9.1`.

## Required validation

- dependency lock consistency;
- repository safety policy;
- Python compilation;
- Ruff lint;
- formatting baseline;
- mypy;
- stable gateway entrypoint test;
- full pytest and coverage;
- dependency audit;
- Bandit/SAST;
- tracked-content secret scan.

## Rollback

Revert the PR-12 squash merge commit. PR-12 changes no database, public API,
Render configuration, broker permission, secret or external system state.
