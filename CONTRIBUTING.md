# Вклад в Omni-CIO Gateway

Omni-CIO поддерживает **один existing Custom GPT v9.0.0 + один production Gateway `app:app`**. WP0–WP15 завершены и owner-accepted; текущий режим репозитория — **controlled maintenance**.

## Перед началом

1. Прочитайте `AGENTS.md`.
2. Прочитайте `README.md` и `docs/README.md`.
3. Прочитайте `knowledge/00_PROJECT_MASTER_CONTEXT.md` и `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
4. Для GPT/config/recovery задач прочитайте `gpt/SETUP_INDEX.md` и `gpt/CONFIGURATION.md`.
5. Прочитайте `docs/architecture/SYSTEM_OVERVIEW.md` и профильный architecture/runbook.
6. Используйте `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` как завершённую specification/audit trail, а не как очередь незавершённых WP.
7. Проверьте актуальный `main`, открытые issues/PR и latest GitHub Actions.

Закрытые issues, merged PR и старые комментарии — **исторические снимки**. Если они противоречат accepted `main` или `knowledge/16_CURRENT_PROGRAM_STATUS.md`, текущий source of truth имеет приоритет.

## Текущее состояние

- Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.
- Protected rollback: **v8.6.1**.
- Gateway entrypoint: `app:app`.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Runtime Action authority: effective production `/openapi.json`.
- Repository mode: **controlled maintenance**.

## Неприкосновенные правила

### Product/runtime

- Не создавать второй Custom GPT, duplicate Gateway, parallel frontend/scheduler или competing broker stack без новой явной owner-approved программы.
- Сохранять стабильный Render entrypoint `app:app`.
- Internal v9 Python engine не считать GPT Action, если его operationId отсутствует в effective production OpenAPI.

### Broker contours

Production intentionally contains three isolated contours:

1. read-only through `TINVEST_TOKEN`;
2. optional virtual Sandbox through `TINVEST_SANDBOX_TOKEN`;
3. optional exact-owner-confirmed Real execution through separate `TINVEST_TRADING_TOKEN` + durable state.

Do not collapse these boundaries.

Real execution remains narrow and protected:

- reviewed operationIds: `getRealTradingStatus`, `prepareRealTrade`, `executeRealTrade`, `getRealOrderState`;
- prepare and execute remain separate;
- exact short-lived owner confirmation must arrive in a **new** user turn;
- own-funds BUY / own-position SELL;
- immutable request/plan identity + one-submit idempotency + broker reconciliation;
- possible-submit ambiguity → reconciliation only, no automatic retry;
- submitted != filled without broker proof;
- no transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real-money execution under the reviewed surface.

`REAL_TRADING_ENABLED=false` remains the master Real kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

### Data/security

- Account IDs remain masked in user-facing output.
- Never commit token/key values, Authorization headers, full account IDs, private broker payloads or secret exports.
- Currencies are not aggregated without verified FX + timestamp.
- Do not double-count payments, commissions, child operations or embedded trades.
- Partial/stale/truncated/contradictory data is never presented as complete/current truth.
- Generated lock files are not edited manually; `.in` files are canonical direct constraints.
- External GitHub Actions stay pinned to full commit SHA.

## Рабочий процесс

Для каждого существенного maintenance package:

1. Создайте branch от актуального `main`.
2. Зафиксируйте точный defect/scope и source of truth.
3. Сделайте одно логическое изменение.
4. Добавьте или обновите deterministic tests/guards.
5. Обновите только существующие canonical docs; не создавайте дублирующие setup/audit/inventory files.
6. Откройте Pull Request.
7. Дождитесь **exact-head Regression Shield + security**.
8. Убедитесь, что unresolved review threads = 0.
9. Выполните squash merge.
10. Если изменился applied GPT config или reviewed Action contract, отдельно выполните owner Preview/`Update` acceptance на **том же** GPT и запишите non-secret evidence.

Repository merge сам по себе не меняет GPT Editor.

## Минимальные проверки

Основной merge gate — `.github/workflows/regression-shield.yml`. Локально/в CI применяются, среди прочего:

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
python -m pip_audit --require-hashes --disable-pip --strict \
  --vulnerability-service osv \
  --progress-spinner off -r requirements.txt
python -m bandit -c pyproject.toml -r . -ll -ii -q
```

Точный набор команд и pinned tooling определяет текущий Regression Shield; не ослабляйте gate ради прохождения обновления зависимости.

## Требования к Pull Request

PR должен объяснять:

- что изменено и почему;
- какие runtime/data/GPT contours затронуты;
- как сохранены credential and authority boundaries;
- менялся ли OpenAPI/operationId/GPT Editor contract;
- какие tests/guards выполнены;
- какие canonical docs обновлены;
- какие dependencies/locks/Action SHAs затронуты;
- что проверить после merge/deploy;
- требуется ли owner Preview/`Update` или это backend/doc-only maintenance;
- какой rollback path остаётся действующим.

## Исторические записи GitHub

Не переписывайте исторический смысл merged PR/closed issue так, будто он всегда описывал текущее состояние. Если старый thread может ввести в заблуждение, добавьте явную supersession/current-state заметку и ссылку на `knowledge/16_CURRENT_PROGRAM_STATUS.md`. Current status должен жить в canonical files, а не в случайном старом комментарии.
