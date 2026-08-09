# Omni-CIO V10 — WP10 Execution Contract

Status: **IMPLEMENTATION CANDIDATE — acceptance requires focused PR, exact-head recovery evidence, OWNER off-device target and WP10 Exit Gate**  
Work package: **WP10 — Backup, restore и off-device recovery**  
Accepted base at start: `615ec003a33ae993abb5942e99c5fabd8c18c26b`

## 1. WP identity and prerequisite

WP10 is authorized only after WP9A was accepted, canonical status PR #262 squash-merged, and post-status Regression Shield #1446 / run `31295682715` completed successfully on the accepted `main`.

The protected baseline remains V9 `app:app` plus accepted WP5–WP9A node, privilege, secret, supervision and operations boundaries. `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.

## 2. Purpose

Prove that V10 private durable state can be backed up, integrity-checked and restored after corruption or node/storage loss without treating GitHub, CI artifacts or runtime secrets as a backup store.

WP10 owns the recovery mechanism and recovery objectives for:

- PostgreSQL logical backup and restore;
- bounded retention and integrity metadata;
- encrypted OWNER-controlled off-device copy;
- explicitly allowlisted private non-secret configuration/metadata backup;
- corrupt/tampered backup detection before restore;
- deterministic recovery rehearsal;
- recovery-state evidence and runbook;
- separation of source-code recovery, private-state recovery and runtime-secret recovery.

## 3. Measurable recovery objectives

The initial Personal-node objectives are:

- **RPO: 60 minutes** for durable private state once the production V10 database binding exists;
- **RTO: 240 minutes** for the documented Personal-node recovery path from accepted GitHub source + approved encrypted off-device state + separately restored secrets.

The RPO is intentionally tighter than a daily backup because later decisions, plans, reconciliation and audit events are durable safety state. The accepted Lenovo has adequate local storage headroom for a small Personal-node logical-backup cadence, while exact production database size is not yet defined before WP13. The retention policy therefore remains bounded by both count and age rather than assuming unlimited storage.

RPO is never claimed while the off-device target is unavailable or the latest verified off-device backup is older than 60 minutes. Such a state is `DEGRADED/BLOCKED_RECOVERY_OBJECTIVE`, not a silent success.

RTO is a target, not a promise that broker or external services are available. Recovery completion requires integrity/migration/health checks; Real execution remains disabled until its own later recovery/readiness gate.

## 4. Existing implementation to reuse

- `docs/architecture/V10_RECOVERY_CONTRACT.md` — **REUSE_AS_IS** as the recovery source-separation and scenario authority.
- accepted WP5 full-disk-encryption/recovery-key custody evidence — **REUSE_AS_IS** for local encrypted-at-rest staging assumptions; no recovery keys are copied into backup.
- WP7 PostgreSQL 18.4 installation and `C:\ProgramData\OmniCIO` infrastructure roots — **REUSE_AS_IS**; WP10 does not reinstall or upgrade PostgreSQL.
- WP8 secret-store separation — **REUSE_AS_IS**; `C:\ProgramData\OmniCIO\secrets` and secret values are explicitly excluded from backup payloads.
- WP9/WP9A supervision/operations boundaries — **REUSE_AS_IS**; WP10 may define a future scheduled backup job but does not activate later product services.
- GitHub hybrid CI / Regression Shield — **REUSE_AS_IS** with hosted compatibility and Lenovo authoritative recovery rehearsal.
- V9 `app:app` production/recovery runtime — **REUSE_AS_IS** and untouched.

No V9 financial engine is rewritten, moved or retired in WP10. No parity-ledger financial row changes ownership here.

## 5. Sequencing fact — product database binding is not invented early

WP13 owns the V10 application persistence schema/migrations and explicitly includes backup/restore integration. At WP10 start, PostgreSQL 18.4 exists on the Lenovo but the future V10 private application schema/database is not yet an accepted durable product surface.

Therefore WP10 must:

1. implement a production-capable logical backup/verification/restore mechanism;
2. prove it end-to-end on an isolated synthetic PostgreSQL 18.4 recovery database with no private user data or real secret;
3. define the sealed production schedule/binding contract now;
4. leave actual product-database binding `NOT_READY_UNTIL_WP13` rather than creating a premature private schema or credential;
5. require WP13 to bind its accepted database to this recovery mechanism rather than inventing a competing backup stack.

This is sequence preservation, not an exemption from the WP10 restore proof.

## 6. Database backup format and portability

The selected baseline is PostgreSQL logical custom archive:

- `pg_dump --format=custom` (`-Fc`);
- `--no-owner`;
- `--no-privileges`;
- PostgreSQL accepted major remains 18;
- restore uses `pg_restore` into a controlled replacement/recovery database;
- archive integrity is checked before restore;
- restore rehearsal verifies application-level probe content after `pg_restore` succeeds.

`pg_dump` is used because PostgreSQL documents its consistent export behavior while a database is concurrently used, and custom archives are portable/flexible inputs to `pg_restore`. WP10 does not enable WAL/PITR or a second backup technology merely because it exists; that would add operational scope without a current RPO requirement proving necessity.

Cluster-global role passwords are not backup payload. Future service/database roles are recreated through reviewed bootstrap/migration/security procedures and credentials are restored separately. WP10 must never use a role-password dump as a substitute for secret recovery.

## 7. Integrity and atomicity contract

Every accepted backup bundle contains:

- exactly one PostgreSQL custom archive;
- one machine-readable manifest;
- SHA-256 of the archive;
- archive byte size;
- schema/format/tool-version classes;
- UTC creation timestamp;
- backup/recovery objective metadata containing no private payload.

Rules:

- archive is first created as an incomplete/staging file;
- SHA-256 is calculated only after `pg_dump` succeeds;
- off-device copy is written to a temporary name, re-hashed at destination, then atomically promoted to its final name;
- manifest is accepted only when its schema and archive hash/size match;
- any hash/size/schema mismatch blocks restore;
- `pg_restore --list` must accept the archive before a destructive/target restore attempt;
- manifests contain no token/password/ciphertext/account/portfolio values.

SHA-256 is an integrity/tamper-detection signal. It is not encryption and is never represented as encryption.

## 8. Encryption and off-device target

The initial supported WP10 off-device target class is an **OWNER-controlled, non-system BitLocker-encrypted Windows volume** (for example a dedicated external disk). This uses the existing Windows security baseline and avoids inventing machine-bound DPAPI encryption for data that must be restorable on replacement hardware.

Acceptance requires the selected target to report:

- it is not the Windows system volume;
- BitLocker volume state is `FullyEncrypted`;
- BitLocker protection is `On`;
- a WP10 non-secret target marker is present;
- recovery-key custody is separately confirmed by OWNER without recording the key;
- the protected backup payload directory is not readable by the GitHub runner identity.

The backup encryption boundary is the encrypted off-device volume. No secret/recovery key is embedded in the archive or manifest. A NAS/other target may be added later only with equivalent proven encryption, OWNER control and recovery semantics; it is not silently assumed compatible.

## 9. Retention policy

For the initial Personal-node logical archive class:

- backup cadence target: every 60 minutes after product DB binding;
- maximum retained successful bundles per target: **72**;
- maximum retained age: **30 days**;
- a bundle may be pruned only when it is WP10-owned, manifest-valid and not the only remaining verified bundle;
- incomplete/staging files older than the bounded cleanup threshold are removable only by the WP10-owned cleanup path;
- retention failure is explicit and must not delete an unknown/unowned file to make space.

This gives a bounded recent recovery window without assuming the future database size. WP13 or a measured later package may revise retention only through reviewed recovery evidence; RPO cannot be weakened silently.

## 10. Non-secret metadata/config scope

WP10 does not recursively copy all of `C:\ProgramData\OmniCIO`.

The private non-secret payload is explicit allowlist only and initially may include recovery-relevant, non-secret application metadata after its owning WP exists, such as:

- accepted migration/schema metadata;
- model/RAG manifests/metadata that contain no model secret/private prompt transcript;
- recovery-relevant job/checkpoint metadata when owned by later WPs;
- reviewed local configuration whose schema marks it `BACKUP_ALLOWED`.

The following are forbidden regardless of convenience:

- `C:\ProgramData\OmniCIO\secrets` or any descendant;
- DPAPI blobs/ciphertext from WP8;
- recovery keys/cert private keys;
- raw process dumps;
- GitHub runner credentials/configuration;
- arbitrary user profile directories;
- unreviewed logs with private payloads.

Before those later metadata families exist, an empty approved metadata payload is valid. WP10 must not fabricate future data merely to populate a backup.

## 11. Authority / privilege effects

WP10 does not expand broker or OS authority.

- GitHub Actions runner receives no read permission to production private backup archives.
- The runner may execute only synthetic recovery rehearsals containing no private data or real secret.
- Final off-device target provisioning/recovery-key custody remains an OWNER physical/admin action.
- Future production backup execution must run under an identity already authorized for the required private DB read path; WP10 does not grant that access to CI.
- Recovery never enables Real execution by itself.
- Restoring an old database is not permission to replay an old plan/order.

## 12. Normal-path acceptance tests

WP10 must prove:

- machine-readable recovery contract parses and enforces RPO/RTO/retention/security boundaries;
- manifest creation is deterministic for metadata and binds SHA-256 + exact archive size;
- valid bundle verification passes;
- atomic off-device copy re-verifies destination before final promotion;
- bounded retention removes only owned/valid eligible bundles;
- PostgreSQL 18.4 synthetic database is dumped in custom format and listed by `pg_restore`;
- the valid synthetic archive restores into a separate recovery database;
- restored deterministic probe rows exactly match source rows;
- no real secret/private portfolio/account payload is required for the rehearsal;
- absent production V10 database before WP13 is reported as `NOT_READY_ALLOWED`, not fabricated as backed up;
- protected `app:app`, `trading_methods=false` and no-broker-write boundaries remain green.

## 13. Negative/failure tests

WP10 must fail closed for:

- archive SHA-256 mismatch;
- archive byte-size mismatch;
- malformed/unsupported manifest schema;
- manifest/archive name mismatch or path traversal;
- `pg_dump`/copy/`pg_restore --list` failure;
- intentionally corrupted archive;
- restore to an unapproved target/state;
- off-device target equal to system volume;
- off-device BitLocker not fully encrypted or protection not on;
- recovery-key custody unknown;
- attempt to include WP8 secret root, secret-like paths or forbidden metadata class;
- runner read access to production backup payload;
- retention attempting to delete unowned/invalid files;
- stale latest off-device backup beyond RPO once production binding is active;
- any attempt to imply recovered execution/broker truth from a stale local snapshot.

## 14. Observability

WP10 health/evidence uses sanitized status only:

- `READY | NOT_READY_ALLOWED | DEGRADED | BLOCKED | ERROR`;
- latest verified backup age band, never private contents;
- RPO/RTO target and measured rehearsal duration;
- backup/restore format/version class;
- off-device encrypted/protected/marker/access booleans;
- corruption-detection and restore-rehearsal PASS/FAIL;
- production-binding readiness class;
- stable reason codes/correlation IDs.

CI must not upload DB archives, private backup manifests containing private identifiers, secret values, recovery keys or raw off-device file listings.

## 15. CI routing

- Fast hosted checks: contract, manifest, path/retention/privacy negative tests.
- Hosted Windows clean-room compatibility: **YES** for PowerShell 5.1 parsing, path semantics and non-mutating target audit behavior.
- Lenovo authoritative checks: **YES** for installed PostgreSQL 18.4 synthetic dump/corruption/restore rehearsal and inherited WP6–WP9A checks.
- Production private DB backup in CI: **NO**.
- GPU AI eval: **NO**.
- Release/recovery matrix: **YES**, WP10 is itself the Block C recovery package.

## 16. Rollback/recovery

Repository rollback is a normal revert/squash recovery to accepted pre-WP10 `main`.

Local WP10 cleanup may remove only marker-owned synthetic/rehearsal state. It must refuse to delete an unrecognized off-device directory or any bundle that cannot be proven WP10-owned. An accepted production backup is recovery evidence and is not deleted as part of code rollback merely because a newer code version is reverted.

V9 remains the protected production/recovery fallback throughout WP10.

## 17. Binary Exit Gate

WP10 is COMPLETE only when all are true:

- focused WP10 PR is based on accepted WP9A-status `main`;
- RPO=60 min and RTO=240 min are machine-readable and enforced as recovery objectives;
- contract/manifest/retention/privacy negative tests pass;
- hosted Windows compatibility passes;
- authoritative Lenovo PostgreSQL 18.4 synthetic backup/corruption/restore rehearsal passes without real secrets/private data;
- one OWNER-controlled non-system off-device target is proven FullyEncrypted + Protection On and separately recoverable;
- OWNER off-device rehearsal copies a synthetic bundle to that target and restores/validates it without exposing its payload to CI;
- runner production-backup payload access remains denied;
- secret-root exclusion and separate secret-recovery contract remain intact;
- production DB binding remains sealed until WP13 rather than creating schema/credentials early;
- no later product service is activated;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and Real-money authority are unchanged;
- exact-head required gates and review-thread resolution pass;
- squash merge lands on `main`;
- post-merge Regression Shield passes.

Only after the WP10 Exit Gate and Block C acceptance/status synchronization may WP11 begin.
