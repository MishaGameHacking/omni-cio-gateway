# Final Decision Review Production Owner Callables V1

## Status

PR-77 production composition boundary. Internal and read-only.

This package registers the fixed PR-76 purchase and sell provider adapters in the production
runtime. It does not provide financial values by itself. A trusted internal workflow must
publish typed owner callables for an exact scenario before either provider can run.

## Safety boundary

- `trading_methods=false`;
- no HTTP route or request body;
- no public publication method;
- no broker order, replacement, cancellation, transfer or withdrawal method;
- no dynamic import or user-selected provider ID;
- no calculator, portfolio or broker call during `app:app` import;
- no serialization or logging of callables, account data or calculator payloads;
- a missing or mismatched owner bundle fails closed.

## Runtime objects

`FinalDecisionReviewProductionRuntimeV1` owns:

1. the existing bounded final-review scenario-source store;
2. the PR-75 calculator provider registry;
3. a new bounded process-local owner-callable store;
4. an immutable receipt confirming registration of the two fixed dispatchers.

The owner-callable store starts empty after every process start. Registration installs:

- `provider:existing:purchase-review`;
- `provider:existing:sell-review`.

Installing those dispatchers never calls an owner. The provider registry is therefore
non-empty at startup while still returning a safe failure until a trusted internal producer
publishes the exact scenario owners.

## Owner bundle

One immutable bundle is keyed by:

```text
(scenario_id, correlation_id, operation)
```

The operation is exactly one of:

- `purchase_review`;
- `sell_review`.

A purchase bundle contains `ApprovedPurchaseCalculatorOwnersV1`. A sell bundle contains
`ApprovedSellCalculatorOwnersV1`. Mixing both directions or providing neither is rejected.
Each common owner set supplies the already typed decision, exact intent, capacity and
explicit pro-forma risk outputs. The directional owner supplies purchase or sell previews.

## Publication rules

Publication is a direct in-process method intended only for trusted composition code.

- scenario and correlation IDs must match the safe identifier contract;
- publication and expiry timestamps are timezone-aware UTC;
- TTL is bounded to `1..86400` seconds;
- capacity is bounded to `1..1024` bundles;
- an active exact duplicate is rejected;
- expired bundles are purged before publication and lookup;
- overflow evicts the least-recently-used older bundle;
- publication does not invoke an owner;
- the receipt explicitly records no broker write, authorization or order creation.

Rejecting active duplicates prevents a callable set from being silently replaced while an
approved invocation begins. The first exact lookup then pins that immutable bundle to the
invocation ID, so later LRU eviction or republication cannot mix owner sets mid-review.

## Invocation flow

1. Trusted internal code publishes a directional owner bundle for the exact scenario.
2. Internal orchestration builds an approved invocation request.
3. The PR-75 registry selects one fixed provider ID and operation.
4. The PR-76 adapter validates the operation before its first owner call.
5. The PR-77 router requires the exact scenario, correlation and operation bundle.
6. Existing owners return typed decision, intent, capacity, preview and pro-forma risk data.
7. PR-76 validates every output and constructs the provider bundle.
8. PR-75 revalidates identity, direction and freshness.
9. PR-74 performs replay-safe trusted publication into the existing scenario store.

The immutable owner bundle remains outside the HTTP layer throughout this flow.

## Fail-closed behavior

| Condition | Result before financial output is accepted |
|---|---|
| Store is empty after startup | Provider call fails |
| Scenario or correlation differs | Lookup fails before first owner call |
| Operation differs | Directional lookup fails |
| Bundle expired | Bundle is purged and lookup fails |
| Bundle was published after invocation time | Invocation fails |
| Invocation-pin capacity is full | Lookup fails before first owner call |
| One invocation ID is reused for a different key or timestamp | Lookup fails |
| Owner raises | PR-76 converts it to a safe owner-call failure |
| Owner returns a raw mapping or wrong type | PR-76 rejects the output |
| Capacity or directional preview is empty | PR-76 rejects the output |
| Pro-forma risk timestamp is invalid | PR-76 rejects the output |
| Registry identity, direction or freshness differs | PR-75 rejects the bundle |

The production HTTP handler may consequently return its existing safe unavailable response.
PR-77 does not change that response contract.

## Concurrency and lifecycle

The store uses an `RLock` only for bounded map operations. Owner code is never called while
the lock is held. Stored bundles are frozen dataclasses.

The first owner lookup pins the exact bundle to `invocation_id`. All later decision, intent,
capacity, risk and preview lookups for that invocation return the pinned object, even if the
active LRU entry is evicted and its key is republished concurrently. Reusing the invocation
ID with another scenario, correlation, operation or invocation timestamp fails. The
directional preview releases the pin in a `finally` block. An abandoned or earlier-failed
invocation retains its pin only until the same bounded TTL expires. New pins fail closed when
pin capacity is full; live pins are never evicted to admit another invocation.

Trusted in-process composition may discard an exact active bundle after invocation. Discard
does not invalidate an already pinned immutable object; pins are released explicitly or by
TTL. No public delete or mutation route is created.

The store is deliberately process-local:

- restarts clear all owner bundles;
- separate workers do not share bundles;
- no callable is persisted or reconstructed;
- a production producer must publish and invoke within the same process and TTL.

Multi-worker or durable distribution is outside this package. It must not be implemented by
serializing Python callables or financial payloads.

## OpenAPI and deployment compatibility

PR-77 does not edit `app.py`, the OpenAPI schema or the Gateway version:

- stable entrypoint: `app:app`;
- Gateway version: `3.10.0`;
- production action surface: 14 GET operations;
- request bodies: none;
- broker write methods: none.

## Explicitly not completed

This package does not yet compose concrete scenario-specific callables from the Decision
Engine, capacity owner, purchase/sell preview owners and an explicit pro-forma risk owner.
It also does not prove Render deployment, GPT schema import, authenticated Preview, action
inspection or rollback.

The next package must construct and publish those owners from existing typed read-only
components without substituting current risk for pro-forma risk. Production acceptance
remains `not_executed` until real external evidence is recorded.
