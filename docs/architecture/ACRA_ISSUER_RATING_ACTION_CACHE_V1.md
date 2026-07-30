# ACRA issuer rating action cache v1

## Purpose

PR-95 adds one bounded process-local cache over the typed PR-94 ACRA source. It
reduces repeated retrieval while preserving explicit freshness and fail-closed
behavior. It is not a route, database, scheduler, recommendation engine or
trading permission.

## Fixed identity and capacity

The source identity is immutable:

- provider `ACRA`;
- source id `ACRA.press_releases.issuer_rating_actions`;
- issuer-level Russian national-scale actions only;
- one fixed source snapshot in one process-local entry.

Capacity is structurally one because callers cannot select an agency, URL,
language, rating scale or query range. A later agency requires its own reviewed
source and cache boundary.

## Two time concepts

PR-95 keeps retrieval freshness separate from source publication evidence.

- `snapshot.retrieved_at` controls cache fresh/stale TTL;
- each `record.published_on` remains the action's official publication date;
- a new HTTP retrieval does not rewrite or refresh a record publication date;
- no inferred event time is created from the cache check timestamp.

Defaults:

- fresh TTL: 900 seconds;
- stale retention: 86400 seconds;
- future timestamp tolerance: 30 seconds;
- capacity: one typed source snapshot.

## Explicit states

`AcraIssuerRatingActionsCacheResultV1` supports exactly:

- `fresh` — typed records may be displayed;
- `stale` — records may be displayed only after a failed refresh and explicit
  trusted `allow_stale=true`;
- `unavailable` — no records are returned for display.

The result always states:

- check time and retrieval age;
- fresh and stale boundaries when an entry is relevant;
- whether it came from cache;
- whether refresh was attempted and succeeded;
- whether stale records physically exist and whether they were exposed;
- fixed source/cache error codes;
- whether display is allowed.

## No-silent-stale policy

When a fresh entry expires, the cache attempts a refresh. A retained stale entry
is never returned unless:

1. refresh failed or returned invalid/unavailable data;
2. the entry is still inside stale retention;
3. the trusted caller supplied `allow_stale=true`.

Without explicit permission, the result is `unavailable`, the typed snapshot is
not returned, and `STALE_NOT_ALLOWED` is recorded. When stale retention ends, the
entry is pruned before refresh and cannot be recovered.

A failed forced refresh while the cached snapshot is still fresh returns an
explicit fresh-cache fallback with `refresh_succeeded=false` and a fixed error
code. It is not silently reported as a successful refresh.

## Single-flight and lifecycle

One process-local `RLock` protects:

- initial load;
- refresh;
- stale selection;
- expiry pruning;
- active-entry count;
- clear/restart state.

The loader executes while this lock is held. Concurrent initial readers therefore
produce one source call; later readers receive the resulting typed snapshot.

`clear()` removes the single entry. A new process starts empty. There is no disk,
database or cross-process persistence.

## Validation and failure behavior

Only `AcraIssuerRatingActionsSnapshotV1` with status `available` may be stored.
The cache verifies:

- fixed ACRA provider and source id;
- non-empty records;
- all records share the snapshot source;
- canonical release URLs are unique;
- source retrieval time is not beyond future tolerance.

Wrong type, source mismatch, future timestamp, unavailable source, loader error
and source data already beyond retention fail closed with fixed cache error codes.
Exception type, exception text and traceback are never copied to the result.

## Data boundary

The cache retains only the immutable typed PR-94 snapshot. It does not retain:

- raw HTML or raw title text;
- upstream response body;
- cookies, credentials or Authorization headers;
- account, portfolio or broker payload;
- exception text or traceback.

All records retain `trading_methods=false`; the cache adds no financial threshold
or trade authorization.

## Startup and API behavior

Import, construction and startup perform no source call. Retrieval occurs only
when an explicit internal caller invokes `get()`.

PR-95 adds no:

- FastAPI route or operationId;
- GPT Action, request body or public response field;
- frontend/dashboard binding;
- background job or automatic emission;
- dependency, database, secret or Render migration;
- T-Invest call or broker write method;
- order, cancellation, transfer or withdrawal capability.

`app:app`, exactly 14 authenticated GET Actions and `trading_methods=false`
remain unchanged.

## Tests

Focused tests cover:

- unique canonical release URL invariant;
- impossible state rejection;
- initial refresh and fresh cache hit;
- failed forced refresh with explicit fresh fallback;
- hidden versus explicitly exposed stale records;
- full-expiry pruning;
- wrong type, unavailable source, future timestamp and source mismatch;
- concurrent single-flight initial load;
- clear/restart-empty and configuration guards;
- versioned exports and absence of route/startup/write surface.

## Next step

The next independent package may map typed source/cache status to allowlisted
observability events. Such events must omit issuer names, ratings, outlooks,
release URLs, publication dates, raw HTML, account data and exception text.
Production owner/UI binding remains blocked until the exact existing caller is
identified.
