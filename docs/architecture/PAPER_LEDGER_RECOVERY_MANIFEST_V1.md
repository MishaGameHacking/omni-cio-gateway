# Paper Ledger Recovery Manifest V1

## Purpose

PR-34 adds authenticated backup evidence, a non-executing retention planner and
strict writer-lock diagnostics over the encrypted paper-ledger storage from
PR-33.

The feature remains paper-only and preserves:

- `trading_methods=false`;
- `execution_ready=false`;
- no broker order creation, replacement or cancellation;
- no transfer or withdrawal surface;
- no FastAPI, OpenAPI or GPT Action change.

## Recovery manifest

A recovery manifest is created only after both the primary archive and a
byte-identical backup archive pass:

1. encrypted-envelope structural validation;
2. filename, sequence and digest binding;
3. external authenticated decryption;
4. PR-32 HMAC and hash-chain verification;
5. exact latest-ledger equality.

The manifest records ordered evidence for every archive file:

- sequence;
- immutable filename;
- authenticated record digest;
- SHA-256 digest of the encrypted envelope;
- exact encrypted-file size.

It also records the latest sequence, latest record digest, event count and a
non-secret backup reference.

The manifest itself is authenticated with an externally supplied HMAC-SHA256
key. The key is not generated, stored, serialized or logged by this module.

## Backup model

V1 requires a byte-identical encrypted backup. Re-encrypting the same ledger
with another nonce or key does not qualify as the same backup evidence because
its encrypted-envelope digest differs. A future migration may define a separate
semantic backup format, but it must not weaken the current evidence.

Backup restore verification requires:

- a valid authenticated manifest;
- exact file evidence matching the manifest;
- successful encrypted archive restoration;
- exact latest sequence, record digest and event count.

No state is returned from an unverified backup.

## Retention planner

The retention planner accepts only an authenticated recovery manifest. It can
identify older records as retention candidates while retaining a configured
number of latest records.

V1 never deletes files. Every plan states:

- `deletion_execution_allowed=false`;
- `deletion_executed=false`;
- explicit operator approval is required;
- backup restore is required when any candidate exists;
- removing an initial chain prefix means the remaining online files cannot be
  independently restored by the PR-32 full-chain verifier.

This avoids representing a backup checkpoint as permission to destroy the
online evidence chain. Physical deletion, compaction and secure erasure require
a separate reviewed execution design.

## Writer-lock diagnostics

The PR-33 writer lock is inspected without modifying it. Diagnostics classify
it as:

- `absent`;
- `active`;
- `stale_candidate`;
- `invalid`.

The age threshold is diagnostic only. An old lock does not prove that the
writer process is dead. Every result retains:

- `automatic_break_allowed=false`;
- `manual_verification_required=true`.

Malformed content, unsafe permissions, symlinks and non-regular lock files are
reported as invalid. This PR never removes a lock.

## Threat boundary

The manifest protects evidence against undetected modification only while its
external HMAC key remains protected. The encrypted backup still depends on the
external AEAD/KMS provider and the PR-32 signing keys.

This PR does not provide:

- automatic backup replication;
- distributed locking;
- automatic stale-lock recovery;
- retention execution;
- compaction or checkpoint-based partial-chain restoration;
- cloud object-store integration;
- key storage or key rotation implementation;
- disaster-recovery scheduling.

## Validation

Focused tests cover:

- primary and byte-identical backup verification;
- manifest serialization, authentication and tamper rejection;
- wrong manifest key and duplicate JSON keys;
- missing backup records and unsafe permissions;
- authenticated backup restoration;
- retention candidate planning without deletion;
- complete-chain retention;
- invalid keep counts;
- absent, active, stale-candidate and invalid writer locks;
- preservation of all read-only and paper-only safety flags.

Regression Shield must pass lock verification, repository policy, compile,
Ruff, formatting, mypy, stable `app:app`, the read-only GPT Actions release
contract, full pytest with coverage, dependency audit, Bandit and secret scan.

## Rollback

Revert the PR merge commit. PR-32 authenticated archives and PR-33 encrypted
atomic storage remain independently usable. No public API, broker permission,
Render configuration or GPT Editor migration is required.
