# ACRA rating actions operations lifecycle v1

## Purpose

PR-98 composes already-produced typed ACRA source/cache results through the
existing PR-96 safe event builders and PR-97 global operational evaluator. It
retains bounded evidence only when an alert is fired or recovered.

## Deterministic flow

```text
typed PR-94/95 result
→ PR-96 safe event
→ PR-97 global evaluation
→ PR-98 fired/recovered evidence
```

The lifecycle does not fetch ACRA, refresh the cache, register a route, or run at
application startup.

## Evidence contract

`AcraRatingActionsAlertEvidenceV1` stores only:

- opaque evidence and correlation identifiers;
- UTC recording timestamp;
- canonical source event name;
- global scope `global_acra_rating_actions_feed`;
- fired or recovered disposition;
- operational alert kind and severity;
- bounded occurrence/threshold counters;
- safe error code when applicable;
- immutable false-valued privacy and trading flags.

Pending, ignored, and cooldown-suppressed evaluations cannot be stored as
evidence. A fired record must meet its threshold and carry a safe error code.

## Privacy boundary

Evidence intentionally excludes:

- issuer identity;
- rating value or scale;
- outlook and rating action;
- press-release URL/id and publication date;
- account, portfolio, broker payload, raw HTML or upstream response;
- exception text;
- financial values and recommendations.

Opaque identifiers cannot be decoded into issuer or instrument identity.

## State and concurrency

The process-local store provides:

- retention from 60 to 604800 seconds;
- capacity from 1 to 256 records;
- oldest-first eviction;
- pruning on observe/read;
- explicit `clear()` and restart-empty behavior;
- one lifecycle `RLock` covering event evaluation, evidence mutation and sink
  handoff.

The event sink is invoked before any evidence sink for the same observation.
Sink failures are reduced to `sink_failure_count`; exception text is not
serialized or retained.

## Safety

The package adds no:

- HTTP route or GPT Action;
- frontend field;
- startup/background source call;
- webhook, email, Telegram, pager or external transport;
- broker call or write method;
- order, cancellation, transfer or withdrawal capability.

`app:app`, 14 GET Actions total (13 authenticated and public `/health`) and
`trading_methods=false` remain unchanged.

## Tests

Focused tests cover:

- pending without evidence;
- fired and recovered evidence;
- contract rejection of non-terminal dispositions;
- deterministic sink ordering;
- sink-exception redaction;
- privacy serialization;
- retention, capacity, eviction and clear;
- concurrent event/evidence pair ordering;
- absence of route, notification and broker-write surfaces.

## Next package

Production registration remains blocked until an exact existing ACRA caller and
owner are found. A later package may add another recognized rating agency only
through its own fixed-source contract, or advance production acceptance without
inventing a duplicate frontend or startup network call.
