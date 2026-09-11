# V10 Engineering Failure Learning Ledger — FL123

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_FUNCTION_PROVENANCE_CUSTOM_HEADER_VISIBILITY_GAP`
- Scope: exact-source provenance discriminator for the production database bootstrap Function only

## Exact-main evidence

After PR #486 was accepted, exact main completed all 11 required post-merge push workflows successfully. The automatic CF-D production release reached an exact staging build, exact single-version staging deployment, exact-SHA pre-custody release and bootstrap-origin custody, then stopped before production promotion because the Function source-provenance probe classified the active Function source as drifted and selected the write-required recovery path. The least-privilege Neon credential correctly rejected that write with the existing `API_KEY_INSUFFICIENT / 403` classification.

The canonical Function source was then independently converged to the exact accepted-main bundle and verified active/current in the provider control plane. A clean retry of the same exact-main release reproduced the identical source-drift classification and `403`. The retry started only after provider deployment convergence had completed, excluding a simple deployment-propagation race.

The provenance parser can return a non-matching result without raising only for the exact source-controlled `405 / METHOD_NOT_ALLOWED` response or for a valid provenance digest mismatch. The deployed bundle was byte-exact to accepted main and had already passed the deterministic source-digest construction. The observed path therefore demonstrates that the custom provenance discriminator cannot be the sole runtime-visible discriminator for this provider ingress shape.

Function telemetry for the clean retry window contained no additional invocation records. Because Neon Functions observability is beta and telemetry completeness is not an application authority boundary, that absence is supporting evidence only; the repair does not depend on claiming an undocumented provider implementation detail.

No provider identifier, Function URL, OIDC token, database credential or secret value is recorded here.

## Root cause

PR #486 correctly moved provenance to the provider-supported Function root and preserved exact digest verification, but it still made provenance interception depend exclusively on the new project-owned `X-Omni-Source-Provenance: v1` request header. That header visibility inside the Function `Request` object had not been independently proven on the live provider path.

The release probe already sends a fixed non-secret `User-Agent` value on the same request. The ordinary bootstrap preflight uses a different fixed `User-Agent`, so the two request classes are deterministically distinguishable without relaxing method, path, query, source digest, TLS, response-size or deployment identity checks.

This is a provenance discriminator transport defect. It is not a reason to weaken source digest equality, accept malformed responses, broaden Neon Management API write authority, bypass exact-main gating, or change database/broker execution authority.

## Permanent correction

The provenance wrapper now treats either of these no-secret discriminators as sufficient only when the rest of the request tuple is still exact `GET /` with an empty query:

- `X-Omni-Source-Provenance: v1`; or
- the fixed release probe `User-Agent` `omni-cio-v10-cf-d-neon-function-deploy/2`.

The existing custom-header contract is retained for explicit project ownership, while the standard-header discriminator prevents provenance correctness from depending on visibility of that one custom header. Ordinary bootstrap `GET /` uses a different fixed User-Agent and therefore continues to delegate to the canonical handler and return `METHOD_NOT_ALLOWED`; bootstrap `POST /` behavior and GitHub OIDC validation remain unchanged.

## Regression guard

`tests/test_v10_cloudflare_neon_function_provenance_ingress.py` now requires:

- the release probe to keep the exact root request, fixed User-Agent and no-secret provenance header;
- the wrapper to recognize the fixed standard User-Agent as a deterministic fallback;
- the bootstrap preflight User-Agent to remain distinct from the provenance User-Agent;
- the exact method/path/empty-query boundary and canonical handler delegation to remain intact;
- the machine-readable root-ingress contract and custom provenance header contract to remain unchanged.

## Reuse rule

A source-provenance request may use a no-secret discriminator, but correctness must not depend on an unproven header namespace being visible after provider ingress processing. Where a fixed standard request attribute is already part of the accepted transport and is disjoint from privileged request classes, it may be used as a bounded secondary discriminator while all cryptographic and source-identity checks remain fail-closed.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no WP23+/Web Visual/Telegram/AI/Cortex scope is opened; no provider secret or private payload is written to source, logs or artifacts.
