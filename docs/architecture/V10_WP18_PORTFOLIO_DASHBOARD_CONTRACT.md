# Omni-CIO V10 WP18 — Portfolio Dashboard Contract

Status: **IMPLEMENTATION / NOT YET ACCEPTED**

Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP18.

## Purpose

WP18 replaces the WP17 placeholders for **Портфель** and **Активы** with a read-only product view of the authenticated tenant's accepted broker data. It reuses the existing `apps/web` application, WP17 server-side session boundary, WP17 Broker Connections repository/vault and WP15 T-Invest READ adapters. It does not create a second Web application, persistence stack, queue, broker SDK surface or credential store.

## Security boundary

The browser may receive only product-safe data. The API MUST NOT return:

- T-Invest token material;
- `secret_ref` or vault path;
- raw provider broker account ID;
- broker account fingerprint;
- another tenant's connection, account, portfolio or session data;
- any broker WRITE/TRADE method or credential.

Tenant scope is resolved from the server-side session. The client does not submit a tenant identifier for portfolio reads. Responses use `Cache-Control: no-store`.

Global invariants remain:

- `app:app` unchanged;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded.

## Data semantics

Every displayed financial value must carry or inherit a visible source and UTC `as_of`/retrieval timestamp. Decimal quantities and money amounts are transported as decimal strings, never binary floats.

The dashboard exposes:

- broker-reported portfolio total;
- cash by currency with reported/available/blocked values;
- normalized positions and quantities;
- broker current unit price and explicitly calculated `current_price × quantity_units` position value when both operands are available;
- same-currency position weights and Top-1/Top-5 concentration over the normalized broker-value subset;
- instrument type and class code;
- snapshot freshness/completeness and unresolved position counts;
- current-market last quote metadata;
- current-market value only when conversion is semantically direct with the available metadata.

Cross-currency aggregation is forbidden unless an explicit reviewed FX conversion contract is later introduced.

### Current-market conversion policy

T-Invest market quotations are not universally money values. Bonds, currencies and futures require asset-specific conversion metadata/formulas. WP18 therefore calculates current-market value directly only for shares and ETFs. For other asset classes it displays the last quote, timestamp and a visible `ASSET_SPECIFIC_CONVERSION_REQUIRED` state instead of inventing a monetary value.

Broker-reported valuation and current-market quotation/value are separate fields and must never silently replace one another.

## Incomplete and stale data

The product service uses the accepted WP15 adapter in partial mode so unresolved broker positions, broker loading state, stale snapshots, missing quotes and stale quotes remain visible.

Rules:

1. Missing/unavailable data is never represented as zero.
2. An account read failure emits an explicit unavailable warning and no fabricated account values.
3. A market-data failure does not hide otherwise valid broker-reported values.
4. Any unresolved positions make the account/dashboard partial.
5. Empty broker configuration is a distinct `EMPTY` state.
6. Stale data remains displayed only with an explicit stale state and timestamp.

## UI routes

- `/portfolio` — portfolio-focused view.
- `/assets` — asset-focused rendering of the same reviewed product contract.

Both routes render inside the existing WP17 authenticated `ApplicationShell` and reuse WP16 design-system primitives.

## Sector metadata

The accepted WP15 canonical `InstrumentIdentity` currently carries instrument type and `class_code` but not sector. WP18 must not infer a sector from ticker/name/class code. Until a reviewed canonical sector enrichment source is added, the UI exposes `sector = null` with `sector_state = UNAVAILABLE_FROM_WP15_CANONICAL_IDENTITY` rather than fabricating classification.

This is an explicit completeness limitation, not a hidden omission. WP18 acceptance must either retain this visible limitation or introduce reviewed sector enrichment before claiming sector coverage.

## Required tests and evidence

Before WP18 can be accepted:

- Python tests cover empty, normal, partial, stale/unavailable and secret-boundary behavior;
- Decimal and same-currency weighting calculations are deterministic;
- bond/other asset market quotes are not naively converted to monetary value;
- API tests prove authentication and session-derived tenant scope;
- Web contract tests prove Portfolio/Assets replace placeholders, source/timestamp/freshness/completeness are visible, and browser code contains no credential persistence surface;
- frontend typecheck/lint/test/build are GREEN;
- full authoritative Windows merge gate is GREEN on the exact PR head;
- WP16/WP17 regression gates remain GREEN;
- review threads are zero;
- full diff is reviewed;
- squash merge is followed by exact-main post-merge Regression Shield SUCCESS.

WP19 remains locked until all WP18 Exit Gate evidence is accepted.
