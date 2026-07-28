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
├── tests/                         # unit, endpoint, OpenAPI, Regression Shield
├── knowledge/                     # правила предметной области для AI
├── gpt/                           # каноническая конфигурация Custom GPT
├── docs/
│   ├── architecture/              # архитектура и карта файлов
│   ├── operations/                # gateway и migration runbooks
│   └── inventory/                 # реестр компонентов и внешних активов
├── scripts/                       # локальные безопасные проверки
├── .github/                       # CI, templates и ownership
├── render.yaml                    # Gateway deploy contract
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── project documentation
```

## Правила размещения

### Gateway runtime

В корне остаются файлы, необходимые для совместимости production gateway. Новые крупные функции не добавляются в `main.py`; они живут в отдельном модуле.

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

### `gpt/`

Переносимая конфигурация единственного поддерживаемого интерфейса —
Custom GPT.

### `docs/`

Архитектура, runbooks, решения и inventory. Старый Telegram deployment
имеет только removal runbook.

### `.github/workflows/`

Только постоянные workflow. Regression Shield проверяет Gateway
entrypoint, read-only contract и отсутствие retired runtime. Одноразовые
patch workflow удаляются после релиза.

### `tests/`

Обязателен отдельный тест отсутствия Telegram package, Blueprint,
configuration, imports и OpenAPI routes. Реальные T-Invest вызовы
запрещены.

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
