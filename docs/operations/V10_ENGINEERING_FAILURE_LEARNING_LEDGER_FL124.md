# V10 Engineering Failure Learning Ledger — FL124

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_FUNCTION_PROVENANCE_HEADER_DISCRIMINATOR_NOT_LIVE_PROOF`
- Scope: exact-source provenance ingress only

## Observed failure

After PR #487 was accepted, exact main `934dde392b3d186fccb1aa62c19e4748b4fd1859` completed all 11 required post-merge push workflows, including Regression Shield. The exact Function bundle was then converged through the already-authorized provider control plane and confirmed active/current before the automatic production release continued.

The release again passed the exact-SHA staging build, single-version deployment, pre-custody release proof and bootstrap-origin custody, then treated Function provenance as stale and entered the write-required recovery path. The least-privilege Neon credential correctly rejected that write with the existing `CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT` classification. Production promotion was not reached.

Function telemetry for the provenance-probe window contained no matching request invocation after the independently observed deployment event. This is supporting evidence only; no undocumented provider implementation behavior is asserted.

No provider response body, Function URL, project/branch identifier, credential, OIDC token, database secret or private payload is recorded here.

## Root cause

The accepted provenance design still made production correctness depend on request-header discrimination at canonical `GET /`. Live evidence after both the project-owned custom header and the fixed standard `User-Agent` fallback did not produce an exact-source proof. The evidence establishes that the header-dependent tuple is insufficient as the production provenance contract; it does not establish which upstream component transformed, consumed or handled that tuple.

This is a provenance transport defect, not a reason to weaken digest equality, broaden Neon Management API write authority, ignore the 403, or bypass staging/release gates.

## Permanent correction

- Keep the canonical Function path `/`.
- Make the primary no-secret provenance discriminator the exact root request target `/?omni_source_provenance=v1`.
- The wrapper recognizes that exact query independently of request-header preservation.
- Retain the prior empty-query project-header/fixed-User-Agent discriminator only as bounded compatibility fallback.
- Plain bootstrap `GET /` and privileged OIDC `POST /` remain delegated to the canonical handler unchanged.
- TLS hostname/certificate verification, no-redirect policy, bounded response size, deterministic SHA-256 equality, active/current deployment identity and deployment-race checks remain unchanged.
- Function management write remains conditional on genuine source drift only.

## Permanent regression / guard

Deterministic tests pin the exact HTTP request target, root path, exact query discriminator, existing non-secret header compatibility, distinct bootstrap/provenance User-Agents, handler delegation and machine-readable release contract. A custom provenance subpath remains forbidden.

## Prevention law

When no-secret provenance must cross an external HTTP front door, the primary discriminator must use an end-to-end proven request component. If live evidence shows that header discrimination is not sufficient, move the discriminator into the bounded request target before considering any authority expansion. Provider write authority must never be widened to compensate for provenance transport failure.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; WP23+, WEB VISUAL, Telegram and AI/Cortex remain out of scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
