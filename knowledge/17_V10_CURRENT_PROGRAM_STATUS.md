# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-21

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A CURRENT / PHASE 1 ACCEPTED / PHASE 2 ACCEPTED / PHASE 3 ACCEPTED / PHASE 4 AUTHORIZED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the only authorized current functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

## Latest accepted engineering baseline

### WP22A Phase 3 — accepted

The five focused Phase-3 hosted-runtime source increments are accepted:

1. PR #341 — dormant Cloud.ru Evolution IaC boundary — exact main `9043e1c4c3d448ca570ec04cdf729dc05d7bb441`;
2. PR #343 — hosted runtime and tenant READ-secret custody contract — exact main `5c17fa329acc294c52db9d09169e0fe63b815733`;
3. PR #345 — hosted PostgreSQL least-privilege runtime-user, effective-ACL and FORCE-RLS boundary — exact main `9ba45a6040365599bcfdebbbec90938e1deaa5e5`;
4. PR #347 — tenant-preserving hosted recovery integrity boundary — exact main `912e3eee44f73d15d9a81186515957c1f3d6cbb8`;
5. PR #350 — hosted edge trust, readiness, observability, capacity/cost and release/rollback boundary — exact main `b4d1098d518613f6c10dfa74397a512c804b2928`.

The final Phase-3 implementation main completed mandatory post-merge Regression Shield #1514 / run `32435410881` with both required jobs `success`.

PR #352 consolidated the accepted Phase-3 evidence and was squash-merged to exact main:

`fbd50b2aa5029170d9aabf178103e2e761648422`

That exact main completed Regression Shield #1515 / run `32445484371` with:

- `Quality, contracts and coverage` — **SUCCESS**;
- `Dependency, code and secret security` — **SUCCESS**.

Temporary verifier PR #353 independently confirmed the exact main/run/job evidence through read-only `actions: read` authority and was closed unmerged.

Therefore **WP22A Phase 3 is accepted** and **WP22A Phase 4 — Protected provider bootstrap/apply** is the authorized current increment.

### Phase-3 accepted boundary

Phase 3 established reviewed source/test contracts for:

- one hosted runtime/deployment/IaC model without creating a parallel product stack;
- tenant-aware PostgreSQL private state, least-privilege runtime authority, effective ACL guards and mandatory FORCE RLS on protected broker relations;
- tenant-scoped opaque broker-secret references and encrypted-custody interfaces without real secret values in source, CI, artifacts, browser storage or logs;
- atomic backup staging, size/SHA-256 integrity, corrupt-backup rejection, tenant-preserving restore, replacement-runtime recovery and rollback;
- trusted proxy, Host, HTTPS/forwarded-protocol, CORS, Origin/Referer, CSRF, private-cache and secure-cookie assumptions for later hosted activation;
- sanitized release-bound readiness evidence across application, provider, database, product-auth, external-broker and recovery domains;
- bounded request, concurrency, database-pool, backup and cost controls with no automatic paid overage;
- accepted-main release identity, health-before-traffic and last-accepted-release rollback.

Phase 3 did not create public production resources, enable public registration, activate real Telegram/VK credentials, activate T-Invest public-service functionality, enable broker write/Real execution or unlock WP23.

## Earlier accepted WP22A authority

### WP22A Phase 1 — accepted

PR #333 selected **Cloud.ru Evolution** as the managed-cloud production provider/security boundary and was accepted on exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` with Regression Shield #1505 SUCCESS.

The accepted cost order remains:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

No paid commitment was authorized by provider selection.

### WP22A Phase 2 — accepted

PR #336 accepted the verified external-identity -> internal account -> tenant -> server-side session boundary, tenant-scoped broker persistence/API authority and PostgreSQL tenant/RLS correction on exact main `00fc692710aa9eaf02ca78ea0535b51600020768`.

Regression Shield #1508 / run `32277165957`, attempt 2, completed SUCCESS with both required jobs GREEN after the first attempt was blocked by a transient OSV network timeout.

Phase 2 did not activate real external-provider credentials, public registration, public production ingress, T-Invest public connector authority, broker write or WP23.

## Current functional development authority

Current engineering authority is:

- **WP22A Phase 4 — Protected provider bootstrap/apply** is the only authorized current implementation increment;
- implementation starts from accepted exact main `fbd50b2aa5029170d9aabf178103e2e761648422` after this status transition is accepted;
- create one reviewed accepted-main privileged deployment boundary for the already connected free Render and Neon accounts;
- use repository secrets `RENDER_API_KEY` and `NEON_API_KEY` only from an accepted-main workflow, never from ordinary pull-request jobs;
- create a separate free service named `omni-cio-v10-web`; the protected V9 `omni-cio-gateway` / `app:app` service remains unchanged;
- build the existing `apps/web` React application and serve it from the existing `apps/api` / `omni_cio` product boundary;
- provision or select only a free Neon PostgreSQL 18 preview database and a free Render Web Service;
- create only synthetic/non-private preview state; no real broker credential, private portfolio/account payload or production tenant data is authorized;
- expose a generated Render HTTPS preview hostname only after migrations, readiness and rollback checks pass;
- keep public registration and real product multi-user activation disabled;
- keep the public T-Invest connector fail-closed pending broker terms/permission;
- do not create Cloud.ru production resources in this free-preview increment;
- no paid plan, card charge, automatic paid scale-up or recurring spend is authorized;
- if either provider requires payment, account verification that cannot be automated, or permissions beyond the supplied keys, stop and request OWNER action;
- do not implement WP23 Telegram Bot Foundation, AI/Cortex or broker-write/Real work early.

The OWNER explicitly authorized the zero-cost Render/Neon website deployment after connecting both API keys and requested a ready working public site. This authorization is limited to the free synthetic preview boundary above and does not authorize paid resources, real tenant-private data, real broker credentials, Cloud.ru production apply or public multi-user activation.

OWNER action required now: **NO**. Engineering may proceed autonomously through source changes, tests, CI, accepted-main workflow creation and zero-cost provider bootstrap using the supplied repository secrets. Stop only at a genuinely non-delegable provider/account/billing/legal/secret action.

## OWNER-approved final V10 product direction

### Public global Web

The approved final product target is a **public modern multi-user Omni-CIO Web service** reachable from ordinary Internet-connected modern phones/desktops through a public HTTPS hostname.

A normal USER must not require PROJECT OWNER home IP/Wi-Fi/router/LAN/home Internet, Lenovo as production origin, Tailscale/native VPN, GitHub repository access, provider membership or Windows/CI credentials.

The final public production origin remains the accepted Cloud.ru Evolution managed-cloud boundary. Render/Neon in Phase 4 are a zero-cost synthetic proof-of-product and do not replace that production decision.

### USER identity and tenant isolation

Canonical product identity remains:

`Telegram Login or VK ID -> verified external identity binding -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The PROJECT OWNER is not a special product role. Provider/GitHub/Windows/CI authority remains engineering authority and must never mint/select a product tenant.

### Sessions

Production session requirements remain:

- opaque high-entropy server-side session identifier;
- `Secure`, `HttpOnly`, appropriately scoped `SameSite` cookie;
- bounded idle and absolute lifetime;
- fixation protection and rotation;
- explicit logout and revoke-all-sessions;
- no auth/session/refresh token in browser Web Storage;
- tenant scope resolved only from authenticated server-side session state.

### Free initial launch

Initial registered-user access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

Future monetization is `DEFERRED_OPTIONAL`.

### Tenant-owned broker credentials

Canonical ownership remains:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker-account binding`

No real broker credential is authorized in the Phase-4 synthetic preview. Public T-Invest-backed production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**.

## Accepted / current WP state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1–WP4 — **COMPLETE (Block B accepted at 9%)**;
- Block C / WP5–WP10 incl. WP9A — **COMPLETE (Block C accepted at 12%)**;
- Block D / WP11–WP15 — **COMPLETE (Block D accepted at 14%)**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **COMPLETE**;
- Block E / WP18 — **COMPLETE**;
- Block E / WP19 — **COMPLETE**;
- Block E / WP20 — **COMPLETE**;
- Block E / WP21 — **COMPLETE**;
- Block E / WP22 — **COMPLETE**;
- Block E / WP22A Phase 1 — **ACCEPTED**;
- Block E / WP22A Phase 2 — **ACCEPTED**;
- Block E / WP22A Phase 3 — **ACCEPTED**;
- Block E / WP22A Phase 4 — **AUTHORIZED CURRENT INCREMENT**;
- Block E / WP22A Phase 5 — **LOCKED**;
- Block E / WP22A overall — **CURRENT / NOT YET COMPLETE**;
- Block F / WP23+ — **LOCKED**;
- public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL EXIT GATES**;
- public production Internet ingress — **OFF / LOCKED**;
- zero-cost synthetic preview HTTPS — **AUTHORIZED ONLY THROUGH ACCEPTED PHASE-4 BOUNDARY**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default during WP22A.

## Current next package — WP22A Phase 4 — Protected provider bootstrap/apply

Phase-4 purpose is to create a reproducible, fail-closed and zero-cost hosted proof-of-product using the existing GitHub, Render and Neon connections without widening product or financial authority.

Required Phase-4 outcome includes at minimum:

1. an accepted-main-only deployment workflow with explicit secret names and no PR secret exposure;
2. deterministic credential preflight that emits only PASS/FAIL classifications;
3. a separate Render service `omni-cio-v10-web` on the Free instance type;
4. a Neon PostgreSQL 18 preview project/branch in an approved European region when available under the connected account;
5. build of `apps/web` plus a hosted FastAPI entrypoint bound to `0.0.0.0:$PORT`;
6. database migrations, schema/tenant/RLS/ACL verification and a least-privilege runtime connection;
7. synthetic preview identity/data only, with public registration and broker-secret submission disabled;
8. generated HTTPS hostname, health/readiness verification and rollback to the last accepted release;
9. no mutation of the protected V9 Render service;
10. no paid resource, automatic paid overage or Cloud.ru production apply.

Phase 4 may create the synthetic preview URL. Phase 5 owns real public-hosted acceptance including normal USER login/logout/session evidence, real tenant-isolation acceptance, deployed recovery/availability evidence and any non-delegable OWNER browser confirmation.

## Canonical authority

Mandatory sources include:

- `AGENTS.md`;
- `README.md`;
- `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- active amendments 8, 9 and 10;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`;
- `docs/architecture/V10_WP22A_PHASE3_ACCEPTANCE_EVIDENCE.md`;
- the accepted Phase-4 authorization/deployment contract added by the current increment;
- accepted security/threat/recovery/WP22A architecture and runbooks.

GitHub remains engineering source of truth. Historical PRs and old OWNER-only Personal-Node assumptions do not override accepted `main` plus later active amendments. OWNER-supplied evidence may be used only for genuinely non-delegable acceptance facts and must never be synthesized.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16–WP22 COMPLETE; WP22A Phases 1–3 ACCEPTED; Phase 4 CURRENT |
| F. Telegram | 8% | NOT STARTED — planning only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **40% ACCEPTED** |

The 40% total is intentional: Block E is not credited piecemeal and WP22A overall has not passed its Exit Gate.

## Permanent safety / rollback invariants

- protected V9 deployment entrypoint remains `app:app`;
- protected V9 service and rollback remain available;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false` until the owning public-activation gate;
- no broker-write expansion by WP22A;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/Telegram/VK/provider secret values, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- Phase-4 provider secrets are consumed only from accepted-main Actions secrets and are never printed;
- no paid resource or recurring spend without a new explicit OWNER approval;
- red CI is red; skipped/queued/pending is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

After this status transition is accepted:

1. add the focused Phase-4 free-preview authorization and deployment contracts;
2. implement a hosted V10 preview entrypoint and deterministic React/Python build;
3. add accepted-main-only Render/Neon credential preflight and idempotent free-resource provisioning;
4. keep all provider mutations impossible from pull-request events;
5. merge only after exact-head DRAFT and READY checks are GREEN;
6. let the accepted-main workflow create/deploy `omni-cio-v10-web` and verify its generated HTTPS URL;
7. stop before any paid plan, real tenant-private data, real broker credential, Cloud.ru production mutation, public registration, Phase 5 acceptance or WP23 work.