# Expert RA rating actions operations lifecycle v1

## Purpose

PR-103 composes the already-typed Expert RA operational chain:

1. PR-101 source/cache result to privacy-safe `ObservabilityEventV1`;
2. PR-102 canonical global alert evaluation;
3. bounded process-local evidence for terminal `fired` and `recovered` states.

The lifecycle is an internal evidence boundary. It is not an external alerting,
notification, trading or recommendation subsystem.

## Inputs

The lifecycle accepts only typed values already defined by the Expert RA
source/cache packages:

- `ExpertRaIssuerRatingActionsSnapshotV1` through `observe_source`;
- `ExpertRaIssuerRatingActionsCacheResultV1` through `observe_cache`.

It delegates event construction to the canonical PR-101 builders and alert state
to the canonical PR-102 evaluator. It does not parse HTML, call Expert RA,
refresh the cache or reconstruct telemetry.

## Deterministic processing order

One `RLock` protects each processing call:

1. build one canonical event from a typed source/cache result;
2. prune expired local evidence;
3. run the canonical evaluator;
4. revalidate every terminal evaluation and bind its timestamp and event name;
5. derive a deterministic opaque evidence ID;
6. return an existing identical record or insert the new record;
7. invoke the optional evidence sink only for newly inserted records;
8. return one immutable redacted batch.

The batch retains only the source event name, evaluations, terminal evidence and
sink-failure count. It does not retain or expose the event payload or correlation
ID. Concurrent callers cannot interleave evaluator/evidence state mutation.

## Evidence contract

`ExpertRaRatingActionsAlertEvidenceV1` contains only:

- deterministic `expert-ra-evidence:` plus 64 `a..p` opaque evidence ID;
- UTC recorded timestamp;
- canonical source event name;
- fixed global scope;
- terminal disposition;
- global operational alert kind and severity;
- bounded occurrence count and threshold;
- optional allowlisted safe error code;
- immutable false-valued correlation, issuer, rating, action, release,
  publication, financial, raw-payload, threshold, delivery, broker-write and
  trading flags.

The contract rejects `ignored`, `pending` and `suppressed_cooldown`
evidence. Fired evidence must meet its threshold and carry a safe error code.
Recovered evidence cannot retain an error code. Source event, kind and severity
must match the canonical Expert RA operational profile.

## Deterministic identity and deduplication

The ID is the SHA-256 digest of the validated terminal evaluation's UTC
timestamp, source event, fixed scope, disposition, kind, severity, occurrence
count, threshold and safe error code. Each digest nibble is encoded with
`a..p`, producing a fixed non-hex opaque token.

Correlation ID is deliberately excluded from both the digest and retained
evidence. Semantically identical terminal evaluations therefore converge on one
record even when callers use different opaque correlations. An identical
existing record is returned without another sink handoff. A same-ID,
different-content condition fails closed as an evidence collision.

## Privacy boundary

Evidence and the returned batch contain no:

- correlation identity or full event payload;
- issuer or instrument identity;
- rating value, scale, outlook or action identity;
- release URL/id or publication date;
- raw HTML, title or upstream body;
- account, portfolio or broker payload;
- financial values or recommendation semantics;
- exception type or exception text.

Sink exceptions are reduced to `sink_failure_count`. Exception text is not
stored in the returned batch or evidence.

## Bounded local state

Defaults:

- retention: 86,400 seconds;
- capacity: 64 evidence records.

Allowed configuration is bounded to 60…604,800 seconds and 1…256 records.
Boolean values are not accepted as integer configuration. Expired records are
pruned on processing and evidence reads. Oldest records are evicted when
capacity is exceeded. `clear()` resets both evaluator and evidence state.
Process restart starts empty.

Evidence is inserted before the optional sink is called. A failing sink
therefore does not erase the internally recorded terminal transition. Only new
records are handed to the sink.

## Fail-closed composition

The lifecycle accepts only the exact canonical PR-102 evaluator type and verifies
its global/privacy/trading safety markers. Terminal evaluations are serialized
through their Pydantic contract again before recording and must remain equal to
the evaluator output.

A terminal evaluation must match the canonical event timestamp and name. Fired
error codes are restricted to the credit-rating source/cache enums and the four
fixed Expert RA operational alert codes. Invalid types, timestamps, bindings,
error codes or identity collisions fail closed.

## Safety and non-goals

PR-103 adds no:

- FastAPI route or GPT Action;
- public response or frontend field;
- database, queue or persistent storage;
- event logger, event sink or automatic external emission;
- webhook, email, Telegram, pager or outbound transport;
- source/cache call at import or startup;
- broker call, order, cancellation, transfer or withdrawal method.

`app:app`, exactly 14 GET Actions total and `trading_methods=false` remain
unchanged.

## Tests

Tests cover:

- pending versus fired/recovered evidence;
- terminal-only contract and source/kind/severity binding;
- event-payload and correlation non-retention;
- deterministic correlation-independent IDs and deduplication;
- new-record-only sink handoff and failure redaction;
- global scope and privacy flags;
- retention, capacity, eviction and clear;
- invalid evaluator/configuration/timestamp rejection;
- issuer/rating payload exclusion;
- concurrent identical-signal collapse;
- stable export identity and absence of route/notification/write surfaces.

## Next boundary

PR-103 completes the separate Expert RA
source/cache/observability/alert/evidence chain. Production binding remains
blocked until an exact existing owner/caller is located. A later package may
bind the lifecycle lazily, but must not add startup network calls, duplicate
frontend state, external delivery or public API changes.
