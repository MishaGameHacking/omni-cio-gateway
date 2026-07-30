# MOEX ISS TQBR quote cache v1

## Purpose

PR-90 adds an internal bounded cache over the typed PR-89 public MOEX ISS quote
source. It provides an explicit `fresh`, `stale` or `unavailable` result for one
exact `TQBR + SECID` identity without adding a route, GPT Action or startup
network call.

The cache controls source-request frequency. It does not convert public delayed
market data into guaranteed real-time data and does not authorize trading.

## Identity

The process-local key is exactly:

```text
("TQBR", normalized SECID)
```

SECID uses the same strict PR-89 validation. Different tickers are never merged.
A loaded snapshot must match SECID, TQBR board and stable instrument key
`MOEX:TQBR:{SECID}`.

## Default lifecycle

- fresh TTL: 60 seconds;
- stale retention: 900 seconds;
- capacity: 64 exact identities;
- future tolerance: 30 seconds.

Configuration is bounded and rejects booleans or invalid ranges. Cache state is
cleared on process restart.

## Two distinct clocks

`fresh_until` and `stale_until` are derived from `snapshot.retrieved_at`; they
control when the public source may be called again and how long a typed snapshot
may remain physically available.

`age_seconds` is derived from `snapshot.quote.as_of`; it represents the age of
the market observation shown to the user. A recently retrieved HTTP response
may therefore have an old market-data age. These clocks must never be conflated.

The immutable source limitations remain visible in every result:

- `public_unauthenticated_feed=true`;
- `delayed_data_possible=true`;
- `realtime_guaranteed=false`;
- `informational_use_only=true`.

## Result states

### Fresh

A fresh result contains one exact available PR-89 snapshot and permits display.
It may represent:

- a successful refresh;
- a normal fresh cache hit with no source call;
- a failed forced refresh while the existing cached snapshot remains inside its
  fresh TTL. That fallback is explicit through refresh/error metadata.

### Stale

A stale result is returned only when:

1. the cached snapshot is past fresh TTL but before stale expiry;
2. a refresh was attempted and did not produce a usable exact snapshot;
3. trusted caller policy explicitly sets `allow_stale=true`.

The result is marked `served_from_cache=true`, `stale_available=true`,
`stale_value_exposed=true` and carries the safe refresh/source error.

### Unavailable

Unavailable returns no snapshot and forbids display. This includes:

- no cache and failed/unavailable source;
- stale exists but `allow_stale=false`;
- expired entry;
- loader exception or wrong return type;
- SECID/board/instrument mismatch;
- future retrieval/quote timestamp;
- newly loaded snapshot already outside the permitted freshness policy.

A physically retained stale entry is never leaked through an unavailable result.

## Single-flight and bounds

One process-local `RLock` protects lookup, pruning, source refresh, replacement,
eviction and clear. Concurrent requests for the same empty key therefore cause
one loader call; later callers receive the stored fresh snapshot.

The cache uses an `OrderedDict` with oldest-entry eviction. Entries are removed
at stale expiry. `active_entry_count()` prunes before reporting, and `clear()`
removes all state.

## Contract invariants

`MoexIssTqbrQuoteCacheResultV1` rejects impossible combinations, including:

- successful refresh without an attempted refresh;
- successful refresh marked as a cache hit or carrying error metadata;
- only one cache boundary present;
- fresh result at or after `fresh_until`;
- stale result outside `[fresh_until, stale_until)`;
- stale exposure without stale availability and cache service;
- unavailable result carrying a snapshot;
- stale-available unavailable result with inconsistent boundaries;
- cached snapshot identity mismatch.

## Source failure behavior

Loader exceptions are reduced to fixed cache error metadata. Exception text is
not retained. An unavailable PR-89 snapshot contributes only its fixed source
error code. Wrong types, identities and future timestamps fail closed.

## Privacy and safety

Only typed public-market snapshots are retained. The cache stores no:

- raw JSON or upstream response body;
- token, cookie or credential;
- account, position or portfolio data;
- exception text;
- broker request or response;
- order or trading authorization.

Immutable flags preserve `raw_json_stored=false`, `credentials_present=false`,
`broker_write_called=false`, `trade_authorized=false`, `order_created=false` and
`trading_methods=false`.

## Compatibility

- `app:app` unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, request body, response field or frontend component added;
- no network call at module import or application startup;
- no new dependency, secret, database or Render migration;
- no T-Invest method or broker write surface.

## Source priority

Broker `getMarketSnapshot` remains primary for execution-style calculations.
MOEX and broker values remain separate sources and are never silently averaged.
PR-90 is suitable only for informational reference, discrepancy analysis and a
future UI with explicit source and freshness labels.

## Tests

Focused tests cover strict contracts, first refresh, fresh hits, two-clock age,
failed force-refresh fallback, explicit stale policy, expiry, single-flight
concurrency, type/identity/future guards, already-old refreshes, capacity
eviction, key isolation, clear/restart behavior, configuration guards, exports
and absence of route/startup/write surfaces.

## Remaining boundary

PR-90 does not register a production caller. A later package may add safe
observability for source/cache status and age without including price values.
Dashboard or Action binding remains blocked until the exact existing owner is
located and reviewed.

## Rollback

Revert the PR-90 squash commit. No persistent data, secret, OpenAPI, database or
deployment migration must be reversed.
