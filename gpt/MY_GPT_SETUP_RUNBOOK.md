# Настройка существующего Omni-CIO в ChatGPT → My GPTs

Дата актуализации: 2026-08-01

Этот runbook настраивает уже существующий Custom GPT как персонального read-only помощника по портфелю T-Invest.

Он не создаёт новый GPT, сайт, приложение, Telegram-интеграцию или торговый режим.

## 1. Предварительные условия

- доступ к web-версии ChatGPT и существующему GPT;
- работающий production Gateway;
- доступ владельца к `GATEWAY_API_KEY` в Render;
- актуальный green GitHub package;
- read-only T-Invest token;
- заполненная личная политика или готовность использовать limited diagnostic mode.

Проверить:

- `<RENDER_EXTERNAL_URL>/health`;
- `<RENDER_EXTERNAL_URL>/openapi.json`.

Ожидается:

- Gateway version `3.10.0` либо актуальная задокументированная версия;
- `build.entrypoint=app:app`;
- `trading_methods=false`;
- ровно 14 GET operations из `ACTIONS_CATALOG.md`;
- write/transfer/withdraw methods отсутствуют.

## 2. Открыть существующий GPT

1. Открыть ChatGPT в браузере.
2. Перейти: GPTs → Мои GPT.
3. Выбрать существующий Omni-CIO.
4. Нажать Edit GPT.
5. Работать во вкладке Configure.
6. Не создавать новый GPT.

## 3. Identity

Взять из `CONFIGURATION.md`:

- имя;
- описание;
- conversation starters.

Рекомендуемое имя:

`Omni-CIO | Портфельный управляющий`

## 4. Instructions

1. Удалить старый текст Instructions полностью.
2. Вставить полный `INSTRUCTIONS_COMPACT.md`.
3. Не добавлять старые website, Telegram, publishing или autonomous-trading правила.
4. Не вставлять секреты и полный account ID.

## 5. Knowledge

Удалить конфликтующие и лишние Knowledge-файлы.

Оставить минимальный набор:

1. Заполненная personal portfolio policy.
2. Компактная методика portfolio/instrument/news/rating analysis, если она нужна сверх Instructions.
3. Нейтральный style/reference файл при необходимости.

Не загружать:

- master-plan PDF;
- CI/security runbooks;
- GitHub history;
- Telegram history;
- внутренние release/evidence docs;
- реальные брокерские отчёты;
- секреты.

## 6. Capabilities

Включить:

- Web Search;
- Code Interpreter / Data Analysis;
- Actions.

Выключить:

- Image generation;
- Apps.

Выбрать модель/режим, поддерживающий Custom Actions. Режим, в котором Actions недоступны, не использовать.

## 7. Actions

1. Открыть Actions.
2. Authentication → API Key → Bearer.
3. Ввести `GATEWAY_API_KEY` вручную.
4. Не показывать значение в чате, screenshot или документации.
5. Импортировать `<RENDER_EXTERNAL_URL>/openapi.json`, если Editor schema отсутствует, устарела или contract изменился.
6. Сверить полный список с `ACTIONS_CATALOG.md`.
7. Убедиться, что присутствуют ровно 14 GET operationId.
8. Убедиться, что отсутствуют POST/PUT/PATCH/DELETE и broker-write Actions.

## 8. Быстрая техническая проверка

### Health

Prompt:

`Проверь только состояние Gateway. Вызови только gatewayHealth.`

Проверить:

- вызван один Action;
- показаны version, entrypoint и `trading_methods=false`.

### Connection

Prompt:

`Проверь подключение. Вызови только getConnection.`

Проверить:

- счёт маскирован;
- других Actions нет.

### Portfolio

Prompt:

`Покажи базовый снимок портфеля. Вызови только getPortfolioSnapshot.`

Проверить:

- данные приватного портфеля пришли через Action;
- нет write methods;
- timestamp и quality не потеряны.

## 9. Полная Preview acceptance

Выполнить все обязательные сценарии:

`PORTFOLIO_GPT_ACCEPTANCE_V1.md`.

Критические сценарии:

- полный анализ портфеля;
- концентрация и диверсификация;
- новости по позициям;
- облигации и рейтинги;
- free-cash candidate search;
- purchase capacity;
- do-nothing option;
- refusal on partial/stale data;
- transaction refusal;
- absence of website/Telegram scope.

Для каждого сценария сохранить redacted evidence без секретов и полного account ID.

## 10. Personal policy

Заполнить `PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md`.

До загрузки заполненной политики GPT работает в limited diagnostic mode:

- анализирует факты и риски;
- показывает concentration;
- строит сценарии;
- не объявляет точные target weights персональной нормой.

После заполнения повторно выполнить diversification и free-cash scenarios.

## 11. Update

Нажать Update только когда:

- Instructions синхронизированы;
- minimal Knowledge проверен;
- Actions совпадают с каталогом;
- Bearer работает;
- обязательные Preview-сценарии прошли;
- нет Telegram/site/autonomous-trading поведения;
- `trading_methods=false` подтверждён.

Оставить GPT private.

## 12. Rollback

При проблеме:

1. Вернуть предыдущий проверенный текст Instructions.
2. Вернуть предыдущий Knowledge set.
3. При schema issue повторно импортировать последний проверенный production OpenAPI.
4. Повторить health, connection и portfolio isolation tests.
5. Нажать Update только после восстановления.

Никогда не исправлять проблему отключением Bearer auth или добавлением write endpoint.

## 13. Частые проблемы

### GPT вызывает лишние Actions

- проверить конфликты в Knowledge;
- убедиться, что используется актуальный Instructions;
- сформулировать один точный prompt;
- проверить Action descriptions.

### GPT не использует портфель перед подбором актива

- проверить наличие workflow «сначала portfolio/cash/policy» в Instructions;
- удалить старые generic analyst instructions;
- повторить free-cash acceptance.

### GPT выдаёт точные доли без personal policy

- проверить loaded Knowledge;
- убедиться, что limited diagnostic mode описан в Instructions;
- повторить scenario E2.

### GPT предлагает сделку

- немедленно прекратить acceptance;
- проверить OpenAPI и operationId;
- проверить `trading_methods=false`;
- вернуть предыдущую конфигурацию;
- не нажимать Update.

## Официальные источники OpenAI

- Creating and editing GPTs: `https://help.openai.com/en/articles/8554397-create-a-gpt`
- Configuring actions in GPTs: `https://help.openai.com/en/articles/9442513`
- GPTs in ChatGPT: `https://help.openai.com/en/articles/8554407-key-guidelines-for-writing-instructions-for-custom-gpts`

Актуальные platform rules перепроверяются перед финальной GPT Editor acceptance.
