# Release checklist

## 1. Подготовка

- [ ] `main` актуален.
- [ ] Открытые PR и Issues проверены.
- [ ] Новая ветка создана от текущего `main`.
- [ ] Прочитаны `AGENTS.md`, master context и профильный knowledge-файл.
- [ ] Определено, какие компоненты меняются: Gateway, Custom GPT или frontend.
- [ ] Версии компонентов явно указаны.

## 2. Код и контракты

- [ ] Gateway entrypoint остаётся `app:app`.
- [ ] Gateway Actions только `GET`.
- [ ] `trading_methods=false` во всех интерфейсах.
- [ ] Не добавлены order create/replace/cancel/submit методы.
- [ ] Telegram runtime, Blueprint, environment variables и imports отсутствуют.
- [ ] OpenAPI object schemas содержат явные `properties`.
- [ ] Секреты, старые Telegram credentials и полный ID счёта отсутствуют в diff.
- [ ] Валюты не складываются без подтверждённого FX.

## 3. Тесты

- [ ] `python scripts/check_repository_layout.py` проходит.
- [ ] `python scripts/check_ci_security_baseline.py` проходит.
- [ ] Ruff lint и formatting baseline проходят.
- [ ] mypy baseline проходит.
- [ ] `python -m compileall ...` проходит.
- [ ] `python -m pytest ... --cov-fail-under=60` проходит.
- [ ] pip-audit, Bandit и detect-secrets проходят.
- [ ] Happy path покрыт.
- [ ] Partial/error path покрыт.
- [ ] Read-only и отсутствие торговли покрыты.
- [ ] `tests/test_no_telegram_runtime.py` подтверждает отсутствие
      Telegram package, config, imports и OpenAPI routes.
- [ ] Regression Shield зелёный.
- [ ] Все external Actions pinned полным commit SHA.
- [ ] Lock-файлы pinned, hashed и согласованы с `.in`.

## 4. Документация

- [ ] Обновлён `CHANGELOG.md`.
- [ ] Обновлён `README.md`.
- [ ] Обновлён master context.
- [ ] Обновлён профильный `knowledge/NN_*`.
- [ ] Обновлён asset inventory.
- [ ] Обновлён соответствующий deployment runbook.
- [ ] `gpt/` обновлён, если менялся Action contract.

## 5. Pull Request

- [ ] Описание содержит изменение, безопасность, тесты и post-merge проверку.
- [ ] Head SHA зафиксирован.
- [ ] Нет нерешённых review threads.
- [ ] Для релиза выбран squash merge.

## 6. Production

### Gateway

- [ ] Render deploy использует merge commit.
- [ ] `/health` подтверждает Gateway version, commit SHA и `app:app`.
- [ ] `trading_methods=false`.
- [ ] При изменении схемы обновлён GPT Editor.

### Final-review evidence dossier

Каждая строка ниже должна быть записана как
`FinalDecisionReviewAcceptanceEvidenceV1`. Галочка без датированного proof и SHA-256 не
считается выполненной.

- [ ] `render_source_commit` — Render использует ожидаемый merge commit.
- [ ] `health_contract` — cache-busted `/health` подтверждает release contract.
- [ ] `private_auth_negative` — запрос без valid Gateway key отклонён.
- [ ] `exact_route_positive` — exact authenticated query возвращает compact response.
- [ ] `gpt_schema_import` — актуальная OpenAPI schema импортирована в GPT Editor.
- [ ] `gpt_authenticated_preview` — authenticated Action выполнен в Preview.
- [ ] `gpt_action_list` — write/order/funds-movement Actions отсутствуют.
- [ ] `rollback_restore` — rollback drill восстановил известный read-only release.
- [ ] Dossier имеет восемь `passed`, `acceptance_completed=true` и
      `trading_methods=false`.

Статусы `not_executed` и `not_applicable` не закрывают production acceptance.

### Telegram retirement (только для PR удаления)

- [x] После merge старый Render service удалён по removal runbook.
- [x] Telegram environment variables удалены вместе со старым service.
- [x] Webhook удалён.
- [x] Старый токен отозван в BotFather.
- [ ] Gateway `/health` после очистки остаётся исправным.

- [ ] Project memory позволяет новому чату понять релиз только из GitHub.
