# Omni-CIO Custom GPT — единая карта настройки и восстановления

Главная точка входа для единственного поддерживаемого бота:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Canonical GPT Editor semantics соответствуют **Instructions v8.6.1 Compact**, с полным engineering reference в v8.6.0.

## Архитектура

```text
GitHub (код + эталон конфигурации)
        │
        ├── Render Free → Omni-CIO Gateway (`app:app`)
        │             ├── TINVEST_TOKEN → production read-only
        │             ├── TINVEST_SANDBOX_TOKEN → optional Sandbox
        │             ├── TINVEST_TRADING_TOKEN → optional confirmed real execution
        │             └── HTTPS → Upstash Redis Free → durable real-order journal
        │
        └── вручную → GPT Editor
                      ├── Instructions v8.6.1 Compact
                      ├── 10 Knowledge files
                      └── Actions → production OpenAPI
```

GitHub не меняет GPT Editor, Render Environment или Upstash автоматически.

## Каноническая конфигурация

- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Sandbox history: `v8.5.0`.
- Read-only fallback/history: `v8.4.1`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- Render instance: **Free**.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Entrypoint: `app:app`.
- Default real durable backend: `upstash`.

## 1. Instructions

В GPT Editor использовать целиком только:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Полный `CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` остаётся инженерным reference. Не смешивать версии.

Ключевая модель безопасности:

- read-only, Sandbox и Real — отдельные contours;
- real proposal и real submit всегда разные user turns;
- submit требует exact short-lived phrase;
- `submitted` не считается `filled` без broker proof;
- ambiguous submit никогда не повторяется автоматически;
- durable journal failure blocks execution;
- `REAL_TRADING_ENABLED=false` — master rollback.

## 2. Knowledge — ровно 10 файлов

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

Не загружать broker reports, source code, account IDs или secrets в Knowledge.

## 3. Actions

GPT Editor → существующий Omni-CIO Action → импорт schema:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: `API Key`;
- Mode: `Bearer`;
- Value: существующий `GATEWAY_API_KEY` из Render.

### Default safe state

`REAL_TRADING_ENABLED=false` → Real Trading Actions отсутствуют.

`SANDBOX_TRADING_ENABLED=false` → Sandbox Actions отсутствуют; остаются 14 baseline GET Actions.

### Sandbox enabled

`SANDBOX_TRADING_ENABLED=true` добавляет 8 virtual-only Sandbox Actions.

### Real enabled

Valid real readiness требует:

- отдельный `TINVEST_TRADING_TOKEN`;
- valid per-order/daily limits;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- valid Upstash REST URL/token;
- durable-journal integrity.

При полной готовности добавляются только:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

No real cancellation/replace/transfer/withdraw/margin/MARKET execution in first release.

## 4. Render Free secrets/config

Никогда не вводить T-Invest или Upstash tokens в GPT Editor.

Always:

- `TINVEST_TOKEN` — existing production read-only;
- `GATEWAY_API_KEY`;
- `SSL_TBANK_VERIFY=True`.

Sandbox optional:

- `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true|false`;
- `SANDBOX_CONFIRMATION_TTL_SECONDS=120`.

Real execution:

- `TINVEST_TRADING_TOKEN` — отдельный account-scoped full-access trading token **без transfer access**;
- `REAL_TRADING_ENABLED=true|false`;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `REAL_TRADING_MAX_ORDER_RUB=1000`;
- `REAL_TRADING_MAX_DAILY_RUB=2000`;
- `REAL_TRADING_CONFIRMATION_TTL_SECONDS=120`;
- `REAL_TRADING_MARKET_MAX_AGE_SECONDS=15`.

Render Persistent Disk не нужен.

## 5. GPT Editor capabilities

- Recommended model: `Thinking 5.6`.
- Web Search: ON.
- Data Analysis / Code Interpreter: ON.
- Image generation: OFF для investment workflow.
- Apps: не использовать вместе с Actions.
- Actions: ON.

## 6. Read-only portfolio routing

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` обязательный старт:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → анализ`

Portfolio-management команда не является разрешением на реальную сделку.

Exact-action запросы изолированы.

## 7. Sandbox acceptance

Owner Preview acceptance 2026-08-02 подтвердил:

- `real_money=false`;
- account/funding/portfolio;
- BUY/SELL proposal + exact confirmation;
- wrong/expired phrase rejection;
- replay protection;
- own-position rejection;
- LIMIT state/cancel;
- portfolio reconciliation.

## 8. Real-money owner acceptance

Owner Phase 3 completed on 2026-08-03 with **zero real submit**.

Verified:

1. permanent Upstash Redis Free configured;
2. separate account-scoped trading token configured;
3. real status ready + masked account + `journal_backend=upstash` + `journal_integrity=ok`;
4. GPT v8.6.1 Compact applied and saved;
5. production OpenAPI refreshed and four real Actions visible;
6. technical proposal created without submit;
7. wrong confirmation rejected;
8. expired confirmation rejected;
9. own-funds guard rejected excessive BUY without margin fallback;
10. read-only exact-action isolation remained intact;
11. Render rollback `REAL_TRADING_ENABLED=false` produced healthy `/health` with `trading_methods=false`;
12. re-enable recovered `status=ready`, `execution_ready=true`, journal integrity ok and durable proposal rows.

Hard-cap, stale-market, SELL-over-position, replay and ambiguous-submit safety remain covered by merged regression tests.

## 9. ONLY remaining release gate — Phase 4

One first controlled real order requires a **new explicit owner instruction at execution time**.

Required sequence:

1. highly liquid supported cash share/ETF, normally 1 lot, preliminary total < 1000 RUB;
2. LIMIT only, fresh market, exact identity, own-funds/own-position preflight;
3. `prepareRealTrade` shows REAL MONEY proposal + exact phrase and stops;
4. owner sends exact phrase in a new user turn;
5. `executeRealTrade` submits once;
6. immediate `getRealOrderState`;
7. broker-confirmed fill/partial fill only;
8. reconcile real portfolio/cash/operations;
9. replay same confirmation once to prove no second submit;
10. ambiguity → never resubmit, reconcile only.

Full procedure: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## 10. Источники истины

- Runtime/API: deployed commit from GitHub `main`.
- GPT registry: `gpt/CONFIGURATION.md`.
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Secrets/Render: `gpt/SECRETS_AND_RENDER.md`.
- Durable journal: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.
- Real release: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.
- Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- Development rules: `AGENTS.md`.

Не восстанавливать конфигурацию из старых чатов/скриншотов, если они расходятся с `main`.