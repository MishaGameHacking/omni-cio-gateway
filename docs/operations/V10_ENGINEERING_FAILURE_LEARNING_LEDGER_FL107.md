# V10 Engineering Failure Learning Ledger — FL107

Date: 2026-09-09  
Scope: CF-D Container rollout / serving-image exact-source provenance  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + Amendment 16 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor

PR #473 was squash-merged as protected `main`
`ab784e6acd7bc1d5b248a230eb78b258ba82f7a1`. Exact-main Regression Shield run
`34352530532` completed successfully.

Fresh exact-main `V10 Cloudflare Production Release` run `34353196063` then passed the
post-merge gate, Cloudflare provider and Workers Builds authority, pinned delivery toolchain,
Containers registry authority, exact-SHA staging Build, bootstrap-origin custody, staging
`/api/v10/release` and `/healthz` acceptance, canonical domain validation and production
Worker-anchor reuse. The production runtime secret was absent, so the one-time production
database bootstrap was required.

That bootstrap again stopped fail-closed at:

`CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`

Production promotion, Custom Domain mutation and canonical live production acceptance were
not attempted. Read-only Neon function telemetry for the failure window contained no
bootstrap Function invocation, localizing the failure before the source-controlled Neon
Function.

Owning predecessor defect: #472.

## Root cause class

`CF_D_CONTAINER_ROLLOUT_IMAGE_PROVENANCE_NOT_PROVEN_BEFORE_BOOTSTRAP`

The accepted staging gate proved the active Worker source SHA and proved that `/healthz`
returned database READY through a Container. It did not prove that the Container instance
serving the next request was built from the same exact source SHA as the active Worker.

Cloudflare's current first-party Containers rollout documentation explicitly states that a
`wrangler deploy` activates the Worker before the Container image rollout is complete and
that the deploy command can return successfully after the rollout has started while existing
instances still run the previous image. During that mixed window, the new Worker can route
requests to old-image Container instances.

Therefore `Worker exact SHA + Container health READY` is not a sufficient provenance proof
for a release-authority POST whose implementation exists only in the new Container image.
The previous gate could accept the new Worker while the bootstrap request was still served by
an older healthy Container image. That failure shape is consistent with the observed generic
route-external staging failure and the absence of a Neon Function invocation.

This is a source/provenance race, not permission to retry unknown bootstrap errors and not
evidence that OIDC, Neon, browser security or broker authority should be weakened.

## Blast radius and adjacent review

The same missing proof affects every place that interprets a successful Cloudflare deploy as
proof that the exact Container image is serving:

- staging candidate acceptance before production database bootstrap;
- the production live-acceptance gate after production promotion;
- any release-authority route that exists in the Container image but not in a previous image;
- future exact-SHA statements derived only from Worker release metadata plus generic health.

The fix deliberately does not change:

- GitHub exact-main rank-1 authority;
- Cloudflare Worker-to-Container routing and edge-header restoration;
- GitHub OIDC validation;
- Neon bootstrap Function or database authority;
- browser Origin/Fetch-Metadata/CSRF semantics for ordinary mutations;
- product authentication or tenant/RLS authority;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker-write / Real-money authority;
- protected V9 `app:app` recovery baseline.

## Corrective change

The correction adds immutable Container image provenance without introducing another provider
control plane or mutation loop:

1. the existing exact-source build-info step writes the exact build SHA to both the Worker
   generated source module and a generated Container source file;
2. `.gitignore` excludes the generated Container source file from source control while
   `.dockerignore` deliberately does not exclude it from the image build context;
3. `Dockerfile.cloudflare` fails the image build if that generated file is absent or empty;
4. Cloudflare runtime startup reads the baked file and fails closed unless it is an exact
   40-hex SHA equal to `OMNI_V10_RELEASE_SHA` supplied by the active Worker;
5. the Container exposes one exact internal API route returning only the already-public exact
   source SHA as `image_source_sha`;
6. the existing HTTPS live probe now checks Worker release identity, exact serving Container
   image identity, and database health in that order;
7. existing bounded staging and production live-probe retry loops become read-only rollout
   convergence. No deployment, secret mutation, bootstrap POST or other mutation is repeated
   merely to force convergence.

The Container source route is inserted ahead of the generic API catch-all so its reachability
cannot regress through Starlette route ordering. It carries no secret, provider identifier,
account identifier, database payload or private portfolio data.

## Permanent regression guards

Deterministic tests and repository guards require:

- exact baked source files are generated for Worker and Container from one source SHA;
- missing or malformed baked Container source identity fails closed;
- runtime Worker SHA and baked image SHA must match exactly;
- the exact Container source route precedes the generic API catch-all;
- live acceptance rejects stale/mismatched image SHA;
- the Docker image build requires the generated source file;
- `.dockerignore` may not discard the generated source file;
- runtime compatibility freezes the baked-source and exact live-probe invariants;
- CF-C/CF-D release acceptance freezes exact Container-image source proof before production
  bootstrap and during production live acceptance;
- stale Container image source is never counted as success.

## Why earlier preflight missed it

Earlier deterministic doubles treated Worker deployment and Container image activation as one
logical deployment boundary. The staging live probe exercised a real Container but asserted
only application/database readiness and a release SHA produced by the Worker/runtime
composition. It did not carry immutable image provenance independent of the Worker.

That model was stricter than a Worker-only deployment but still weaker than Cloudflare's real
rollout semantics. A healthy previous image can satisfy generic health while lacking a new
release-authority route. Exact-source release proofs must therefore identify the serving image,
not merely the Worker that selected the Container binding.

## Future prevention rule

When a provider deploys a control plane and a data/runtime plane asynchronously, provider
command success is not proof that every serving runtime has converged. If an exact-source
statement depends on both planes, bake immutable provenance into the runtime artifact and
verify that provenance through the serving path before any dependent irreversible or
authority-bearing action.

Use bounded read-only convergence for rollout proof. Do not replay release, secret, database
or bootstrap mutations merely because an old runtime can still serve during a documented
provider rollout window.

## First-party provider references reviewed

- Cloudflare Containers — Rollouts:
  `https://developers.cloudflare.com/containers/configuration/rollouts/`
- Cloudflare Containers — Deploy a Container:
  `https://developers.cloudflare.com/containers/guides/deploy/`
- Cloudflare Wrangler — Containers commands:
  `https://developers.cloudflare.com/workers/wrangler/commands/containers/`
- Cloudflare Containers — Image management:
  `https://developers.cloudflare.com/containers/guides/image-management/`

## Acceptance rule

Source/tests alone do not make this defect accepted. The focused correction requires normal
exact-head DRAFT review, deterministic SUCCESS-only applicable CI, independent review,
unchanged-head READY verification, zero unresolved blocking threads, squash merge, exact-new-
main Regression Shield and owning post-merge gates.

A fresh exact-main `V10 Cloudflare Production Release` must then prove the exact staging
Container image before production database bootstrap and complete the full production
bootstrap/promotion/domain/live-acceptance chain, or expose a different bounded
source-controlled defect. The failed run `34353196063` is evidence of the precursor, not
acceptance evidence for this correction.
