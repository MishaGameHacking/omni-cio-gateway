# Safe Observability v1

## Scope

PR-17 adds allowlist-based structured observability for Omni-CIO. It replaces
the existing portfolio contract shadow-validation text log with canonical JSON
while preserving the public response and runtime behavior.

It does not add a public route, external telemetry service, network exporter,
database, broker permission or trading capability.

## Design rule

Observability events are built from explicit typed metadata. Callers cannot pass
an arbitrary payload, dictionary, exception body, document content, holdings or
money amount into the event schema.

The event contract contains only:

- event time, name, component, severity and outcome;
- opaque correlation, request and action IDs;
- an optional already-masked account reference;
- duration;
- external provider/operation/status;
- latency, retries, rate-limit balance and circuit-breaker state;
- freshness, data quality and completeness;
- error code and exception class name;
- non-negative allowlisted count metrics;
- explicit `contains_sensitive_payload=false`;
- explicit `trading_methods=false`.

There is no free-form message field.

## Sensitive-data boundary

The contract has no fields for:

- API keys, authorization headers or cookies;
- full account identifiers;
- positions, holdings, instrument lists or portfolio composition;
- monetary balances or order amounts;
- private document content;
- raw request or response payloads;
- exception messages or stack traces;
- user confirmation text.

Pydantic `extra="forbid"` rejects unknown fields. `AccountReference` rejects an
identifier that is not visibly masked.

The existing portfolio shadow event remains stricter: it does not include even
the masked account ID because the established shadow tests prohibit account
identifiers in that log stream.

## Trace identifiers

`new_trace_id` creates an opaque UUID-based identifier with a normalized prefix.
It does not derive an ID from an account, token, instrument or request payload.

A caller may pass an existing correlation/request/action ID only when it matches
the restricted trace-ID pattern.

## External-call telemetry

Optional external metadata supports:

- success, degraded, failure, timeout and rate-limited states;
- latency in milliseconds;
- retry count;
- rate-limit remaining count;
- circuit-breaker state;
- freshness state.

A `not_called` record cannot claim latency, retries or rate-limit values.

## Canonical emission

`emit_safe_event` serializes the immutable contract as sorted compact JSON and
routes it to the requested logger level. It never passes `exc_info`, exception
text or arbitrary formatting arguments.

## Portfolio shadow integration

Portfolio contract shadow validation now emits
`portfolio.shadow.validation` with:

- success/degraded/rejected outcome;
- quality and completeness;
- error code and exception class for rejected validation;
- issue, warning, position, cash-balance and currency counts.

It does not log the source payload, account, names, instrument identifiers,
quantities, balances or valuation totals.

## Current limitations

PR-17 does not yet add request middleware or an external metrics backend. Those
require a separate integration PR with explicit retention, access-control and
operational ownership decisions.

Rate-limit and circuit-breaker fields are contracts only until the relevant
broker adapters expose those signals safely.

## Execution boundary

Every event has `trading_methods=false`. Observability code has no broker or
execution adapter and cannot create, replace, cancel or submit an order.

## Rollback

Revert the PR merge commit. No OpenAPI, database, Render, secret or broker-side
migration is required.
