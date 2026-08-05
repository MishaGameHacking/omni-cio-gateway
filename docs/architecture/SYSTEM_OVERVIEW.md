# Архитектура Omni-CIO

## 1. Поддерживаемая система

Репозиторий содержит один пользовательский продукт и один production runtime:

```text
Пользователь в ChatGPT
        ↓
Existing Custom GPT Omni-CIO v9.0.0
        ↓ Bearer GATEWAY_API_KEY
Omni-CIO Gateway (`app:app`) on Render
        ├─ read-only T-Invest contour
        ├─ optional virtual Sandbox contour
        ├─ exact-owner-confirmed Real execution contour
        ├─ durable state
        └─ hidden Watchtower/QStash routes
```

Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05. Protected rollback remains v8.6.1.

## 2. GitHub ↔ Render ↔ GPT Editor

GitHub:

- хранит backend code;
- хранит tests/CI;
- хранит эталон applied/recovery GPT configuration/Knowledge;
- хранит reviewed Action/recovery contracts;
- не хранит secret values.

Render:

- запускает production Gateway из `main` согласно deploy-настройке service;
- хранит broker/Gateway/durable-state/scheduler secrets как environment values;
- сохраняет стабильный entrypoint `app:app`.

GPT Editor:

- хранит фактически применённые Instructions/Knowledge/model/capabilities;
- хранит Bearer secret для Action;
- не синхронизируется с GitHub автоматически.

Custom GPT при обычной работе обращается к Render Gateway, а не к GitHub.

## 3. Gateway runtime

- `app.py` — production wrapper, release/OpenAPI surface, entrypoint `app:app`.
- `app_v371.py` — current runtime compatibility dependency.
- `app_v360.py` — current runtime compatibility dependency.
- `main.py` — base FastAPI/auth/read-only core dependency.
- `portfolio_market.py` — portfolio market snapshot.
- `portfolio_analytics.py` — structure/concentration analytics.
- `cash_liquidity.py` — cash/liquidity diagnostics.
- `purchase_capacity.py` / `purchase_capacity_integrity.py` — technical affordability.
- `operations_analytics.py` — operations/cash-flow analytics.
- `broker_report_reconciliation/` — official broker-report reconciliation and extension hook.
- `omni_cio/` — versioned v9 contracts and deterministic engines for routing, policy, universe, candidates, research, credit, funds, risk, strategy, optimization, plans, safe execution, Watchtower, journal/evaluation and release checks.

Wrappers/core нельзя удалять только из-за исторического имени: текущий `app.py` импортирует их. Их консолидация — отдельный compatibility refactor.

## 4. Custom GPT configuration

Applied configuration lives in `gpt/`:

- `SETUP_INDEX.md` — single setup/update/recovery entrypoint;
- `CONFIGURATION.md` — applied UI/capability registry;
- `CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` — applied Instructions;
- `KNOWLEDGE_MANIFEST_V9_0_0.md` — exact 10-file Knowledge registry;
- `knowledge/` — exactly 10 applied production Knowledge files;
- `ACTIONS_CATALOG.md` — reviewed baseline/Sandbox/Real Action authority;
- `SECRETS_AND_RENDER.md` — external secret/deployment boundary;
- `MY_GPT_SETUP_RUNBOOK.md` — Preview/Update/recovery procedure;
- `CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` — protected rollback Instructions.

The existing GPT was upgraded rather than duplicated. Acceptance evidence is recorded in completed #216/#176.

## 5. Production endpoints

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `/health`
- OpenAPI: `/openapi.json`
- API version: `3.10.0`
- Entrypoint: `app:app`

The effective deployed `/openapi.json` is the runtime GPT Action authority.

## 6. Security boundary

- production read-only broker credential remains read-only and never becomes a Real fallback;
- Sandbox remains virtual and separately credentialed;
- Real execution uses a separate credential and server readiness gates;
- real submit requires exact owner confirmation in a new turn plus immutable/idempotent server state;
- ambiguous possible-submit is reconciled, never automatically retried;
- submitted is not treated as filled without broker proof;
- transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async and autonomous recurring real execution remain outside the reviewed surface;
- account IDs stay masked in user-facing output;
- secrets remain in external secret storage, not GitHub/Knowledge;
- money uses exact decimal logic and currencies remain separate without verified FX.

Master real kill switch: `REAL_TRADING_ENABLED=false`.

Watchtower kill switch: `WATCHTOWER_ENABLED=false`.

## 7. Portfolio decision flow

For portfolio-management requests:

```text
getPortfolioSnapshot
        ↓ success
getCashLiquiditySnapshot
        ↓
getPortfolioAnalytics
        ↓
quality / structure / risk analysis
        ↓ if needed
instrument identity + fresh market checks
        ↓
recommendation / NO_ACTION / reviewed plan
```

A recommendation or portfolio-management prompt is not real-execution authorization. Web Search may add public context after broker facts but never replaces broker Actions.

## 8. Internal v9 engines versus Actions

Internal v9 modules are not automatically GPT Actions. The GPT may call only operationIds present in the effective imported production OpenAPI and may claim server execution only when returned Action/evidence proves it.

Reviewed Real operationIds are:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Sandbox operationIds remain explicitly virtual. Hidden Watchtower scheduler/callback routes are excluded from GPT OpenAPI.

## 9. Market/sizing boundary

- last price is not an executable guarantee;
- fresh market/trading status is required for current market-sensitive sizing;
- technical purchase capacity does not automatically equal personal sizing;
- free cash alone is not a reason to buy;
- `withdraw_limits` does not automatically equal buying budget;
- stale/incomplete/contradictory data blocks unjustified precision.

## 10. Deploy and CI

`render.yaml` is the production deployment contract:

```text
pip install --require-hashes -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Regression Shield verifies repository structure, locks, contracts, type/lint/format, tests/coverage, dependency audit, SAST and secret scanning.

A separate **Live Gateway Authority Acceptance** checks only public `/health` + `/openapi.json` against the reviewed v9 allowlist. It does not send credentials or call protected broker Actions.

Green repository CI does not itself prove GPT Editor state; applied-state claims require owner evidence. Current v9 owner acceptance is already complete.

## 11. Maintenance mode

WP0–WP15 is complete. Current work is controlled maintenance only:

- dependency PRs remain proposals until current-main exact-head Regression Shield/security succeeds;
- known-incompatible toolchain versions are held narrowly and documented;
- obsolete one-time bootstrap/generated artifacts are removed through reviewed cleanup PRs;
- no maintenance change may silently broaden broker or GPT authority.
