# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но
не заменяет профильные правила поведения Gateway Actions.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — стратегическая проектная память.
4. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — фактический активный этап и оставшиеся пакеты.
5. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы системы.
6. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
7. `inventory/PROJECT_ASSETS.md` — GitHub и внешние системы.
8. `inventory/FILE_INDEX.md` — индекс runtime, tests, configuration и knowledge.

## Разделы

### Architecture

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`
- `architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md` — private GET Action, bounded TTL registry, fail-closed HTTP and OpenAPI contract.
- `architecture/FINAL_DECISION_REVIEW_PUBLISHER_V1.md` — internal exact-source publication, concurrency, replacement, eviction and safe observability.
- `architecture/FINAL_DECISION_REVIEW_ORCHESTRATION_V1.md` — end-to-end PR-53…PR-62 composition, first-blocker semantics and unchanged production OpenAPI.
- `architecture/FINAL_DECISION_REVIEW_ACCEPTANCE_EVIDENCE_V1.md` — immutable Render/Gateway/GPT/rollback evidence, SHA-256 proof binding and completion rules.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_V1.md` — production-importable typed workflow boundary, scenario/binding composition, TTL and no-route guarantees.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_V1.md` — exactly-one buy/sell source, risk explanation, no-action behavior and coordinator boundary.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_V1.md` — canonical acquisition evidence, source freshness/account/direction gates and adapter boundary.

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md` — основной gateway.
- `operations/TELEGRAM_REMOVAL_RUNBOOK.md` — одноразовая очистка
  выведенного Telegram service.
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

### Retired Telegram integration

Runtime и deployment contract удалены. Решение и запрет случайного
возврата описаны в `../knowledge/12_TELEGRAM_RETIREMENT.txt`, а внешняя
очистка — в `operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

### CI and security

Воспроизводимые dependencies, quality/security gates, начальные
thresholds и остаточный долг описаны в
`../knowledge/14_CI_SECURITY_BASELINE.txt`.

### Current program status

Фактическая вершина программы, завершённые контуры и следующий безопасный
рабочий пакет фиксируются в `../knowledge/16_CURRENT_PROGRAM_STATUS.md`.
Этот файл используется для активного номера PR; стратегические требования
остаются в `../knowledge/00_PROJECT_MASTER_CONTEXT.md`.

### Domain knowledge

Проверяемые правила конкретных возможностей находятся в `../knowledge/`. Они имеют приоритет над краткими описаниями в `docs/`.

## Что не хранится в GitHub

Секреты, реальные отчёты, полный номер счёта и пользовательские
финансовые данные не должны находиться в репозитории. Старые Telegram
credentials, обнаруженные при внешней очистке, также нельзя сохранять.
