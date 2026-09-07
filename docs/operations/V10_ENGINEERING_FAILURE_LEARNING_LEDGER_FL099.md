# V10 Engineering Failure Learning Ledger — FL099

Date: 2026-09-07  
Scope: CF-D exact-main staging bootstrap-origin custody version/deployment ordering  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Observed failure

Accepted protected `main` `70e5a05809c45043a85f4d2175a0c260f265139f` completed
Regression Shield run `34088646739` successfully. Downstream `V10 Cloudflare Production
Release` run `34089444931` / run number 25 then passed the exact-main post-merge gate,
Cloudflare provider/Workers Builds authority, pinned delivery-toolchain bootstrap,
Container-registry read authority, staging database-secret reuse, staging Worker-anchor
reuse and the gated exact-SHA staging Build.

The staging Build reached terminal success and orchestration then stopped at bootstrap
origin custody with:

`CLOUDFLARE_CF_C_CANDIDATE=STOPPED code=CLOUDFLARE_CF_D_ORIGIN_SYNC_REJECTED`

The temporary gated trigger was quarantined successfully. Production database bootstrap,
production promotion, Custom Domain mutation and canonical live acceptance were not
attempted.

## Root cause

The repository armed the short-lived `OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN` only **after** the
exact-SHA staging Build had already been accepted. That secret write uses Cloudflare's
legacy script-secret endpoint:

`PUT /accounts/{account_id}/workers/scripts/{script_name}/secrets`

Cloudflare's current first-party Workers documentation defines a Worker version as a
snapshot of code plus configuration/bindings, and a deployment as the version actually
serving traffic. Cloudflare also documents that ordinary `wrangler secret put` creates a
new Worker version and deploys it immediately. Cloudflare's Workers API changelog records
that legacy settings/secret endpoints historically coupled simple configuration changes
to implicit version creation and deployment.

Therefore the accepted orchestration sequence was not actually:

`exact Build SUCCESS -> custody proof`

It was:

`exact Build SUCCESS -> sync-token secret mutation -> new implicit Worker version/deployment -> custody proof`

The pipeline consequently invalidated the exact deployment state it had just proved before
calling the security-sensitive custody endpoint. This created a real version/configuration
race: the request could reach an older/newly propagated version whose compiled source SHA
and secret binding were not the exact pair the custody request expected.

A second diagnostic defect amplified the problem. The Python control plane collapsed every
non-200 custody response into `CLOUDFLARE_CF_D_ORIGIN_SYNC_REJECTED`, even though the
Worker intentionally distinguishes unauthorized/exact-SHA or token failure (`403`), route
absence (`404`) and Neon branch/origin derivation failure (`502`). The exact provider
subclass was therefore lost in run 25.

## Blast radius

The defect class is any legacy Worker secret mutation placed between an exact-version
acceptance point and a later request that assumes the accepted version is still active.
Directly coupled surfaces reviewed include:

- ephemeral staging `OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN` custody;
- persistent staging `OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN` custody;
- staging `OMNI_V10_POSTGRES_DSN` first-time convergence;
- production `OMNI_V10_POSTGRES_DSN` first-time convergence;
- exact-SHA staging live acceptance after candidate orchestration.

The existing production release already performs a fresh exact-SHA `/api/v10/release` and
`/healthz` acceptance after candidate orchestration, so post-custody persistent-secret
mutation remains fail-closed behind that live revalidation. No V9, broker, Telegram/VK,
public-user or Real-money authority is changed by this correction.

## Corrective change

The custody lifecycle is made version-bound:

1. Generate and mask the fresh 256-bit synchronization token.
2. Remove any stale token and arm the new staging Worker secret **before** the gated
   exact-SHA Build starts.
3. Verify the token binding exists before starting the Build, so the Build inherits the
   intended secret state.
4. Start and wait for the exact-SHA gated staging Build.
5. After Build success, perform only read/network operations until bootstrap-origin custody
   is proved; no Worker secret mutation is allowed in this interval.
6. Preserve sanitized HTTP failure classes (`403`, `404`, `502`, `503`, unexpected status)
   and retry only the explicit bounded rollout/transient classes plus transport failure.
7. Remove and verify absence of the ephemeral synchronization token on every success/failure
   path before persisting the trusted bootstrap origin.
8. Persist the trusted bootstrap origin only after successful same-SHA custody proof.
9. Retain the existing following exact-SHA live staging acceptance, which re-proves the
   final serving source/health/database state after the cleanup/persistent-secret mutations.

This correction does not weaken exact SHA, TLS, token authentication, Frankfurt Neon
same-branch/same-cell validation, trigger quarantine or any fail-closed gate.

## Permanent regression guards

Deterministic tests now require:

- synchronization-token arm before exact manual Build start;
- Build terminal success before custody proof;
- no secret mutation between Build acceptance and custody proof;
- token cleanup before persistent origin write;
- cleanup on Build/custody failure and fail-closed cleanup failure;
- exact 256-bit lowercase-hex token validation;
- distinct sanitized `403`/`404`/`502`/`503`/unexpected-status classification;
- bounded retry only for the explicit rollout/transient set;
- machine-readable release-contract fields freezing the version-bound lifecycle;
- existing post-custody exact-SHA live staging revalidation.

## Why earlier preflight missed it

PR #451 focused on establishing missing producer/convergence custody and PR #452 corrected
the endpoint-specific HTTP `200/201` success contract. Their deterministic doubles treated
secret writes as configuration mutations but did not model Cloudflare's version/deployment
side effect. The gap was therefore not the secret value or HTTP success code; it was the
provider lifecycle semantics of the accepted write endpoint.

Future Cloudflare control-plane changes must treat Worker code, bindings, versions and
deployments as one coupled state machine. A successful configuration API response is not
proof that the previously attested serving version remains authoritative.

## First-party provider references

- Cloudflare Workers — Versions & deployments:
  `https://developers.cloudflare.com/workers/versions-and-deployments/`
- Cloudflare Workers — Secrets:
  `https://developers.cloudflare.com/workers/configuration/secrets/`
- Cloudflare changelog — A new, simpler REST API for Cloudflare Workers:
  `https://developers.cloudflare.com/changelog/post/2025-09-03-new-workers-api/`

## Acceptance rule

Source/tests alone do not make this defect accepted. The focused correction requires normal
protected-branch exact-head SUCCESS-only verification, zero blocking review threads, squash
merge, exact-new-main Regression Shield success and a fresh exact-main Cloudflare production
release that passes the formerly failing staging custody boundary. Any newly exposed
provider failure remains RED and must be classified separately rather than hidden by this
repair.
