# Структура репозитория

## Каноническое дерево

```text
omni-cio-gateway/
├── app.py                         # стабильный gateway entrypoint
├── app_v371.py                    # архивный совместимый wrapper
├── app_v360.py                    # базовый legacy wrapper
├── main.py                        # историческое ядро FastAPI
├── *_analytics.py / *_market.py   # доменные gateway-модули
├── broker_report_reconciliation/  # официальный отчёт и сверка
├── omni_cio/
│   ├── contracts/v1/              # versioned typed read-only contracts
│   └── release/                   # internal final-review release chain
├── tests/                         # unit, endpoint, OpenAPI, Regression Shield
├── knowledge/                     # правила предметной области для AI
├── gpt/                           # каноническая конфигурация Custom GPT
├── docs/
│   ├── master-plan/               # исходная спецификация и поисковая копия
│   ├── architecture/              # архитектура и карта файлов
│   ├── operations/                # gateway и migration runbooks
│   └── inventory/                 # реестр компонентов и внешних активов
├── scripts/                       # локальные безопасные проверки
├── .github/                       # CI, templates и ownership
├── render.yaml                    # Gateway deploy contract
├── requirements.in                # production constraints
├── requirements.txt               # pinned + SHA-256 runtime lock
├── requirements-dev.in            # development constraints
├── requirements-dev.txt           # pinned + SHA-256 development lock
├── pyproject.toml                  # Ruff, mypy, pytest, coverage, Bandit
├── .env.example
└── project documentation
```

## Правила размещения

### Gateway runtime

В корне остаются файлы, необходимые для совместимости production gateway. Новые крупные функции не добавляются в `main.py`; они живут в отдельном модуле.

Versioned domain contracts размещаются в `omni_cio/contracts/v1/`. Внутренние
final-review coordinators, adapters, registries, owner-acquisition и
owner-installation boundaries размещаются в `omni_cio/release/`; они не создают
публичный Action автоматически. Публичная регистрация остаётся явной и
проверяется 14-GET release contract.

PR-80 `final_decision_review_approved_owner_installation_v1.py` является
одноразовым typed adapter между существующими PR-78 owner ports и PR-79
acquisition. Он не является HTTP handler, source-publication route или
calculator implementation.

### Retired transport paths

`telegram_bot/`, `render.telegram.yaml` и `/telegram/webhook` удалены.
Repository checks должны блокировать их случайное возвращение.

### `knowledge/`

Нумерация:

- `00_` — общий контекст;
- `01_..08_` — базовые возможности;
- `09_` — рынок и покупательная способность;
- `10_` — операции;
- `11_` — асинхронный брокерский отчёт;
- `12_` — решение о выводе Telegram runtime из эксплуатации.
- `13_` — communication profile;
- `14_` — CI, dependency и security baseline;
- `15_` — versioned contracts и data-quality профили;
- `16_` — фактическая вершина программы, acceptance и следующий пакет.

### `gpt/`

Переносимая конфигурация единственного поддерживаемого интерфейса — Custom GPT. `MY_GPT_SETUP_RUNBOOK.md` является канонической ручной процедурой подключения в ChatGPT → My GPTs.

### `docs/`

`master-plan/` хранит неизменяемый PDF, текстовую поисковую копию и правила приоритета. `architecture/`, `operations/` и `inventory/` хранят реализованную архитектуру, runbooks и реестр. Старый Telegram deployment имеет только retirement history/removal runbook.

### `.github/workflows/`

Только постоянные workflow. Regression Shield проверяет Gateway
entrypoint, read-only contract, отсутствие retired runtime, lock
integrity, quality, coverage и security. Все external Actions pinned
полным commit SHA. Одноразовые patch/bootstrap workflow удаляются до
merge.

### `tests/`

Обязателен отдельный тест отсутствия Telegram package, Blueprint,
configuration, imports и OpenAPI routes. Реальные T-Invest вызовы
запрещены.

`tests/test_ci_security_baseline.py` проверяет parser lock-файлов,
full-SHA Action policy и secret-scan report handling.

PR-80 тестируется отдельно: purchase/sell direction isolation, exact owner
call count, stale server context, operation mismatch, startup laziness и
отсутствие HTTP/broker-write surface.

## Что нельзя переносить без отдельного PR

- `app.py` и `app:app`;
- wrapper-модули gateway;
- operationId и публичные Gateway paths;
- ключевые поля ответов, используемые Custom GPT.

## Deployment separation

`render.yaml` является единственным deployment contract в репозитории.

## Будущий рефакторинг

Gateway-код может перейти в пакет `omni_cio_gateway/` только через
compatibility migration. Новый transport integration потребует
отдельного ADR и security review.
