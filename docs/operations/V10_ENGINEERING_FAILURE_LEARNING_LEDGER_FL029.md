# FL-029 — Windows hard-link metadata views are not interchangeable

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #347; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-20**  
WP / PR / reference: **WP22A Phase 3 hosted recovery integrity boundary / PR #347 / authoritative Windows CI run `32402292634`**

## Symptom / failing gate

PR #347 exact head `7efb57c1a9df6d8c53a2af19bc6c1e1fdfdc17ae` reached the authoritative Lenovo protected-runtime regression and failed two recovery-archive tests while the remaining 2238 tests passed and coverage remained above the required threshold.

Both failures came from post-publication validation of a newly created hard-linked final archive. The code compared the full `Path.stat()` snapshot of the final hard-link path with the full `os.fstat()` snapshot from an open handle and raised `HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION` even though the file identity/content had not changed.

The authoritative gate therefore remained RED. The failure is a real portability defect, not infrastructure noise and not acceptance evidence.

## Root cause

On Windows, creation-time/`st_ctime_ns` metadata observed through a hard-link path can differ from the value observed through an already-open handle to the same file identity. Treating that platform-specific representation as a cross-view tamper signal caused a false positive.

The security-relevant replacement/content invariants are still available through device/inode identity, size and modification time together with the streamed SHA-256 digest and the existing before/opened/after checks.

## Blast radius searched

The defect class was isolated to the hosted recovery atomic archive snapshot helper used for staging and post-hard-link validation. The correction preserves:

- hard-link no-clobber publication;
- device/inode identity binding;
- size and modification-time drift detection;
- streamed SHA-256 integrity and maximum-size enforcement;
- symlink/reparse rejection;
- staging/final cleanup ownership checks;
- provider apply OFF and public ingress OFF;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- the WP23+ lock.

## Why preflight missed it

Focused preflight executed on a non-Windows environment and exercised the logical hard-link flow, but it did not reproduce the exact Windows `stat` versus `fstat` metadata representation used by the authoritative Lenovo runner.

The branch therefore entered an expensive exact-head cycle without a Windows-specific portability guard for the new filesystem identity logic.

## Corrective change

Normalize the archive snapshot so Windows does not use `st_ctime_ns` as a cross-view equality signal while retaining device, inode, size and modification-time checks. Unix continues to include `st_ctime_ns` in the snapshot.

Add a deterministic hard-link regression test that compares the validation snapshot obtained from the hard-link path with the snapshot obtained from an open handle to that same identity.

## Permanent regression / guard

The new hard-link snapshot portability test runs in the normal regression suite and therefore on the authoritative Windows lane. Future recovery-filesystem changes must preserve the same exact-head Windows execution before merge.

No security gate is weakened: archive bytes are still streamed and hashed, file replacement remains bound by stable identity, and any new commit invalidates earlier GREEN evidence.

## Future prevention rule

Filesystem security checks that compare metadata obtained through different OS APIs (`stat`, `fstat`, hard-link paths, handles, reparse-aware calls) must be tested on every authoritative operating system before the branch is declared pre-CI ready. Do not assume timestamp fields have identical semantics or representation across those views.

When a metadata field is platform-ambiguous, retain the strongest portable identity/content signals and document the excluded field rather than accepting false-positive tamper failures or suppressing the entire integrity check.

## Dependency/tooling knowledge change

Windows file metadata semantics are part of the recovery toolchain contract. In particular, `st_ctime_ns` must not be treated as a portable cross-view hard-link identity token on the authoritative Windows runner.
