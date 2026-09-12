# V10 Engineering Failure Learning Ledger — FL129

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_RUNNER_TO_NEON_FUNCTION_PROVENANCE_FRONTDOOR_403`
- Scope: exact-main Neon Function source-provenance transport only

## Observed failure

Exact accepted `main` `8ba1ab80af1147e90975c4b7f9ed6400fbd7d736` reached `V10 Cloudflare Production Release` run `34691668602` after PR #493. The release accepted the exact-main post-merge batch with 11 successful push workflows, then passed Cloudflare provider readiness, Workers Builds authority, the pinned delivery toolchain, Containers registry authority and provider control-plane dependency installation.

The exact-main staging rehearsal reused the staging database secret and Worker anchor, quarantined stale staging build activity, completed the gated exact-SHA build, proved one exact active staging version, passed the exact release probe and completed bootstrap-origin custody. It then stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID status=403`

Production database bootstrap, production Worker promotion, custom-domain mutation and live acceptance did not execute. Trigger/build cleanup completed successfully.

No Function URL, project/branch identifier, credential, OIDC token, database secret or private payload is recorded here.

## Root cause evidence

The accepted source probes exact Function provenance by sending a credential-free `GET /` directly from the GitHub runner to the Function invocation hostname. The source-controlled wrapper can return only an exact `200` source-digest proof for that request shape, while a pre-wrapper legacy deployment can return the exact accepted `405 METHOD_NOT_ALLOWED` stale classification. It does not return the observed provider-shaped 403.

A read-only provider cross-check after the failure proved that the canonical Frankfurt PostgreSQL 18 project, default branch and `cfdprodbootstrap` Function still existed and that the active/current Function deployment was completed on Node.js 24. The active deployment predates the current method-only provenance wrapper and therefore legitimately requires source convergence.

Function telemetry for the exact release-failure window contained no Function invocation entry even though historical Function invocations are present. Neon documents the deployed Function URL as a public HTTPS HTTP entrypoint and documents platform invocation log records for requests that reach the Function runtime. Taken together with the source-controlled response contract, the bounded evidence places the observed 403 before the Function handler. The exact undocumented provider front-door subtype is not inferred or fabricated.

The defect is therefore transport-specific: the GitHub runner cannot use the public Function invocation front door as the authoritative no-secret source-provenance channel in this release environment. Source equality, the Function deployment credential and the Function handler are separate concerns and must not be weakened to work around that front-door rejection.

## Permanent correction

- Preserve canonical method-only Function provenance: the provider request remains exact `GET /` with `Accept: application/json`, no authorization credential, no query discriminator and no custom provenance header.
- Route that read-only provenance request through the already accepted exact-SHA staging Worker while its existing short-lived origin-sync token is armed.
- Reuse the staging Worker's existing destination-bounded Neon authority. The Worker derives the exact Function destination from the staging PostgreSQL branch identity and Frankfurt cell; the release runner cannot select or supply a Function URL.
- Expose a separate token-bound staging control-plane custody route for provenance. It is available only for the staging runtime role, requires the exact accepted source SHA plus the ephemeral origin-sync token, and executes before generic `/api/` container proxying.
- Return only a bounded digest proof or the exact legacy-stale classification. Do not return the Function URL, provider identifiers, provider response bodies, credentials or private database material.
- Keep deterministic wrapper+handler SHA-256 equality on the release runner. A digest mismatch remains source drift; malformed/oversized/redirect/provider failures remain fail-closed.
- Keep `NEON_FUNCTION_DEPLOY_API_KEY` as the bounded project-scoped management authority used only after source drift is proven for project/branch/Function state, deployment creation, polling and final deployment identity verification.
- Keep the direct GitHub-OIDC production database bootstrap transport unchanged. This correction does not activate the legacy public staging relay for production bootstrap and does not move OIDC bootstrap authority into the new provenance route.
- Preserve TLS certificate/hostname validation, no redirects, bounded responses, exact active/current deployment identity, race detection, stale-build quarantine, rollback, domain and live-acceptance gates.

## Blast radius and adjacent review

Directly coupled surfaces reviewed and corrected:

- `cloudflare/src/cf-d-neon-function-provenance.js`;
- `cloudflare/src/cf-d-bootstrap-origin-custody.js`;
- `cloudflare/src/index.js`;
- `scripts/probe_v10_cloudflare_neon_function_provenance_via_staging.py`;
- `scripts/run_v10_cloudflare_gated_candidate.py`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py` integration boundary;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- deterministic Worker, Python transport, candidate-lifecycle and contract regressions.

The existing staging database-secret recovery, PostgreSQL schema/runtime-role/RLS logic, production database direct OIDC bootstrap, production Worker build/promotion, custom-domain attachment, rollback and live-acceptance logic are not rewritten by this defect. Run #49 did not reach those downstream production gates, so no independent defect is claimed there.

## Permanent regression / guard

Deterministic coverage requires:

- provenance Function egress to derive the exact same-branch Function destination from staging database authority rather than a request-controlled URL;
- the provider request to remain exact `GET /`, credential-free, no-redirect and bounded;
- exact source digest equality to pass, digest mismatch to report source drift, and only the exact legacy `405 METHOD_NOT_ALLOWED` contract to report legacy stale source;
- malformed content type/body/digest, provider 403, redirects and oversized responses to fail closed without provider-body reflection;
- the provenance custody route to require staging runtime role, exact source SHA and the ephemeral origin-sync token before any provider egress;
- the custody response to contain no Function URL or provider identifier;
- the release runner to bind all Function provenance probes during source convergence to the exact-SHA staging Worker while the token is armed, and restore the normal module probe afterward;
- Function management mutation to remain project-scoped and conditional on proven source drift;
- direct production database bootstrap to remain `GITHUB_OIDC_DIRECT_NEON_FUNCTION` and free of this custody route;
- exact-head CI, security, Sonar/review and exact-main post-merge certification to remain mandatory.

## Prevention law

When a provider's public invocation front door rejects a no-secret control-plane proof before source-controlled user code can run, do not weaken the proof and do not add credentials merely to force that public path. Prefer an already-trusted exact-version, destination-bounded read-only egress contour that can reach the same provider resource, keep the mutation authority separate, and return only the minimum evidence required for deterministic equality.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
