# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-04

Этот файл хранит короткую долговременную память **одного проекта**: одного Custom GPT Omni-CIO и одного production Gateway для T-Invest.

## 1. Product identity

Repository target configuration:

`Omni-CIO API | Управляющий и аналитик v9.0.0`

Target GPT Editor payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Target Knowledge source:

`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`

Applied external GPT remains **v8.6.1** until the WP15 repository release is merged and owner Preview + `Update` acceptance is completed and recorded. Protected rollback Instructions remain:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Never create a second GPT to apply v9.

## 2. Runtime architecture

```text
EXISTING Omni-CIO GPT
        │
        ▼
Omni-CIO Gateway (`app:app`, Render Free)
        ├─ production read-only broker contour
        ├─ optional T-Invest Sandbox contour
        ├─ exact-owner-confirmed Real execution contour
        ├─ Upstash durable state
        └─ hidden signed Watchtower/QStash routes
```

GitHub stores code plus canonical target/recovery configuration. Render runs the Gateway. GPT Editor holds the actually applied Instructions/Knowledge/Action authentication and is not synchronized automatically by GitHub.

## 3. Protected v8.6.1 baseline

Protected release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

Owner-accepted real BUY/SELL v1 remains **100% complete**.

Canonical recovery invariant: **idempotent replay verified with no second submit**.

Accepted real lifecycle remains:

`fresh facts → prepare immutable proposal → exact owner confirmation in a NEW turn → one idempotent broker submit → broker reconciliation → confirmed fill only with broker proof`.

The first controlled real SBER acceptance and portfolio/operations reconciliation remain historical release evidence; WP15 does not require repeating a real-money order merely to update GPT configuration.

## 4. v9 program

Canonical owner-approved / program-locked roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Tracking epic: #176.

WP0–WP14 are complete. WP15 Custom GPT v9 Configuration & Recovery is the final active package until repository delivery and owner external Preview/Update acceptance are complete.

Exact current state: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 5. v9 implemented capability stack

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

Current reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Sandbox operations remain virtual-only and separately enabled.

Watchtower scheduler/callback routes remain hidden from GPT OpenAPI.

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

Critical constraints and calculations belong in deterministic code/server contracts where implemented; GPT reasoning never overrides server enforcement.

## 9. WP15 target configuration

Canonical target sources:

- `gpt/SETUP_INDEX.md` — upgrade/recovery entry;
- `gpt/CONFIGURATION.md` — target registry;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` — target Instructions;
- `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` — exact Knowledge set;
- `gpt/ACTIONS_CATALOG.md` — reviewed Action catalog;
- `gpt/SECRETS_AND_RENDER.md` — external role/env-name boundary;
- `gpt/MY_GPT_SETUP_RUNBOOK.md` — Preview/Update/rollback procedure;
- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md` — WP15 architecture;
- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_THREAT_MODEL.md` — WP15 threats.

Target editor policy:

- Actions ON;
- Apps OFF while custom Actions are used;
- Web Search for public context;
- Data Analysis when supported;
- choose a currently available non-Pro model that supports Custom GPT Actions and verify it in Preview;
- user-facing timezone `Europe/Moscow` / MSK.

## 10. External owner boundary

GitHub cannot press `Update` in GPT Editor, upload Knowledge to the external GPT or supply external secret values.

After the WP15 repository PR passes exact-head CI/security and is squash-merged, the owner must update the **existing** GPT in ChatGPT web using `gpt/MY_GPT_SETUP_RUNBOOK.md`, complete Preview acceptance/restoration demonstration and then select `Update`.

Until that evidence is recorded:

- repository target = v9.0.0;
- applied external GPT = v8.6.1.

Do not conflate these states.

## 11. Secrets / external roles

Canonical role/env-name source: `gpt/SECRETS_AND_RENDER.md`.

External roles include read-only broker, Sandbox broker, separate real-execution broker, Gateway bearer, Upstash durable-state and Watchtower/QStash credentials. Values remain outside GitHub/chat/Knowledge.

## 12. Runtime compatibility warning

Current `app.py` still depends on compatibility/runtime wrapper files including `app_v371.py` and `app_v360.py`. Do not delete them merely because they look legacy; a compatibility refactor requires its own regression evidence.

## 13. Git workflow

Significant changes:

`branch → PR → exact-head Regression Shield/security → zero unresolved review threads → squash merge → external owner acceptance when required`.

Never report an external acceptance step as complete merely because repository CI is green.

## 14. Current readiness

- production read-only: accepted;
- Sandbox: accepted/conditional;
- real BUY/SELL v1: accepted and protected;
- WP0–WP14: complete;
- WP15 repository target: in progress;
- external applied GPT: v8.6.1 until owner Preview/Update evidence.
