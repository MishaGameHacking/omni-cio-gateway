# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-24

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A CURRENT / PHASE 1 ACCEPTED / PHASE 2 ACCEPTED / PHASE 3 ACCEPTED / PHASE 4 ACCEPTED / PHASE 5 AUTHORIZED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the only authorized current functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

This file is current authority only when read from accepted protected `main`. A branch/PR copy is proposed status, not accepted authority. Any transition described below becomes effective only after its own exact-head GREEN lifecycle, squash merge and required exact-main Regression Shield.

## Latest accepted WP22A engineering baseline

### Phase 4 — accepted hosted proof-of-product

WP22A Phase 4 established the accepted zero-cost synthetic hosted proof-of-product using the existing React/FastAPI product on Render Free plus Neon PostgreSQL 18 while preserving V9 and all broker/Real locks.

Canonical Phase-4 evidence remains:

- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json`;
- `.github/workflows/v10-wp22a-phase4-public-acceptance.yml`.

The accepted Phase-4 boundary is synthetic only: no normal real-user registration, no real broker credential/private portfolio/account payload, no paid resource/automatic paid overage, no protected V9 mutation, broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, WP23 locked.

The Phase-4 chain and exact historical SHAs remain preserved in the Phase-4 evidence files and merged PR history. Those historical records are evidence and do not override newer accepted Phase-5 source on `main`.

### Phase 5 provider-auth foundations — accepted

The first Phase-5 source foundations are now accepted on protected `main`:

1. PR #384 — bounded provider authorization-transaction core with server-generated state, S256 PKCE, nonce, provider binding, replay protection and deterministic concurrency/negative coverage — exact main `5343de4ae6f8e9c33f3c8d8fd85566946995eb8d`;
2. PR #385 — dormant Telegram OIDC Authorization Code + PKCE adapter with strict issuer/audience/nonce/time/JWKS verification and no product-session activation — exact main `4066a81054b4064ca847de88647989024783f7f5`; post-merge Regression Shield #1531 / run `32717629717` SUCCESS;
3. PR #386 — dormant VK ID OAuth 2.1 adapter plus typed `device_id` callback correction — exact main `bda8f51ad495520a92bd2715182684e216f76000`; post-merge Regression Shield #1532 / run `32760188417` SUCCESS with both required jobs `Quality, contracts and coverage` and `Dependency, code and secret security` terminal `success`.

PR #386's downstream Phase-4 free-preview deployment run `32763262424` independently verified exact-main Regression Shield before provider mutation, then failed only at the external zero-cost provider boundary with `RENDER_ZERO_CHARGE_ATTESTATION_STALE`; provider deployment steps were skipped. That downstream failure is not represented as GREEN and does not fabricate provider acceptance. It is an external provider/cost attestation state to be re-established only when a later hosted/provider mutation actually requires it.

The accepted provider adapters remain source-only/dormant. They do not by themselves establish normal-user login, create a product session, activate public multi-user mode or authorize provider spend.

## Amendment 11 — technical closeout versus later public activation

The OWNER-approved sequencing correction is defined by:

`docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`.

For the transition containing this status update, Amendment 11 becomes accepted authority only after that focused governance PR is squash-merged and the resulting exact-main permanent Regression Shield is GREEN. Until that lifecycle completes, the current branch remains proposed governance only.

Once Amendment 11 is accepted, WP22A Phase 5 is explicitly split into two independent gates:

### A. WP22A technical-closeout gate — current source implementation authority

The technical gate may close WP22A only after the complete browser/auth/session/tenant/security/recovery architecture is implemented and accepted on the reviewed hosted technical boundary.

The technical gate may use deterministic Telegram/VK provider doubles only where real provider secrets, production callback registration or provider-console actions are genuinely non-delegable. Such doubles must remain below the deployed routing/network authority boundary and must never become a human-accessible login/session bypass.

The source implementation must still conform to current official Telegram/VK provider contracts and fail closed when provider configuration is absent or invalid.

### B. Public-production activation — later independent fail-closed gate

The following remain outside WP22A technical closeout and are not authorized merely because WP22A source/security becomes complete:

- final Cloud.ru Evolution production apply/cutover;
- production DNS/edge mutation;
- real provider secret provisioning and production callback registration when those actions require OWNER-held secrets/provider-console access;
- real-user public-production cutover;
- `PUBLIC_MULTI_USER_ENABLED=true`;
- recurring paid infrastructure commitment above the current zero-cost authority;
- production privacy/personal-data/legal/capacity/monitoring/incident sign-off;
- public T-Invest-backed functionality until the independent broker-terms permission gate passes.

## Current functional development authority

Current engineering authority remains **WP22A Phase 5 — Public-hosted acceptance**.

After Amendment 11 itself is accepted through merge + exact-main Regression Shield, the remaining Phase-5 source work is one integrated technical-closeout implementation branch/PR unless a concrete schema rollout, dependency/toolchain, security-isolation or objective reviewability constraint proves that a split is safer.

Ordinary module/file boundaries are not sufficient reason to return to many micro-increments.

The integrated source package must reuse the existing `apps/web`, `apps/api`, `omni_cio`, PostgreSQL, provider adapters, deployment and recovery architecture; no second Web product/Core/identity/database/broker stack is authorized.

## Canonical product-auth invariant

Every human product USER, including the PROJECT OWNER when using the product, follows exactly:

`Telegram Login or VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The deployed product must have no OWNER/admin/developer/demo login and no alternate session-minting path.

Historical acceptance mechanisms such as public preview session minting, loopback `private-test-login`, Cloudflare/engineering `private-external-login` or equivalent OWNER/admin routes must not survive as product-session entry points after integrated Phase-5 cutover.

Initial user access remains free of billing:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

Free access means no payment entitlement is required; it does not mean anonymous/demo access.

## Integrated Phase-5 technical-closeout outcome

The remaining source implementation must prove at minimum:

1. one hosted Web/BFF product path with provider/OAuth artefacts kept server-side and only an opaque first-party session exposed to the browser;
2. durable/shared one-time pre-auth transactions with state/browser-proof digests, server-side PKCE verifier/nonce as applicable, exact provider/redirect binding, TTL/capacity and atomic consume;
3. a separate high-entropy initiating-browser proof so provider callbacks cannot be completed from a different browser context merely by possessing callback parameters;
4. distinct Telegram/VK start and callback trust boundaries with provider mix-up, replay, stale-state and browser-swap failures denied;
5. Telegram JWKS live-concurrency/key-rotation hardening before provider routes are activated;
6. verified provider identity -> internal `OmniCIOUserAccount` -> Tenant -> durable PostgreSQL Session composition using the accepted identity/persistence architecture;
7. production-grade session fixation protection, fresh token issuance/rotation, bounded idle and absolute lifetime, logout and true revoke-all-sessions;
8. tenant authority only from resolved server-side session state, plus application authorization and PostgreSQL RLS/FORCE-RLS cross-tenant negatives;
9. coherent CSRF/Origin/Referer/Fetch-Metadata/CORS/Host/trusted-proxy/TLS/private-cache/security-header behavior;
10. bounded pre-auth/login/session/provider-outbound rate/abuse/capacity controls and fail-closed degradation;
11. no provider/product tokens in browser Web Storage and no auth codes, PKCE verifier, nonce, session cookie, provider token/client secret, raw provider subject, broker secret or tenant-private payload in source/CI/logs/artifacts;
12. frontend login surface with exactly Telegram and VK ID, disabled/fail-closed provider states and no demo/OWNER/admin fallback;
13. USER-facing `/system` diagnostics only, with no product-admin authority or misleading active OWNER-only semantics;
14. restart/redeploy/replacement-runtime, migration idempotency, recovery/restore-isolation and rollback evidence;
15. deterministic canonical phone/tablet/desktop browser acceptance against the hosted technical boundary;
16. exact release/Git SHA and health-before-traffic evidence;
17. complete preflight/full trust-flow diff review before one comprehensive DRAFT remote verification cycle;
18. all applicable exact-head DRAFT checks `success`, independent Gitar/Sonar review resolved, fresh unchanged-head READY checks `success`, zero blockers, squash merge and exact-main permanent Regression Shield `success`.

Technical browser/auth/session/tenant/security/recovery items cannot be deferred to the later public-production activation gate merely to close WP22A.

## Session and tenant boundary

Production session requirements remain:

- opaque high-entropy server-side session identifier;
- digest-only durable token storage;
- host-scoped `Secure`, `HttpOnly`, reviewed `SameSite` cookie;
- bounded idle and absolute lifetime;
- fixation protection and fresh issuance/rotation after authentication;
- explicit logout and revoke-all-sessions;
- no auth/session/refresh/provider token in browser Web Storage;
- tenant scope resolved only from authenticated server-side session state;
- private/auth responses protected from shared caching.

One normal account owns one isolated tenant in the baseline. Client-supplied `tenant_id`, `user_id`, URL/object identifier or provider engineering identity never grants product authority.

PostgreSQL RLS/FORCE-RLS remains a second independent isolation boundary; the hosted runtime role may not have SUPERUSER/BYPASSRLS authority.

## Broker, provider and cost locks

Final production provider remains **Cloud.ru Evolution**.

Current recurring infrastructure authorization remains:

- `0 RUB/month`;
- `0 USD/month`;
- provider apply false;
- no automatic paid fallback;
- no automatic paid overage/card charge.

Before a later production apply, exact current SKU/region/price/free-or-bonus eligibility and shutdown path must be revalidated. Any recurring commitment above zero requires explicit OWNER cost approval.

Public T-Invest-backed functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**.

Broker write remains OFF. `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged. No transfer/withdrawal/margin/uncovered-short authority is introduced by WP22A.

## OWNER-approved Web visual direction

The OWNER-approved Premium Spatial Financial OS specification remains planning authority at:

`docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`

It remains **NOT CURRENT-WP AUTHORITY BY ITSELF**. Amendment 11 and the integrated Phase-5 implementation do not silently authorize its CSS/TSX/runtime implementation.

Only the later evidence-backed WP22A closeout may explicitly authorize that named implementation increment in sequence.

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
- Block E / WP22A Phase 4 — **ACCEPTED**;
- Block E / WP22A Phase 5 — **AUTHORIZED CURRENT INCREMENT**;
- Block E / WP22A overall — **CURRENT / NOT YET COMPLETE**;
- Block F / WP23+ — **LOCKED**;
- public multi-user activation — **APPROVED TARGET / FLAG REMAINS OFF**;
- public-production activation — **SEPARATE LATER GATE / NOT AUTHORIZED**;
- zero-cost hosted technical boundary — **AVAILABLE FOR TECHNICAL ACCEPTANCE SUBJECT TO CURRENT ZERO-COST ATTESTATION**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe state through WP22A technical closeout.

## Current next package — WP22A Phase 5 — Public-hosted acceptance

The current governance transition is Amendment 11. It is not an implementation-progress increment and does not change the 40% program total.

After Amendment 11's own focused PR is accepted through squash merge + exact-main Regression Shield, the next authorized source package is **one integrated WP22A Phase-5 technical-closeout implementation branch/PR** covering the complete remaining auth/session/tenant/browser-security/recovery vertical flow.

That integrated implementation must be designed and completed before the first comprehensive remote DRAFT cycle. GitHub CI, Gitar, Sonar and hosted deployment are independent verifiers, not the normal interactive debugger. Cheap/focused compile/lint/type/schema/migration/security/negative tests and full-diff trust-flow review remain mandatory during implementation.

If the integrated implementation is accepted through merge + exact-main Regression Shield, Phase 5 still does not automatically make WP22A COMPLETE. A final small evidence/status closeout must map every technical Exit-Gate item to accepted evidence. Only then may canonical status mark WP22A COMPLETE and determine the next Master Plan unlock.

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
- active amendments 8, 9, 10 and 11 once Amendment 11's transition is accepted;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`;
- `docs/architecture/V10_WP22A_PHASE3_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`;
- accepted security/threat/recovery/WP22A architecture and runbooks.

GitHub remains engineering source of truth. Historical PRs, stale chat and old OWNER-only Personal-Node assumptions do not override accepted `main` plus later active amendments. OWNER-supplied evidence may be used only for genuinely non-delegable acceptance facts and must never be synthesized.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16–WP22 COMPLETE; WP22A Phases 1–4 ACCEPTED; Phase 5 CURRENT |
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
- `PUBLIC_MULTI_USER_ENABLED=false` through WP22A technical closeout and until the later production-activation gate;
- no broker-write expansion by WP22A;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/Telegram/VK/provider secret values, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- no paid resource or recurring spend without exact current cost revalidation and explicit OWNER approval above the current authorized cap;
- red CI is red; skipped/queued/pending/neutral is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

1. Complete the focused Amendment 11 governance PR on an exact branch from accepted main `bda8f51ad495520a92bd2715182684e216f76000`.
2. Require its full deterministic documentation/contract guard preflight, exact-head DRAFT GREEN, independent review where applicable, fresh READY GREEN, zero blockers, squash merge and exact-main Regression Shield.
3. Only from that accepted new main, create the single integrated WP22A Phase-5 technical-closeout implementation branch.
4. Implement the complete remaining browser/provider/account/session/tenant/security/recovery flow before opening its comprehensive DRAFT verification cycle.
5. Keep final Cloud.ru/public-user/provider-secret/paid activation, public T-Invest, broker write, Real execution, WP23 and visual runtime implementation locked until their separate accepted gates explicitly open them.
