# ACRA rating actions alert policy v1

## Purpose

PR-97 adds one bounded process-local operational alert evaluator over canonical
PR-96 ACRA source/cache events. It monitors source and cache health only. It does
not evaluate issuers, ratings, outlooks, actions, releases, publication dates,
portfolio risk or investment suitability.

## Immutable scope

The only scope is `global_acra_rating_actions_feed`.

The policy cannot represent per-issuer or per-rating state because PR-96 telemetry
intentionally excludes issuer identity, rating values, outlooks, action types,
release URLs and publication dates. Correlation identifiers are opaque and must
not be decoded or used to reconstruct hidden identity.

## Supported operational conditions

- source unavailable;
- cache unavailable;
- stale records explicitly exposed;
- refresh failed while a still-fresh cached snapshot remains usable.

No rating level, downgrade, outlook, issuer, publication age or financial value
can trigger this policy.

## Canonical event gate

Known PR-96 event names are accepted only when the complete event profile is
canonical:

- exact event name and component;
- provider `ACRA`;
- operation `press_releases.issuer_rating_actions`;
- exact allowlisted metric-name set;
- fixed-official-source and issuer-scope flags;
- valid outcome, severity, external-call status and freshness combination;
- valid cache-hit, refresh, stale and display flags;
- no account, request/action identity, exception type or generic payload.

A forged same-name event fails closed before state changes. Unknown event names
are ignored and cannot create alert state.

## State lifecycle

The evaluator provides:

- `ignored`, `pending`, `fired`, `suppressed_cooldown` and `recovered` results;
- bounded consecutive thresholds;
- saturating counters;
- cooldown and recovery;
- out-of-order rejection;
- state retention and fixed capacity four;
- one `RLock` around state transitions;
- restart-empty and explicit `clear()` behavior.

Default thresholds are three source failures, two cache failures, two stale
exposures and three failed refreshes using fresh fallback. Default cooldown is
900 seconds and retention is 86400 seconds.

## Privacy and safety

Evaluation serialization contains only global operational state, counters,
thresholds, severity, disposition, source event name and safe error code.
It contains no issuer, rating, outlook, action, release, publication date,
financial value, account data, raw HTML, upstream body or exception text.

The package adds no:

- route or GPT Action;
- frontend field;
- startup/background source call;
- logger or automatic emission;
- webhook, email, Telegram, pager or external transport;
- broker call or write method;
- order, cancellation, transfer or withdrawal capability.

`app:app`, exactly 14 authenticated GET Actions and `trading_methods=false`
remain unchanged.

## Tests

Tests cover canonical mapping, thresholds, cooldown, recovery, sibling recovery,
healthy-event recovery, retention, clear, concurrency, out-of-order rejection,
forged-event rejection, privacy serialization, stable exports and absence of
external transport or broker-write surfaces.

## Next package

A later reviewed package may compose PR-96 event -> PR-97 evaluation and retain
only bounded fired/recovered global evidence. It must not add external delivery,
issuer/rating identity or startup network calls.
