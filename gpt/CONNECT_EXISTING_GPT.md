# Подключение существующего Omni-CIO GPT к GitHub/Render/T-Invest

Эта инструкция предназначена именно для уже существующего Custom GPT `Omni-CIO API | Управляющий и аналитик`.

Цель: не создавать второго бота, а привести текущий GPT к канонической конфигурации из GitHub и сохранить безопасную read-only архитектуру.

## 1. Итоговая архитектура

Использовать:

`GitHub → Render/Gateway → Custom GPT Actions → Omni-CIO`

и для брокерских данных:

`T-Invest → Render/Gateway → Custom GPT Actions → Omni-CIO`

GitHub хранит код, Instructions, Knowledge-пакет, runbooks и конфигурацию.
Render запускает Gateway и хранит секреты.
Custom GPT использует Actions и получает приватные данные только через Gateway.

Не подключать GitHub App непосредственно внутрь этого Custom GPT: текущий Omni-CIO должен сохранять Actions для Gateway/T-Invest.

## 2. Что уже существует

Repository:

`Misha2304/omni-cio-gateway`

Каноническая папка настройки GPT:

`gpt/`

Главная карта:

`gpt/SETUP_INDEX.md`

Production Render:

`https://omni-cio-gateway-au6d.onrender.com`

Health:

`https://omni-cio-gateway-au6d.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway-au6d.onrender.com/openapi.json`

## 3. Открыть существующего GPT

В web-версии ChatGPT:

1. Открыть `GPTs`.
2. Открыть `Мои GPT`.
3. Найти `Omni-CIO API | Управляющий и аналитик`.
4. Нажать значок редактирования.
5. Перейти в `Конфигурация`.

Не создавать новый GPT.

## 4. Имя, описание и starters

Открыть GitHub-файл:

`gpt/CONFIGURATION.md`

Перенести в GPT Editor:

- Name;
- Description;
- четыре Conversation starters.

Текущая конфигурационная версия — v8.4.
Backend/Gateway — v3.10.0.

## 5. Instructions

Открыть:

`gpt/INSTRUCTIONS_COMPACT.md`

В GPT Editor:

1. открыть поле `Инструкции`;
2. удалить старый текст полностью;
3. скопировать 100% содержимого `INSTRUCTIONS_COMPACT.md`;
4. не объединять вручную старую v8.3 и новую v8.4.

Критические правила Instructions:

- read-only;
- `trading_methods=false`;
- запрет create/submit/replace/cancel orders;
- узкий запрос не расширять;
- общий запрос управления запускает автономный read-only цикл;
- last price не равна гарантированной цене сделки;
- `withdraw_limits` не является бюджетом покупки;
- technical affordability не равна персональному sizing;
- существенные решения сравнивать с бездействием;
- при необходимости формировать DecisionCard.

## 6. Knowledge

Перед обновлением удалить из GPT старые одноимённые Knowledge-файлы.

Скачать из GitHub папки:

`gpt/knowledge/`

и загрузить в Knowledge ровно эти 10 файлов:

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

Не загружать в production GPT Knowledge:

- master plan;
- исходный код Gateway;
- реальные брокерские отчёты как постоянную конфигурацию;
- токены;
- полный accountId;
- GitHub development runbooks, если они не нужны самому GPT для ответов.

## 7. Capabilities

Для существующего Omni-CIO:

- Web Search: ON;
- Code Interpreter / Data Analysis: ON;
- Image generation: можно оставить ON, но для Gateway не требуется;
- Apps: не использовать;
- Actions: использовать.

Если включение Apps конфликтует с Actions, приоритет у Actions.

## 8. Проверить Render до Actions

Открыть в браузере:

`https://omni-cio-gateway-au6d.onrender.com/health`

Проверить минимум:

- `status = ok`;
- `version = 3.10.0`;
- `build.entrypoint = app:app`;
- `trading_methods = false`;
- T-Invest token configured = true;
- gateway API key configured = true.

Если это не выполняется, GPT Editor пока не менять дальше: сначала восстановить Gateway.

## 9. Actions

В GPT Editor открыть существующее действие Omni-CIO.

### Authentication

Настроить:

- Authentication: `API Key`;
- Mode: `Bearer`;
- Secret: значение `GATEWAY_API_KEY` из Render.

Не использовать `TINVEST_TOKEN` в GPT Editor.

### Schema

Нажать:

`Импортировать из URL-адреса`

и использовать:

`https://omni-cio-gateway-au6d.onrender.com/openapi.json`

После импорта сверить с:

`gpt/ACTIONS_CATALOG.md`

Ожидается ровно 14 GET Actions.

Никаких write/execute/transfer/withdraw Actions быть не должно.

## 10. Секреты

Render Environment хранит:

- `GATEWAY_API_KEY`;
- `TINVEST_TOKEN`;
- `SSL_TBANK_VERIFY`.

GPT Editor знает только Bearer secret, совпадающий с `GATEWAY_API_KEY`.

GitHub не хранит значения секретов.

Подробно:

`gpt/SECRETS_AND_RENDER.md`

## 11. Preview acceptance

Выполнить тесты строго по одному.

### Test A — Gateway

`Проверь шлюз. Вызови только gatewayHealth. Другие методы не вызывай.`

Ожидание:
- один Action;
- `status=ok`;
- `trading_methods=false`.

### Test B — T-Invest

`Проверь подключение к T-Invest. Вызови только getConnection. Полный анализ не запускай.`

Ожидание:
- счёт замаскирован;
- нет полного accountId;
- другие Actions не вызываются.

### Test C — Portfolio isolation

`Вызови только getPortfolioSnapshot. Покажи G1–G4. Операции не вызывай. Рекомендаций не давай.`

Ожидание:
- один портфельный Action;
- нет рекомендаций.

### Test D — autonomous CIO

`УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Ожидание v8.4:
- бот сам обращается к Gateway;
- не просит вручную «обновить доступ», пока Action не вернул реальную ошибку;
- сначала определяет состояние и структурный пробел;
- сравнивает действие с бездействием;
- не прыгает сразу к случайному тикеру;
- перед точной ценой проверяет market snapshot;
- technical affordability отделяет от strategy sizing;
- при существенном решении показывает DecisionCard.

### Test E — closed market / no ask

Если рынок закрыт или best ask отсутствует, бот должен дать `WAIT_FOR_FRESH_MARKET`/условный сценарий, а не выдавать last price за гарантированную цену покупки.

## 12. Сохранить GPT

Только после успешного Preview:

1. нажать `Обновить`;
2. закрыть редактор;
3. снова открыть GPT;
4. убедиться, что Instructions, Knowledge и Action сохранились;
5. повторить `getConnection`.

## 13. Что обновляется автоматически, а что вручную

Автоматически:

`GitHub main → Render deploy → Gateway runtime`

при изменениях runtime/config, которые входят в deploy.

Вручную в GPT Editor пока остаются:

- изменение Instructions;
- замена Knowledge-файлов;
- повторный импорт OpenAPI при изменении Action schema;
- Bearer secret при ротации `GATEWAY_API_KEY`;
- Capabilities/Sharing.

GitHub является source of truth и резервной копией, но GPT Editor не синхронизируется с GitHub автоматически.

## 14. Восстановление в новом чате

В новом ChatGPT-чате достаточно дать разработчику/ассистенту команду:

`Подключись к Misha2304/omni-cio-gateway. Сначала прочитай AGENTS.md, gpt/SETUP_INDEX.md, gpt/CONNECT_EXISTING_GPT.md и knowledge/00_PROJECT_MASTER_CONTEXT.md. Продолжай настройку существующего Omni-CIO, не создавай дубликат.`

## 15. Восстановление после полного сбоя

Порядок:

1. GitHub `gpt/SETUP_INDEX.md`.
2. Render `/health`.
3. `CONFIGURATION.md`.
4. `INSTRUCTIONS_COMPACT.md`.
5. 10 файлов `gpt/knowledge/`.
6. OpenAPI URL.
7. API Key → Bearer (`GATEWAY_API_KEY`).
8. Preview acceptance.
9. Update.

При таком порядке история чатов не является обязательной частью восстановления.