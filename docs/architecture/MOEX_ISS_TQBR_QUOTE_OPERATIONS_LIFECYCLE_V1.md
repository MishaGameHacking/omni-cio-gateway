# MOEX ISS TQBR Quote Operations Evidence Lifecycle v1

## Status

PR-93 composes already-produced typed MOEX source/cache results with PR-91 observability and PR-92 global alert policy. It does not fetch MOEX or refresh a cache during import/startup.

## Deterministic lifecycle

For one typed source snapshot or cache result:

1. build one canonical PR-91 event;
2. evaluate it through the PR-92 global-only policy;
3. retain evidence only for `fired` and `recovered` evaluations;
4. call the optional event sink first;
5. call the optional evidence sink for each retained item second;
6. return one immutable batch with a redacted sink-failure count.

One lifecycle `RLock` remains held through pruning, alert-state mutation, evidence recording and sink calls. Concurrent calls therefore cannot interleave an evidence sink before its corresponding event sink.

## Evidence contract

`MoexQuoteAlertEvidenceV1` contains only:

- opaque evidence and correlation identifiers;
- recorded timestamp;
- canonical source event name;
- fixed scope `global_moex_tqbr_feed`;
- operational kind, severity and fired/recovered disposition;
- consecutive count and threshold;
- optional safe error code;
- immutable false safety flags.

`pending`, `ignored` and `suppressed_cooldown` cannot be stored as evidence. Fired evidence requires the threshold to be met and a safe error code.

## Privacy boundary

Evidence cannot represent:

- SECID, instrument key, short name, board or lot metadata;
- price, bid, ask, spread, currency, market timestamp or age;
- account, position, cash, broker payload or user identifier;
- raw JSON, HTTP body, credentials, exception type, exception text or traceback;
- trading authorization or external-notification state.

PR-92 is global-only because PR-91 excludes instrument identity. PR-93 does not reconstruct identity from correlation IDs or hidden state.

## Retention and capacity

Defaults:

- evidence retention: 86400 seconds;
- capacity: 64 evidence records;
- allowed retention: 60…604800 seconds;
- allowed capacity: 1…256.

Reads and observations prune evidence older than retention. Capacity overflow evicts the oldest item. `clear()` removes alert state and evidence. Process restart starts empty.

## Sink behavior

Sinks are optional callables. The event sink runs before evidence sinks. Sink exceptions are reduced to `sink_failure_count`; exception text is never copied into event, evaluation, evidence or batch output. There is no automatic retry.

## Non-goals

PR-93 adds no:

- webhook, email, Telegram, pager or external notification transport;
- route, request body, GPT Action or frontend field;
- source/cache scheduler or startup call;
- database, persistent queue or cross-process coordination;
- broker call, order, cancellation, transfer or withdrawal method.

## Compatibility invariants

- `app:app` remains unchanged;
- exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`;
- public MOEX data remains potentially delayed, non-real-time-guaranteed and informational-only;
- broker `getMarketSnapshot` remains primary for execution-style calculations.
