# MOEX ISS TQBR Quote Observability v1

## Status

PR-91 adds pure allowlisted observability builders over the already typed PR-89 source and PR-90 cache results. The builders do not fetch MOEX, refresh a cache, emit logs automatically, register a route, or change a public Action.

## Purpose

Operational telemetry must make source/cache health visible without leaking market values, instrument identity, account context, raw upstream payloads, or exception text.

## Source event

`build_moex_iss_quote_source_event` maps one `MoexIssTqbrQuoteSnapshotV1` into an immutable `ObservabilityEventV1`.

Allowed fields:

- fixed event/component/provider/operation identifiers;
- success or failure outcome;
- info or error severity;
- optional validated duration;
- external-call status;
- safe source error code;
- safe count/boolean metrics for source availability and immutable feed limitations.

The event intentionally uses `FreshnessTelemetry.UNKNOWN`. PR-89 source availability alone does not prove that the public market value is fresh enough for any caller.

## Cache event

`build_moex_iss_quote_cache_event` maps one `MoexIssTqbrQuoteCacheResultV1` into one immutable event.

Mappings:

- fresh cache hit: success/info, external call `not_called`, freshness `fresh`;
- successful refresh: success/info, external call `success`, freshness `fresh`;
- failed refresh with still-fresh cached value: degraded/warning, external call `failure`, freshness `fresh`;
- explicit stale exposure: degraded/warning, external call `failure`, freshness `stale`;
- unavailable: failure/error, external call `failure`, freshness `unknown`.

Safe metrics are limited to:

- cache hit;
- refresh attempted;
- refresh succeeded;
- stale physically available;
- stale exposed;
- display allowed;
- public feed;
- delayed data possible;
- real-time guaranteed;
- informational-only.

## Privacy and safety boundary

The builders never copy:

- `SECID`, short name, instrument key, lot size, decimals, board identity;
- last price, bid, ask, spread, currency, `quote.as_of`, retrieved timestamp or age;
- account, position, cash, broker payload or user identifier;
- raw JSON, HTTP body, cookie, credential, Authorization header;
- exception type, exception text, traceback or arbitrary upstream message.

The canonical event may serialize `account=null` because that field exists in the shared immutable event contract; no account value is accepted by these builders.

## Feed limitations

Every event keeps immutable operational metrics equivalent to:

- `public_unauthenticated_feed=true`;
- `delayed_data_possible=true`;
- `realtime_guaranteed=false`;
- `informational_use_only=true`.

Moscow Exchange documents ISS as a web API for market/historical data and states that free access is delayed while real-time access requires subscription. These source limitations are therefore operational facts, not optional UI labels.

## Non-goals

PR-91 does not add:

- automatic event emission;
- logger or external sink registration;
- alert policy, webhook, email, Telegram or pager transport;
- source/cache lifecycle orchestration;
- public route, request body, GPT Action or frontend field;
- broker call, order, cancellation, transfer or withdrawal method.

## Compatibility invariants

- stable Render entrypoint remains `app:app`;
- exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`;
- no network call occurs at import/startup;
- broker `getMarketSnapshot` remains primary for execution-style calculations.
