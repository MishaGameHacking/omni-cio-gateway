# V9 Portfolio Watchtower

## Status

WP13 is a read-only monitoring layer over canonical Omni-CIO evidence. It does not create a second risk engine, credit engine, broker client, execution service or Gateway.

Applied Custom GPT remains v8.6.1 until WP15.

## Objective

Portfolio Watchtower periodically evaluates the latest trusted portfolio/risk, credit and market-event state, emits only material deduplicated alerts, and can request downstream recommendation/proposed-plan work. It can never authorize or submit an unconfirmed real-money order.

## Canonical inputs

Watchtower consumes existing versioned objects:

- WP8 `PortfolioRiskAssessmentV1` for concentration, liquidity, data-quality and policy-compliance state;
- WP6 `CreditPassportV1` for rating actions and active default/restructuring/payment events;
- `MarketResearchBundleV1` for trusted corporate events;
- exact `PolicyReferenceV1` and portfolio snapshot identity.

The reducer does not independently calculate credit ratings, risk weights, concentration limits, liquidity thresholds or portfolio valuation.

## Deterministic reducer

`PortfolioWatchtowerV1` converts canonical evidence into semantic signal fingerprints. A fingerprint describes the condition rather than a transient delivery or observation hash. This gives three required properties:

1. repeated QStash delivery cannot duplicate an alert;
2. a persistent unchanged condition does not notify repeatedly;
3. after a condition disappears, the same condition may alert again if it later reappears.

The reducer keeps only current active fingerprints plus a bounded set of recent delivery IDs. The durable journal uses revisioned compare-and-swap semantics so concurrent deliveries cannot both commit the same transition.

## Signal families

Initial deterministic signal families are:

- rating downgrade / rating watch;
- active default, technical default, restructuring or payment delay;
- material corporate events (maturity, offer, amortization, delisting);
- current policy non-compliance or policy identity change;
- concentration breach/high-risk state;
- stale/unknown/high liquidity-risk state;
- data-quality degradation.

Severity reuses the existing safe observability taxonomy: `info`, `warning`, `error`. WP13 does not introduce a competing severity hierarchy.

## Notification rule

`should_notify` is true if and only if the evaluation emits at least one new material alert. A clean run or a deduplicated/replayed run is silent.

## Recommendation boundary

Watchtower output may request `review` or `recommendation`. A later WP13 slice may optionally invoke the existing deterministic decision/plan pipeline to produce a proposed immutable plan. Such a plan remains subject to WP11/WP12 owner-confirmation and execution gates.

Hard invariants:

- `execution_authorized=false`;
- `trading_methods=false`;
- no `TINVEST_TRADING_TOKEN` in Watchtower runtime;
- no direct broker mutation API;
- no autonomous recurring real execution.

## Scheduler boundary

Production scheduling stays in the existing `app:app` Gateway. QStash calls dedicated internal POST endpoints that are excluded from GPT OpenAPI. The endpoint verifies QStash signature evidence before reading or changing Watchtower state.

QStash configuration must use bounded retries and signed callbacks/failure callbacks. Application-level deduplication remains mandatory because delivery and callback retries can repeat.

## Durable state

Production requires Upstash-backed durable state. The Watchtower namespace is separate from real-trading and plan-execution namespaces. Records contain only safe fingerprints, schedule/delivery identifiers and versioned Watchtower state; raw broker holdings, account numbers, tokens and unredacted source payloads are not persisted by the Watchtower journal.

## Recovery and observability

Schedule configuration and Watchtower journal state are independently observable. Recovery is deterministic from:

1. GitHub configuration/documentation;
2. QStash schedule identity/configuration;
3. Upstash Watchtower state;
4. latest canonical read-only evidence.

A missing/corrupt durable state, invalid signature, stale binding or CAS conflict fails closed and does not create a notification, proposed plan or broker write.
