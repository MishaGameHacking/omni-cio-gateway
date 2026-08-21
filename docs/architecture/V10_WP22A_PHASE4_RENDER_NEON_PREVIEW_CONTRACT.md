# WP22A Phase 4 - Render + Neon zero-cost preview implementation contract

Status: **IMPLEMENTATION UNDER REVIEW / PROVIDER APPLY LOCKED UNTIL AUTHORIZATION IS ACCEPTED ON `main`**  
Owning package: **WP22A - External Web Access / Product Authentication Security Gate**

## Purpose

This contract binds the single supported implementation for the temporary public Omni-CIO V10 proof-of-product. It deploys the existing React client and FastAPI application to a zero-recurring-cost Render + Neon preview while the accepted final production provider remains **Cloud.ru Evolution**.

The preview proves build, PostgreSQL 18 migrations, least-privilege runtime access, HTTPS reachability, server-side sessions and exact-release health. It does not accept final production hosting, public registration, real tenant-private data, broker credentials, broker write authority, Real execution or WP23.

## Canonical source path

Exactly one deployment implementation is supported:

- deployment workflow: `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- exact-main Regression Shield verifier: `scripts/check_v10_exact_main_regression.py`;
- exact-main verification tests: `tests/test_v10_exact_main_regression.py`;
- provider provisioner: `scripts/provision_v10_render_neon_preview.py`;
- hosted application factory: `apps/api/hosted_preview.py`;
- existing Web product: `apps/web`;
- deployment contract tests: `tests/test_wp22a_phase4_deploy_contract.py`;
- hosted application tests: `tests/test_wp22a_phase4_hosted_preview_app.py`.

A second Docker-based deploy workflow, duplicate provider client, temporary self-modifying status workflow or GitHub-hosted Ubuntu acceptance lane is forbidden. The repository's current zero-budget CI boundary remains authoritative.

## Provider resources

The implementation may create or reuse only:

1. one Render **Free** native Python Web Service named `omni-cio-v10-web`, branch `main`, region Frankfurt;
2. one Neon PostgreSQL 18 project named `omni-cio-v10-preview-frankfurt`, region `aws-eu-central-1`;
3. the provider-generated HTTPS hostname and PostgreSQL endpoints;
4. a SQL-created runtime role named `omni_cio_hosted_api`;
5. synthetic preview tenant, user and session records.

No paid instance, paid database feature, automatic paid overage, custom domain, Cloud.ru resource, real identity credential, broker credential or private portfolio payload is authorized. Any payment, card, broader permission, non-free plan or account-verification requirement stops the apply.

The legacy unscoped project name `omni-cio-v10-preview` is out of scope. If it exists in another immutable region, the provisioner must preserve it without mutation or deletion and create or reuse only the Frankfurt-scoped project.

## GitHub authority and trigger

Provider mutation is allowed only after the authorization/status transition is accepted on `main`, the implementation PR is accepted, and the exact accepted-main Regression Shield succeeds.

The canonical workflow:

- runs on the existing self-hosted Windows `omni-cio-ci` runner rather than budget-blocked GitHub-hosted capacity;
- has no `pull_request` trigger;
- grants only job-scoped `actions: read` and `contents: read` permissions;
- re-verifies through the read-only GitHub Actions API, for both automatic and manual dispatch paths, that exactly one push-triggered Regression Shield run for the exact accepted-main SHA completed successfully;
- requires the exact run's `Quality, contracts and coverage` and `Dependency, code and secret security` jobs to be completed and successful before any provider mutation;
- receives `RENDER_API_KEY` and `NEON_API_KEY` only in the provider-mutation step;
- bootstraps and verifies the exact accepted-main SHA;
- runs deterministic deployment-source tests before any provider call;
- masks provider keys, generated runtime credentials and database URIs;
- writes only sanitized classifications, non-sensitive resource IDs, release SHA and the public preview URL;
- fails closed on unexpected workflow, run, job, workspace, service, project, plan, version, region, role, migration, health or billing state.

## Render runtime

The Render service uses the existing repository as a native Python service.

Build command requirements:

- install Python dependencies from hash-locked `requirements.txt`;
- install Web dependencies with `npm ci`;
- run Web typecheck, lint and tests;
- build `apps/web/dist`.

Start command:

`uvicorn apps.api.hosted_preview:create_app --factory --host 0.0.0.0 --port $PORT`

The service must remain on plan `free`, branch `main`, region `frankfurt`, health path `/healthz`, and exact reviewed build/start commands. Drift is a hard failure.

## Neon runtime boundary

The Neon project must use PostgreSQL 18 in Frankfurt. The privileged bootstrap URI may be used only inside the accepted-main workflow for migrations and role provisioning; it is never supplied to the Render runtime.

The runtime role must be created with SQL and have exactly:

- `LOGIN`;
- `NOSUPERUSER`;
- `NOCREATEDB`;
- `NOCREATEROLE`;
- `NOREPLICATION`;
- `NOBYPASSRLS`;
- no role memberships.

The application receives only the pooled runtime URI. Startup verifies PostgreSQL 18, exact runtime-role attributes, absence of memberships, required schema objects, RLS and FORCE RLS before serving traffic.

## Product behavior

The preview is public by URL but synthetic by data and authority.

- `PUBLIC_MULTI_USER_ENABLED=false`;
- public registration remains disabled;
- Telegram and VK providers remain disabled;
- the login screen offers an explicit synthetic preview action;
- that action creates a server-side synthetic session; no automatic impersonation occurs;
- session and CSRF cookies are Secure, HttpOnly and SameSite=Strict;
- the CSRF proof is returned only in a same-origin, `no-store` response header and retained only in the active JavaScript process memory;
- no session, CSRF proof, provider token or database credential is stored in browser Web Storage;
- real broker connection mutations are rejected;
- portfolio, research, incident, decision and system views expose only synthetic or empty preview data;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write, billing, trial, subscription and premium gating remain disabled.

## HTTP security and release identity

The hosted application must preserve:

- exact `RENDER_GIT_COMMIT` release identity;
- generated Render hostname allowlisting;
- HTTPS-only request enforcement behind the trusted Render edge;
- same-origin mutation checks and CSRF validation;
- deny-by-default cross-origin behavior;
- HSTS, CSP, `nosniff`, referrer and opener protections;
- `Cache-Control: no-store` for API and health responses;
- no provider or database secret in source, logs, summaries or artifacts.

`GET /healthz` must report `status=ok`, the exact accepted-main `release_sha`, `database=READY` and `synthetic_preview=true`. A mismatch, unavailable database or missing security header is RED.

## Acceptance

Phase 4 preview acceptance requires:

1. authorization/status PR accepted on `main`;
2. implementation exact-head DRAFT checks all SUCCESS;
3. fresh READY checks all SUCCESS;
4. zero unresolved blocking review threads;
5. squash merge to `main`;
6. exact-main Regression Shield SUCCESS;
7. deployment workflow re-verification of that exact Regression Shield run and both required jobs;
8. deployment workflow SUCCESS;
9. Render deploy `live` on the exact accepted-main SHA;
10. public HTTPS health and security probes SUCCESS;
11. ordinary-browser smoke evidence for the V10 shell;
12. negative checks proving real credentials and mutations remain blocked.

Only then may the public URL be described as a working synthetic preview. Phase 5 and final Cloud.ru production acceptance remain separate.
