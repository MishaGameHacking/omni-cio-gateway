## Что изменено

Опишите одну логическую цель и затронутые файлы.

## Причина

Какую проблему решает изменение и почему оно необходимо сейчас?

## Безопасность

- [ ] Пользовательские endpoints остаются только `GET`.
- [ ] `trading_methods=false`.
- [ ] Не добавлены создание, отправка, замена или отмена заявок.
- [ ] `app:app` сохранён.
- [ ] В diff нет токенов, API-ключей, полного ID счёта и реальных брокерских данных.
- [ ] Валюты не агрегируются без подтверждённого FX.

## Тесты

- [ ] `python -m compileall ...`
- [ ] `python -m pytest ... --cov-fail-under=60`
- [ ] `python scripts/check_repository_layout.py`
- [ ] `python scripts/check_ci_security_baseline.py`
- [ ] Ruff, formatting и mypy
- [ ] pip-audit, Bandit и detect-secrets
- [ ] Regression Shield

Результаты:

```text
вставьте краткий результат
```

## Контракты и документация

- [ ] Изменение сопоставлено с `docs/master-plan/` и фактическим статусом в `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- [ ] OpenAPI/operationId не изменены либо описана миграция.
- [ ] Обновлён `CHANGELOG.md`.
- [ ] Обновлён профильный `knowledge/` файл.
- [ ] Обновлены `gpt/` файлы, если изменился Action.
- [ ] Обновлён `docs/inventory/PROJECT_ASSETS.md`, если изменились внешние компоненты.
- [ ] `.in`, lock-файлы и dependency hashes согласованы.
- [ ] Все external Actions pinned full commit SHA.

## Проверка после merge

1. Для runtime/deploy change дождаться Render deploy; для docs-only change явно указать, что deploy не требуется.
2. Если runtime затронут, проверить `/health`, версию, commit SHA, `app:app` и `trading_methods=false`.
3. При изменении схемы обновить GPT Actions по `gpt/MY_GPT_SETUP_RUNBOOK.md`.
4. Выполнить один целевой smoke test без лишних Actions и зафиксировать acceptance state.
