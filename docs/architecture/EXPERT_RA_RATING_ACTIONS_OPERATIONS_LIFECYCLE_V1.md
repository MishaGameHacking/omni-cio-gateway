# Expert RA rating-actions operations lifecycle v1

## Purpose

PR-103 completes the separate Expert RA operational chain:

1. PR-101 typed source/cache state -> privacy-safe `ObservabilityEventV1`;
2. PR-102 canonical global alert evaluation;
3. bounded process-local terminal evidence for only `fired` and `recovered`.

The lifecycle is an internal evidence boundary. It is not an external alerting,
notification, trading or recommendation subsystem.

## Input boundary

The lifecycle accepts only:

- `ExpertRaIssuerRatingActionsSnapshotV1` through `observe_source`;
- `ExpertRaIssuerRatingActionsCacheResultV1` through `observe_cache`.

Canonical PR-101 builders fully validate those inputs and construct the event.
The exact PR-102 evaluator is required; evaluator subclasses or caller-provided
lookalikes are rejected. The lifecycle does not parse HTML, call Expert RA,
refresh the cache or reconstruct alert logic.

## Deterministic processing order

One lifecycle `RLock` serializes each call:

1. prune expired terminal evidence;
2. build the canonical PR-101 event;
3. evaluate it with the canonical PR-102 state machine;
4. revalidate terminal evaluations and exact event/evaluation binding;
5. construct deterministic evidence IDs;
6. persist new evidence before any sink call;
7. invoke only the optional evidence sink for newly inserted evidence;
8. return an immutable batch without the source event object.

There is deliberately no event sink in PR-103. A terminal-evidence consumer does
not receive the correlation-bearing source event through this lifecycle.

## Terminal evidence contract

`ExpertRaRatingActionsAlertEvidenceV1` contains only:

- deterministic `expert-ra-evidence:` + 64 `a..p` characters;
- UTC recorded timestamp;
- canonical source event name;
- fixed global scope;
- terminal disposition (`fired` or `recovered`);
- one of four global operational alert kinds;
- fixed operational severity;
- bounded consecutive count and threshold;
- safe operational error code for `fired`; recovery has no error code;
- immutable false-valued privacy, delivery, broker-write and trading flags.

The contract additionally binds:

- `source_unavailable` evidence to the source event;
- all cache alert kinds to the cache event;
- source/cache unavailable severity to `error`;
- stale/fresh-refresh-failure severity to `warning`.

`ignored`, `pending` and `suppressed_cooldown` are never terminal evidence.

## Deterministic evidence ID

The evidence identifier is a SHA-256 digest over only privacy-safe operational
fields:

- evaluated UTC timestamp;
- canonical source event name;
- fixed global scope;
- terminal disposition;
- global alert kind and severity;
- occurrence count and threshold;
- safe error code or empty recovery marker.

Each SHA-256 nibble is encoded as `a..p`, producing 64 opaque characters. The
correlation ID is intentionally not part of the digest. Equivalent terminal
operational state therefore produces the same evidence ID across independent
process-local lifecycle instances.

If the same deterministic evidence is recorded twice, insertion is idempotent and
the evidence sink is not called again. A same-ID/different-content condition
fails closed as an evidence-ID collision.

## Privacy boundary

Terminal evidence contains no:

- correlation ID;
- issuer, instrument or source-title identity;
- rating value, rating scale, outlook or rating action identity;
- release URL/id or publication date;
- raw HTML, title or upstream body;
- account, portfolio, position, price, cash or broker payload;
- financial values or recommendation semantics;
- exception type, exception text or traceback.

The evidence contract carries explicit false flags for correlation, issuer,
rating, action, release, publication date, financial values and raw source
payload. `trading_methods=false` remains structural.

## Sink boundary

PR-103 has only an injected `evidence_sink` callable. There is no built-in logger,
webhook, email, Telegram, pager or queue transport.

Evidence is inserted before the optional sink is called. Sink exceptions are
reduced to `sink_failure_count`; exception text is not returned or retained.
Only newly inserted deterministic evidence is sent to the sink.

## Bounded local state

Defaults:

- retention: 86,400 seconds;
- capacity: 64 evidence records.

Allowed configuration is bounded to 60…604,800 seconds and 1…256 records.
Expired records are pruned on processing and evidence reads. Oldest records are
evicted at capacity. `clear()` resets both PR-102 evaluator state and evidence.
Process restart starts empty; no disk/database persistence exists.

## Concurrency and ordering

The lifecycle and PR-102 evaluator both use re-entrant locks. Concurrent equal-
timestamp observations are serialized deterministically by state mutation. For a
threshold-one source outage, concurrent equivalent observations create exactly
one `fired` evidence item; subsequent same-state calls are cooldown-suppressed.
A following healthy event creates one `recovered` item.

Decreasing timestamps for a retained known alert state remain fail-closed through
PR-102.

## Safety and non-goals

PR-103 adds no:

- FastAPI route or GPT Action;
- public response or frontend field;
- database, queue or persistent storage;
- event sink or automatic external emission;
- webhook, email, Telegram, pager or outbound transport;
- source/cache call at import or startup;
- T-Invest call or broker write method;
- order, cancellation, transfer or withdrawal method;
- margin, short or derivative execution.

`app:app`, exactly 14 GET Actions and `trading_methods=false` remain unchanged.

## Tests

Focused tests cover:

- pending versus fired/recovered evidence;
- terminal-only contract validation;
- deterministic IDs across independent lifecycles with different correlation IDs;
- idempotent duplicate evidence insertion;
- evidence-sink-after-store ordering;
- sink failure redaction;
- serialized absence of correlation/issuer/rating/action/release/publication data;
- source/cache kind, severity and global-scope binding;
- retention, capacity, eviction and clear;
- exact evaluator/config/input type guards;
- terminal evaluation event/time/error-code rebinding;
- concurrent same-timestamp source failures;
- stable exports and absence of route/event-sink/notification/write surfaces.

## Next boundary

PR-103 completes the separate Expert RA source/cache/observability/alert/evidence
chain. Production binding remains blocked until an exact existing owner/caller is
located. Any later binding must be lazy, must reuse the existing owner, and must
not add startup network calls, duplicate frontend state, external delivery or
public API changes.
