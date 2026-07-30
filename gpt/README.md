# Custom GPT Omni-CIO

Эта папка хранит воспроизводимую конфигурацию пользовательского интерфейса Omni-CIO внутри ChatGPT. История чатов, память аккаунта и секреты для восстановления не нужны.

## Канонические точки входа

- `MY_GPT_SETUP_RUNBOOK.md` — точная настройка в ChatGPT → My GPTs.
- `CONFIGURATION.md` — желаемое состояние GPT Editor.
- `INSTRUCTIONS_COMPACT.md` — рабочий текст для поля Instructions.
- `INSTRUCTIONS.md` — расширенная каноническая версия поведения.
- `ACTIONS_CATALOG.md` — ровно 14 production GET Actions.
- `NEW_ACCOUNT_BOOTSTRAP.md` — запуск в новом аккаунте.
- `BOT_ONLY_FILE_MANIFEST.md` — что относится к боту и что не переносится.
- `PROJECT_INSTRUCTIONS.md` и `NEW_CHAT_PROMPT.md` — восстановление контекста разработки.

Стратегическая спецификация разработки находится в `docs/master-plan/`; фактический выполненный этап и следующий пакет — в `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Что вводится вручную

- имя, описание, starters, модель и режим доступа;
- текст из `INSTRUCTIONS_COMPACT.md`;
- минимально необходимые Knowledge-файлы;
- Web Search, если нужны текущие публичные сведения;
- production `/openapi.json` в разделе Actions;
- API Key с типом Bearer и секретным значением `GATEWAY_API_KEY`.

Секрет никогда не записывается в GitHub, Instructions или Knowledge. Подробная последовательность и проверки — в `MY_GPT_SETUP_RUNBOOK.md`.

## Синхронизация

Если меняется только поведение ответа, синхронизируйте оба файла Instructions, профиль `knowledge/13_COMMUNICATION_STYLE_2026.txt` и затем проверьте Preview. Если меняется OpenAPI, после production deploy повторно импортируйте schema и сверяйте весь каталог Actions.

Внутри GPT нельзя считать Render/Gateway/GPT acceptance выполненной по одному зелёному CI. Статус acceptance фиксируется только после реальных проверок из `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
