# ACRA rating actions operations lifecycle v1

## Purpose

PR-98 composes the already-typed ACRA operational chain:

1. PR-96 source/cache result to privacy-safe `ObservabilityEventV1`;
2. PR-97 canonical global alert evaluation;
3. bounded process-local evidence for terminal `fired` and `recovered` states.

The lifecycle is an internal evidence boundary. It is not an external alerting,
notification, trading or recommendation subsystem.

## Inputs

The lifecycle accepts only typed values already defined by the ACRA source/cache
packages:

- `AcraIssuerRatingActionsSnapshotV1` through `observe_source`;
- `AcraIssuerRatingActionsCacheResultV1` through `observe_cache`.

It delegates event construction to the canonical PR-96 builders and alert state
to the canonical PR-97 evaluator. It does not parse HTML, call ACRA, refresh the
cache or reconstruct telemetry.

## Deterministic processing order

One `RLock` protects each processing call:

1. prune expired local evidence;
2. evaluate the canonical event;
3. create evidence only for `fired` or `recovered` evaluations;
4. invoke the optional event sink;
5. invoke optional evidence sinks in evidence order;
6. return one immutable batch.

The event sink therefore runs before evidence sinks for the same call. Calls are
serialized so concurrent callers cannot interleave one event/evidence pair.

## Evidence contract

`AcraRatingActionsAlertEvidenceV1` contains only:

- generated opaque evidence id;
- UTC recorded timestamp;
- opaque correlation id;
- canonical source event name;
- fixed global scope;
- terminal disposition;
- global operational alert kind and severity;
- bounded occurrence count and threshold;
- optional safe error code;
- immutable false-valued privacy, delivery and trading flags.

The contract rejects `ignored`, `pending` and `suppressed_cooldown` evidence.
Fired evidence must meet its threshold and carry a safe error code.

## Privacy boundary

Evidence contains no:

- issuer or instrument identity;
- rating value, scale, outlook or action;
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
Expired records are pruned on processing and evidence reads. Oldest records are
evicted when capacity is exceeded. `clear()` resets both evaluator and evidence
state. Process restart starts empty.

Evidence is inserted before optional sinks are called. A failing sink therefore
does not erase the internally recorded terminal transition; the batch reports
the number of failed sink invocations.

## Safety and non-goals

PR-98 adds no:

- FastAPI route or GPT Action;
- public response or frontend field;
- database, queue or persistent storage;
- logger or automatic external emission;
- webhook, email, Telegram, pager or outbound transport;
- source/cache call at import or startup;
- broker call, order, cancellation, transfer or withdrawal method.

`app:app`, exactly 14 GET Actions total and `trading_methods=false` remain
unchanged.

## Tests

Tests cover:

- pending versus fired/recovered evidence;
- terminal-only contract validation;
- event-before-evidence sink ordering;
- sink failure redaction;
- global scope and privacy flags;
- retention, capacity, eviction and clear;
- invalid configuration;
- issuer/rating payload exclusion;
- concurrent pair ordering;
- stable exports and absence of route/notification/write surfaces.

## Next boundary

Production binding remains blocked until an exact existing owner/caller is
located. A later package may bind this lifecycle lazily to that owner, but must
not introduce startup network calls, duplicate frontend state, external delivery
or public API changes.
