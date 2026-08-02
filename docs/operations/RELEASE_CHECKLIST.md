# Omni-CIO release checklist

## 1. Scope

- [ ] `main` актуален.
- [ ] Открытые PR/Issues проверены.
- [ ] Branch создана от текущего `main`.
- [ ] Прочитаны `AGENTS.md`, current status и профильный файл.
- [ ] Изменение относится непосредственно к Omni-CIO Custom GPT, Gateway, его данным, безопасности, тестам или эксплуатации.
- [ ] Один логический scope на PR.

## 2. Read-only contract

- [ ] Gateway entrypoint остаётся `app:app`.
- [ ] User-facing Actions только GET.
- [ ] `trading_methods=false`.
- [ ] Нет create/submit/replace/cancel/stop-order/withdraw/transfer surface.
- [ ] Account ID маскирован.
- [ ] Секреты и реальные private broker payloads отсутствуют в diff.
- [ ] OpenAPI object schemas совместимы с GPT Actions.
- [ ] Валюты не агрегируются без verified FX + timestamp.
- [ ] Partial/truncated/stale state не выдаётся за complete/current.

## 3. Runtime/dependencies

- [ ] Не удалены runtime dependencies текущего `app.py` без отдельного compatibility refactor.
- [ ] Dependency `.in` изменяются осознанно.
- [ ] Generated locks не редактируются вручную.
- [ ] Runtime/dev locks pinned + hashed.
- [ ] External GitHub Actions pinned full SHA.

## 4. Tests / Regression Shield

- [ ] `python scripts/check_repository_layout.py`.
- [ ] `python scripts/check_ci_security_baseline.py`.
- [ ] Ruff lint.
- [ ] Formatting baseline.
- [ ] mypy.
- [ ] compileall.
- [ ] pytest + branch coverage >=60%.
- [ ] dependency audit.
- [ ] Bandit.
- [ ] secret scan.
- [ ] relevant happy path.
- [ ] relevant partial/error paths.
- [ ] read-only/no-write invariants.
- [ ] exact-head Regression Shield fully green.

## 5. Documentation/configuration

Обновлять только затронутые источники истины:

- [ ] `README.md`, если меняется использование/архитектура.
- [ ] `CHANGELOG.md`, если изменение release-visible.
- [ ] `knowledge/00_PROJECT_MASTER_CONTEXT.md`, если меняется архитектура/границы.
- [ ] `knowledge/16_CURRENT_PROGRAM_STATUS.md`, если меняется accepted status.
- [ ] профильный domain/architecture file.
- [ ] `gpt/` при изменении Custom GPT configuration/behavior/action contract.
- [ ] deploy/recovery runbook при эксплуатационном изменении.

Не создавать параллельные setup/inventory/audit файлы без реальной необходимости.

## 6. Pull Request

- [ ] PR описывает purpose, changes, safety, tests and post-merge acceptance.
- [ ] Head SHA зафиксирован перед final merge decision.
- [ ] Нет unresolved review threads.
- [ ] Нет merge conflicts.
- [ ] Squash merge используется для release package.

## 7. Production Gateway acceptance

После backend/deployment change:

- [ ] Render deploy использует ожидаемый main commit.
- [ ] `https://omni-cio-gateway.onrender.com/health` возвращает healthy read-only contract.
- [ ] `version=3.10.0` либо ожидаемая новая версия.
- [ ] `app:app`.
- [ ] `trading_methods=false`.
- [ ] auth-negative test отклоняется.
- [ ] нужный auth-positive endpoint работает.

## 8. GPT acceptance

Если менялись Instructions/Knowledge/Actions:

- [ ] Production Instructions взяты из `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` либо явно новой канонической версии.
- [ ] В Knowledge ровно 10 актуальных файлов без дублей.
- [ ] Recommended supported model выбран.
- [ ] Production OpenAPI повторно импортирован, если contract менялся.
- [ ] Action list сверена с `gpt/ACTIONS_CATALOG.md`.
- [ ] Bearer secret настроен без публикации значения.
- [ ] `gatewayHealth` smoke test.
- [ ] `getConnection` smoke test.
- [ ] simple balance/portfolio command test.
- [ ] operations test.
- [ ] `УПРАВЛЯЙ ПОРТФЕЛЕМ` запускает tool-first chain.
- [ ] user-visible time по Москве.
- [ ] stale-market sizing gate работает.
- [ ] account ID masked.
- [ ] `trading_methods=false`.
- [ ] Нажат `Update` после Preview acceptance.

## 9. Rollback

- [ ] Известен предыдущий accepted GitHub commit.
- [ ] Render rollback path известен.
- [ ] Для GPT configuration известно, какие Instructions/Knowledge восстановить.
- [ ] Secrets не ротируются без отдельной причины.

Green CI не заменяет реальные Render/GPT проверки, когда изменение затрагивает production state.
