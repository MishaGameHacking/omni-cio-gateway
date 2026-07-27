# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но не заменяет профильные правила поведения Actions.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — единая проектная память.
4. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы системы.
5. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
6. `inventory/PROJECT_ASSETS.md` — что находится в GitHub, а что хранится во внешних системах.
7. `inventory/FILE_INDEX.md` — быстрый индекс runtime, tests, configuration и knowledge.

## Разделы

### Architecture

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md`
- `operations/RELEASE_CHECKLIST.md`

### Inventory

- `inventory/PROJECT_ASSETS.md`
- `inventory/FILE_INDEX.md`

### Custom GPT

Каноническая конфигурация помощника хранится в `../gpt/`:

- `../gpt/README.md`
- `../gpt/CONFIGURATION.md`
- `../gpt/INSTRUCTIONS.md`
- `../gpt/ACTIONS_CATALOG.md`
- `../gpt/NEW_CHAT_PROMPT.md`

### Domain knowledge

Проверяемые правила конкретных возможностей находятся в `../knowledge/`. Они имеют приоритет над краткими описаниями в `docs/`.

## Что не хранится в GitHub

Секреты, реальные отчёты, полный номер счёта и пользовательские финансовые данные не должны находиться в репозитории. Их наличие во внешней системе отмечается только в inventory без раскрытия значений.
