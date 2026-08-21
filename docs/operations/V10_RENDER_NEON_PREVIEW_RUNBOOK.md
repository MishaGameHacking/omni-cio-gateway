# Omni-CIO V10 Render + Neon synthetic preview runbook

Status: **WP22A PHASE 4 IMPLEMENTATION RUNBOOK / APPLY ONLY FROM ACCEPTED `main`**  
Production provider authority remains: **Cloud.ru Evolution**

## Purpose

This runbook operates the temporary public synthetic preview for the existing Omni-CIO V10 React/FastAPI product. It is a zero-recurring-cost proof surface for Web build, PostgreSQL 18, server-side sessions, HTTPS and exact-release health. It is not the final production topology and must never contain real user, broker or portfolio data.

## Canonical implementation

Use only:

- `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- `scripts/provision_v10_render_neon_preview.py`;
- `apps/api/hosted_preview.py`;
- `apps/web`.

Do not deploy through a second workflow, Dockerfile, temporary status workflow, local laptop command or GitHub-hosted Ubuntu lane. The accepted self-hosted Windows workflow is the only provider-mutation path.

## Managed resources

The workflow may manage only:

- Render Free native Python Web Service `omni-cio-v10-web` in Frankfurt;
- Neon PostgreSQL 18 project `omni-cio-v10-preview` in `aws-eu-central-1`;
- SQL-created least-privilege role `omni_cio_hosted_api`;
- provider-generated HTTPS and PostgreSQL endpoints;
- synthetic preview tenant, user and session state.

Recurring authorized cost is zero. Stop immediately when either provider requires a paid plan, card, paid overage, broader account permission or OWNER verification.

## Preconditions

Before provider mutation, confirm:

1. the Phase 4 authorization/status transition is accepted on `main`;
2. the implementation PR completed exact-head DRAFT and fresh READY cycles with all applicable checks SUCCESS;
3. there are no unresolved blocking review threads;
4. the implementation was squash-merged;
5. the exact-main Regression Shield completed SUCCESS;
6. repository secrets `RENDER_API_KEY` and `NEON_API_KEY` are present without exposing their values.

Never paste either key into source, pull requests, issues, chat, screenshots, summaries or artifacts.

## Trigger and source verification

Normal deployment is triggered by a successful `Regression Shield` workflow run on branch `main`. A manual dispatch is allowed only from `main`.

The workflow must:

- use the self-hosted Windows `omni-cio-ci` runner;
- derive the exact accepted-main SHA from the triggering event;
- fetch and detach-checkout that exact SHA;
- remove Git credential helpers after checkout;
- create an isolated Python environment;
- install only hash-locked runtime dependencies;
- compile and run the Phase 4 deployment/application tests before provider calls;
- pass secrets only to the provision step;
- clean the isolated environment and repository workspace afterward.

A source SHA mismatch is a hard failure.

## Database bootstrap

The provisioner discovers or creates the exact Neon project and verifies PostgreSQL major version 18 and Frankfurt region.

Using the privileged bootstrap connection only inside the workflow, it:

1. applies committed migrations;
2. creates or rotates `omni_cio_hosted_api` with `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`;
3. verifies that the runtime role has no memberships;
4. applies the committed hosted-runtime grants;
5. inserts and verifies only the synthetic preview tenant and user;
6. derives a pooled URI containing the generated runtime credential;
7. masks all bootstrap and runtime URIs and credentials.

The privileged bootstrap URI must never be stored in Render. Render receives only the pooled least-privilege runtime URI.

## Render build and start

The provisioner discovers or creates exactly one Render Free service named `omni-cio-v10-web` on branch `main` in Frankfurt.

The exact native build command installs hash-locked Python dependencies, runs `npm ci`, Web typecheck, lint and tests, and builds `apps/web/dist`.

The exact start command is:

`uvicorn apps.api.hosted_preview:create_app --factory --host 0.0.0.0 --port $PORT`

Required environment remains fail-closed:

- `OMNI_V10_HOSTED_PREVIEW=1`;
- `OMNI_V10_POSTGRES_DSN` set to the pooled runtime URI;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- billing, trial, subscription and premium gating disabled;
- `REAL_TRADING_ENABLED=false`;
- `TRADING_METHODS=false`;
- `BROKER_WRITE_ENABLED=false`.

The deployment must target the exact accepted-main SHA. Plan, region, repository, branch, build command, start command or health-path drift is RED.

## Runtime behavior

An unauthenticated browser receives the normal V10 login shell with an explicit synthetic preview action. The action creates a server-side synthetic session and CSRF cookie. It does not register a real user or impersonate a production tenant.

The preview:

- disables Telegram and VK login;
- rejects real broker-connection mutations;
- exposes only synthetic or empty portfolio, research, incident, decision and system data;
- stores sessions only in PostgreSQL;
- keeps session credentials out of browser Web Storage;
- uses Secure and SameSite=Strict cookies, with the session cookie HttpOnly;
- requires same-origin and CSRF proof for state-changing requests;
- keeps API and health responses `no-store`;
- applies Host allowlisting, HSTS, CSP, `nosniff`, referrer and opener protections.

Do not enter real broker tokens or private data into the preview.

## Health and release acceptance

After Render reports the deploy `live`, the provisioner probes the public HTTPS endpoint until a finite deadline.

`GET /healthz` must return HTTP 200 with:

- `status` equal to `ok`;
- `release_sha` equal to the exact accepted-main SHA;
- `database` equal to `READY`;
- `synthetic_preview` equal to `true`;
- `Cache-Control: no-store`;
- `Strict-Transport-Security: max-age=31536000`.

The final workflow summary may contain only the exact release SHA, public preview URL and non-sensitive provider resource IDs. Provider keys, database credentials and connection URIs are forbidden.

## Failure handling

Provider API, plan, region, PostgreSQL version, migration, role, RLS, build, deploy, health, release or security-header failure remains RED.

Safe recovery order:

1. inspect sanitized GitHub and provider status;
2. classify the failure without revealing secrets;
3. fix source on a focused branch;
4. complete exact-head DRAFT and fresh READY validation;
5. squash-merge the accepted fix;
6. require exact-main Regression Shield SUCCESS;
7. allow the accepted-main deployment workflow to retry.

Never recover by weakening exact-SHA, free-plan, TLS, PostgreSQL 18, least-privilege, RLS, no-secret or no-real-data controls.

## Exit from preview

Public registration, normal Telegram/VK authentication, per-user tenant acceptance, real broker READ credentials, production recovery/SLO evidence and Cloud.ru production apply remain later gates. The Render URL is only a synthetic engineering and product demonstration endpoint.
