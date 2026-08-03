# Omni-CIO Custom GPT — единая карта настройки и восстановления

Главная точка входа для единственного поддерживаемого бота:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Текущий применённый production baseline: **v8.6.1**.  
Активная программа разработки второго релиза: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## Архитектура

```text
GitHub (код + каноническая конфигурация)
        │
        ├── Render Free → Omni-CIO Gateway (`app:app`)
        │             ├── TINVEST_TOKEN → production read-only
        │             ├── TINVEST_SANDBOX_TOKEN → optional Sandbox
        │             ├── TINVEST_TRADING_TOKEN → confirmed real execution
        │             └── HTTPS → Upstash Redis Free → durable real-order journal
        │
        └── вручную → GPT Editor
                      ├── Instructions v8.6.1 Compact
                      ├── ровно 10 Knowledge files
                      └── Actions → production OpenAPI
```

GitHub не применяет изменения в GPT Editor, Render Environment или Upstash автоматически.

## Каноническая production-конфигурация

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`, пока он поддерживает Actions.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Durable real journal: Upstash Redis over HTTPS REST.

## Production Knowledge — ровно 10 файлов

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

Каждый файл загружать один раз. Secrets, полный accountId, source code и приватные broker reports в Knowledge не загружать.

## Actions / authentication

В GPT Editor импортировать schema из:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: API Key;
- Mode: Bearer;
- Value: существующий `GATEWAY_API_KEY` из Render.

T-Invest и Upstash tokens никогда не вводятся в GPT Editor.

### Production read-only

`TINVEST_TOKEN` остаётся отдельным read-only credential и не заменяется trading token-ом.

### Sandbox

При `SANDBOX_TRADING_ENABLED=true` доступны только virtual Sandbox Actions с `sandbox=true`, `real_money=false`.

### Real execution v1

При valid `REAL_TRADING_ENABLED=true` + отдельном `TINVEST_TRADING_TOKEN` + исправном durable journal доступны только:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Защищённый lifecycle:

`fresh portfolio/market → immutable proposal → exact short-lived owner confirmation в новом сообщении → submit once → broker reconciliation → portfolio/operations reconciliation`.

Сохраняются запреты v8.6.1: no withdrawal/transfer, no margin/short, no MARKET/BESTPRICE, no derivatives execution, no automatic retry after ambiguous submit. `REAL_TRADING_ENABLED=false` остаётся master rollback.

## Owner acceptance v8.6.1 — COMPLETE

На 2026-08-03 подтверждены:

- read-only аналитический контур;
- Sandbox acceptance;
- separate trading token;
- Upstash durable journal + integrity;
- wrong/expired confirmation rejection;
- own-funds protection;
- kill-switch rollback/recovery;
- первая явно разрешённая real LIMIT BUY SBER;
- broker `FILL` reconciliation;
- real portfolio/operations reconciliation;
- replay/idempotency без второго submit.

**Real BUY/SELL v1 Definition of Done = 100% complete.**

Подробности: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` и `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Активная программа v9

Канонический roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Baseline/migration contract:

`docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`

Пока v9 Definition of Done не завершён, не начинать конкурирующий roadmap, второй бот, второй Gateway или дублирующий execution surface. Стабильный v8.6.1 сохраняется и расширяется только через staged/feature-flagged v9 work packages.

Текущий applied GPT остаётся v8.6.1 до WP15. Промежуточные backend-компоненты v9 не требуют ручного изменения GPT после каждого PR.

## Восстановление с нуля

1. Проверить `main`, `README.md`, `AGENTS.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
2. Прочитать этот файл и `gpt/CONFIGURATION.md`.
3. В GPT Editor применить `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
4. Загрузить ровно 10 Knowledge-файлов выше.
5. Выбрать рекомендованную модель/capabilities из `gpt/CONFIGURATION.md`.
6. Импортировать production OpenAPI URL.
7. Настроить API Key → Bearer с `GATEWAY_API_KEY`.
8. Render secrets восстанавливать только по `gpt/SECRETS_AND_RENDER.md`; значения secrets в GitHub не хранятся.
9. Проверить `/health`, read-only smoke и `getRealTradingStatus`, если real contour включён.
10. Провести Preview acceptance и нажать `Update`.

## Источники истины

- Runtime/API: GitHub `main` + deployed Render state.
- Active v9 roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- Migration rules: `docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`.
- GPT registry: `gpt/CONFIGURATION.md`.
- GPT Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Knowledge manifest: `gpt/BOT_ONLY_FILE_MANIFEST.md`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Secrets/Render: `gpt/SECRETS_AND_RENDER.md`.
- Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- Development rules: `AGENTS.md`.

Не восстанавливать конфигурацию из старых чатов или скриншотов, если они расходятся с `main`.
