# Omni-CIO V10 WP14 — Durable Job System

Status: **WP14 IMPLEMENTATION CONTRACT / EXIT GATE EVIDENCE REQUIRED**  
Block: **D — V10 Core and data**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Accepted baseline: `62a482246c8ca59e3a6f0489248e17676813b8c2`

## 1. WP identity

- Block: D — V10 Core and data.
- WP: WP14.
- Title: Durable Job System.
- Authorized by current program status: **YES**.
- Prior Exit Gate: WP13 PR #273 -> `d74b0177c730cad0a8e3a69d1504e226bedbac27`; post-WP13 Regression Shield #1456 / run `31370195951` SUCCESS; status PR #274 -> `62a482246c8ca59e3a6f0489248e17676813b8c2`; post-status Regression Shield #1457 / run `31372144270` SUCCESS.
- Next package remains locked: **WP15 — T-Invest read-only data layer and freshness**.

## 2. Accepted baseline

Protected runtime remains Omni-CIO v9.0.0 with `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and the accepted WP6–WP13 privilege/secret/recovery/Core/domain/PostgreSQL boundaries.

Relevant authorities:

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP14 section;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_RECOVERY_CONTRACT.md`;
- `docs/architecture/V10_WP13_POSTGRESQL_PERSISTENCE_CONTRACT.md`;
- `docs/operations/V10_WP13_POSTGRESQL_RUNBOOK.md`.

The accepted database baseline remains PostgreSQL 18 and schema `omni_cio_v10`.

## 3. Purpose

Make V10 background work observable, idempotent and recoverable after process crash or node restart by adding bounded job lifecycle semantics on top of the accepted WP13 PostgreSQL persistence layer.

## 4. Inputs and prerequisites

WP14 consumes rather than redefines:

- the WP13 PostgreSQL migration framework and `jobs` persistence shape;
- WP12 OWNER tenant identity;
- WP10 backup/restore/recovery boundary;
- WP9 supervision/restart policy;
- WP6 runtime least-privilege boundary;
- WP8 local secret-store separation.

Acceptance uses only synthetic OWNER-scoped job identities, payload hashes and worker identifiers. No broker token, Telegram token, recovery key, private portfolio payload, production database or full account ID is required.

## 5. Existing implementation to reuse

### PostgreSQL persistence and migrations

- path: `omni_cio/persistence/`;
- decision: **REUSE_AS_IS / EXTEND_BY_FORWARD_MIGRATION**;
- rule: migration `0001` is immutable; WP14 adds `0002+` and never edits accepted migration history.

### WP13 jobs relation

- path: `omni_cio/persistence/migrations/0001_initial.sql`;
- decision: **WRAP_ADAPTER**;
- accepted behavior: stable job identity/type/idempotency/payload-hash shape only;
- WP14 adds runtime lifecycle fields and an append-only job event journal through a new migration.

### WP9 supervision

- path: `infrastructure/windows/` and accepted WP9 operations contracts;
- decision: **REUSE_AS_IS**;
- rule: WP14 makes work recoverable after restart but does not replace Windows service/task supervision.

### Future domain handlers

Portfolio/market refresh, research, Watchtower, AI research, reconciliation, backup and health are registered job types from the Master Plan. Their business logic remains owned by the corresponding later/current domain packages. WP14 supplies durable orchestration semantics only.

No material V9 financial engine receives a `REWRITE_REQUIRED` decision in WP14.

## 6. Allowed changes

WP14 may change only what is required for the durable job runtime and acceptance evidence:

- `omni_cio/jobs/` lifecycle/repository/worker code;
- forward PostgreSQL migration(s) for jobs and job journal;
- persistence digest/recovery binding needed to include durable job state;
- deterministic WP14 tests and synthetic PostgreSQL rehearsal scripts;
- a focused Lenovo WP14 audit workflow;
- `pyproject.toml` static-analysis scope;
- WP14 architecture/operations documentation;
- WP13 migration-series acceptance probes only where required to remain valid after an authorized new migration.

## 7. Explicit non-goals

WP14 must not:

- implement WP15 T-Invest reads or request a broker read token;
- implement Web, Telegram, Cortex/AI provider, Research Collector or public ingress;
- implement broker-write/Real execution handlers;
- turn a job retry into broker-submit retry authority;
- change V9 financial formulas, `app:app`, `trading_methods=false` or `REAL_TRADING_ENABLED=false`;
- add Redis/QStash/Celery/another database or hosted queue as a competing durable-state stack;
- place secret values/private payloads/full account IDs in GitHub, logs or artifacts.

## 8. Interfaces and contracts

Canonical package: `omni_cio.jobs`.

### Job identity

A job has:

- canonical `job_id` derived from `job_type + idempotency_key` inside OWNER scope;
- `job_type` from the bounded WP14 registry;
- application-provided `idempotency_key`;
- `payload_sha256`, never raw private payload in the job row;
- `correlation_id` for sanitized tracing.

Equivalent scheduling replay returns the existing identity. Reuse of the same identity/idempotency key with conflicting payload/lifecycle policy fails closed.

### States

WP14 states are:

- `QUEUED`;
- `RUNNING`;
- `RETRY_WAIT`;
- `SUCCEEDED`;
- `FAILED_PERMANENT`;
- `RECONCILIATION_REQUIRED`;
- `CANCELLED`.

Only `QUEUED`/`RETRY_WAIT` are claimable. Only a current unexpired lease owner may heartbeat, complete or explicitly fail a `RUNNING` job.

### Lease and concurrency

Claim uses a PostgreSQL row lock with deterministic ordering and `SKIP LOCKED`, then changes the row in the same transaction. A lease records owner and expiry. A stale worker loses authority when the lease expires or the row transitions away from `RUNNING`.

### Retry classification

- `RETRYABLE`: bounded retry while `attempts < max_attempts`, otherwise `FAILED_PERMANENT`;
- `PERMANENT` and `VALIDATION`: immediate `FAILED_PERMANENT`;
- `AMBIGUOUS`: immediate `RECONCILIATION_REQUIRED`, never blind retry.

Lease-expiry recovery is per-job policy:

- `RETRY_SAFE`: return to durable retry only while attempts remain;
- `RECONCILE`: transition to `RECONCILIATION_REQUIRED`.

This policy is orchestration safety only. It never authorizes automatic broker resubmission.

### Job journal

Every lifecycle transition writes an append-only `job_events` row containing only canonical job identity, state transition, attempt, sanitized worker/error class, timestamp and a deterministic record hash. `UPDATE`/`DELETE` of journal rows is database-rejected.

## 9. Data/persistence effects

- migration required: **YES**;
- forward migration: WP13 `0001` -> WP14 `0002_durable_jobs`;
- accepted migrations are immutable;
- rollback strategy: forward recovery or restore a verified compatible backup, not destructive history rewrite;
- private-data handling: job rows store hashes/identities/state, not raw private job payloads;
- backup/recovery consequence: deterministic durable-state digest includes mutable job state and append-only job events, and synthetic backup/restore must preserve them exactly.

## 10. Security/authority effects

WP14 adds no external authority.

- secret access: unchanged; none required by generic job runtime;
- broker authority: unchanged;
- OS/runtime privileges: unchanged;
- GitHub permissions: unchanged;
- Web/Telegram ingress: none;
- AI tool authority: none;
- Real execution path: unchanged and disabled by existing kill switch.

A process restart, job recovery or retry is never Real approval or broker-submit authority. Any future broker-affecting handler must apply the owning execution/reconciliation contract independently.

## 11. Normal-path acceptance tests

Tests must prove at minimum:

- clean PostgreSQL 18 migration through current WP14 schema;
- equivalent duplicate schedule returns one durable job;
- a due job is claimed once with attempts incremented and a lease established;
- heartbeat extends only the current lease;
- successful completion is durable and journaled;
- retryable failure schedules a bounded later attempt;
- state/event digest is deterministic;
- backup/restore preserves current migration state and durable job digest.

## 12. Negative/failure tests

Tests must reject/prove at minimum:

- conflicting idempotency replay;
- two workers claiming the same job;
- wrong/stale worker heartbeat or completion;
- lease-expired completion;
- permanent/validation error retry loops;
- retry beyond `max_attempts`;
- ambiguous failure auto-retry;
- unsafe crash recovery for `RECONCILE` jobs;
- `UPDATE`/`DELETE` of job journal;
- invalid lifecycle state/lease combinations at the database layer;
- secret/private payload exposure in acceptance evidence;
- any restart alone producing broker-write authority.

## 13. Observability

WP14 exposes sanitized durable state only:

- job ID/type/state;
- correlation ID;
- attempts/max attempts;
- next-run/lease timing;
- sanitized error class;
- append-only transition history.

Raw payloads, credentials and private portfolio contents are excluded from logs and CI evidence.

## 14. CI routing

- Fast hosted checks: normal path-aware feedback when hosted capacity permits.
- Hosted clean-room compatibility: existing policy; hosted startup billing failure is infrastructure failure, not PASS.
- Lenovo authoritative checks: exact-head `V10 authoritative merge gate` plus focused PostgreSQL 18 WP14 crash/lease/idempotency/recovery rehearsal.
- GPU AI eval required: **NO**.
- Release/recovery matrix required: **YES, bounded to synthetic PostgreSQL job-state backup/restore parity**.

## 15. Rollback/recovery

Code rollback before private WP14 state exists returns to the accepted WP13 baseline. Once job state exists, do not delete job/audit/reconciliation truth to run older code. Use a reviewed forward repair or verified backup restore. On restart, expired work follows its persisted recovery policy; ambiguous work remains blocked for reconciliation.

V9 remains the protected product rollback while Block D is incomplete.

## 16. Exit Gate

WP14 PASS requires on the exact reviewed PR head:

1. forward migration from accepted WP13 schema succeeds on PostgreSQL 18;
2. durable job state/lease/retry/journal model exists with DB constraints;
3. duplicate scheduling is idempotent and conflicting replay fails closed;
4. concurrent claim proves a single owner;
5. crash/lease-expiry recovery proves `RETRY_SAFE` vs `RECONCILE` behavior;
6. stale workers cannot mutate jobs after lease loss;
7. permanent/validation/ambiguous errors never enter unbounded retry;
8. append-only job journal rejects mutation;
9. backup/restore preserves migration and durable job-state digest;
10. no WP15/Web/Telegram/Cortex/Real feature work or broker authority is introduced;
11. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged;
12. authoritative Self-Hosted Windows CI and focused WP14 PostgreSQL gate are GREEN;
13. dependency audit, SAST and tracked-secret scan are GREEN through the authoritative gate;
14. zero unresolved blocking review threads;
15. full PR diff reviewed;
16. squash merge completes;
17. post-merge Regression Shield succeeds on the exact resulting `main` SHA.

## 17. Required acceptance evidence

Record:

- exact PR head SHA;
- migration series/version digest;
- duplicate/concurrent-claim/crash/lease/retry test results;
- source/restored durable-state digest;
- exact authoritative Self-Hosted Windows CI run;
- exact focused WP14 audit run;
- hosted-lane infrastructure classification if applicable;
- zero blocking review threads;
- merge SHA;
- exact post-merge Regression Shield run.

No OWNER physical action or real secret input is required for WP14.

## 18. Documentation/status updates

The implementation PR owns this contract, runbook, job code/migration/tests and focused acceptance evidence. Official `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` advances only in the separate post-merge status synchronization after the post-WP14 Regression Shield is GREEN.

## 19. Next WP unlock

Only **WP15 — T-Invest read-only data layer and freshness** may be unlocked, and only after all WP14 Exit Gate evidence above is accepted.

## 20. Scope-discovery rule

Broker reads, Web, Telegram, AI, research business logic, public ingress or Real execution discovered during WP14 is future-WP work unless strictly required for durable job correctness. It must not be implemented opportunistically.

## Reviewed technical references

The implementation relies on PostgreSQL 18 row-lock semantics. PostgreSQL documents `FOR UPDATE ... SKIP LOCKED` as appropriate for avoiding lock contention with multiple consumers of a queue-like table while warning that it is not a general-purpose consistent view. Job claim therefore locks and updates the selected row inside one transaction and uses deterministic ordering. Psycopg transaction contexts are used so claim/transition/journal changes commit atomically or roll back together.