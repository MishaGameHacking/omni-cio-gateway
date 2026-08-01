# Expert RA issuer rating action source v1

## Purpose

PR-99 adds one separate, fixed-source parser and transport boundary for
issuer-level rating actions published by AO Expert RA. It does not create a
generic credit-rating-agency adapter and does not compare Expert RA ratings with
ACRA ratings.

## External verification basis

The source was selected only after current external verification:

- Bank of Russia decisions identify AO `Expert RA` and its Russian national
  scale using `ru...` values;
- the official Russian site publishes a dedicated `Рейтинговые действия` block;
- current homepage markup exposes action/date pairs and ends that block with a
  canonical linked `Аналитика` heading at `/researches/`;
- official release identities use stable
  `https://raexpert.ru/releases/{year}/{slug}` paths;
- current official examples include issuer actions, unsupported bond actions,
  developing outlooks and a withdrawal combined with removal of `под наблюдением`;
- the source site states that rating information is informational and is not an
  investment recommendation.

The repository does not store copies of external pages. Live registry/source
status and source-site terms must be re-verified before production binding.

## Fixed identity

- endpoint: exactly `https://raexpert.ru/`;
- provider: `Expert RA`;
- source id: `EXPERT_RA.home.rating_actions`;
- accepted release hosts: only `raexpert.ru` and its fixed `www.raexpert.ru`
  alias;
- canonical stored host: always `raexpert.ru`;
- release path: exactly `/releases/{20xx}/{jan..dec}{valid day}[a-z]?`;
- source language: Russian;
- redirects, caller-controlled URLs and secondary domains are not allowed.

`en.raexpert.ru`, query strings, fragments, unknown three-letter month tokens,
calendar-invalid dates and arbitrary paths are rejected at the release-URL
boundary. The fixed `www` alias is never selected dynamically and cannot change
the endpoint.

## Page-scope boundary

The HTML parser opens the extraction scope only on a plain visible
`Рейтинговые действия` heading. A navigation link with the same label cannot open
the scope.

Anchor state is tracked separately from the `href` value. Therefore an `<a>`
element without `href`, or with a blank `href`, remains a link event and cannot
impersonate plain heading text.

The scope ends only on:

- a plain visible `Аналитика` heading; or
- the exact official internal `https://raexpert.ru/researches/` identity,
  including the fixed `www` host alias.

External hosts, other paths, query strings, fragments and no-`href` anchors
cannot terminate the scope. This matches the current live homepage while
preserving fail-closed identity controls.

A publication date may be plain visible text or a separate link to the same
official release. The date must be the immediately following visible event after
its action. The parser does not scan ahead across unrelated text. Every linked
date is canonicalized under the same release URL rules as its action and must
resolve to the exact same release. External, blank, different-release or
non-adjacent date events fail closed. Missing, invalid or materially future dates
also fail closed. The calendar date encoded in the canonical release URL must
exactly equal `published_on`.

## Supported records

V1 accepts singular issuer-level actions only:

- assigned;
- affirmed;
- upgraded;
- downgraded;
- withdrawn.

Supported rating values are the agency-specific Russian national scale from
`ruAAA` through `ruD`, including modifiers. Visually mixed Cyrillic and Latin
A/B/C/R/D glyphs are normalized only inside the rating token and then checked
against the closed allowlist.

Stable, positive, negative and developing outlook wording may be captured only
when it matches the explicit title grammar. `Под наблюдением` is modeled only as
a bounded source-title status suffix, not as a `CreditRatingOutlook` value.
Direct contract construction therefore rejects the shared enum value
`under_revision` for Expert RA v1. A non-empty unknown title suffix does not
disappear silently; it fails with a typed outlook/schema error.

A withdrawn action may use the exact official bounded suffix
`и снял статус «под наблюдением»`. This suffix is not stored as issuer identity,
rating or outlook. Withdrawal subject text containing residual control markers
such as an unconsumed `статус` or `прогноз` fails closed instead of being stored
inside `subject_name`.

## Unsupported scope

The parser skips:

- bond and other issue-level actions;
- series, tranches and structured-finance instruments;
- ESG and other non-credit ratings;
- plural or multi-object actions;
- complex `пересмотрел и присвоил` titles that cannot be mapped without prior
  rating evidence;
- international scales;
- standalone watch-status publications that do not contain one of the five
  supported rating actions;
- publications without a supported rating action.

A title that clearly claims a singular supported issuer national-Russia action
but no longer matches the allowlisted grammar fails closed.

## Transport and parsing controls

- fixed HTTPS GET only;
- always-owned isolated `httpx.Client`;
- dependency injection is transport-only via `httpx.BaseTransport`;
- no shared client, inherited auth, cookies, headers or request hooks;
- `trust_env=false` and redirects disabled;
- explicit allowlisted `Accept` and `User-Agent` headers;
- caller controls may only reduce the default timeout and response-byte budget;
- `NaN`, infinities, huge values and expanded budgets are rejected before I/O;
- HTML/XHTML content types only;
- streamed byte limit with declared and actual size checks;
- UTF-8/UTF-8-BOM only;
- script, style and noscript content ignored;
- unclosed or mismatched anchor/script/style/noscript state fails as invalid HTML;
- exact page-section markers required;
- linked dates must use the exact action release identity;
- publication date must be immediately adjacent, valid and not materially in the
  future;
- release URL month/day must be calendar-valid before canonicalization and match
  `published_on`;
- release URL conflicts fail closed;
- response records are bounded and sorted newest first;
- network/body/exception text is not retained in unavailable results.

Source text is treated strictly as data. No instructions from external HTML are
executed.

## Contract boundary

`ExpertRaIssuerRatingActionV1` and
`ExpertRaIssuerRatingActionsSnapshotV1` are separate from ACRA models. They are
exported through both the direct module and `omni_cio.contracts.v1` and permanently
declare:

- fixed official source and issuer-only scope;
- agency-specific scale only;
- informational use only;
- redistribution not authorized by this software contract;
- not an investment recommendation;
- no raw title or HTML storage;
- no credentials or full account identity;
- no broker write, trade authorization or order creation;
- `trading_methods=false`.

Direct Pydantic construction enforces the same supported semantics as the parser:

- rating must be inside the fixed Expert RA national-Russia allowlist;
- outlook may be only stable, positive, negative, developing or absent;
- publication cannot exceed the one-day source-retrieval tolerance;
- URL month/day must be calendar-valid;
- URL date and publication date must match exactly;
- available snapshot `retrieved_at` must equal `source.retrieved_at`;
- every record must share the exact snapshot source;
- available snapshot records are bounded and already sorted newest first.

These flags are conservative software controls and do not replace source-site
terms or legal review.

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

`app:app`, 14 GET Actions total (13 authenticated and public `/health`) and the
existing read-only OpenAPI remain unchanged.

## Tests

Tests cover contracts, five action types, rating-glyph normalization, exact
direct outlook grammar, bounded withdrawal/watch-status suffixes, issuer-only
filtering, malformed supported titles, live linked section boundary, exact
action/date adjacency, no-`href` anchor isolation, spoofed boundary rejection,
URL confinement, explicit month allowlisting, calendar-valid release identity,
URL/publication-date matching, exact linked-date release identity,
source/snapshot retrieval timestamp matching, snapshot bounds/order, duplicate
conflicts, script exclusion, truncated/mismatched HTML, isolated transport,
finite/non-expansive controls, fixed endpoint, content type/size, network failure
redaction, versioned exports and absence of generic URL, startup, route and
broker-write surfaces.

## Validation continuity

Regression Shield run #781 on the frozen PR-99 candidate reached the complete
repository test suite. Security, lock consistency, repository layout, compile,
Ruff, formatting, mypy, stable `app:app`, the 14-GET read-only contract and the
coverage threshold all passed. The only failure was an existing ACRA lifecycle
test that created evidence under a fixed 2026-07-31 clock and later read it
without passing the same deterministic clock, so normal retention pruning used
the actual 2026-08-01 time.

The test-only clock correction was isolated in GitHub PR #131 and squash-merged
to `main` after Regression Shield run #782 passed both blocking jobs on its exact
head. Production ACRA retention/pruning behavior was not changed. Because the
base branch changed, PR-99 still requires a new complete Regression Shield on a
new exact head against the updated `main`; run #781 is diagnostic evidence but
is not final merge evidence.

## Next package

A separate reviewed package may add a one-entry bounded fresh/stale/unavailable
cache for typed PR-99 snapshots. It must preserve retrieval-date versus
publication-date separation, single-flight refresh, no silent stale exposure and
no startup fetch.
