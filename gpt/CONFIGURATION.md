# Custom GPT configuration registry — Omni-CIO v8.4

> Этот файл — реестр настроек. Не вставлять его целиком в поле Instructions.
> Production Instructions находятся только в `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик v8.4`
- Purpose: личный read-only инвестиционный аналитик и клиент Omni-CIO Gateway.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- GPT configuration release: `v8.4`.
- Production Instructions release: `v8.4.1`.
- Backend/Gateway release: `v3.10.0`.
- Recommended model: `Thinking 5.6`.

## Description

> Личный read-only GPT для T-Invest. Сам получает портфель, операции, ликвидность, параметры инструментов и котировки через Omni-CIO Gateway. В режиме «УПРАВЛЯЙ ПОРТФЕЛЕМ» анализирует структуру, сравнивает варианты и формирует read-only план. Не создаёт заявки, не совершает сделки и не выводит деньги.

## Conversation starters

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — сначала вызови getPortfolioSnapshot. Если успешно, вызови getCashLiquiditySnapshot и getPortfolioAnalytics. Затем проанализируй данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Первый starter намеренно содержит Action names для максимально надёжного dispatch. Простые естественные команды также должны маршрутизироваться автоматически по Instructions.

## Instructions

В поле `Instructions` вставить **100% содержимого**:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Других production Instructions-файлов нет. Не смешивать старые версии из чатов, локальных копий или Git history.

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

Каждый файл загружать один раз. Не загружать исходный код, master plan, реальные брокерские отчёты, accountId или secrets.

## Capabilities

- Web Search: **ON**.
- Code Interpreter / Data Analysis: **ON**.
- Image generation: **OFF** для текущего инвестиционного workflow.
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

- Type: `API Key`
- Mode: `Bearer`
- Value: `GATEWAY_API_KEY` из Render service `omni-cio-gateway`
- `TINVEST_TOKEN` в GPT Editor не вставлять

Expected surface:

- ровно 14 GET Actions из `gpt/ACTIONS_CATALOG.md`;
- никаких create/order/execute/cancel/replace/transfer/withdraw методов;
- `trading_methods=false`.

## Portfolio dispatch acceptance

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` ожидаемый обязательный старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. только затем анализ, рынок/кандидаты при необходимости и DecisionCard.

Если бот пишет «нет свежих данных» до реальной попытки первого Action, acceptance не пройден.

## Market/sizing acceptance

Если рынок закрыт, нет свежего `best ask` или доступен только stale `last price`:

- решение должно быть `WAIT_FOR_FRESH_MARKET`/эквивалентное ожидание;
- точное количество лотов не должно подаваться как персональный sizing;
- stale price не используется как подтверждённая цена покупки.

## Secrets boundary

GitHub хранит только имена переменных и инструкции. Никогда не коммитить:

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization header;
- полный broker accountId;
- реальные позиции/операции как configuration data.

Подробности: `gpt/SECRETS_AND_RENDER.md`.

## Publishing/update checklist

1. Открыть `gpt/SETUP_INDEX.md`.
2. Вставить `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` без ручного смешивания версий.
3. Загрузить ровно 10 Knowledge-файлов без дублей.
4. Выбрать `Thinking 5.6`, пока эта модель доступна и поддерживает Actions.
5. Web Search + Data Analysis ON; Image generation + Apps OFF.
6. Проверить `/health`: `status=ok`, `version=3.10.0`, `entrypoint=app:app`, `trading_methods=false`.
7. Импортировать production `/openapi.json`.
8. Сверить 14 GET Actions.
9. Настроить API Key → Bearer.
10. Выполнить Preview smoke tests из `SETUP_INDEX.md`.
11. Проверить маскирование account ID и московское время.
12. Нажать `Update` только после успешных проверок.

## Важная граница GitHub ↔ GPT Editor

GitHub — эталон и история версий. Он не применяет Instructions, Knowledge, model selection, sharing state или Bearer secret в GPT Editor автоматически. Эти значения применяются/проверяются вручную после изменения соответствующего GitHub-файла.
