# Omni-CIO V10 Render + Neon synthetic preview runbook

Status: **WP22A PHASE 4 IMPLEMENTATION RUNBOOK / APPLY ONLY FROM ACCEPTED `main`**  
Production provider authority remains: **Cloud.ru Evolution**

## Purpose

This runbook operates the temporary public synthetic preview for the existing Omni-CIO V10 React/FastAPI product. It is a zero-recurring-cost proof surface for Web build, PostgreSQL 18, server-side sessions, HTTPS and exact-release health. It is not the final production topology and must never contain real user, broker or portfolio data.

## Canonical implementation

Use only:

- `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- `scripts/check_v10_exact_main_regression.py`;
- `scripts/provision_v10_render_neon_preview.py`;
- `scripts/diagnose_v10_render_deploy.py`;
- `apps/api/hosted_preview.py`;
- `apps/web`.

Do not deploy through a second workflow, Dockerfile, temporary status workflow, local laptop command or GitHub-hosted Ubuntu lane. The accepted self-hosted Windows workflow is the only provider-mutation path. The Render diagnostic is read-only and runs only inside that same accepted-main secret boundary after the canonical provisioner has already failed.

## Managed resources

The workflow may manage only:

- Render Free native Python Web Service `omni-cio-v10-web` in Frankfurt;
- Neon PostgreSQL 18 project `omni-cio-v10-preview-frankfurt` in `aws-eu-central-1`;
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

Normal deployment is triggered by a successful `Regression Shield` workflow run on branch `main`. A manual dispatch is allowed only from `main` as a retry path; it never bypasses Regression Shield.

Before any provider mutation, every trigger path must use the read-only GitHub Actions API to prove that the exact target SHA has exactly one completed successful `push` run of `.github/workflows/regression-shield.yml`, and that both required jobs are completed and successful:

- `Quality, contracts and coverage`;
- `Dependency, code and secret security`.

Missing, duplicate, queued, cancelled, failed, manually triggered or SHA-mismatched Regression Shield evidence is a hard failure.

The workflow must:

- use the self-hosted Windows `omni-cio-ci` runner;
- derive the exact accepted-main SHA from the triggering event;
- fetch and detach-checkout that exact SHA;
- remove Git credential helpers after checkout;
- grant only job-scoped `actions: read` and `contents: read` permissions;
- execute `scripts/check_v10_exact_main_regression.py` before provider credentials or mutation are used;
- create an isolated Python environment;
- install only hash-locked runtime dependencies;
- compile and run the Phase 4 deployment/application tests before provider calls;
- pass secrets only to the provision step;
- capture a UTC provision-attempt boundary immediately before invoking the canonical provisioner;
- on provider failure, preserve the original non-zero result while allowing only read-only sanitized Render diagnostics for exactly one deploy from the same exact release and current provision attempt;
- require that deploy to be in an allowlisted failed terminal state for ordinary build/update/start/health diagnosis;
- allow a unique current-attempt `pipeline_minutes_exhausted` event to explain a still `created`/`queued` deploy whose build was prevented from starting;
- treat stale prior deploys/events, multiple current-attempt matches, unsupported non-failed states or malformed timestamps as unavailable diagnostics rather than inferred root cause;
- clean the isolated environment and repository workspace afterward.

A source SHA or Regression Shield evidence mismatch is a hard failure.

## Database bootstrap

The provisioner discovers or creates the exact Neon project and verifies PostgreSQL major version 18 and Frankfurt region.

Neon project regions are immutable. A legacy project named `omni-cio-v10-preview` in another region is deliberately ignored and is never updated or deleted. The region-scoped Frankfurt project is created or reused independently.

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

The Render Hobby workspace currently provides an included Starter pipeline-minute allowance. The preview must not buy extra pipeline minutes or add a payment method automatically. If Render emits `pipeline_minutes_exhausted`, classify the apply as `PIPELINE_MINUTES_EXHAUSTED`, keep it RED and stop; paid continuation requires a separate explicit OWNER decision, while a later free allowance reset may permit a normal accepted-main retry.

## Runtime behavior

An unauthenticated browser receives the normal V10 login shell with an explicit synthetic preview action. The action creates a server-side synthetic session and CSRF cookie. It does not register a real user or impersonate a production tenant.

The preview:

- disables Telegram and VK login;
- rejects real broker-connection mutations;
- exposes only synthetic or empty portfolio, research, incident, decision and system data;
- stores sessions only in PostgreSQL;
- keeps session credentials and CSRF proofs out of browser Web Storage;
- uses Secure, HttpOnly and SameSite=Strict session and CSRF cookies;
- returns the CSRF proof only through a same-origin, `no-store` response header and keeps it only in active process memory;
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

GitHub authority, provider API, plan, region, PostgreSQL version, migration, role, RLS, build, deploy, health, release or security-header failure remains RED.

For Render provider failures, the workflow may retrieve only one structured deploy for the exact accepted-main SHA created at or after the current provision-attempt UTC boundary. Ordinary deploy-failure diagnosis requires that deploy to be in an allowlisted failed terminal state and may inspect only its matching `deploy_ended` event; if that event links a failed build by provider build ID, the diagnostic may also retrieve only the matching structured `build_ended` event. The diagnostic may additionally query only the documented `pipeline_minutes_exhausted` event type with the same service and current-attempt start boundary; exactly one such current event produces `PIPELINE_MINUTES_EXHAUSTED` even if the deploy remains `created` or `queued` because the build never started. It emits only allowlisted classifications and never copies free-form provider event/log text into Actions output. A stale, ambiguous, unsupported non-failed or malformed match makes diagnostics unavailable; diagnostic failure never converts the original provider failure to success and never triggers a second provider mutation.

Safe recovery order:

1. inspect sanitized GitHub and provider status;
2. classify the failure without revealing secrets;
3. fix source on a focused branch when the cause is source/runtime/configuration;
4. complete exact-head DRAFT and fresh READY validation;
5. squash-merge the accepted fix;
6. require exact-main Regression Shield SUCCESS;
7. allow the accepted-main deployment workflow to re-verify that exact run and retry.

For `PIPELINE_MINUTES_EXHAUSTED`, do not patch application code or add a payment method automatically. Preserve the zero-cost boundary and wait for a free allowance reset or obtain an explicit OWNER-approved cost decision before any paid continuation.

Never recover by weakening exact-SHA, Regression Shield, free-plan, TLS, PostgreSQL 18, least-privilege, RLS, no-secret or no-real-data controls.

## Exit from preview

Public registration, normal Telegram/VK authentication, per-user tenant acceptance, real broker READ credentials, production recovery/SLO evidence and Cloud.ru production apply remain later gates. The Render URL is only a synthetic engineering and product demonstration endpoint.
