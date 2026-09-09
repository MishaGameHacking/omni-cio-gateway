# V10 Engineering Failure Learning Ledger — FL106

Date: 2026-09-09  
Scope: CF-D exact-main production database bootstrap composition  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + Amendment 16 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Symptom / failing gate

PR #470 was squash-merged as protected `main`
`c7e8cd138217c37f7f93d0778b1ba24234db281a` after complete exact-head DRAFT and READY certification.

Automatic exact-main `V10 Cloudflare Production Release` run `34338404802`, job
`102423137819`, passed the exact-main post-merge gate, Cloudflare authority checks,
immutable staging Build, exact-SHA release proof, bootstrap-origin custody, post-custody
staging acceptance, domain configuration validation and production Worker-anchor reuse.

The release then stopped fail-closed while creating the production database runtime secret:

`CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=STOPPED code=CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`

Production database-secret write, production Build/promotion, Custom Domain mutation and
canonical live production acceptance did not run. Staging trigger/workspace cleanup
succeeded.

Owning defect: #472.

## Root cause class

`CF_D_SERVER_TO_SERVER_BOOTSTRAP_REAL_COMPOSITION_MISMATCH`

The source-level CF-D database bootstrap route was correct in isolation but its deployed
FastAPI composition had two independent blockers that the isolated route tests did not
exercise.

### Browser mutation authority mismatch

The GitHub Actions release runner sends an authenticated server-to-server
`POST /api/internal/v10/cf-d/production-database-bootstrap` with the exact accepted source
SHA and a GitHub OIDC Bearer token. It intentionally has no browser Origin, Fetch Metadata,
product session cookie or CSRF cookie/header because those are browser/product-session
authority, not release-engineering authority.

The real Cloudflare Container application installs that route on the app returned by
`create_hosted_preview_app()`. `HostedPreviewSecurityMiddlewareV1` runs before route
dispatch and previously applied the ordinary browser unsafe-request policy to every POST.
It therefore required same-origin browser metadata and CSRF material before the CF-D route
could validate exact SHA + GitHub OIDC.

The runner correctly refused to classify the unrelated browser-middleware `ORIGIN_REQUIRED`
shape as an endpoint-owned bootstrap failure and collapsed the untrusted response to the
sanitized generic `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED` boundary.

### Route priority mismatch

The hosted app also installs a generic fail-closed `/api/{path:path}` catch-all before the
CF-D route is added by the Cloudflare runtime composition. FastAPI/Starlette route dispatch
is order-sensitive: a path-converter catch-all registered first can match the internal
bootstrap path before a later exact route. Therefore merely bypassing browser CSRF/Origin
would still leave the bootstrap endpoint unreachable through the real composed app.

The repair makes the internal exact route priority explicit before the generic API catch-all.

## Blast radius and adjacent review

The review covered:

- `apps/api/cloudflare_runtime.py` real application composition;
- `apps/api/hosted_preview.py` transport, admission, session, Origin, Fetch Metadata and CSRF middleware;
- `apps/api/cf_d_database_bootstrap.py` exact-SHA/OIDC route and provider egress;
- the GitHub Actions runner bootstrap request and endpoint-specific failure classifier;
- the Cloudflare Container Worker proxy and trusted internal edge restoration;
- the Cloudflare Container outbound handler / Neon bootstrap egress boundary;
- the Neon Function OIDC/database bootstrap failure taxonomy;
- generic hosted API catch-all ordering;
- ordinary browser mutation routes and provider-start exceptions.

No analogous server-to-server release endpoint was found that legitimately requires the
same browser-mutation exemption. The correction is therefore exact method + exact path only.

Current Cloudflare Containers documentation continues to support the accepted egress model:
outbound handlers run in Workers-side trusted code, can inject authorization without
exposing it to the container and may be restricted by host. The provider egress boundary is
not changed by this repair.

## Corrective change

The correction:

- exposes one canonical `CF_D_DATABASE_BOOTSTRAP_PATH` constant while retaining the legacy
  private alias for existing source-level tests;
- registers the staging-only CF-D POST route ahead of generic API catch-all routing;
- exempts only exact `POST` to that exact CF-D bootstrap path from browser
  Origin/Fetch-Metadata/CSRF mutation checks;
- retains hosted global admission/abuse controls before that exemption;
- retains Cloudflare edge/Host/TLS restoration and TrustedHost processing;
- retains route-level exact-source-SHA validation;
- retains GitHub OIDC Bearer requirement and downstream OIDC claim/signature validation;
- retains strict provider egress allowlisting, bounded response handling and sanitized
  endpoint-specific failure classification;
- does not create a browser login/session bypass and does not accept a cookie as
  release-engineering authority.

Ordinary product/browser unsafe requests still require their existing Origin, Fetch Metadata
and CSRF controls. Near-miss paths and wrong methods do not receive the exemption.

## Permanent regression guards

Deterministic full-composition tests now require that:

- the exact bootstrap route is ordered before `/api/{path:path}` in the composed hosted app;
- an exact POST without browser Origin/CSRF reaches the CF-D route and fails at the route's
  GitHub OIDC guard with `CLOUDFLARE_CF_D_OIDC_REQUIRED` rather than being rejected as a
  browser mutation;
- an exact-path near miss without Origin remains `ORIGIN_REQUIRED`;
- a wrong unsafe method on the exact path remains `ORIGIN_REQUIRED`;
- the release acceptance contract freezes exact route, exact POST-only exemption,
  route-priority, exact-SHA and GitHub-OIDC requirements.

## Why earlier preflight missed it

Earlier tests installed `install_cf_d_database_bootstrap_route()` on a plain `FastAPI()`
instance and validated its request/response, OIDC forwarding, response bounds and failure
classification in isolation. Those tests never composed the route through
`create_hosted_preview_app()` and therefore did not include either the browser security
middleware or the already-registered generic API catch-all.

Source-level assertions proved that the route existed, but route presence is not equivalent
to deployed reachability. The preflight model stopped at component correctness rather than
exercising the actual producer -> middleware -> router -> endpoint composition used by the
Cloudflare Container runtime.

## Future prevention rule

Any internal engineering/server-to-server endpoint added to an existing browser Web/API app
must be tested through the same middleware stack and route table used in the deployed runtime.
Do not infer reachability from route presence or isolated endpoint tests.

For every non-browser authority path, explicitly prove all three layers:

1. transport/admission middleware permits the intended machine request without weakening
   ordinary browser security;
2. exact route priority prevents generic fallback/catch-all shadowing;
3. endpoint-specific cryptographic/identity authority still rejects unauthenticated callers
   fail-closed.

Browser CSRF/Origin authority and engineering OIDC authority must remain separate rather than
manufacturing synthetic browser credentials for machine-to-machine release operations.
