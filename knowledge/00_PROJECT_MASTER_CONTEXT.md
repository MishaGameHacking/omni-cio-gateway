# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-05

Этот файл хранит короткую долговременную память **одного проекта**: текущего Custom GPT Omni-CIO / production Gateway V9 и последовательно развиваемой автономной платформы V10.

## 1. Product identity

Applied and repository-aligned production configuration:

`Omni-CIO API | Управляющий и аналитик v9.0.0`

Applied GPT Editor payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Applied Knowledge source:

`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`

Owner acceptance for the existing GPT completed on 2026-08-05. Issues #176 and #216 are closed completed.

Protected rollback Instructions remain:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Never create a second GPT to recover or maintain v9.

## 2. Runtime architecture

```text
EXISTING Omni-CIO GPT v9.0.0
        │
        ▼
Omni-CIO Gateway (`app:app`, Render)
        ├─ production read-only broker contour
        ├─ optional T-Invest Sandbox contour
        ├─ exact-owner-confirmed Real execution contour
        ├─ Upstash durable state
        └─ hidden signed Watchtower/QStash routes
```

GitHub stores code plus canonical applied/recovery configuration. Render runs the Gateway. GPT Editor holds the applied Instructions/Knowledge/Action authentication and is not synchronized automatically by GitHub.

This remains the accepted runtime while V10 is developed. V10 does not silently replace any V9 runtime boundary before the relevant V10 work package passes its Exit Gate.

## 3. Protected v8.6.1 rollback baseline

Protected release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

Owner-accepted real BUY/SELL v1 remains **100% complete**.

Canonical recovery invariant: **idempotent replay verified with no second submit**.

Accepted real lifecycle remains:

`fresh facts → prepare immutable proposal → exact owner confirmation in a NEW turn → one idempotent broker submit → broker reconciliation → confirmed fill only with broker proof`.

The protected baseline is rollback evidence, not the currently applied GPT version.

## 4. v9 program

Canonical owner-approved / program-locked roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Tracking epic #176 is complete. WP0–WP15 repository delivery and owner external acceptance are complete.

Exact current V9 runtime state: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 5. v9 capability stack

The repository contains reviewed deterministic components for:

- natural-language CIO routing;
- Investment Policy Statement/readiness;
- market universe;
- candidate funnel;
- research/evidence;
- credit/rating/default;
- Fund X-Ray;
- portfolio risk 2.0;
- meta-strategy selection;
- optimizer/capital scaling;
- immutable portfolio plans;
- safe plan execution over the protected real-order primitive;
- read-only Portfolio Watchtower;
- append-only decision journal/evaluation/replay.

These internal engines are **not automatically GPT Actions**. The GPT may call only operationIds present in the effective production `/openapi.json`, and it must not claim an internal engine ran without returned Action/evidence.

## 6. Production Action contours

Gateway/OpenAPI:

- `https://omni-cio-gateway.onrender.com`;
- `https://omni-cio-gateway.onrender.com/openapi.json`;
- stable entrypoint `app:app`.

Baseline portfolio-management read-only routing:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Sandbox operations remain virtual-only and separately enabled. Watchtower scheduler/callback routes remain hidden from GPT OpenAPI.

Owner post-update smoke confirmed exact `gatewayHealth` isolation, portfolio/cash/analytics routing, advisory SBER behavior without proposal/submit, honest Watchtower/journal explanation, and real-readiness isolation to `getRealTradingStatus` with no prepare/execute.

## 7. Absolute execution boundary

Always preserve:

- production read-only broker credential is never a real-execution fallback;
- Sandbox and Real remain isolated;
- no real submit merely from advisory/portfolio-management wording;
- real execution requires server readiness, supported instrument/order rules, fresh market, own-funds BUY or own-position SELL, hard caps and immutable proposal/plan context;
- exact owner phrase arrives in a new message before execute;
- at most one submit per request/proposal identity;
- ambiguous possible-submit → no automatic retry, reconciliation only;
- submitted != filled without broker proof;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, stop/replace/async, token management or autonomous recurring real-money execution under the current reviewed surface;
- account identity user-facing only masked;
- secret values/private broker payloads never enter GitHub, GPT Knowledge or public responses.

Master real rollback: `REAL_TRADING_ENABLED=false`.

Watchtower rollback: `WATCHTOWER_ENABLED=false`.

## 8. Decision discipline

For personal recommendations:

- facts/calculations/assumptions/recommendation stay distinct;
- freshness/completeness/identity are checked before strong conclusions;
- owner IPS/policy constraints precede personal sizing;
- define structural portfolio gap before choosing tickers;
- compare alternatives on one scale and include `NO_ACTION`;
- hard blockers cannot be averaged away;
- free cash is not by itself a reason to buy;
- concentration, liquidity, credit/default, currency, fund look-through/overlap and data quality matter when applicable;
- stale market cannot be presented as exact executable sizing;
- clean bond price and accrued interest remain distinct.

Critical constraints and calculations belong in deterministic code/server contracts where implemented; GPT/AI reasoning never overrides server enforcement.

## 9. Applied GPT configuration / recovery

Canonical sources:

- `gpt/SETUP_INDEX.md` — setup/recovery entry;
- `gpt/CONFIGURATION.md` — applied registry;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` — applied Instructions;
- `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` — exact Knowledge set;
- `gpt/ACTIONS_CATALOG.md` — reviewed Action catalog;
- `gpt/SECRETS_AND_RENDER.md` — external role/env-name boundary;
- `gpt/MY_GPT_SETUP_RUNBOOK.md` — Preview/Update/rollback procedure;
- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md` — WP15 architecture;
- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_THREAT_MODEL.md` — WP15 threats.

Editor policy:

- Actions ON;
- Apps OFF while custom Actions are used;
- Web Search for public context;
- Data Analysis when supported;
- use a currently available non-Pro model that supports Custom GPT Actions;
- user-facing timezone `Europe/Moscow` / MSK.

## 10. External owner boundary

GitHub cannot press `Update` in GPT Editor or supply external secret values. The v9 external application and acceptance were completed by the owner and recorded in #216.

Future configuration changes still require the same rule: repository review first, then owner-controlled Preview/Update on the **same** GPT when external state changes are required.

V10 does not decommission the current Custom GPT until the explicit V10 parity/decommission gate passes and the owner accepts that transition.

## 11. Secrets / external roles

Canonical role/env-name source: `gpt/SECRETS_AND_RENDER.md`.

External roles include read-only broker, Sandbox broker, separate real-execution broker, Gateway bearer, Upstash durable-state and Watchtower/QStash credentials. Values remain outside GitHub/chat/Knowledge.

Future V10 Telegram, local AI/runtime and encryption secret values also remain outside GitHub and outside ordinary developer access.

## 12. Runtime compatibility warning

Current `app.py` still depends on compatibility/runtime wrapper files including `app_v371.py` and `app_v360.py`. Do not delete them merely because they look legacy; a compatibility refactor requires its own regression evidence.

## 13. Git / maintenance workflow

Significant changes:

`branch → PR → exact-head Regression Shield/security → zero unresolved review threads → squash merge → external owner acceptance when required`.

Dependency updates are proposals, not automatic authorization. Generated hash locks remain derived from their `.in` sources and are verified by CI. Known-incompatible tooling is held narrowly rather than weakening the gate.

During V10, begin the next work package only after the current WP Exit Gate is accepted on `main`.

## 14. Current V9 readiness

- applied Custom GPT: **v9.0.0 owner-accepted**;
- production read-only: accepted;
- Sandbox: accepted/conditional;
- real BUY/SELL v1: accepted and protected;
- WP0–WP15: complete;
- repository/runtime mode: controlled maintenance while V10 is built;
- protected v8.6.1 rollback: retained and recoverable.

## 15. V10 active program

Canonical V10 program:

`docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`

Program Lock:

`docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`

Current progress authority:

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

Owner issued explicit **`START V10`** on 2026-08-05. Start evidence:

`docs/master-plan/OMNI_CIO_V10_START_RECORD.md`

Accepted WP0 architecture freeze sources:

- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_DATA_FLOW.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_RECOVERY_CONTRACT.md`;
- `docs/architecture/V10_ADR_PROCESS.md`;
- `docs/architecture/V10_V9_BASELINE_FREEZE.md`;
- ADR-019 in `docs/architecture/DECISIONS.md`.

WP1 repository architecture/boundary authority:

- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `.github/CODEOWNERS`;
- `scripts/check_v10_repository_boundaries.py`;
- `tests/test_v10_repository_boundaries.py`;
- permanent Regression Shield boundary step.

On accepted `main` after the focused WP1 acceptance merge:

- **WP0 / Block A = COMPLETE**;
- **WP1 = COMPLETE**;
- **V10 accepted progress remains 5%** until all of Block B is complete;
- next authorized package = **WP2 — Toolchain and Dependency Baseline**.

If this file is viewed in the unmerged WP1 PR, that handoff state is only the acceptance candidate and is not authoritative until final exact-head CI/security is green and the PR is squash-merged.

V10 target architecture is GitHub-controlled and account-independent: Lenovo is the first replaceable Personal runtime node; Web, Telegram and the future AI Copilot share one Core; AI has no direct broker-write authority; current GPT knowledge/configuration is migrated and retained until parity acceptance; Real execution remains deterministic, explicit-owner-confirmed, immutable, idempotent and reconciled.

The planned one-time Lenovo setup is deliberately later in Block C, after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts.
