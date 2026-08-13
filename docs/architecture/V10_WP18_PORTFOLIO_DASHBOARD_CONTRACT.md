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

Every displayed financial or derived value must carry or visibly inherit a source and UTC `as_of`/retrieval/evaluation timestamp. Decimal quantities and money amounts are transported as decimal strings, never binary floats.

The dashboard exposes:

- broker-reported portfolio total;
- cash by currency with reported/available/blocked values; optional canonical cash components remain `null` when unknown rather than being converted to zero;
- normalized positions and quantities;
- broker current unit price and explicitly calculated `current_price × quantity_units` position value when both operands are available;
- same-currency position weights and Top-1/Top-5 concentration over the normalized broker-value subset;
- stable instrument identity, instrument type and class code;
- reviewed issuer/sector classification where exact T-Invest instrument/asset metadata supports it;
- snapshot freshness/completeness and unresolved position counts;
- current-market last quote metadata;
- current-market value only when conversion is semantically direct with the available metadata.

Cross-currency aggregation is forbidden unless an explicit reviewed FX conversion contract is later introduced.

### Current-on-demand refresh semantics

WP18 v1 is a bounded pull model, not a silent streaming/polling model:

1. opening `/portfolio` or `/assets` performs one current-on-demand READ snapshot;
2. the explicit **Обновить** action performs another snapshot;
3. there is no silent polling timer;
4. `generated_at`, broker `retrieved_at`, market quote `as_of` and freshness/stale state remain visible so an old snapshot is never described as continuously live.

This preserves broker rate-limit safety and keeps currentness explainable.

### Current-market conversion policy

T-Invest market quotations are not universally money values. Bonds, currencies and futures require asset-specific conversion metadata/formulas. WP18 therefore calculates current-market value directly only for shares and ETFs. For other asset classes it displays the last quote, timestamp and a visible `ASSET_SPECIFIC_CONVERSION_REQUIRED` state instead of inventing a monetary value.

Broker-reported valuation and current-market quotation/value are separate fields and must never silently replace one another.

## Issuer / sector enrichment

WP18 does not infer issuer or sector from ticker, display name or class code.

For a normalized position with a stable instrument UID, the connection-scoped READ adapter uses the canonical instrument type to select exactly one T-Invest point method:

- share → `ShareBy`;
- bond → `BondBy`;
- ETF → `EtfBy`;
- currency → `CurrencyBy`;
- future → `FutureBy`;
- option → `OptionBy`;
- structured product → `StructuredNoteBy`.

The request uses the exact instrument UID and the returned UID must match. Where the type-specific response supplies `asset_uid`, WP18 may call `GetAssetBy(asset_uid)` and use `AssetFull.brand.company` as issuer plus `AssetFull.brand.sector` as the preferred sector. The type-specific instrument `sector` field is retained as an authoritative sector fallback.

Futures/options are handled truthfully when no asset UID is exposed by the exact instrument response: the authoritative direct sector may be displayed, issuer remains unavailable, and the classification state is `PARTIAL`. Unsupported canonical classes are `UNAVAILABLE_ASSET_CLASS`. Missing mappings and point-read failures stay explicit rather than being replaced with guessed values.

No broad `GetAssets` list scan is used. No generic `GetInstrumentBy -> asset_uid` assumption is used. Ticker/name/display matching is forbidden. The enrichment method repeats the existing exact READ-account binding before any remote metadata call.

## Position detail and downstream links

Each normalized row has an expandable **Position detail** containing stable identity fields available from the accepted portfolio contract (`uid`, `position_uid`, FIGI, ISIN, class, type, currency).

WP18 does not synthesize research or incident links. The existing research binding contract only creates a target for an exact decision-ready shortlist candidate; WP18 has no accepted current-state research/incident index that can deterministically resolve arbitrary portfolio positions. The UI therefore marks these links unavailable rather than crossing into WP19/WP20 or fabricating associations.

## Incomplete and stale data

The product service uses the accepted WP15 adapter in partial mode so unresolved broker positions, broker loading state, stale snapshots, missing quotes, stale quotes and missing classification remain visible.

Rules:

1. Missing/unavailable data is never represented as zero.
2. An account read failure emits an explicit unavailable warning and no fabricated account values.
3. A market-data failure does not hide otherwise valid broker-reported values.
4. A classification failure does not hide the position and emits no inferred issuer/sector.
5. Any unresolved positions make the account/dashboard partial.
6. Empty broker configuration is a distinct `EMPTY` state.
7. Stale data remains displayed only with an explicit stale state and timestamp.

## UI routes

- `/portfolio` — portfolio-focused view.
- `/assets` — asset-focused rendering of the same reviewed product contract.

Both routes render inside the existing WP17 authenticated `ApplicationShell` and reuse WP16 design-system primitives.

## Required tests and evidence

Before WP18 can be accepted:

- Python tests cover empty, normal, partial, stale/unavailable, optional-unknown cash and secret-boundary behavior;
- dedicated adapter tests prove exact type-specific UID classification, point asset lookup, partial derivative sector behavior, unsupported-class handling, instrument/asset identity-conflict rejection and same-UID/type-conflict rejection;
- golden frontend fixtures cover normal, empty, partial and stale states without private values;
- Decimal and same-currency weighting calculations are deterministic;
- bond/other asset market quotes are not naively converted to monetary value;
- API tests prove authentication and session-derived tenant scope;
- Web contract tests prove Portfolio/Assets replace placeholders, source/timestamp/freshness/completeness are visible, and browser code contains no credential persistence surface;
- frontend typecheck/lint/test/build are GREEN;
- full authoritative Windows merge gate is GREEN on the exact PR head;
- WP15/WP16/WP17 regression gates remain GREEN;
- review threads are zero;
- full diff is reviewed;
- squash merge is followed by exact-main post-merge Regression Shield SUCCESS.

WP19 remains locked until all WP18 Exit Gate evidence is accepted.
