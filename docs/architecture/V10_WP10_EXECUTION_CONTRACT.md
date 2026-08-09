# Omni-CIO V10 — WP10 Execution Contract

Status: **REBUILD CANDIDATE — NOT ACCEPTED / OWNER ACTION REQUIRED BEFORE EXIT GATE**  
Work package: **WP10 — Backup, restore и off-device recovery**  
Required accepted base: post-WP9A status (`615ec003a33ae993abb5942e99c5fabd8c18c26b` tree)

## 1. Purpose

WP10 must prove that private durable V10 state can be backed up, verified and restored after database corruption or loss of the Lenovo/SSD. GitHub remains the engineering source; private state lives only in encrypted owner-controlled backup; runtime secrets are restored separately.

This rebuild deliberately separates **software readiness** from **OWNER physical acceptance**. CI, a developer, or a PR description may never manufacture or substitute the OWNER off-device evidence required by the Master Plan.

## 2. Canonical authority

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — WP10 deliverables and mandatory RPO/RTO.
- `docs/architecture/V10_RECOVERY_CONTRACT.md` — R1–R8 recovery separation and corruption/node-loss rules.
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` — binary Exit Gate discipline.
- accepted WP5 hardware/OS evidence — capacity and encrypted-system-volume baseline.
- accepted WP8 secret-store separation — secret payloads are excluded from backup.
- accepted WP9/WP9A supervision/operations boundaries — no privilege or money-authority expansion.

Protected invariants remain `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, protected V9 rollback, and no broker-write authority change.

## 3. Recovery objectives

Initial Personal-node objectives are:

- candidate **RPO = 60 minutes** once the production V10 database is bound;
- candidate **RTO = 240 minutes** for the documented replacement-node recovery path.

These values are not considered achieved merely because they are written in a contract. WP10 Exit Gate requires:

1. backup automation capable of a <=60 minute cadence;
2. a verified latest off-device copy at or inside the RPO during final acceptance;
3. a measured end-to-end synthetic restore rehearsal within 240 minutes;
4. integrity/reconciliation checks are never skipped to meet RTO.

Before product DB binding, RPO status is `NOT_APPLICABLE_YET`; software and physical rehearsal evidence are still mandatory.

## 4. Required deliverables

WP10 implements all Master Plan requirements:

- automated PostgreSQL logical backup mechanism;
- retention/rotation and SHA-256 + exact-size integrity manifest;
- corruption/tamper rejection before restore;
- encrypted OWNER-controlled off-device copy;
- allowlist-only backup of private non-secret configuration/model/RAG metadata;
- deterministic restore into a separate recovery DB/location;
- full replacement-Windows-node recovery runbook;
- executed restore/recovery rehearsal;
- separately documented GitHub source, private-state and secret recovery paths.

## 5. Sequence-safe product binding

WP13 owns the future product schema/migrations and WP14 owns durable product jobs. WP10 therefore must not invent production schema or credentials early.

However, WP10 **does not waive the Master Plan automation requirement**. It must implement and test the production-capable backup runner and schedule contract now, prove it against an isolated synthetic PostgreSQL database, and leave only the future product DB/credential binding sealed.

States:

- mechanism: `READY_AFTER_TESTS`;
- schedule definition: `READY_AFTER_TESTS`;
- production DB binding: `NOT_READY_UNTIL_WP13`;
- production scheduled-task/service credential binding: `NOT_READY_UNTIL_WP13_WP14`.

## 6. Backup format and integrity

Baseline:

- PostgreSQL 18 `pg_dump --format=custom --no-owner --no-privileges`;
- restore by `pg_restore` into a separate recovery database;
- `pg_restore --list` preflight before restore;
- bundle manifest binds archive name, SHA-256, byte size, PostgreSQL major/version class, UTC timestamp and backup class;
- archive and manifest are written through temporary names and promoted only after verification;
- destination is re-hashed after off-device copy;
- path traversal, symlinks/reparse points, malformed manifests, duplicate final names and unknown content fail closed.

SHA-256 is integrity evidence, not encryption.

## 7. Retention

Initial bounded policy after product binding:

- target cadence: 60 minutes;
- retain up to 72 verified successful bundles;
- maximum age: 30 days;
- never delete the only verified bundle;
- never delete unknown/unowned/invalid files to make space;
- re-verify immediately before deletion.

## 8. Private non-secret metadata

Metadata backup is explicit allowlist only. It may include later recovery-relevant local configuration/model/RAG manifests whose owning schema marks them backup-allowed.

Always forbidden:

- WP8 secret root or DPAPI blobs;
- broker/Telegram/API credentials;
- BitLocker/recovery keys;
- GitHub runner credentials;
- process dumps;
- arbitrary logs/user profiles;
- unreviewed portfolio/report payloads outside the database backup contract.

An empty metadata set is valid before later owning WPs create eligible files; the mechanism must still be implemented and tested with synthetic fixtures.

## 9. Off-device target — non-destructive rule

Final acceptance requires one OWNER-controlled encrypted off-device location. Initial supported class is a non-system BitLocker-encrypted Windows volume.

**WP10 code must not repartition, format, shrink, erase, or automatically repurpose a physical disk.** The OWNER provides an already chosen target. The audit may only verify:

- target is not the system volume;
- BitLocker volume is fully encrypted and protection is on;
- separate recovery-key custody is confirmed without exposing the key;
- a dedicated Omni-CIO backup root/marker exists;
- backup payload ACL is not readable/writable by the non-admin CI runner;
- no secret value is logged.

If no suitable target exists, state is `OWNER_ACTION_REQUIRED`; it is never converted to PASS by synthetic evidence.

## 10. OWNER evidence boundary

Final physical evidence must come from one reviewed local PowerShell procedure executed by OWNER. The procedure emits only sanitized booleans/reason codes/timings and no key, token, account ID, private DB payload or raw disk identity.

CI may validate that sanitized evidence, but CI may not create the OWNER assertion itself.

Required physical proof:

1. target encryption/protection audit;
2. synthetic bundle copied to off-device target and re-verified;
3. one deliberate corrupt copy rejected;
4. valid copy restored into separate recovery DB;
5. deterministic probe rows match;
6. temporary synthetic state cleaned;
7. runner backup-root read/write denial confirmed.

## 11. Normal-path tests

- contract validates and enforces RPO/RTO/retention/authority rules;
- bundle finalize/verify/copy succeeds for valid fixture;
- scheduled backup runner can execute the synthetic DB backup path non-interactively;
- schedule definition is <= RPO and contains no secret value;
- valid PostgreSQL custom archive passes `pg_restore --list`;
- valid archive restores into separate recovery DB with exact probe parity;
- metadata allowlist packs/restores only approved synthetic files;
- retention prunes only verified owned bundles;
- sanitized OWNER evidence parser accepts only the fixed schema;
- protected V9 and money-authority invariants stay green.

## 12. Negative/failure tests

Fail closed for hash/size/schema/name mismatch, path traversal, symlink/reparse point, corrupted archive, `pg_dump`/`pg_restore` failure, stale off-device copy after product binding, secret-like metadata path, secret root inclusion, system-volume target, encryption/protection off, unknown recovery-key custody, runner access to backup payload, destructive target operation, schedule cadence > RPO, and any attempt to infer broker execution truth from a restored old snapshot.

## 13. CI routing

- repository/unit tests: required;
- Windows PowerShell 5.1 parse/compatibility: required where workflow capacity is available;
- Lenovo self-hosted PostgreSQL synthetic backup/corruption/restore: authoritative and required;
- OWNER physical off-device rehearsal: required for final Exit Gate, never simulated by CI;
- production private DB in CI: forbidden;
- backup archive upload as CI artifact: forbidden.

Optional/accelerator hosted failure must be reported truthfully. A check explicitly declared mandatory by this contract may not be silently reclassified inside the same implementation PR merely to obtain acceptance.

## 14. Rollback

Repository rollback is a normal revert PR to the accepted post-WP9A state; protected `main` is never force-reset. Local cleanup may delete only WP10 marker-owned synthetic rehearsal state and must refuse unknown user data.

## 15. Binary Exit Gate

WP10 is COMPLETE only when **all** of the following are true:

- focused WP10 PR is based on accepted post-WP9A main;
- automatic backup mechanism and <=60-minute schedule contract are implemented and tested;
- integrity/retention/corruption/privacy negative tests pass;
- Lenovo PostgreSQL synthetic backup + corruption rejection + separate restore rehearsal passes;
- private non-secret metadata allowlist mechanism is implemented/tested;
- replacement-node recovery runbook is complete;
- one real OWNER-controlled encrypted off-device target is audited without destructive provisioning;
- OWNER off-device copy + corrupt rejection + restore probe rehearsal passes with sanitized evidence;
- measured rehearsal duration is <=240 minutes;
- runner cannot read/write production backup payload;
- runtime secrets remain separately restored and excluded from backup;
- production DB/job binding remains sealed until its owning WP;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and broker authority are unchanged;
- exact-head repository-required CI is green and unresolved review threads are zero;
- squash merge lands on `main`;
- mandatory post-merge Regression Shield passes;
- only then is Block C credited and WP11 unlocked.

Until the OWNER physical gate and all required checks pass, status remains **WP10 IN PROGRESS / WP11 LOCKED**.
