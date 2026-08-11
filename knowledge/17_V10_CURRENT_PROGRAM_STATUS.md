# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-11

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK C COMPLETE / WP15 CODE+SECURITY ACCEPTED / WP17 COMPLETE / BLOCK D LIVE ACCEPTANCE REQUIRED NEXT / WP18 LOCKED**.

Accepted implementation progress remains **26%**.

Block C's full 12% weight is accepted. Block D is deliberately **not credited** yet: WP11–WP14 are complete and WP15 implementation/code/security is accepted, but the OWNER-approved Identity / Multi-Tenant Account / Authentication Amendment requires the deferred real T-Invest READ acceptance to be completed through the reviewed authenticated Web broker-provisioning flow delivered by WP17.

WP16 and WP17 are repository-accepted through exact-head PR review, required Lenovo CI, squash merge and exact-main post-merge Regression Shield. Block E remains in progress and is not credited piecemeal before its own Block Exit Gate.

The next authorized dependency gate is **the deferred WP15 live broker READ acceptance through the accepted WP17 `Settings -> Broker Connections` flow**. WP18 implementation is not authorized until that dependency is handled according to the amendment and Master Plan; WP18 real-data acceptance remains explicitly locked until the live evidence passes.

The live gate must prove, for the authenticated tenant/BrokerConnection:

- READ_ONLY broker authority;
- intended broker-account selection using masked outward identity only;
- portfolio-summary parity;
- one sample-position quantity/value parity;
- acceptable freshness;
- sanitized evidence bound to the reviewed implementation.

No real T-Invest token, full account ID or private portfolio payload may be placed in GitHub, CI, chat, logs or artifacts. The normal credential entry point is the authenticated Web UI, not PowerShell.

Owner action required now: **none while this status-only transition is being reviewed and regression-verified**. After the dedicated live-acceptance path is prepared and rehearsed without secrets, the OWNER will be asked only for the physical browser action that cannot be delegated: enter the existing READ token into the accepted local/private Web Settings flow and verify the requested masked/parity evidence.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Accepted / current WP state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B / WP3 — **COMPLETE**;
- Block B / WP4 — **COMPLETE (Block B accepted at 9%)**;
- Block C / WP5 — **COMPLETE**;
- Block C / WP6 — **COMPLETE**;
- Block C / WP7 — **COMPLETE**;
- Block C / WP8 — **COMPLETE**;
- Block C / WP9 — **COMPLETE**;
- Block C / WP9A — **COMPLETE**;
- Block C / WP10 — **COMPLETE (Block C accepted at 12%)**;
- Block D / WP11 — **COMPLETE**;
- Block D / WP12 — **COMPLETE**;
- Block D / WP13 — **COMPLETE**;
- Block D / WP14 — **COMPLETE**;
- Block D / WP15 — **IMPLEMENTATION / CODE / SECURITY ACCEPTED; LIVE BROKER EVIDENCE REQUIRED THROUGH ACCEPTED WP17 WEB FLOW**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **COMPLETE**;
- Block E / WP18+ — **LOCKED behind owning dependencies and Master Plan sequence**;
- WP18 real-data acceptance — **LOCKED behind deferred WP15 live evidence**;
- public multi-user activation — **OFF / LOCKED**;
- public Internet ingress — **OFF / LOCKED until its owning security gate**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED by this status transition**.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

Accepted planning amendments are indexed by:

- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`.

The current WP15/WP17/WP18 sequencing is additionally governed by the accepted OWNER amendment:

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `docs/operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`;
- `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`;
- `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`;
- `docs/architecture/V10_WP16_WEB_DESIGN_SYSTEM_CONTRACT.md`;
- `docs/architecture/ADR-0011-web-read-credential-provisioning.md`;
- `docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json`;
- `docs/operations/V10_WP17_APPLICATION_SHELL_RUNBOOK.md`.

Binding execution/navigation sources also include:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- accepted architecture/security/recovery/operations contracts.

GitHub remains engineering source of truth. The protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | IMPLEMENTATION ACCEPTED THROUGH WP15 CODE+SECURITY; LIVE BROKER EVIDENCE REQUIRED / BLOCK CREDIT WITHHELD |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 COMPLETE / WP17 COMPLETE / WP18 LOCKED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **26% ACCEPTED** |

The 26% accepted total is intentional. WP16/WP17 acceptance advances Block E implementation but does not credit Block E piecemeal. Block D receives its planned weight only after the deferred WP15 live broker evidence and the amended Block D acceptance requirements are actually satisfied.

## Accepted implementation evidence index

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 primary PR #248 -> `cc37bdce69331e8b03f5fd46554dc486616414f6`;
- WP4 hardening PR #249 -> `6c97df17f0de21a27ec0d12ee9699d2a00fab53f`; post-merge Regression Shield run `31181814984` — **SUCCESS**;
- WP5 PR #251 -> `d0b80f91a434e93e5facb244a92b17b066ccdf2a`; post-merge Regression Shield run `31252745722` — **SUCCESS**;
- WP6 PR #253 -> `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-merge Regression Shield run `31270545874` — **SUCCESS**;
- WP7 PR #255 -> `82225eef984f6c14c254108bada0627c1f0368a4`; post-merge Regression Shield run `31281148813` — **SUCCESS**;
- WP8 PR #257 -> `422ef68864050eec858e32d980165c995d9e7ecb`; post-merge Regression Shield run `31284931677` — **SUCCESS**;
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`; post-merge Regression Shield run `31291892741` — **SUCCESS**;
- WP9A PR #261 -> `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`; post-merge Regression Shield #1445 / run `31294998878` — **SUCCESS**;
- WP10 rebuild PR #267 -> `6ba81af6d8abd676ad994ddef83048c170c99584`; post-merge Regression Shield #1450 / run `31326712297` — **SUCCESS**;
- WP11 clean rebuild PR #269 -> `1aa65e2420a01a5da7b5123a279a5940b3ea59d4`; post-merge Regression Shield #1452 / run `31329587509` — **SUCCESS**;
- WP12 PR #271 -> `365b49ad1ef428f4b534555cf387f2d3504a770f`; post-merge Regression Shield #1454 / run `31332149156` — **SUCCESS**;
- WP13 PR #273 -> `d74b0177c730cad0a8e3a69d1504e226bedbac27`; post-merge Regression Shield #1456 / run `31370195951` — **SUCCESS**;
- WP14 PR #275 -> `ff9bb37b6538fe9665ea0a652a0623354f0195da`; post-merge Regression Shield #1458 / run `31379587986` — **SUCCESS**;
- Identity / Multi-Tenant Account / Authentication planning PR #278 -> `cbf6a7adba78fa56d23e90ce2cfe2952d21a5e5b`; post-merge Regression Shield #1460 — **SUCCESS**;
- WP15 PR #277 -> `f8862d1af88400189d3c0780d2029a87cb5427ca`; post-merge Regression Shield #1461 / run `31419650823` — **SUCCESS**;
- WP16 PR #280 -> `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`; post-merge Regression Shield #1463 / run `31468739530` — **SUCCESS**;
- WP17 PR #282 -> `5b6b12f144c9bfa71307dcb28548a97527456b5b`; post-merge WP17 Audit #59 / run `31499348099` — **SUCCESS**; post-merge Regression Shield #1465 / run `31499348098` — **SUCCESS**.

## WP15 accepted implementation and deferred live evidence

WP15 final reviewed PR head was `077b2dab32f6f0efc281cd18c332bdd80752e4cd`; it was squash-merged as `f8862d1af88400189d3c0780d2029a87cb5427ca` after fresh exact-head authoritative/focused/deferred-live gates and zero blocking review threads. Post-WP15 Regression Shield #1461 / run `31419650823` completed **SUCCESS**.

Accepted WP15 code provides the narrow connection-scoped T-Invest READ layer with `Tenant -> BrokerConnection -> READ credential -> verified broker-account bindings`, fail-closed authority validation, masked outward identity, exact Decimal/UTC normalization, market enrichment and bounded/resumable operations reads. No broker write, transfer/withdrawal, trading-token fallback or Real execution authority was added.

The accepted Identity / Multi-Tenant Account / Authentication Amendment intentionally supersedes the old normal PowerShell OWNER token workflow. The source-controlled marker remains `LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING` until a dedicated reviewed live-acceptance transition records real evidence safely.

The deferred live gate must be completed through the accepted WP17 authenticated Web flow. For the authenticated tenant/BrokerConnection it must prove READ_ONLY authority, intended broker-account selection, portfolio-summary parity, one sample-position quantity/value parity, acceptable freshness and sanitized evidence bound to the reviewed implementation. Until that succeeds, Block D stays uncredited and WP18 cannot claim real broker data accepted.

## WP16 accepted implementation evidence

WP16 final reviewed PR head was `b4adef760696343382ca7319f7f7ac7e95db671a`; it was squash-merged as `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`. Post-WP16 Regression Shield #1463 / run `31468739530` completed **SUCCESS**.

Accepted WP16 provides the single source-controlled Web foundation at `apps/web/` with exact-pinned React/Vite/TypeScript/Node/npm baseline, reusable design tokens/components, responsive/accessibility evidence and dependency/browser security guards. It did not activate WP17 auth/navigation early, public multi-user/ingress, real portfolio UI, broker write, transfer/withdrawal or Real authority.

## WP17 accepted implementation evidence

WP17 final reviewed PR head was:

`bb68126f37270c06763cb1765db5d5944a73bc95`

Fresh exact-head acceptance on that head proved:

- V10 WP13 PostgreSQL Audit #112 / run `31495349542` — **SUCCESS**;
- V10 WP14 Durable Jobs Audit #69 / run `31495349554` — **SUCCESS**;
- V10 WP15 T-Invest Read Audit #137 / run `31495349539` — **SUCCESS**;
- V10 WP16 Web Design System Audit #87 / run `31495349584` — **SUCCESS**;
- V10 WP17 Application Shell Audit #58 / run `31495349557` — **SUCCESS**;
- Self-Hosted Windows CI #757 / run `31495349537` — **SUCCESS**, including protected Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan;
- V10 WP17 OWNER Read Vault Audit #12, rerun attempt 2 — **SUCCESS**, exact implementation/script hashes bound, runner non-admin, runner secret read/write denied, runner evidence write denied, no real secret values used, `ready=true`;
- review submissions — **zero**;
- blocking inline review threads — **zero**;
- PR conversation comments — **zero**;
- base `main...head` was `behind_by=0` with exactly 44 expected files.

GitHub-hosted Fast PR Checks #665 and Toolchain Compatibility #700 did not start because GitHub reported account payment/spending-limit startup failure. They remain recorded as external hosted-infrastructure/billing failures, **not PASS and not code failures**; downstream skipped jobs are not credited.

PR #282 was squash-merged with an exact-head guard as:

`5b6b12f144c9bfa71307dcb28548a97527456b5b`

That exact commit became `main`. Post-merge WP17 Application Shell Audit #59 / run `31499348099` completed **SUCCESS**. Mandatory post-merge Regression Shield #1465 / run `31499348098` also completed **SUCCESS**: its quality/contracts/coverage job passed dependency-lock reproduction, policy/repository/toolchain/regression guards, compile, Ruff, formatter baseline, mypy, stable gateway entrypoint, read-only release contract and the full Regression Shield with coverage; its independent security job passed runtime dependency audit, medium/high-confidence SAST and tracked-content secret scan.

### WP17 functional/security acceptance

Accepted WP17 provides:

- the single source-controlled authenticated application shell and canonical navigation routes;
- Telegram/VK ID provider abstraction while real provider credentials/public ingress remain disabled;
- server-side opaque revocable sessions with no browser Web Storage credential/session state;
- server-derived tenant context and route guards;
- global health/freshness and degraded-state behavior;
- Web build/version identity shown only on System;
- authenticated `Settings -> Broker Connections` READ-token preview/select/commit/replace/revoke UX;
- accepted WP15 multi-account READ validation reused rather than replaced;
- connection-scoped WP8 DPAPI LocalMachine READ vault child with no `broker_trading` authority;
- PostgreSQL session/BrokerConnection/account-binding metadata without raw token/ciphertext storage;
- exact-head OWNER ACL/evidence finalization and an independent non-admin negative probe;
- local/private acceptance only: public registration, public multi-user activation and public Internet ingress remain OFF/LOCKED.

WP17 did not add a T-Invest TRADE credential, order/withdrawal API, broker write authority, WP18 real portfolio UI or Real execution activation. Protected `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged.

## Next required gate — deferred WP15 live broker READ acceptance

The accepted amendment states that WP18 Portfolio Dashboard may consume real broker data only after Web READ-token provisioning completes the deferred WP15 live evidence for the corresponding tenant/broker account.

Therefore the next permitted engineering activity after this status-only transition is accepted is to prepare and verify the **smallest dedicated live-acceptance support path** needed to collect sanitized, implementation-bound evidence from the already accepted WP17 Web flow. This is dependency-gate completion, not WP18 feature work.

Engineering must autonomously complete everything possible before asking the OWNER: source-controlled evidence contract/validator if needed, exact implementation binding, local launch/rehearsal path, synthetic negative tests, secret-redaction checks and CI. No synthetic evidence may be substituted for the required real OWNER broker observation.

Only at the final non-delegable point may the OWNER be asked to enter the real READ token in the authenticated local/private Web UI and verify the required masked/parity/freshness facts. The token itself must never be sent in chat, PowerShell command history, GitHub, CI logs or artifacts.

Until the live evidence passes and its own acceptance/status transition is merged and post-merge regression-verified:

- Block D credit remains withheld;
- WP18 real-data acceptance remains locked;
- WP18 feature work remains locked by this status;
- public multi-user remains OFF;
- public Internet ingress remains OFF;
- broker write / TRADE / Real authority remains unchanged.

## Permanent safety / rollback invariants

The following remain mandatory while V10 develops:

- deployment entrypoint: `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded by planning, Web or read-adapter work;
- no real broker/Telegram/VK tokens, encryption/recovery keys, private portfolio payload or full account IDs in GitHub, CI logs or artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped is not PASS; billing/infrastructure failure is distinct from code failure;
- every feature/acceptance package uses its own branch and PR;
- mandatory CI, exact-head review, zero unresolved blocking threads, squash merge and post-merge Regression Shield remain required before formal acceptance;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Complete this WP17 status-only acceptance through PR, exact-head required CI, squash merge and post-merge Regression Shield. Only after that exact status merge is GREEN may the dedicated deferred-WP15 live-acceptance support package be opened. WP18 remains locked.