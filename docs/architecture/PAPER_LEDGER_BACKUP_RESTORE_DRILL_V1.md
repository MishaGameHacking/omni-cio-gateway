# Paper Ledger Backup Restore Drill V1

## Purpose

PR-35 operationalizes the encrypted paper-ledger recovery boundary by copying
verified encrypted archive records to a distinct local backup root, building an
authenticated recovery manifest, storing that manifest atomically and proving a
complete restoration from the backup.

The drill remains paper-only and preserves:

- `trading_methods=false`;
- `execution_ready=false`;
- no broker order creation, replacement or cancellation;
- no transfer or withdrawal surface;
- no FastAPI, OpenAPI or GPT Action change.

## Source verification and locking

The source archive must already exist with a private directory mode. Before any
copy is accepted, the drill acquires the same exclusive `.paper-ledger.lock`
used by the PR-33 writer. The backup root receives the same lock. Lock
acquisition is ordered by resolved path and fails immediately on contention.

Holding both locks prevents a normal paper-ledger writer or another drill from
changing either archive during the snapshot. Source files are read before and
after replication and the fully restored source state is compared both times.

The temporary source lock is an operational directory entry. The drill does not
modify, replace or delete source `.plae` archive files.

## Replication

Only encrypted `.plae` payloads are replicated. For every source record the
drill validates:

- strict immutable filename;
- contiguous sequence beginning at 1;
- regular-file status;
- mode `0600` or stricter;
- bounded size;
- strict encrypted-envelope contract;
- envelope sequence and record-digest binding.

A missing target is copied through a same-directory temporary file, full write,
file `fsync`, atomic `os.replace`, mode normalization and directory `fsync`.

An existing byte-identical target is reused without rewriting. An existing
conflicting file, symlink, unsafe permission or unexpected additional `.plae`
file fails closed. No backup archive file is deleted.

Each record is atomic, but the entire multi-record archive is explicitly not a
single filesystem transaction. A crash can leave a verified prefix. Rerunning
the drill is idempotent and resumes by accepting identical immutable files.

## Recovery manifest storage

After replication, PR-34 builds an HMAC-authenticated recovery manifest only
when the primary and backup both pass full external AEAD decryption and PR-32
HMAC/hash-chain restoration.

The manifest is stored in the backup root as:

`recovery-<latest-sequence>-<manifest-digest>.plrm`

Manifest storage uses the same atomic-write and `0600` permission rules. An
existing byte-identical manifest is reused; an immutable conflict fails closed.
The manifest contains operational checkpoint evidence, not raw encryption or
signing keys.

## Restore drill

The stored manifest is read from disk and authenticated again. The backup is
then restored against that exact manifest. The drill succeeds only when the
restored latest paper ledger exactly equals the source latest ledger for:

- sequence;
- authenticated record digest;
- complete typed ledger state and events.

No merely copied, parsed or decrypted state is represented as a successful
backup.

## Failure behavior

The drill fails closed for:

- identical primary and backup roots;
- active writer or backup lock;
- malformed, missing or non-contiguous source records;
- unsafe permissions, symlinks or non-regular files;
- extra backup archive files;
- immutable target conflicts;
- source changes during the drill;
- manifest authentication or storage conflicts;
- backup restore mismatch;
- invalid timestamps.

A failure before atomic replace leaves no visible final record. Temporary files
are removed during handled failures. Process termination can leave orphaned
hidden temporary files; automatic orphan cleanup remains a separate reviewed
operations feature.

## Scope not included

PR-35 does not add:

- scheduled backup execution;
- remote object storage or geographic replication;
- automatic stale-lock removal;
- archive deletion or retention execution;
- full-archive transactional rollback;
- secure erasure;
- key storage or KMS implementation;
- monitoring or alert delivery;
- public API or GPT Action exposure.

## Validation

Focused tests cover:

- fresh encrypted replication and complete restore;
- source-file digest preservation;
- file and directory permissions;
- repeat-run idempotency;
- distinct-root enforcement;
- extra-file and immutable-file conflicts;
- active-lock contention;
- simulated `os.replace` failure and cleanup;
- tampered stored manifest rejection;
- unsafe source permissions and invalid drill time;
- preservation of all read-only and paper-only safety flags.

Regression Shield must pass lock verification, repository policy, compile,
Ruff, formatting, mypy, stable `app:app`, the read-only GPT Actions release
contract, full pytest with coverage, dependency audit, Bandit and secret scan.

## Rollback

Revert the PR merge commit. PR-32 authenticated archives, PR-33 encrypted atomic
storage and PR-34 recovery manifests remain independently usable. No public API,
Render, broker or GPT Editor migration is required.
