# Omni-CIO V10 — WP10 Recovery Runbook

Status: **IN PROGRESS — software rehearsal may pass before OWNER off-device acceptance; WP11 remains locked**

This runbook is the operator procedure for V10 private-state recovery. It does not grant broker-write authority and it never treats GitHub as a private database or secret backup.

## 1. Recovery sources are deliberately separate

1. **Engineering source:** accepted GitHub `main` / immutable accepted release provenance.
2. **Private durable state:** verified encrypted OWNER-controlled off-device PostgreSQL backup and explicitly allowlisted non-secret metadata.
3. **Runtime secrets:** separately restored OWNER-controlled WP8 secret store. Secrets are never copied into the database bundle, metadata archive, GitHub, Actions artifact, or runbook evidence.

If any one source is missing, report the corresponding degraded/blocked state. Never substitute one source for another.

## 2. Recovery objectives

- RPO objective after product DB binding: **60 minutes**.
- RTO objective: **240 minutes**.

Before WP13 binds the product database, RPO is `NOT_APPLICABLE_YET`; WP10 still proves the hourly-capable mechanism, corruption rejection, separate restore and physical off-device path. RTO is measured from the start of the recovery rehearsal through the verified restore probe. Integrity/reconciliation checks are never skipped to meet the objective.

## 3. Normal backup path

The production-capable runner is `infrastructure/windows/run_wp10_backup.ps1`.

It requires only connection identity/location plus working/output directories. It accepts **no password/token/secret parameter**. Future database authentication is supplied to the process through a separately reviewed least-privilege binding (for example a short-lived environment/`PGPASSFILE` prepared from the restored secret boundary). The scheduled task definition must never embed a credential value.

Backup sequence:

1. verify WP10 contract and PostgreSQL 18 toolchain;
2. run `pg_dump --format=custom --no-owner --no-privileges --no-password`;
3. write dump to encrypted local staging;
4. build SHA-256 + exact-size manifest;
5. atomically promote the local bundle only after verification;
6. copy bundle to the selected encrypted off-device target through temporary names;
7. re-hash/re-size at destination before promotion;
8. apply retention only to verified WP10-owned bundles;
9. never delete unknown/unowned content and never delete the only verified bundle.

The schedule contract is `infrastructure/windows/wp10_backup_schedule.json`: 60-minute cadence, production activation sealed until WP13/WP14 bind the product DB and least-privilege job identity.

## 4. Corruption / database loss

When the active database is suspected corrupt:

1. stop write-producing V10 components; keep Real execution disabled;
2. identify latest off-device bundle inside RPO and verify manifest/schema/size/SHA-256;
3. run `pg_restore --list` preflight;
4. create a **separate** recovery database/location;
5. restore there with `--no-owner --no-privileges --exit-on-error`;
6. run migration/schema/integrity/reconciliation checks owned by the current product version;
7. compare required deterministic probes/business invariants;
8. only after all checks pass may a later owning procedure promote recovered state;
9. broker execution truth after the backup timestamp is **not inferred** from the backup. Reconcile from authoritative broker sources before any execution-related workflow resumes.

A hash mismatch, size mismatch, malformed manifest, unexpected archive member, failed list preflight or failed restore probe blocks recovery from that bundle.

## 5. Complete Lenovo/SSD loss — replacement Windows node

1. Provision a supported Windows replacement node using the accepted WP5/WP7 hardware/toolchain/security contracts.
2. Restore engineering source by cloning accepted GitHub `main` / checking accepted release provenance. Do not force-reset protected GitHub history.
3. Re-apply WP6 least-privilege identity boundaries.
4. Recreate WP7 machine runtime prerequisites exactly from reviewed bootstrap contracts.
5. Recreate the WP8 secret-store boundary **without** copying secret values from GitHub/backup archives.
6. Attach/unlock the OWNER-controlled encrypted off-device recovery location using OWNER custody material outside the repository.
7. Verify the selected backup bundle before reading/restoring it.
8. Restore the PostgreSQL bundle into a new isolated recovery database.
9. Restore only explicitly allowlisted non-secret model/RAG/config metadata; reject traversal/symlinks/secret-like paths.
10. Run current schema/migration/integrity/reconciliation checks.
11. Rebind separately restored secrets through the WP8 boundary.
12. Run Regression Shield plus the responsible V10 recovery/health gates.
13. Start deterministic/read-only paths first. Keep `trading_methods=false` / `REAL_TRADING_ENABLED=false` unless a later explicitly accepted money-authority WP says otherwise.
14. Reconcile any external broker state newer than the restored backup before considering execution readiness.

## 6. OWNER off-device preparation — non-destructive

WP10 never formats, repartitions, shrinks, initializes, clears or erases a disk. OWNER chooses an already existing non-system data volume.

`prepare_wp10_offdevice_target.ps1` may only:

- verify the chosen volume is a non-system BitLocker `Data` volume;
- require `FullyEncrypted` + protection `On`;
- require OWNER confirmation that recovery-key custody exists separately without disclosing the key;
- create the dedicated `OmniCIO-WP10-Backups` directory, marker and non-private access sentinel;
- restrict that directory to SYSTEM/Administrators;
- write a local-only descriptor under `C:\ProgramData\OmniCIO\wp10` for later local audits.

The local descriptor contains the mount point because local automation needs it. It is **never uploaded to GitHub/CI artifacts** and final repository-safe evidence contains no raw disk identity or mount point.

## 7. Non-admin isolation proof

`audit_wp10_offdevice_target.ps1` runs under the non-admin self-hosted runner identity. It intentionally does **not** call privileged BitLocker cmdlets. It consumes the locally stored OWNER-validated descriptor and must prove:

- reading the access sentinel is denied;
- creating a write probe in the backup root is denied.

A missing/unmounted target is not counted as an ACL denial. Successful read/write is a WP10 blocker.

## 8. Synthetic Lenovo rehearsal

`rehearse_wp10_recovery.ps1` creates a temporary PostgreSQL 18 cluster containing only synthetic rows. It proves:

- non-interactive backup runner works;
- local bundle verifies;
- deliberately corrupted copy is rejected;
- `pg_restore --list` succeeds for the valid copy;
- restore occurs into a different database;
- exact probe rows match;
- temporary state is cleaned;
- no real secret, account ID, private portfolio payload or production database is used.

`V10 WP10 Recovery Audit` runs this on the Lenovo self-hosted runner. CI evidence can prove software readiness but **cannot** produce OWNER physical acceptance.

## 9. Final OWNER physical rehearsal

Final WP10 acceptance additionally requires a reviewed OWNER procedure on one real encrypted off-device target. It must produce only evidence conforming to `V10_WP10_OWNER_EVIDENCE.schema.json` and prove:

- target is non-system, fully encrypted and protected;
- separate recovery-key custody was confirmed without recording the key;
- bundle copied to off-device and re-verified;
- one corrupted copy rejected;
- valid off-device copy restored to a separate DB and exact probe matched;
- non-admin runner read/write denial passed;
- temporary synthetic state cleaned;
- end-to-end duration <= 240 minutes.

If no eligible target is available, result is `OWNER_ACTION_REQUIRED`; WP10 stays IN PROGRESS and WP11 stays locked.

## 10. Retention and cleanup safety

Retention defaults: maximum 72 verified bundles / 30 days. Never delete the only verified bundle. Invalid, foreign or unknown files are ignored rather than deleted. Re-verify immediately before deletion.

Synthetic rehearsal cleanup may remove only exact paths/bundle names created by the current WP10 rehearsal. It must never recursively clean an OWNER volume or unknown directory tree.

## 11. Evidence that may be committed/uploaded

Allowed: PASS/FAIL, reason codes, PostgreSQL version class/major, duration, booleans for integrity/corruption/restore/isolation, and contract/run IDs.

Forbidden: database archive, private rows, account identifiers, tokens/passwords, DPAPI ciphertext, BitLocker recovery material, disk serial/UUID, user/host identity, raw file listing of the off-device target, local descriptor containing the target mount point.

## 12. Exit discipline

Passing software CI is not WP10 acceptance. WP10 remains **IN PROGRESS / WP11 LOCKED** until every binary condition in `V10_WP10_EXECUTION_CONTRACT.md` is satisfied, the focused PR is squash-merged, and the mandatory post-merge Regression Shield succeeds.
