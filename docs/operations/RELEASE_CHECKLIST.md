# Release checklist

## 1. Подготовка

- [ ] `main` актуален.
- [ ] Открытые PR и Issues проверены.
- [ ] Новая ветка создана от текущего `main`.
- [ ] Прочитаны `AGENTS.md` и профильный `knowledge/NN_*.txt`.
- [ ] Версия релиза определена в одном месте плана.

## 2. Код и контракты

- [ ] Runtime, `/health`, OpenAPI и Regression Shield показывают одну версию.
- [ ] Render entrypoint остаётся `app:app`.
- [ ] Пользовательские endpoints только `GET`.
- [ ] `trading_methods=false`.
- [ ] Не добавлены order create/replace/cancel/submit operationId.
- [ ] Все object schemas содержат явные `properties`.
- [ ] Секреты и полный ID счёта отсутствуют в diff.
- [ ] Денежные суммы считаются через безопасную десятичную логику.
- [ ] Валюты не складываются без подтверждённого FX.

## 3. Тесты

- [ ] `python -m compileall ...` проходит.
- [ ] `python -m pytest -q` проходит.
- [ ] `python scripts/check_repository_layout.py` проходит.
- [ ] Happy path покрыт.
- [ ] Partial/error path покрыт.
- [ ] OpenAPI/endpoint покрыт.
- [ ] Read-only и отсутствие торговых методов покрыты.
- [ ] Для денежных функций есть защита от двойного счёта.

## 4. Документация

- [ ] Обновлён `CHANGELOG.md`.
- [ ] Обновлён `README.md`, если изменились запуск или текущий release.
- [ ] Обновлён `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
- [ ] Обновлён профильный `knowledge/NN_*.txt`.
- [ ] Обновлены `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если изменился Action contract.
- [ ] Обновлён `docs/inventory/PROJECT_ASSETS.md`, если добавлен внешний компонент.

## 5. Pull Request

- [ ] Описание содержит изменение, безопасность, тесты и post-merge проверку.
- [ ] Head SHA зафиксирован перед merge.
- [ ] Regression Shield зелёный.
- [ ] Нет нерешённых review threads.
- [ ] Для релиза выбран squash merge.

## 6. Production

- [ ] Render deploy использует merge commit.
- [ ] `/health` подтверждает версию, commit SHA и `app:app`.
- [ ] `trading_methods=false`.
- [ ] При необходимости проверен `getConnection`.
- [ ] OpenAPI импортирован в GPT Editor без schema errors.
- [ ] Один целевой Action протестирован без вызова других методов.
- [ ] Project memory позволяет новому чату понять релиз только из GitHub.
