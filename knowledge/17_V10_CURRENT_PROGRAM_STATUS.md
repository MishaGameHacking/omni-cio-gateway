# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-18

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16–WP22 COMPLETE / WP22A AUTHORIZED CURRENT PACKAGE / PUBLIC-FREE-HOSTED PLANNING CORRECTION ACCEPTED**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E remains in progress: WP16–WP22 are accepted COMPLETE; **WP22A — External Web Access / Product Authentication Security Gate** is the current authorized functional package and is not yet accepted complete. Block E receives no percentage credit until its own Exit Gate.

WP23+ remains locked behind the corrected WP22A Exit Gate and Master Plan sequence.

## Latest accepted engineering baseline

OWNER-approved public/free/hosted planning correction PR #329 was squash-merged to exact `main`:

`5f535c0ced9514866bd3680042f3ba0bb012f866`

Required post-merge evidence for that exact main is complete: **Regression Shield #1503 / run `32129304332` — SUCCESS**. Both required jobs completed SUCCESS:

- `Dependency, code and secret security`;
- `Quality, contracts and coverage`.

PR #329 is therefore accepted planning/governance authority. It does not itself increase implementation progress, complete WP22A, activate public production, select/purchase a provider, enable T-Invest public connector functionality, expand broker write authority or unlock WP23+.

CI-resilience maintenance PR #328 remains accepted engineering history at exact main `10c1c0368c6415c70279e8de71ee0792e371dd3a` with post-merge Regression Shield #1502 SUCCESS.

PR #327 (`Plan: separate Omni-CIO USER identity from PROJECT OWNER authority`) was closed **unmerged / superseded** on 2026-08-18. Its valid USER-vs-PROJECT-OWNER intent is carried forward by accepted PR #329 and Amendments 9/10. PR #327 itself is historical and is not accepted authority.

## Planning correction acceptance / functional development authority

OWNER required all agreed V10 plan corrections to be committed, reviewed, GREEN, squash-merged and post-merge verified before functional WP22A development resumed. That prerequisite is now satisfied by accepted PR #329 plus exact-main Regression Shield #1503 SUCCESS.

Therefore current engineering authority is:

- corrected **WP22A** functional development may resume from the latest accepted `main`;
- implementation must follow the corrected public-hosted WP22A execution/service-selection contracts and the Master Plan sequence;
- service/provider comparison and source-controlled architecture may proceed, but no paid provider purchase or privileged provider mutation is implied;
- public DNS/production activation remains locked until the owning security/isolation/recovery/legal/broker/capacity gates pass;
- broker write / Real execution authority remains unchanged;
- WP23+ remains locked.

OWNER action required now: **NO**. Engineering may proceed autonomously with the corrected WP22A implementation until a genuinely non-delegable provider/account/legal/secret/admin/budget/physical decision is reached; then use the accepted OWNER handoff standard.

## OWNER-approved final V10 product direction

### Public global Web

The approved final product target is a **public modern multi-user Omni-CIO Web service** reachable from ordinary Internet-connected modern phones/desktops through a public HTTPS hostname.

A normal USER must not require:

- PROJECT OWNER home public IP;
- PROJECT OWNER Wi-Fi/cable/mobile home Internet;
- PROJECT OWNER router/NAT/LAN;
- Lenovo laptop as public production origin;
- Tailscale/native VPN client for ordinary product use;
- GitHub repository access;
- Cloudflare/provider membership;
- Windows/CI credentials.

The final public production origin must be an approved **managed-cloud runtime** selected through the V10 service-selection/security/recovery process. Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback, not the public availability anchor.

Cloudflare may be used for reviewed DNS/TLS/WAF/DDoS/edge functions. Cloudflare/provider identity belongs to engineering authority and is not product authentication. A Tunnel whose sole production origin is the OWNER's home Lenovo/network does not satisfy the final hosted target.

### USER identity and tenant isolation

Canonical product identity remains:

`OmniCIOUserAccount -> Tenant -> Session -> tenant-scoped product state`

The PROJECT OWNER is not a special product role. When using Omni-CIO, the PROJECT OWNER is an ordinary USER using exactly the same account/tenant/session path as supported users.

Ordinary login methods remain Telegram Login and VK ID mapped to the internal Omni-CIO account. Product authority comes from reviewed product authentication plus server-side session state, never GitHub/cloud-provider/Windows ownership.

Before public activation, API plus database-enforced tenant isolation and cross-tenant negative tests must cover records, jobs, queues, caches, notifications, exports, backups/recovery and AI/RAG memory.

### Free initial launch

Initial registered-user access is free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no payment method required for registration/login;
- no 7-day trial or 1/3/6/12-month entitlement required for initial use.

Earlier paid/trial architecture is superseded for the initial launch. Future monetization is `DEFERRED_OPTIONAL` and requires a later explicit OWNER-approved amendment plus applicable legal/payment implementation.

### Tenant-owned broker credentials

For public V10, broker credentials are not application-global user credentials.

Canonical ownership:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker-account binding`

A credential submitted by USER A belongs only to Tenant A and must never be usable by Tenant B.

Raw credentials:

- are entered/replaced/revoked only through authenticated USER Web settings over reviewed HTTPS;
- are never returned to the browser after submission;
- are never stored in browser Web Storage;
- never enter GitHub, CI logs or artifacts;
- require encrypted-at-rest tenant-scoped cloud secret/data protection;
- are inaccessible to Cortex, ordinary CI and unrelated tenants.

Optional TRADE authority remains separate. Execution eligibility remains the same-tenant intersection:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

The accepted planning correction does not enable Real execution.

### Hosted tenant-private data

The managed-cloud public target explicitly supersedes the older assumption that every public USER's private investment data must remain on an OWNER/Personal Node.

Hosted tenant-private state and encrypted broker credentials are permitted only after the exact architecture passes security, privacy/personal-data, retention, secrets, backup/recovery and broker/legal gates. GitHub/CI still never stores these private values.

## T-Invest public connector gate

Current official T-Invest API documentation states that a public service based on T-Invest API is not permitted under ordinary client API access because data retransmission rights are not granted.

Therefore:

- public Omni-CIO Web/account/tenant development is a separate concern from T-Invest public connector activation;
- a user-supplied token does not waive broker terms;
- T-Invest-backed public production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION** until a contractually valid permission/partner arrangement or another explicitly accepted compliant architecture exists;
- no plan/UI/status may claim broker-terms approval before it exists.

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
- Block E / WP22A — **AUTHORIZED CURRENT PACKAGE / NOT YET ACCEPTED COMPLETE**;
- Block F / WP23+ — **LOCKED behind corrected WP22A and Master Plan sequence**;
- public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL EXIT GATES**;
- public Internet ingress — **OFF / LOCKED until corrected WP22A and production launch gates**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe implementation default during current WP22A implementation. The approved target after all required launch gates is public multi-user enabled.

## Current next package — WP22A External Web Access / Product Authentication Security Gate

Corrected objective: deliver the external-access, product-authentication and isolation security boundary for the eventual **public hosted** Omni-CIO product without making PROJECT OWNER infrastructure identity a product account and without making OWNER home infrastructure the production origin.

Required WP22A direction under the accepted planning correction:

- reuse the one accepted source-controlled Web App/Core rather than create a second site;
- design/accept an approved managed-cloud production origin independent of OWNER home IP/Wi-Fi/LAN/Lenovo;
- define public TLS termination, certificate lifecycle, trusted proxy chain, HSTS and Host allowlist;
- keep Cloudflare/provider administration separate from Omni-CIO USER authentication;
- use Telegram/VK -> internal Omni-CIO account -> server-side session product auth;
- define bounded session lifetime, rotation, revoke/logout and Secure/HttpOnly/SameSite cookies;
- enforce CSRF plus Origin/Referer/Host validation and deny-by-default CORS;
- enforce login/API abuse/rate limits without self-DoS of critical monitoring;
- deny direct/API tenant access without valid USER session/authorization;
- prove database-enforced tenant isolation and cross-scope negatives;
- define tenant-scoped secrets, encrypted hosted private state, backup/recovery and restoration without cross-tenant leakage;
- prove the public product does not depend on Lenovo/home availability;
- keep T-Invest public connector fail-closed until broker-terms permission is accepted;
- keep any future Real approval USER-scoped to that USER's own tenant/account with step-up/recent auth and all money-path gates.

Required checks retain ASVS-relevant controls, stolen/invalid/expired sessions, CSRF, Host/Origin abuse, brute-force/rate-limit behavior, direct API calls, tenant IDOR/cross-scope tests, restore leakage tests and Telegram replay/staleness where applicable.

WP22A Exit Gate: **no production public activation is accepted until the corrected hosted architecture and all required security/isolation/recovery/legal/broker/capacity gates are GREEN.**

## Canonical authority

Mandatory sources include:

- `AGENTS.md`;
- `README.md`;
- `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` + synchronized PDF/SHA manifest;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- accepted security/threat/recovery/WP22A architecture and runbooks.

GitHub remains engineering source of truth. Historical PRs/old OWNER-only Personal-Node contracts remain historical implementation evidence where superseded; they do not override later accepted amendments.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16–WP22 COMPLETE; corrected WP22A CURRENT |
| F. Telegram | 8% | NOT STARTED — planning only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **40% ACCEPTED** |

The 40% total is intentional: Block E is not credited piecemeal and corrected WP22A has not passed its Exit Gate.

## Accepted implementation evidence summary

Accepted implementation/history remains available through the merged PR chain and Git history. Key current anchors:

- WP0–WP15 accepted through the existing V10 evidence chain;
- Identity/Multi-Tenant amendment PR #278 accepted;
- WP16 PR #280 accepted;
- WP17 PR #282 accepted;
- WP18 PR #303 + post-merge Regression Shield #1486 — SUCCESS;
- WP19 PR #308 + post-merge Regression Shield #1488 — SUCCESS;
- WP20 PR #310 + post-merge Regression Shield #1490 — SUCCESS;
- WP21 PR #312 + post-merge Regression Shield #1492 — SUCCESS;
- WP22 PR #314 + post-merge Regression Shield #1494 and focused WP22 audit — SUCCESS;
- Browser-Only/Headless operations PRs #319/#320 accepted as engineering/operations history, superseded only where the later public-hosted amendment changes final production topology;
- Engineering Quality governance PR #322 accepted; post-merge Regression Shield #1498 — SUCCESS;
- WP22A Phase-A browser-only/clientless PR #321 accepted as dormant/pre-amendment implementation evidence, **not** final public product authority where OWNER identity/home origin conflicts with later planning;
- WP15 physical OWNER audit failures on later unrelated Web SHAs remain historical fail-closed evidence and were never relabeled PASS;
- CI-resilience PR #328 -> exact main `10c1c0368c6415c70279e8de71ee0792e371dd3a`; post-merge Regression Shield **#1502 SUCCESS** on that exact main;
- public/free/hosted planning PR #329 -> exact main `5f535c0ced9514866bd3680042f3ba0bb012f866`; post-merge Regression Shield **#1503 / run `32129304332` SUCCESS**, both required jobs SUCCESS.

Hosted jobs that did not execute because of external capacity/billing conditions were never counted as PASS.

## Permanent safety / rollback invariants

- deployment entrypoint for protected V9 remains `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion by Web/planning work;
- no real broker/Telegram/VK/provider secrets, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped/queued/pending is not PASS;
- focused PR + exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Begin corrected **WP22A Phase 1 — Service/hosting architecture decision** from the latest accepted `main` under `docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md` and `docs/architecture/V10_WP22A_SERVICE_SELECTION.md`.

First produce a current official-provider comparison and an explicit managed-cloud production-origin decision satisfying the no-home dependency, tenant data/secret isolation, recovery, capacity, cost and legal constraints. Do not place real provider secrets in PR/CI, do not purchase or mutate a paid provider without the required OWNER decision, do not activate public production, and do not begin WP23+ until the corrected WP22A Exit Gate passes.
