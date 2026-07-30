# Final Decision Review Trusted Owner Composition V1

## Status

PR-78 internal production composition boundary. Read-only and fail-closed.

This package materializes already existing typed calculation owners once, proves that their
outputs describe one exact post-change scenario, publishes immutable snapshot owners through
the PR-77 store, invokes one fixed PR-76 provider, and removes the temporary owner bundle.

## Why a pro-forma scenario is required

A raw `RiskPolicyEvaluationV1` cannot prove whether it describes the current portfolio or
the portfolio after the reviewed change. PR-78 therefore requires the existing
`ProFormaRiskScenarioV1` owner contract.

That contract carries:

- `current_portfolio_risk=false`;
- `pro_forma_post_change=true`;
- method `exact_capacity_intent_post_change`;
- masked account;
- requested option and homogeneous direction;
- exact capacity-order requests;
- deterministic intent fingerprint;
- scenario generation time equal to the risk retrieval time;
- no order, execution or trading capability.

PR-78 recalculates the fingerprint and rechecks all markers before publication. Current risk
cannot be silently substituted for post-change risk.

## Trusted owner ports

The common owner set supplies callable ports for:

1. one typed `DecisionSetV1`;
2. one typed `CapacityIntentDecisionGateRequestV1`;
3. one bounded non-empty iterable of `CapacityAssessmentV1`;
4. one typed `ProFormaRiskScenarioV1`.

The directional owner supplies one bounded non-empty iterable of either purchase or sell
previews. The maximum capacity and preview row count is 100. Raw mappings and mixed
directional preview types are rejected.

## Materialization

An owner is called only inside explicit `invoke_purchase` or `invoke_sell`; production
registration does not call it.

The five owner ports are materialized exactly once:

1. decision;
2. intent;
3. capacity;
4. pro-forma scenario;
5. directional previews.

The later PR-76 adapter receives immutable snapshot callables. Those accessors only return
the already materialized typed objects and reject any request other than the exact approved
request. Financial calculations are therefore not repeated by the provider adapter.

## Binding gates before publication

PR-78 requires:

- approved operation matches purchase or sell method;
- scenario ID matches the approved request;
- scenario option matches the exact intent request;
- scenario capacity requests equal the intent requests;
- every intent and capacity request uses the homogeneous direction;
- capacity coverage is unique, complete and exactly equal to intent;
- preview stable keys are unique and exactly cover intent instruments;
- decision, preview, scenario and risk use the same masked account;
- risk retrieval time equals the scenario generation time;
- scenario fingerprint equals a fresh canonical fingerprint;
- scenario method and current/pro-forma literal markers are correct;
- margin, short sale, derivatives and currency-operation risk flags are false;
- scenario time is at most 300 seconds old and no more than 30 seconds ahead of invocation.

Any exception, wrong type, empty iterable, row overflow, mismatch or unsafe risk policy fails
before owner publication.

## One-shot invocation flow

1. A trusted internal caller supplies an approved request and directional owner ports.
2. PR-78 materializes and validates all typed outputs.
3. Snapshot owners are published under exact scenario, correlation and operation identity.
4. PR-75 invokes the fixed PR-76 purchase or sell provider.
5. PR-77 pins the immutable snapshot bundle to the full invocation identity.
6. PR-76 and PR-75 revalidate output types, identity, direction and freshness.
7. PR-74 performs replay-safe publication into the final-review scenario store.
8. PR-78 releases any remaining invocation pin and discards the active owner bundle in a
   `finally` path.

Owner cleanup occurs on both success and downstream failure. Abandoned pins caused by a
process interruption still expire under the bounded PR-77 TTL.

## Failure behavior

| Failure | Boundary behavior |
|---|---|
| Wrong approved operation | No owner is called |
| Owner raises | Safe owner-call error; no publication |
| Raw or wrong output type | Rejected before publication |
| Current risk supplied as pro-forma | Rejected before publication |
| Fingerprint, account, option or direction mismatch | Rejected before publication |
| Capacity or preview coverage differs | Rejected before publication |
| More than 100 capacity or preview rows | Rejected before publication |
| PR-77 publication fails | No provider invocation |
| PR-75/PR-74 invocation fails | Pin released and owner bundle discarded |

Original exception text is not returned in the public error message.

## Production registration

`FinalDecisionReviewProductionRuntimeV1` owns one
`FinalDecisionReviewTrustedOwnerCompositionV1` connected to the same provider registry and
owner-callable store registered by PR-77. Construction performs no portfolio, network,
calculator or broker call.

The runtime still begins with:

- zero scenario-specific owner bundles;
- zero owner pins;
- zero final-review scenario bundles.

## Compatibility and safety

- stable entrypoint: `app:app`;
- Gateway version: `3.10.0`;
- production OpenAPI: unchanged 14 GET operations;
- request bodies: none;
- public owner publication route: none;
- dynamic provider selection: none;
- broker write methods: none;
- trade authorization: none;
- order creation: none;
- `trading_methods=false`.

## Explicitly not completed

PR-78 provides the trusted internal call boundary but does not choose when a real user
request should run the Decision Engine, capacity, broker-preview and post-change risk
calculators. It does not add a public route for supplying callables or financial payloads.

A later package must bind an approved server-side acquisition workflow to these ports
without accepting raw user payloads, credentials or full account identifiers. Render,
Gateway, GPT Editor and rollback acceptance remain `not_executed` until real external
evidence is recorded.
