# Omni-CIO v8.4 — полный setup/recovery runbook

Этот документ нужен для полного восстановления существующего Custom GPT после сбоя, удаления Action или перехода на новый GPT Editor. Для обычного обслуживания сначала использовать `gpt/SETUP_INDEX.md`.

## 1. Архитектура

```text
GitHub main → Render service `omni-cio-gateway` → T-Invest API
      │
      └→ эталон GPT configuration → вручную GPT Editor

Custom GPT Actions → HTTPS Bearer → https://omni-cio-gateway.onrender.com
```

GitHub не содержит значений secrets и не обновляет GPT Editor автоматически.

## 2. Production baseline

- GPT: `Omni-CIO API | Управляющий и аналитик v8.4`
- Production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`
- Recommended model: `Thinking 5.6`
- Gateway: `v3.10.0`
- Entrypoint: `app:app`
- Base URL: `https://omni-cio-gateway.onrender.com`
- Health: `https://omni-cio-gateway.onrender.com/health`
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`
- Expected Action surface: exactly 14 GET operations
- Safety: `trading_methods=false`

## 3. Проверить Render до GPT Editor

Открыть production `/health` и убедиться:

- `status=ok`;
- `version=3.10.0`;
- `build.entrypoint=app:app` или эквивалентный entrypoint marker;
- `trading_methods=false`.

В Render Environment production service должны быть:

- `GATEWAY_API_KEY`;
- `TINVEST_TOKEN`;
- `SSL_TBANK_VERIFY=True`.

Значения не копировать в GitHub, issues, chats, Instructions или Knowledge.

## 4. Настроить GPT Editor

Открыть существующий Omni-CIO в `Мои GPT → Редактировать → Конфигурация`.

### Name / Description / starters

Сверить с `gpt/CONFIGURATION.md`.

### Instructions

Удалить старое содержимое поля Instructions и вставить **целиком**:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Не смешивать с Git history или локальными копиями.

### Knowledge

Удалить старые дубликаты и загрузить ровно 10 файлов:

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

### Capabilities

- Web Search: ON
- Data Analysis / Code Interpreter: ON
- Image generation: OFF для текущего инвестиционного workflow
- Apps: не использовать вместе с Actions
- Actions: ON

### Recommended model

Выбрать `Thinking 5.6`, пока эта модель доступна в GPT Editor и поддерживает Actions.

## 5. Настроить Action

Schema import URL:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- `API Key`
- `Bearer`
- secret: текущее значение `GATEWAY_API_KEY` из Render

`TINVEST_TOKEN` в GPT Editor **не вводится**.

После импорта сверить operationId с `gpt/ACTIONS_CATALOG.md`: ожидается ровно 14 GET Actions.

## 6. Preview acceptance

Открыть новый Preview-чат и выполнить:

1. `Проверь шлюз. Вызови только gatewayHealth. Другие методы не вызывай.`
2. `Проверь подключение к брокеру.`
3. `Сколько у меня сейчас денег?`
4. `Что у меня сейчас в портфеле?`
5. `Какие операции были за последние 90 дней?`
6. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Для portfolio-management должен реально выполняться базовый dispatch:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics`

Только потом разрешён содержательный анализ.

Acceptance также требует:

- masked account ID;
- время пользователя по Москве;
- read-only поведение;
- no write Actions;
- `trading_methods=false`;
- no stale-price sizing при закрытом/неподтверждённом рынке.

## 7. Сохранение

После успешного Preview:

1. Нажать `Update`.
2. Закрыть редактор.
3. Открыть GPT заново.
4. Повторить `Проверь подключение к брокеру` и один portfolio query.

## 8. Recovery by failure type

### Бот отвечает, но Actions не вызываются

- убедиться, что выбрана модель, поддерживающая Actions;
- проверить, что Action присутствует в GPT Editor;
- проверить production OpenAPI import;
- проверить Bearer key;
- начать новый Preview-чат;
- выполнить exact-action test.

### `401/403`

Проверить соответствие `GATEWAY_API_KEY` между Render и GPT Action Bearer. Не менять `TINVEST_TOKEN`, если проблема относится к Gateway auth.

### Gateway health работает, connection не работает

Проверить `TINVEST_TOKEN` в Render и T-Invest access. Не переносить token в GPT.

### После backend update изменились operationId/schema

Повторно импортировать production `/openapi.json` и сверить `ACTIONS_CATALOG.md`.

### Поведение GPT ухудшилось после Instructions/Knowledge update

Вернуться к последнему проверенному commit GitHub, восстановить соответствующий production Instructions/Knowledge и повторить Preview acceptance.

## 9. Правило обновления

Все изменения сначала фиксируются в GitHub через отдельную branch/PR. Backend merge разрешён только после Regression Shield. Изменения GPT UI затем вручную применяются из `main` и подтверждаются Preview.

Подробная матрица обновлений находится в `gpt/SETUP_INDEX.md`.
