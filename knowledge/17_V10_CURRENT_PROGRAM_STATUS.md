# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-09-21

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCKS A–E COMPLETE / WP0–WP22A COMPLETE / ACCEPTED IMPLEMENTATION 54% / AMENDMENT 18 TIMEWEB-ONLY PLATFORM CONSOLIDATION OWNER-APPROVED PENDING GREEN MERGE / CURRENT NEXT PACKAGE TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED / WEB-VISUAL PAUSED / WP23+ LOCKED / PUBLIC USER ACTIVATION FAIL-CLOSED**.

Accepted implementation progress is **54%**.

Blocks A (5%), B (9%), C (12%), D (14%) and E (14%) have passed their owning Exit Gates. WP16–WP22 and the complete **WP22A — External Web Access / Product Authentication Security Gate** are accepted COMPLETE.

Amendment 14 remains accepted authority: GitHub is engineering authority rank 1 and Cloudflare Workers Paid is platform rank 2 for new V10 application/edge/build work. The complete `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` execution chain is now accepted on protected `main`; its final focused CF-D hardening landed through PR #547.

Amendment 15 records the 2026-08-29 OWNER delivery correction: the four Amendment-14 Cloudflare implementation stages remain ordered and fail-closed but are executed as internal milestones of one `INTEGRATED_SYSTEM_UPDATE`, `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, on default branch `system/cloudflare-public-product`, with one final PR by default. Separate protected-main acceptance between CF-A/CF-B/CF-C/CF-D is no longer required. A real Amendment-12 split trigger discovered during implementation still forces a stop/split.

Neither Amendment 14 nor Amendment 15 by itself deploys Cloudflare, mutates DNS/domain/provider state, provisions secrets, activates public users or authorizes Real money.

`PUBLIC_MULTI_USER_ENABLED=false` remains the **current runtime state, not a V10-wide release lock**. Under Amendment 13, completed capabilities may become live as soon as their own real authentication/runtime/privacy/security/capacity/monitoring gates pass; unrelated unfinished V10 blocks are not a reason to hold a ready capability forever.

Amendment 18 records the OWNER decision to retire Cloudflare/Neon/Render/Cloud.ru/VK from active future V10 authority and consolidate production on Timeweb with Telegram-only human login. Once this governance change is accepted, `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` is the current authorized System Update. WEB-VISUAL and WP23+ remain paused until the consolidation/public-activation path reaches its owning exit gate.

## Amendment 18 — Timeweb-only platform consolidation / Telegram-only login

Accepted historical Cloudflare/Render/Neon chains remain evidence of what earlier code proved, but they do not remain future platform authority after Amendment 18 acceptance.

Final selected operating model:

- ChatGPT = engineering assistant only;
- GitHub = source/review/CI/release provenance;
- Timeweb Cloud = sole selected production infrastructure platform;
- Telegram Login = sole selected human product login provider.

Retirement targets are Cloudflare, Neon, Render, Cloud.ru and VK ID. External review/CI SaaS is also to be removed from the required path after equivalent-or-stronger GitHub-native checks are proven.

The active System Update is `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`, with ordered milestones TW-A→TW-G. It delivers provider-neutral application source, Timeweb App Platform exact-SHA deployment, Timeweb PostgreSQL 18 production cutover, Timeweb DNS/TLS/no-VPN Russian ingress, Telegram-only activation, then external-provider decommission with legacy repository artifacts left archive-in-place.

No new Cloudflare/Neon/Render/Cloud.ru/VK feature work is authorized. During migration the last-known-good provider remains only until its owning replacement/cutover gate succeeds.

Git history is not rewritten to remove old provider names. Legacy provider files remain archive-in-place by default; after cutover their live workflow/provider authority is disabled or revoked while historical provenance remains intact.

## Latest accepted Cloudflare runtime/release baseline

The final functional CF-D runtime/release baseline before this documentation-only closeout is:

`b8b27217a177d954ae1efb327b224503fd0e30b0`

It is the squash merge of PR #547, **CF-D: freeze provider secret custody on current main**, and it completes the accepted CF-D provider-secret custody hardening on top of the earlier Cloudflare/Neon convergence and recovery repairs. The exact current protected `main` SHA is always resolved from GitHub; this documentation record intentionally does not try to self-reference the future squash SHA that accepts its own closeout.

Exact-new-main acceptance on `b8b2721...` is proven by:

- Regression Shield #1617 / run `35320951393`: `completed / success`;
- V10 Engineering Governance #1607 / run `35320951440`: `completed / success`;
- the complete applicable exact-main push batch reached terminal `success`;
- V10 Cloudflare Production Release #78 / run `35321810810`: `completed / success` on the same exact main SHA;
- CF-D exact-main database-state/staging-anchor, staging rehearsal/production database-state, gated production promotion and terminal release DAG all concluded `success`;
- hosted staging and production database recovery jobs were correctly `skipped` only because their accepted reusable runtime database bindings were already ready; no required recovery outcome was suppressed;
- the exact accepted main was deployed through the gated Cloudflare Workers Build, the canonical Custom Domain was attached/verified, live production release acceptance passed, and rollback was correctly unnecessary.

This closes the implementation/recovery/security evidence chain for `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`. Issue #510 is completed. Issue #412 is the owning historical System Update dashboard; its issue lifecycle does not override this canonical accepted-state record.

Render is retired from active new-V10 deployment/alignment authority; historical WP22A Render/Neon evidence remains preserved. Protected V9 Render production/recovery and stable entrypoint `app:app` remain separate protected recovery boundaries.

## WP22A technical Exit Gate — COMPLETE

WP22A remains technically COMPLETE and Block E remains COMPLETE. The accepted technical boundary includes:

1. exactly Telegram Login and VK ID product-authentication contracts;
2. browser-bound durable one-time provider-auth transactions with state/PKCE/nonce/provider/redirect binding as applicable;
3. replay, stale, provider-mix-up and browser-swapping negatives;
4. verified external identity -> internal account -> isolated tenant -> server-side session composition;
5. opaque server-side session authority with fixation protection, bounded lifetime, logout/revocation semantics and no browser Web Storage token authority;
6. tenant scope derived only from authenticated server-side state plus PostgreSQL RLS/FORCE-RLS and cross-tenant negatives;
7. CSRF, Origin/Referer, Fetch Metadata, Host, trusted-edge/TLS, CORS, cache and security-header controls;
8. bounded request/provider abuse, rate, capacity and degraded fail-closed behavior;
9. migration/restart/redeploy/recovery/restore-isolation/rollback evidence;
10. hosted ordinary-browser/exact-release technical evidence independent of PROJECT OWNER home availability;
11. complete exact-head DRAFT/READY review chain plus exact-main Regression Shield.

Therefore:

- `wp22a_technical_gate_complete=true`;
- `wp22a_complete=true`;
- Block E is COMPLETE;
- accepted V10 implementation progress is **54%**.

### Historical WP22A hosted acceptance evidence

WP22A Phase 4/5 accepted a zero-cost synthetic Render + Neon PostgreSQL 18 proof-of-product as technical evidence. That historical chain remains valid evidence for the code/security/runtime properties it proved at the time:

- accepted implementation main `bb15739acf82ded8eafb6d006cf222fb3988770d`;
- Regression Shield run `32958019958`: `success`;
- hosted deployment run `32960260373`, attempt 2: `success`;
- fresh zero-charge OWNER attestation: `PASS_FRESH_NO_PAYMENT_METHOD`;
- Neon organization plan: `FREE_VERIFIED`;
- PostgreSQL bootstrap/migrations/runtime-role/grants/synthetic seed: PASS;
- historical Render deploy: `LIVE_EXACT_SHA`;
- historical external HTTPS exact-release probe: PASS;
- historical technical preview: `https://omni-cio-v10-web.onrender.com`.

This is **Render/Neon historical technical evidence**, not current new-V10 provider authority. Amendments 14/15 do not rewrite or delete it. Protected V9 Render production/recovery and stable entrypoint `app:app` also remain protected.

Canonical historical closeout evidence remains:

- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json`;
- `.github/workflows/v10-wp22a-phase5-technical-closeout.yml`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`.

## Earlier accepted WP22A authority

- WP22A Phase 1 — **ACCEPTED** historical provider/security-selection evidence;
- WP22A Phase 2 — **ACCEPTED**: verified identity -> account -> tenant -> session and tenant/RLS boundary;
- WP22A Phase 3 — **ACCEPTED**: hosted runtime/data/secret/recovery source boundary;
- WP22A Phase 4 — **ACCEPTED**: zero-cost synthetic Render Free + Neon PostgreSQL 18 proof-of-product;
- WP22A Phase 5 — **ACCEPTED**: integrated technical browser/provider/account/tenant/session/security/recovery/abuse closeout;
- WP22A overall — **COMPLETE**.

Provider names inside those accepted historical contracts remain true historical evidence. Amendment 14 supersedes conflicting **current/future** Cloud.ru/Render provider-selection wording for new V10 work without pretending that earlier acceptance happened on Cloudflare.

## Amendment 12 — ACCEPTED governance law

Amendment 12 defines exactly two execution units:

- `FOCUSED_CHANGE` for isolated defects, governance/documentation corrections, maintenance and mandatory split boundaries;
- `INTEGRATED_SYSTEM_UPDATE` for one coherent OWNER-authorized system outcome with ordered member WP/increments.

Mandatory split triggers include DB/migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

Amendment 14 originally represented build integration, runtime compatibility, provider mutation and public cutover as four separately accepted split states. Amendment 15 explicitly supersedes only that delivery granularity for this already-selected provider transition: the same four stages remain internal ordered authority milestones CF-A…CF-D inside one integrated update. Each milestone must pass its branch-local Exit Gate before dependent work begins. A concrete mandatory split trigger still overrides the one-branch default.

The prepared visual product update remains separate:

`WEB-VISUAL-A -> WEB-VISUAL-B -> WEB-VISUAL-C -> WEB-VISUAL-D -> WEB-VISUAL-E -> WEB-VISUAL-F -> WEB-VISUAL-G`

No `apps/web` visual-refresh source is authorized by Amendments 14/15.

## Amendment 13 — progressive capability activation

Amendment 13 remains active and its activation-state vocabulary remains exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

A completed user-facing capability does not need to wait for unrelated later V10 blocks or final `V10.0.0`. It becomes `LIVE_OPERABLE` only after every gate that actually owns that capability is accepted.

A separate user-facing staging product is not required. Local/CI/provider doubles, T-Invest Sandbox and Shadow remain allowed engineering/safety contours but never become a second product or product-auth bypass.

### Current capability activation baseline

| Capability | Current activation state | Current blocker summary |
|---|---|---|
| telegram_login | `BLOCKED_EXTERNAL` | Timeweb canonical runtime/callback + Telegram secret custody + public runtime privacy/capacity/monitoring acceptance |
| public_multi_user_tenant_access | `BLOCKED_EXTERNAL` | live Telegram auth + public-user privacy/legal/capacity/monitoring + accepted Timeweb runtime/database/DNS cutover |
| tinvest_read | `BLOCKED_EXTERNAL` | `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION` + tenant secret-custody/security/privacy/live-connection acceptance |

Current user-facing activation transitions — **BLOCKED_EXTERNAL where listed above**.

Public T-Invest-backed production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**. READ/live portfolio/positions/operations are independent from unfinished Real execution, but cannot become public `LIVE_OPERABLE` until broker terms/permission and tenant secret-custody/security/privacy/live acceptance are real and accepted.

## Amendment 14 — Cloudflare Platform & Continuous Release Authority

Canonical accepted-on-main sources:

- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`;
- `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `scripts/check_v10_cloudflare_platform_authority.py`;
- `.github/workflows/v10-engineering-governance.yml`.

Amendment 14 establishes:

- GitHub = engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid = managed application/edge/build platform rank 2 for new V10 work;
- Cloud.ru Evolution = no longer the selected new-V10 target;
- Render = no longer active new-V10 deployment, zero-charge attestation, hosted-release-alignment or recovery target;
- historical WP22A Render/Neon evidence and protected V9 Render `app:app` remain preserved;
- one canonical public Omni-CIO Web/product-auth/account/tenant/session stack;
- Cloudflare edge security is additive and never substitutes for product authorization or PostgreSQL tenant/RLS authority;
- existing React/Vite Web is the migration source; FastAPI/Python Workers/native dependency compatibility must be proved rather than assumed;
- Neon/PostgreSQL 18 authority stays intact until explicit equivalent migration proof; D1 does not silently replace it; Hyperdrive + PostgreSQL 18 requires compatibility evidence;
- Workers Paid included build capacity may be used only through the owning integration milestone;
- automatic paid overage or higher-plan expansion is not authorized without a fresh OWNER cost decision.

Current official Workers Builds reference values recorded by the contract on 2026-08-29 are mutable external facts and must be revalidated before material configuration: 6000 included build minutes/month, 6 concurrent builds/account, 20-minute build timeout, 4 vCPU/build, 8 GB memory/build and 20 GB disk/build.

### Continuous exact-main release law

Each accepted protected `main` SHA becomes a new public product revision **candidate**, not an automatic production deployment.

Required flow:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`

Before promotion the pipeline re-checks current `main`. A superseded candidate must not be promoted. If a newer `main` is not promotable, production stays on the last-known-good version and must expose `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC` rather than silently drifting.

Public release identity is event-derived CalVer `YYYY.MM.DD.N` plus exact `source_sha`, `cloudflare_version_id`, `released_at_utc` and release status. It must not create a source-code version-bump commit solely to change the displayed release number.

Cloudflare Worker rollback does not roll back external KV/R2/D1/Durable Object state; schema/storage compatibility and rollback remain separate required evidence.

## Amendment 15 — Cloudflare Public Product Integrated Delivery

Canonical proposed/accepted-on-main sources:

- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md`;
- `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json`;
- `scripts/check_v10_cloudflare_public_product_integrated.py`;
- `.github/workflows/v10-engineering-governance.yml`.

During execution, Amendment 15 established:

- execution unit = `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`;
- execution type = `INTEGRATED_SYSTEM_UPDATE`;
- default branch = `system/cloudflare-public-product`;
- one final PR by default;
- `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` -> `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` -> `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` -> `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` remain mandatory ordered internal milestones;
- a milestone's branch-local Exit Gate is required before dependent milestone work;
- separate main merge/acceptance between CF-A…CF-D is not required;
- a real Amendment-12 split trigger still forces a stop/split;
- Cloudflare-first replacement is preferred only where semantically equivalent and safe;
- Cloudflare Containers are allowed only for a proven full-Linux/native dependency runtime need;
- PostgreSQL/Neon may remain where Cloudflare lacks an accepted PostgreSQL 18/RLS equivalent;
- active new-V10 Render dependencies must be retired only after replacement parity/consumer/recovery review;
- protected historical WP22A evidence and V9 Render `app:app` remain preserved;
- WEB VISUAL remains separately OWNER-locked.

## Current functional development authority

The accepted `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED — Cloudflare Public Product System Update` is **COMPLETE**. Its ordered CF-A -> CF-B -> CF-C -> CF-D implementation/recovery/cutover chain has passed accepted-main production release evidence.

Current authorized functional implementation package: **NONE**.

Focused maintenance, defect repair, security/recovery hardening and documentation/governance corrections remain allowed when they are actually required, but they do not authorize a new product System Update.

The current next prepared product package is `WEB-VISUAL-INTEGRATED`. It remains **OWNER START REQUIRED** and is not authorized for source implementation until the exact start command below is issued.

### Prepared product package — WEB-VISUAL-INTEGRATED / OWNER START REQUIRED

`WEB-VISUAL-INTEGRATED — Premium Spatial Financial OS A→G System Update` remains the already prepared product update from Amendments 12/13. It is not erased by the Cloudflare transition, but it is not executed inside the current Cloudflare integrated branch.

Prepared member scope remains:

1. `WEB-VISUAL-A` — design-system foundation;
2. `WEB-VISUAL-B` — spatial shell/navigation;
3. `WEB-VISUAL-C` — Portfolio/Assets presentation;
4. `WEB-VISUAL-D` — Watchtower/Research/Risk/Decisions/Plans presentation;
5. `WEB-VISUAL-E` — Execution/Journal/System/Settings presentation;
6. `WEB-VISUAL-F` — atmosphere/optional spatial brand layer;
7. `WEB-VISUAL-G` — visual/performance/accessibility hardening.

**OWNER START REQUIRED.** The exact command remains:

`START V10 WEB VISUAL SYSTEM UPDATE`

Until that separate product execution is authorized and current sequencing is revalidated, do not create the visual-refresh implementation branch or modify `apps/web` merely for visual redesign.

## Amendment 17 — Russian PostgreSQL migration current stage

Amendment 17 / RU-PG-A is accepted on protected `main` through PR #560, squash merge `4c0422a5...`, Regression Shield #1625, V10 Engineering Governance #1666 and Cloudflare Production Release #86.

Accepted implementation progress remains **54%**. This migration is a legal/security/provider compatibility prerequisite and does not add product-progress percentage by itself.

Current authorized focused stage: **RU-PG-B — provider bootstrap / synthetic PostgreSQL 18 parity**.

RU-PG-B rules:

- first candidate: Timeweb Cloud Managed PostgreSQL 18 in Moscow / MSK-1 / Terraform location `ru-3`;
- synthetic data only;
- current Neon production authority remains accepted until an explicit later cutover;
- no production `OMNI_V10_POSTGRES_DSN` mutation;
- no real Telegram/user/session/portfolio/broker data;
- separate bootstrap and least-privilege runtime identities are mandatory;
- the documented minimum Timeweb 1 CPU / 1 GB / 8 GB tier remains unaccepted until real provider evidence proves the identity split without weakening security;
- OWNER-selected beta target: PostgreSQL 18, Moscow, 1 CPU / 2 GB RAM / 20 GB NVMe, recorded base price 790 RUB/month as of 2026-09-19;
- the 790 RUB approval covers the base DBaaS configuration; on 2026-09-20 the OWNER separately approved one public IPv4 up to 200 RUB/month for the RU-PG-B/RU-PG-C connectivity path, while backup-storage and other paid add-ons remain unauthorized; public-IP cost approval does not bypass the owning firewall/TLS security gate;
- scale up only after capacity evidence; Timeweb documents that scale-down is not supported;
- provider credentials never belong in source, chat, PR comments, CI logs or artifacts;
- RU-PG-C remains locked until RU-PG-B is `CERTIFIED_GREEN`.


## Amendment 18 — Russia-only public registration / reachable ingress

The OWNER-approved Russia-only public-launch direction becomes authority only when the
synchronized Amendment 18 checkpoint is accepted on protected `main`. It does not add
product-progress percentage and does not activate users by itself.

Current exact infrastructure evidence immediately preceding this checkpoint:

- protected main `33a47a728b024e80590761e45d643e2ef1c5b538` is the squash merge of PR #579;
- Regression Shield #1644 and V10 Engineering Governance #1793 completed `success`;
- Cloudflare Production Release #105 / run `35604840698` completed `success`;
- automatic Timeweb Read-Only Proof #11 / run `35606185512` completed `success`;
- provider marker: `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY` for PostgreSQL 18,
  location `ru-3`, 1 CPU / 2 GB RAM / 20 GB disk, existing target present;
- IPv4 inventory remains one unbound unproven address and recovery remains fail-closed with
  `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`.

The credential-health blocker is therefore closed. The current RU-PG-B live prerequisite
remains the already-designed existing-IPv4 custody transition, followed by firewall/TLS and
synthetic PostgreSQL parity.

Russia public-launch direction:

- issue #580 is the umbrella launch dashboard;
- final V10 production PostgreSQL target is Timeweb Cloud Managed PostgreSQL 18 in Russia;
- Neon remains current production/rollback authority until RU-PG-D cutover acceptance and
  is retired from active V10 production authority only through RU-PG-E;
- GitHub remains source/review/provenance authority;
- Cloudflare remains accepted build/release/staging/fallback authority;
- Cloudflare-only public ingress is not sufficient evidence for the supported Russia-only
  launch because current Cloudflare evidence records ISP-side reachability disruption;
- Timeweb App Platform is the first Russia-facing ingress/runtime candidate, but no live
  deployment, DNS cutover or purchase occurs merely from governance acceptance;
- one canonical Web/account/session/tenant/database truth is mandatory; no second product;
- production App Platform auto-deploy is forbidden; an exact accepted-main commit and
  release provenance are required;
- public registration remains fail-closed until database cutover, Russia-reachable ingress,
  privacy/legal/regulatory, monitoring and real-user isolation gates pass.

WEB-VISUAL and WP23+ remain independently locked. This infrastructure/public-activation
program does not start Telegram Bot, AI/Cortex, Guardian or broker-write work.

## Current external activation baseline — BLOCKED_EXTERNAL where gates remain

Current facts after accepted CF-D infrastructure/release cutover:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- the canonical Cloudflare Worker/Container/Custom Domain production release path is accepted on exact main `b8b2721...` through Production Release #78;
- that infrastructure/release acceptance does not by itself activate Telegram/VK login, public multi-user tenant access, T-Invest public READ or any broker-write capability;
- Render is historical new-V10 evidence only and must not receive new V10 mutation/attestation/alignment actions;
- Telegram canonical origin/callback registration and production runtime-secret readiness are accepted; VK ID remains independently unactivated;
- public-user privacy/personal-data/legal/capacity/monitoring/incident sign-off is pending;
- included Workers Paid capacity is authorized baseline, but uncontrolled paid overage/higher-plan expansion is not;
- public T-Invest remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

A capability may transition from `BLOCKED_EXTERNAL` to `LIVE_OPERABLE` only when its own exact provider/runtime/privacy/legal/security/capacity/monitoring/broker gates are actually satisfied. CF-D infrastructure acceptance is now complete; missing capability-specific evidence remains a truthful blocker and does not block unrelated safe capabilities.

## Broker / Real execution boundary — unchanged

Unchanged current locks:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- tenant READ/optional TRADE credential separation remains mandatory;
- TRADE/full-access credential is never a fallback for READ operations;
- `TRADE credential connected/verified` is not broker-submit authorization;
- `LIVE_OPERABLE` is not `REAL_MONEY_AUTHORIZED`;
- a GitHub merge, AI output, Cloudflare deployment, public release, System Update, WP22A completion or capability dashboard is never broker-submit authorization.

Real order submission may become `REAL_MONEY_AUTHORIZED` only through its later owning execution gate after representative Sandbox/Shadow evidence, immutable plan, authenticated USER approval, drift/preflight, ambiguous-submit reconciliation, kill switches and actual broker terms/permission.

Protected V9 production/recovery entrypoint remains `app:app`; its rollback boundary is untouched.

## OWNER-approved final V10 product direction

The approved final product remains one public modern multi-user Omni-CIO Web service reachable through ordinary Internet HTTPS without dependency on PROJECT OWNER home IP/Wi-Fi/router/LAN/Lenovo.

Canonical product identity remains:

`Telegram Login or VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The PROJECT OWNER is an ordinary USER when using the product. GitHub/Cloudflare/Windows/CI engineering authority cannot mint/select a tenant.

Initial USER access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

Future monetization remains `DEFERRED_OPTIONAL`.

## Accepted / current package state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1–WP4 — **COMPLETE (9%)**;
- Block C / WP5–WP10 incl. WP9A — **COMPLETE (12%)**;
- Block D / WP11–WP15 — **COMPLETE (14%)**;
- Block E / WP16–WP22 — **COMPLETE**;
- Block E / WP22A Phase 1 — **ACCEPTED**;
- Block E / WP22A Phase 2 — **ACCEPTED**;
- Block E / WP22A Phase 3 — **ACCEPTED**;
- Block E / WP22A Phase 4 — **ACCEPTED**;
- Block E / WP22A Phase 5 — **ACCEPTED**;
- Block E / WP22A overall — **COMPLETE**;
- Block E — **COMPLETE (14%)**;
- accepted V10 implementation — **54%**;
- Cloudflare platform authority — **Amendment 14 ACCEPTED on `main`**;
- Cloudflare integrated-delivery authority — **Amendment 15 ACCEPTED on `main`**;
- Cloudflare Public Product System Update — **CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / ACCEPTED COMPLETE**;
- current functional implementation package — **NONE**;
- product implementation — **PAUSED pending a new authorized System Update**;
- current next prepared product System Update — **WEB-VISUAL-INTEGRATED / OWNER START REQUIRED**;
- Block F / WP23+ — **LOCKED**;
- current user-facing activation transitions — **BLOCKED_EXTERNAL where listed above**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | COMPLETE — WP16–WP22A |
| F. Telegram | 8% | NOT STARTED — WP23 locked |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **54% ACCEPTED** |

## Current next package — TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED — Timeweb-only runtime/database/DNS/Telegram consolidation

OWNER authorization is recorded by Amendment 18.

Target stack:

`ChatGPT + GitHub + Timeweb Cloud + Telegram Login`

Default source branch after Amendment 18 acceptance:

`system/timeweb-platform-consolidation`

Ordered internal milestones:

1. `TW-A` — provider/dependency inventory and authority cleanup;
2. `TW-B` — provider-neutral runtime + Timeweb deployment source + Telegram-only auth + GitHub-native quality replacement;
3. `TW-C` — exact-SHA Timeweb App Platform candidate;
4. `TW-D` — Timeweb PostgreSQL 18 production cutover;
5. `TW-E` — Timeweb canonical DNS/TLS and Russia no-VPN acceptance;
6. `TW-F` — Telegram public registration/multi-user activation after legal/privacy/capacity gates;
7. `TW-G` — destructive legacy-provider decommission and current-tree cleanup.

WEB-VISUAL remains paused. WP23+ remains locked. No broker-write or Real-money authority changes.

Amendment-12 mandatory split triggers remain stronger than the one-branch preference. Production DB cutover, DNS/public cutover, destructive provider deletion, OWNER/legal actions and recovery boundaries require independent acceptance.

## Canonical authority

Mandatory current sources include:

- `AGENTS.md`;
- `README.md`;
- `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md` when Amendment 15 is accepted;
- `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
- `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`;
- `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json` when Amendment 15 is accepted;
- `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md`;
- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`;
- `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`;
- accepted active amendments and protected V9/security/recovery contracts.

GitHub remains engineering source of truth. Historical PR text, old screenshots, Cloudflare dashboard state or earlier package-local status headings do not override accepted `main` and this canonical status.

## Permanent safety / rollback invariants

- protected V9 deployment entrypoint remains `app:app`;
- protected V9 service and rollback remain available;
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain current protected defaults until the owning execution/Real-money gate explicitly changes them;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the current fail-closed runtime state until all remaining capability-specific authentication/multi-user external gates required for a transition are accepted;
- no broker-write expansion without `REAL_MONEY_AUTHORIZED` owning evidence;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- no cross-tenant authority expansion;
- no real broker/Telegram/VK/provider secret values, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts/chat;
- no paid overage or plan expansion without exact current cost revalidation and explicit OWNER approval above the already purchased Workers Paid baseline;
- RED is RED; skipped/queued/pending/neutral is not applicable-gate PASS;
- exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret/legal/provider evidence is never synthesized.

## Current next action

1. keep the authorized RU-PG-B infrastructure stage moving on issue #559 until it is `CERTIFIED_GREEN`; the immediate live blocker is the existing-IPv4 custody transition proven by Timeweb Read-Only Proof #11;
2. coordinate the complete Russia-only public-registration launch through issue #580 while preserving Amendment-12/17 split boundaries for provider mutation, recovery, DB cutover, ingress/DNS cutover, legal actions and user activation;
3. do not delete or disable current Neon production authority before accepted RU-PG-D cutover and rollback evidence; retire active Neon authority only through RU-PG-E;
4. do not deploy or purchase the Timeweb App Platform public candidate before its owning source/runtime/cost gate proves the exact accepted-main configuration;
5. no new functional product package is authorized while `WEB-VISUAL-INTEGRATED` remains OWNER-locked; keep it prepared but unstarted until the exact OWNER START command;
6. do not begin WP23+, Telegram Bot, AI/Cortex, Guardian, broker-write or Real execution;
7. never treat Cloudflare/Timeweb deployment, a GitHub merge, AI output or an OWNER visual START command as broker-submit authorization.
