# Bounded CBR key-rate alert policy v1

## Purpose

PR-87 adds an internal alert policy over the allowlisted PR-86 CBR source/cache
observability events. It turns repeated operational failures into typed alert
evaluations without adding an outbound notification transport.

The package does not inspect or compare the key-rate value. It operates only on
status, outcome, freshness, fixed error codes and consecutive event counts.

## Inputs

Only these event names are recognized:

- `macro.cbr_key_rate.source`;
- `macro.cbr_key_rate.cache`.

Other `ObservabilityEventV1` instances are returned as `ignored` and do not
create state.

## Alert kinds

- `source_unavailable` — official PR-84 source failed;
- `cache_unavailable` — PR-85 has no displayable snapshot;
- `stale_value_exposed` — stale display was explicitly allowed after refresh
  failure;
- `refresh_failed_using_fresh_cache` — refresh failed while a still-fresh cached
  snapshot remained usable.

Source/cache unavailable alerts use error severity. Stale exposure and failed
refresh with fresh fallback use warning severity.

## Default thresholds

- source unavailable: 3 consecutive events;
- cache unavailable: 2 consecutive events;
- stale exposure: 2 consecutive events;
- failed refresh with fresh cache: 3 consecutive events;
- cooldown: 900 seconds;
- state retention: 86400 seconds;
- bounded state capacity: 4 alert kinds.

Thresholds are immutable typed configuration, not environment-derived financial
values.

## State machine

Each evaluation returns one or more immutable
`CbrKeyRateAlertEvaluationV1` values:

- `ignored` — event is unsupported or healthy with no active state;
- `pending` — the condition is consecutive but below threshold;
- `fired` — threshold was reached and cooldown permits an alert;
- `suppressed_cooldown` — the condition remains active but a duplicate alert is
  inside cooldown;
- `recovered` — a healthy or different same-domain state clears a previously
  fired alert.

A change between cache conditions recovers the old active cache alert before
starting the new condition. Pending sibling conditions are reset silently.

## Deduplication and cooldown

After an alert fires, repeated matching events are suppressed until cooldown
expires. The evaluation exposes only a non-negative remaining-seconds count.
No notification is emitted by this package.

Active state is not pruned before cooldown ends, even if configured generic
state retention is shorter. Pending state still expires at normal retention.
This prevents a short retention setting from bypassing deduplication.

## Bounded lifecycle

- process-local `OrderedDict` state;
- `RLock` guards evaluation, pruning, recovery and clear;
- configured finite capacity;
- retention pruning for abandoned state;
- consecutive counters saturate at 1,000,000;
- explicit `clear()` and restart-clear behavior;
- out-of-order matching events fail closed with a fixed code.

No database or persistent alert journal is added.

## Privacy and safety

Serialized alert evaluations contain no:

- key-rate value;
- effective or requested dates;
- raw XML or SOAP payload;
- exception text;
- account or portfolio data;
- broker request/response;
- order or trading authorization.

Every evaluation keeps `contains_sensitive_payload=false` and
`trading_methods=false`.

## Compatibility

- `app:app` unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, request body, response field or frontend component added;
- no webhook, email, Telegram or external alert service;
- no T-Invest call or broker write method;
- no dependency or secret migration.

## Tests

Focused tests cover thresholds, firing, cooldown suppression, reminder firing,
recovery, cache-kind transitions, unsupported events, out-of-order rejection,
pending/active retention, concurrent equal-timestamp evaluation, payload
exclusions and absence of route/webhook/write surfaces.

## Remaining boundary

PR-87 produces typed decisions only. A later package may connect `fired` and
`recovered` evaluations to a bounded existing logging or operations sink. Any
external notification transport, paging destination, retention service or
production threshold tuning requires a separate reviewed package and production
acceptance evidence.

## Rollback

Revert the PR-87 squash commit. No database, secret, dependency, OpenAPI or
Render migration is required.
