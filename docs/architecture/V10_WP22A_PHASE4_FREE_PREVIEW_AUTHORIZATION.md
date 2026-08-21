# Omni-CIO V10 — WP22A Phase 4 Free Preview Authorization

Status: **AUTHORIZED ON ACCEPTANCE / ZERO-COST SYNTHETIC PREVIEW ONLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## Purpose

This contract records the narrow transition from accepted WP22A Phase 3 source work to Phase 4 protected provider bootstrap/apply for a working public proof-of-product.

The authorized preview topology is:

`ordinary browser -> generated Render HTTPS hostname -> existing V10 React/FastAPI product -> free Neon PostgreSQL 18 preview database`

It reuses the existing `apps/web`, `apps/api` and `omni_cio` implementation. It does not create a second product, Core, identity model or broker stack.

## Accepted prerequisite

Phase 3 is accepted through the merged implementation chain and exact-main evidence recorded in `V10_WP22A_PHASE3_ACCEPTANCE_EVIDENCE.md`.

PR #352 was squash-merged to exact main assembled from the following hexadecimal chunks:

`fbd50b2a` + `a5029170` + `d9aabf17` + `8103e2e7` + `61648422`

Regression Shield #1515 / run `32445484371` completed SUCCESS on that exact main with both required jobs SUCCESS. Temporary verifier PR #353 independently confirmed the evidence through read-only Actions metadata and was closed unmerged.

## OWNER authorization

The OWNER connected repository secrets named `RENDER_API_KEY` and `NEON_API_KEY` and explicitly requested deployment of a ready working website.

The accepted meaning is deliberately narrow:

- recurring authorized cost remains `0 RUB/month` and `0 USD/month`;
- only Render Free plus Neon Free resources may be created or reused;
- no payment/card charge or automatic paid overage is allowed;
- no Cloud.ru production resource mutation is authorized by this preview;
- no real tenant-private state, broker credential or private portfolio/account payload is authorized;
- stop and request OWNER action if account verification, payment, broader permissions or any non-free resource is required.

## GitHub privilege boundary

Provider credentials may be consumed only by an explicitly reviewed workflow that is present on accepted `main`.

Required controls:

1. no provider secret access from `pull_request` events;
2. no provider secret value in source, logs, summaries or artifacts;
3. exact accepted-main SHA verification before mutation;
4. idempotent provider discovery/create/update behavior;
5. no mutation of the protected V9 Render service or `app:app` entrypoint;
6. sanitized output limited to classifications, resource IDs when non-sensitive, release SHA and public preview URL;
7. fail closed if a provider returns an unexpected workspace, project, plan, version, region or billing state.

## Preview service boundary

The only new Render service name is:

`omni-cio-v10-web`

It must:

- use branch `main`;
- use the Free instance type;
- build the existing React app in `apps/web`;
- run a hosted FastAPI entrypoint built from the existing `apps/api` and `omni_cio` boundaries;
- bind to `0.0.0.0:$PORT`;
- serve Web and API from one origin;
- expose a generated Render HTTPS hostname;
- pass health/readiness before traffic is accepted;
- retain rollback to the previous accepted release;
- leave the existing `omni-cio-gateway` service unchanged.

## Preview database boundary

The preview database must be PostgreSQL 18 on Neon Free, with a European/Frankfurt region preferred when available to the connected account.

Neon roles created through the Console, CLI or control-plane API inherit membership in `neon_superuser`, whose authority includes `BYPASSRLS`. Such a role is forbidden for the Omni-CIO runtime. The deployment boundary must use a separately injected privileged bootstrap connection only for migrations and idempotent SQL creation of `omni_cio_hosted_api` with exact `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS` attributes and no role memberships. The bootstrap connection is never supplied to the Render runtime. The runtime password is generated inside the accepted-main workflow, masked before use, passed directly to Render as a secret environment value and never written to source, logs, summaries or artifacts.

Required controls:

- TLS connection only;
- pooled runtime connection;
- migration/bootstrap authority separated from runtime authority;
- runtime role created with SQL only, never through Neon Console/CLI/API;
- no `neon_superuser`, predefined broad role or `BYPASSRLS` membership;
- exact login/non-superuser/non-CREATEDB/non-CREATEROLE/non-replication/non-BYPASSRLS attributes;
- least-privilege runtime role;
- exact migration/schema verification;
- tenant context, RLS and FORCE-RLS verification;
- no database secret in GitHub source, logs or artifacts;
- no public browser readback of the connection string.

## Product boundary

The Phase-4 preview is public as a URL but synthetic as a product environment.

It must keep:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- public registration disabled;
- real Telegram/VK credentials absent;
- public T-Invest connector disabled;
- real broker credential submission disabled;
- broker write disabled;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- billing/trial/subscription/premium gating disabled;
- WP23 locked.

A synthetic demo identity or fixture must never select, create or impersonate a production tenant. Any demo state is disposable and must contain no real private data.

## Phase-4 acceptance evidence

Phase 4 is accepted only after the reviewed accepted-main workflow proves:

- Render and Neon credential preflight PASS without value disclosure;
- expected free plans and PostgreSQL 18;
- successful React/Python build;
- successful database migrations and structural isolation checks;
- exact runtime-role attributes and absence of membership/BYPASSRLS authority;
- exact release SHA deployed;
- generated HTTPS URL responds successfully;
- public readiness is GREEN;
- unsafe/private responses remain `no-store`;
- protected V9 service remains unchanged;
- rollback is available;
- no paid resource or real private/broker data was introduced.

This evidence does not imply Phase 5 acceptance. Phase 5 still owns normal USER login/logout/session acceptance, deployed tenant-isolation acceptance, real recovery/availability evidence and any genuinely non-delegable OWNER browser confirmation.

## Stop conditions

Stop without fallback or paid substitution when any of the following occurs:

- provider key is invalid or insufficient;
- payment method, card charge or paid plan is required;
- free capacity is unavailable;
- account verification requires OWNER interaction;
- protected V9 mutation would be required;
- real tenant-private or broker data would be required;
- Cloud.ru production mutation would be required;
- exact-main, migration, tenant-isolation, readiness or rollback evidence is not GREEN.
