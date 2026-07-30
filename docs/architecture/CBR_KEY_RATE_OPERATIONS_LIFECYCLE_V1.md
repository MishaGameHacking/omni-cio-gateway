# CBR key-rate operations lifecycle v1

## Purpose

PR-88 composes the existing PR-84…PR-87 internal boundaries without adding a
new network caller or public API:

1. a trusted caller obtains one typed CBR source snapshot or cache result;
2. PR-86 builds one allowlisted observability event;
3. PR-87 evaluates that event under the bounded alert policy;
4. PR-88 retains only `fired` and `recovered` operator evidence;
5. optional typed sinks receive the safe event first and any evidence second.

The package does not fetch the Bank of Russia source at startup. Repository
search found no registered production owner of the CBR cache, so PR-88 remains
an internal coordinator until an exact caller is identified.

## Inputs

The lifecycle accepts only existing typed contracts:

- `CbrKeyRateSnapshotV1` through `observe_source(...)`;
- `CbrKeyRateCacheResultV1` through `observe_cache(...)`.

Source event time defaults to `snapshot.retrieved_at`. Cache event time defaults
to `result.checked_at`. A caller may provide an explicit aware timestamp,
latency and opaque correlation ID.

No raw XML, SOAP body, free-form exception text or untyped dictionary is
accepted.

## Deterministic processing order

Each call is serialized under one process-local `RLock`:

1. prune expired evidence;
2. evaluate the PR-86 event using PR-87;
3. materialize `fired/recovered` evidence;
4. enforce evidence capacity;
5. invoke the event sink;
6. invoke evidence sinks in evaluation order;
7. return one immutable batch.

The lock remains held through safe sink invocation so concurrent calls cannot
reorder event/evidence output relative to alert-state evaluation.

## Evidence contract

`CbrKeyRateAlertEvidenceV1` contains only:

- opaque evidence and correlation identifiers;
- recorded timestamp;
- source event name;
- alert kind, severity and `fired/recovered` disposition;
- consecutive occurrence count and threshold;
- fixed safe error code when required;
- immutable `contains_sensitive_payload=false`;
- immutable `trading_methods=false`.

Evidence cannot represent `pending`, `ignored` or cooldown-suppressed states.
A fired evidence item must meet its threshold and have a safe error code.

Evidence contains no:

- key-rate value or effective/requested date;
- XML, SOAP Fault or upstream body;
- account, portfolio, position or monetary field;
- exception message or secret;
- order, transfer, withdrawal or trading authorization.

## Retention and capacity

Defaults:

- evidence retention: 86,400 seconds;
- evidence capacity: 64 entries.

Allowed bounds:

- retention: 60…604,800 seconds;
- capacity: 1…256 entries.

Expired items are pruned on the next observation or evidence read. Oldest items
are evicted when capacity is exceeded. `clear()` removes both PR-87 alert state
and all PR-88 evidence. Process restart clears all state.

## Sink behavior

Both sinks are optional typed callables:

- event sink receives `ObservabilityEventV1`;
- evidence sink receives `CbrKeyRateAlertEvidenceV1`.

A sink exception is never copied into an event or evidence record. It is reduced
to `sink_failure_count` in the returned internal batch. Evidence remains stored
and alert state remains valid. There is no automatic retry or outbound
notification transport in this package.

## Concurrency

The lifecycle serializes event construction handoff, alert evaluation, evidence
publication and sink ordering. Concurrent repeated failures therefore produce:

- the required pending occurrences;
- one fired evidence at the threshold;
- cooldown-suppressed evaluations without duplicate evidence.

## Compatibility

- `app:app` is unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no request body or public response field is added;
- no dependency, secret, database or Render migration is added;
- no source fetch or cache refresh happens at import/startup;
- no T-Invest method is called;
- `trading_methods=false`.

## Tests

Focused tests cover:

- source pending → fired → cooldown → recovered lifecycle;
- stale cache event mapping;
- deterministic event/evidence sink order;
- sink failure redaction;
- evidence retention, capacity and clear;
- concurrent deduplication;
- invalid configuration and timestamp rejection;
- evidence contract validation and payload exclusions;
- absence of route, webhook, email and broker-write surfaces.

## Rollback

Revert the PR-88 squash commit. No database, external service, OpenAPI, secret
or deployment migration is required.

## Remaining boundary

A later package may register this lifecycle only after the exact existing CBR
caller/owner is found. Production registration must remain lazy and must not
perform a source or cache call during application startup. External notification
routing remains a separate owner-approved operations decision.
