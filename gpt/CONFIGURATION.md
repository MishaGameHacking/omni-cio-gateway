# Custom GPT configuration registry — Omni-CIO

> Этот файл — реестр настроек. Не вставлять его целиком в поле Instructions.

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик v8.4`.
- Purpose: личный инвестиционный аналитик и клиент Omni-CIO Gateway.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- Current accepted GPT configuration release: `v8.4`.
- Current accepted production Instructions: `v8.4.1`.
- Sandbox acceptance Instructions candidate: `v8.5.0`.
- Backend/Gateway accepted baseline: `v3.10.0` до merge Sandbox release.
- Recommended model: `Thinking 5.6`.

## Current production description

> Личный GPT для T-Invest. Сам получает портфель, операции, ликвидность, параметры инструментов и котировки через Omni-CIO Gateway. Реальный брокерский контур работает только на чтение. В режиме «УПРАВЛЯЙ ПОРТФЕЛЕМ» анализирует структуру, сравнивает варианты и формирует план.

После Sandbox backend acceptance отдельная песочница может быть включена для виртуальных BUY/SELL с обязательным двухфазным подтверждением. Это не real-money trading.

## Conversation starters

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — сначала вызови getPortfolioSnapshot. Если успешно, вызови getCashLiquiditySnapshot и getPortfolioAnalytics. Затем проанализируй данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Первый starter намеренно содержит Action names для максимально надёжного dispatch. Простые естественные команды также должны маршрутизироваться автоматически по Instructions.

## Instructions

До Sandbox enable в поле `Instructions` остаётся 100% содержимого:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

После merge Sandbox backend, настройки отдельного Sandbox token в Render, включения Sandbox routes и успешного `getSandboxTradingStatus` для Sandbox acceptance заменить Instructions целиком на:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`

Не смешивать версии вручную. `v8.5.0` разрешает broker mutation только когда Action явно является Sandbox (`sandbox=true`, `real_money=false`); реальный контур остаётся read-only.

## Knowledge — ровно 10 файлов

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

Каждый файл загружать один раз. Не загружать исходный код, master plan, реальные broker reports, accountId или secrets.

## Capabilities

- Web Search: **ON**.
- Code Interpreter / Data Analysis: **ON**.
- Image generation: **OFF** для текущего investment workflow.
- Apps: **OFF / не использовать вместе с Actions**.
- Actions: **ON**.

## Actions

Production service:

`https://omni-cio-gateway.onrender.com`

Schema URL:

`https://omni-cio-gateway.onrender.com/openapi.json`

Health URL:

`https://omni-cio-gateway.onrender.com/health`

Authentication:

- Type: `API Key`.
- Mode: `Bearer`.
- Value: `GATEWAY_API_KEY` из Render service `omni-cio-gateway`.
- `TINVEST_TOKEN` и `TINVEST_SANDBOX_TOKEN` в GPT Editor не вставлять.

### Default real-money-safe surface

При `SANDBOX_TRADING_ENABLED=false`:

- ровно 14 GET Actions из `gpt/ACTIONS_CATALOG.md`;
- никаких real create/order/execute/cancel/replace/transfer/withdraw методов;
- `trading_methods=false`.

### Sandbox acceptance surface

При `SANDBOX_TRADING_ENABLED=true` дополнительно публикуются только Sandbox Actions:

- `getSandboxTradingStatus` — GET;
- `openSandboxAccount` — POST, consequential, explicit confirmation;
- `fundSandboxAccount` — POST, consequential, explicit confirmation;
- `getSandboxPortfolio` — GET;
- `prepareSandboxTrade` — POST, proposal only;
- `executeSandboxTrade` — POST, consequential, requires exact short-lived confirmation from a separate user turn;
- `getSandboxOrderState` — GET;
- `cancelSandboxOrder` — POST, consequential, explicit confirmation.

Все ответы Sandbox должны явно показывать `sandbox=true`, `real_money=false`, `real_trading_methods=false`.

## Portfolio dispatch acceptance

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` ожидаемый обязательный старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. только затем анализ, рынок/кандидаты при необходимости и DecisionCard.

Sandbox execution не включается автоматически обычным portfolio-management запросом.

## Sandbox confirmation acceptance

Нормальный виртуальный BUY/SELL:

1. `prepareSandboxTrade` возвращает proposal и exact confirmation phrase.
2. GPT показывает параметры, rationale, TTL и сообщает, что ничего не отправлено.
3. GPT останавливается.
4. Пользователь отправляет exact phrase новым сообщением.
5. Только после этого `executeSandboxTrade`.
6. Затем `getSandboxOrderState`.
7. При `unknown_do_not_resubmit` никакого повторного submit; только status reconciliation.

## Market/sizing acceptance

Для инвестиционного решения, если рынок закрыт, нет свежего `best ask` или доступен только stale `last price`:

- `WAIT_FOR_FRESH_MARKET`/эквивалент;
- точное количество лотов не выдавать как персональный sizing;
- stale price не использовать как подтверждённую цену покупки.

Строго технический Sandbox test может иметь явно заданные пользователем виртуальные параметры, но не должен маскироваться под инвестиционную рекомендацию.

## Secrets boundary

GitHub хранит только имена переменных и инструкции. Никогда не коммитить значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- будущего real full-access token;
- `GATEWAY_API_KEY`;
- Authorization header;
- полный broker accountId;
- реальные позиции/операции как configuration data.

Подробности: `gpt/SECRETS_AND_RENDER.md` и `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## Publishing/update checklist — current read-only

1. Открыть `gpt/SETUP_INDEX.md`.
2. Использовать `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
3. Ровно 10 Knowledge-файлов.
4. `Thinking 5.6`, пока модель доступна и поддерживает Actions.
5. Web Search + Data Analysis ON; Image generation + Apps OFF.
6. Проверить `/health`.
7. Импортировать production `/openapi.json`.
8. Сверить 14 GET Actions.
9. API Key → Bearer с `GATEWAY_API_KEY`.
10. Preview smoke tests.
11. Маскированный account ID + MSK.
12. `Update` только после успешных проверок.

## Publishing/update checklist — Sandbox acceptance

Только после green/merged Sandbox backend:

1. Выполнить `docs/operations/SANDBOX_TRADING_RUNBOOK.md` до раздела Render secrets.
2. В Render добавить отдельный `TINVEST_SANDBOX_TOKEN`; существующий `TINVEST_TOKEN` не менять.
3. `SANDBOX_TRADING_ENABLED=true`, TTL 120.
4. Дождаться healthy redeploy.
5. Проверить `getSandboxTradingStatus` напрямую через Gateway/OpenAPI.
6. В GPT Editor заменить Instructions целиком на `CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.
7. Knowledge оставить теми же 10 файлами.
8. Повторно импортировать `/openapi.json`.
9. Проверить, что видны 14 baseline Actions + 8 Sandbox Actions и нет real-money mutation Actions.
10. Bearer `GATEWAY_API_KEY` не менять.
11. Выполнить virtual BUY/SELL/negative acceptance из Sandbox runbook.
12. После успеха нажать `Update`.

## Важная граница GitHub ↔ GPT Editor

GitHub — эталон и история версий. Он не применяет Instructions, Knowledge, model selection, sharing state, Bearer secret или OpenAPI в GPT Editor автоматически. Эти значения применяются/проверяются вручную после изменения соответствующего GitHub-файла.
