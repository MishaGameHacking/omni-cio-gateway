# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная история каждого старого PR остаётся в Git history; этот файл намеренно не дублирует сотни промежуточных инженерных пакетов.

## [Unreleased]

### Real-money execution v1 — default-off engineering release

- Issue #164 ведёт отдельную staged release программу реальных BUY/SELL без повышения прав существующего `TINVEST_TOKEN`.
- PR #168 добавил durable state contract и conditional real-money Actions: `getRealTradingStatus`, `prepareRealTrade`, `executeRealTrade`, `getRealOrderState`.
- PR #169 синхронизировал canonical GPT behavior/config до `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Real v1 поддерживает только supported cash share/ETF, RUB, BUY/SELL, LIMIT/CURRENCY/DAY, own-funds/own-position.
- Margin/short, MARKET/BESTPRICE, derivatives/currencies, stop orders, ReplaceOrder, async submit, transfer/withdrawal, autonomous execution и first-release real cancellation отсутствуют.
- Proposal immutable/HMAC-bound; exact phrase требуется новым user message; preflight повторяется перед submit.
- UUID request id даёт idempotency; possible-submit ambiguity → `unknown_do_not_resubmit`; `submitted` не считается `filled` без broker proof.
- Hard per-order/daily limits и immutable code ceilings fail closed.
- Initial Phase 2 durable implementation used SQLite on `/var/data`, but Render Free does not support Persistent Disks.
- Current zero-cost migration replaces the **production default** journal with external Upstash Redis Free over HTTPS REST while keeping Render service on the Free plan.
- Free journal authenticates metadata, proposal envelopes and Moscow-day notional counters with application HMAC and uses atomic Redis Lua compare-and-swap for proposal/daily-cap reservation.
- Missing/unreachable/tampered durable storage publishes no usable real mutation path and never falls back to ephemeral memory.
- SQLite remains an explicit compatibility/test backend only.
- `REAL_TRADING_ENABLED=false` remains the safe default; no real order is authorized merely by deploying the code.

### T-Invest Sandbox execution

- PR #160 добавил изолированный optional T-Invest Sandbox-контур для виртуальных BUY/SELL; real-money production remained read-only at that release stage.
- Отдельный `TINVEST_SANDBOX_TOKEN` не заменяет существующий read-only `TINVEST_TOKEN`.
- `SANDBOX_TRADING_ENABLED=false` по умолчанию сохраняет прежний production Action surface.
- Добавлены Sandbox account/status/portfolio, proposal/preflight, confirmed submit, order-state и confirmed cancel.
- Виртуальная сделка двухфазная: immutable proposal → короткоживущее exact confirmation → submit.
- BUY/SELL limits проверяются при prepare и повторно непосредственно перед submit.
- Добавлены UUID idempotency, duplicate protection и fail-closed `unknown_do_not_resubmit` для неоднозначного timeout/5xx.
- Margin confirmation жёстко выключен; withdrawal/transfer, auto-replace и stop-order automation не добавлены.
- PR #162 исправил Render TLS/CA transport для T-Invest Sandbox REST без отключения проверки сертификатов.
- Owner Preview acceptance 2 августа 2026 подтвердил Sandbox status/account/funding/portfolio, MARKET BUY/SELL, own-position rejection, expiration rejection, exact-confirmation mismatch rejection, replay protection, LIMIT order state, cancel и последующую сверку виртуального портфеля.
- Во всех наблюдавшихся Sandbox-тестах `real_money=false`.

### Repository cleanup

- Консолидирована структура вокруг одного продукта: Omni-CIO Custom GPT + Gateway.
- `gpt/SETUP_INDEX.md` назначен единственной точкой настройки, обновления и восстановления.
- Исторические Instructions сохранены как fallback; current canonical behavior — v8.6.0.
- Удалены obsolete duplicate setup/instructions, dated audit/inventory artifacts и неиспользуемые external-transport artifacts.
- README/AGENTS/SECURITY/architecture/status синхронизируются с production endpoint `https://omni-cio-gateway.onrender.com`.
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
- Сохранены Bearer protection, masked account output и `app:app`.
- Portfolio, market, liquidity, operations, purchase-capacity и broker-report reconciliation workflows покрыты Regression Shield.
- Dependency/security baseline использует pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## История до текущего baseline

Полная инженерная последовательность, старые feature PR и прежние версии файлов доступны через Git commit/PR history. Они не являются текущей configuration-инструкцией и не должны использоваться вместо `main`, `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` и `gpt/SETUP_INDEX.md`.
