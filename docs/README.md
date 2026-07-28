# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но не заменяет профильные правила поведения Actions и Telegram Companion.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — единая проектная память.
4. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы системы.
5. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
6. `inventory/PROJECT_ASSETS.md` — GitHub и внешние системы.
7. `inventory/FILE_INDEX.md` — индекс runtime, tests, configuration и knowledge.

## Разделы

### Architecture

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md` — основной gateway.
- `operations/TELEGRAM_COMPANION_RUNBOOK.md` — отдельный Telegram service.
- `operations/RELEASE_CHECKLIST.md`

### Inventory

- `inventory/PROJECT_ASSETS.md`
- `inventory/FILE_INDEX.md`

### Custom GPT

Каноническая конфигурация помощника хранится в `../gpt/`:

- `../gpt/README.md`
- `../gpt/CONFIGURATION.md`
- `../gpt/INSTRUCTIONS.md`
- `../gpt/INSTRUCTIONS_COMPACT.md`
- `../gpt/ACTIONS_CATALOG.md`
- `../gpt/NEW_CHAT_PROMPT.md`
- `../gpt/PROJECT_INSTRUCTIONS.md`
- `../gpt/BOT_ONLY_FILE_MANIFEST.md`
- `../gpt/NEW_ACCOUNT_BOOTSTRAP.md`

Для запуска Omni-CIO в новом аккаунте ChatGPT без переноса личных чатов используйте `../gpt/NEW_ACCOUNT_BOOTSTRAP.md`.

### Telegram Companion

Runtime находится в `../telegram_bot/`, правила — в `../knowledge/12_TELEGRAM_COMPANION.txt`, а развёртывание — в `operations/TELEGRAM_COMPANION_RUNBOOK.md`.

### Domain knowledge

Проверяемые правила конкретных возможностей находятся в `../knowledge/`. Они имеют приоритет над краткими описаниями в `docs/`.

## Что не хранится в GitHub

Секреты, Telegram token, webhook secret, реальные Telegram user IDs, реальные отчёты, полный номер счёта и пользовательские финансовые данные не должны находиться в репозитории. Их наличие во внешней системе отмечается только в inventory без раскрытия значений.
