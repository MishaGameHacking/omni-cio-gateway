# Custom GPT Omni-CIO configuration

Эта папка хранит переносимую, обезличенную конфигурацию Custom GPT. Она нужна, чтобы новый чат или новый GPT-проект мог восстановить поведение помощника из GitHub.

## Файлы

- `CONFIGURATION.md` — имя, описание, starters, publishing и ручные настройки GPT Editor.
- `INSTRUCTIONS.md` — канонические системные инструкции бота.
- `ACTIONS_CATALOG.md` — operationId, paths, назначение и правила вызовов.
- `NEW_CHAT_PROMPT.md` — стартовый запрос для подключения нового чата к проекту.

## Что всё равно настраивается вручную в GPT Editor

- имя и иконка GPT;
- выбранная модель;
- публикация и доступ;
- импорт OpenAPI schema с production `/openapi.json`;
- Bearer API key, равный `GATEWAY_API_KEY` в Render;
- conversation starters.

Секретный Bearer key не хранится в GitHub.

## Обновление

При изменении Action contract:

1. обновить backend и тесты;
2. обновить `CONFIGURATION.md`, `INSTRUCTIONS.md` и `ACTIONS_CATALOG.md`;
3. обновить профильный файл в `knowledge/`;
4. после production deploy заново импортировать OpenAPI в GPT Editor;
5. проверить, что доступны только ожидаемые GET Actions;
6. подтвердить `trading_methods=false`.
