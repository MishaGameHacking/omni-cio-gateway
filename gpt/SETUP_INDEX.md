# Omni-CIO Custom GPT — Setup Index

Эта страница — **главная точка восстановления существующего Omni-CIO GPT**.

Если GPT сломался, был удалён, нужно перейти в другой чат/аккаунт или проверить настройки — начинайте отсюда.

Если задача — обновить и подключить **уже существующий** Omni-CIO без создания второго GPT, сначала откройте:

`gpt/CONNECT_EXISTING_GPT.md`

## Быстрая карта

| Что настраивается в GPT Editor | Что брать из GitHub | Что делать |
|---|---|---|
| Существующий Omni-CIO | `gpt/CONNECT_EXISTING_GPT.md` | Выполнить пошагово, не создавать дубликат |
| Name / Description / Starters | `gpt/CONFIGURATION.md` | Скопировать значения вручную |
| Instructions | `gpt/INSTRUCTIONS_COMPACT.md` | Скопировать **весь файл целиком** в поле Instructions |
| Knowledge | `gpt/knowledge/*.txt` | Скачать **все 10 файлов** и загрузить в Knowledge |
| Actions schema | production `/openapi.json` | Импортировать **по URL**, не скачивать вручную |
| Actions authentication | `GATEWAY_API_KEY` из Render | Ввести вручную: API Key → Bearer |
| T-Invest token | `TINVEST_TOKEN` в Render | В GPT не копировать |
| 14 Action names | `gpt/ACTIONS_CATALOG.md` | Использовать как контрольный список |
| Полная установка | `gpt/MY_GPT_SETUP_RUNBOOK.md` | Выполнить шаги по порядку |
| Секреты/Render | `gpt/SECRETS_AND_RENDER.md` | Проверить архитектуру, секреты не коммитить |

## 1. Что копировать как текст

### Instructions

Открыть:

`gpt/INSTRUCTIONS_COMPACT.md`

Скопировать **100% содержимого**, начиная с первой строки и заканчивая последней.

В GPT Editor:

`Конфигурация → Инструкции`

Старую версию удалить полностью и заменить новой.

### Name / Description / Conversation starters

Открыть:

`gpt/CONFIGURATION.md`

Скопировать соответствующие значения вручную.

## 2. Какие файлы скачать и загрузить в Knowledge

Папка:

`gpt/knowledge/`

Загрузить все 10:

- `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
- `04_CIO_PORTFOLIO_MANAGER.txt`
- `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
- `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
- `07_PERSONAL_STRATEGY.txt`
- `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
- `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
- `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
- `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
- `13_COMMUNICATION_STYLE_2026.txt`

**Важно:** перед загрузкой удалить старые одноимённые Knowledge-файлы из GPT, чтобы не держать одновременно v8.3 и v8.4.

## 3. Что НЕ надо скачивать для Actions

OpenAPI schema импортируется прямо по URL:

`https://omni-cio-gateway-au6d.onrender.com/openapi.json`

В GPT Editor:

`Действия → существующий Omni-CIO Action → Импортировать из URL-адреса`

После импорта сверить с:

`gpt/ACTIONS_CATALOG.md`

Ожидается ровно 14 GET Actions.

## 4. Какой ключ куда вводить

### В GPT Editor

Authentication:
- `API Key`
- `Bearer`
- значение: **`GATEWAY_API_KEY` из Render**

### В Render

Environment:
- `GATEWAY_API_KEY`
- `TINVEST_TOKEN`
- `SSL_TBANK_VERIFY`

### Никогда не делать

- не коммитить значения ключей в GitHub;
- не вставлять `TINVEST_TOKEN` в GPT Action;
- не вставлять секреты в Instructions/Knowledge;
- не показывать Authorization header;
- не хранить полный accountId.

## 5. Текущий production Gateway

Base URL:

`https://omni-cio-gateway-au6d.onrender.com`

Health:

`https://omni-cio-gateway-au6d.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway-au6d.onrender.com/openapi.json`

Ожидание по `/health`:
- status = ok;
- version = 3.10.0;
- entrypoint = app:app;
- trading_methods = false.

## 6. Минимальный тест после восстановления

В Preview выполнить по очереди:

1. `Проверь Gateway. Вызови только gatewayHealth. Другие методы не вызывай.`
2. `Проверь подключение к T-Invest. Вызови только getConnection. Полный анализ не запускай.`
3. `Вызови только getPortfolioSnapshot. Операции не вызывай. Рекомендаций не давай.`
4. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Тест №4 должен подтвердить новую логику v8.4: бот сам идёт в Gateway, не прыгает сразу к тикеру, сравнивает действие с бездействием, проверяет рынок и отделяет technical affordability от персонального sizing.

## 7. Что является каноном

Для UI-настройки Custom GPT каноническая папка:

`gpt/`

Для production Knowledge upload каноническая папка:

`gpt/knowledge/`

Не собирать Knowledge вручную из случайных старых чатов или старых скачанных копий.

## 8. Полный runbook

Если нужно обновить существующего бота:

`gpt/CONNECT_EXISTING_GPT.md`

Если нужна настройка с нуля или после полного сбоя:

`gpt/MY_GPT_SETUP_RUNBOOK.md`

Если нужно понять состояние полей GPT Editor:

`gpt/CONFIGURATION.md`

Если нужно проверить секреты/Render:

`gpt/SECRETS_AND_RENDER.md`
