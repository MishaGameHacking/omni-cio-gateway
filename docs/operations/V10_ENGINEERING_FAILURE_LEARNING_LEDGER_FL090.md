# V10 Engineering Failure Learning Ledger — FL090

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main production database bootstrap after accepted main `59575bd4b247b887a676fbb770babd784698e8c2`.

Owning external blocker: `#430`.

## Failure observed

Fresh exact-main production release run `33917756467` completed the protected post-merge gate, Cloudflare authority checks, exact-main staging Worker/Container rehearsal and staging live acceptance. The existing staging database secret was healthy and reused. The production Worker anchor was also created successfully.

The release then reached the only remaining database bootstrap path because the production Cloudflare `OMNI_V10_POSTGRES_DSN` secret did not yet exist. That fallback still depended on the protected static Neon API credential. Exact-project and exact-branch reads returned HTTP `403`, so the workflow stopped fail-closed before production promotion, Custom Domain mutation or canonical live acceptance.

The canonical Neon project and database were independently healthy through the connected Neon control surface: PostgreSQL 18, Frankfurt region, accepted migrations and the existing staging least-privilege role were present. The missing production runtime role therefore could not be created only because the GitHub-held Neon management credential lacked the required exact-project authority.

## Root cause class

`CF_D_STATIC_NEON_CONTROL_PLANE_CREDENTIAL_COUPLING`

The production first-bootstrap path had an unnecessary dependency on a long-lived Neon management API credential even though the database platform already exposes a branch-scoped execution surface with injected database credentials. This made Cloudflare production bootstrap availability depend on an unrelated provider-management credential whose authority had repeatedly drifted.

The defect is not solved by weakening the exact-project `403` check, broadening the Neon key, hardcoding a database credential, committing provider identifiers, or treating diagnostics as success.

## Correction

CF-D production first-bootstrap uses a dedicated short-lived federated path:

1. The production release job requests a GitHub Actions OIDC token only after all exact-main post-merge gates and the exact-main staging rehearsal have succeeded.
2. The token uses a dedicated audience and is never written to logs, source, summaries or artifacts.
3. A staging-only internal Cloudflare API route forwards that token to a source-controlled Neon Function. Production runtime never exposes this route.
4. The staging route derives the Function origin in-process from the connected Neon branch metadata and database endpoint cell; no Neon project or branch identifier is committed or emitted.
5. The Neon Function verifies the GitHub issuer/JWKS signature and exact repository, private visibility, main ref, workflow, workflow ref, workflow SHA, source SHA, event and self-hosted runner claims before any database mutation.
6. The Function uses only Neon-injected branch-scoped `DATABASE_URL` / `DATABASE_URL_UNPOOLED`; it does not consume `NEON_API_KEY`, `NEON_PROJECT_ID`, `NEON_ORG_ID` or a committed database credential.
7. The production runtime password is deterministically derived with HMAC-SHA384 from the Neon-injected owner credential and a domain-separated constant. Replaying the same authorized bootstrap does not rotate the runtime password to a different value.
8. Role convergence preserves the existing least-privilege boundary: LOGIN only, no superuser/CREATEDB/CREATEROLE/replication/BYPASSRLS, no inherited memberships, no database/schema/object ownership, exact object grants and FORCE RLS on broker tables.
9. The resulting production DSN exists only in process memory, a fixed `RUNNER_TEMP` file with private permissions, and the protected Cloudflare secret. It is never printed.
10. Once the Cloudflare production secret exists, later releases reuse it and do not execute the federated bootstrap.

The existing static Neon API path remains available only for the already-established staging recovery fallback when the staging runtime secret itself is absent. A healthy staging secret does not require that credential.

## Regression invariant

Deterministic tests and guards require that:

- `V10 Cloudflare Production Release` has `id-token: write` but no additional GitHub write permission;
- the production database bootstrap step contains no `NEON_API_KEY`, `NEON_ORG_ID`, `NEON_PROJECT_ID`, exact-project probe or Neon management provisioner;
- the static Neon API provisioner remains limited to staging-secret recovery in that workflow;
- the internal bootstrap route is installed only for `omni_cio_cloudflare_staging`;
- the route requires the exact release SHA and a bounded Bearer token, disables redirects/proxy inheritance and returns `Cache-Control: no-store`;
- the Neon Function contains no provider IDs, management API keys, committed DSNs or credential logging;
- OIDC verification is RS256/JWKS-based and checks the exact release authority claims rather than relying on the mutable/default `sub` format;
- an unknown OIDC signing `kid` triggers at most one forced JWKS refresh before fail-closed rejection, so signing-key rotation does not leave a valid token blocked behind a still-live stale cache;
- the staging proxy consumes the Neon Function response as a bounded stream and stops before buffering an oversized body;
- only PostgreSQL 18 in the Frankfurt Neon region is accepted;
- role/object ownership drift and privilege widening fail closed;
- the runtime credential derivation is deterministic for the same owner credential;
- runtime DSNs are accepted only for `omni_cio_cloudflare_prod` with TLS required;
- broker-write, `trading_methods` and `REAL_TRADING_ENABLED` invariants are untouched.

## Permanent learning

- Provider management credentials and workload identity are different authority classes. A production runtime bootstrap should not depend on a long-lived provider-management key when a narrowly scoped workload-identity path can perform exactly the required operation.
- Removing a failing secret dependency must not replace it with a hardcoded identifier, broad account authority, public unauthenticated endpoint or suppressed failure.
- Short-lived OIDC is only safe when the receiver verifies exact workflow provenance and source identity before mutation.
- Bootstrap retries must be credential-idempotent. Replaying an otherwise valid short-lived assertion must not silently rotate a production database password to a new value.
- Secret custody remains end-to-end: provider-injected owner credentials, OIDC assertions and generated runtime DSNs are process/private-file/provider-secret material only.

## Verification-batch follow-up — PR #449 exact head `60935d37a54d35794277a993992a8781e71c480d`

The first full exact-head verification batch exposed one deterministic preflight miss and two adjacent review findings before merge.

Self-Hosted Windows CI run `33948910200`, authoritative job `101259879426`, reached `Run protected runtime static quality`. Ruff correctness passed, but `ruff format --check` rejected `scripts/bootstrap_v10_cloudflare_production_database_via_staging.py`. The job is therefore RED. Full pytest, dependency audit, SAST and tracked-content secret scanning after that fail-fast step were skipped and are not PASS evidence.

The formatter defect was local in code shape but systemic in process: the focused preflight compiled and unit-tested the new bootstrap code without running the accepted formatter gate on every changed Python file. The correction applies the accepted Ruff formatting and this batch may not be treated as final until a fresh exact-head cycle runs.

Independent PR review also identified two credible resilience gaps in the same new bootstrap path:

1. a cached GitHub JWKS set with no matching token `kid` caused immediate rejection and did not perform one bounded cache-bypassing refetch, creating an avoidable transient failure during signing-key rotation;
2. the staging proxy checked `_MAX_PROVIDER_RESPONSE_BYTES` only after `httpx` had buffered the complete provider response, so the size guard did not actually bound response-body memory use.

The blast radius is limited to the new CF-D federated production-bootstrap path: the Neon Function OIDC verifier, the staging-only proxy route, their deterministic tests and the bootstrap CLI formatter surface. No V9 runtime, tenant model, broker authority, general Cloudflare release sequencing or staging static-Neon recovery authority is changed.

The coherent correction batch therefore:

- refreshes JWKS exactly once only when the cached set contains zero matching RSA keys for the requested `kid`, then preserves exact-one-key fail-closed validation;
- streams the provider response through fixed-size chunks and aborts once the decoded byte budget is exceeded;
- adds deterministic regression guards for the one-time JWKS refresh path and early oversized-response termination;
- applies the exact Ruff formatting required by the authoritative gate.

Future authentication/provider bootstrap changes must include compile/static checks, focused positive/negative tests, `ruff check`, `ruff format --check`, secret-shape review and directly coupled transport/rotation failure-mode review before an exact-head verification batch is published.

## Verification-batch follow-up — PR #449 exact head `4f3fac299e7104caf6156b0bc6d27ddbd069a9fb`

The next exact-head authoritative batch proved the formatter correction but exposed a Windows-specific secret-file custody defect in the new bootstrap implementation and its regression assertion.

Self-Hosted Windows CI run `33952214377`, authoritative job `101269010433`, passed PostgreSQL 18 rehearsal, repository/CI policy contracts, compile, Ruff correctness, Ruff formatting, mypy, protected `app:app` and the read-only release contract. The full Regression Shield then completed 2914 tests successfully before one focused CF-D test failed; branch-inclusive coverage remained above the required threshold at 62.20%.

The failing test expected POSIX mode `0600` from `path.stat().st_mode` after `_write_private_file()`. On Windows the observed mode bits were `0666`. This is not a reason to relax the test: the implementation itself was relying on `os.open(..., 0600)` plus `os.chmod(..., 0600)` as if POSIX permission bits represented the Windows confidentiality boundary. They do not establish an NTFS DACL boundary, so the failure exposed a real platform-assumption gap in the production DSN custody path.

Because pytest failed, dependency audit, SAST and tracked-content secret scanning in that authoritative job were skipped and are not PASS evidence. Exact head `4f3fac299e7104caf6156b0bc6d27ddbd069a9fb` is RED.

The blast radius is limited to the new fixed `RUNNER_TEMP` production-DSN handoff file and its focused tests. No database role, OIDC claim validation, Cloudflare secret destination, provider authority, V9 runtime or broker authority is affected.

The correction strengthens the custody boundary rather than weakening the assertion:

- the output file is now created exclusively and refuses a pre-existing path instead of truncating it;
- no DSN content is written until the platform-specific permission boundary has been applied and verified;
- Windows uses a protected NTFS DACL through the existing repository `Set-Acl` / SID pattern, removes inherited and unexpected rules, and grants FullControl only to the current runner identity, LocalSystem and the built-in Administrators group;
- the Windows ACL helper receives only a minimal non-secret child environment plus the fixed file path, suppresses subprocess output, uses bounded execution time and fails closed on any apply/verification error;
- Unix-like hosts retain explicit `0600` mode enforcement and verification;
- a permission-hardening failure removes the still-empty handoff file before returning failure;
- deterministic regression tests cover the exact SID allowlist, inheritance protection, minimal environment, fail-closed ACL rejection, exclusive-create behavior and cleanup-before-secret-write semantics;
- the authoritative Windows test now relies on the production ACL helper's own apply-and-verify result instead of treating POSIX mode bits as the Windows authority model.

Future cross-platform secret-file tests must assert the operating system's actual access-control primitive. POSIX mode assertions remain valid on Unix-like systems; Windows confidentiality must be proven through an explicit protected DACL or an equivalent accepted Windows security descriptor.

## Security and authority invariants preserved

- protected V9 `app:app` is unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged;
- broker write remains OFF;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- no Telegram/VK provider activation is introduced;
- no Neon API key, provider identifier value, database DSN, OIDC token or tenant-private payload is committed or logged;
- production remains behind exact-main post-merge, staging, rollback and canonical live-acceptance gates.
