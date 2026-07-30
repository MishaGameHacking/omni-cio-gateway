# ACRA issuer rating action observability v1

## Purpose

PR-96 maps typed PR-94 source snapshots and PR-95 cache results to the existing
immutable `ObservabilityEventV1` contract. Builders are pure and return one
allowlisted event; they do not fetch, refresh, log, emit, alert or schedule work.

## Event boundary

Source event:

- name `market.acra_rating_actions.source`;
- component `market.acra_rating_actions_source`;
- provider `ACRA`;
- operation `press_releases.issuer_rating_actions`;
- available/unavailable status and optional validated latency;
- safe record count and fixed-source/issuer-scope boolean metrics.

Cache event:

- name `market.acra_rating_actions.cache`;
- component `market.acra_rating_actions_cache`;
- fresh/stale/unavailable freshness;
- cache hit, refresh attempted/succeeded, stale available/exposed and display
  allowed metrics;
- safe record count only when a typed snapshot is present;
- fixed source/cache error code when degraded or unavailable.

A cache hit with no source call records `external_call.status=not_called` and does
not attach external latency. A successful refresh records external success. A
failed force refresh with still-fresh cached data is degraded/warning while
freshness remains fresh. Explicit stale exposure is degraded/warning. An
unavailable result is failure/error.

## Prohibited payload

Events cannot include:

- issuer or subject name;
- rating, rating scale or outlook;
- action type;
- release URL or release id;
- publication date or record content;
- source raw HTML or title text;
- account, position, portfolio or broker payload;
- credential, cookie or Authorization data;
- upstream body, exception type/text or traceback;
- free-form external instructions.

The existing event contract fixes `contains_sensitive_payload=false` and
`trading_methods=false`. Account remains `None`.

## Metrics

Only bounded integer/boolean metrics are used:

- `acra.record_count`;
- `acra.source_available`;
- `acra.cache_hit`;
- `acra.refresh_attempted`;
- `acra.refresh_succeeded`;
- `acra.stale_available`;
- `acra.stale_exposed`;
- `acra.display_allowed`;
- `acra.fixed_official_source`;
- `acra.issuer_scope_only`.

No issuer count by name, rating value, rating transition or financial threshold
is emitted.

## Validation

Builders require exact typed PR-94/95 models and finite non-negative Decimal
latency. Wrong types and invalid duration fail before event construction. Error
codes are copied only from fixed source/cache enums.

## Startup and API behavior

PR-96 adds no:

- automatic event emission or logger call;
- alert policy, webhook, email, Telegram or pager transport;
- source/cache call at import or startup;
- FastAPI route, operationId, GPT Action or response field;
- frontend/dashboard field;
- dependency, database, secret or Render migration;
- T-Invest call or broker write method.

`app:app`, exactly 14 authenticated GET Actions and `trading_methods=false`
remain unchanged.

## Tests

Focused tests cover:

- available/unavailable source mapping;
- cache hit, successful refresh and failed force-refresh mapping;
- explicit stale and unavailable mapping;
- safe metric sets and latency semantics;
- serialized exclusion of issuer, rating, outlook, URL, publication date and raw
  HTML fields;
- wrong-type and invalid-duration guards;
- package exports and absence of route/startup/emission/write surface.

## Next step

A later package may build a bounded global operational alert policy over these
canonical events. It must not create per-issuer or per-rating semantics because
PR-96 events intentionally omit issuer identity and rating content. Production
binding remains blocked until the exact existing caller/owner is identified.
