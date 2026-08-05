# Вклад в Omni-CIO

Omni-CIO — один продукт. Текущий production/recovery runtime остаётся **existing Custom GPT v9.0.0 + production Gateway `app:app`**, а owner-approved V10 развивается последовательно в этом же репозитории.

V9 WP0–WP15 завершены и owner-accepted; V9 runtime остаётся в режиме **controlled maintenance**. V10 активирована владельцем командой `START V10` 2026-08-05.

## Перед началом

1. Прочитайте `AGENTS.md`.
2. Прочитайте `README.md` и `docs/README.md`.
3. Прочитайте `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитайте `knowledge/16_CURRENT_PROGRAM_STATUS.md` для текущего V9 runtime baseline.
5. Прочитайте `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`, `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` и `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
6. Прочитайте `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`, `docs/architecture/REPOSITORY_STRUCTURE.md`, `docs/architecture/V10_SECURITY_BOUNDARIES.md` и профильный current-WP architecture/runbook.
7. Для current GPT/config/recovery задач прочитайте `gpt/SETUP_INDEX.md` и `gpt/CONFIGURATION.md`.
8. Используйте `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` как завершённую specification/audit trail, а не как очередь незавершённых WP.
9. Проверьте актуальный `main`, открытые issues/PR и latest GitHub Actions.

Закрытые issues, merged PR и старые комментарии — **исторические снимки**. Если они противоречат accepted `main`, Program Lock или current status files, текущий source of truth имеет приоритет.

## Текущее состояние

- Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.
- Protected rollback: **v8.6.1**.
- Gateway entrypoint: `app:app`.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Runtime GPT Action authority: effective production `/openapi.json`.
- V9 runtime mode: **controlled maintenance**.
- V10 feature program: active; exact accepted progress/current WP is only `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## V10 sequence

V10 развивается строго по одному Work Package:

`restore context → current WP → focused branch → implementation/tests → security/boundary review → exact-head Regression Shield → zero unresolved review blockers → squash merge → status handoff → next WP`.

Нельзя начинать WP N+1 до acceptance Exit Gate WP N.

Не начинать Web/Telegram/AI/Lenovo/Real V10 runtime вне последовательности, даже если отдельная задача кажется простой.

## Неприкосновенные правила

### Product/runtime

- Не создавать второй Custom GPT, duplicate Gateway, parallel frontend/scheduler/AI stack или competing broker stack.
- Сохранять стабильный V9 Render entrypoint `app:app`, пока отдельный accepted V10 migration package не докажет replacement.
- Internal Python engine не считать GPT Action, если его operationId отсутствует в effective production OpenAPI.
- `docs/architecture/REPOSITORY_STRUCTURE.md` определяет canonical repository ownership.
- `scripts/check_v10_repository_boundaries.py` является обязательным структурным guard и не должен ослабляться ради merge.

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

`START V10`, development approval, AI output or alert acknowledgement is not broker-submit authorization.

### Data/security

- Account IDs remain masked in user-facing output.
- Never commit token/key values, Authorization headers, full account IDs, private broker payloads or secret exports.
- Currencies are not aggregated without verified FX + timestamp.
- Do not double-count payments, commissions, child operations or embedded trades.
- Partial/stale/truncated/contradictory data is never presented as complete/current truth.
- Generated lock files are not edited manually; `.in` files are canonical direct constraints.
- External GitHub Actions stay pinned to full commit SHA.

## Development/test bootstrap baseline

WP1 defines repository ownership; WP2 will freeze the exact V10 toolchain versions. Until WP2 acceptance, use the existing reviewed V9 development baseline and do not guess new frontend/DB/package-manager versions.

Safe local configuration starts from `.env.example`. Real secret values stay outside GitHub.

Existing Python dependency sources/locks:

- `requirements.in`;
- `requirements.txt`;
- `requirements-dev.in`;
- `requirements-dev.txt`.

Minimal existing Windows/Python verification commands are the same commands used by current Regression Shield. A new developer must be able to clone GitHub, create local configuration from safe examples, install from hash-locked dependencies and run the gates without access to the original ChatGPT account.

## Рабочий процесс

Для каждого существенного V9 maintenance package или V10 Work Package:

1. Создайте branch от актуального `main`.
2. Зафиксируйте точный current WP/defect и source of truth.
3. Сделайте одно логическое изменение в пределах current scope.
4. Добавьте или обновите deterministic tests/guards.
5. Обновите существующие canonical docs; не создавайте competing setup/audit/inventory sources.
6. Откройте Pull Request.
7. Дождитесь **exact-head Regression Shield + security**.
8. Убедитесь, что unresolved review threads = 0.
9. Выполните squash merge.
10. Обновите current V10 status/handoff только из accepted evidence.
11. Если изменился applied GPT config или reviewed Action contract, отдельно выполните owner Preview/`Update` acceptance на **том же** GPT и запишите non-secret evidence.

Repository merge сам по себе не меняет GPT Editor и не расширяет Real-money authority.

## Минимальные проверки

Основной merge gate — `.github/workflows/regression-shield.yml`. Локально/в CI применяются, среди прочего:

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
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

- какой V10 WP или V9 maintenance defect выполняется;
- что изменено и почему;
- какие runtime/data/GPT contours затронуты;
- как сохранены credential and authority boundaries;
- менялся ли OpenAPI/operationId/GPT Editor contract;
- какие tests/guards выполнены;
- какие canonical docs обновлены;
- какие dependencies/locks/Action SHAs затронуты;
- что проверить после merge/deploy;
- требуется ли owner Preview/`Update` или это backend/doc-only package;
- какой rollback path остаётся действующим.

## Исторические записи GitHub

Не переписывайте исторический смысл merged PR/closed issue так, будто он всегда описывал текущее состояние. Если старый thread может ввести в заблуждение, добавьте явную supersession/current-state заметку и ссылку на current status. Current status должен жить в canonical files, а не в случайном старом комментарии.
