# Final Decision Review Approved Owner Acquisition V1

## Status

PR-79 internal production acquisition boundary. Read-only, server-owned and
fail-closed.

This package closes the gap between a trusted server request context and the
PR-78 one-shot composition boundary. It does not calculate financial values,
publish a new Action or choose a provider from user input.

## Trusted server context

`FinalDecisionReviewApprovedServerContextV1` is the only source of:

- invocation ID;
- scenario ID;
- correlation ID;
- purchase/sell operation;
- masked account;
- invocation timestamp.

The context is immutable, authenticated, internal-only and read-only. It can
contain only `AccountReference`, so a full account identifier is rejected by
the existing masking contract. The acquisition method accepts no financial
payload, credential, account argument, provider name or request body.

## Exact owner source set

The internal source set has seven evidence slots:

1. server context;
2. Decision Engine owner;
3. exact capacity-intent owner;
4. capacity-assessment owner;
5. explicit `ProFormaRiskScenarioV1` owner;
6. purchase-preview owner;
7. sell-preview owner.

For one invocation, the four common owners and exactly one directional preview
owner are selected. The opposite preview owner is marked `not_selected` and is
never loaded.

Each selected loader returns only an immutable owner lease:

- exact slot;
- callable owner reference;
- safe provider and operation names;
- timezone-aware observation time;
- fixed safety flags.

The lease carries no calculated financial value, credential or full account
identifier. Loader metadata must exactly match lease metadata.

## Presence and freshness gates

The default limits are:

- maximum context/lease age: 300 seconds;
- future-clock tolerance: 30 seconds.

The context must be present, typed and fresh before any owner loader is called.
All five selected owner leases are then loaded exactly once. PR-78 is called
only when every selected lease is present, typed, metadata-bound and fresh.

A missing, failed, timed-out, mismatched, stale or future-dated source prevents
all financial owner calls. Source exception text is not returned or logged.

## Account and request binding

PR-79 builds `ApprovedCalculatorInvocationRequestV1` from the server context.
It wraps the selected callables so they accept only that exact request.

Before PR-78 accepts the values, the wrappers also require:

- Decision Engine output account equals the server-context account;
- pro-forma scenario account equals the server-context account;
- every selected directional preview account equals the server-context
  account.

PR-78 then performs its existing exact scenario, intent, capacity, preview,
risk, direction, fingerprint, policy and freshness validation. No owner is
executed twice.

## Existing safe unavailable mapping

Acquisition has only two internal statuses:

- `acquired` — PR-78 completed successfully;
- `unavailable` — no final-review source was produced.

Every blocked result maps to the already published handler outcome:

```text
FINAL_REVIEW_SOURCE_UNAVAILABLE
HTTP 503
```

The public final-review route therefore keeps its existing response contract.
Missing or stale evidence is never presented as `ok`, `pending` or a completed
review.

## Production registration

`FinalDecisionReviewProductionRuntimeV1` owns one
`FinalDecisionReviewApprovedOwnerAcquisitionV1` connected to the same PR-78
composition object.

Production startup installs fixed missing source loaders and a missing context
loader. Registration performs no:

- context acquisition;
- owner acquisition;
- Decision Engine calculation;
- portfolio load;
- network or broker call.

The runtime remains unavailable until a later, separately reviewed production
composition supplies exact server-context and existing owner loaders.

## Safety and compatibility

- stable entrypoint: `app:app`;
- Gateway version: `3.10.0`;
- production OpenAPI: unchanged 14 authenticated GET operations;
- request bodies: none;
- dynamic imports and user-selected providers: none;
- raw financial payloads: none;
- credentials and full account identifiers: none;
- broker order, replacement, cancellation, transfer or withdrawal calls:
  none;
- trade authorization and execution readiness: false;
- `trading_methods=false`.

The official T-Invest token documentation states that a read-only token cannot
place trading orders. PR-79 additionally preserves the repository broker-write
allowlist and contains no broker client call.

Official source checked on 2026-07-30:
[`T-Invest API — Token`](https://developer.tbank.ru/invest/intro/intro/token).

## Explicitly not completed

PR-79 defines and registers the approved acquisition controller, but production
still lacks an authenticated server-context producer and concrete loader
installation for the existing calculators. Those components must be reviewed
separately; they cannot be replaced with raw Action payloads.

Render, Gateway, GPT Editor and rollback acceptance also remain
`not_executed`. Green CI does not satisfy those external cases.

## Rollback

Revert PR-79. The PR-78 composition, fixed PR-77 provider routing and the
existing fail-closed `503` route behavior remain intact. No data, secret,
OpenAPI or dependency migration is required.
