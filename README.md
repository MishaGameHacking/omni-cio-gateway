# Omni-CIO Gateway

Приватный **read-only** шлюз между Custom GPT Omni-CIO и T-Invest API. Репозиторий является единым техническим центром управления backend, конфигурацией помощника, тестами, документацией и обезличенной проектной памятью.

## Текущее состояние

- Runtime: **v3.9.1 Broker Report Async Integrity**.
- Production entrypoint: `app:app`.
- Публичные пользовательские endpoints: только `GET`.
- `trading_methods=false`.
- Создание, отправка, замена и отмена заявок запрещены.
- Официальный брокерский отчёт формируется асинхронно.
- T-Invest `30058` трактуется как штатное состояние `pending`.
- Максимальный период одного официального отчёта: `31` день.

## Начать работу

### Новый чат, Codex, Copilot или IDE

Прочитайте по порядку:

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/README.md`](docs/README.md)
3. [`knowledge/00_PROJECT_MASTER_CONTEXT.md`](knowledge/00_PROJECT_MASTER_CONTEXT.md)
4. [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md)
5. [`gpt/ACTIONS_CATALOG.md`](gpt/ACTIONS_CATALOG.md)
6. профильный файл из [`knowledge/`](knowledge/)

Готовый стартовый запрос находится в [`gpt/NEW_CHAT_PROMPT.md`](gpt/NEW_CHAT_PROMPT.md).

## Карта репозитория

```text
app.py + runtime modules             backend gateway
broker_report_reconciliation/        официальный отчёт и сверка
tests/                               unit, endpoint, OpenAPI, Regression Shield
knowledge/                           строгие правила предметной области
gpt/                                 переносимая конфигурация Custom GPT
docs/architecture/                   архитектура и карта файлов
docs/operations/                     deploy и release runbooks
docs/inventory/                      реестр GitHub и внешних активов
scripts/                             безопасные локальные проверки
.github/                             CI, CODEOWNERS, PR и Issue templates
```

Полная схема: [`docs/architecture/REPOSITORY_STRUCTURE.md`](docs/architecture/REPOSITORY_STRUCTURE.md).

## Что хранится в GitHub

- весь backend-код gateway;
- OpenAPI-контракт и тесты;
- Render blueprint;
- правила безопасности и разработки;
- канонические инструкции Custom GPT;
- каталог Actions;
- проектная память и дорожная карта;
- runbooks и changelog.

## Что намеренно не хранится

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный номер брокерского счёта;
- реальные брокерские отчёты и операции пользователя;
- настройки публикации GPT и секретный Bearer key;
- Render secrets.

Полный реестр: [`docs/inventory/PROJECT_ASSETS.md`](docs/inventory/PROJECT_ASSETS.md).

## Основные документы

- [`AGENTS.md`](AGENTS.md) — обязательные правила для AI и разработчиков.
- [`CHANGELOG.md`](CHANGELOG.md) — история релизов.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — рабочий процесс.
- [`SECURITY.md`](SECURITY.md) — политика безопасности.
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md) — архитектура.
- [`docs/operations/DEPLOYMENT_RUNBOOK.md`](docs/operations/DEPLOYMENT_RUNBOOK.md) — Render deployment.
- [`docs/operations/RELEASE_CHECKLIST.md`](docs/operations/RELEASE_CHECKLIST.md) — Definition of Done.
- [`knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt`](knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt) — рынок и покупательная способность.
- [`knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt`](knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt) — операции.
- [`knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`](knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt) — асинхронный отчёт.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export TINVEST_TOKEN="..."
export GATEWAY_API_KEY="..."
export SSL_TBANK_VERIFY="True"
uvicorn app:app --reload
```

В Windows PowerShell используйте `$env:NAME="value"` вместо `export`.

## Проверки

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Дополнительно Regression Shield проверяет:

- актуальную версию runtime;
- `app:app`;
- уникальные operationId;
- Bearer authentication;
- явные OpenAPI object properties;
- отсутствие торговых endpoints;
- `trading_methods=false`;
- расчёты по валютам без скрытого FX.

## Деплой

Render использует [`render.yaml`](render.yaml):

```text
build: pip install -r requirements.txt
start: uvicorn app:app --host 0.0.0.0 --port $PORT
health: /health
```

После merge в `main` нужно проверить production `/health`, commit SHA и только затем обновлять OpenAPI schema в GPT Editor.

## Важная граница проекта

Исходный frontend существующего сайта Omni-CIO пока не закреплён за этим репозиторием. Не создавайте дубликат сайта. Состояние frontend и внешних компонентов ведётся в `docs/inventory/PROJECT_ASSETS.md`.
