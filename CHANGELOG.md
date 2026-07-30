# Changelog

Все заметные изменения Omni-CIO фиксируются здесь. Источник истины по коду — ветка `main`; подробности релизов находятся в соответствующих Pull Request.

## [Unreleased]

### Added
- Read-only final-review source acquisition adapter with four typed loader ports, selected
  buy/sell call routing, explicit available/missing/failed outcomes and safe timeout/type/
  timestamp error codes; exact artifacts and evidence are handed to PR-67 without payload,
  credential, account or exception-text logging and with `trading_methods=false`.
- Read-only final-review workflow coordinator with four canonical source slots, explicit
  available/missing/failed acquisition evidence, freshness/account/direction gates and exact
  evidence-to-artifact correspondence; incomplete or stale bundles never call PR-66, no
  payload/credential/full-account logging occurs and `trading_methods=false` is preserved.
- Live read-only final-review workflow producer from exactly one typed buy/sell pre-trade
  gate plus current/pro-forma risk evidence; producer reuses existing directional,
  account, freshness and exact-intent builders, derives requests only from retained source
  contracts, publishes review or safe no-action through PR-65 and keeps the 14-GET surface,
  no broker calls and `trading_methods=false`.
- Process-local final-review workflow bridge, зарегистрированный в `app.py` без нового
  route: bridge принимает typed risk/pre-trade evidence, строит pro-forma scenario и exact
  binding, вызывает PR-63 orchestration, публикует safe review/no-action response через
  PR-62 registry и сохраняет GET-only OpenAPI, `app:app`, отсутствие broker writes и
  `trading_methods=false`.
- Versioned final-review production-acceptance evidence contract and offline collector с
  восемью обязательными Render/Gateway/GPT/rollback case, статусами `not_executed`,
  `passed`, `failed`, `not_applicable`, canonical SHA-256 proof binding, dependency order,
  sensitive-data guards и запретом считать acceptance завершённой без восьми `passed`;
  collector не выполняет network/deploy/GPT changes и сохраняет `trading_methods=false`.
- End-to-end internal final-review orchestration, последовательно объединяющая PR-53
  response/shadow, PR-54 eligibility, PR-55 Action shadow, PR-56 input binding,
  PR-57 readiness, PR-58 route plan и PR-62 publication; первая заблокированная
  стадия останавливает цепочку, production OpenAPI не изменяется и
  `trading_methods=false` сохраняется.
- Internal final-review publisher с exact plan/binding context, one-lock-per-registry
  concurrency, `published/replaced` semantics, bounded-capacity eviction accounting,
  TTL/restart behavior и safe `ObservabilityEventV1`; publisher не создаёт HTTP method,
  не меняет OpenAPI, не вызывает брокера и сохраняет `trading_methods=false`.
- Production private `GET /decision/final-review` с exact eight-query identity,
  existing Gateway Bearer auth, `FinalDecisionReviewResponseV1`, bounded 15-minute/
  64-entry internal source registry, fail-closed 400/401/409/422/503 behavior и safe
  observability; маршрут не вызывает брокера, не пересчитывает решение и сохраняет
  `trading_methods=false`.
- Isolated test-only FastAPI final-review candidate с private `ApiKeyAuth`,
  exact eight-query contract, TestClient 200/400/401/409/422/503 coverage и
  проверкой candidate OpenAPI существующим GET-only release guard; production
  `app`, OpenAPI и Render не импортируются и не изменяются.
- Final-review handler shadow adapter с exact plan/input identity, fixed
  400/401/409/422/503 error mapping и safe `ObservabilityEventV1`; adapter не
  регистрирует route, не вызывает брокера и возвращает только PR-53 response.
- Machine-validated final-review route implementation plan и 13-case blocking
  acceptance matrix для pre-merge, post-deploy, GPT Editor Preview и rollback;
  все будущие проверки остаются `executed=false`, `passed=false`, route diff не
  применяется и implementation authorization не выдаётся.
- Final-review production-route readiness dossier, объединяющий PR-53 response,
  PR-54 eligibility, PR-55 Action shadow и PR-56 input binding с exact digest/
  context parity, private authentication, rollback и safe observability gates;
  результат разрешает только отдельный route review, но не сам route.
- Final-review read-only query/input binding с exact account, requested/final
  option, intent fingerprint, ordered instrument set, response/Action SHA-256,
  freshness и bounded allowlist; request body и execution/mutation/transfer/
  withdrawal/credential fields остаются запрещены.
- Final review GET Action candidate и OpenAPI shadow validation: фиксированный
  private/authenticated GET contract проверяется на deep-copy схемы существующим
  read-only release guard без добавления production route или изменения OpenAPI.
- Auditable final response release-eligibility assessment с canonical JSON,
  SHA-256, shadow parity, schema/account/payload/provenance gates и строгим
  ограничением будущего contract review только методом GET/read-only.
- Compact user-safe final decision-review response и internal shadow parity
  validation без раскрытия full account ID, source contracts или execution
  surface; source provenance очищается от `source_id`.
- Tamper-evident pro-forma risk/intention binding с SHA-256 fingerprint точного
  option, account context, direction и полного capacity-request set; результат
  остаётся review-only и явно сохраняет `trade_authorized=false`.
- Account-aware portfolio-risk/pre-trade explanation envelope с freshness,
  canonical layer attribution, fail-closed no-action и явным запретом считать
  current-portfolio risk полноценным pro-forma одобрением изменения.
- Unified directional pre-trade review envelope для однородного buy- или
  sell-intent set с fail-closed блокировкой смешанных направлений и без
  повторного расчёта брокерских значений.
- Read-only sell capacity/pre-trade decision gate с точной привязкой стороны,
  валюты, цены, размера лота и количества, а также fail-closed проверками
  позиции, открытых заявок, налоговой базы и комиссии.
- Hash-locked runtime и development dependency sets, генерируемые из
  `requirements.in` и `requirements-dev.in`.
- Blocking Ruff, formatting, mypy, coverage, pip-audit, Bandit и
  detect-secrets gates в Regression Shield.
- Self-test CI/security policy, weekly Dependabot и профиль
  `knowledge/14_CI_SECURITY_BASELINE.txt`.
- Retirement guard, который запрещает возврат `telegram_bot/`,
  `render.telegram.yaml`, Telegram imports, active env configuration и
  `/telegram/*` routes.
- `knowledge/12_TELEGRAM_RETIREMENT.txt` и post-merge runbook очистки
  внешнего Render service, webhook и token.
- Явный read-only allowlist T-Invest SDK для purchase preview:
  `users`, `instruments`, `orders.get_max_lots` и
  `orders.get_order_price`.
- Негативные тесты и AST-проверка, блокирующие broker order,
  stop-order, sandbox, withdrawal и transfer write-методы.
- Versioned financial contracts v1 и fail-closed portfolio market adapter.
- Portfolio contract shadow validation со статусами `ready`, `partial`,
  `rejected`, безопасными aggregate logs и отдельным decision-quality gate.
- `OperationsAnalyticsV1`: immutable Decimal-контракты операций, денежных
  потоков, оборота, пагинации, сверки и качества данных отдельно по валютам.
- Fail-closed adapter текущего `getOperationsAnalytics` payload в contract v1
  без изменения публичного Action response и без broker SDK imports.
- Девять contract/adapter-тестов для арифметики, multi-currency separation,
  masking, pagination, reconciliation, component errors и read-only guards.
- `AdvancedPortfolioAnalyticsV1`: exact per-currency structure, cash/invested
  weights, asset-class allocation, top-1/top-5 concentration, HHI, effective
  position count и deterministic stress sensitivities.
- Explicit missing-data records для issuer, sector, liquidity, historical
  prices, volatility, drawdown, correlation, tax basis и bond-specific inputs.
- Десять focused analytics tests, включая cash-only, multi-currency,
  repeating Decimal fractions, missing totals, currency mismatch, negative
  long-position value, incomplete valuation и naïve timestamp rejection.
- `ConservativeRiskPolicyV1` с независимыми threshold checks, состояниями
  `pass`, `warning`, `breach`, `unknown`, `not_applicable` и строгой
  блокировкой margin, shorts, derivatives и currency operations.
- `MarketResearchBundleV1` для instrument reference, quotes, liquidity,
  issuer/issue ratings, bond metrics и corporate events.
- Offline market readiness assessment по source authority, component coverage,
  value timestamps и freshness без сетевого fetch или нового Action.
- Exact Decimal spread arithmetic, fresh empty-event checks, withdrawn-rating
  handling и thirteen focused market contract/readiness tests.
- `NewsDocumentInputV1`, `SanitizedNewsDocumentV1` и auditable exact-dedup
  contracts для недоверенного внешнего текста и HTML.
- Offline stack-based HTML sanitization, NFKC/zero-width normalization,
  Russian/English prompt-injection flags и deterministic source ranking.
- Security tests для hidden/script content, tool/credential/code/trade/transfer
  instructions, oversized input, Unicode obfuscation, entity resolution и
  repeated-object deduplication.
- Сохранение полного mypy-вывода в краткоживущем Regression Shield artifact
  при сохранении блокирующего `pipefail`.
- Профиль Custom GPT `Modern Financial Sage — 2026`.
- Современный разговорный русский язык без банковского канцелярита.
- Обязательный перевод сложных финансовых терминов на человеческий язык.
- Понятная шкала риска: зелёный, жёлтый, оранжевый, красный.
- Разделение фактов, аналитических выводов и сценариев.
- Правила умеренной нецензурной лексики без оскорбления пользователя и без подмены анализа эмоциями.
- Отдельный стандарт Telegram-постов: короткие мобильные абзацы, главный вывод в начале, дата и источники.
- Профиль знаний `knowledge/13_COMMUNICATION_STYLE_2026.txt`.
- Компактный рабочий файл `gpt/INSTRUCTIONS_COMPACT.md`, рассчитанный на лимит 8000 символов GPT Editor.

### Removed
- Telegram Companion runtime package и его unit-тесты.
- Telegram Render Blueprint и active environment template.
- Telegram entrypoint, webhook, startup configuration и проверки из
  Regression Shield.

### Changed
- Render и GitHub Actions устанавливают зависимости только с
  `--require-hashes`.
- Все внешние GitHub Actions закреплены полными commit SHA.
- Начальный branch-inclusive coverage floor установлен на 60% после
  фактического измерения 60,8%.
