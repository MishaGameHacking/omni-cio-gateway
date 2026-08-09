# Omni-CIO V10 — WP10 Backup / Restore / Off-Device Recovery Runbook

## Purpose

WP10 proves recovery of V10 durable private state before Block C is accepted. It does not activate WP11 or any later product runtime, does not create the future WP13 application schema early, and never changes `app:app`, `trading_methods=false` or `REAL_TRADING_ENABLED=false`.

The recovery model has three deliberately separate planes:

1. **Engineering source** — accepted GitHub `main` / release identity.
2. **Private durable state** — verified encrypted OWNER-controlled backups.
3. **Runtime secrets** — restored separately through the WP8 local secret lifecycle; secrets and recovery keys are never database-backup payload.

GitHub and CI artifacts are not private-state or secret backups.

## Recovery objectives

The initial Personal-node objectives are:

- RPO: **60 minutes** once the production V10 database is bound by WP13.
- RTO: **240 minutes** for the documented Personal-node recovery path.

Before WP13 there is no accepted product database to schedule. WP10 therefore proves the backup mechanism against an isolated synthetic PostgreSQL 18 recovery database and leaves production binding `NOT_READY_UNTIL_WP13`.

A stale/missing off-device backup after production binding is an explicit degraded/blocking recovery-objective state. RTO never bypasses integrity, migration, reconciliation or later Real-execution readiness gates.

## PostgreSQL logical-backup baseline

WP10 uses PostgreSQL 18 logical custom archives:

- `pg_dump --format=custom`;
- `--no-owner`;
- `--no-privileges`;
- integrity manifest with SHA-256 and exact byte size;
- `pg_restore --list` before restore;
- restore into a separate controlled recovery database;
- deterministic probe validation after restore.

Cluster role passwords, broker tokens, Telegram tokens and WP8 ciphertext are excluded. Future database/service roles and credentials are recreated/restored through their owning reviewed procedures.

## Bundle lifecycle

A backup becomes accepted only through this sequence:

1. `pg_dump` completes into an incomplete staging file.
2. The bundle engine calculates archive SHA-256 and exact size.
3. A strict allowlisted manifest is built.
4. The archive is copied to its managed final name and flushed before atomic promotion.
5. The manifest is written atomically.
6. The bundle is re-opened and hash/size/name verified.
7. Off-device copy is written under a temporary name.
8. Destination bytes are re-hashed before final promotion.
9. Only verified WP10-owned bundles are eligible for retention pruning.

Unknown, malformed or unowned files are never deleted merely to satisfy retention.

## Retention

After WP13 production binding:

- target cadence: every 60 minutes;
- maximum successful bundles per target: 72;
- maximum age: 30 days;
- never delete the only remaining verified bundle;
- retention does not infer ownership from a filename alone — manifest verification is required.

The policy may be changed later only with reviewed recovery evidence. RPO must not be silently weakened.

## Synthetic Lenovo recovery rehearsal

`infrastructure/windows/rehearse_wp10_recovery.ps1` is designed for the non-private GitHub self-hosted lane. It:

- starts a temporary isolated PostgreSQL 18 cluster under runner temp;
- creates deterministic synthetic rows only;
- creates a custom archive;
- creates and verifies the WP10 manifest;
- verifies `pg_restore --list` accepts the archive;
- flips archive bytes and proves corruption is rejected;
- copies a valid bundle through the same atomic copy engine to a synthetic temp target;
- restores into a separate database;
- proves restored rows exactly match the source probe;
- removes temporary cluster/bundle state.

It must never access the production V10 database, a real secret, an account identifier or private portfolio data.

## Off-device target policy

The initial accepted target class is an OWNER-controlled, non-system Windows data volume protected by BitLocker.

The target must be:

- a drive other than the Windows system volume;
- a BitLocker **Data** volume;
- `VolumeStatus=FullyEncrypted`;
- `ProtectionStatus=On`;
- under OWNER control;
- recoverable using recovery material stored separately from GitHub and separately from the backup volume;
- protected so the GitHub runner cannot read or write backup payloads.

WP10 does not auto-enable BitLocker, create/export a recovery password, or print key-protector material. If a target is not already correctly encrypted, OWNER configures it through the normal Windows BitLocker UI/administrative flow and keeps recovery material separately.

## OWNER target preparation

Do not run this until the WP10 PR exact head is otherwise ready for the final off-device gate.

Preview is non-mutating:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\prepare_wp10_offdevice_target.ps1 `
  -TargetVolume E: -AsJson
```

Replace `E:` with the dedicated external/off-device data volume.

Final apply must be run from an elevated OWNER PowerShell only after the OWNER has independently confirmed custody of the BitLocker recovery material:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\prepare_wp10_offdevice_target.ps1 `
  -TargetVolume E: -Apply -RecoveryKeyCustodyConfirmed -AsJson
```

The script never asks for or records the recovery key. It creates only the reviewed WP10 backup root, safe marker/sentinel and sanitized local evidence. It refuses to take over a pre-existing directory that is not already marked as WP10-owned.

## Off-device ACL boundary

The protected backup root grants:

- SYSTEM — FullControl;
- built-in Administrators — FullControl;
- `omni-cio-runtime` — Modify for the future reviewed production backup path;
- `omni-ci-runner` — no payload grant.

The final ready-for-review self-hosted gate runs under the ordinary runner identity and must prove both sentinel read and write are denied. The gate uploads no backup content and does not read the protected target marker.

## Corrupt/tampered backup handling

A restore is blocked before `pg_restore` if any of these fail:

- manifest schema/field allowlist;
- archive managed name binding;
- exact archive byte size;
- SHA-256;
- regular-file/path checks;
- PostgreSQL archive listing.

Do not “repair” a mismatched manifest by recalculating its hash and proceeding. Select another verified backup or investigate the corruption event.

## Recovery after database corruption

1. Keep Real execution disabled.
2. Stop/contain the damaged owning application path once it exists.
3. Select the latest off-device bundle that passes manifest/hash/size verification and satisfies the recovery policy.
4. Verify the archive with `pg_restore --list`.
5. Restore into a separate controlled recovery database/location first.
6. Run migration/schema/version checks owned by WP13+.
7. Run application-level integrity/reconciliation checks.
8. Switch the application binding only through the owning reviewed recovery procedure.
9. Restore runtime secrets separately if required; never derive them from the database backup.
10. Re-enable later Real execution only through its own later recovery/readiness gate.

## Recovery after Lenovo/SSD loss

1. Recover accepted source from GitHub using the reviewed release/provenance path.
2. Re-establish the Windows node/bootstrap/security baseline from WP5–WP9A.
3. Attach/unlock the OWNER-controlled encrypted off-device backup target without exposing its recovery key to GitHub/CI.
4. Restore a verified private-state bundle into the replacement PostgreSQL environment.
5. Apply WP13+ migrations and reconciliation checks when those WPs exist.
6. Restore WP8 secrets separately through local OWNER procedures.
7. Confirm service/operations health.
8. Keep Real execution disabled until later execution-specific recovery acceptance.

## Privacy and diagnostic rules

Never upload or log:

- PostgreSQL private archives;
- private portfolio/account payloads;
- connection strings or database passwords;
- WP8 ciphertext;
- broker/Telegram/external-source secrets;
- BitLocker recovery passwords/keys;
- private process dumps;
- raw off-device file listings.

Allowed evidence is limited to sanitized status/reason codes, PostgreSQL version class, RPO/RTO, duration, integrity/corruption/restore booleans, BitLocker state booleans and runner access-denied booleans.

## WP10 Exit Gate

WP10 is not COMPLETE until all of these are true:

- deterministic contract/bundle/retention/privacy tests pass;
- hosted Windows PowerShell compatibility passes;
- Lenovo PostgreSQL 18 synthetic dump/corrupt/restore rehearsal passes;
- an OWNER-controlled non-system BitLocker target is physically available and passes the OWNER apply;
- final non-admin runner audit proves target encryption/protection and runner read/write denial;
- production DB binding remains sealed until WP13;
- exact-head general V10 gates pass;
- PR is ready/reviewed with no unresolved threads;
- squash merge lands on `main`;
- post-merge Regression Shield passes;
- Block C canonical status is then synchronized before WP11 begins.
