# V10 Timeweb Post-Merge Production Acceptance Runbook

Status: branch-local P6 implementation in PR #584.

P6 is the final evidence-composition gate. It does not create provider resources, mutate
DNS, write secrets, migrate PostgreSQL or activate Telegram.

Final chain:

`exact accepted main SHA -> P2 Timeweb candidate -> P3 PostgreSQL 18 -> P4 omnicio.ru ->
P5 Telegram LIVE_OPERABLE -> P6 acceptance seal`.

Before `accept`, collect sanitized SHA-256 evidence for P2, P3, P4, P5 readiness, P5
real login/logout/re-login and cross-tenant negative acceptance, plus rollback evidence
and a distinct last-known-good release SHA.

The workflow first proves the dispatched SHA is still exact protected `main`, then probes
`/livez`, `/healthz` and the sole enabled Telegram provider. Any SHA/runtime/provider
drift is `OUT_OF_SYNC / DEPLOYMENT_BLOCKED`.

Acceptance produces a deterministic SHA-256 seal bound to the exact source SHA,
`https://omnicio.ru`, the Telegram callback, all P2-P5 evidence and rollback evidence.
Secret values are never inputs or artifacts.

On RED, production stays on last-known-good. P6 never grants broker write,
`trading_methods`, `REAL_TRADING_ENABLED`, WEB-VISUAL or WP23+ authority.
