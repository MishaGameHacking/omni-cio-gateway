# Стартовый запрос для нового чата

Скопируйте этот текст в новый чат после подключения GitHub:

```text
Подключись к GitHub-репозиторию Misha2304/omni-cio-gateway.

Сначала прочитай:
1. AGENTS.md
2. README.md
3. docs/README.md
4. knowledge/00_PROJECT_MASTER_CONTEXT.md
5. gpt/INSTRUCTIONS.md
6. gpt/ACTIONS_CATALOG.md
7. профильные файлы из knowledge/ по текущей задаче

Затем:
- проверь актуальную ветку main;
- проверь последние Pull Request и GitHub Actions;
- считай код в main источником истины;
- сохраняй строгий read-only режим;
- не добавляй торговые endpoints;
- сохраняй trading_methods=false;
- сохраняй Render entrypoint app:app;
- не сохраняй токены, ключи, полный номер счёта и реальные брокерские данные;
- работай через отдельную ветку и Pull Request;
- после значимого изменения обновляй project memory и профильную документацию.

Перед началом кратко покажи:
- текущий release;
- commit main;
- открытые PR;
- состояние Regression Shield;
- какие файлы прочитаны;
- план безопасных изменений.
```

## Для задачи по Custom GPT

Дополнительно прочитайте папку `gpt/` и проверьте production `/openapi.json` после Render deploy.

## Для задачи по frontend

Сначала прочитайте `docs/inventory/PROJECT_ASSETS.md`. Не создавайте новый сайт, пока не найден и не подтверждён исходный frontend-проект существующего Omni-CIO Bot.
