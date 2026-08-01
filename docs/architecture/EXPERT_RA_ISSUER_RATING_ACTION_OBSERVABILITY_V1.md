# Expert RA issuer rating-action observability v1

## Purpose

PR-101 adds pure privacy-safe observability builders over the typed PR-99 source
and PR-100 cache. It converts only bounded operational state and counts into the
existing `ObservabilityEventV1` allowlist. It does not expose rating-action
content, emit externally, register a route or authorize trading.

## Inputs

The builders accept only:

- `ExpertRaIssuerRatingActionsSnapshotV1` from the fixed official source;
- `ExpertRaIssuerRatingActionsCacheResultV1` from the one-entry cache;
- optional finite non-negative duration;
- optional timezone-aware event timestamp;
- optional opaque correlation id in the exact format produced by
  `new_trace_id("corr")`.

Source and cache models are serialized with Pydantic warnings treated as errors
and fully revalidated before any telemetry state is derived. Validator-bypassed
or forged Literal/privacy/trading state therefore fails closed with a fixed
observability error and is never converted to telemetry.

## Allowed event content

The source event may contain only:

- fixed provider `Expert RA`;
- fixed operation `home.rating_actions`;
- source available/failure status;
- fixed source/cache error code when present;
- call duration;
- record count;
- fixed official-source flag;
- issuer-scope flag;
- identity-resolution-required flag;
- cross-agency-identity-merged flag, expected to remain false.

The cache event may additionally contain only:

- fresh/stale/unavailable-derived outcome and freshness state;
- cache hit;
- refresh attempted/succeeded;
- stale physically available/exposed;
- display allowed;
- record count when a typed snapshot is actually exposed.

No age, TTL boundary or publication timestamp is needed in the event payload.

## Forbidden content

Telemetry must never contain:

- issuer/subject name or source-title text;
- rating, rating scale or outlook;
- action kind;
- release URL or release identity;
- publication date;
- raw title, raw HTML or upstream response body;
- arbitrary upstream exception type/text or traceback;
- account, portfolio, position, price, cash or broker payload;
- credential, cookie, Authorization header or token;
- request body or caller-selected source URL;
- investment recommendation or trade authorization.

`account`, `request_id`, `action_id` and `exception_type` are not populated by
these builders. `contains_sensitive_payload=false` and `trading_methods=false`
remain enforced by the generic observability contract.

## Opaque correlation boundary

PR-101 is stricter than the older agency telemetry packages. A caller cannot
supply an arbitrary free-form correlation string because that could accidentally
carry issuer or account text.

An optional supplied correlation id must match the exact opaque entropy shape of
`new_trace_id("corr")`: `corr:` plus 32 characters from `a` through `p`.
Otherwise the builder fails closed. When omitted, the existing safe-event builder
generates a fresh opaque id automatically.

## State mapping

### Source

- available -> success/info, external call success, freshness fresh;
- unavailable -> failure/error, external call failure, freshness unknown, fixed
  source error code required by the source contract.

### Cache

- fresh cache hit without refresh -> success/info, external call not called;
- successful refresh -> success/info, external call success;
- failed refresh while a still-fresh cache entry is served -> degraded/warning;
- stale explicitly exposed after failed refresh -> degraded/warning, freshness stale;
- unavailable -> failure/error with fixed source/cache error code.

No alert threshold, financial threshold or outbound notification is introduced.

## Purity and lifecycle

The module is a pure builder layer:

- no import/startup network call;
- no background task or scheduler;
- no global mutable state;
- no logger emission helper;
- no webhook, email, Telegram or pager transport;
- no disk/database retention;
- no FastAPI app/router/route;
- no T-Invest import or broker write call.

The caller owns whether a returned `ObservabilityEventV1` is later emitted by an
already approved generic sink. PR-101 itself does not emit it.

## Compatibility

PR-101 preserves:

- production entrypoint `app:app`;
- exactly 14 read-only GET Actions;
- existing OpenAPI and Render behavior;
- `trading_methods=false`;
- separate Expert RA and ACRA source/cache identities;
- unresolved Expert RA subject identity; no cross-agency merge.

## Tests

Focused tests cover:

- available and unavailable source mapping;
- fresh hit, successful refresh, degraded fresh fallback, stale and unavailable
  cache mapping;
- exact allowlisted count metrics;
- serialized-event absence of issuer, rating, outlook, action, release URL,
  publication date and raw HTML markers;
- absence of account/request/action/exception payload;
- negative/NaN duration rejection;
- free-form correlation id rejection and safe automatic opaque trace generation;
- validator-bypassed source/cache model rejection;
- stable package exports;
- absence of route/startup/emitter/outbound/write surfaces.

## Next step

Only after PR-101 passes Regression Shield on its exact head and squash-merges may
a separate PR-102 define a bounded global Expert RA operational alert policy over
these privacy-safe events. Such a policy must remain global-only, contain no
issuer/rating/action identity or financial threshold, and add no outbound
transport.
