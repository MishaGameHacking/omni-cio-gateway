# Expert RA issuer rating action source v1

## Purpose

PR-99 adds one separate, fixed-source parser and transport boundary for
issuer-level rating actions published by AO Expert RA. It does not create a
generic credit-rating-agency adapter and does not compare Expert RA ratings with
ACRA ratings.

## External verification basis

The source was selected only after current external verification:

- the Bank of Russia infrastructure register publishes the current credit rating
  agency registry;
- the Bank of Russia decision dated 7 July 2026 explicitly identifies AO
  `Expert RA` and its Russian national scale using `ru...` values;
- the official Russian site publishes rating-action links under stable
  `https://raexpert.ru/releases/{year}/{slug}` identities;
- official examples cover assigned, affirmed, upgraded, downgraded and withdrawn
  issuer actions.

The repository does not store copies of the external pages. Live registry/source
status must be re-verified before future production binding.

## Fixed identity

- endpoint: `https://raexpert.ru/`;
- provider: `Expert RA`;
- source id: `EXPERT_RA.home.rating_actions`;
- release host: exactly `raexpert.ru`;
- release path: exactly `/releases/{20xx}/{monDD[a-z]?}`;
- source language: Russian;
- redirects, caller-controlled URLs and secondary hosts are not allowed.

`www.raexpert.ru`, `en.raexpert.ru`, query strings, fragments and arbitrary paths
are rejected rather than silently canonicalized.

## Supported records

V1 accepts singular issuer-level actions only:

- assigned;
- affirmed;
- upgraded;
- downgraded;
- withdrawn.

Supported rating values are the agency-specific Russian national scale from
`ruAAA` through `ruD`, including allowed modifiers. Visually mixed Cyrillic and
Latin A/B/C glyphs are normalized only inside the rating token and then checked
against the closed allowlist.

Stable, positive, negative and developing outlook wording may be captured when
it is explicitly present in the title. The parser does not infer outlook from a
rating or from another agency.

## Unsupported scope

The parser skips:

- bond and other issue-level actions;
- series, tranches and structured-finance instruments;
- ESG and other non-credit ratings;
- plural/multi-object rating actions;
- international scales;
- publications without a supported rating action.

A title that clearly claims a singular supported issuer credit-rating action but
no longer matches the allowlisted grammar fails closed with a typed schema
error.

## Transport and parsing controls

- fixed HTTPS GET only;
- redirects disabled for the owned client;
- HTML/XHTML content types only;
- streamed byte limit with declared and actual size checks;
- UTF-8/UTF-8-BOM only;
- script, style and noscript content ignored;
- publication date must be adjacent, valid and not materially in the future;
- release URL conflicts fail closed;
- response records are bounded and sorted newest first;
- network/body/exception text is not retained in unavailable results.

Source text is treated strictly as data. No instructions from external HTML are
executed.

## Contract boundary

`ExpertRaIssuerRatingActionV1` and
`ExpertRaIssuerRatingActionsSnapshotV1` are separate from ACRA models. They
permanently declare:

- fixed official source and issuer-only scope;
- agency-specific scale only;
- informational use only;
- redistribution not authorized by this software contract;
- not an investment recommendation;
- no raw title or HTML storage;
- no credentials or full account identity;
- no broker write, trade authorization or order creation;
- `trading_methods=false`.

These flags are conservative software controls and do not replace the source
site's terms or legal review.

## Non-goals

PR-99 adds no:

- cache or stale-data policy;
- observability, alert or evidence lifecycle;
- route, GPT Action or public response field;
- frontend component;
- startup/background fetch;
- database or persistent source copy;
- external notification transport;
- broker call or execution method.

`app:app`, exactly 14 GET Actions total and the existing read-only OpenAPI remain
unchanged.

## Tests

Tests cover contracts, five action types, rating-glyph normalization, outlooks,
issuer-only filtering, malformed supported titles, URL confinement, date checks,
duplicate conflicts, script exclusion, fixed endpoint use, content type/size,
network failure redaction, invalid controls, exports and absence of generic URL,
startup, route and broker-write surfaces.

## Next package

A separate reviewed package may add a one-entry bounded fresh/stale/unavailable
cache for typed PR-99 snapshots. It must preserve retrieval-date versus
publication-date separation, single-flight refresh, no silent stale exposure and
no startup fetch.
