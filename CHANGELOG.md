# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная история каждого старого PR остаётся в Git history; этот файл намеренно не дублирует сотни промежуточных инженерных пакетов.

## [Unreleased]

### Omni-CIO v9 Portfolio Autopilot — program development

- Owner-approved v9 program закреплён как единственный активный roadmap в `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`; стабильный v8.6.1 остаётся защищённым production baseline до завершения соответствующих v9 exit gates.
- WP0 Baseline freeze and recovery correctness завершён через PR #181: recovery/configuration sources согласованы с v8.6.1, protected baseline commit зафиксирован, v9 program lock и правило earliest dependency-ready incomplete WP проверяются автоматически; exact-head Regression Shield #989 прошёл.
- WP1 Natural Language CIO Router завершён через PR #184 и squash-merged в `main` как `7f6772889837ba632dc40c893d080a35b5f902ff` после exact-head Regression Shield #1002:
  - versioned `IntentRouteV1` классифицирует обычные русские запросы на analysis, portfolio management, risk, research, cash allocation, plan review, execution, monitoring и diagnostics;
  - exact-action scope остаётся изолированным, а разговорное упоминание Action не считается вызовом;
  - advisory `стоит ли купить/продать` отделён от imperative execution;
  - bare BUY/SELL, real/Sandbox ambiguity и BUY/SELL ambiguity fail closed;
  - router всегда возвращает `execution_authorized=false`; v8.6.1 server confirmation/HMAC/TTL/idempotency/preflight остаются авторитетными;
  - raw user free text не сохраняется в routing state;
  - расширенный Russian acceptance corpus покрывает распространённые опечатки и неоднозначности.
- WP2 Investment Policy Statement Engine разрабатывается как internal/additive слой без изменения `app.py`, OpenAPI, broker clients или applied GPT:
  - versioned owner IPS отделён от неперсонализированного `ConservativeRiskPolicyV1`;
  - objective, horizon, explicit liquidity reserve, risk willingness/capacity, max drawdown, concentration caps, credit floor, account/tax constraints и rebalance band моделируются явно;
  - allowed/prohibited markets and instrument classes проверяются на противоречия;
  - material deny constraints требуют provenance и owner confirmation;
  - system safe defaults не могут удовлетворять owner policy provenance для personal sizing;
  - missing/invalid provenance, missing owner confirmation, stale/review-due, not-effective и superseded policy fail closed;
  - deterministic SHA-256 policy reference предназначен для будущих immutable plans;
  - margin, short, withdrawal, transfer и autonomous real execution остаются `Literal[False]`.
- Applied Custom GPT остаётся v8.6.1 до WP15; текущая v9 разработка не является разрешением на более широкий real-money execution.

### Omni-CIO v8.6.1 — released / owner accepted

- GPT Editor payload переведён на `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`, который помещается в текущий лимит Instructions; полный v8.6.0 остаётся engineering reference.
- UI-name владельцем обновлён до `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Production OpenAPI повторно импортирован; saved GPT видит read-only, Sandbox и conditional Real Trading surfaces.
- Permanent Upstash Redis Free настроен как production durable real journal; Render остаётся Free, Persistent Disk не требуется.
- Dedicated `TINVEST_TRADING_TOKEN` настроен отдельно от неизменяемого read-only `TINVEST_TOKEN`.
- Owner Phase 3 acceptance 3 августа 2026 прошёл с нулевым real submit:
  - real readiness `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`;
  - technical LIMIT proposal создаётся без submit;
  - expired confirmation → rejection, zero submit;
  - wrong confirmation → rejection before execute, zero submit;
  - excessive BUY блокируется own-funds guard without margin fallback;
  - read-only exact-action path остаётся изолированным;
  - kill switch `REAL_TRADING_ENABLED=false` успешно возвращает Gateway в healthy read-only state;
  - re-enable восстанавливает ready state и durable proposal rows.
- Hard-cap, stale-market, SELL-over-position, replay and ambiguous-submit protections покрыты fake-client/regression tests; live tests не форсировались, если для этого пришлось бы ослабить более ранние safety gates.
- Owner Phase 4 acceptance 3 августа 2026 завершён:
  - владелец явно разрешил первую controlled real trade;
  - подготовлена и отправлена одна реальная LIMIT BUY заявка SBER на 1 лот;
  - broker state reconciled to `EXECUTION_REPORT_STATUS_FILL`, `lots_executed=1`, `fill_confirmed=true`;
  - цена исполнения 280.55 RUB, комиссия 0.84 RUB;
  - real portfolio reconciled: SBER = 1 акция / 1 лот;
  - operations history reconciled: executed purchase 280.55 RUB + commission 0.84 RUB;
  - exact confirmation replay returned the already submitted/filled proposal state and did not call `executeRealTrade` again;
  - no second broker submit was created.
- Real BUY/SELL v1 Definition of Done полностью закрыт. Release status: **100% complete**.

### Real-money execution v1 engineering

- Issue #164 ведёт staged release программу реальных BUY/SELL без повышения прав существующего `TINVEST_TOKEN`.
- PR #168 добавил durable state contract и conditional real-money Actions: `getRealTradingStatus`, `prepareRealTrade`, `executeRealTrade`, `getRealOrderState`.
- PR #169 синхронизировал full v8.6 behavior reference.
- PR #170 заменил production durable journal на external Upstash Redis Free over HTTPS REST while keeping Render Free.
- Real v1 поддерживает только supported cash share/ETF, RUB, BUY/SELL, LIMIT/CURRENCY/DAY, own-funds/own-position.
- Margin/short, MARKET/BESTPRICE, derivatives/currencies, stop orders, ReplaceOrder, async submit, transfer/withdrawal, autonomous execution и real cancellation отсутствуют.
- Proposal immutable/HMAC-bound; exact phrase требуется новым user message; preflight повторяется перед submit.
- UUID request id даёт idempotency; possible-submit ambiguity → unknown/do-not-resubmit; `submitted` не считается `filled` без broker proof.
- Hard per-order/daily limits и immutable ceilings fail closed.
- Journal authenticates metadata, proposal envelopes and Moscow-day counters and uses atomic Redis Lua compare-and-swap.
- Missing/unreachable/tampered durable storage publishes no usable real mutation path and never falls back to ephemeral memory.

### T-Invest Sandbox execution

- PR #160 добавил изолированный optional Sandbox-контур для virtual BUY/SELL.
- `TINVEST_SANDBOX_TOKEN` не заменяет `TINVEST_TOKEN`.
- `SANDBOX_TRADING_ENABLED=false` сохраняет production baseline surface.
- Sandbox proposal → exact confirmation → submit, with repeated limits, UUID idempotency and ambiguous-submit no-retry.
- Margin confirmation off; withdrawal/transfer/auto-replace/stop automation absent.
- PR #162 исправил Render TLS/CA transport для Sandbox REST без отключения certificate verification.
- Owner Preview acceptance 2 августа 2026 подтвердил Sandbox account/funding/portfolio, MARKET BUY/SELL, own-position rejection, expiry/mismatch rejection, replay protection, LIMIT state/cancel и reconciliation.
- Sandbox responses remain `real_money=false`.

### Repository cleanup

- Структура консолидирована вокруг одного продукта: Omni-CIO Custom GPT + Gateway.
- `gpt/SETUP_INDEX.md` — единая точка настройки/восстановления.
- Current GPT Editor behavior — v8.6.1 Compact; v8.6.0 — full reference.
- Runtime dependencies `app_v371.py`, `app_v360.py` и `main.py` намеренно сохранены, потому что current `app.py` всё ещё их импортирует.

## [2026-08-02] Custom GPT v8.4.1 acceptance

- PR #146 сделал portfolio-management routing tool-first.
- Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` обязательна цепочка `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics` до анализа.
- Exact-action запросы изолированы.
- Recommended model зафиксирован как Thinking 5.6.
- Canonical endpoint: `https://omni-cio-gateway.onrender.com`.
- User-visible timezone: Europe/Moscow / MSK.
- Market gate блокирует exact personalized sizing при отсутствии fresh best ask / market readiness.
- Production Knowledge set: ровно 10 файлов.

## [2026-08-01] Gateway v3.10.0 baseline

- Read-only Gateway surface стабилизирован на 14 GET Actions.
- Добавлен private read-only `getFinalDecisionReview` contract.
- Сохранены Bearer protection, masked account output и `app:app`.
- Portfolio, market, liquidity, operations, purchase-capacity и broker-report workflows покрыты Regression Shield.
- Security baseline использует pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## История до текущего baseline

Полная инженерная последовательность доступна через Git commit/PR history. Старые версии не являются текущей configuration-инструкцией и не должны использоваться вместо `main`, `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` и `gpt/SETUP_INDEX.md`.
