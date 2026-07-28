# Market Research Contracts v1

## Purpose

PR-10 introduces a strict, immutable data boundary for market reference data,
quotes, liquidity, credit ratings, bond metrics and corporate events.

The package is offline and data-only. It does not fetch URLs, call T-Invest,
parse news, publish a FastAPI route or change the GPT Action schema.

## Contract structure

```text
MarketResearchBundleV1
├── MarketResearchMetadataV1
├── InstrumentReferenceV1
├── MarketQuoteV1
├── MarketLiquidityV1
├── CreditRatingV1[]
├── BondMetricsV1
├── CorporateEventV1[]
├── ComponentStateV1 for every component
└── trading_methods=false
```

Every source contains provider, authority, retrieval time and an optional source
record identifier. Component state is separate from component content so an
empty result can be distinguished from a source that was not checked.

## Authority model

The decision-readiness assessment accepts primary, official and regulated
sources for market facts. Secondary sources remain useful context but cannot by
themselves make a quote, rating, liquidity record or corporate-event check
decision-ready.

Ratings preserve:

- agency;
- agency-native rating string;
- issuer or issue scope;
- action type, including withdrawal;
- action timestamp;
- outlook and previous rating when available;
- source and retrieval timestamp.

Issuer and issue ratings are not interchangeable. A bond requires both current
scopes for decision readiness. PR-10 does not attempt to compare agency scales;
that requires a separately reviewed methodology.

## Freshness

Freshness is assessed using the timestamp of the underlying value where one
exists:

- quote: `quote.as_of`;
- liquidity: `liquidity.as_of`;
- bond metrics: `bond_metrics.as_of`.

Reference data, ratings and events use their explicit component check time. A
recent HTTP response cannot make an old quote fresh.

Default limits:

- quote and liquidity: 5 minutes;
- ratings, events and bond metrics checks: 24 hours;
- reference data: 30 days;
- future timestamp tolerance: 60 seconds.

All values are configurable through `MarketFreshnessPolicyV1`.

## Liquidity arithmetic

`MarketLiquidityV1` uses exact `Decimal` arithmetic:

```text
spread_absolute = best_ask - best_bid
midpoint = (best_ask + best_bid) / 2
spread_bps = spread_absolute / midpoint * 10_000
```

A bid above ask, non-finite value or inconsistent spread fails validation.
Depth and 24-hour turnover remain optional because source coverage differs.
Absence of those optional fields must not be silently converted into a positive
liquidity conclusion.

## Corporate events

Corporate events are structured records with separate announcement and event
timestamps. An empty event list is accepted only when `events_state=ok`, the
source is trusted and the check timestamp is fresh. This distinguishes “no
known events” from “events were not checked”.

Raw HTML, PDF content, arbitrary external instructions and executable code are
outside PR-10. They remain untrusted inputs for PR-11.

## Assessment states

- `ready`: required components are present, fresh and trusted;
- `partial`: required data is missing, degraded, stale or future-dated;
- `rejected`: at least one required fact relies on a secondary/untrusted source.

Required for all instruments:

- reference;
- quote;
- liquidity;
- a fresh corporate-event check.

Additionally required for bonds:

- current issuer rating;
- current issue rating;
- fresh bond metrics including maturity and duration.

## Compatibility and safety

PR-10 does not change:

- public FastAPI routes or methods;
- OpenAPI operation IDs or response schemas;
- broker SDK permissions or calls;
- `trading_methods=false`;
- Gateway version `3.9.1`;
- Render entrypoint `app:app`.

The bundle itself requires `trading_methods=false` and rejects identity or
currency mismatch between components.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
