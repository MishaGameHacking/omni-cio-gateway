# AGENTS.md — Omni-CIO Project Rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, работающего с репозиторием.

## 1. Сначала восстановить контекст

Перед изменением кода:

1. Прочитать `README.md`.
2. Прочитать `docs/README.md`.
3. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитать `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если задача касается Custom GPT.
5. Для Telegram прочитать `knowledge/12_TELEGRAM_COMPANION.txt` и `docs/operations/TELEGRAM_COMPANION_RUNBOOK.md`.
6. Прочитать профильный файл из `knowledge/`.
7. Проверить `main`, открытые PR, последние релизы и GitHub Actions.
8. Не считать старую переписку источником истины, если она расходится с кодом в `main`.

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
- Telegram Companion вызывает gateway только методом `GET`;
- единственный допустимый публичный `POST` в Telegram service — входящий `/telegram/webhook`, который не изменяет брокерский счёт;
- `trading_methods=false`;
- Regression Shield отклоняет торговые operationId и mutating gateway routes.

## 3. Секреты и персональные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` или `OMNI_GATEWAY_API_KEY`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- реальные Telegram user IDs владельца;
- полный номер брокерского счёта;
- реальные брокерские отчёты, операции и позиции;
- Authorization headers;
- секреты Render или GPT Editor.

Допустимы только имена переменных и безопасные placeholders. Счёт в ответах должен быть маскирован.

## 4. Стабильность runtime и деплоя

- Gateway entrypoint: `app:app`.
- Telegram entrypoint: `telegram_bot.app:app`.
- Gateway и Telegram разворачиваются как отдельные Render services.
- Telegram использует отдельный `render.telegram.yaml`; не ломать существующий `render.yaml`.
- Gateway API version и Telegram service version могут отличаться; это нужно явно документировать.
- Перенос root runtime-модулей выполняется только отдельным refactor PR.

## 5. Структура репозитория

- Gateway runtime и wrappers — в корне;
- Telegram runtime — в `telegram_bot/`;
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

## 7. Telegram Companion

- Webhook проверяет `X-Telegram-Bot-Api-Secret-Token`.
- Разрешены только личные чаты.
- Доступ только для `TELEGRAM_ALLOWED_USER_IDS`.
- Повторные `update_id` игнорируются.
- Действует per-user rate limit.
- Команды не управляют GitHub, Render, ключами или торговыми действиями.
- Telegram token никогда не должен появляться в URL ошибок, логах или health.
- Startup setup (`getMe`, `setMyCommands`, `setWebhook`) не должен падением ломать health service; ошибка отражается безопасным degraded status.
- `/report` использует максимум 31 день и сохраняет `task_id` только как временное удобство; пользовательский task ID должен оставаться видимым для восстановления после restart.
- Нормальный ответ команды — краткая безопасная сводка, а не полный JSON.
- Friendly formatter не должен пересчитывать финансовые данные, смешивать валюты или менять `status`, `complete`, `quality`.
- Длинные ответы должны безопасно делиться ниже лимита Telegram Bot API.
- Retry разрешён только для того же GET-запроса при временной сетевой ошибке или HTTP 408/425/429/5xx.
- HTTP 401/403, validation errors и любые mutating requests нельзя повторять.
- После исчерпания retry вернуть ошибку, а не ложный `ok`.

## 8. Деньги и качество данных

- Не складывать валюты без подтверждённого FX.
- Денежные расчёты выполнять через `Decimal` или безопасную эквивалентную логику.
- Не двойно учитывать комиссии, child operations, nested commissions или embedded trades.
- Не объявлять данные полными при `complete=false`, `status=partial` или `pagination.truncated=true`.
- Telegram не должен улучшать или переинтерпретировать финансовые данные gateway: он только безопасно доставляет ответ.

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
  operations_analytics.py broker_report_reconciliation telegram_bot tests scripts
python -m pytest -q
```

Для Telegram обязательны тесты: health без секретов, auto setup, неверный webhook secret, unauthorized user, GET-only gateway call, `/status`, retryable и non-retryable errors, friendly output, safe message splitting, report task reuse, duplicate update suppression и `trading_methods=false`.

Тесты не должны обращаться к реальным Telegram, Render или T-Invest API.

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
- BotFather для создания и ротации Telegram token;
- T-Invest для реальных данных;
- исходный frontend-проект, пока он не найден.

Не создавать дубликат существующего frontend.
