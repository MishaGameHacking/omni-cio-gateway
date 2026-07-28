# Custom GPT Omni-CIO configuration

Эта папка хранит переносимую, обезличенную конфигурацию Custom GPT. Она нужна, чтобы новый чат, новый GPT-проект или новый аккаунт ChatGPT мог восстановить поведение помощника из GitHub без переноса личной истории аккаунта.

## Файлы

- `CONFIGURATION.md` — имя, описание, starters, publishing и ручные настройки GPT Editor.
- `INSTRUCTIONS_COMPACT.md` — рабочий текст для поля Instructions в GPT Editor; укладывается в лимит 8000 символов.
- `INSTRUCTIONS.md` — расширенные канонические инструкции для GitHub, разработки и восстановления контекста.
- `ACTIONS_CATALOG.md` — operationId, paths, назначение и правила вызовов.
- `NEW_CHAT_PROMPT.md` — стартовый запрос для подключения нового чата к проекту.
- `PROJECT_INSTRUCTIONS.md` — готовый текст для Project instructions нового ChatGPT Project.
- `BOT_ONLY_FILE_MANIFEST.md` — полный список только файлов Omni-CIO и внешних настроек без данных аккаунта.
- `NEW_ACCOUNT_BOOTSTRAP.md` — пошаговый запуск Omni-CIO в новом аккаунте только из GitHub.

Профиль стиля также зафиксирован в `knowledge/13_COMMUNICATION_STYLE_2026.txt`. Его можно загрузить в Knowledge как справочник с расширенными примерами. При конфликте компактные Instructions имеют приоритет.

## Новый аккаунт без переноса личных данных

Для переезда проекта не нужен экспорт истории старого аккаунта. Используйте:

1. `NEW_ACCOUNT_BOOTSTRAP.md`;
2. `PROJECT_INSTRUCTIONS.md`;
3. `BOT_ONLY_FILE_MANIFEST.md`;
4. `NEW_CHAT_PROMPT.md`;
5. существующий приватный репозиторий и production Gateway.

Старые личные чаты, память другого аккаунта и файлы посторонних проектов не входят в перенос Omni-CIO.

## Что всё равно настраивается вручную в GPT Editor

- имя и иконка GPT;
- выбранная модель;
- публикация и доступ;
- текст Instructions из `INSTRUCTIONS_COMPACT.md`;
- Knowledge-файл `knowledge/13_COMMUNICATION_STYLE_2026.txt`;
- включение Web Search;
- импорт OpenAPI schema с production `/openapi.json`;
- Bearer API key, равный `GATEWAY_API_KEY` в Render;
- conversation starters.

Секретный Bearer key не хранится в GitHub.

## Обновление поведения без изменения Actions

Если меняются только язык, структура ответа или правила публикаций:

1. обновить расширенный `INSTRUCTIONS.md`;
2. синхронизировать рабочий `INSTRUCTIONS_COMPACT.md`, сохраняя размер менее 8000 символов;
3. обновить `CONFIGURATION.md` и профильный файл в `knowledge/`;
4. после merge открыть GPT Editor;
5. заменить поле Instructions полным содержимым `INSTRUCTIONS_COMPACT.md`;
6. при необходимости загрузить профиль стиля в Knowledge;
7. проверить Preview;
8. нажать Update.

Повторно импортировать OpenAPI не нужно, если контракт Actions не изменился.

## Обновление Action contract

При изменении Action contract:

1. обновить backend и тесты;
2. обновить `CONFIGURATION.md`, оба файла Instructions и `ACTIONS_CATALOG.md`;
3. обновить профильный файл в `knowledge/`;
4. после production deploy заново импортировать OpenAPI в GPT Editor;
5. проверить, что доступны только ожидаемые GET Actions;
6. подтвердить `trading_methods=false`.
