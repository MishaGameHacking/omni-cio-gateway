# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-24

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A CURRENT / PHASE 1 ACCEPTED / PHASE 2 ACCEPTED / PHASE 3 ACCEPTED / PHASE 4 ACCEPTED / PHASE 5 TECHNICAL CLOSEOUT AUTHORIZED / PUBLIC PRODUCTION ACTIVATION LOCKED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the only authorized current functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

Amendment 11 separates the complete WP22A technical Exit Gate from the later real public-production/provider activation gate. This is a sequencing correction only: all browser-auth/session/tenant/security/recovery/abuse requirements remain mandatory, while final Cloud.ru apply, real provider secret provisioning, paid commitment and `PUBLIC_MULTI_USER_ENABLED=true` remain independently fail-closed.

This file becomes current authority only when present on accepted protected `main`. The Phase-4 acceptance transition recorded here is valid only because its owning transition PR must complete the dedicated exact-base public acceptance gate plus all ordinary exact-head DRAFT/READY gates before squash merge.

## Latest accepted engineering baseline

### WP22A Phase 4 — accepted

Phase 4 established the zero-cost synthetic hosted proof-of-product through the accepted Render Free + Neon PostgreSQL 18 boundary while preserving V9 and all broker/Real locks.

The focused Phase-4 chain includes:

1. PR #357 — initial zero-cost Render + Neon preview — exact main `9814ce151c713711c33c9ee5026f34a6e11255cd`;
2. PR #359 — Frankfurt preview project selection — exact main `21c055a9f9abc1596c4f883801ee75ebd185b32f`;
3. PR #360 — Neon active-region response parsing — exact main `96154892e39f72f3d647aea089d44a3d000a112c`;
4. PR #364 — provisioner import-root correction — exact main `4e10a04376523248cba8d5fa2ec8288de345e1e9`;
5. PR #366 — PostgreSQL 18 runtime-role bootstrap semantics — exact main `3e6a50801e2ac8c75ab872a64d100a9a9424bc06`;
6. PR #368 — Render-assigned hostname authority — exact main `3aa41fdad9057ad1ca50b32ab5b03f7e4438fbf9`;
7. PR #369 — idempotent existing runtime-role retry — exact main `38f79cd5425bda1e745bb61a3eb560671db4ee8e`;
8. PR #370 — attempt-correlated secret-safe Render terminal diagnostics — exact main `60ced8498bd6ce64bdbbe04a63eed706d37098a6`;
9. PR #376 — read-only hosted startup under least-privilege runtime role — exact main `4dd5cf123726a76a08424f5376db5b6b10ba5a31`;
10. PR #378 — unavailable CircleCI retirement and PostgreSQL-18 evidence migration into the authoritative Windows gate — exact main `227296afe94212c1ca54b291edfb35740940e0b8`;
11. PR #379 — canonical mobile-shell token repair and responsive regression evidence — exact main `235ebfd386d46b74fb2428085ac233aa4494d696`;
12. PR #380 — OWNER-approved future Web visual-refresh brief only — exact main `4b8b0ce71e33c5e7b723e2f748a6fcf334bf6481`; runtime code is unchanged relative to `235ebfd386d46b74fb2428085ac233aa4494d696`.

Provider/runtime acceptance is consolidated in:

- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json`;
- `.github/workflows/v10-wp22a-phase4-public-acceptance.yml`.

The transition gate is read-only and must prove the public Render preview is HTTPS, healthy, database-ready, synthetic-only, private-cache protected, HSTS protected and bound to exact accepted runtime main `4b8b0ce71e33c5e7b723e2f748a6fcf334bf6481`. A stale release SHA or any failed probe keeps Phase 4 RED and blocks this transition.

### Phase-4 accepted boundary

Phase 4 accepts only the synthetic proof-of-product:

- separate Render Free service `omni-cio-v10-web`;
- Neon PostgreSQL 18 Free preview database in the accepted Frankfurt boundary;
- exact migration/bootstrap and least-privilege SQL-created runtime-role separation;
- FORCE-RLS / tenant-aware database protections and synthetic seed only;
- hosted FastAPI + existing React application in one source-controlled product;
- provider-returned public HTTPS preview URL and exact release/readiness proof;
- public registration disabled;
- no real broker credential/private portfolio/account payload;
- no protected V9 service mutation;
- no paid resource/automatic paid overage;
- broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- WP23 remains locked.

Phase 4 does not imply normal USER product-auth technical acceptance or real public-production activation. Phase 5 owns the former; Amendment 11 assigns the latter to a separate later gate.

## Earlier accepted WP22A authority

### WP22A Phase 3 — accepted

The five focused Phase-3 hosted-runtime source increments are accepted:

1. PR #341 — dormant Cloud.ru Evolution IaC boundary — exact main `9043e1c4c3d448ca570ec04cdf729dc05d7bb441`;
2. PR #343 — hosted runtime and tenant READ-secret custody contract — exact main `5c17fa329acc294c52db9d09169e0fe63b815733`;
3. PR #345 — hosted PostgreSQL least-privilege runtime-user, effective-ACL and FORCE-RLS boundary — exact main `9ba45a6040365599bcfdebbbec90938e1deaa5e5`;
4. PR #347 — tenant-preserving hosted recovery integrity boundary — exact main `912e3eee44f73d15d9a81186515957c1f3d6cbb8`;
5. PR #350 — hosted edge trust, readiness, observability, capacity/cost and release/rollback boundary — exact main `b4d1098d518613f6c10dfa74397a512c804b2928`.

PR #352 consolidated Phase-3 evidence to exact main `fbd50b2aa5029170d9aabf178103e2e761648422`. Regression Shield #1515 / run `32445484371` completed SUCCESS with both required jobs SUCCESS, and temporary verifier PR #353 independently confirmed the exact main/run/job evidence through read-only `actions: read` authority before closing unmerged.

### WP22A Phase 2 — accepted

PR #336 accepted the verified external-identity -> internal account -> tenant -> server-side session boundary, tenant-scoped broker persistence/API authority and PostgreSQL tenant/RLS correction on exact main `00fc692710aa9eaf02ca78ea0535b51600020768`.

Regression Shield #1508 / run `32277165957`, attempt 2, completed SUCCESS with both required jobs GREEN after the first attempt was blocked by a transient OSV network timeout.

### WP22A Phase 1 — accepted

PR #333 selected **Cloud.ru Evolution** as the managed-cloud production provider/security boundary and was accepted on exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` with Regression Shield #1505 SUCCESS.

The accepted cost order remains:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

Provider selection did not authorize a paid commitment.

## Current functional development authority

Current engineering authority is:

- **WP22A Phase 5 — Integrated technical closeout** is the only authorized current implementation increment;
- Amendment 11 authorizes one integrated Phase-5 source branch/PR unless a documented deploy-before-code migration, independently reversible rollout, security-isolation boundary or objectively unreviewable final diff requires a split;
- Phase 5 begins only after the Phase-4 acceptance/status transition is accepted on protected `main`;
- reuse the existing `apps/web`, `apps/api`, `omni_cio`, PostgreSQL, deployment and recovery architecture; no second Web product/Core/identity/database/broker stack;
- prove normal hosted HTTPS product use from ordinary supported phone/desktop browsers without OWNER home infrastructure as the availability anchor;
- implement/accept only the Telegram Login and VK ID product-auth surface required for verified external identity -> internal account binding; do not start WP23 Telegram Bot Foundation;
- remove every deployed preview/private/OWNER/admin/developer/demo session-minting bypass; free access still requires Telegram or VK ID;
- accept deterministic provider doubles only below deployed routing/network boundaries when real secrets/provider-console actions are non-delegable; such doubles may never become a human-accessible session issuer;
- resolve tenant scope only from authenticated server-side session state;
- prove login/logout/session rotation/revocation, deployed tenant isolation, recovery/availability and rate/abuse/capacity behavior;
- keep public T-Invest-backed production functionality fail-closed pending accepted broker permission;
- keep broker write OFF, `trading_methods=false` and `REAL_TRADING_ENABLED=false`;
- keep `PUBLIC_MULTI_USER_ENABLED=false` through WP22A technical closeout and until the later independent public-production activation gate proves all owning acceptance conditions;
- keep initial USER access free: `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`;
- final production provider remains Cloud.ru Evolution;
- current recurring infrastructure authorization remains `0 RUB/month` / `0 USD/month`;
- before any paid Cloud.ru apply, revalidate exact SKU/region/current price and obtain explicit OWNER cost approval above the current zero-cost cap;
- no automatic paid fallback or card charge is authorized;
- final Cloud.ru apply, production DNS/edge mutation, real provider secret provisioning and real public-user cutover remain outside technical closeout and are not authorized by Phase 5;
- do not implement WP23, AI/Cortex or broker-write/Real work early.

The Phase-5 authority is defined by:

- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`;
- `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
- accepted active amendments 8, 9, 10 and 11;
- the existing WP22A security/recovery/service-selection contracts.

OWNER action required now: **NO** for the integrated Phase-5 source implementation and deterministic hosted technical acceptance. Stop only at a genuinely non-delegable provider/account/billing/legal/secret/physical action. Such an action belongs to the later public-production activation gate unless it is strictly required to verify a non-synthesizable technical fact. In particular, a recurring paid Cloud.ru commitment above the current `0` cap requires explicit OWNER approval after exact current pricing/SKU is known.

## OWNER-approved final V10 product direction

### Public global Web

The approved final product target is a **public modern multi-user Omni-CIO Web service** reachable from ordinary Internet-connected modern phones/desktops through a public HTTPS hostname.

A normal USER must not require PROJECT OWNER home IP/Wi-Fi/router/LAN/home Internet, Lenovo as production origin, Tailscale/native VPN, GitHub repository access, provider membership or Windows/CI credentials.

The final public production origin remains the accepted Cloud.ru Evolution managed-cloud boundary. Render/Neon Phase 4 remains a zero-cost synthetic proof-of-product and does not replace that production decision.

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

No real broker credential is authorized in the Phase-4 synthetic preview. Phase 5 may implement only the accepted tenant-scoped real-user custody boundary; public T-Invest-backed production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION** until its independent permission gate passes.

## OWNER-approved Web visual direction

The OWNER-approved Premium Spatial Financial OS specification is accepted planning authority at:

`docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`

It remains **NOT CURRENT-WP AUTHORITY BY ITSELF**. Phase 5 does not silently authorize its CSS/TSX/runtime implementation. The visual refresh may begin only when a later accepted canonical status/amendment explicitly authorizes that named increment in sequence. Until then, Phase-5 Web changes are limited to the functional/auth/session/tenant/recovery/acceptance work required by WP22A.

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
- Block E / WP22A Phase 5 — **INTEGRATED TECHNICAL CLOSEOUT AUTHORIZED CURRENT INCREMENT**;
- Block E / WP22A overall — **CURRENT / NOT YET COMPLETE**;
- Block F / WP23+ — **LOCKED**;
- public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL SEPARATE PUBLIC-PRODUCTION ACTIVATION GATE**;
- public production Internet ingress — **SEPARATE PUBLIC-PRODUCTION ACTIVATION GATE / LOCKED**;
- zero-cost synthetic preview HTTPS — **PHASE-4 ACCEPTED PROOF-OF-PRODUCT**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default during and after WP22A technical closeout until the separate public-production activation gate passes.

## Current next package — WP22A Phase 5 — Integrated technical closeout

Phase-5 purpose is to close the complete hosted technical product-authentication/security/recovery boundary without widening broker/execution authority or bypassing provider/cost/legal requirements. Final Cloud.ru/public-user activation remains a later independent fail-closed gate.

Required Phase-5 outcome includes at minimum:

1. ordinary hosted HTTPS reachability from supported phone/desktop browsers independent of OWNER home infrastructure;
2. verified Telegram Login / VK ID -> internal account binding with no provider engineering identity as product authority;
3. no deployed preview/private/OWNER/admin/developer/demo route capable of minting a product session;
4. durable browser-bound one-time pre-auth transactions plus provider mix-up/replay/browser-swapping negatives;
5. server-side session fixation protection, rotation, bounded lifetime, logout and revoke-all acceptance;
6. tenant scope derived only from server-side session state and deployed cross-tenant negatives over applicable private surfaces;
7. tenant-scoped secret/private-state custody without raw credential return or browser Web Storage;
8. deployed recovery/replacement-runtime/availability evidence with tenant isolation preserved;
9. measured request/rate/abuse/capacity controls and fail-closed degraded behavior;
10. accepted trusted-proxy/Host/TLS/CORS/Origin/Referer/CSRF/Fetch-Metadata/private-cache/security-header behavior;
11. exact release provenance, health-before-traffic and rollback evidence;
12. deterministic provider acceptance below deployed routing where real secrets/provider-console actions are non-delegable, without any deployed synthetic session issuer;
13. public T-Invest-backed functionality remaining independently fail-closed until broker permission;
14. no broker-write/Real execution expansion and no WP23 early work;
15. one comprehensive exact-head DRAFT GREEN -> independent Gitar/Sonar -> fresh READY GREEN -> zero blockers -> squash merge -> exact-main Regression Shield GREEN cycle for the integrated implementation.

Integrated Phase-5 implementation acceptance does not automatically make WP22A COMPLETE. A final small WP22A closeout must map all technical Exit-Gate evidence and only then may canonical status advance. Final Cloud.ru apply, real provider/public-user cutover, paid commitment and `PUBLIC_MULTI_USER_ENABLED=true` remain pending even after technical WP22A closure until their later activation gate passes.

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
- `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
- active amendments 8, 9, 10 and 11;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`;
- `docs/architecture/V10_WP22A_PHASE3_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`;
- accepted security/threat/recovery/WP22A architecture and runbooks.

GitHub remains engineering source of truth. Historical PRs and old OWNER-only Personal-Node assumptions do not override accepted `main` plus later active amendments. OWNER-supplied evidence may be used only for genuinely non-delegable acceptance facts and must never be synthesized.

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
- `PUBLIC_MULTI_USER_ENABLED=false` until the separate public-production activation gate;
- no broker-write expansion by WP22A;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/Telegram/VK/provider secret values, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- Phase-4 provider secrets remain accepted-main-only and are never printed;
- no paid resource or recurring spend without exact current cost revalidation and explicit OWNER approval above the current authorized cap;
- red CI is red; skipped/queued/pending/neutral is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

After Amendment 11 is accepted:

1. restore exact new `main` and its required post-merge Regression Shield evidence;
2. create one integrated WP22A Phase-5 technical-closeout implementation branch from that exact accepted main;
3. implement the complete Browser -> Provider -> Account -> Tenant -> Session -> API/PostgreSQL flow, retire deployed synthetic/OWNER/admin session bypasses and add deterministic negative/recovery/browser evidence;
4. finish all source, migrations, tests, frontend, deployment contracts and documentation before the first comprehensive DRAFT verification cycle;
5. complete exact-head DRAFT GREEN, independent Gitar/Sonar, fresh READY GREEN, squash merge and exact-main Regression Shield;
6. create only then a small evidence/status closeout PR mapping every technical Exit-Gate item before marking WP22A complete or authorizing the next named increment;
7. leave final Cloud.ru/public-user/provider-secret/paid production activation locked for its later explicit gate and OWNER action where non-delegable;
8. keep public T-Invest, broker write, Real execution, WP23 and the Premium Spatial visual-refresh implementation locked until their own accepted authority explicitly opens them.
