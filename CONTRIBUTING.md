# Вклад в Omni-CIO

Omni-CIO — один продукт. Текущий production/recovery runtime остаётся **existing Custom GPT v9.0.0 + production Gateway `app:app`**, а owner-approved V10 развивается последовательно в этом же репозитории.

V9 WP0–WP15 завершены и owner-accepted; V9 runtime остаётся в режиме **controlled maintenance**. V10 активирована владельцем командой `START V10` 2026-08-05.

## Перед началом

1. Прочитайте `AGENTS.md`.
2. Прочитайте `README.md`, `docs/README.md` и `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.
3. Прочитайте `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитайте `knowledge/16_CURRENT_PROGRAM_STATUS.md` для текущего V9 runtime baseline.
5. Прочитайте `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`, `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`, `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` и `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
6. Прочитайте `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`, `docs/architecture/REPOSITORY_STRUCTURE.md`, `docs/architecture/V10_SECURITY_BOUNDARIES.md` и профильный current-WP architecture/runbook.
7. Для current GPT/config/recovery задач прочитайте `gpt/SETUP_INDEX.md` и `gpt/CONFIGURATION.md`.
8. Используйте `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` как завершённую specification/audit trail, а не как очередь незавершённых WP.
9. Проверьте актуальный `main`, открытые issues/PR и latest GitHub Actions.

Закрытые issues, merged PR, package-local execution contracts и старые комментарии — **исторические снимки**. Если они противоречат accepted `main`, Program Lock, accepted amendments или current status files, текущий source of truth имеет приоритет.

## Текущее состояние

- Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.
- Protected rollback: **v8.6.1**.
- Gateway entrypoint: `app:app`.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Runtime GPT Action authority: effective production `/openapi.json`.
- V9 runtime mode: **controlled maintenance**.
- V10 feature program: active; exact accepted progress/current WP is only `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
- Engineering Quality / Pre-CI / Green-Merge governance: **accepted and active**.

Do not maintain a second `NEXT` or V10 percentage in this contributor guide.

## V10 sequence

V10 развивается строго по одному Work Package:

`restore authority → current WP/defect → focused branch → root-cause/blast-radius review → implementation/tests → cheap/focused preflight → full-diff review → all applicable exact-head checks SUCCESS → zero unresolved review blockers → squash merge → exact-main post-merge verification → OWNER acceptance only if required → status handoff → next WP`.

Нельзя начинать WP N+1 до acceptance Exit Gate WP N.

Не начинать Telegram/AI/later commercial-public/Real V10 runtime вне последовательности, даже если отдельная задача кажется простой.

## Неприкосновенные правила

### Product/runtime

- Не создавать второй Custom GPT, duplicate Gateway, parallel frontend/scheduler/AI stack или competing broker stack.
- Сохранять стабильный V9 Render entrypoint `app:app`, пока отдельный accepted V10 migration package не докажет replacement.
- Internal Python engine не считать GPT Action, если его operationId отсутствует в effective production OpenAPI.
- `docs/architecture/REPOSITORY_STRUCTURE.md` определяет canonical repository ownership.
- `scripts/check_v10_repository_boundaries.py`, `scripts/check_v10_engineering_governance.py` и `scripts/check_v10_documentation_consistency.py` являются обязательными guards и не должны ослабляться ради merge.

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

WP1 established repository ownership and WP2 **already selected and accepted** the reproducible V10 toolchain/dependency baseline.

Canonical V10 toolchain sources:

- `docs/architecture/V10_TOOLCHAIN_BASELINE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json`.

Do not infer versions from memory or blindly upgrade to `latest`. Material dependency/runtime changes follow accepted support/security/license/platform/reproducibility/rollback review and focused PR evidence.

Safe local configuration starts from `.env.example`. Real secret values stay outside GitHub.

Canonical Python dependency sources/locks:

- `requirements.in`;
- `requirements.txt`;
- `requirements-dev.in`;
- `requirements-dev.txt`.

A new developer must be able to clone GitHub, create local configuration from safe examples, install from reviewed locks and run the applicable gates without access to the original ChatGPT account.

## Рабочий процесс

Для каждого существенного V9 maintenance package, V10 Work Package или governance/documentation defect:

1. Создайте focused branch от актуального `main`.
2. Зафиксируйте точный current WP/defect и source of truth.
3. Установите root cause, blast radius и найдите аналогичные места до исправления material defect.
4. Сделайте минимальное логическое изменение в пределах current scope.
5. Добавьте или обновите deterministic tests/guards, если класс ошибки повторяемый.
6. Выполните все доступные cheap/focused preflight проверки: format/lint/type/compile, focused/negative tests, schema/config/IaC/PowerShell validation, dependency locks, secret/private-data guards, rollback/recovery review.
7. Обновите существующие canonical docs; не создавайте competing setup/audit/inventory/current-status sources.
8. Проверьте полный diff до запуска expensive final CI.
9. Откройте Pull Request.
10. Дождитесь **всех applicable exact-head checks с conclusion `success`**. `skipped`, `neutral`, `cancelled`, `pending` и инфраструктурный RED не являются GREEN evidence для applicable gate.
11. Убедитесь, что unresolved blocking review threads = 0 и повторно просмотрите полный diff.
12. Выполните squash merge.
13. Проверьте exact new `main` и обязательный post-merge Regression Shield/профильные post-merge gates.
14. Обновите current V10 status/handoff только из accepted evidence.
15. OWNER product acceptance выполняется только после merge + required post-merge GREEN и только там, где её требует owning Exit Gate.
16. Если изменился applied GPT config или reviewed Action contract, отдельно выполните owner Preview/`Update` acceptance на **том же** GPT и запишите non-secret evidence.

Repository merge сам по себе не меняет GPT Editor и не расширяет Real-money authority.

## Минимальные проверки

Точный набор команд и routing определяет текущая repository governance. Среди постоянных проверок:

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Dependency audit, SAST, secret scan, frontend type/lint/test/build/audit and current-WP focused checks run where applicable. Do not weaken a gate to make a PR green.

## Требования к Pull Request

PR должен объяснять:

- какой V10 WP, V9 maintenance defect или governance/documentation defect выполняется;
- root cause и blast radius для material defect;
- что изменено и почему;
- какие runtime/data/GPT contours затронуты;
- как сохранены credential and authority boundaries;
- менялся ли OpenAPI/operationId/GPT Editor contract;
- какие cheap/focused preflight checks и exact-head gates выполнены;
- какие deterministic regression guards добавлены;
- какие canonical docs обновлены;
- какие dependencies/locks/Action SHAs затронуты;
- какой rollback path остаётся действующим;
- требуется ли post-merge OWNER acceptance и почему.

## Исторические записи GitHub

Не переписывайте исторический смысл merged PR/closed issue/WP record так, будто он всегда описывал текущее состояние. Если старый файл может ввести в заблуждение, добавьте явную lifecycle/supersession заметку и ссылку на current status.

Current status должен жить в canonical status files, а не в случайном старом комментарии. Полная классификация — `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.