# Omni-CIO Custom GPT — единая карта настройки и восстановления

Главная точка восстановления текущего production-бота:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Current GPT Editor semantics: **Instructions v8.6.1 Compact**.  
Full engineering reference: v8.6.0.

## Важно: v9 ещё не production-конфигурация GPT

Active owner-approved development program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Until that program reaches its complete Definition of Done and owner acceptance, **recover/apply v8.6.1**, not unfinished v9 behavior.

## Архитектура current production

```text
GitHub (код + эталон конфигурации)
        │
        ├── Render Free → Omni-CIO Gateway (`app:app`)
        │             ├── TINVEST_TOKEN → production read-only
        │             ├── TINVEST_SANDBOX_TOKEN → optional Sandbox
        │             ├── TINVEST_TRADING_TOKEN → confirmed narrow real execution
        │             └── HTTPS → Upstash Redis Free → durable real-order journal
        │
        └── вручную → GPT Editor
                      ├── Instructions v8.6.1 Compact
                      ├── 10 Knowledge files
                      └── Actions → production OpenAPI
```

GitHub не меняет GPT Editor, Render Environment или Upstash автоматически.

## 1. Каноническая current production конфигурация

- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Render: Free.
- Entrypoint: `app:app`.
- Durable real journal: `upstash`.

Historical fallbacks:

- v8.5.0 — Sandbox-era;
- v8.4.1 — read-only-era.

Do not mix historical files with current production configuration.

## 2. Instructions

In GPT Editor use the complete contents of:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Do not paste full v8.6.0 into the current editor Instructions field when it exceeds editor limits; it remains engineering reference.

Key safety model:

- REAL READ-ONLY, SANDBOX and REAL EXECUTION are separate;
- real proposal and submit are separate user turns;
- exact short-lived confirmation is required;
- `submitted` != `filled` without broker proof;
- ambiguous submit is never automatically retried;
- durable journal failure blocks execution;
- `REAL_TRADING_ENABLED=false` is master rollback.

## 3. Knowledge — exactly 10 current files

1. `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
2. `04_CIO_PORTFOLIO_MANAGER.txt`
3. `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
4. `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
5. `07_PERSONAL_STRATEGY.txt`
6. `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
7. `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
8. `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
9. `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
10. `13_COMMUNICATION_STYLE_2026.txt`

Do not upload broker reports, source code, account IDs or secrets into Knowledge.

## 4. Actions

GPT Editor → existing Omni-CIO Action → import schema:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: API Key;
- Mode: Bearer;
- Value: current `GATEWAY_API_KEY` from Render.

### Kill-switch state

`REAL_TRADING_ENABLED=false` → Real Trading mutation surface is absent.

`SANDBOX_TRADING_ENABLED=false` → Sandbox mutation surface is absent.

### Real readiness

Requires:

- separate `TINVEST_TRADING_TOKEN`;
- valid server caps;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- valid Upstash REST URL/token;
- durable-journal integrity.

Current real Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

## 5. Render Free environment boundary

Never put T-Invest/Upstash tokens in GPT Editor.

Always/current:

- `TINVEST_TOKEN` — production read-only;
- `GATEWAY_API_KEY`;
- `SSL_TBANK_VERIFY=True`.

Optional Sandbox:

- `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true|false`;
- `SANDBOX_CONFIRMATION_TTL_SECONDS=120`.

Real execution current settings:

- `TINVEST_TRADING_TOKEN` — account-scoped trading token without transfer access;
- `REAL_TRADING_ENABLED=true|false`;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `REAL_TRADING_MAX_ORDER_RUB=1000` — initial accepted safety cap;
- `REAL_TRADING_MAX_DAILY_RUB=2000` — initial accepted safety cap;
- `REAL_TRADING_CONFIRMATION_TTL_SECONDS=120`;
- `REAL_TRADING_MARKET_MAX_AGE_SECONDS=15`.

These initial caps are not the v9 capital-scaling policy; raising them is a later controlled release task.

## 6. GPT Editor capabilities current production

- Recommended model: Thinking 5.6.
- Web Search: ON.
- Data Analysis / Code Interpreter: ON.
- Image generation: OFF for investment workflow.
- Actions: ON.

## 7. Current portfolio-management routing

v8.6.1 `УПРАВЛЯЙ ПОРТФЕЛЕМ` starts:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

This is not real-trade authorization.

v9 is explicitly intended to make this interaction natural-language driven so users do not need Action names or UIDs, while retaining write-authority separation.

## 8. Acceptance state

### Sandbox — COMPLETE

Owner Preview 2026-08-02 validated virtual account/funding/portfolio, BUY/SELL, wrong/expired confirmation rejection, replay protection, own-position rejection, LIMIT state/cancel and portfolio reconciliation with `real_money=false`.

### Real v8.6.1 — COMPLETE

Owner Phase 3 validated negative controls, dedicated trading credential, durable Upstash journal, kill-switch rollback and recovery.

Owner Phase 4 validated the first controlled real order:

- SBER 1-lot real LIMIT BUY;
- one broker submit;
- broker `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot at 280.55 RUB;
- commission 0.84 RUB;
- portfolio/operations reconciliation;
- replay created no second submit.

**v8.6.1 real BUY/SELL v1 is fully released and owner-accepted.**

## 9. Active v9 development

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Engineering research:

`docs/architecture/V9_RESEARCH_AND_ENGINEERING_PRINCIPLES.md`

Current work package and progress:

`knowledge/16_CURRENT_PROGRAM_STATUS.md`

Do not apply unfinished v9 Instructions/Knowledge/OpenAPI to the current production GPT.

## 10. Sources of truth

- Runtime/API: deployed GitHub `main` commit.
- Active roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- GPT registry: `gpt/CONFIGURATION.md`.
- Current GPT Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Secrets/Render: `gpt/SECRETS_AND_RENDER.md`.
- Durable journal: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.
- Development rules: `AGENTS.md`.

Do not restore configuration from old chats/screenshots when they conflict with `main`.
