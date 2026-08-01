# Expert RA issuer rating action cache v1

## Purpose

PR-100 adds one bounded process-local cache over the typed PR-99 Expert RA
source. It reduces repeated retrieval while preserving explicit freshness,
agency isolation and fail-closed behavior. It is not a route, database,
scheduler, recommendation engine or trading permission.

## Fixed identity and capacity

The source identity is immutable:

- provider `Expert RA`;
- source id `EXPERT_RA.home.rating_actions`;
- issuer-level Russian national-scale actions only;
- unresolved source-title issuer identity remains unresolved;
- one fixed source snapshot in one process-local entry.

Capacity is structurally one because callers cannot select an agency, URL,
language, rating scale or query range. Expert RA remains separate from ACRA; no
cross-agency cache, scale conversion or identity merge is introduced.

## Two time concepts

PR-100 keeps retrieval freshness separate from publication evidence.

- `snapshot.retrieved_at` alone controls cache fresh/stale TTL;
- each `record.published_on` remains the official action publication date;
- a new source retrieval does not rewrite a record publication date;
- cache check time does not become an inferred event time.

Defaults:

- fresh TTL: 900 seconds;
- stale retention: 86,400 seconds;
- future retrieval timestamp tolerance: 30 seconds;
- capacity: one typed source snapshot.

## Explicit states

`ExpertRaIssuerRatingActionsCacheResultV1` supports exactly:

- `fresh` — typed records may be displayed;
- `stale` — records may be displayed only after an unsuccessful refresh and
  explicit trusted `allow_stale=true`;
- `unavailable` — no records are returned for display.

The result states:

- check time and retrieval age;
- fresh and stale boundaries when an entry is relevant;
- whether it came from cache;
- whether refresh was attempted and succeeded;
- whether stale records physically exist and whether they were exposed;
- fixed source/cache error codes;
- whether display is allowed.

## No-silent-stale policy

When a fresh entry expires, the cache attempts a refresh. A retained stale entry
is never returned unless all of the following are true:

1. refresh failed or returned invalid/unavailable data;
2. the retained entry is still inside stale retention;
3. the trusted caller explicitly supplied `allow_stale=true`.

Without explicit permission, the result is `unavailable`, the snapshot is not
returned, and `STALE_NOT_ALLOWED` is recorded. When stale retention ends, the
entry is pruned before refresh and cannot be recovered.

A failed forced refresh while the cached snapshot is still fresh returns an
explicit fresh-cache fallback with `refresh_succeeded=false` and a fixed cache
error code. It is never reported as a successful refresh.

## Single-flight lifecycle

One process-local `RLock` protects:

- initial load;
- refresh;
- stale selection;
- expiry pruning;
- active-entry count;
- clear state.

The loader executes while the lock is held. Concurrent initial readers therefore
produce one source call; subsequent readers receive the resulting immutable typed
snapshot.

`clear()` removes the single entry. A new process starts empty. There is no disk,
database or cross-process persistence.

## Fail-closed validation boundary

Only `ExpertRaIssuerRatingActionsSnapshotV1` may be stored. The cache repeats
identity checks even when a caller hands it an already-constructed model, so a
model created with validator-bypassing APIs cannot silently weaken the source
boundary.

An available snapshot must satisfy:

- official source authority;
- exact provider `Expert RA`;
- exact source id `EXPERT_RA.home.rating_actions`;
- `snapshot.retrieved_at == snapshot.source.retrieved_at`;
- non-empty records;
- every record is the Expert RA typed record and shares the exact source;
- every record remains issuer scope with unresolved identity semantics;
- release URLs are unique;
- records remain deterministic newest-first;
- `cross_agency_identity_merged=false`;
- `trading_methods=false`.

Wrong type, source mismatch, invalid model-constructed ordering/identity,
future retrieval timestamp, unavailable source, loader exception and data already
outside retention fail closed with fixed cache error codes. Exception type,
exception text and traceback are never copied to the result.

## Privacy and use boundary

The cache retains only the immutable typed PR-99 snapshot. It does not retain:

- raw HTML or raw title text;
- upstream response body;
- cookies, credentials or Authorization headers;
- account, portfolio or broker payload;
- exception text or traceback.

The cache and result explicitly preserve:

- `agency_specific_scale_only=true`;
- `subject_identity_resolution_required=true`;
- `cross_agency_identity_merged=false`;
- `informational_use_only=true`;
- `redistribution_authorized=false`;
- `investment_recommendation=false`;
- `trading_methods=false`.

## Startup and API behavior

Import, construction and application startup perform no source call. Retrieval
occurs only when an explicit internal caller invokes `get()`.

PR-100 adds no:

- FastAPI route or operationId;
- GPT Action, request body or public response field;
- frontend/dashboard binding;
- background job or automatic source fetch;
- generic multi-agency adapter;
- dependency, database, secret or Render migration;
- T-Invest call or broker write method;
- order, cancellation, transfer or withdrawal capability.

`app:app`, exactly 14 GET Actions and `trading_methods=false` remain unchanged.

## Tests

Focused tests cover:

- cache-result impossible-state rejection;
- initial refresh and fresh cache hit;
- retrieval time rather than publication date as freshness clock;
- failed forced refresh with explicit fresh fallback;
- hidden versus explicitly exposed stale records;
- full-expiry pruning;
- wrong type, unavailable source and future timestamp;
- validator-bypassed source/order/cross-agency identity rejection;
- concurrent single-flight initial load;
- clear/restart-empty and configuration guards;
- conservative privacy/use flags;
- versioned exports and absence of route/startup/generic-adapter/write surface.

## Next step

Only after PR-100 passes the full Regression Shield and squash-merges may a
separate package map typed Expert RA source/cache status to allowlisted
privacy-safe observability events. Such telemetry must omit issuer names,
ratings, outlooks, actions, release URLs, publication dates, raw HTML, account
data and exception text. Production owner/UI binding remains a separate task.
