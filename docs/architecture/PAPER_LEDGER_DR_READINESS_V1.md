# Paper Ledger Disaster-Recovery Readiness V1

## Purpose

PR-36 adds a read-only disaster-recovery readiness assessment over the
paper-ledger archive, encrypted storage, recovery manifest and backup drill
introduced in PR-32 through PR-35.

The assessment answers a narrow operational question: can the current primary
and backup evidence be restored safely enough to be considered ready under an
explicit policy?

It never repairs, deletes, unlocks, copies or rewrites storage.

## Readiness conditions

`ready` requires all of the following:

1. primary and backup roots exist, are private directories and do not overlap;
2. both roots have sufficient free capacity under the active policy;
3. filesystem-device independence satisfies the active policy;
4. neither root has an active, stale-candidate or invalid writer lock;
5. neither root contains a reported hidden temporary artifact;
6. a latest authenticated recovery manifest can be selected unambiguously;
7. the manifest is not from the future and is within the allowed age;
8. the primary encrypted archive passes full restoration;
9. the backup passes restoration against the selected stored manifest;
10. primary and backup latest typed paper-ledger records are exactly equal;
11. the authenticated checkpoint is not from the future and is within the
    allowed age.

Any blocker produces `status=blocked`. Warnings do not make incomplete evidence
ready.

## Policy

`PaperLedgerDrReadinessPolicyV1` controls:

- maximum authenticated-manifest age;
- maximum authenticated-checkpoint age;
- minimum free bytes for each root;
- whether primary and backup must be on different filesystem devices;
- stale-lock diagnostic threshold;
- bounded temporary-artifact reporting.

The conservative default requires separate filesystem devices. A caller may
explicitly allow the same device for development or constrained local
operations, but the result then includes
`same_filesystem_device_allowed` as a warning.

This setting does not claim that same-device storage is a disaster-resistant
backup.

## Manifest selection

Backup directories can contain older authenticated recovery manifests. The
assessment:

1. validates manifest filenames;
2. considers only manifests for the greatest filename sequence;
3. reads them through no-follow, regular-file, single-link, private-permission
   and size checks;
4. resolves each non-secret manifest key ID through the caller-supplied key map;
5. authenticates each candidate with HMAC-SHA256;
6. selects the unique greatest authenticated `created_at` value.

Selection never trusts an unauthenticated timestamp. If two authenticated
candidates have the same greatest sequence and timestamp, readiness is blocked
as ambiguous rather than choosing arbitrarily.

Older valid manifests are retained and reported as a warning. The assessment
never removes them.

## Lock and temporary-artifact evidence

PR-34 lock diagnostics classify a lock as absent, active, stale-candidate or
invalid. Any present lock blocks readiness. A stale-candidate status is not
permission to remove the lock.

Hidden files matching `.*.tmp` are reported with:

- root role;
- filename;
- size;
- modification timestamp and age;
- regular-file status;
- symlink status;
- permission status.

Any reported temporary artifact blocks readiness. Every artifact retains
`cleanup_performed=false`.

## Capacity and device evidence

The assessment reads filesystem capacity with `statvfs` and records:

- device ID;
- total bytes;
- available bytes;
- policy minimum;
- sufficiency result.

No space is reserved and no file is deleted. Capacity is a point-in-time fact,
not a guarantee that a later write will succeed.

Different directory paths on one device are not represented as independent
filesystems. The separate-device gate does not prove geographic independence or
protection from host-wide failure.

## Fail-closed blockers

Blockers include:

- invalid or overlapping roots;
- present writer locks;
- temporary artifacts;
- missing, malformed, unavailable-key, unauthenticated, ambiguous, future or
  stale manifests;
- failed primary or backup restoration;
- primary/backup state mismatch;
- future or stale checkpoints;
- insufficient free capacity;
- missing filesystem-device independence when required.

The assessment preserves partial evidence where it can do so honestly. It does
not invent capacity or restored state for an inaccessible root.

## Safety boundary

Every result preserves:

- `read_only_assessment=true`;
- `no_cleanup_performed=true`;
- `no_lock_break_performed=true`;
- `no_retention_executed=true`;
- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

PR-36 adds no FastAPI route, HTTP method, OpenAPI operation, GPT Action, broker
SDK call or execution adapter.

## Scope not included

PR-36 does not add:

- scheduled assessments;
- monitoring or alert delivery;
- automatic backup runs;
- automatic stale-lock removal;
- orphan temporary-file cleanup;
- capacity reservation;
- remote or geographic backup verification;
- retention deletion or compaction;
- key storage or KMS implementation;
- public API exposure.

## Validation

Focused tests cover:

- a fully verified recent matching primary and backup;
- explicit same-device allowance and warning;
- conservative separate-device blocking;
- stale manifest and checkpoint blocking;
- active lock, temporary artifact and capacity blockers;
- missing manifest and unavailable manifest key;
- tampered manifest handling without repair;
- invalid-root blocked results without invented capacity;
- preservation of all read-only and paper-only safety flags.

Regression Shield must pass lock verification, repository policy, compile,
Ruff, formatting, mypy, stable `app:app`, the read-only GPT Actions release
contract, full pytest with coverage, dependency audit, Bandit and secret scan.

## Rollback

Revert the PR merge commit. PR-32 authenticated archives, PR-33 encrypted atomic
storage, PR-34 recovery manifests and PR-35 backup drills remain independently
usable. No public API, Render, broker or GPT Editor migration is required.
