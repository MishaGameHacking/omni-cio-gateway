# NCR issuer rating action source v1

## Purpose

PR-104 adds one independent fixed-source parser and transport boundary for
issuer-level rating actions published by LLC National Credit Ratings (NCR). It
does not create a generic credit-rating-agency adapter, compare agency scales or
merge NCR subjects with ACRA or Expert RA identities.

## External verification basis

The source boundary was selected only after current external verification:

- the Bank of Russia lists LLC NCR in the register of Russian credit rating
  agencies;
- the official NCR press-release page exposes a `Название | Сектор | Дата |
  Скачать` list containing issuer and issue actions together;
- current issuer examples cover assignment, affirmation, upgrade, downgrade,
  withdrawal, stable/positive/negative/uncertain outlook wording and a bounded
  rating-under-review phrase;
- official release identities use
  `https://ratings.ru/ratings/press-releases/{slug}-RA-DDMMYY/`;
- the official national-Russia scale runs from `AAA.ru` through `C.ru`, plus
  `D`, while expected ratings use a separate `e` prefix;
- the source terms limit site information to informational use and prohibit
  reproduction or distribution without prior written permission.

No external HTML, title or release body is stored in the repository. Registry,
page structure, source terms and scale semantics must be re-verified before any
production binding.

## Fixed identity

- endpoint: exactly `https://ratings.ru/ratings/press-releases/`;
- provider: `NCR`;
- source id: `NCR.press_releases.issuer_rating_actions`;
- accepted release hosts: only `ratings.ru` and the fixed `www.ratings.ru`
  alias;
- canonical stored host: always `ratings.ru`;
- release path: exactly
  `/ratings/press-releases/{ASCII slug}-RA-DDMMYY/`;
- source language: Russian;
- query strings, fragments, arbitrary paths, redirects, caller-selected URLs
  and secondary domains are rejected.

The date encoded in the release URL must be calendar-valid and exactly equal
the visible publication date associated with the action. The fixed `www` alias
and case-insensitive `RA` token are canonicalized without allowing dynamic host
selection.

## Page and date boundary

The parser requires the exact visible list headers `Название`, `Сектор` and
`Дата` near the beginning of the extraction scope. A page without this schema
fails closed.

Each supported action must be an anchor with an allowlisted canonical release
identity. Its publication date must appear within the bounded remainder of the
same row, before any different release anchor. A date linked to another release,
a missing date, an invalid calendar date, a URL/date disagreement or a date
materially after retrieval fails closed.

Anchor state is independent of the `href` value. Nested, unclosed or mismatched
anchors and script/style/noscript state are invalid HTML. Script, style and
noscript content is ignored and can never create an action, date or list header.

## Supported records

V1 accepts singular issuer-level actions only:

- assigned;
- affirmed;
- upgraded;
- downgraded;
- withdrawn.

The closed rating allowlist is the NCR national-Russia scale:

`AAA.ru`, `AA+.ru`, `AA.ru`, `AA-.ru`, `A+.ru`, `A.ru`, `A-.ru`,
`BBB+.ru`, `BBB.ru`, `BBB-.ru`, `BB+.ru`, `BB.ru`, `BB-.ru`,
`B+.ru`, `B.ru`, `B-.ru`, `CCC.ru`, `CC.ru`, `C.ru` and `D`.

Visually confusable Cyrillic and Latin A/B/C/D/R/U glyphs are normalized only
inside the bounded rating token, then checked against the closed allowlist.
Expected `e...` ratings, international-scale values and values from another
agency are rejected.

Stable, positive, negative and developing outlooks are accepted only through
explicit NCR title grammar. NCR `неопределённый` wording and the bounded
`рейтинг на пересмотре...` phrase map to the shared `under_revision` value. Any
unknown non-empty suffix on an otherwise supported title fails closed.

A withdrawn issuer action may include only the bounded official forms
`и прогноз по нему`, `без подтверждения` and `в связи с ...`. It carries no
rating or outlook in the contract.

## Unsupported scope

The parser skips:

- bond, emission, series, tranche and other issue-level actions;
- plural or multi-object issuer/issue actions;
- expected ratings with the `e` prefix;
- standalone outlook changes without one of the five supported rating actions;
- ESG, international-scale and non-credit publications;
- titles outside the explicit NCR action grammar.

A title that clearly claims a singular supported issuer action but contains a
malformed rating, outlook or identity fails closed rather than disappearing.

## Transport and parsing controls

- fixed HTTPS GET only;
- always-owned isolated `httpx.Client`;
- dependency injection is transport-only via `httpx.BaseTransport`;
- no caller-provided client, inherited auth, cookies, headers or hooks;
- `trust_env=false`, `auth=None` and redirects disabled;
- explicit allowlisted `Accept` and `User-Agent` headers;
- caller controls may only reduce the ten-second timeout and two-megabyte byte
  budget;
- booleans, non-finite values, non-positive values and expanded budgets fail
  before I/O;
- HTML/XHTML content types and UTF-8/UTF-8-BOM only;
- declared and streamed response-size enforcement;
- exact list headers and bounded action/date association;
- canonical release identity and URL/publication-date equality;
- duplicate URL conflicts fail closed;
- output is bounded to 30 supported records and sorted newest first;
- upstream body, exception and redirect text is never retained in unavailable
  results.

Source text is data only. External instructions are never executed.

## Contract boundary

`NcrIssuerRatingActionV1` and `NcrIssuerRatingActionsSnapshotV1` are separate
from the ACRA and Expert RA models. They are exported through both the direct
module and `omni_cio.contracts.v1` and permanently declare:

- fixed official source and issuer-only scope;
- unresolved source-text subject identity requiring a separate resolver;
- agency-specific scale only and no cross-agency merge;
- informational use only;
- redistribution not authorized by this software contract;
- not an investment recommendation;
- no raw title or HTML storage;
- no credentials or full account identity;
- no broker write, trade authorization or order creation;
- `trading_methods=false`.

Direct Pydantic construction enforces the same core semantics as the parser:

- exact agency, legal name, source provider/id and official authority;
- rating inside the fixed NCR national-Russia allowlist;
- no rating or outlook on withdrawal;
- rating required for every non-withdrawal action;
- calendar-valid canonical URL with exact publication-date equality;
- publication not materially after source retrieval;
- available snapshot/source timestamp equality;
- exact shared source for every record;
- unique release URLs, maximum 30 records and newest-first order.

These conservative flags do not replace source-site terms or legal review.

## Non-goals

PR-104 adds no:

- cache or stale-data policy;
- observability, alert or evidence lifecycle;
- generic agency mapper or cross-agency comparison;
- subject/entity resolution;
- route, GPT Action or public response field;
- frontend component;
- startup/background fetch;
- database or persistent external-content copy;
- external notification transport;
- broker call or execution method.

`app:app`, exactly 14 GET Actions and the existing read-only OpenAPI remain
unchanged.

## Tests

Tests cover direct contracts, the five actions, the closed rating scale,
confusable glyphs, outlook grammar, withdrawal forms, issuer-only filtering,
expected and issue-level exclusions, malformed supported titles, exact list
headers, bounded action/date adjacency, release URL confinement and
canonicalization, calendar and URL/date identity, duplicate conflicts,
deterministic ordering and bounds, invalid/truncated HTML, script exclusion,
fixed isolated transport, request allowlisting, redirect blocking, bounded
controls, content type and byte limits, redacted failures, stable exports and
absence of route/startup/write surfaces.

## Next package

Only after PR-104 passes Regression Shield on its exact final head and
squash-merges may a separate reviewed package add an NCR cache. It must preserve
fixed source identity, retrieval/publication separation, single-flight refresh,
explicit fresh/stale/unavailable states and no startup fetch.
