# V10 WP22 — System/Admin UI Execution Contract

Status: **WP22 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Protected runtime baseline: `app:app`  
Authority expansion: **none**

## 1. Identity

- Work Package: **WP22 — System/Admin UI**.
- Block: **E — Web Platform**.
- Accepted base: `4bb18b7cddc33b8d79d168103c747852b8624b23` after WP21 acceptance/status synchronization and exact-main post-status Regression Shield.
- Branch: `v10/wp22-system-admin-ui`.
- Next package remains locked: **WP22A — Public ingress and Web security hardening**.

## 2. Purpose

WP22 replaces the thin `/system` build card with one OWNER-only local/private operating surface for ordinary diagnostics. It aggregates already accepted runtime, persistence, recovery, durable-job and READ-broker state so the OWNER can understand normal system health without GitHub or PowerShell.

WP22 is a read projection, not a second control plane. It does not create another database, queue, secret store, Web application, monitoring SaaS or broker authority path.

## 3. Preconditions and reuse audit

| Capability | Accepted authority | WP22 decision |
|---|---|---|
| authenticated local/private Web shell and server-side sessions | WP17 | **REUSE_AS_IS** |
| PostgreSQL migration state | WP13 | **READ_PROJECTION_ONLY** |
| durable job lifecycle and sanitized error classes | WP14 | **READ_PROJECTION_ONLY** |
| T-Invest verified READ connections | WP15/WP17 | **READ_PROJECTION_ONLY** |
| Watchtower durable job observations | WP14 plus accepted Watchtower contracts | **READ_PROJECTION_ONLY** |
| backup objectives and durable BACKUP job state | WP10/WP14 | **READ_PROJECTION_ONLY** |
| free-space limits | WP5 | **REUSE_THRESHOLDS** |
| NVIDIA temperature limit/probe | WP5 | **BOUNDED_READ_ONLY_PROBE** |
| Web build identity | WP16/WP17 | **REUSE_AS_IS** |
| `/settings` READ-token provisioning and session controls | WP17 | **REUSE_AS_IS / DO_NOT_DUPLICATE** |
| Real/broker-write authority | later execution WPs | **DISPLAY_ONLY / DO_NOT_EXPAND** |
| Telegram runtime | WP23+ | **LOCKED_FUTURE_WP** |
| AI/Cortex runtime | WP27+ | **LOCKED_FUTURE_WP** |

No material V9 financial engine is rewritten by WP22.

## 4. Allowed changes

WP22 may add only what is required for the local/private system operating surface and its acceptance evidence:

- one tenant-scoped `GET /api/v10/web/system-status` read route;
- one sanitized system-status read service over accepted sources;
- the existing `/system` React surface and typed browser contract;
- bounded recent-job/recent-error projections;
- deterministic unit/browser tests;
- a focused exact-head WP22 audit workflow;
- WP22 architecture/operations documentation.

No database migration is required.

## 5. Explicit non-goals

WP22 must not:

- implement WP22A TLS/public ingress/external identity hardening;
- activate Telegram before WP23+;
- activate AI/Cortex before WP27+;
- add a kill-switch mutation endpoint or a new admin command plane;
- accept/store broker-write credentials;
- add order/trade/transfer authority;
- expose secrets, secret references, raw exception text, full account identifiers, private portfolio payloads, backup mount paths or recovery material;
- fake temperature, backup, service-health or deployment observations;
- change `app:app`, `trading_methods=false` or the required `REAL_TRADING_ENABLED=false` safety baseline;
- weaken V9 rollback or the local/private TrustedHost boundary.

## 6. System-status API

`GET /api/v10/web/system-status` exists only inside the accepted local/private Web application.

The route:

1. resolves the server-side Web session;
2. derives tenant scope only from that session;
3. returns an allowlisted diagnostics DTO;
4. uses `Cache-Control: no-store` and `Pragma: no-cache`;
5. accepts no client-supplied tenant/account identity;
6. has no POST/PUT/PATCH/DELETE companion route.

The DTO may contain only sanitized release/deploy metadata, DB/migration state, backup summary, service observations, resource observations, safety-state observations and bounded durable job/error metadata.

## 7. Failure-state contract

Unknown state is never converted into `READY`.

WP22 uses explicit availability values:

- `AVAILABLE` — observation was obtained from the accepted source;
- `NOT_CONFIGURED` — an allowed current capability has no configuration/state yet;
- `NOT_AVAILABLE` — the current observation could not be proven;
- `LOCKED_FUTURE_WP` — the owning future package has not been authorized.

A live migration mismatch or critical disk condition is `BLOCKED`. Query/probe failures are sanitized and reported as degraded/unavailable. Telegram and AI being `LOCKED_FUTURE_WP` do not falsely count as current-WP runtime failures.

## 8. PostgreSQL and migrations

WP22 compares the live migration series from `current_migration_state()` with the exact source-controlled `discover_migrations()` series.

- exact match -> `READY`;
- mismatch -> `BLOCKED`;
- inability to query/verify -> `DEGRADED / NOT_AVAILABLE`.

The UI does not run migrations and does not mutate PostgreSQL.

## 9. Backup and recovery projection

The accepted recovery objectives remain:

- **RPO: 60 minutes**;
- **RTO: 240 minutes**.

WP22 may show only the latest tenant-scoped durable `BACKUP` job that reached `SUCCEEDED`, plus the accepted objectives. It does not read backup payloads, mount points, BitLocker material, recovery keys or secret-store contents. Missing successful durable observation is explicit `NOT_AVAILABLE`, not fabricated success.

## 10. Resource projection

Disk free-space state reuses the WP5 system-volume policy:

- warning below 20% or 50 GiB free;
- block below 10% or 20 GiB free.

GPU temperature may be read with a bounded, no-shell `nvidia-smi` probe where available. The accepted WP5 GPU ceiling is 87 °C. Missing or unsupported temperature telemetry remains `NOT_AVAILABLE`; WP22 does not synthesize a CPU/GPU temperature.

## 11. Service projection

The service-health section includes only bounded status metadata for:

- local/private Web;
- PostgreSQL;
- T-Invest **READ** connection state without account identifiers or credentials;
- Watchtower from the latest durable Watchtower job observation;
- Telegram as `LOCKED_FUTURE_WP` until WP23+;
- AI/Cortex as `LOCKED_FUTURE_WP` until WP27+.

WP22 does not start, stop or configure those services.

## 12. Safety / kill-switch boundary

WP22 exposes safety state for diagnosis only. There is no browser mutation control and no mutation API.

Required invariants remain:

- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker-write authority absent from the Web application;
- public ingress absent before WP22A.

If an observable runtime safety setting contradicts a required invariant, the system surface must fail closed rather than mask the contradiction.

## 13. Recent jobs and errors

The diagnostics response is bounded to at most:

- 12 recent jobs;
- 8 recent errors.

Allowed fields are job type, lifecycle state, attempts/max attempts, sanitized WP14 `error_class` and timestamp. Raw job payloads, raw exception strings, worker identities, credentials, private portfolio data and full account IDs are excluded.

## 14. Security and authority effects

WP22 introduces no new external ingress and no new money authority.

- Web session model: unchanged;
- tenant model: unchanged and OWNER-only;
- broker authority: READ projection only;
- secret access: none added;
- database write authority: none added;
- public Internet listener: none added;
- Telegram/AI runtime authority: none added;
- Real execution: unchanged and disabled by the required safety baseline.

## 15. Normal-path acceptance tests

Tests must prove at minimum:

- authenticated OWNER session can read the system-status contract;
- tenant scope comes only from the server-side session;
- exact DB migration state is visible;
- RPO/RTO and latest successful backup observation are visible;
- T-Invest READ/Watchtower service observations are visible without private identifiers;
- Telegram/AI remain explicitly future-locked;
- disk/temperature availability is explicit;
- Web/build/runtime identity is visible where available;
- recent jobs/errors are bounded;
- `/system` is usable at accepted browser sizes and contains no mutation controls.

## 16. Negative/failure acceptance tests

Tests must prove at minimum:

- unauthenticated access returns 401;
- migration mismatch is `BLOCKED`;
- critical low disk is `BLOCKED`;
- failed broker/read-state query does not leak exception text;
- missing temperature stays unavailable instead of being fabricated;
- system-status API failure leaves the authenticated shell usable and explicitly non-READY;
- no token/password/authorization/full broker-account identifier enters the diagnostics DTO/browser evidence;
- no WP22 action can enable broker write, Real execution, public ingress, Telegram or AI.

## 17. CI routing

WP22 merge eligibility requires:

- dedicated exact-head `V10 WP22 System Admin Audit` on the Self-Hosted Windows runner;
- authoritative inherited V10 merge/security gates;
- Web typecheck/lint/unit/build/Playwright evidence;
- Python Ruff format/lint, mypy and WP22 tests;
- Web dependency audit plus inherited dependency/SAST/tracked-secret checks;
- exact reviewed PR head identity;
- zero unresolved blocking review threads;
- full diff review.

Hosted startup/billing failures remain infrastructure failures and are never called PASS. The dedicated audit explicitly checks out `github.event.pull_request.head.sha` rather than relying on the default pull-request merge ref, preserving the project exact-head rule.

## 18. Rollback/recovery

WP22 has no schema migration and writes no new durable state. A code rollback removes the diagnostics projection and returns to the accepted pre-WP22 system surface without discarding PostgreSQL/job/recovery truth.

V9 remains the protected product rollback while V10 is not finally accepted.

## 19. Exit Gate

WP22 PASS requires on the exact reviewed PR head:

1. the `/system` operating surface shows the Master Plan WP22 diagnostic categories;
2. unavailable/degraded/future-locked states are explicit and never fabricated as READY;
3. safety/kill-switch information is read-only and no authority is expanded;
4. recent jobs/errors are bounded and secret/private-data safe;
5. ordinary diagnostics no longer require GitHub or PowerShell;
6. dedicated WP22 and authoritative Self-Hosted Windows gates are GREEN;
7. inherited dependency audit, SAST and tracked-secret scan are GREEN;
8. zero unresolved blocking review threads and full focused diff review;
9. exact-head squash merge completes;
10. the exact resulting `main` SHA passes post-merge Regression Shield.

Only then may the separate official status transition authorize **WP22A**.

## 20. OWNER action

No OWNER physical action, secret input or irreversible operation is required for WP22 software implementation. Hardware/runtime telemetry that cannot be safely observed remains explicit `NOT_AVAILABLE`; it is not a reason to fabricate evidence or weaken the gate.

## Reviewed technical references

- GitHub Actions event semantics: `https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows`.
