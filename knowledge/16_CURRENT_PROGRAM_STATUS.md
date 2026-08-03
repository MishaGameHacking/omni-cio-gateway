# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

### Production baseline — COMPLETE

**Omni-CIO v8.6.1 real BUY/SELL v1 is owner-accepted and 100% complete.**

Accepted production facts:

- production read-only analytics: accepted;
- isolated T-Invest Sandbox execution: accepted;
- durable real journal: permanent Upstash Redis over HTTPS;
- Render remains Free;
- current GPT: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- current Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- owner Phase 3 negative acceptance + kill-switch rollback/recovery complete;
- owner Phase 4 first controlled real order complete;
- broker `FILL`, portfolio/operations reconciliation and replay/idempotency acceptance complete.

First accepted real lifecycle:

`prepare → exact owner confirmation → single submit → broker reconciliation → portfolio/operations reconciliation → safe replay`.

### Active development program — LOCKED

Owner approved **Omni-CIO v9 / Release 2 — Portfolio Autopilot & Capital Management Program**.

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Supporting research:

`docs/architecture/V9_RESEARCH_AND_ENGINEERING_PRINCIPLES.md`

Tracker:

GitHub issue **#175 — EPIC: Omni-CIO v9 Portfolio Autopilot / Capital Management Engine**.

Rule:

- continue from the earliest incomplete v9 work package;
- no competing roadmap until the v9 Definition of Done is complete;
- exceptions only for critical production/security/API compatibility and mandatory dependency/CI maintenance;
- v8.6.1 remains the protected fallback/recovery baseline.

## Current v9 work package

**WP0 — Baseline freeze and recovery correctness**

Progress on branch `feat/v9-portfolio-autopilot-program-lock`:

- [x] canonical v9 program exists on `main` and is owner-approved/program-locked;
- [x] GitHub epic #175 aligned to WP0–WP15;
- [x] external engineering research/principles documented;
- [x] `AGENTS.md` program-lock rules added on WP0 branch;
- [x] stale `knowledge/00_PROJECT_MASTER_CONTEXT.md` Phase-4-only status corrected on WP0 branch;
- [ ] stale `gpt/SETUP_INDEX.md` release-gate wording corrected;
- [ ] canonical config consistency CI check/tests added;
- [ ] repository-layout CI aligned with accepted v8.6.1 + v9 sources;
- [ ] exact-head Regression Shield green;
- [ ] WP0 PR reviewed and merged.

No v9 runtime behavior is enabled by WP0 documentation work.

## Canonical production configuration — v8.6.1 fallback

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: Thinking 5.6.
- Timezone: Europe/Moscow / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- Render: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 canonical files.

GitHub is canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash.

## Broker contours

### Production read-only

`TINVEST_TOKEN` remains read-only and separate from execution credentials.

Current v8.6.1 portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

v9 will evolve this into natural-language typed orchestration while preserving write-authority isolation.

### Sandbox

Uses only `TINVEST_SANDBOX_TOKEN`; virtual execution remains `real_money=false`.

### Real execution v1

Uses only separate account-scoped `TINVEST_TRADING_TOKEN` without transfer access.

Current conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Current v8.6.1 restrictions remain:

- BUY/SELL only;
- supported cash share/ETF;
- RUB;
- LIMIT / CURRENCY / DAY;
- own-funds BUY / own-position SELL;
- no margin/short;
- fresh trusted market;
- immutable proposal + exact short-lived owner confirmation;
- server hard caps;
- UUID idempotency;
- ambiguity = reconcile only;
- broker proof required for fill.

v9 roadmap text does not authorize new mutations by itself.

## Current safety state

- account output masked;
- durable Upstash journal remains required;
- initial accepted server caps remain unchanged during WP0;
- `REAL_TRADING_ENABLED=false` remains master rollback;
- production v8.6.1 stays available while v9 is built.

## v9 work-package checklist

- [ ] WP0 — Baseline freeze and recovery correctness
- [ ] WP1 — Natural Language CIO Router
- [ ] WP2 — Investment Policy Statement Engine
- [ ] WP3 — Market Universe Engine
- [ ] WP4 — Deterministic Candidate Funnel
- [ ] WP5 — Research & Evidence Engine
- [ ] WP6 — Credit, Rating & Default Engine 2.0
- [ ] WP7 — Fund X-Ray Engine
- [ ] WP8 — Portfolio Risk Engine 2.0
- [ ] WP9 — Meta-Strategy Selector
- [ ] WP10 — Portfolio Optimizer & Capital Scaling
- [ ] WP11 — Immutable Portfolio Plan Protocol
- [ ] WP12 — Safe Plan Execution Engine
- [ ] WP13 — Portfolio Watchtower
- [ ] WP14 — Decision Journal, Evaluation & Learning Loop
- [ ] WP15 — Custom GPT v9 Configuration & Recovery

**Current release:** v8.6.1 stable/accepted.  
**Active development:** v9, WP0.  
**Do not mark v9 complete until the canonical program Definition of Done is fully satisfied.**
