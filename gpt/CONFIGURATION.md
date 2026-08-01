# Custom GPT configuration registry — Portfolio Assistant v1

## Identity

- Existing GPT: update in place; do not create a duplicate.
- Recommended name: `Omni-CIO | Портфельный управляющий`.
- Primary language: Russian.
- Product: personal read-only portfolio assistant for the owner’s T-Invest account.
- Backend: existing Omni-CIO Gateway, stable `app:app`.

## Recommended description

> Личный инвестиционный AI-ассистент для моего портфеля T-Invest. Получает актуальные позиции через защищённые Actions, проверяет новости и кредитные рейтинги, анализирует риски и диверсификацию, помогает выбрать активы и рассчитать изменения. Работает только по моим командам и не совершает сделки.

## Instructions

- Полностью вставить `gpt/INSTRUCTIONS_COMPACT.md` в поле Instructions существующего GPT.
- `gpt/INSTRUCTIONS.md` — расширенная каноническая версия для разработки и аудита.
- Не добавлять поверх канонического текста старые Telegram, website, publishing или autonomous-trading instructions.
- При нехватке места сокращать примеры, но не удалять safety, quality gate, action routing, три варианта и personal policy requirements.

## Knowledge

Production Knowledge должен быть минимальным.

Загружать только:

1. Заполненную личную политику владельца на основе `gpt/PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md`.
2. Краткие правила анализа портфеля, инструментов, новостей и рейтингов, если они не помещаются в Instructions.
3. Один нейтральный style/reference файл без конфликтующих workflows.

Не загружать:

- master plans;
- CI/security runbooks;
- GitHub history;
- Telegram retirement/history;
- внутренние release/evidence документы;
- секреты;
- реальные брокерские отчёты;
- полный account ID.

## Capabilities

Включить:

- Web Search — свежие новости, раскрытия, рейтинги и рынок;
- Code Interpreter / Data Analysis — расчёты, таблицы и графики;
- Actions — Gateway API.

Выключить:

- Image generation — не требуется для portfolio workflow;
- Apps — текущий GPT использует Actions, а не Apps.

Модель должна поддерживать Custom Actions. Не выбирать режим, в котором Actions недоступны.

## Actions

- Schema source: production Gateway `/openapi.json`.
- Authentication: API Key → Bearer.
- Secret: `GATEWAY_API_KEY`, вводится владельцем вручную в защищённом поле.
- Expected surface: ровно 14 GET operations из `gpt/ACTIONS_CATALOG.md`.
- Write/execute/transfer/withdraw methods отсутствуют.
- `trading_methods=false` обязателен.

## Conversation starters

1. `Проанализируй мой портфель: структура, риски, диверсификация и конкретные варианты действий.`
2. `Проверь свежие новости и кредитные риски по активам моего портфеля.`
3. `У меня есть свободные деньги. Сначала проверь портфель, затем предложи 3–5 подходящих активов.`
4. `Какие позиции в моём портфеле стоит держать, сократить или пересмотреть?`
5. `Сравни текущую структуру с моей личной инвестиционной политикой и предложи ребалансировку.`
6. `Проверь, достаточно ли данных для надёжной рекомендации. Не додумывай недостающие цифры.`

## Preview acceptance order

1. `gatewayHealth` — проверить version, `app:app`, capabilities и `trading_methods=false`.
2. `getConnection` — проверить маскированный счёт.
3. Полный portfolio analysis по первому conversation starter.
4. News/rating review по второму starter.
5. Free-cash candidate search с purchase-capacity calculation.
6. Stale/partial-data refusal scenario.
7. Method-isolation scenario: попросить вызвать только один Action.
8. Проверить отсутствие Telegram, website и trade-execution предложений.
9. Выполнить полную матрицу `gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md`.

## Publishing checklist

1. Дождаться green GitHub package с exact head.
2. Проверить production `/health`.
3. Обновить Instructions в существующем GPT.
4. Удалить устаревшие/конфликтующие Knowledge-файлы.
5. Загрузить заполненную personal policy и выбранные minimal Knowledge files.
6. Импортировать актуальный `/openapi.json`, только если contract changed или Editor schema stale.
7. Проверить Bearer auth без раскрытия ключа.
8. Пройти Preview acceptance.
9. Оставить GPT private.
10. Нажать Update только после успешной приёмки.

## External state

GitHub хранит желаемое состояние, но не применяет его автоматически к GPT Editor. Владелец вручную выполняет только:

- вставку Instructions;
- загрузку Knowledge;
- ввод Bearer key;
- Preview;
- Update.

ChatGPT/agent выполняет код, документы, тесты, OpenAPI review, GitHub branch/PR/CI и подготовку точных UI-шагов.
