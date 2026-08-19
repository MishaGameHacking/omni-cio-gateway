# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-19

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A CURRENT / PHASE 1 ACCEPTED / PHASE 2 ACCEPTED / PHASE 3 AUTHORIZED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the only authorized current functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

## Latest accepted engineering baseline

### WP22A Phase 2 — accepted

WP22A Phase 2 product-auth / tenant-security implementation PR #336 (`WP22A: implement product-auth tenant security correction`) was squash-merged to exact `main`:

`00fc692710aa9eaf02ca78ea0535b51600020768`

Its final exact PR head was:

`d3bc7b03b0ba589877e771ffe77bdd31e3d2a100`

Before merge, the exact PR head completed the required DRAFT and fresh READY verification cycles with all applicable GitHub/Lenovo checks `success`, supplemental CircleCI Linux governance/PostgreSQL lanes `success`, zero unresolved blocking review threads and final review of the expected 20-file Phase-2 diff.

Required post-merge Regression Shield evidence for exact main `00fc692710aa9eaf02ca78ea0535b51600020768` is now complete:

- Regression Shield **#1508**, run `32277165957`, exact branch `main`, exact head SHA `00fc692710aa9eaf02ca78ea0535b51600020768`;
- first attempt was RED only because `pip-audit` timed out reading `api.osv.dev`; `Quality, contracts and coverage` had already completed SUCCESS while SAST/secret-scan steps in the security job had not yet executed;
- the failed `Dependency, code and secret security` job was re-run on the **same exact main SHA**, without source changes or weakened checks;
- run attempt 2 completed **SUCCESS**;
- `Quality, contracts and coverage` — **SUCCESS**;
- `Dependency, code and secret security` — **SUCCESS**, including dependency audit, medium/high-confidence SAST and tracked-content secret scan.

The transient OSV timeout is infrastructure/network failure history, not a vulnerability finding and not a bypass: the RED attempt blocked acceptance until the same exact-main security job actually completed GREEN.

Therefore **WP22A Phase 2 is accepted**, and **WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation** is the authorized current increment.

### Phase-2 accepted product/security boundary

Phase 2 established the reviewed source/test boundary for:

- verified Telegram/VK identity abstraction -> internal Omni-CIO account -> one isolated tenant;
- keyed provider-subject binding without raw/enumerable provider subject storage;
- registration fail-closed by default;
- fresh/rotated opaque server-side sessions;
- historical engineering OWNER identity excluded from Telegram/VK product bindings;
- product session/API scope derived from server-side session state rather than client selectors;
- tenant-scoped broker persistence/API authority;
- transaction-local PostgreSQL tenant context plus RLS on generalized broker relations;
- restricted-role PostgreSQL cross-tenant negative rehearsal;
- removal of the historical remote OWNER edge-login UX from the normal product shell.

Phase 2 did **not** activate real Telegram/VK credentials, public registration, provider resources, public production ingress, T-Invest public connector authority, broker-write authority or WP23.

## Earlier accepted WP22A authority

### WP22A Phase 1 — accepted

WP22A Phase 1 service/hosting architecture decision PR #333 (`WP22A: adopt staged free-first hosting architecture`) was squash-merged to exact `main`:

`51dbe41ad1e63ddb4c0b101f573b70254a5255b8`

Required post-merge evidence completed successfully: Regression Shield **#1505 — SUCCESS** with both required jobs GREEN.

Accepted production managed-cloud provider/security boundary: **Cloud.ru Evolution**.

This selection is source architecture authority, not purchase/apply authority. Current recurring infrastructure authorization remains **0 RUB/month OWNER out-of-pocket**.

Binding cost order remains:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

Accepted staged model:

1. **Stage 0 — 0 RUB proof-of-product**: already-owned GitHub/Lenovo engineering capability; any public preview is synthetic/non-private only and Lenovo is not public production.
2. **Stage 1 — 0 RUB free/bonus hosted pilot**: eligible safe Cloud.ru free/bonus resources only after a fail-closed spend boundary.
3. **Stage 2 — minimum safe paid Cloud.ru pilot**: only when real-user production cannot safely be proven in Stages 0/1; exact SKU/cost must be revalidated immediately before apply and requires explicit OWNER recurring-cost approval.
4. **Stage 3 — HA scale-up**: only from measured load/SLA/failure-budget need.

No paid commitment is authorized by the Phase-1 selection itself.

### Earlier planning authority

OWNER-approved public/free/hosted planning correction PR #329 was squash-merged to exact `main` `5f535c0ced9514866bd3680042f3ba0bb012f866` with Regression Shield #1503 / run `32129304332` SUCCESS.

PR #329 remains accepted planning/governance authority for the public/free/multi-user hosted target. PR #333 is accepted Phase-1 service-selection authority. PR #336 is accepted Phase-2 product-auth/tenant-security implementation authority.

Temporary verification PR #338 was closed unmerged and is not accepted implementation authority.

## Current functional development authority

Current engineering authority is now:

- **WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation** is the only authorized current implementation increment;
- implementation starts from accepted exact `main` `00fc692710aa9eaf02ca78ea0535b51600020768` after this status transition is accepted;
- source-control the managed-cloud runtime/deployment/IaC boundary for the accepted Cloud.ru Evolution target;
- define durable tenant-aware PostgreSQL/private-state storage and migration/recovery behavior;
- define encrypted tenant-scoped broker-secret custody with least-privilege runtime access and no secret value in GitHub/CI/artifacts;
- define backup/restore, integrity verification, corrupt-backup rejection, replacement-runtime recovery and rollback while preserving tenant isolation;
- define runtime/service identities, public-edge trust assumptions, observability/incident boundaries and bounded capacity/cost controls needed before provider apply;
- provider configuration in this phase remains non-secret/dormant; **provider apply is not authorized by Phase 3 source work**;
- real public registration and public production ingress remain disabled until later WP22A phases;
- do not implement WP23 Telegram Bot Foundation, AI/Cortex or broker-write/Real work early;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the safe default.

OWNER action required now: **NO**. Engineering may proceed autonomously through source design, code, tests, CI and recovery rehearsal that do not require provider credentials or privileged provider mutation. Stop only at a genuinely non-delegable OWNER/provider/secret/admin/budget/legal/physical action.

## OWNER-approved final V10 product direction

### Public global Web

The approved final product target is a **public modern multi-user Omni-CIO Web service** reachable from ordinary Internet-connected modern phones/desktops through a public HTTPS hostname.

A normal USER must not require PROJECT OWNER home IP/Wi-Fi/router/LAN/home Internet, Lenovo as production origin, Tailscale/native VPN, GitHub repository access, provider membership or Windows/CI credentials.

The final public production origin must use the accepted managed-cloud boundary. Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback infrastructure, not the public availability anchor.

### USER identity and tenant isolation

Canonical product identity:

`Telegram Login or VK ID -> verified external identity binding -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The PROJECT OWNER is not a special product role. When using Omni-CIO, the PROJECT OWNER is an ordinary USER on the same account/tenant/session path as supported users.

Cloudflare/GitHub/cloud-provider/Windows/CI authority remains engineering authority and must never mint/select a product tenant.

Before public activation, API plus database-enforced tenant isolation and cross-tenant negative evidence must cover private records, broker connections, jobs, queues, caches, notifications, exports, backups/recovery and later AI/RAG memory.

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
- tenant scope resolved only from authenticated server-side session state.

### Free initial launch

Initial registered-user access is free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no payment method required for registration/login.

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

Public Omni-CIO Web/account/tenant development is separate from T-Invest public connector activation. A user-supplied token does not waive broker terms.

T-Invest-backed public production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION** until contractually valid permission/partner authority or another explicitly accepted compliant architecture exists. No UI/status may claim this gate passed before evidence exists.

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
- Block E / WP22A Phase 3 — **AUTHORIZED CURRENT INCREMENT**;
- Block E / WP22A overall — **CURRENT / NOT YET COMPLETE**;
- Block F / WP23+ — **LOCKED**;
- public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL EXIT GATES**;
- public Internet production ingress — **OFF / LOCKED**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default during WP22A.

## Current next package — WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation

Phase-3 purpose is to make the accepted public USER/tenant model deployable and recoverable on the selected managed-cloud boundary **without applying provider resources yet**.

Required Phase-3 source outcome includes at minimum:

- preserve the one existing `apps/web`, `apps/api` and deterministic `omni_cio` Core;
- source-controlled runtime/deployment/IaC declarations for the accepted Cloud.ru Evolution architecture;
- durable tenant-aware PostgreSQL/private-state design with explicit least-privilege runtime role and database-enforced isolation compatible with Phase-2 RLS;
- encrypted tenant broker-secret custody boundary with no plaintext secret material in source, CI, artifacts, browser storage or logs;
- backup/restore design and deterministic rehearsal covering integrity/hash verification, corrupt-backup rejection, tenant-preserving restore, replacement-runtime recovery and rollback;
- source-controlled public-edge/runtime trust configuration needed for later HTTPS activation, while actual public ingress remains off;
- health/observability/incident/recovery evidence hooks that distinguish application, cloud-provider and external provider/broker degradation;
- bounded capacity/cost declarations compatible with the accepted 0-RUB-first sequence;
- fail-closed provider placeholders only; no real provider credentials or privileged apply;
- `PUBLIC_MULTI_USER_ENABLED=false`, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and WP23 lock preserved.

Phase 3 does **not** itself create the public URL. Phase 4 owns protected provider bootstrap/apply; Phase 5 owns real public-hosted acceptance including HTTPS and normal USER login/session evidence.

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
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16–WP22 COMPLETE; WP22A Phase 1 ACCEPTED; Phase 2 ACCEPTED; Phase 3 CURRENT |
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
- WP22A Phase 1 PR #333 -> exact main `51dbe41ad1e63ddb4c0b101f573b70254a5255b8` + Regression Shield #1505 SUCCESS — accepted;
- WP22A Phase 2 PR #336 -> exact main `00fc692710aa9eaf02ca78ea0535b51600020768` + Regression Shield #1508 / run `32277165957`, attempt 2 SUCCESS with both required jobs SUCCESS — **accepted**.

Hosted jobs that did not execute because of external capacity/billing conditions are never counted as clean-room PASS. Infrastructure/network failures are classified truthfully but remain blocking until the applicable gate actually completes SUCCESS.

## Permanent safety / rollback invariants

- protected V9 deployment entrypoint remains `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false` until the owning public-activation gate;
- no broker-write expansion by WP22A;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/Telegram/VK/provider secrets, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped/queued/pending is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

After this Phase-2 closeout/status transition is accepted, begin **WP22A Phase 3 — Hosted runtime/data/secret/recovery implementation** from the resulting exact accepted `main`.

First implementation scope is intentionally narrow:

1. fill the V10 WP execution template for Phase 3 and freeze the exact source-only acceptance surface;
2. map the accepted Cloud.ru Evolution target to source-controlled runtime/IaC/deployment components without applying resources;
3. define least-privilege hosted PostgreSQL/private-state and encrypted tenant-secret boundaries;
4. implement deterministic backup/restore/replacement-runtime rehearsal and tenant-isolation recovery guards that can run without real provider secrets;
5. add focused source/security/recovery contracts and CI before any privileged provider action;
6. keep public ingress, real provider credentials, public registration and paid commitments off.

Do not start Phase 4 provider apply, Phase 5 public-hosted acceptance, WP23 Telegram Bot Foundation, AI/Cortex or broker-write work early.