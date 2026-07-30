# MOEX ISS TQBR Quote Alert Policy v1

## Status

PR-92 adds a bounded in-process operational alert policy over the pure PR-91 MOEX source/cache observability events. It does not fetch MOEX, refresh the PR-90 cache, emit events, persist evidence, or send notifications.

## Scope and identity

The policy has one immutable scope:

```text
global_moex_tqbr_feed
```

PR-91 intentionally excludes SECID, instrument identity and account context. PR-92 therefore evaluates only global component health. It cannot represent per-instrument alerts and must not reconstruct identity from correlation IDs, error text, logs or hidden state.

## Supported operational conditions

- source unavailable;
- cache unavailable;
- stale value explicitly exposed;
- refresh failed while a still-fresh cached value remains displayable.

There are no price, bid/ask, spread, return, volatility, volume, liquidity or portfolio thresholds.

## Canonical event gate

Known PR-91 event names are accepted only when their complete allowlisted shape is valid:

- exact event name and component;
- exact Moscow Exchange ISS provider and fixed operation;
- exact safe metric-name set;
- immutable public/delayed/non-realtime/informational flags;
- allowed outcome/severity/external-call/freshness profile;
- no account, request/action identity, quality/completeness payload or exception type.

An arbitrary `ObservabilityEventV1` that copies a PR-91 event name but changes this shape is rejected fail-closed with `MOEX_ALERT_EVENT_CONTRACT_INVALID`. Unrelated event names are ignored without creating state.

## State machine

Each of the four alert kinds has bounded process-local state:

- `pending` below the configured consecutive threshold;
- `fired` when the threshold is reached outside cooldown;
- `suppressed_cooldown` for repeated threshold-level signals during cooldown;
- `recovered` when a healthy event or a different condition clears an active sibling;
- `ignored` for unrelated or healthy events without active state.

Defaults:

- source unavailable threshold: 3;
- cache unavailable threshold: 2;
- stale exposure threshold: 2;
- refresh failure threshold: 3;
- cooldown: 900 seconds;
- state retention: 86400 seconds;
- capacity: exactly 4 global alert kinds.

One `RLock` protects pruning, sibling recovery, counters, firing, cooldown and clear. Out-of-order matching events fail closed. Counters saturate at 1,000,000.

## Retention and recovery

Pending state expires after retention. Active state is not pruned while its cooldown remains in force. The state is process-local and empty after restart. `clear()` removes all state.

Source health recovers only the source condition. Cache events share one recovery domain: a new canonical cache condition clears active sibling conditions before evaluating the new signal.

## Output boundary

`MoexQuoteAlertEvaluationV1` contains only:

- evaluation timestamp;
- canonical source event name;
- global scope;
- disposition, operational kind and severity;
- consecutive count, threshold and cooldown remaining;
- safe error code;
- immutable false safety flags.

It contains no SECID, instrument key, price, bid, ask, spread, currency, market timestamp, age, account, position, cash, raw JSON, exception payload or trading authorization.

## Non-goals

PR-92 adds no:

- automatic event emission;
- evidence store or operations lifecycle;
- webhook, email, Telegram, pager or external notification transport;
- route, request body, GPT Action or frontend field;
- startup/import network call;
- broker call, order, cancellation, transfer or withdrawal method.

## Compatibility invariants

- Render entrypoint remains `app:app`;
- exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`;
- broker `getMarketSnapshot` remains primary for execution-style calculations;
- public MOEX ISS limitations remain explicit: delayed data is possible and real-time is not guaranteed.
