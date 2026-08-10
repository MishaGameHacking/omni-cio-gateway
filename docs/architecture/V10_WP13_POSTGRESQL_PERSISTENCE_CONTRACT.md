# V10 WP13 — PostgreSQL persistence and migrations

Status: **WP13 IMPLEMENTATION CONTRACT / EXIT GATE EVIDENCE REQUIRED**  
Block: **D — V10 Core and data**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Accepted baseline: `1e8c65cd1f4d0a6ba0ea2ebea92c7b9ff1dcc0c2`  
Prior Exit Gate: WP12 PR #271 -> `365b49ad1ef428f4b534555cf387f2d3504a770f`; Regression Shield #1454 / `31332149156` SUCCESS; status PR #272 -> `1e8c65cd1f4d0a6ba0ea2ebea92c7b9ff1dcc0c2`; Regression Shield #1455 / `31357236365` SUCCESS.

## 1. WP identity

- Block: D — V10 Core and data.
- WP: WP13.
- Title: PostgreSQL persistence and migrations.
- Authorized by current program status: **YES**.
- Next package remains locked: **WP14 — Durable Job System**.

## 2. Accepted baseline

Protected runtime remains Omni-CIO v9.0.0 with `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and the accepted WP6–WP12 privilege/secret/recovery/Core/domain boundaries.

Relevant authorities:

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP13 section;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_DATA_FLOW.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_RECOVERY_CONTRACT.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.md`;
- `docs/architecture/V10_WP10_RECOVERY_CONTRACT.json`;
- `docs/architecture/V10_WP12_CANONICAL_DOMAIN_MODEL_CONTRACT.md`.

Selected database baseline remains PostgreSQL major 18, reviewed patch 18.4. The migration and schema design is PostgreSQL-specific and does not introduce a second database stack.

## 3. Purpose

Bind the accepted WP12 canonical identity/scope contracts to one versioned local PostgreSQL durable-state schema with deterministic migrations, exact numeric semantics, append-only audit protection, concurrency/idempotency guarantees and tested WP10 backup/restore compatibility.

## 4. Inputs and prerequisites

WP13 consumes, rather than redefines:

- `omni_cio.contracts.v1.domain` canonical OWNER/tenant/portfolio/policy/instrument identities and UTC semantics;
- accepted V9 financial payload contracts as the authoritative calculation semantics;
- PostgreSQL 18.4 selected by WP2 and installed/validated by Block C;
- WP10 logical backup/restore mechanism, RPO/RTO and encrypted off-device recovery boundary;
- WP6 least-privilege separation and WP8 secret-store separation.

Acceptance uses only synthetic database names, canonical IDs, hashes and payload references. No broker token, Telegram token, recovery key, production portfolio payload or full broker account ID is needed.

## 5. Existing implementation to reuse

### Canonical domain model

- path: `omni_cio/contracts/v1/domain.py`;
- decision: **WRAP_ADAPTER**;
- rule: persistence mirrors accepted WP12 identity/scope relationships and must not silently change them.

### Financial payload contracts and engines

- paths: accepted `omni_cio/contracts/v1/*` financial DTOs and V9/Core engines;
- decision: **REUSE_AS_IS / WRAP_ADAPTER as already accepted by owning WPs**;
- rule: WP13 stores canonical references/content hashes and does not reinterpret financial formulas.

### PostgreSQL backup/recovery

- paths: `infrastructure/windows/run_wp10_backup.ps1`, `infrastructure/windows/rehearse_wp10_recovery.ps1`, WP10 recovery contract/runbook;
- decision: **REUSE_AS_IS with WP13 database binding only**;
- rule: WP13 may bind the product database identity/schema contract; scheduled job ownership/activation remains WP14.

No material V9 component receives a `REWRITE_REQUIRED` decision in WP13.

## 6. Allowed changes

WP13 may change only what is required for PostgreSQL persistence and its acceptance evidence:

- `omni_cio/persistence/` PostgreSQL migration/repository code;
- versioned SQL migrations under `omni_cio/persistence/migrations/`;
- root dependency source/locks only for the reviewed PostgreSQL Python driver if required;
- deterministic WP13 tests/scripts and a focused Lenovo PostgreSQL integration workflow;
- `pyproject.toml` static-analysis scope;
- WP10 production database binding metadata/checks while keeping WP14 task identity locked;
- WP13 architecture/operations documentation;
- parity/reuse metadata only where a persistence-specific clarification is necessary.

## 7. Explicit non-goals

WP13 must not:

- implement the WP14 durable job worker, leases, retry engine, scheduler or crash-recovery state machine;
- implement the WP15 T-Invest read adapter or request a read token;
- activate Web, Telegram, Cortex/AI or public/multi-user operation;
- add external hosted database/queue/SaaS dependencies;
- modify V9 financial formulas or broker-write authority;
- activate Real execution or change `REAL_TRADING_ENABLED=false`;
- change `app:app` or the protected Render/V9 runtime;
- place real secrets/private portfolio payloads/full account IDs in GitHub, CI logs or artifacts.

The `jobs` relation required by the Master Plan is persistence shape only. WP14 owns runtime job semantics.

## 8. Interfaces and contracts

Canonical persistence package: `omni_cio.persistence`, schema family `omni_cio_v10`, migration series `0001+`.

### Migration contract

- migrations are immutable, ordered and SHA-256 checked;
- applied migration identity is stored in a dedicated metadata table;
- a transaction-scoped PostgreSQL advisory lock serializes migration application;
- migration checksum drift fails closed;
- clean bootstrap applies the full series from an empty database;
- rollback policy is **forward recovery by default**, which is explicitly allowed by the WP13 Master Plan; destructive down-migrations are not invented merely to satisfy symmetry;
- a failed migration transaction must not leave a migration recorded as applied.

### Numeric policy

- Python money/price/quantity values remain `Decimal`;
- PostgreSQL exact values use `numeric`, never `real`, `double precision` or PostgreSQL `money` for canonical financial facts;
- initial canonical quantity policy is `numeric(38,18)`; future domain-specific money/price columns must declare an explicit precision/scale before introduction;
- values outside declared precision/scale fail rather than being silently converted to binary floating point.

### Time policy

- persisted instants use `timestamptz` and are normalized/returned as timezone-aware UTC values at the contract boundary;
- source/broker/published/retrieved/local-receive distinctions from WP12 are preserved as separate columns where present.

### Idempotency/replay policy

For immutable identity records, replay of the same canonical ID with byte-for-byte equivalent persisted semantics is idempotent. The same ID with conflicting scope/hash/content is an error, never an overwrite. Concurrent writers are resolved by database uniqueness/constraints plus conflict verification.

### Append-only policy

Audit-sensitive records are protected by database triggers rejecting `UPDATE` and `DELETE` through the application schema. Corrections require a new version/revision/event according to the owning domain contract; silent history rewrite is forbidden.

### Cache/retention policy

Research/market cache rows carry explicit expiry/retention timestamps and indexed lookup/expiry fields. Retention deletion is allowed only for cache-class tables, never audit-sensitive decision/plan/execution/journal truth.

## 9. Data/persistence effects

- migration required: **YES**;
- forward migration: empty database -> ordered immutable SQL migrations;
- rollback/forward-recovery rule: restore accepted backup or apply a reviewed forward repair migration; do not erase broker/reconciliation truth to force an old schema;
- private-data handling: local PostgreSQL/private encrypted backups only; GitHub tests are synthetic;
- backup/recovery consequence: WP10 logical backup/restore must recognize the WP13 product schema/database binding and prove restored schema version plus deterministic state digest/revisions.

Initial schema must cover the Master Plan persistence families:

- tenant/user/broker-account/portfolio/instrument/policy identity roots needed for referential integrity;
- portfolio snapshots;
- positions;
- evidence;
- research cache/metadata;
- incidents and incident-evidence relations;
- decisions and decision-evidence relations;
- plans;
- executions;
- journal;
- jobs persistence shape only;
- system-health observations;
- migration metadata.

## 10. Security and authority effects

WP13 adds private durable-state access but **does not add any broker authority**.

- secret access: database credentials remain local/runtime-only and are not committed; connection settings accept a separately provisioned secret source;
- broker authority: unchanged;
- OS/runtime privileges: no administrator requirement for ordinary persistence access;
- GitHub permissions: unchanged;
- Web/Telegram ingress: none;
- AI tool authority: none;
- Real execution path: unchanged and disabled by existing kill switch.

Database corruption/unavailability must fail closed for state mutation. Tests/logs expose only synthetic IDs and sanitized diagnostics.

## 11. Normal-path acceptance tests

Tests must prove at minimum:

- empty PostgreSQL 18 database migrates to the current schema version;
- all required relations, constraints and indexes exist;
- WP12 OWNER-scoped synthetic catalog persists and round-trips without identity/scope drift;
- `Decimal` quantity values round-trip exactly through `numeric(38,18)`;
- UTC/source timestamps round-trip with their distinct semantics;
- immutable replay of equivalent records is idempotent;
- state digest/revision evidence is deterministic;
- bounded research/health cache retention affects only eligible cache/observation rows;
- WP10 logical backup/restore of a migrated synthetic DB preserves migration version and state digest.

## 12. Negative/failure tests

Tests must reject at minimum:

- unsupported PostgreSQL major;
- migration checksum drift or duplicate version identity;
- migration race applying the same version twice;
- non-OWNER tenant rows;
- FK/scope violations and duplicate canonical identities;
- float canonical financial storage/types;
- update/delete of append-only audit rows;
- same immutable ID replayed with conflicting hash/scope/content;
- duplicate positions for the same `(snapshot_id, instrument_id)`;
- cross-portfolio policy/evidence/decision/plan/execution/journal references;
- missing parent identity;
- connection/migration failure incorrectly reported as success;
- backup restore whose migration version/state digest does not match source.

## 13. Observability

WP13 emits only sanitized persistence diagnostics:

- schema version/current migration count;
- database readiness state;
- migration version/checksum identity;
- deterministic state digest where required for recovery evidence;
- no raw private payloads or credential values.

Operational state uses the V10 vocabulary. Unavailable/corrupt persistence is `BLOCKED`/`ERROR` for state mutation, not silently downgraded to volatile memory.

## 14. CI routing

- Fast hosted checks: normal path-aware static/unit feedback when hosted account capacity permits.
- Hosted clean-room compatibility: existing policy; hosted startup billing failure remains infrastructure failure, not PASS.
- Lenovo authoritative checks: **required** exact-head `V10 authoritative merge gate` plus focused PostgreSQL 18 WP13 integration/recovery rehearsal.
- GPU AI eval required: **NO**.
- Release/recovery matrix required: **YES, bounded to WP10 PostgreSQL backup/restore integration using synthetic state**.

## 15. Rollback/recovery

Before production data exists, code rollback is source-only plus recreation of the synthetic acceptance DB. Once durable private state exists, schema rollback follows the recovery contract: prefer forward repair migration or restore a verified compatible backup, preserve execution/reconciliation truth, and never delete ambiguous broker state to make an old binary start.

V9 remains the protected product rollback while V10 Block D is in development.

## 16. Exit Gate

WP13 PASS requires on the exact reviewed PR head:

1. versioned PostgreSQL migration framework and required schemas exist;
2. clean database bootstrap from zero succeeds on PostgreSQL 18;
3. exact numeric/no-float policy is enforced;
4. append-only/audit-sensitive records reject silent overwrite/delete;
5. concurrency/idempotency and migration serialization tests pass;
6. WP12 scope/identity relationships remain fail closed in persistence;
7. WP10 backup/restore rehearsal preserves schema version and state digest;
8. no WP14/WP15/Web/Telegram/Cortex/Real feature work is introduced;
9. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged;
10. authoritative Self-Hosted Windows CI and focused PostgreSQL 18 integration/recovery gate are GREEN;
11. dependency audit, SAST and tracked-content secret scan are GREEN through the authoritative gate;
12. zero unresolved blocking review threads;
13. full PR diff reviewed;
14. squash merge completes;
15. post-merge Regression Shield succeeds on the exact resulting `main` SHA.

## 17. Required acceptance evidence

Record:

- exact PR head SHA;
- current migration version and migration checksums;
- clean bootstrap result;
- Decimal/UTC/append-only/idempotency/concurrency test result;
- synthetic backup/restore source and restored state digests;
- exact authoritative Self-Hosted Windows CI run;
- exact focused WP13 PostgreSQL integration/recovery run;
- hosted-lane infrastructure classification if applicable;
- zero blocking review threads;
- merge SHA;
- exact post-merge Regression Shield run.

No OWNER physical action or real secret input is required for WP13.

## 18. Documentation/status updates

The implementation PR owns this contract, persistence code/migrations/tests, bounded recovery-binding changes and any persistence-specific operations notes. Official `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` advances only in a separate post-merge status synchronization after the post-WP13 Regression Shield is GREEN.

## 19. Next WP unlock

Only **WP14 — Durable Job System** may be unlocked, and only after all WP13 Exit Gate evidence above is accepted. WP14 may then implement job leases/retries/recovery against the WP13 job persistence shape without changing the persistence safety guarantees silently.

## 20. Scope-discovery rule

Any broker-read, job-runtime, Web, Telegram, AI, public-ingress or Real-execution work discovered during WP13 is future-WP work unless strictly required to make the WP13 database correct and recoverable. It must not be implemented opportunistically.

## Reviewed external technical references

- PostgreSQL 18 data types: `https://www.postgresql.org/docs/18/datatype.html`;
- PostgreSQL 18 advisory locks: `https://www.postgresql.org/docs/18/functions-admin.html`;
- PostgreSQL 18 concurrency control: `https://www.postgresql.org/docs/18/mvcc.html`;
- Psycopg installation/support matrix: `https://www.psycopg.org/psycopg3/docs/basic/install.html`;
- Psycopg PyPI release metadata: `https://pypi.org/project/psycopg/3.3.4/`.
