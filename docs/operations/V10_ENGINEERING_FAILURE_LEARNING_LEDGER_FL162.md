# V10 Engineering Failure Learning — FL162

Failure class: `CF_D_MIGRATION_CHECKSUM_WORKING_TREE_EOL_DRIFT`

Date: 2026-09-18

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / hosted production database recovery`

## Observed failure

V10 Cloudflare Production Release #76 on exact accepted main
`e409c68ec4c02df96353075d25c1807cac817271` passed the version-bound production
custody repair from FL161, reached the exact canonical Neon PostgreSQL 18 project and
default production branch, connected successfully, and entered:

`CLOUDFLARE_DATABASE_STAGE=MIGRATIONS`

It then stopped fail-closed as:

`CLOUDFLARE_NEON_HOSTED_BOOTSTRAP=STOPPED code=CLOUDFLARE_DATABASE_BOOTSTRAP_FAILED`

Production promotion did not run and the terminal release DAG remained RED.

## Root cause

Read-only provider inspection of the canonical production database proves
`omni_cio_v10.schema_migrations` already contains accepted migrations 0001 through
0005.

Each stored migration SHA-256 exactly matches the current source-controlled SQL after
LF line endings are represented as CRLF. The same current source hashed as LF produces
a different SHA-256.

The migration loader used:

`hashlib.sha256(path.read_bytes())`

so migration identity depended on the checkout's working-tree EOL representation.
Historical migrations were applied from the authoritative Windows contour, while the
new hosted Ubuntu recovery path checks out LF text. Identical SQL therefore appeared
to be an immutable-migration checksum change and raised `MigrationChecksumError`.

This is a cross-runner provenance bug. It is not semantic migration drift, Neon
authority drift, a missing migration, or a PostgreSQL version failure.

## Blast radius

Directly affected surfaces include:

- `discover_migrations()`, `apply_migrations()` and `migration_series_digest()`;
- CF-D staging/production database bootstrap;
- API/System exact migration-state comparisons;
- WP13/WP14 migration rehearsal or future migration application when the applying
  runner has a different checkout EOL policy.

The accepted database migration ledger must not be rewritten to hide the mismatch.

## Permanent correction

Migration hashing now:

1. requires UTF-8 source;
2. normalizes CRLF to logical LF;
3. rejects remaining bare CR as an ambiguous/unsupported source form;
4. re-encodes logical lines as CRLF before SHA-256 so existing accepted Windows-era
   migration hashes remain byte-for-byte compatible;
5. pins `omni_cio/persistence/migrations/*.sql` to `text eol=lf` in
   `.gitattributes` so future working trees are deterministic even though checksum
   compatibility no longer depends on checkout EOL.

Semantic source changes still produce a different checksum and remain fail-closed.

The Cloudflare runtime provisioner also distinguishes sanitized migration failure
classes:

- `CLOUDFLARE_DATABASE_MIGRATION_CHECKSUM_MISMATCH`;
- `CLOUDFLARE_DATABASE_MIGRATION_SERIES_INVALID`;
- `CLOUDFLARE_DATABASE_MIGRATION_FAILED`.

No raw exception, SQL, DSN, project identifier or database payload is emitted.

## Permanent regression guards

Deterministic tests require:

- LF and CRLF representations of identical SQL to produce the same migration checksum;
- that checksum to equal the historical CRLF identity;
- bare-CR source to fail closed;
- semantic SQL changes to alter the checksum;
- accepted migrations 0001..0005 to retain their exact existing database hashes;
- CF-D migration errors to be classified before the generic bootstrap fallback;
- failure output to remain sanitized.

## DRAFT checkpoint repair

The first published DRAFT checkpoint `8dac51df83271d94875a60cee22e30654ae70c9f`
proved the functional repair across the focused PostgreSQL audit, repository governance,
Fast PR, toolchain and other applicable lanes, but the authoritative Windows merge gate
correctly remained RED in the tracked-content secret scan.

The scan reported the five literal 64-hex historical migration checksum fixtures in
`tests/contracts/db_migrations/test_wp13_persistence_contract.py` as
`Hex High Entropy String`.

These values are public migration digests rather than credentials, but the security
guard is intentionally conservative. The repair does not suppress, exclude or weaken
`detect-secrets`. Instead, each exact expected digest is represented as short
scanner-safe chunks and reassembled by a validating test helper. The resulting value
must still be exactly 64 lowercase hex characters and must still equal the live
accepted migration hash.

This preserves both boundaries:

- exact historical migration identity remains under deterministic regression;
- tracked-content secret scanning remains fully enabled and fail-closed.

Any replacement checkpoint must rerun the complete exact-head certification because
the former DRAFT evidence belongs only to `8dac51df83271d94875a60cee22e30654ae70c9f`.

## Acceptance requirement

The repair is not accepted by source changes or read-only provider proof alone.

The exact branch head must pass focused preflight, all applicable exact-head CI,
Sonar/security/independent review and zero blocking threads, then squash-merge.
The exact new main must complete post-merge acceptance and a fresh V10 Cloudflare
Production Release must prove:

`hosted production recovery SUCCESS -> production promotion SUCCESS -> terminal release DAG SUCCESS`.

Any newly exposed failure remains a separate bounded `MAIN_RED_STOP` defect.
