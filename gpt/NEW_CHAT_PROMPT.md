# Стартовый запрос для нового чата

Скопируйте этот текст в новый чат после подключения GitHub. Для запуска проекта в новом аккаунте сначала используйте `NEW_ACCOUNT_BOOTSTRAP.md` и `PROJECT_INSTRUCTIONS.md`.

```text
Подключись к GitHub-репозиторию Misha2304/omni-cio-gateway.

Сначала прочитай:
1. AGENTS.md
2. README.md
3. docs/README.md
4. docs/master-plan/README.md
5. docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt
6. knowledge/00_PROJECT_MASTER_CONTEXT.md
7. knowledge/16_CURRENT_PROGRAM_STATUS.md
8. gpt/README.md
9. gpt/INSTRUCTIONS_COMPACT.md
10. gpt/ACTIONS_CATALOG.md
11. профильные файлы из knowledge/ по текущей задаче

Затем:
- проверь актуальную ветку main;
- проверь последние Pull Request и GitHub Actions;
- считай код в main источником истины;
- сохраняй строгий read-only режим;
- не добавляй торговые endpoints;
- сохраняй trading_methods=false;
- сохраняй Render entrypoint app:app;
- не сохраняй токены, ключи, полный номер счёта и реальные брокерские данные;
- не используй историю, память или файлы других аккаунтов и проектов;
- работай через отдельную ветку и Pull Request;
- после значимого изменения обновляй project memory и профильную документацию.

Перед началом кратко покажи:
- текущий release;
- commit main;
- открытые PR;
- состояние Regression Shield;
- какие файлы прочитаны;
- план безопасных изменений.

Пока ничего не изменяй.
```

## Для задачи по Custom GPT

Дополнительно прочитайте всю папку `gpt/`, `knowledge/13_COMMUNICATION_STYLE_2026.txt` и проверьте production `/openapi.json` после Render deploy.

## Для проверки завершённой миграции с Telegram

Прочитайте `knowledge/12_TELEGRAM_RETIREMENT.txt` и
`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`. Не восстанавливайте
удалённый runtime без нового ADR, threat model и решения владельца.

## Для задачи по frontend

Сначала прочитайте `docs/inventory/PROJECT_ASSETS.md`. Не создавайте новый сайт, пока не найден и не подтверждён исходный frontend-проект существующего Omni-CIO Bot.
