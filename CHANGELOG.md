# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная история каждого старого PR остаётся в Git history; этот файл намеренно не дублирует сотни промежуточных инженерных пакетов.

## [Unreleased]

### Omni-CIO v9 Portfolio Autopilot — program development

- Owner-approved v9 program закреплён как единственный активный roadmap в `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`; стабильный v8.6.1 остаётся защищённым production baseline до завершения соответствующих v9 exit gates.
- WP0 Baseline freeze and recovery correctness завершён через PR #181; exact-head Regression Shield #989 прошёл.
- WP1 Natural Language CIO Router завершён через PR #184 и squash-merged в `main` как `7f6772889837ba632dc40c893d080a35b5f902ff` после exact-head Regression Shield #1002:
  - обычные русские запросы детерминированно маршрутизируются без знания Action names;
  - exact-action scope изолирован;
  - advice отделён от execution;
  - ambiguity fail closed;
  - router всегда возвращает `execution_authorized=false`.
- WP2 Investment Policy Statement Engine завершён через PR #187 и squash-merged в `main` как `75c9ae078309f32d1519b76cbedd89a221b62bf0` после exact-head Regression Shield #1014:
  - versioned owner IPS отделён от неперсонализированного `ConservativeRiskPolicyV1`;
  - objective, horizon, explicit liquidity reserve, risk willingness/capacity, max drawdown, concentration caps, credit floor, account/tax constraints и rebalance band моделируются явно;
  - allowed/prohibited markets and instrument classes проверяются на противоречия;
  - material deny constraints требуют owner provenance/confirmation;
  - system safe defaults не могут удовлетворять personal-policy provenance;
  - bond permission требует и rating floor, и named rating scale;
  - missing/invalid provenance, missing owner confirmation, stale/review-due, not-effective и superseded policy fail closed;
  - deterministic SHA-256 policy reference предназначен для будущих immutable plans;
  - margin, short, withdrawal, transfer и autonomous real execution остаются `Literal[False]`.
- WP3 Market Universe Engine завершён через PR #189 и squash-merged в `main` как `5ae81aa921999a6d4b1bb15aa0c506f7dea92a3f` после exact-head Regression Shield #1019:
  - universe строится из T-Invest `Shares`, `Bonds`, `Etfs` с `INSTRUMENT_STATUS_BASE`, без LLM/`FindInstrument` brute-force enumeration;
  - сохраняются UID/position_uid/FIGI/ISIN/ticker+class_code и broker eligibility evidence;
  - exact duplicates удаляются, stable-alias identity conflicts fail closed;
  - account qualification обновляется отдельно от кэшируемого broker catalog, без сохранения `user_id`/full account ID;
  - incomplete sources, invalid rows, unknown account eligibility и conflicts не становятся `decision_ready`;
  - catalog fingerprint source-order invariant и mutation-sensitive;
  - cache хранит только complete/validated BASE catalog, а degraded catalog не кэшируется;
  - repository guard запрещает universe package использовать `FindInstrument`, trading/Sandbox mutation credentials and services.
- WP4 Deterministic Candidate Funnel завершён через PR #191 и squash-merged в `main` как `3946fc9af995338504dee8002c82c630ab8629b7` после exact-head Regression Shield #1035:
  - portfolio gap → role → hard blockers → ordinal score → CASH comparison → bounded WP5 shortlist;
  - неполное evidence coverage всего policy+role-eligible universe fail closed и не публикует частичный ranking;
  - stale/future/untrusted market evidence блокируется до score;
  - fixed factor weights проверяются самим Pydantic contract, LLM score injection отсутствует;
  - `NO_ACTION/CASH` всегда присутствует и может занять первое место;
  - minimum-lot affordability и one-lot position/group/sector/currency headroom проверяются до shortlist;
  - bond price points и per-lot accrued interest обрабатываются без share-style арифметической ошибки;
  - ranking, tie-breaks и funnel SHA-256 детерминированы и source-order invariant;
  - candidate runtime остаётся pure/internal и repository guard запрещает broker SDK/tokens/mutation services.
- WP5 Research & Evidence Engine завершён через PR #194 и squash-merged в `main` как `f8f0bb95fc9692d68ce89c820a6ccbd1ff9868aa` после exact-head Regression Shield #1043:
  - bounded WP4 shortlist превращается в source-backed research dossiers с точной привязкой к funnel/candidate/instrument identity;
  - source hierarchy приоритизирует broker/exchange/issuer/official disclosure/regulator/rating agency, а media остаётся contextual secondary evidence;
  - material facts несут source provenance, timestamps, freshness и canonical record SHA-256;
  - T-Invest structured research adapter нормализует asset fundamentals, report schedules, dividends и bond events;
  - external/prompt-injection-shaped text остаётся inert data и не может менять control flow или execution authority;
  - bounded retrieval, deterministic cache keys/TTLs и rate-limit policy закреплены контрактами;
  - contradictions эксплицитны, а unresolved critical contradiction блокирует strong recommendation;
  - dossier fingerprint детерминирован и source-order invariant;
  - no broker mutation, public execution route, OpenAPI or GPT Editor change in WP5.
- WP6 Credit, Rating & Default Engine 2.0 завершён через PR #196 и squash-merged в `main` как `643160085520f1a2a333385aa7431d1b595b2eef` после exact-head Regression Shield #1057:
  - Credit Passport привязан к exact WP5 dossier fingerprint и WP2 policy reference;
  - issue / issuer / guarantor / guarantee / seniority моделируются раздельно;
  - material credit inputs ссылаются на decision-grade WP5 evidence hashes;
  - ACRA, Expert RA, NKR и NRA Russian national scales моделируются явно, agency/scale compatibility contract-enforced;
  - incompatible scales не усредняются и не получают скрытый crosswalk;
  - minimum credit floor сравнивается детерминированно на совместимой named scale;
  - issue rating предпочтителен, issuer proxy и eligible guarantor basis маркируются явно;
  - maturity/offer/coupon/amortization/collateral/guarantee terms структурированы;
  - optional leverage/coverage/liquidity/12-month refinancing metrics provenance-bound и не фабрикуются при отсутствии данных;
  - default, technical default, restructuring и payment delay сохраняются как отдельные события, active events fail closed;
  - current rating state определяется по latest effective observation, а same-timestamp contradictions fail closed;
  - dossier/policy/rating/outlook/watch/default/terms/financial changes создают deterministic re-analysis triggers;
  - passport SHA-256 детерминирован и source-order invariant;
  - repository guard защищает WP5 research и WP6 credit runtime boundaries;
  - no broker mutation, public execution route, OpenAPI or GPT Editor change in WP6.
- WP7 Fund X-Ray Engine завершён через PR #198 и squash-merged в `main` как `15505272872681cb7c3ad1e845affaa79f6ebdc1` после exact-head Regression Shield #1064; blocking dependency hardening #202 включено в WP8 PR #201:
  - ETF wrapper связывается с exact WP5 research target и full WP3 `InstrumentIdentity` / universe fingerprint;
  - composition states различают full holdings, partial holdings, documented exposure buckets и unavailable;
  - partial holdings не нормализуются до 100%, undisclosed residual остаётся `UNKNOWN`;
  - asset-class/sector/currency/issuer/geography look-through выводится только из disclosed weights;
  - WP7 schema v1.1 добавляет credit-quality look-through с `UNKNOWN` preservation и weighted duration вместе с measured coverage, без extrapolation partial evidence;
  - top-1/top-5 и HHI показывают hidden concentration для holdings-based composition;
  - direct-holding overlap и fund-to-fund overlap вычисляются детерминированно;
  - manager/benchmark/strategy/AUM/turnover/tracking-error/expense metadata остаётся optional/provenance-bound;
  - stale composition fail closed, missing composition не фабрикуется;
  - xray SHA-256 детерминирован и source-order invariant;
  - fund runtime pure/internal и repository guard запрещает broker SDK/tokens/mutation services;
  - no public execution route, OpenAPI or GPT Editor change in WP7.
- WP8 Portfolio Risk Engine 2.0 находится в активной разработке через issue #199 / draft PR #201:
  - exact portfolio snapshot и recomputed WP2 IPS fingerprint связывают risk state с конкретной политикой и данными;
  - permanent-loss, market, concentration, liquidity, credit, currency, inflation/opportunity и data-quality сохраняются как восемь независимых vectors; composite score отсутствует;
  - cross-currency positions требуют explicit FX provenance, exact native→base reconciliation и freshness;
  - Top-1/Top-3/Top-5 плюс position/issuer/group/sector/asset-class/currency concentration считаются детерминированно;
  - ETF требуют WP7 Fund X-Ray look-through, caller-supplied `POSITION` exposure запрещён для защиты от wrapper/underlying double counting;
  - exact-X-Ray-bound Fund Credit Summary сохраняет applicable/assessed/unknown/floor-breach/default weights и не выводит credit safety из wrapper ETF;
  - direct bonds требуют WP6 credit evidence; default и IPS credit-floor breach остаются hard blockers;
  - owner liquidity reserve, stale/missing liquidity, spread и position-size-aware exit capacity учитываются отдельно;
  - deterministic stress scenarios проверяют owner max-drawdown;
  - hypothetical trade effects строят полный after-state, новые/устранённые blockers и канонический SHA, invariant к порядку эквивалентных trade effects;
  - SYSTEM_GUARDRAIL не может притворяться owner-confirmed hard policy;
  - `omni_cio/risk` pure/read-only и repository-guarded; no broker mutation/public route/OpenAPI/GPT Editor change.
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
