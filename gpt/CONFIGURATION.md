# Custom GPT configuration registry — Omni-CIO v8.4

## Identity

- Name: `Omni-CIO API | Управляющий и аналитик v8.4`
- Purpose: личный read-only инвестиционный аналитик и клиент Omni-CIO Gateway.
- Primary language: Russian.
- GPT configuration release: `v8.4`.
- Backend/Gateway release: `v3.10.0`.
- Communication profile: `Modern Financial Sage — 2026`.

## Recommended model

- Recommended model: **Thinking 5.6**.
- Причина: в реальном GPT Editor/Preview этот режим стабильно выполняет Custom Actions и корректно следует многошаговой оркестрации Omni-CIO.
- `GPT-5.5 Instant` не использовать как рекомендуемый режим для production Omni-CIO: в тестах он мог отвечать текстом без фактического Action-вызова.
- Pro mode не использовать: Custom Actions в Pro mode недоступны.
- Пользователь может вручную переключить модель, но для штатной работы Omni-CIO рекомендовать именно Thinking 5.6.

## Description

> Личный read-only GPT для T-Invest. Сам получает портфель, операции, ликвидность, параметры инструментов и котировки через Omni-CIO Gateway. В режиме «УПРАВЛЯЙ ПОРТФЕЛЕМ» анализирует структуру, сравнивает варианты и формирует read-only план. Не создаёт заявки, не совершает сделки и не выводит деньги.

## Conversation starters

Использовать эти четыре основных starter-а:

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

## Instructions

В поле Instructions вставить **полное содержимое** файла:

`gpt/INSTRUCTIONS_COMPACT.md`

Не сокращать его вручную и не смешивать с предыдущими версиями.

`gpt/INSTRUCTIONS.md` остаётся расширенной версией для разработки и аудита; в GPT Editor по умолчанию используется именно `INSTRUCTIONS_COMPACT.md`.

## Knowledge — production upload set

В Knowledge существующего Custom GPT загрузить **ровно эти 10 файлов из `gpt/knowledge/`, каждый один раз**:

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

Не загружать дубликаты Knowledge-файлов. Если один и тот же номер/файл присутствует дважды, удалить обе копии и загрузить один актуальный файл из GitHub.

Эта папка является каноническим набором для загрузки в GPT Knowledge. Не загружать туда master-plan, исходный код Gateway, реальные брокерские отчёты, полный accountId или секреты.

## Capabilities

Для текущей конфигурации:

- Web Search: **ON** — для свежих публичных сведений о компаниях, фондах, отчётности, дивидендах, санкциях, ставках и новостях.
- Code Interpreter / Data Analysis: **ON** — для безопасных расчётов и анализа пользовательских файлов, без передачи секретов.
- Image generation: **опционально**; для Gateway не требуется и не влияет на инвестиционную логику.
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
- Auth mode: `Bearer`
- Secret value: вручную ввести **значение `GATEWAY_API_KEY` из Render service `omni-cio-gateway`**.
- `TINVEST_TOKEN` в GPT Editor не вставлять.

Expected Action surface:

- ровно 14 операций из `gpt/ACTIONS_CATALOG.md`;
- все методы `GET`;
- никаких create/order/execute/cancel/replace/transfer/withdraw методов;
- `trading_methods=false`.

## Secrets boundary

GitHub хранит только имена переменных и инструкции.

Никогда не коммитить:
- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization header;
- полный брокерский accountId;
- реальные позиции/операции как конфигурационные данные.

Подробности: `gpt/SECRETS_AND_RENDER.md`.

## Publishing checklist

1. Проверить `gpt/SETUP_INDEX.md`.
2. Выбрать recommended model **Thinking 5.6**.
3. Вставить `INSTRUCTIONS_COMPACT.md` без ручных изменений.
4. Загрузить ровно 10 Knowledge-файлов без дубликатов.
5. Проверить production `/health`: `status=ok`, `version=3.10.0`, `build.entrypoint=app:app`, `trading_methods=false`.
6. Импортировать `https://omni-cio-gateway.onrender.com/openapi.json`.
7. Сверить 14 GET Actions по `ACTIONS_CATALOG.md`.
8. Настроить API Key → Bearer с `GATEWAY_API_KEY` от `omni-cio-gateway`.
9. В Preview выполнить method-isolation, `gatewayHealth`, `getConnection` и один портфельный тест.
10. Проверить команду `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.` именно в Thinking 5.6.
11. Убедиться, что счёт маскирован и write Actions отсутствуют.
12. Нажать Update/Create только после успешных проверок.

## External UI state

GitHub хранит желаемое и воспроизводимое состояние, но не может автоматически применить изменения к GPT Editor. Имя, sharing, capabilities, recommended model, фактически загруженные Knowledge-файлы и Bearer secret всё равно вводятся/проверяются вручную в интерфейсе ChatGPT.
