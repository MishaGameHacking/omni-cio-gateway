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
├── telegram_bot/                  # Telegram Companion v4.0.0
│   ├── __init__.py                # версия компонента
│   ├── config.py                  # env configuration
│   ├── clients.py                 # Telegram и Gateway HTTP clients
│   ├── commands.py                # allowlist, команды и безопасность
│   └── app.py                     # entrypoint telegram_bot.app:app
├── tests/                         # unit, endpoint, OpenAPI, Regression Shield
├── knowledge/                     # правила предметной области для AI
├── gpt/                           # каноническая конфигурация Custom GPT
├── docs/
│   ├── architecture/              # архитектура и карта файлов
│   ├── operations/                # gateway и Telegram runbooks
│   └── inventory/                 # реестр компонентов и внешних активов
├── scripts/                       # локальные безопасные проверки
├── .github/                       # CI, templates и ownership
├── render.yaml                    # Gateway deploy contract
├── render.telegram.yaml           # Telegram deploy contract
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── project documentation
```

## Правила размещения

### Gateway runtime

В корне остаются файлы, необходимые для совместимости production gateway. Новые крупные функции не добавляются в `main.py`; они живут в отдельном модуле.

### `telegram_bot/`

Отдельный Python package для Telegram interface. Он не импортируется в Gateway `app.py`, не меняет его OpenAPI и разворачивается отдельным Render service.

Допустимые endpoints Telegram service:

- `GET /health`;
- `POST /telegram/webhook` — только входящий Telegram update с secret header.

Telegram package не содержит торговых методов и вызывает Gateway только GET-запросами.

### `knowledge/`

Нумерация:

- `00_` — общий контекст;
- `01_..08_` — базовые возможности;
- `09_` — рынок и покупательная способность;
- `10_` — операции;
- `11_` — асинхронный брокерский отчёт;
- `12_` — Telegram Companion.

### `gpt/`

Переносимая конфигурация Custom GPT. Telegram не заменяет эти файлы и не синхронизирует историю ChatGPT.

### `docs/`

Архитектура, runbooks, решения и inventory. Gateway и Telegram имеют отдельные deployment runbooks.

### `.github/workflows/`

Только постоянные workflow. Regression Shield проверяет оба entrypoint. Одноразовые patch workflow удаляются после релиза.

### `tests/`

Для Telegram нужны health, bootstrap, secret header, allowlist, GET-only gateway, report task reuse и duplicate-update tests. Реальные Telegram/T-Invest вызовы запрещены.

## Что нельзя переносить без отдельного PR

- `app.py` и `app:app`;
- `telegram_bot.app:app` после production запуска;
- wrapper-модули gateway;
- operationId и публичные Gateway paths;
- `/telegram/webhook` path после регистрации webhook;
- ключевые поля ответов, используемые Custom GPT и Telegram.

## Deployment separation

`render.yaml` управляет Gateway contract. `render.telegram.yaml` создаёт только Telegram service и намеренно не меняет существующий Gateway service.

## Будущий рефакторинг

Gateway-код может перейти в пакет `omni_cio_gateway/` только через compatibility migration. Telegram state может получить внешнее хранилище в отдельном релизе, но v4.0.0 не требует базы данных.
