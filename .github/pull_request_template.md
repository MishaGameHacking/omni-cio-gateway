## Что изменено

Опишите одну логическую цель и затронутые файлы.

## Причина

Какую проблему Omni-CIO решает изменение и почему оно нужно сейчас?

## Scope

- [ ] Изменение относится непосредственно к Custom GPT, Gateway, данным, безопасности, тестам или эксплуатации Omni-CIO.
- [ ] Не создаётся параллельный продукт/setup/configuration source.

## Безопасность

- [ ] User-facing endpoints остаются только `GET`.
- [ ] `trading_methods=false`.
- [ ] Не добавлены create/submit/replace/cancel/stop-order/withdraw/transfer methods.
- [ ] `app:app` сохранён.
- [ ] Account IDs остаются masked.
- [ ] В diff нет token/key values, Authorization headers, full account IDs или private broker payloads.
- [ ] Валюты не агрегируются без verified FX + timestamp.
- [ ] Partial/stale/truncated data не выдаются за complete/current.

## Тесты

- [ ] `python scripts/check_repository_layout.py`
- [ ] `python scripts/check_ci_security_baseline.py`
- [ ] Ruff / formatting / mypy
- [ ] compileall
- [ ] pytest + branch coverage >=60%
- [ ] dependency audit / Bandit / secret scan
- [ ] exact-head Regression Shield

Результаты:

```text
вставьте краткий результат
```

## Контракты и документация

- [ ] OpenAPI/operationId не изменены либо описана migration/acceptance.
- [ ] Обновлены только затронутые canonical docs.
- [ ] `knowledge/16_CURRENT_PROGRAM_STATUS.md` обновлён, если изменился accepted status.
- [ ] `gpt/` обновлён, если менялись Custom GPT configuration/behavior/Actions.
- [ ] Если менялись dependencies, `.in` и generated hash locks согласованы.
- [ ] External GitHub Actions pinned full SHA.

## После merge

- [ ] Для backend change проверен deployed Render commit и `/health`.
- [ ] Для OpenAPI change schema повторно импортирована в GPT Editor.
- [ ] Для Instructions/Knowledge change применены актуальные файлы из `main`.
- [ ] Выполнены соответствующие Preview smoke tests.
- [ ] Проверены masked account, MSK display и `trading_methods=false`.
- [ ] Известен rollback path.
