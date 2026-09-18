# V10 Telegram Public-User Operations Readiness — Pre-Activation Evidence

Status: **ENGINEERING PRE-ACTIVATION BASELINE / LIVE USER EVIDENCE STILL REQUIRED**

Scope: issue #549, capability `telegram_login`, exact base `66ef57dedd07ad68d472cb205da6bb8e87528e94`.

## Accepted production architecture

The current Cloudflare production contour is already accepted through Production Release #84 / run `35379210101`:

- exact-main release gate: success;
- isolated staging rehearsal: success;
- production promotion: success;
- terminal fail-closed release DAG: success;
- rollback: not required;
- canonical `/healthz` and exact-release acceptance: success.

This establishes deploy/recovery mechanics for the current public architecture. It does not claim real Telegram user availability while the login flags remain disabled.

## Bounded launch envelope

The current application-level policy is intentionally finite:

| Dimension | Current bound |
|---|---:|
| Window | 60 seconds |
| Global API | 5000 requests/window |
| Health | 120 requests/window |
| Anonymous | 300 requests/window |
| Authenticated session | 600 requests/window/session |
| Telegram/VK provider start | 60 requests/window/provider |
| Provider callback | 120 requests/window/provider |
| Concurrent outbound provider calls | 8 |
| Remembered session limiter keys | 4096 |
| Cloudflare production Container instances | 1 |
| Container instance type | `lite` |

The limiter applies a global cap before attacker-controlled session lookup, resolves authenticated capacity only after server-side session verification, bounds provider starts/callbacks separately and fails fast when outbound-provider concurrency is exhausted.

This is an initial bounded safety envelope, not a throughput/SLA promise. Automatic capacity expansion or paid overage is not authorized by this evidence.

## Monitoring baseline

Cloudflare Workers metrics are the minimum always-available runtime telemetry used for traffic/error/usage awareness. Cloudflare documents Workers metrics as request/performance/usage telemetry in the Workers dashboard:
https://developers.cloudflare.com/workers/observability/metrics-and-analytics/

Stored Workers Logs and tracing are **not** made a prerequisite by this change. Cloudflare's current documentation states that Workers Logs have included quotas with paid overage and that tracing billing begins on 2026-10-01. Enabling additional stored telemetry without a cost decision would violate the project's no-uncontrolled-overage rule:
https://developers.cloudflare.com/workers/observability/logs/workers-logs/
https://developers.cloudflare.com/workers/observability/traces/
https://developers.cloudflare.com/workers/platform/pricing/

Operational detection therefore starts with:

- Cloudflare Workers metrics;
- canonical `/healthz`;
- exact-main production-release acceptance;
- provider-auth bounded error classes;
- release rollback to last-known-good;
- server-side logout/revoke and provider misconfiguration fail-closed behavior.

## Activation stop / rollback conditions

Do not proceed to `LIVE_OPERABLE` if any of these occur:

- Telegram start/callback cannot complete on the canonical domain;
- provider misconfiguration produces an unbounded/raw-secret error;
- canonical health/database readiness degrades;
- logout/revoke does not invalidate the correct session;
- cross-tenant read/write negative fails;
- release identity differs from accepted main;
- request/error pressure exceeds the bounded launch envelope without an accepted capacity change;
- the legal/privacy gate is still unresolved.

After source activation, the first real-user acceptance must capture sanitized evidence only: login, callback/session success, logout/revoke, provider outage/misconfiguration behavior and at least two-user tenant-isolation negatives. No raw Telegram subject, token, Client Secret, session cookie or private portfolio data may be recorded.
