# Custom GPT Omni-CIO Portfolio Assistant

Эта папка хранит воспроизводимую конфигурацию существующего Omni-CIO внутри ChatGPT.

## Канонические файлы

- `INSTRUCTIONS_COMPACT.md` — полностью вставляется в GPT Editor.
- `INSTRUCTIONS.md` — расширенная версия для разработки и аудита.
- `CONFIGURATION.md` — имя, описание, capabilities, starters и publishing checklist.
- `ACTIONS_CATALOG.md` — фактические 14 GET Actions.
- `PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md` — личная инвестиционная политика владельца.
- `PORTFOLIO_GPT_ACCEPTANCE_V1.md` — Preview end-to-end acceptance.
- `MY_GPT_SETUP_RUNBOOK.md` — точная ручная настройка существующего GPT.
- `BOT_ONLY_FILE_MANIFEST.md` — минимальный набор файлов и исключения.

Текущий product scope:

`docs/master-plan/OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md`.

## Назначение

Omni-CIO должен по команде владельца:

- получать реальный портфель через Gateway;
- анализировать структуру, концентрацию, ликвидность и риски;
- проверять свежие новости и кредитные рейтинги;
- искать подходящие инструменты;
- предлагать hold/wait/reduce/sell/increase/buy/do-nothing;
- рассчитывать доступный объём без создания заявки.

## Что исключено

- отдельный сайт;
- web-кабинет;
- мобильное приложение;
- Telegram;
- собственная AI-модель;
- автономная торговля;
- write Actions.

## Что вводится вручную

Владелец вручную выполняет только:

1. Открывает существующий GPT в web editor.
2. Вставляет `INSTRUCTIONS_COMPACT.md`.
3. Загружает заполненную personal policy и минимальный Knowledge.
4. Включает Web Search и Data Analysis.
5. Выключает Image generation.
6. Проверяет/imports production `/openapi.json`.
7. Вводит Bearer `GATEWAY_API_KEY` в защищённом поле.
8. Проходит `PORTFOLIO_GPT_ACCEPTANCE_V1.md`.
9. Нажимает Update.

Секреты, полный account ID и реальные brokerage payload не хранятся в GitHub или Knowledge.

## Синхронизация

- Поведение изменилось → обновить оба Instructions и Preview acceptance.
- GPT Editor settings изменились → обновить `CONFIGURATION.md`.
- Action contract изменился → обновить OpenAPI и `ACTIONS_CATALOG.md`.
- Личная политика изменилась → обновить только owner Knowledge file, не public repository secrets.
- GitHub CI не заменяет реальный Preview.
