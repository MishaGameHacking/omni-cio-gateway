# Paper Ledger Encrypted Atomic Storage V1

## Purpose

PR-33 attaches a real filesystem storage adapter to the authenticated paper-ledger
archive introduced in PR-32. The adapter encrypts every serialized archive record
through an externally managed authenticated-encryption provider and commits each
immutable record with a same-directory atomic replace.

The storage remains paper-only. It does not expose a FastAPI route, GPT Action,
broker method, database API or execution surface.

## External key-management boundary

The storage module defines `ExternalPaperLedgerKeyManager`. The caller supplies an
implementation backed by an approved AEAD/KMS service.

The adapter passes only:

- a non-secret encryption key ID;
- plaintext archive bytes;
- authenticated associated data.

The adapter never:

- generates encryption keys;
- serializes raw keys;
- logs raw keys;
- stores key material beside ciphertext;
- retrieves keys from environment variables itself;
- claims that a checksum is encryption.

Key rotation is supported record by record through `encryption_key_id`. Recovery
asks the external key manager to decrypt each envelope with the recorded key ID.

The provider must implement authenticated encryption. Production deployments
should use a reviewed AES-256-GCM, ChaCha20-Poly1305 or cloud-KMS envelope-encryption
implementation. Test ciphers are not production providers.

## Encrypted envelope

`PaperLedgerEncryptedEnvelopeV1` stores:

- format and storage versions;
- external AEAD algorithm identifier;
- non-secret encryption key ID;
- UTC creation time;
- archive sequence and authenticated record digest;
- SHA-256 digest of associated data;
- base64 nonce and ciphertext;
- plaintext and ciphertext sizes;
- explicit external-key, authenticated-encryption and atomic-write requirements;
- immutable paper-only safety flags.

The envelope intentionally does not store the masked account ID, currency, ledger
content, positions or operations in plaintext metadata.

Associated data binds:

- storage format;
- creation time;
- sequence;
- authenticated archive-record digest;
- encryption key ID;
- paper-only and disabled-execution flags.

Any change to bound metadata must cause external AEAD decryption to fail.

## Atomic write sequence

One record is committed as follows:

1. reject a symlink storage root;
2. create or normalize the root with mode `0700`;
3. acquire an exclusive `O_CREAT | O_EXCL` writer lock;
4. encrypt and serialize the envelope;
5. create a same-directory temporary file with mode `0600`;
6. write all bytes and `fsync` the temporary file;
7. atomically replace the final immutable filename with `os.replace`;
8. enforce mode `0600` on the final file;
9. `fsync` the parent directory;
10. remove the lock and synchronize the directory again.

A failure before `os.replace` leaves no visible final record. A failure during a
concurrent write fails closed instead of racing two archive sequences.

The adapter does not automatically break stale lock files. Crash-lock recovery,
lock leases and multi-host coordination remain a separate reviewed stage.

## Immutable filenames

Files use:

`<8-digit sequence>-<64-character authenticated record digest>.plae`

The loader rejects:

- sequence gaps;
- duplicate sequence records;
- filename/envelope sequence mismatch;
- filename/envelope digest mismatch;
- symlinks and non-regular files;
- group- or world-accessible files;
- oversized, malformed or duplicate-key JSON;
- invalid base64, nonce or ciphertext size;
- external decryption or authentication failure;
- invalid PR-32 HMAC signatures or broken archive chains.

Recovery returns state only after both layers succeed:

1. external AEAD decryption;
2. complete PR-32 HMAC/hash-chain verification.

## Scope not included

PR-33 does not add:

- cloud object storage;
- SQL or document databases;
- retention and compaction policy;
- automated stale-lock recovery;
- backup replication;
- disaster-recovery orchestration;
- multi-host distributed locks;
- a key-management implementation;
- a public endpoint;
- any real trade execution.

These remain separate stages so that storage security is reviewable and
rollback-safe.

## Validation

Focused tests cover:

- encrypted round trip and absence of plaintext ledger/account content;
- file and directory permissions;
- signing-key and encryption-key rotation;
- ciphertext tampering and wrong keys;
- concurrent writer rejection;
- failure before atomic replace with no partial record;
- immutable sequence conflicts and sequence gaps;
- root and record symlink rejection;
- unsafe file permissions;
- envelope metadata tampering;
- complete authenticated archive recovery.

Regression Shield must pass lock verification, repository policy, compile, Ruff,
formatting baseline, mypy, stable `app:app`, read-only release contract, full
pytest/coverage, dependency audit, Bandit and secret scan before merge.

## Safety invariants

The new envelope and recovered ledger preserve:

- `paper_only=true`;
- `broker_order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

Public GPT Actions, OpenAPI, broker permissions, gateway version `3.9.1` and Render
entrypoint `app:app` are unchanged.

## Rollback

Revert the PR merge commit. PR-32 authenticated archive records and the in-memory
paper ledger remain independently usable. No public API, Render or broker-side
migration is required.
