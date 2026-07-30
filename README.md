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
  публичный Action response остаётся без изменений, а будущие decision flows
  получают отдельный fail-closed quality gate.
- Private `GET /decision/final-review` возвращает только ранее сформированный и
  проверенный compact response из bounded TTL source registry. Пустой registry
  fail-closed возвращает `503`; маршрут не вызывает брокера и не создаёт решение
  заново.
- PR-79 добавляет внутренний acquisition-контроллер: invocation и masked account
  берутся только из доверенного server context, все пять выбранных owner sources должны
  быть свежими до PR-78, а production startup остаётся безопасно `unavailable` без
  конкретных loaders. OpenAPI и 14 GET Actions не меняются.
- PR-80 добавляет concrete typed installation boundary для уже существующих PR-78
  purchase/sell owner ports. Один immutable server context получает фиксированные
  PR-79 loaders только на время одного вызова; startup не выполняет installation,
  owner calls, portfolio/network/broker calls.
- PR-81 сохраняет из trusted publication только exact scenario ID, trusted
  correlation, direction и masked account, а после existing Bearer auth и exact
  route validation создаёт server-generated approved context. Контекст хранится
  не более 300 секунд в bounded process-local store; owner selection и PR-80
  invocation остаются отдельным следующим пакетом.
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
- содержимое bounded final-review и approved-context registries после остановки процесса.

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
- [`docs/architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_V1.md`](docs/architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_V1.md) — exact typed PR-78 owner ports into one PR-79 acquisition call.
- [`docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_ROUTE_CONTEXT_V1.md`](docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_ROUTE_CONTEXT_V1.md) — trusted publication seed, post-auth approved context и bounded lifecycle.
- [`docs/operations/DEPLOYMENT_RUNBOOK.md`](docs/operations/DEPLOYMENT_RUNBOOK.md) — gateway deployment.
- [`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md) — очистка выведенного Telegram service.
- [`knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`](knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt) — асинхронный отчёт.
- [`knowledge/12_TELEGRAM_RETIREMENT.txt`](knowledge/12_TELEGRAM_RETIREMENT.txt) — запрет возврата Telegram runtime без нового ADR.
- [`knowledge/13_COMMUNICATION_STYLE_2026.txt`](knowledge/13_COMMUNICATION_STYLE_2026.txt) — современная речь и публикации.
- [`knowledge/14_CI_SECURITY_BASELINE.txt`](knowledge/14_CI_SECURITY_BASELINE.txt) — dependency locks, quality и security gates.
- [`knowledge/15_DATA_QUALITY_SHADOW_VALIDATION.txt`](knowledge/15_DATA_QUALITY_SHADOW_VALIDATION.txt) — статусы качества и fail-closed gate.

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
python -m bandit -c pyproject.toml -r . -ll -ii -q
```

Regression Shield контролирует стабильный `app:app`, отсутствие Telegram
runtime/configuration, отсутствие торговых функций,
`trading_methods=false`, dependency supply chain и минимальный quality/
security baseline. Полная команда secret scan закреплена непосредственно
в workflow, чтобы shell использовал `pipefail`.

## Деплой

- Gateway: [`render.yaml`](render.yaml), entrypoint `app:app`.
- Функциональная вершина и следующий пакет указаны в `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
- Render/Gateway/GPT/rollback acceptance остаётся незавершённой, пока восемь реальных cases не зафиксированы как `passed`.

## Важная граница проекта

Исходный frontend существующего сайта Omni-CIO пока не закреплён за этим репозиторием. Не создавайте дубликат сайта.
