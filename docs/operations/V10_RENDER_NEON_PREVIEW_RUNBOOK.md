# Omni-CIO V10 Render + Neon synthetic preview runbook

Status: **WP22A Phase 4 free preview boundary**  
Production provider authority remains: **Cloud.ru Evolution**

## Purpose

This runbook publishes the accepted V10 Web shell as a zero-cost, non-production,
synthetic, shared and read-only preview. It exists to prove that the React client,
FastAPI application, PostgreSQL 18 migrations, HTTPS service edge and external
health checks work together before real public registration or private tenant data
is allowed.

The preview is not the final public production topology and does not change the
accepted Cloud.ru production-provider decision.

## Created resources

The accepted-main deployment workflow manages only:

- one Render free Docker Web Service named `omni-cio-v10-preview` in Frankfurt;
- one Neon free PostgreSQL 18 project named `omni-cio-v10-preview` in Frankfurt;
- the provider-generated Render HTTPS hostname;
- secret environment injection from Neon to Render without writing the DSN to
  GitHub source, artifacts or visible workflow output.

No paid Render or Neon plan, paid overage, custom domain, Cloud.ru resource,
Telegram/VK credential, broker credential or recovery key is created by this
preview workflow.

## Authority and trigger

`.github/workflows/v10-preview-deploy.yml` has no `pull_request` trigger. Provider
secrets are available only on an exact `main` push or an explicit manual dispatch
from `main`.

The workflow:

1. checks that the ref is exactly `refs/heads/main`;
2. checks out the exact `GITHUB_SHA` without a third-party checkout action;
3. compiles and runs the deterministic preview contract tests;
4. authenticates to Neon and Render through masked repository secrets;
5. verifies or creates only the exact free preview resources;
6. injects the PostgreSQL URI directly into Render environment storage;
7. deploys the exact accepted-main Docker image;
8. waits for the Render deploy to become `live`;
9. verifies `/healthz` returns the same exact release SHA;
10. writes only the public URL and non-secret status to the workflow summary.

Required repository-secret names:

- `NEON_API_KEY`;
- `RENDER_API_KEY`.

Their values must never be pasted into source, issues, pull requests, chat,
artifacts or screenshots.

## Runtime behavior

`apps/api/hosted_preview.py` deliberately differs from production behavior:

- a shared synthetic session is issued automatically;
- public registration remains disabled;
- all non-safe `/api/v10/web` methods are rejected with
  `HOSTED_PREVIEW_READ_ONLY`;
- real broker credential submission is therefore impossible;
- broker write and Real execution remain disabled;
- the database contains only synthetic preview state;
- session cookies are `Secure`, `HttpOnly` and `SameSite=Strict`;
- CORS is not opened;
- private/API responses use `Cache-Control: no-store`;
- Host validation and security headers remain active.

The preview must never be used for personal portfolio data, real broker tokens,
real external identities, legal acceptance evidence or production availability
claims.

## Build

`Dockerfile.v10-preview` uses pinned build/runtime identities:

- Node.js `24.18.0`;
- npm `11.16.0`;
- Python `3.12.10`;
- hash-locked Python dependencies from `requirements.txt`.

The Node stage runs `npm ci` and `npm run build`. The Python stage copies the
resulting `apps/web/dist` and starts the hosted FastAPI factory on Render's
`$PORT`.

## Health and acceptance

A successful deployment requires:

- Render deploy status `live`;
- public HTTPS `GET /healthz` response;
- `status=ok`;
- `mode=synthetic_read_only_preview`;
- response `release` exactly equal to the accepted-main SHA that triggered the
  deployment;
- PostgreSQL `SELECT 1` success from the running application.

A cold free Render service may need additional startup time. The workflow allows
up to 20 minutes for deploy and public health confirmation but never converts a
timeout into PASS.

## Failure handling

Provider API, build, migration, deploy or public-health failure leaves the
workflow RED. Do not retry by weakening version, region, free-plan, TLS, exact-SHA
or safety checks.

Safe recovery order:

1. inspect the sanitized GitHub Actions and Render build status;
2. fix source or provider configuration on a focused branch;
3. complete the normal exact-head DRAFT and READY cycles;
4. squash-merge the accepted fix;
5. let the accepted-main workflow deploy the corrected SHA;
6. retain or restore the last Render deploy that passed exact-release health.

If either provider would require payment, the workflow must fail. No paid upgrade
is authorized by this runbook.

## Exit from preview

Real public registration, normal Telegram/VK login, tenant-private records, broker
READ credentials and production availability remain separate later acceptance
gates. The preview URL is an engineering/product demonstration endpoint only.
