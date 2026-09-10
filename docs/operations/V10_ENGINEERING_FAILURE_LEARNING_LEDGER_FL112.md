# V10 Engineering Failure Learning Ledger — FL112

## Failure class

`CF_D_DIRECT_BOOTSTRAP_SECURITY_BOUNDARY_AND_PREFLIGHT_GAPS`

## Exact-head evidence

PR #478 exact head `6caa7bf80946c0a4f3e7627087b66c3ce2d37a78` completed the real branch Cloudflare Provider Readiness and CF-C staging Worker + Container acceptance successfully, but the same exact PR head remained RED in independent and authoritative review:

- SonarQube Cloud: `Quality Gate failed`, Security Rating on New Code `C` where `A` is required, with two annotations;
- V10 Engineering Governance: failed at its exact-head Sonar fail-fast step as a consequence of that Sonar RED;
- Self-Hosted Windows CI authoritative merge gate: failed at protected runtime static quality because `ruff format --check` reported `scripts/bootstrap_v10_cloudflare_production_database_direct.py` would be reformatted.

The connected repository interface does not expose the private Sonar annotation payload, so this ledger does not invent rule text, line numbers or a scanner-provided root cause. The changed security-sensitive surface was therefore reviewed directly, including the direct production bootstrap runner, its tests, the release workflow, the staging custody producer and the release-acceptance contract.

## Root-cause and adjacent defect review

Three concrete defects existed in the new direct-bootstrap checkpoint regardless of the unavailable Sonar annotation text:

1. the control-plane handoff persisted a complete HTTPS Function origin and later supplied that dynamic URL directly to a generic URL request object;
2. the regression test embedded fixed synthetic authentication/database credential-shaped literals instead of generating ephemeral test-only values at runtime;
3. the new direct-bootstrap module was published without the canonical formatter preflight that the authoritative Windows lane later rejected deterministically.

The first representation made destination authority less explicit than necessary. The trusted custody response already proves a narrowly constrained Neon branch/function target; the release handoff therefore does not need to persist a complete network URL. The second representation creates avoidable credential-detection ambiguity and violates the repository pattern established by earlier security reviews for synthetic secrets. The third was a process defect: compile and focused semantic review are not substitutes for the exact formatter gate required by the repository.

Blast radius is bounded to the CF-D one-time production database bootstrap path and its tests/contracts. Staging ordinary application traffic, PostgreSQL runtime connections, Cloudflare Workers Builds, product authentication, V9 `app:app`, broker authority and Real execution are not changed.

## Correction

The direct bootstrap boundary is hardened as follows:

- staging custody still validates the exact Neon Function origin before handoff;
- the private runner file now stores only an exact JSON target descriptor with `branch_id` and `cell`, not a URL;
- descriptor keys and values are exact and reconstructed through the existing canonical Function-origin pattern;
- the release runner constructs the only permitted HTTPS hostname from the validated descriptor plus source-controlled literal suffixes;
- transport uses `http.client.HTTPSConnection` on port 443 with the default certificate-validating SSL context, a fixed `/` request target and no redirect/proxy URL machinery;
- response size/content type and provider failure classification remain bounded and fail-closed;
- GitHub OIDC remains short-lived and is sent only in the Function-boundary `Authorization` header;
- the descriptor remains fixed-path, exclusive-create, no-symlink, hardened ACL/POSIX 0600, never logged/output/artifacted, and is deleted after use/cleanup;
- test OIDC/database credentials are generated at runtime with `secrets`, never hard-coded;
- the replacement source is compile-checked and prepared in canonical formatter layout before publication; the authoritative exact-head formatter remains the final proof.

No Sonar suppression, exclusion, Quality Gate reduction, credential-scan weakening or authority widening is used.

## Prevention law

1. A trusted control-plane handoff should carry the minimum provider identity fields required to reconstruct an allowlisted destination, not an arbitrary or complete network URL when the URL is derivable.
2. Outbound privileged control-plane requests must use an explicit scheme/port/path and verified TLS hostname, with redirects and inherited proxy routing absent unless separately required and proven.
3. Synthetic security tests must generate credential-shaped values at runtime; fixed strings that resemble tokens/passwords are forbidden when the exact value is not part of the contract under test.
4. Every new Python security/control-plane file must receive the same focused compile, `ruff check`, `ruff format --check` and relevant typing/test preflight before publication. If the exact formatter is unavailable locally, publication remains provisional and the first authoritative formatter RED is repaired before any dependent work.
5. An inaccessible independent-scanner payload is never guessed. Review the changed security-sensitive data flow, correct proven defects, publish a replacement SHA, and require the scanner itself to certify the replacement.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
