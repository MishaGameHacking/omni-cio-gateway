# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-18

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A CURRENT / PHASE 1 ACCEPTED / PHASE 2 AUTHORIZED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the only authorized current functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

## Latest accepted engineering baseline

### WP22A Phase 1 — accepted

WP22A Phase 1 service/hosting architecture decision PR #333 (`WP22A: adopt staged free-first hosting architecture`) was squash-merged to exact `main`:

`51dbe41ad1e63ddb4c0b101f573b70254a5255b8`

Its final PR head was:

`595c7fb2924de71812d8f28b70230fca8089632f`

Before merge, the exact PR head completed the required DRAFT and fresh READY verification cycles with all applicable checks `success`, including the focused WP22A audit, authoritative Self-Hosted Windows CI, Engineering Governance, Fast PR Checks, Toolchain Compatibility and inherited Web regression gates. Final review had zero unresolved blocking threads.

Required post-merge evidence for exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` is complete. On 2026-08-18 the PROJECT OWNER supplied direct GitHub Actions evidence showing **Regression Shield #1505 — SUCCESS** on branch `main` / commit `51dbe41`. Both required jobs completed SUCCESS:

- `Dependency, code and secret security`;
- `Quality, contracts and coverage`.

This is genuine OWNER-supplied post-merge evidence; it is not synthesized CI evidence.

Therefore **WP22A Phase 1 is accepted**, and Phase 2 may begin from exact accepted `main` `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`.

### Accepted Phase-1 architecture decision

Production managed-cloud provider/security boundary: **Cloud.ru Evolution**.

This selection is source architecture authority, not purchase/apply authority. The current recurring infrastructure authorization remains **0 RUB/month OWNER out-of-pocket**.

Binding cost order remains:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

Accepted staged model:

1. **Stage 0 — 0 RUB proof-of-product**: use already-owned GitHub/Lenovo engineering capability; any public preview is synthetic/non-private only and Lenovo is not public production.
2. **Stage 1 — 0 RUB free/bonus hosted pilot**: eligible safe Cloud.ru free/bonus resources only after a fail-closed spend boundary; no real tenant-private/broker-secret state by implication.
3. **Stage 2 — minimum safe paid Cloud.ru pilot**: only when real-user production cannot safely be proven in Stages 0/1; exact SKU/cost revalidated immediately before apply and requires explicit OWNER recurring-cost approval.
4. **Stage 3 — HA scale-up**: only from measured load/SLA/failure-budget need; the previous ~24.5k RUB/month HA reference is not an authorized startup purchase.

No provider resource, provider credential, production DNS/public ingress or paid commitment was created by Phase 1.

## Earlier accepted planning authority

OWNER-approved public/free/hosted planning correction PR #329 was squash-merged to exact `main`:

`5f535c0ced9514866bd3680042f3ba0bb012f866`

Required post-merge evidence for that exact main completed successfully: **Regression Shield #1503 / run `32129304332` — SUCCESS**, with both required jobs GREEN.

PR #329 remains the accepted planning/governance authority for the public/free/multi-user hosted target. PR #333 is the accepted Phase-1 implementation decision under that authority.

CI-resilience maintenance PR #328 remains accepted engineering history at exact main `10c1c0368c6415c70279e8de71ee0792e371dd3a` with post-merge Regression Shield #1502 SUCCESS.

PR #327 (`Plan: separate Omni-CIO USER identity from PROJECT OWNER authority`) was closed unmerged/superseded. Its valid USER-vs-PROJECT-OWNER intent is carried forward by accepted PR #329 and the active amendments; PR #327 itself is historical only.

## Current functional development authority

Current engineering authority is now:

- **WP22A Phase 2 — Product-auth / tenant-security correction** is the next authorized implementation increment;
- implementation starts from accepted `main` `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` on a fresh focused branch;
- remove OWNER edge-identity assumptions from the product-session path while preserving reusable Host/Origin/CSRF/session/rate-limit controls;
- prove that product USER/tenant scope comes only from reviewed product authentication plus server-side session state;
- generalize only the necessary OWNER-only persistence/session/broker-connection boundaries required by the accepted multi-user model;
- preserve database-enforced tenant isolation and add cross-tenant negative evidence rather than relying on UI convention;
- do not implement WP23 Telegram Bot Foundation early; Telegram Login integration inside WP22A product authentication is distinct from WP23 bot functionality;
- no provider apply, paid purchase, real public registration, broker-write expansion or WP23 work is authorized by this transition;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the safe default.

OWNER action required now: **NO**. Engineering may proceed autonomously until a genuinely non-delegable provider account/secret/admin/budget/legal/physical action is reached.

## OWNER-approved final V10 product direction

### Public global Web

The approved final product target is a **public modern multi-user Omni-CIO Web service** reachable from ordinary Internet-connected modern phones/desktops through a public HTTPS hostname.

A normal USER must not require PROJECT OWNER home IP/Wi-Fi/router/LAN/home Internet, Lenovo as production origin, Tailscale/native VPN, GitHub repository access, provider membership or Windows/CI credentials.

The final public production origin must be an approved managed-cloud runtime. Phase 1 selected **Cloud.ru Evolution** as that production boundary. Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback infrastructure, not the public availability anchor.

### USER identity and tenant isolation

Canonical product identity:

`Telegram Login or VK ID -> verified external identity binding -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The PROJECT OWNER is not a special product role. When using Omni-CIO, the PROJECT OWNER is an ordinary USER on the same account/tenant/session path as supported users.

Cloudflare/GitHub/cloud-provider/Windows/CI authority remains engineering authority and must never mint/select a product tenant.

Before public activation, API plus database-enforced tenant isolation and cross-tenant negative tests must cover private records, broker connections, jobs, queues, caches, notifications, exports, backups/recovery and later AI/RAG memory.

### Sessions

Production session requirements remain:

- opaque high-entropy session identifier;
- server-side revocable session state;
- `Secure`, `HttpOnly`, appropriately scoped `SameSite` cookie;
- bounded idle and absolute lifetime;
- fixation protection and rotation;
- explicit logout and revoke-all-sessions;
- no auth/session/refresh token in browser Web Storage;
- stale/expired/revoked/stolen-session negatives;
- tenant scope resolved only from the authenticated server-side session.

### Free initial launch

Initial registered-user access is free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no payment method required for registration/login;
- no trial/subscription expiry required for initial ordinary product use.

Future monetization is `DEFERRED_OPTIONAL` and requires a later explicit OWNER-approved amendment plus applicable legal/payment implementation.

### Tenant-owned broker credentials

Canonical ownership:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker-account binding`

A credential submitted by USER A belongs only to Tenant A and must never be usable by Tenant B.

Raw credentials are entered/replaced/revoked only through authenticated USER Web settings over reviewed HTTPS; they are never returned to the browser, never stored in browser Web Storage, never committed/logged/artifacted in GitHub/CI, and require an approved encrypted tenant-scoped cloud secret/data boundary before real hosted use.

Optional TRADE authority remains separately gated. Execution eligibility remains the same-tenant intersection:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

No current WP22A work enables Real execution.

## T-Invest public connector gate

Current accepted planning authority records that ordinary T-Invest client API access does not authorize a public retransmission service.

Therefore:

- public Omni-CIO Web/account/tenant development is separate from T-Invest public connector activation;
- a user-supplied token does not waive broker terms;
- T-Invest-backed public production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION** until contractually valid permission/partner authority or another explicitly accepted compliant architecture exists;
- no UI/status may claim this gate passed before evidence exists.

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
- Block E / WP22A Phase 2 — **AUTHORIZED CURRENT INCREMENT**;
- Block E / WP22A overall — **CURRENT / NOT YET COMPLETE**;
- Block F / WP23+ — **LOCKED**;
- public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL EXIT GATES**;
- public Internet production ingress — **OFF / LOCKED**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default during WP22A.

## Current next package — WP22A Phase 2 — Product-auth / tenant-security correction

Phase-2 purpose is to replace historical OWNER/home-specific product authentication assumptions with the accepted public USER model while reusing existing V10 components and security controls.

Required Phase-2 outcome:

- preserve the one existing `apps/web`, `apps/api` and deterministic `omni_cio` Core;
- product identity path is Telegram/VK -> verified external identity -> internal Omni-CIO account -> tenant -> server-side session;
- Cloudflare/provider engineering identity cannot create or select a product session/tenant;
- internal account linking does not auto-merge by display name, username, phone, email or avatar;
- server-side session scope is the only authority for `user_id` / `tenant_id` in product APIs;
- direct client-supplied tenant/user selectors do not grant access;
- session rotation/logout/revoke/expiry properties remain enforced;
- persistence no longer relies on OWNER-only constraints where those constraints conflict with the accepted multi-user target;
- tenant/user and broker-connection relationships retain explicit foreign-key/scope protection;
- cross-tenant IDOR/reference/session negative tests fail closed;
- no real Telegram/VK/provider secrets in source/CI/artifacts;
- public registration/production activation stays disabled while later WP22A phases remain incomplete.

Phase 2 does **not** require provider apply or a real public site deployment. Hosted runtime/data/secret/recovery implementation is Phase 3; protected provider apply is Phase 4; real public-hosted acceptance is Phase 5.

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
- `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`;
- accepted security/threat/recovery/WP22A architecture and runbooks.

GitHub remains engineering source of truth. Historical PRs, old OWNER-only Personal-Node contracts and old screenshots do not override accepted `main` plus later active amendments. OWNER-supplied evidence may be used only for genuinely non-delegable acceptance facts and must never be synthesized.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16–WP22 COMPLETE; WP22A Phase 1 ACCEPTED; Phase 2 CURRENT |
| F. Telegram | 8% | NOT STARTED — planning only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **40% ACCEPTED** |

The 40% total is intentional: Block E is not credited piecemeal and WP22A overall has not passed its Exit Gate.

## Accepted implementation evidence summary

Key accepted anchors remain available in merged PR/Git history. Current high-level chain:

- WP0–WP15 — accepted through the existing V10 evidence chain;
- Identity/Multi-Tenant planning amendment PR #278 — accepted;
- WP16 PR #280 — accepted;
- WP17 PR #282 — accepted;
- WP18 PR #303 + Regression Shield #1486 — SUCCESS;
- WP19 PR #308 + Regression Shield #1488 — SUCCESS;
- WP20 PR #310 + Regression Shield #1490 — SUCCESS;
- WP21 PR #312 + Regression Shield #1492 — SUCCESS;
- WP22 PR #314 + Regression Shield #1494 — SUCCESS;
- WP22A historical OWNER/clientless Phase-A PR #321 — accepted historical/dormant evidence only where superseded by later public-hosted authority;
- Engineering Quality governance PR #322 + Regression Shield #1498 — accepted;
- CI-resilience PR #328 + Regression Shield #1502 — accepted;
- public/free/hosted planning PR #329 + Regression Shield #1503 / run `32129304332` — accepted;
- WP22A Phase 1 PR #333 -> exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` + OWNER-confirmed Regression Shield **#1505 SUCCESS**, both required jobs SUCCESS — **accepted**.

Hosted jobs that did not execute because of external capacity/billing conditions are never counted as clean-room PASS.

## Permanent safety / rollback invariants

- protected V9 deployment entrypoint remains `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion by WP22A;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/Telegram/VK/provider secrets, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped/queued/pending is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Begin **WP22A Phase 2 — Product-auth / tenant-security correction** from exact accepted `main` `51dbe41ad1e63ddb4c0b101f573b70254a5255b8`.

First implementation scope is intentionally narrow:

1. map and remove the historical OWNER edge-identity -> OWNER session coupling from the product-auth path;
2. introduce/reuse the internal verified external-identity -> Omni-CIO account -> tenant binding boundary without implementing WP23 bot functionality;
3. generalize the necessary OWNER-only Web session/broker-connection persistence constraints while preserving scope FKs and fail-closed behavior;
4. add deterministic session/tenant/cross-tenant negative tests;
5. keep provider secrets/dormant external auth credentials out of source and keep `PUBLIC_MULTI_USER_ENABLED=false`;
6. run cheap focused preflight before the full exact-head CI cycle.

Do not start hosted provider apply, real public registration, WP23 Telegram Bot Foundation, AI/Cortex or broker-write work during this increment.
