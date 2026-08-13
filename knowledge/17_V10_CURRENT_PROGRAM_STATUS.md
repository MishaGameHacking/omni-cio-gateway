# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-13

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16 COMPLETE / WP17 COMPLETE / WP18 COMPLETE / WP19 AUTHORIZED NEXT**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E is in progress: WP16, WP17 and WP18 are complete; WP19 — Watchtower / Incident UI — is the next authorized implementation package. Block E receives no percentage credit until its own Block Exit Gate.

WP18 was implemented in PR #303 and squash-merged to exact `main` `90c8b52c864db034d31d6184346b2ff62707c121`. The final reviewed PR head was `18ce03a3557b51255499fa22c2e1f5ac4be92cc2`. On that exact head the fresh `ready_for_review` cycle completed SUCCESS for the dedicated WP18 audit, WP15 Read/Live/Deferred regressions, WP16, WP17 and the authoritative Self-Hosted Windows merge gate. The authoritative gate included the protected Regression Shield, dependency audit, SAST, tracked-content secret scan and Windows smoke.

After squash merge, post-merge Regression Shield #1486 / run `31705088464` completed **SUCCESS** on exact `main` `90c8b52c864db034d31d6184346b2ff62707c121`. Both independent jobs passed: quality/contracts/coverage and dependency/code/secret security. The post-merge WP18 Portfolio Dashboard Audit #83 also completed SUCCESS on the same exact main.

The WP18 product surface is local/private and READ-only. It exposes source/timestamp/freshness/completeness for displayed portfolio data, keeps broker-reported valuation distinct from raw current-market quotations, preserves explicit incomplete/stale/unavailable states, uses exact instrument identity for reviewed issuer/sector enrichment, and does not add broker write/TRADE authority. Public Internet ingress and public multi-user activation remain locked.

The deferred WP15 real T-Invest READ acceptance remains accepted and unchanged. Broker provisioning remains connection-scoped through the authenticated local/private Web flow; raw broker credentials, full provider account IDs and private portfolio payloads remain outside GitHub/CI evidence.

OWNER action required now: **NO**. Engineering can proceed autonomously into WP19 until a later explicit OWNER/secret/physical gate is reached.

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
- Block D / WP15 — **COMPLETE (Block D accepted at 14%)**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **COMPLETE**;
- Block E / WP18 — **COMPLETE**;
- Block E / WP19 — **AUTHORIZED NEXT / NOT STARTED**;
- Block E / WP20+ — **LOCKED behind owning dependencies and Master Plan sequence**;
- public multi-user activation — **OFF / LOCKED**;
- public Internet ingress — **OFF / LOCKED until WP22A or later owning security gate**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

## Current next package — WP19 Watchtower / Incident UI

Master Plan objective: make every alert a verifiable incident object instead of a transient message.

Required WP19 deliverables remain exactly the Master Plan scope:

- incident timeline, severity, subject, evidence references, current state, risk impact and dedup/reopen status;
- visible lifecycle transitions and links to Decision/Plan where those owning contracts exist;
- filters for active/resolved/critical incidents.

Required WP19 tests:

- incident-state E2E coverage;
- duplicate/reopened scenario;
- missing-evidence display.

WP19 Exit Gate: **for every alert the OWNER can understand what happened, why, when, and what the system did after detection**.

WP19 depends on accepted WP18 and must reuse the existing source-controlled Web App, WP16 design system, WP17 application shell/session boundary and accepted Watchtower/Core incident contracts. WP19 does not authorize Telegram delivery, AI research, public ingress, broker write or Real execution.

## Canonical authority

Base program:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`.

Identity, broker provisioning and Web work are additionally governed by:

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `docs/operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`;
- `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`;
- `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`;
- `docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json`;
- `docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md`;
- `docs/architecture/V10_WP16_WEB_DESIGN_SYSTEM_CONTRACT.md`;
- `docs/architecture/ADR-0011-web-read-credential-provisioning.md`;
- `docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json`;
- `docs/operations/V10_WP17_APPLICATION_SHELL_RUNBOOK.md`;
- `docs/architecture/V10_WP18_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP18_PORTFOLIO_DASHBOARD_CONTRACT.md`.

GitHub remains engineering source of truth. Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | COMPLETE — WP11 / WP12 / WP13 / WP14 / WP15 incl. real READ evidence |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 / WP17 / WP18 COMPLETE; WP19 NEXT |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **40% ACCEPTED** |

The 40% total is intentional: Block E is not credited piecemeal.

## Accepted implementation evidence index

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 PR #248 / hardening #249 -> accepted Block B;
- WP5 PR #251; WP6 #253; WP7 #255; WP8 #257; WP9 #259; WP9A #261; WP10 rebuild #267 -> accepted Block C;
- WP11 clean rebuild #269; WP12 #271; WP13 #273; WP14 #275;
- WP15 primary PR #277 -> `f8862d1af88400189d3c0780d2029a87cb5427ca`;
- Identity / Multi-Tenant / Authentication amendment PR #278 -> `cbf6a7adba78fa56d23e90ce2cfe2952d21a5e5b`;
- WP16 PR #280 -> `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`;
- WP17 PR #282 -> `5b6b12f144c9bfa71307dcb28548a97527456b5b`;
- deferred WP15 live support PR #284 and acceptance hardening PRs #285/#286/#287/#290/#292/#293/#294/#295/#296/#297/#298/#299;
- V10 status/runbook sync PR #300 -> `0825e6c4625944d7b8e7dd796150fb1ae6707e6d`;
- WP15 live responsiveness/deadline correction PR #301 -> exact accepted implementation `a7ecad5f7e84e756d19fca2969a71c62fca744a2`;
- WP15 live acceptance/status transition PR #302 -> accepted pre-WP18 `main` `8b6780dc2d0c6cb3f70577e6f24a5e8ca11def07`;
- WP18 PR #303 -> squash merge `90c8b52c864db034d31d6184346b2ff62707c121`;
- WP18 final reviewed head `18ce03a3557b51255499fa22c2e1f5ac4be92cc2`: fresh `ready_for_review` runs WP18 #82, WP15 Read #272, WP15 Live #200, WP15 Deferred #204, WP16 #324, WP17 #295 and Self-Hosted Windows CI #973 — **SUCCESS**;
- post-WP18 Regression Shield #1486 / run `31705088464` on exact `main` `90c8b52c864db034d31d6184346b2ff62707c121` — **SUCCESS**, including coverage, dependency audit, SAST and tracked-secret scan;
- post-WP18 dedicated Portfolio Dashboard Audit #83 — **SUCCESS** on the same exact main.

Hosted Fast PR Checks / Toolchain Compatibility runs that GitHub did not start because of the account billing/spending-limit condition remain infrastructure failures, not PASS and not code failures.

## WP18 closeout evidence

WP18 satisfies its Master Plan Exit Gate:

- displayed portfolio/cash/position/weight/concentration/current-market values expose or visibly inherit source and relevant timestamps;
- Decimal values are transported as strings and cross-currency aggregation is forbidden without an explicit reviewed conversion;
- broker-reported values remain distinct from raw market quotations and unsupported asset-specific conversion is not fabricated;
- empty, partial, stale and unavailable states remain explicit and are never silently converted to zero;
- broker connection state remains visible even when a safe account snapshot is unavailable;
- instrument classification is bound to exact stable UID/type-specific point reads, with identity conflicts failing closed and provenance timestamps captured after the corresponding metadata read/attempt;
- post-enrichment snapshot and market freshness are reevaluated before presentation;
- browser payload/source contains no broker token, secret reference, raw provider account ID or account fingerprint;
- review state before merge was clean and the full 19-file WP18 diff was reviewed;
- squash merge and exact-main post-merge Regression Shield both completed successfully.

This acceptance does not claim continuously streaming prices. WP18 v1 intentionally uses a bounded current-on-demand/manual refresh model with explicit timestamps and stale semantics.

## Permanent safety / rollback invariants

- deployment entrypoint remains `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded by Web/read work;
- no real broker/Telegram/VK tokens, encryption/recovery keys, private portfolio payload or full account IDs in GitHub, CI logs or artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped is not PASS; billing/infrastructure failure is distinct from code failure;
- feature work uses focused branch/PR, mandatory exact-head CI, zero blocking threads, squash merge and required post-merge Regression Shield;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Start **WP19 — Watchtower / Incident UI** only after this status-only transition itself passes exact-head required gates, is squash-merged, and the resulting exact `main` passes the required post-merge Regression Shield. WP19 must begin from that accepted main, use the mandatory WP execution template, preserve all safety boundaries above, remain inside the single source-controlled Web App, and leave public Internet ingress, public multi-user activation and broker write/Real execution locked for their owning later gates.
