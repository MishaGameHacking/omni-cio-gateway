# Changelog

Все заметные изменения Omni-CIO фиксируются здесь. Источник истины по коду — ветка `main`; подробности релизов находятся в соответствующих Pull Request.

## [Unreleased]

### Added
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
