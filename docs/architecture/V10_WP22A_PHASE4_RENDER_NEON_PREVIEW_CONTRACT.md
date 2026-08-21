# WP22A Phase 4A — Render + Neon zero-cost preview contract

Status: **CURRENT FOCUSED IMPLEMENTATION BOUNDARY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## Decision

The OWNER has explicitly requested that the V10 site be published and has supplied
repository-scoped Render and Neon API secrets. That instruction authorizes an
autonomous **zero-recurring-cost synthetic preview apply only**.

It does not authorize paid capacity, a change of the accepted production provider,
real product registration, private tenant data, real external identities, broker
credentials, broker write or Real execution.

The accepted final production provider remains **Cloud.ru Evolution**. Render and
Neon are an interim proof-of-product surface used to verify the complete Web build,
FastAPI runtime, PostgreSQL 18 migrations, HTTPS reachability and exact-release
health before the protected production-provider apply and real-user acceptance.

## Exact scope

Phase 4A may create or update only:

1. one Render free Docker Web Service named `omni-cio-v10-preview`;
2. one Neon free PostgreSQL 18 project named `omni-cio-v10-preview`;
3. provider-generated free HTTPS and database connection endpoints;
4. secret Render environment values required to connect that service to Neon;
5. synthetic, non-private preview database state.

No other provider resource is in scope. If either provider requires billing,
payment information, a paid plan or automatic paid overage, apply must stop RED.

## Product behavior

The preview is public but deliberately not a normal multi-user product launch.

- `PUBLIC_MULTI_USER_ENABLED=false`;
- registration is disabled;
- a shared synthetic server-side session is issued only for demonstration;
- all non-safe V10 Web API methods are rejected;
- no real Telegram/VK identity is accepted;
- no real broker credential can be submitted;
- no private tenant or portfolio payload may be stored;
- broker write and Real execution remain disabled;
- WP23 remains locked.

The public preview must visibly function as the accepted V10 React/FastAPI product
shell and read-only diagnostic surface, but it must not imply that public account,
broker, legal or production-availability gates have passed.

## Security boundary

The runtime must preserve:

- exact accepted-main release identity;
- PostgreSQL 18 verification and committed migrations;
- TLS connection to Neon;
- Secure, HttpOnly, SameSite=Strict session cookie;
- no session or credential in browser Web Storage;
- Host allowlisting;
- deny-by-default CORS;
- no-store private/API responses;
- HSTS, CSP, nosniff, referrer and permissions headers;
- no provider token or database DSN in source, PRs, artifacts, summaries or logs;
- no provider secrets in pull-request workflows.

## Deployment authority

Provider mutation may run only from `.github/workflows/v10-preview-deploy.yml` on
exact accepted `main`. Pull requests receive no Render or Neon secrets. The
workflow must verify source tests before provider mutation, mask provider values,
create or reuse only exact-name free resources, deploy the exact triggering SHA
and require public `/healthz` evidence for that same SHA.

A failed provider call, build, migration, deploy or health probe is RED. No check
may be weakened to force a deployment.

## Acceptance

Phase 4A preview acceptance requires all of the following:

1. implementation PR exact-head DRAFT checks SUCCESS;
2. fresh READY checks SUCCESS;
3. squash merge to `main`;
4. normal post-merge Regression Shield SUCCESS;
5. preview deploy workflow SUCCESS;
6. Render reports the exact deploy `live`;
7. public HTTPS `/healthz` returns the exact accepted-main SHA;
8. ordinary-phone browser smoke evidence shows the V10 shell loads;
9. mutation and real-credential negative checks remain fail-closed.

Only the public preview URL may then be reported as available. It remains a
synthetic preview, not final Cloud.ru production acceptance.

## Later gates remain separate

The following still require later, separately accepted boundaries:

- Cloud.ru protected production bootstrap/apply;
- public registration and Telegram/VK login;
- normal per-user account/tenant/session acceptance;
- tenant-private hosted state and real broker READ credentials;
- T-Invest public-service permission;
- broker TRADE authority and all Real-money safeguards;
- production SLO, recovery and legal acceptance;
- WP23 and subsequent work packages.
