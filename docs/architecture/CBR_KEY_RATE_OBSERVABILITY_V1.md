# Safe CBR key-rate observability v1

## Purpose

PR-86 adds allowlisted structured telemetry for the PR-84 official Bank of
Russia source and the PR-85 key-rate cache lifecycle. The package reports
operational state without logging the key-rate value or upstream payload.

It reuses the existing immutable `ObservabilityEventV1`,
`ExternalCallTelemetryV1` and `build_safe_event` contracts. It does not create a
new logging format, HTTP route, GPT Action or frontend field.

## Source event

`build_cbr_key_rate_source_event(...)` maps one typed PR-84 snapshot to:

- success/info when the official source returned an available snapshot;
- failure/error with one fixed source error code when unavailable;
- provider `Bank of Russia DailyInfo`;
- operation `KeyRateXML`;
- optional bounded latency;
- fresh/unknown freshness state;
- safe count metrics only:
  - `cbr.observation_count`;
  - `cbr.source_available`.

The event does not include any observation value, effective date, requested date
range, XML, SOAP Fault, exception text or account context.

## Cache event

`build_cbr_key_rate_cache_event(...)` maps one typed PR-85 result:

- fresh cache hit: success/info, external call `not_called`;
- successful refresh: success/info, external call `success`;
- failed forced refresh while cached data remains fresh: degraded/warning,
  external call `failure`, freshness still `fresh`;
- explicit stale exposure: degraded/warning with freshness `stale`;
- unavailable result: failure/error with no displayable value.

Safe metrics are limited to counts and boolean indicators:

- `cbr.observation_count`;
- `cbr.cache_hit`;
- `cbr.refresh_attempted`;
- `cbr.refresh_succeeded`;
- `cbr.stale_exposed`;
- `cbr.display_allowed`.

No metric contains the rate, date range, portfolio/account or monetary data.

## Error precedence

When source and cache error codes are both present, the source error code is the
primary event error. Otherwise the fixed cache error code is used. Exception
class names and exception messages are not attached.

A failed or rejected event always contains a safe error code as required by the
base observability contract. Degraded warnings may also include a safe code.

## Latency semantics

- overall event `duration_ms` may represent the local source/cache operation;
- external-call latency is attached only when an upstream call was attempted;
- a fresh cache hit uses external status `not_called` and cannot carry external
  latency or retry activity.

Durations must be finite non-negative `Decimal` values.

## Privacy and safety

The serialized event contains no:

- `rate_percent` or numeric key-rate value;
- effective/requested dates;
- raw XML or SOAP content;
- upstream fault or exception text;
- credentials, full account ID or broker payload;
- trading authorization or order data.

All events keep `contains_sensitive_payload=false` and
`trading_methods=false`.

## Compatibility

- `app:app` is unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no request body, operation ID or public response field is added;
- no T-Invest call or broker write method is introduced;
- event builders are pure and do not emit automatically; a later operations
  package may connect them to an existing logger/telemetry sink.

## Remaining operations boundary

PR-86 builds typed events but intentionally does not configure alert transport,
retention or an external telemetry service. A later package must define:

1. exact emission points around PR-84/85 calls;
2. bounded logging/metrics retention;
3. alert thresholds for repeated unavailable/stale outcomes;
4. rate limiting and deduplication;
5. production acceptance evidence without sensitive payloads.

## Tests

Focused tests cover available/unavailable source events, fresh cache hits,
successful refresh, degraded fresh-cache fallback, stale and unavailable cache
states, latency/type guards, serialized payload exclusions and absence of HTTP or
broker-write surfaces.

## Rollback

Revert the PR-86 squash commit. No database, secret, dependency, OpenAPI or
Render migration is required.
