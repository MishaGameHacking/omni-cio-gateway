# Omni-CIO Custom GPT — единая карта настройки и восстановления

Главная точка входа для единственного поддерживаемого бота:

`Omni-CIO API | Управляющий и аналитик v8.4`

UI-name меняется владельцем вручную. Канонические backend/config semantics теперь соответствуют **Instructions v8.6.0**.

## Архитектура

```text
GitHub (код + эталон конфигурации)
        │
        ├── Render → Omni-CIO Gateway (`app:app`)
        │             ├── TINVEST_TOKEN → production read-only
        │             ├── TINVEST_SANDBOX_TOKEN → optional Sandbox
        │             └── TINVEST_TRADING_TOKEN → optional confirmed real execution
        │
        └── вручную → GPT Editor
                      ├── Instructions v8.6.0
                      ├── 10 Knowledge files
                      └── Actions → production OpenAPI
```

GitHub не меняет GPT Editor автоматически. Instructions, Knowledge, OpenAPI import и Bearer key применяются владельцем вручную.

## Каноническая конфигурация

- GPT Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Sandbox fallback/history: `v8.5.0`.
- Read-only fallback/history: `v8.4.1`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Entrypoint: `app:app`.

## 1. Instructions

В GPT Editor использовать целиком только:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Не смешивать версии.

Ключевая модель безопасности v8.6:

- production broker facts остаются отдельным read-only contour;
- Sandbox — только виртуальные деньги;
- real BUY/SELL возможен только через опубликованный Real Trading surface;
- real proposal и real submit всегда разные user turns;
- submit требует exact short-lived phrase;
- `submitted` не считается `filled` без broker fill state;
- ambiguous submit никогда не повторяется автоматически.

## 2. Knowledge — ровно 10 файлов

Загрузить по одному экземпляру каждого файла из `gpt/knowledge/`:

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

Полный условный Action surface: `gpt/ACTIONS_CATALOG.md`.

### Default safe state

`REAL_TRADING_ENABLED=false` означает отсутствие Real Trading Actions в OpenAPI.

При `SANDBOX_TRADING_ENABLED=false` также отсутствуют Sandbox Actions; остаются 14 baseline GET Actions.

### Sandbox enabled

`SANDBOX_TRADING_ENABLED=true` добавляет 8 изолированных Sandbox Actions.

### Real enabled

`REAL_TRADING_ENABLED=true` сам по себе недостаточен. Gateway также требует:

- отдельный `TINVEST_TRADING_TOKEN`;
- valid per-order/daily limits;
- durable journal на `/var/data`;
- успешную journal integrity initialization.

Если static readiness не выполнен, публикуется только `getRealTradingStatus`; real mutation routes не публикуются.

При полной готовности добавляются только:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

`cancelRealOrder`, replace, transfer, withdrawal, margin, MARKET execution в first real release отсутствуют.

## 4. Render secrets/config

Никогда не вводить T-Invest tokens в GPT Editor.

### Всегда

- `TINVEST_TOKEN` — existing production read-only;
- `GATEWAY_API_KEY`;
- `SSL_TBANK_VERIFY=True`.

### Sandbox optional

- `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true|false`;
- `SANDBOX_CONFIRMATION_TTL_SECONDS=120`.

### Real execution optional

- `TINVEST_TRADING_TOKEN` — отдельный account-scoped full-access trading token **без transfer access**;
- `REAL_TRADING_ENABLED=true|false`;
- `REAL_TRADING_MAX_ORDER_RUB`;
- `REAL_TRADING_MAX_DAILY_RUB`;
- optional `REAL_TRADING_CONFIRMATION_TTL_SECONDS`;
- optional `REAL_TRADING_MARKET_MAX_AGE_SECONDS`.

Persistent disk должен быть смонтирован в существующий Render service по `/var/data` до real enable.

Подробности: `gpt/SECRETS_AND_RENDER.md` и `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## 5. Capabilities в GPT Editor

- Recommended model: `Thinking 5.6`.
- Web Search: ON.
- Data Analysis / Code Interpreter: ON.
- Image generation: OFF для investment workflow.
- Apps: не использовать вместе с Actions.
- Actions: ON.

## 6. Read-only Preview smoke

В новом Preview-чате:

1. `Проверь шлюз. Вызови только gatewayHealth. Другие методы не вызывай.`
2. `Проверь подключение к брокеру.`
3. `Сколько у меня сейчас денег?`
4. `Что у меня сейчас в портфеле?`
5. `Какие операции были за последние 90 дней?`
6. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Для пункта 6 обязательный старт:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → анализ`

Проверить masked account, MSK и отсутствие stale sizing.

## 7. Sandbox acceptance

Когда Sandbox включён:

- `getSandboxTradingStatus` → `sandbox=true`, `real_money=false`;
- proposal не submit-ит;
- execute требует exact phrase из нового user turn;
- wrong/expired phrase fail closed;
- duplicate confirmation не создаёт вторую заявку;
- после submit `getSandboxOrderState`;
- cancellation только Sandbox + отдельное confirmation.

Полный runbook: `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## 8. Real-money staged acceptance

Первый real enable выполняется строго по:

`docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`

До реальной заявки обязательно пройти Phase 3 без submit:

1. отдельный account-scoped trading token;
2. persistent disk `/var/data`;
3. маленькие hard limits;
4. controlled real enable;
5. `getRealTradingStatus` ready + masked account;
6. wrong phrase rejection;
7. expiry rejection;
8. hard-limit rejection;
9. stale/unsupported market rejection;
10. SELL beyond owned position rejection;
11. rollback drill: `REAL_TRADING_ENABLED=false` removes real Actions;
12. read-only and Sandbox regression smoke.

Первая настоящая сделка — только после нового явного разрешения владельца в Phase 4, minimum practical size, LIMIT only, submit once, immediate `getRealOrderState`, then real portfolio reconciliation.

## 9. Источники истины

- Runtime/API: deployed commit from GitHub `main`.
- GPT registry: `gpt/CONFIGURATION.md`.
- Canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Secrets/Render: `gpt/SECRETS_AND_RENDER.md`.
- Real release: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.
- Current engineering status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- Development rules: `AGENTS.md`.

Не восстанавливать конфигурацию из старых чатов/скриншотов, если они расходятся с `main`.