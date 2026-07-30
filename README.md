# Omni-CIO Control Center

Приватная read-only система инвестиционной аналитики. Поддерживаемый
пользовательский интерфейс находится в Custom GPT внутри ChatGPT:

```text
Custom GPT ── Omni-CIO Gateway (`app:app`) ── T-Invest API
```

## Текущее состояние

- System release: **v4.1.0 ChatGPT-only Runtime**.
- Gateway API component: **v3.10.0 Final Decision Review GET Route**.
- Custom GPT communication profile: **Modern Financial Sage — 2026**.
- Gateway production entrypoint: `app:app`.
- `trading_methods=false`.
- Создание, отправка, замена и отмена заявок запрещены.
- Telegram Companion выведен из эксплуатации; его package, Blueprint,
  webhook и активная конфигурация отсутствуют.
- Portfolio market snapshot проходит внутреннюю contract v1 shadow validation;
  публичный Action response остаётся без изменений, а decision flows получают
  отдельный fail-closed quality gate.
- Private `GET /decision/final-review` возвращает только ранее сформированный и
  проверенный compact response из bounded TTL registry. Пустой registry
  fail-closed возвращает `503`; маршрут не создаёт решение заново.
- PR-79…PR-80 формируют approved server-context acquisition и одноразовую
  установку существующих typed purchase/sell owner ports.
- PR-81…PR-83 завершают внутреннюю post-auth цепочку: trusted context capture →
  exact typed owner snapshot → fresh invocation rebinding → один PR-80 call →
  bounded redacted evidence. Missing, stale или mismatched data остаются
  fail-closed; public response и OpenAPI не меняются.
- PR-84 добавляет официальный read-only источник истории ключевой ставки Банка
  России `DailyInfo.KeyRateXML`: fixed HTTPS endpoint, bounded streaming,
  защищённый XML parser, Decimal-контракт, provenance и безопасные error codes.
- PR-85 добавляет exact-range process-local cache над PR-84: explicit
  fresh/stale/unavailable contract, single-flight refresh, TTL pruning,
  capacity eviction и запрет скрытого показа stale values. Cache остаётся
  internal-only и не добавляет новый Action или dashboard field.
- Runtime и CI устанавливают полностью pinned зависимости только после
  проверки SHA-256 hashes.
- Regression Shield включает lint, formatting baseline, mypy, покрытие
  не ниже 60%, SCA, SAST и secret scan.

## Начать работу

Новый чат, Codex, Copilot или IDE должны прочитать:

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/README.md`](docs/README.md)
3. [`docs/master-plan/README.md`](docs/master-plan/README.md)
4. [`docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`](docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt)
5. [`knowledge/00_PROJECT_MASTER_CONTEXT.md`](knowledge/00_PROJECT_MASTER_CONTEXT.md)
6. [`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md)
7. [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md)
8. [`gpt/ACTIONS_CATALOG.md`](gpt/ACTIONS_CATALOG.md)
9. профильный файл из [`knowledge/`](knowledge/)

Готовый стартовый запрос: [`gpt/NEW_CHAT_PROMPT.md`](gpt/NEW_CHAT_PROMPT.md).

## Карта репозитория

```text
app.py + runtime modules             Omni-CIO Gateway
omni_cio/contracts/                  versioned financial contracts
omni_cio/adapters/                   legacy-to-contract adapters
omni_cio/quality/                    shadow validation and quality gates
omni_cio/market/                     market, macro and capacity sources/analysis
omni_cio/release/                    read-only release, route and acceptance controls
broker_report_reconciliation/        официальный отчёт и сверка
tests/                               unit, endpoint, OpenAPI, Regression Shield
knowledge/                           строгие правила предметной области
gpt/                                 переносимая конфигурация Custom GPT
docs/master-plan/                    исходная спецификация развития
docs/architecture/                   архитектура и карта файлов
docs/operations/                     deploy и release runbooks
docs/inventory/                      реестр GitHub и внешних активов
scripts/                             безопасные локальные проверки
.github/                             CI, CODEOWNERS, PR и Issue templates
```

Полная схема: [`docs/architecture/REPOSITORY_STRUCTURE.md`](docs/architecture/REPOSITORY_STRUCTURE.md).

## Custom GPT: современный стиль 2026

Канонический файл [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md) задаёт единый стиль анализа и публикаций:

- главный вывод в первых предложениях;
- короткие абзацы без банковского канцелярита;
- перевод сложных терминов на человеческий язык;
- разделение факта, вывода и возможного сценария;
- понятная шкала риска;
- умеренный мат только как эмоциональный акцент, а не замена фактам;
- формат денег ru-RU для рублей и сохранение исходной валюты;
- мобильный формат публикаций с датой и источниками;
- сохранение GET-only и `trading_methods=false`.

Профиль знаний: [`knowledge/13_COMMUNICATION_STYLE_2026.txt`](knowledge/13_COMMUNICATION_STYLE_2026.txt).

GitHub хранит канонические инструкции, но не применяет их в GPT Editor автоматически. Точная настройка, Preview и rollback описаны в [`gpt/MY_GPT_SETUP_RUNBOOK.md`](gpt/MY_GPT_SETUP_RUNBOOK.md). OpenAPI повторно импортируется только после фактического изменения Action contract.

## ChatGPT-only runtime

Omni-CIO больше не содержит Telegram runtime. Полезная финансовая логика
не потеряна: она изначально находилась в Gateway, а удалённые модули
обслуживали только Telegram transport, команды и форматирование.

Внешняя очистка старого Telegram service, webhook и token завершена владельцем 2026-07-28. История и контрольные проверки сохранены в [`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md); основной service `omni-cio-gateway` остаётся единственным backend runtime.

## Что хранится в GitHub

- весь backend-код gateway;
- OpenAPI-контракт и тесты;
- Gateway Render Blueprint;
- правила безопасности и разработки;
- канонические инструкции Custom GPT;
- современный профиль общения и публикаций;
- каталог Actions;
- исходный master plan, проектная память и дорожная карта;
- runbooks и changelog.

## Что намеренно не хранится

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный номер брокерского счёта;
- реальные брокерские отчёты и операции пользователя;
- Render secrets и секретный GPT Bearer key;
- сырой XML Банка России и upstream fault/exception text;
- содержимое process-local CBR cache;
- содержимое bounded final-review, approved-context, owner-snapshot и evidence
  registries после остановки процесса.

Полный реестр: [`docs/inventory/PROJECT_ASSETS.md`](docs/inventory/PROJECT_ASSETS.md).

## Основные документы

- [`AGENTS.md`](AGENTS.md) — обязательные правила.
- [`CHANGELOG.md`](CHANGELOG.md) — история релизов.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — рабочий процесс.
- [`SECURITY.md`](SECURITY.md) — политика безопасности.
- [`docs/master-plan/README.md`](docs/master-plan/README.md) — исходная спецификация и иерархия источников.
- [`gpt/MY_GPT_SETUP_RUNBOOK.md`](gpt/MY_GPT_SETUP_RUNBOOK.md) — подключение в ChatGPT → My GPTs.
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md) — архитектура.
- [`docs/architecture/PORTFOLIO_SHADOW_VALIDATION_V1.md`](docs/architecture/PORTFOLIO_SHADOW_VALIDATION_V1.md) — shadow validation и decision gate.
- [`docs/architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md`](docs/architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md) — production GET route, registry и fail-closed HTTP contract.
- [`docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_V1.md`](docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_V1.md) — post-auth snapshot selection и one-shot installation.
- [`docs/architecture/CBR_KEY_RATE_SOURCE_V1.md`](docs/architecture/CBR_KEY_RATE_SOURCE_V1.md) — официальный источник ключевой ставки и security boundary.
- [`docs/architecture/CBR_KEY_RATE_CACHE_V1.md`](docs/architecture/CBR_KEY_RATE_CACHE_V1.md) — cache, freshness и stale/unavailable policy.
- [`docs/operations/DEPLOYMENT_RUNBOOK.md`](docs/operations/DEPLOYMENT_RUNBOOK.md) — gateway deployment.
- [`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md) — очистка выведенного Telegram service.
- [`knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt`](knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt) — market и macro source/cache semantics.
- [`knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`](knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt) — асинхронный отчёт.
- [`knowledge/14_CI_SECURITY_BASELINE.txt`](knowledge/14_CI_SECURITY_BASELINE.txt) — dependency locks, quality и security gates.
- [`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md) — фактическая вершина и остаток программы.

## Локальный запуск gateway

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
export TINVEST_TOKEN="..."
export GATEWAY_API_KEY="..."
export SSL_TBANK_VERIFY="True"
uvicorn app:app --reload
```

## Проверки

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python -m ruff check .
python -m ruff format --check scripts tests/test_ci_security_baseline.py
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
python -m pip_audit --require-hashes --disable-pip --strict \
  --vulnerability-service osv \
  --progress-spinner off -r requirements.txt
python -m bandit -q -lll -iii -r . \
  -x tests,.venv,venv,htmlcov,broker_report_reconciliation/_parts \
  --exclude "./broker_report_reconciliation/__init__.py"
python scripts/scan_tracked_secrets.py
```
