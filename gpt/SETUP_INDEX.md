# Omni-CIO Custom GPT — единая карта настройки и восстановления

Это **главная точка входа** для настройки, обновления и восстановления единственного поддерживаемого бота:

`Omni-CIO API | Управляющий и аналитик v8.4`

Архитектура:

```text
GitHub (код + эталон настроек)
        │
        ├── Render deploy → Omni-CIO Gateway (`app:app`)
        │                         │
        │                         ├── production T-Invest read-only
        │                         └── optional T-Invest Sandbox execution
        │
        └── вручную → GPT Editor: Instructions + Knowledge
                                  │
                                  └── Actions → Render Gateway
```

## Что GitHub делает и чего не делает

GitHub — источник истины, резервная копия и история версий кода/настроек Omni-CIO.

GitHub **не меняет поле Instructions и Knowledge внутри GPT Editor автоматически**. После изменения этих файлов их нужно вручную применить в GPT Editor и нажать `Update`.

Gateway-код хранится в GitHub и разворачивается отдельным Render service. Custom GPT обращается не к GitHub, а к production Gateway через Actions.

## Каноническая конфигурация

- GPT UI/product name: `v8.4` until manually renamed by the owner.
- Accepted read-only Instructions baseline: `v8.4.1`.
- Canonical Sandbox-enabled Instructions after owner Preview acceptance: `v8.5.0`.
- Recommended model: `Thinking 5.6`.
- Production base URL: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Gateway entrypoint: `app:app`.
- Sandbox OFF surface: exactly `14` GET operations.
- Sandbox ON surface: 14 baseline + 8 isolated Sandbox Actions.
- Real-money safety invariant: `real_trading_methods=false`.
- User-visible timezone: Moscow / `Europe/Moscow` / MSK.

## 1. Что копировать в GPT Editor

### Name, Description, starters and capabilities

Использовать:

`gpt/CONFIGURATION.md`

### Instructions

Для текущей Sandbox-capable конфигурации использовать **только**:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`

В GPT Editor:

`Конфигурация → Инструкции`

Старый текст удалить полностью и вставить весь файл целиком. Не смешивать несколько версий Instructions.

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` сохраняется как read-only fallback/baseline, но не содержит Sandbox execution protocol.

## 2. Что загрузить в Knowledge

Загрузить **ровно 10 файлов** из `gpt/knowledge/`, каждый один раз:

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

Перед заменой изменённого файла удалить старую одноимённую копию из Knowledge, затем загрузить новую. Дубликаты запрещены.

## 3. Как подключены Actions

В GPT Editor открыть существующее действие Omni-CIO и импортировать schema по URL:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: `API Key`
- Mode: `Bearer`
- Value: текущее значение `GATEWAY_API_KEY` из Render service `omni-cio-gateway`

Ожидаемый список operationId находится в:

`gpt/ACTIONS_CATALOG.md`

При `SANDBOX_TRADING_ENABLED=false` после импорта должно быть ровно 14 GET Actions.

При `SANDBOX_TRADING_ENABLED=true` дополнительно должны появиться только 8 Sandbox Actions:

- `getSandboxTradingStatus`;
- `openSandboxAccount`;
- `fundSandboxAccount`;
- `getSandboxPortfolio`;
- `prepareSandboxTrade`;
- `executeSandboxTrade`;
- `getSandboxOrderState`;
- `cancelSandboxOrder`.

Ни в одном режиме не должно быть real-money create/order/execute/cancel/replace/transfer/withdraw Actions.

## 4. Где находятся T-Invest tokens

Оба T-Invest tokens хранятся **только в Render Environment** и никогда не вводятся в GPT Editor:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — отдельный Sandbox token.

Render Environment для Sandbox-capable production service:

- `TINVEST_TOKEN`
- `TINVEST_SANDBOX_TOKEN`
- `GATEWAY_API_KEY`
- `SSL_TBANK_VERIFY=True`
- `SANDBOX_TRADING_ENABLED=true|false`
- `SANDBOX_CONFIRMATION_TTL_SECONDS=120`

Границы секретов: `gpt/SECRETS_AND_RENDER.md`.

## 5. Полная настройка существующего или восстановленного GPT

1. Открыть `ChatGPT → Мои GPT → Omni-CIO → Редактировать`.
2. Сверить Name/Description/starters по `gpt/CONFIGURATION.md`.
3. Вставить `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` целиком.
4. Загрузить ровно 10 Knowledge-файлов из списка выше.
5. Выбрать recommended model `Thinking 5.6`.
6. Включить Web Search.
7. Включить Data Analysis / Code Interpreter.
8. Image generation для инвестиционного workflow оставить выключенным.
9. Apps не использовать вместе с Actions.
10. В Action импортировать production OpenAPI URL.
11. Настроить API Key → Bearer с `GATEWAY_API_KEY`.
12. Сверить Action surface с текущим `SANDBOX_TRADING_ENABLED`.
13. Запустить Preview tests из раздела ниже.
14. Нажать `Update` только после успешных тестов.

Подробный аварийный runbook: `gpt/MY_GPT_SETUP_RUNBOOK.md`.

## 6. Минимальные Preview tests

### Real production read-only smoke

В новом Preview-чате выполнить по очереди:

1. `Проверь шлюз. Вызови только gatewayHealth. Другие методы не вызывай.`
2. `Проверь подключение к брокеру.`
3. `Сколько у меня сейчас денег?`
4. `Что у меня сейчас в портфеле?`
5. `Какие операции были за последние 90 дней?`
6. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Для пункта 6 ожидаемая базовая цепочка:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → анализ`

Проверить дополнительно:

- account ID показывается только маскированно;
- пользовательские даты отображаются по Москве;
- `real_trading_methods=false`;
- бот не утверждает, что совершил real сделку;
- при закрытом/неподтверждённом рынке не выдаёт точный sizing по stale last price.

### Sandbox smoke when enabled

1. `getSandboxTradingStatus` → `sandbox=true`, `real_money=false`.
2. Proposal through `prepareSandboxTrade` must not submit anything.
3. `executeSandboxTrade` requires exact short-lived phrase from a separate user message.
4. Wrong/expired phrase must fail closed.
5. After submit, verify `getSandboxOrderState`.
6. Duplicate confirmation must not create a second broker order.
7. For cancellation, use only Sandbox order + explicit confirmation and verify final state.

Full sequence: `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## 7. Как обновлять бот

### Изменились только Instructions

1. Изменение проходит через branch/PR в GitHub.
2. После merge открыть актуальный `CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` из `main`.
3. Заменить Instructions в GPT Editor целиком.
4. Preview test.
5. `Update`.

### Изменился Knowledge-файл

1. Merge изменения в GitHub.
2. В GPT Editor удалить старую одноимённую копию.
3. Скачать новую копию из `gpt/knowledge/` и загрузить её.
4. Проверить, что всего ровно 10 Knowledge-файлов.
5. Preview test → `Update`.

### Изменился Gateway-код без изменения OpenAPI

1. Merge только после зелёного Regression Shield.
2. Render разворачивает commit из `main` согласно своей настройке deploy.
3. Проверить `/health` и нужный endpoint.
4. GPT schema повторно импортировать не нужно, если API contract не менялся.

### Изменился OpenAPI / Action contract

1. Merge и deploy Gateway.
2. Проверить production `/health`.
3. Повторно импортировать `https://omni-cio-gateway.onrender.com/openapi.json` в GPT Actions.
4. Сверить surface с `ACTIONS_CATALOG.md` и текущим Sandbox flag.
5. Убедиться, что real-money mutation Actions отсутствуют.
6. Preview acceptance → `Update`.

### Изменился секрет

- `TINVEST_TOKEN`: заменить только в Render и сохранять read-only.
- `TINVEST_SANDBOX_TOKEN`: заменить только в Render.
- `GATEWAY_API_KEY`: заменить в Render и тем же значением обновить Bearer key в GPT Action.
- Секреты никогда не сохранять в GitHub, Knowledge или Instructions.

## 8. Что умеет текущий бот

Через Gateway и доступные публичные источники Omni-CIO умеет:

- проверить Gateway и подключение T-Invest;
- получить текущий портфель и обогащённые позиции;
- показать деньги и ликвидность;
- анализировать структуру и концентрацию;
- получить рыночный snapshot инструмента и портфеля;
- найти инструмент;
- проверить техническую покупательную способность без real заявки;
- получить историю и аналитику операций;
- сверять официальный broker report;
- выполнять read-only final decision review;
- объяснять данные простым русским языком;
- проверять свежие публичные новости/события через Web Search, когда это действительно требуется;
- при Sandbox enable создавать виртуальный Sandbox account, пополнять его виртуальными деньгами, готовить/подтверждать Sandbox BUY/SELL, проверять состояние и отменять Sandbox orders.

Он **не умеет и не должен** создавать, отправлять, заменять или отменять реальные заявки, выводить/переводить деньги или менять права брокерского доступа.

## 9. Что является источником истины

- Runtime/API: фактический `main` GitHub + deployed Render Gateway.
- GPT UI configuration: `gpt/CONFIGURATION.md`.
- Canonical Sandbox-capable Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.
- Read-only fallback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
- Production Knowledge: ровно 10 файлов `gpt/knowledge/`.
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`.
- Development rules: `AGENTS.md`.
- Exact current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

Не восстанавливать бот из старых чатов, скриншотов или локальных копий, если они расходятся с `main`.
