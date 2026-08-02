# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная история каждого старого PR остаётся в Git history; этот файл намеренно не дублирует сотни промежуточных инженерных пакетов.

## [Unreleased]

### T-Invest Sandbox execution

- PR #160 добавил изолированный optional T-Invest Sandbox-контур для виртуальных BUY/SELL; real-money production остаётся read-only.
- Отдельный `TINVEST_SANDBOX_TOKEN` не заменяет существующий read-only `TINVEST_TOKEN`.
- `SANDBOX_TRADING_ENABLED=false` по умолчанию сохраняет прежний production Action surface.
- Добавлены Sandbox account/status/portfolio, proposal/preflight, confirmed submit, order-state и confirmed cancel.
- Виртуальная сделка двухфазная: immutable proposal → короткоживущее exact confirmation → submit.
- BUY/SELL limits проверяются при prepare и повторно непосредственно перед submit.
- Добавлены UUID idempotency, duplicate protection и fail-closed `unknown_do_not_resubmit` для неоднозначного timeout/5xx.
- Margin confirmation жёстко выключен; withdrawal/transfer, real order execution, auto-replace и stop-order automation не добавлены.
- Добавлен candidate `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` и owner runbook `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.
- Exact-head Regression Shield #909 прошёл quality/contracts/coverage и dependency/code/secret security до squash merge PR #160.

### Repository cleanup

- Консолидирована структура вокруг одного продукта: Omni-CIO Custom GPT + Gateway.
- `gpt/SETUP_INDEX.md` назначен единственной точкой настройки, обновления и восстановления.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` остаётся accepted production Instructions до Sandbox owner acceptance.
- Удалены obsolete duplicate setup/instructions, dated audit/inventory artifacts и неиспользуемые external-transport artifacts.
- Активные GPT Knowledge/communication files очищены от внешнего publishing behavior.
- README/AGENTS/SECURITY/architecture/status синхронизированы с production endpoint `https://omni-cio-gateway.onrender.com`.
- Runtime dependencies `app_v371.py`, `app_v360.py` и `main.py` намеренно сохранены, потому что current `app.py` всё ещё их импортирует.

## [2026-08-02] Custom GPT v8.4.1 acceptance

- PR #146 сделал portfolio-management routing tool-first.
- Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` обязательна цепочка `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics` до анализа.
- Exact-action запросы изолированы.
- Recommended model зафиксирован как Thinking 5.6 на основании Preview acceptance.
- Canonical production endpoint: `https://omni-cio-gateway.onrender.com`.
- User-visible timezone: Europe/Moscow / MSK.
- Market gate блокирует exact personalized sizing при отсутствии fresh best ask / market readiness.
- Production Knowledge set: ровно 10 файлов без дублей.

## [2026-08-01] Gateway v3.10.0 baseline

- Read-only Gateway surface стабилизирован на 14 GET Actions.
- Добавлен private read-only `getFinalDecisionReview` contract.
- Сохранены Bearer protection, masked account output, `app:app` и `trading_methods=false`.
- Portfolio, market, liquidity, operations, purchase-capacity и broker-report reconciliation workflows покрыты Regression Shield.
- Dependency/security baseline использует pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## История до текущего baseline

Полная инженерная последовательность, старые feature PR и прежние версии файлов доступны через Git commit/PR history. Они не являются текущей configuration-инструкцией и не должны использоваться вместо `main`, `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` и `gpt/SETUP_INDEX.md`.
