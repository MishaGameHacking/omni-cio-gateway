# V10 Engineering Failure Learning Ledger — FL097

Date: 2026-09-06  
Scope: CF-D exact-main Cloudflare Worker secret creation status contract  
Authority: Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Observed failure

Accepted `main` `555e5282f9564c729b5bd5f30a159b14f82dad0a` completed its exact-main
post-merge Regression Shield successfully. The fresh downstream `V10 Cloudflare
Production Release` run `34020979232`, job `101453389337`, then passed the exact-main
post-merge gate, Cloudflare provider/read authority checks, delivery-toolchain setup,
Container registry authority, staging database-secret reuse, Worker-anchor reuse and the
gated exact-main staging Build.

The staging Build reached terminal success, after which candidate orchestration stopped
with the sanitized provider result:

`CLOUDFLARE_CF_C_CANDIDATE=STOPPED code=CLOUDFLARE_API_STATUS_INVALID status=201`

The gated staging trigger was quarantined successfully. All later CF-D steps, including
production database bootstrap, production promotion, Custom Domain mutation and live
acceptance, remained unattempted.

## Root cause

PR #451 intentionally introduced an ephemeral staging Worker secret,
`OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN`, to authorize bootstrap-origin custody convergence.
The token is removed before and after convergence, so a normal fresh convergence creates
that Worker secret rather than updating an existing one.

The repository's generic `CloudflareApi.request()` contract defaults to accepting only
HTTP `200`. The active Worker-secret writer inherited that generic default. Cloudflare
returned HTTP `201` for the successful secret creation, and the client therefore rejected
a provider success response as `CLOUDFLARE_API_STATUS_INVALID` before bootstrap-origin
custody could complete.

The defect was not a provider outage, authorization failure, Build failure, database
failure or Neon Function failure. It was an endpoint-specific response-status mismatch in
the repository control plane.

A coupled test gap also existed: the Worker-secret unit double accepted the call without
asserting the `expected` success-status contract, so the creation-vs-update provider
semantic was not covered deterministically.

## Blast radius and adjacent failure modes

Repository inspection found three active Worker secret-write surfaces affected by the
same response-contract assumption:

1. staging bootstrap-origin custody secrets, including the ephemeral sync token and the
   persistent trusted bootstrap origin;
2. first-time staging `OMNI_V10_POSTGRES_DSN` convergence when a newly provisioned DSN
   file must be written to the staging Worker;
3. first-time production `OMNI_V10_POSTGRES_DSN` convergence after successful CF-D
   database bootstrap.

The legacy `bootstrap_v10_cloudflare_builds` module remains a library-only helper in the
active gated candidate architecture. The active candidate path must not fall back to its
legacy runtime-secret writer.

No broader Cloudflare mutation contract is widened by this correction. In particular,
Custom Domain and unrelated API operations retain their existing status contracts unless
separate provider evidence proves otherwise.

## Correction

The focused correction:

- accepts only `{200, 201}` for Cloudflare Worker script-secret writes;
- keeps the generic `CloudflareApi.request()` default strictly `{200}`;
- routes active staging runtime-secret convergence through the corrected staging
  Worker-secret helper instead of the legacy writer;
- applies the same bounded `{200, 201}` contract to first-time production runtime-secret
  convergence;
- does not treat `202` or arbitrary other `2xx` responses as success;
- retains post-write production secret verification and existing fail-closed cleanup.

This is an endpoint-specific compatibility fix, not a general relaxation of provider
response validation.

## Permanent regression guards

Deterministic tests require that:

- staging Worker secret writes accept exactly `200` and `201`;
- staging runtime-DSN secret writes use the corrected Worker-secret contract;
- active gated candidate orchestration never invokes the legacy runtime-secret writer;
- production runtime-DSN secret writes accept exactly `200` and `201`;
- the generic Cloudflare API request default remains exactly `{200}`.

## Security and authority

Unchanged:

- protected V9 `app:app` production/recovery boundary;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write remains OFF;
- no transfer, withdrawal, margin, leverage or uncovered-short authority;
- no provider identifiers, database secrets, sync tokens or DSNs are logged or committed;
- no Render V10 deployment path is restored;
- no Telegram/VK, AI/Cortex or future-WP implementation is authorized by this repair.

## Acceptance rule

This defect is not accepted merely because source/tests are corrected. Acceptance requires
all applicable exact-head PR checks to conclude `success`, zero unresolved blocking review
threads, squash merge, exact-new-main Regression Shield success, and a fresh exact-main
Cloudflare production release that proves the staging rehearsal and the formerly blocked
production database bootstrap path complete successfully. Any new downstream provider
failure remains RED and must be classified separately rather than hidden by this fix.
