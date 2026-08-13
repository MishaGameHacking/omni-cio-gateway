# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-13

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16 COMPLETE / WP17 COMPLETE / WP18 AUTHORIZED NEXT**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E is in progress: WP16 and WP17 are complete; WP18 — Portfolio Dashboard and Assets — is the next authorized implementation package. Block E receives no percentage credit until its own Block Exit Gate.

The deferred WP15 real T-Invest READ acceptance is now complete. OWNER performed the real local/private Web comparison on exact implementation `a7ecad5f7e84e756d19fca2969a71c62fca744a2`; the source-controlled finalizer produced sanitized `WP15_LIVE_WEB_READ_VERIFIED` evidence with all required parity/freshness confirmations true, READ_ONLY authority, no recorded secret/full account/private portfolio values, guarded runtime cleanup, `app:app`, `trading_methods=false` and `ready=true`.

Engineering then reran the independent non-admin `V10 WP15 Live Web OWNER Audit` on the same exact implementation. Run `31672850918`, latest attempt, completed **SUCCESS**. The independent audit reported `WP15_LIVE_WEB_READ_ACCEPTED`, `evidence_present=true`, implementation/script binding valid, forbidden private fields absent, runner non-admin, runtime role disabled, temporary task absent, runner secret/evidence write denied, real broker READ observation true, no secret/private portfolio values recorded, no broker write authority, `trading_methods=false`, `gateway_entrypoint=app:app`, `ready=true`. Sanitized artifact `wp15-live-owner-sanitized-audit` was uploaded with short retention.

The machine-readable transition is `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`: Block D credit is allowed and the WP18 real-data lock is removed. This transition does **not** enable public multi-user access, public Internet ingress, broker write/TRADE authority or Real execution.

OWNER action required now: **NO**. Engineering can proceed autonomously into WP18 until a later explicit OWNER/secret/physical gate is reached.

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
- Block E / WP18 — **AUTHORIZED NEXT / NOT STARTED**;
- Block E / WP19+ — **LOCKED behind owning dependencies and Master Plan sequence**;
- public multi-user activation — **OFF / LOCKED**;
- public Internet ingress — **OFF / LOCKED until WP22A or later owning security gate**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

## Current next package — WP18 Portfolio Dashboard and Assets

Master Plan objective: give the OWNER a transparent current view of capital without relying on GPT.

Required WP18 deliverables remain exactly the Master Plan scope:

- portfolio value, cash, positions, weights, currencies, issuers, sectors/classes and data timestamp;
- concentration/top positions, stale-data warnings and broker-connection state;
- position detail with instrument identity and linked incidents/research where those owning contracts already exist;
- explainable calculations and explicit broker/current-market distinction where applicable.

Required WP18 tests:

- golden portfolio UI fixtures;
- Decimal/currency correctness;
- empty portfolio;
- partial data;
- stale data.

WP18 Exit Gate: **every displayed number has a source/timestamp and the UI must not hide incomplete data**.

The OWNER-observed acceptance screen in WP15 is intentionally a short-lived one-shot parity challenge, not the production Portfolio Dashboard. It is therefore not expected to continuously update after the snapshot is rendered. For WP18, however, “current” valuation must be truthful: the implementation contract must define bounded refresh/current-market behavior and visible `as_of`/stale semantics so a changing portfolio value is never presented as silently live when it is actually an old snapshot. T-Invest streaming/polling integration may be used only after the WP18 architecture review selects the smallest safe approach; no broker-write authority is needed.

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

The WP15/WP17 identity and broker-provisioning sequence is additionally governed by:

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
- `docs/operations/V10_WP17_APPLICATION_SHELL_RUNBOOK.md`.

GitHub remains engineering source of truth. Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | COMPLETE — WP11 / WP12 / WP13 / WP14 / WP15 incl. real READ evidence |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 COMPLETE / WP17 COMPLETE / WP18 NEXT |
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
- WP15 live responsiveness/deadline correction PR #301 -> exact `main` `a7ecad5f7e84e756d19fca2969a71c62fca744a2`;
- post-merge Regression Shield #1484 / run `31672850860` — **SUCCESS**;
- post-merge WP15 Live Web Support Audit #114 / run `31672850933` — **SUCCESS**;
- post-merge WP16 Web Design System Audit #230 / run `31672850921` — **SUCCESS**;
- post-merge WP17 Application Shell Audit #201 / run `31672850866` — first attempt failed only at synthetic artifact transport after all test/recovery checks; same exact-main rerun completed **SUCCESS** without code changes;
- WP15 Live Web OWNER Audit #16 / run `31672850918` — initial attempt correctly reported OWNER action required before evidence; after real OWNER finalization, failed jobs were rerun on the same exact SHA and the complete independent audit finished **SUCCESS**, with sanitized artifact digest recorded by GitHub Actions.

Hosted Fast PR Checks / Toolchain Compatibility runs that GitHub did not start because of the account billing/spending-limit condition remain infrastructure failures, not PASS and not code failures.

## WP15 closeout evidence

WP15 READ implementation remains connection-scoped and fail-closed: `Tenant -> BrokerConnection -> READ credential -> verified broker-account bindings`, exact Decimal/UTC normalization, masked outward identity, market enrichment and bounded/resumable operations reads. No trading-token fallback, transfer/withdrawal, broker write or Real authority was added.

The real acceptance path used the accepted local/private WP17 `Settings -> Broker Connections` flow. Raw broker credential and raw portfolio/account identifiers never became GitHub evidence. OWNER finalization wrote only sanitized booleans/status/hash metadata, removed the temporary task/runtime, disabled the temporary runtime role and restored PostgreSQL authentication configuration. The subsequent independent non-admin runner audit proved that the runner could read the final sanitized evidence but could not mutate it or access the protected secret/private boundaries.

This satisfies the amended Block D acceptance requirement and removes the WP18 real-data dependency lock.

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

Start **WP18 — Portfolio Dashboard and Assets** only after this closeout/status transition itself passes exact-head required gates, is squash-merged, and the resulting exact `main` passes required post-merge Regression Shield. WP18 must begin from that accepted main, use the mandatory WP execution template, preserve all safety boundaries above, and remain local/private; public Internet ingress and public multi-user activation stay locked for their owning later gates.
