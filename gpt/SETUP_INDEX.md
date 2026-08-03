# Omni-CIO Custom GPT — единая карта настройки и восстановления

Главная точка входа для единственного поддерживаемого бота:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Production baseline: **v8.6.1**.  
Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.  
Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.

Активная программа разработки второго большого релиза:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Статус программы: **OWNER-APPROVED / PROGRAM LOCKED**. До закрытия её Definition of Done не начинать конкурирующий roadmap, второго бота, второй Gateway или отдельный execution surface.

## Архитектура

```text
GitHub (код + эталон конфигурации)
        │
        ├── Render Free → Omni-CIO Gateway (`app:app`)
        │             ├── TINVEST_TOKEN → production read-only
        │             ├── TINVEST_SANDBOX_TOKEN → optional Sandbox
        │             ├── TINVEST_TRADING_TOKEN → confirmed real execution
        │             └── HTTPS → Upstash Redis Free → durable real-order journal
        │
        └── вручную → GPT Editor
                      ├── Instructions v8.6.1 Compact
                      ├── 10 Knowledge files
                      └── Actions → production OpenAPI
```

GitHub не меняет GPT Editor, Render Environment или Upstash автоматически.

## 1. Каноническая конфигурация

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Real durable backend: Upstash Redis over HTTPS.

Не смешивать compact Instructions с полным v8.6.0 reference.

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

Каждый файл загружать один раз. Secrets, accountId, private broker reports и source code в Knowledge не помещать.

## 3. Actions

GPT Editor → существующий Omni-CIO Action → импорт schema:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: `API Key`;
- Mode: `Bearer`;
- Value: существующий `GATEWAY_API_KEY` из Render.

### Baseline read-only

При выключенных execution flags остаются baseline GET Actions.

### Sandbox

`SANDBOX_TRADING_ENABLED=true` добавляет только изолированные virtual-only Sandbox Actions. Sandbox всегда `sandbox=true`, `real_money=false`.

### Real execution v1

Valid real readiness требует отдельный `TINVEST_TRADING_TOKEN`, валидные caps, durable Upstash journal и совпадение торгового/read-only счёта.

Публикуются только:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real v1 остаётся: BUY/SELL, supported cash share/ETF, RUB, LIMIT/CURRENCY/DAY, own funds/own position, no margin/short, immutable proposal, exact short-lived confirmation, UUID idempotency and broker reconciliation.

No transfer/withdraw, MARKET/BESTPRICE, derivatives/currency execution, stop orders, replace, async submit, autonomous recurring real execution or token management through GPT.

## 4. Render / secrets

Никогда не вводить T-Invest или Upstash tokens в GPT Editor.

Required names:

- `TINVEST_TOKEN` — production read-only;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer;
- `SSL_TBANK_VERIFY=True`.

Optional Sandbox:

- `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED`.

Real execution:

- `TINVEST_TRADING_TOKEN` — separate account-scoped full-access trading token without transfer access;
- `REAL_TRADING_ENABLED`;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `REAL_TRADING_MAX_ORDER_RUB`;
- `REAL_TRADING_MAX_DAILY_RUB`;
- `REAL_TRADING_CONFIRMATION_TTL_SECONDS`;
- `REAL_TRADING_MARKET_MAX_AGE_SECONDS`.

Secret values остаются только во внешних системах.

## 5. GPT Editor capabilities

- Recommended model: `Thinking 5.6`.
- Web Search: ON.
- Data Analysis / Code Interpreter: ON.
- Image generation: OFF для investment workflow.
- Apps: не использовать вместе с Actions.
- Actions: ON.

## 6. Portfolio routing

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` production v8.6.1 стартует:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → анализ`.

Portfolio-management запрос не является разрешением на реальную сделку. Exact-action запросы остаются изолированными.

В v9 этот UX расширяется Natural Language CIO Router, но текущий безопасный routing сохраняется до отдельного acceptance соответствующего work package.

## 7. Acceptance state v8.6.1

Real BUY/SELL v1 полностью owner-accepted 2026-08-03:

- readiness и durable Upstash journal подтверждены;
- wrong/expired confirmation fail closed;
- own-funds protection подтверждена;
- kill switch и recovery подтверждены;
- первая реальная LIMIT BUY SBER исполнена брокером;
- `getRealOrderState` подтвердил `EXECUTION_REPORT_STATUS_FILL`, 1/1 lot;
- portfolio/operations reconciled;
- replay exact confirmation не создал второго broker submit.

**Release state: v8.6.1 = 100% complete.**

Полный runbook: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## 8. v9 development boundary

Active program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Protected baseline/recovery contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Каждый v9 package: architecture → deterministic implementation → fake-client/unit/integration tests → security → exact-head Regression Shield → squash merge → feature-flag/shadow acceptance as required.

Production v8.6.1 не заменяется, пока новый пакет не прошёл свой exit gate.

## 9. Источники истины

- Runtime/API: deployed GitHub `main` commit.
- Program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- GPT registry: `gpt/CONFIGURATION.md`.
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Bot manifest: `gpt/BOT_ONLY_FILE_MANIFEST.md`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Secrets/Render: `gpt/SECRETS_AND_RENDER.md`.
- Real release: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.
- Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- Development rules: `AGENTS.md`.

Не восстанавливать конфигурацию из старых чатов/скриншотов, если они расходятся с `main`.
