# Omni-CIO v9 — WP11 Immutable Portfolio Plan Protocol

## Status

WP11 defines the internal, read-only `PORTFOLIO_PLAN` protocol between WP10 portfolio optimization and the future WP12 safe execution engine. It does **not** add an order endpoint, broker mutation service, Sandbox submit path, real-trading token use, OpenAPI Action, Render mutation state or Custom GPT configuration change.

The applied Custom GPT remains v8.6.1 until WP15.

## Purpose

A portfolio recommendation is not safe to approve if its portfolio state, policy, risk state, strategy, optimizer output, market evidence or cost assumptions can change without changing the object being approved. WP11 therefore compiles the exact upstream decision state into one immutable, fingerprinted object whose approval challenge is derived from that exact identity.

WP11 is a protocol and review layer only. `execution_authorized=false` and `trading_methods=false` are hard-coded contract invariants.

## Exact upstream binding

A plan binds all of the following:

1. exact portfolio snapshot SHA-256;
2. exact WP2 policy reference and recomputed policy fingerprint;
3. exact current WP8 assessment SHA-256;
4. exact WP9 selection SHA-256;
5. exact WP10 optimizer SHA-256;
6. exact WP10 target WP8 assessment SHA-256;
7. exact optimizer target rows and ordered rebalance legs;
8. exact market, friction and FX baselines used for each actionable leg.

WP11 recomputes the canonical WP8/WP9/WP10 hashes before plan construction. A caller cannot pass a `model_copy` mutation while retaining an old embedded SHA and still obtain a plan.

## Plan identity

`PortfolioPlanV1` is frozen through the common Pydantic `ContractModel`. Its canonical SHA-256 excludes only the self-referential `plan_sha256` and the derived owner approval phrase. Every material input remains inside the hashed payload.

The approval challenge is deterministic:

`ПОДТВЕРЖДАЮ ПЛАН <first 12 hex chars of exact plan SHA>`

The phrase is a downstream approval challenge, not an execution authorization. Any material plan mutation changes the canonical SHA and therefore changes the expected phrase. A stale phrase cannot approve a mutated plan.

## Ordered legs and arithmetic

Every actionable WP10 optimizer leg appears exactly once in deterministic order and remains embedded as the exact `OptimizerRebalanceLegV1`. The plan preserves:

- BUY/SELL side;
- current and target lots;
- lot size;
- clean execution reference price;
- bond accrued interest (НКД) per lot and total;
- clean notional;
- settlement notional;
- commission basis points and amount;
- estimated sell-tax basis points and amount;
- exact cash delta;
- staged-execution metadata and partial-fill awareness;
- market and friction evidence hashes.

Plan totals must reconcile to the embedded legs. Current and target values must reconcile to target rows plus cash, and the WP8 risk before/after values must reconcile to the corresponding optimizer scenarios.

`NO_ACTION` is represented explicitly as one `NO_ACTION` leg with zero turnover/costs, unchanged lots and identical risk before/after.

## Market, friction and FX evidence

Actionable plan creation fails closed unless required WP10 evidence is still fresh at plan creation time.

Default freshness limits:

- market evidence: 300 seconds;
- friction evidence: 86,400 seconds;
- FX evidence: 300 seconds;
- future timestamp tolerance: 60 seconds.

Bond BUY/SELL legs require explicit accrued-interest evidence. Missing values are not converted to zero. BUY legs require current account eligibility. SELL legs may remain reviewable when an already-held instrument is no longer buy-eligible; this allows risk-reducing exits without falsely treating buy eligibility as sell eligibility.

## Validity and cancellation

The default plan validity window is 900 seconds. Review before `created_at` or at/after `expires_at` invalidates the approval challenge.

The plan declares every hard cancellation condition in its immutable payload. Cancellation classes include:

- plan not yet valid / expired;
- portfolio, policy, current-risk, strategy, optimizer or target-risk identity change;
- missing, stale or future market evidence;
- stale or future friction evidence;
- stale or future FX evidence;
- clean-price drift;
- accrued-interest drift;
- spread widening;
- turnover-capacity deterioration;
- top-of-book depth deterioration;
- FX drift;
- friction source/rate/tax change;
- BUY account-eligibility change.

Default drift tolerances are deliberately bounded and deterministic. Observed drift values themselves are not artificially capped at 10,000 bps, so extreme discontinuities remain representable and still fail closed.

## Review protocol

`review_portfolio_plan` first re-validates the complete plan payload. A `model_copy` mutation with a stale plan hash is rejected as a tampered plan before market review.

The review then checks exact upstream identities and one current observation per actionable leg. Missing observations cancel the plan; observations for unknown plan legs are rejected. Equivalent observation ordering is canonicalized.

A valid review may expose the exact plan-specific owner approval phrase. It still returns:

- `execution_authorized=false`;
- `trading_methods=false`.

No WP11 function accepts broker client, token, journal, order, submit, execute, replace or cancel parameters.

## Threat model

WP11 specifically protects against:

- approving a different portfolio than the one optimized;
- approving a mutated IPS/risk/strategy/optimizer object under an old hash;
- approving different lots/costs than WP10 produced;
- reviving stale optimizer market or friction evidence later;
- hiding bond НКД from settlement cash;
- silently changing commission/tax evidence;
- using stale/future market or FX observations;
- approval challenge replay after a material plan mutation;
- converting a read-only plan into broker execution authority.

WP11 does not claim to provide cryptographic signatures or broker-side authorization. Those are outside this protocol. WP12 must consume the exact valid plan identity and preserve the already-proven v8.6.1 explicit confirmation, idempotency, limits and broker-reconciliation safety boundary.

## Repository guard

`scripts/check_plan_boundary.py` and `tests/test_portfolio_plan_boundary_v1.py` permanently guard the WP11 package against broker/Sandbox/Real mutation imports, order-state fields and accidental execution parameters. The plan package is included in mypy scope.

## Exit gate

WP11 is complete only after:

- architecture/contracts/runtime/tests are committed;
- boundary guard passes;
- Ruff and Ruff format pass;
- mypy passes with `omni_cio/plans` included;
- full exact-head Regression Shield passes;
- all PR review threads are resolved;
- squash merge to `main` is complete;
- epic/status documents identify WP12 as the next dependency-ready package.
