# AGENTS.md — Omni-CIO Project Rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, работающего с репозиторием.

## 1. Сначала восстановить контекст

Перед изменением кода:

1. Прочитать `README.md`.
2. Прочитать `docs/README.md`.
3. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитать `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если задача касается Custom GPT.
5. Прочитать профильный файл из `knowledge/`.
6. Проверить `main`, открытые PR, последние релизы и GitHub Actions.
7. Не считать старую переписку источником истины, если она расходится с кодом в `main`.

## 2. Неприкосновенный read-only режим

Запрещено добавлять или вызывать:

- создание заявки;
- отправку заявки;
- замену заявки;
- отмену заявки;
- стоп-заявки;
- любые другие методы, изменяющие брокерский счёт.

Обязательные инварианты:

- пользовательские Gateway Actions — только `GET`;
- `trading_methods=false`;
- Regression Shield отклоняет торговые operationId и mutating gateway routes.
- Telegram runtime выведен из эксплуатации и не должен появляться в
  Gateway, OpenAPI или deployment configuration.

## 3. Секреты и персональные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` или `OMNI_GATEWAY_API_KEY`;
- любые старые Telegram tokens, webhook secrets и user IDs, обнаруженные
  при очистке внешних систем;
- полный номер брокерского счёта;
- реальные брокерские отчёты, операции и позиции;
- Authorization headers;
- секреты Render или GPT Editor.

Допустимы только имена переменных и безопасные placeholders. Счёт в ответах должен быть маскирован.

## 4. Стабильность runtime и деплоя

- Gateway entrypoint: `app:app`.
- Поддерживается только Gateway Render service из `render.yaml`.
- `telegram_bot/`, `render.telegram.yaml` и `/telegram/webhook` выведены
  из эксплуатации и не должны возвращаться без отдельного ADR и решения
  владельца.
- Перенос root runtime-модулей выполняется только отдельным refactor PR.

## 5. Структура репозитория

- Gateway runtime и wrappers — в корне;
- доменные правила — в `knowledge/`;
- Custom GPT — в `gpt/`;
- архитектура, runbooks и inventory — в `docs/`;
- проверки — в `scripts/`;
- постоянный CI и templates — в `.github/`.

Одноразовые release-patcher workflow нельзя оставлять в `main`.

## 6. GPT Actions и OpenAPI

Для каждого Action:

- уникальный стабильный `operationId`;
- Bearer-защита через `GATEWAY_API_KEY`;
- явные `properties` у object schema;
- `status`, `version`, `retrieved_at`, masked account, `quality`, `complete`, `component_errors`, `warnings`, где применимо;
- неизвестные ошибки нельзя маскировать под `pending` или `ok`.

При изменении Action contract обновить `gpt/` и профильный `knowledge/` файл.

## 7. Выведенный из эксплуатации Telegram runtime

- Не добавлять package `telegram_bot/`.
- Не добавлять `render.telegram.yaml`.
- Не публиковать `/telegram/webhook`.
- Не возвращать Telegram-specific переменные в `.env.example`,
  `render.yaml` или dependency files.
- История решения хранится в `knowledge/12_TELEGRAM_RETIREMENT.txt`.
- Ручная очистка внешнего сервиса выполняется по
  `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

## 8. Деньги и качество данных

- Не складывать валюты без подтверждённого FX.
- Денежные расчёты выполнять через `Decimal` или безопасную эквивалентную логику.
- Не двойно учитывать комиссии, child operations, nested commissions или embedded trades.
- Не объявлять данные полными при `complete=false`, `status=partial` или `pagination.truncated=true`.

## 9. Брокерский отчёт T-Invest

Для `getBrokerReportReconciliation`:

- `days=1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий `task_id`;
- повторный вызов использует тот же `task_id`;
- T-Invest `30058` означает `pending`;
- прочие ошибки остаются ошибками;
- до готовности отчёта `complete=false`.

## 10. Тестирование

Минимум:

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Обязателен тест, подтверждающий отсутствие Telegram runtime, Blueprint,
active env configuration, imports и OpenAPI routes.

Тесты не должны обращаться к реальным Render или T-Invest API.

## 11. Git workflow

- Работать в отдельной ветке.
- Делать логические commits.
- Открывать PR по шаблону.
- Проверять head SHA, review threads и CI.
- Для релизов использовать squash merge.
- После merge проверять каждый затронутый production service отдельно.

## 12. Обновление проектной памяти

После значимого изменения обновить:

- `CHANGELOG.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- профильный `knowledge/NN_*`;
- `gpt/`, если меняется Custom GPT;
- `docs/inventory/PROJECT_ASSETS.md`;
- deployment runbook;
- `.github/copilot-instructions.md`, если меняются обязательные AI-правила.

## 13. Внешние компоненты

GitHub не заменяет:

- Render Dashboard для секретов и deploy state;
- GPT Editor для публикации и Bearer key;
- T-Invest для реальных данных;
- исходный frontend-проект, пока он не найден.

BotFather и старый Telegram Render service нужны только для одноразовой
очистки по retirement runbook.

Не создавать дубликат существующего frontend.
