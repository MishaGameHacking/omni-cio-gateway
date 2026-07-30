# CBR key-rate cache lifecycle v1

## Purpose

PR-85 adds a bounded process-local cache and freshness boundary over the trusted
PR-84 Bank of Russia key-rate source. It prevents repeated upstream calls and,
more importantly, makes fresh, stale and unavailable behavior explicit.

The package is internal-only. It does not add a FastAPI route, GPT Action,
request body or frontend component.

## Exact identity

A cache entry is keyed only by the exact requested date range:

```text
(requested_from, requested_to)
```

Data from one range cannot satisfy another range. Returned source snapshots must
match the requested range exactly.

## Status contract

`CbrKeyRateCacheResultV1` has three statuses:

- `fresh` — the value is inside the fresh TTL and may be displayed;
- `stale` — the fresh TTL expired, refresh failed and a stale value is exposed
  only because the trusted caller explicitly enabled `allow_stale`;
- `unavailable` — no displayable value is returned.

The result records retrieval age, fresh/stale deadlines, cache/source error
codes, whether refresh was attempted/succeeded, whether data came from cache,
and whether display is allowed.

Stale data is never silently presented as current. `stale_value_exposed=true`
requires `stale_available=true`, an explicit stale status and a failed refresh.

## Default lifecycle

- fresh TTL: 3600 seconds;
- stale retention: 86400 seconds;
- capacity: 16 exact ranges;
- source-future tolerance: 30 seconds.

All values are bounded by constructor validation. Fully expired entries are
removed before lookup and are never returned, even when `allow_stale=true`.
Oldest entries are evicted when capacity is exceeded. Process restart or
`clear()` removes the cache.

## Refresh behavior

- the loader is not called during construction/startup;
- a missing entry triggers one refresh;
- a fresh entry is returned without a refresh;
- `force_refresh=true` attempts a refresh;
- a successful refresh atomically replaces the entry;
- if forced refresh fails while the previous value is still fresh, the result
  remains `fresh`, explicitly served from cache, and includes a safe refresh
  error;
- after the fresh TTL, a failed refresh returns stale data only with
  `allow_stale=true`;
- without that opt-in, stale availability is reported but no snapshot/display
  value is returned;
- source exceptions, wrong types, range mismatch, future timestamps and source
  unavailable results fail closed with fixed error codes.

## Single-flight and concurrency

A process-local re-entrant lock protects lookup, refresh, publication, pruning
and eviction. Concurrent requests for the same empty range perform one loader
call; later callers receive the published fresh entry. This intentionally
serializes the low-frequency macro refresh path to prevent a source stampede.

## Privacy and safety

- only typed PR-84 snapshots are cached;
- raw XML, fault text and exception text are not retained;
- credentials, full account IDs and brokerage payloads are absent;
- no T-Invest or broker write method is introduced;
- `app:app` is unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- `trading_methods=false`.

## Frontend and owner boundary

Repository search did not find a registered existing frontend/dashboard owner
for the key-rate field. PR-85 therefore does not invent a new UI or silently
change an existing response.

A later package must first identify the real existing frontend or exact internal
owner, then bind this result with explicit presentation rules:

- `fresh`: display value plus effective/retrieved timestamps;
- `stale`: visibly mark stale and show age only when policy explicitly permits;
- `unavailable`: display no numeric value and a safe unavailable state;
- never combine the macro timestamp with broker-account or market-price
  timestamps;
- version and accept any public contract change separately.

## Tests

Focused tests cover lazy startup, first refresh, cache hit, successful and failed
forced refresh, explicit stale opt-in, expired pruning, unavailable source,
wrong type/range/future data, old source data, capacity eviction, concurrent
single-flight behavior, restart/clear, input guards, contract rejection of
silent stale display and absence of route/write surfaces.

## Rollback

Revert the PR-85 squash commit. No database, secret, dependency, OpenAPI or
Render migration is required.
