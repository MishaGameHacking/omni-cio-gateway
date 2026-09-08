# V10 Engineering Failure Learning Ledger — FL104

Date: 2026-09-08  
Scope: CF-D Worker script-secret read-after-mutation convergence  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor

PR #468 was squash-merged as protected `main`
`8cde74950eb2143ad3daa8150e05780d27d20f22`. The exact-main post-merge gate later
reported all 11 observed push workflows ready, and Regression Shield run `34243727871`
completed both quality/contracts/coverage and dependency/code/secret-security jobs with
terminal `success`.

Automatic `V10 Cloudflare Production Release` run `34245003070`, job `102124622259`,
then passed the exact-main post-merge gate, Cloudflare provider and Workers Builds
authority, pinned delivery toolchain, Containers registry authority, hashed provider
control-plane dependencies, staging database-secret reuse, staging Worker-anchor reuse,
gated exact-SHA manual Build, exact single-version deployment proof and pre-custody
exact-SHA `/api/v10/release` proof.

Candidate orchestration then stopped fail-closed with:

`CLOUDFLARE_CF_C_CANDIDATE=STOPPED code=CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE`

The temporary staging trigger was quarantined and workspace/private-file cleanup
succeeded. Production database bootstrap, production Build/promotion, Custom Domain
mutation and canonical live production acceptance were not attempted.

Owning defect: #469.

## Root cause class

`CF_D_WORKER_SECRET_CONTROL_PLANE_CONVERGENCE_SINGLE_READ_ASSUMPTION`

The version-bound custody lifecycle correctly removes the short-lived
`OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN` after custody proof and requires the token to be absent
before persisting the trusted bootstrap origin. The implementation, however, treated one
immediate control-plane read after a successful script-secret mutation as definitive:

`DELETE -> one GET/list -> TOKEN_STALE if the first read still shows the binding`

The observed `TOKEN_STALE` code proves that the DELETE path returned without a prior API
error; otherwise the source-controlled cleanup path would have emitted the separate cleanup
failure class. The immediately following valid secret-state read still observed the binding.
The defect was therefore the synchronous single-read assumption, not evidence that a second
DELETE was required or safe.

Cloudflare's current first-party Workers documentation defines a Worker version as a
snapshot that includes bindings and states that ordinary `wrangler secret put` creates a new
version and deploys it immediately. Current Wrangler command documentation applies the same
version/deployment behavior to the `secret` action, and the Workers versions/deployments
documentation states that configuration changes create versions while deployments select
what serves traffic. These facts make Worker secret mutation a deployment-coupled
control-plane transition rather than an in-process dictionary mutation.

The first-party documentation does not provide an accepted guarantee that the legacy
script-secret list endpoint must reflect a just-completed mutation in the very first
subsequent read. The repository therefore must not invent such a guarantee. It must instead
allow only a short, bounded, read-only convergence window and then fail closed if the
expected state still cannot be proved.

## Blast radius and adjacent review

The same assumption or a weaker missing-verification variant existed in directly coupled
secret transitions:

- stale custody-token DELETE before arming a new token;
- custody-token PUT -> presence proof before exact Build start;
- custody-token DELETE -> absence proof before persistent-origin write;
- persistent bootstrap-origin PUT -> presence proof;
- staging database-secret first-time PUT, which previously printed `READY` immediately
  after write without a bounded state proof;
- production `OMNI_V10_POSTGRES_DSN` first-time PUT -> one immediate presence proof before
  production Build/promotion.

The legacy `_put_runtime_secret()` helper in `bootstrap_v10_cloudflare_builds.py` remains
outside the active candidate path; the accepted candidate guard already requires the active
path to use `put_staging_runtime_secret()` instead. It is not reactivated by this defect fix.

The exact-SHA/version custody ordering from PR #455 remains mandatory. In particular, no
secret mutation is introduced between exact staging Build/live-release proof and custody
proof. Secret convergence is checked only after the mutation points that already exist in
the accepted lifecycle.

## Corrective change

The correction introduces one shared bounded state-convergence primitive for Worker secret
control-plane reads:

- maximum 15 state reads;
- 2-second delay between non-matching reads;
- the mutation is never repeated merely because visibility has not converged;
- the state reader is the only operation repeated;
- reader/API/shape/duplicate/type-drift failures are not swallowed or reclassified as
  transient convergence;
- exhaustion returns control to the caller, which retains its existing fail-closed semantic
  code such as `CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE` or
  `CLOUDFLARE_PRODUCTION_SECRET_VERIFY_FAILED`.

The same read-only convergence law now protects custody-token presence/absence, persistent
bootstrap-origin presence, first-time staging runtime-secret presence and first-time
production runtime-secret presence.

No OIDC, TLS, exact-SHA, broker, product-auth, public-user or Real-money boundary is widened.
No secret value, provider response body, provider identifier or credential is logged.

## Permanent regression guards

Deterministic tests now require:

- delayed state visibility can converge within the bounded read-only window;
- successful convergence does not repeat PUT/DELETE mutation;
- token cleanup exhaustion retains `CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE`;
- production secret convergence exhaustion retains
  `CLOUDFLARE_PRODUCTION_SECRET_VERIFY_FAILED`;
- staging and production runtime-secret writes each occur exactly once while state reads may
  repeat;
- malformed/duplicate staging secret state fails immediately and is not retried;
- provider/read exceptions propagate immediately rather than becoming successful
  convergence;
- the machine release contract freezes the shared attempt/delay bounds, read-only rule and
  prohibition on mutation replay.

## Why earlier preflight missed it

PR #455 correctly discovered that Worker secrets are version/deployment-coupled and moved
the ephemeral custody token before the exact Build. Its deterministic secret double still
made PUT/DELETE instantly visible to every following GET, which modeled logical state but
not control-plane convergence. PR #452 then corrected the accepted Worker secret write HTTP
status set without changing that synchronous visibility assumption.

The gap therefore survived source-level lifecycle tests even though the higher-level
version ordering was correct. Future provider-control-plane doubles must distinguish
"mutation accepted" from "new state already visible to a subsequent read" whenever the
provider operation is deployment/version coupled.

## Future prevention rule

For external control planes, a successful mutation response proves only the contract of that
mutation endpoint. Do not infer immediate read-after-write/read-after-delete visibility
unless current first-party documentation explicitly guarantees it or an accepted runtime
contract proves it. When later steps require the new state, use bounded read-only
convergence; never blindly replay a mutation to manufacture convergence.

## First-party provider references reviewed

- Cloudflare Workers — Secrets:
  `https://developers.cloudflare.com/workers/configuration/secrets/`
- Cloudflare Workers — Versions & deployments:
  `https://developers.cloudflare.com/workers/versions-and-deployments/`
- Cloudflare Wrangler — Workers / secret commands:
  `https://developers.cloudflare.com/workers/wrangler/commands/workers/`
- Cloudflare Workers changelog — newer versions/deployments API model:
  `https://developers.cloudflare.com/changelog/post/2025-09-03-new-workers-api/`

## Acceptance rule

Source/tests alone do not make the CF-D defect accepted. The focused correction requires the
normal exact-head DRAFT SUCCESS-only cycle, independent review, unchanged-head READY fresh
SUCCESS-only cycle, zero blocking threads, squash merge, exact-new-main Regression Shield
and owning post-merge success, followed by a fresh exact-main
`V10 Cloudflare Production Release`.

That release must pass the formerly failing token-cleanup convergence boundary and either
continue through production bootstrap/promotion or expose a different bounded
source-controlled failure class. Blind rerun of run `34245003070` is not acceptance
evidence.
