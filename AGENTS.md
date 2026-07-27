# AGENTS.md — Omni-CIO Project Rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, работающего с репозиторием.

## 1. Сначала восстановить контекст

Перед изменением кода:

1. Прочитать `README.md`.
2. Прочитать `docs/README.md`.
3. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Прочитать `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если задача касается Custom GPT.
5. Прочитать профильный файл из `knowledge/`.
6. Проверить текущую ветку `main`, открытые PR, последние релизы и GitHub Actions.
7. Не считать сведения из старого чата источником истины, если они расходятся с кодом в `main`.

## 2. Неприкосновенный read-only режим

Публичный шлюз должен оставаться строго read-only.

Запрещено добавлять или вызывать:

- создание заявки;
- отправку заявки;
- замену заявки;
- отмену заявки;
- выставление стоп-заявки;
- любые другие методы, изменяющие брокерский счёт.

Обязательные инварианты:

- HTTP endpoints шлюза для пользовательских Action-методов — только `GET`;
- `trading_methods=false`;
- описание API прямо сообщает, что сделки не совершаются;
- Regression Shield отклоняет торговые operationId и mutating routes.

## 3. Секреты и персональные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный номер брокерского счёта;
- содержимое реального брокерского отчёта пользователя;
- персональные данные, номера сделок и иные чувствительные значения;
- логи с Authorization header;
- секреты Render или GPT Editor.

Допустимы только имена переменных и безопасные placeholders. Счёт в ответах должен быть маскирован.

Перед работой с внешними компонентами прочитать `docs/inventory/PROJECT_ASSETS.md`.

## 4. Стабильность runtime и деплоя

- Основной entrypoint: `app:app`.
- Не менять Render start command без отдельной доказанной необходимости.
- Версия в runtime, `/health`, OpenAPI и Regression Shield должна совпадать.
- Старые wrapper-модули можно сохранять для совместимости, но публичный `app` должен указывать на актуальную версию.
- Перенос root runtime-модулей в пакет выполняется только отдельным refactor PR с compatibility imports и production smoke test.

## 5. Структура репозитория

- runtime и совместимые wrappers находятся в корне;
- доменные правила — в `knowledge/`;
- переносимая конфигурация Custom GPT — в `gpt/`;
- архитектура, runbooks и inventory — в `docs/`;
- локальные проверки — в `scripts/`;
- постоянный CI, CODEOWNERS и templates — в `.github/`.

Одноразовые release-patcher workflow нельзя оставлять в `main` после завершения релиза.

Подробности: `docs/architecture/REPOSITORY_STRUCTURE.md`.

## 6. Правила GPT Actions и OpenAPI

Для каждого Action:

- уникальный и стабильный `operationId`;
- Bearer-защита через `GATEWAY_API_KEY`;
- явные `properties` у каждого object schema;
- компактный JSON, пригодный для GPT Actions;
- `status`, `version`, `retrieved_at`, masked account, `quality`, `complete`, `component_errors`, `warnings` там, где это применимо;
- частичный сбой компонента не должен уничтожать безопасный полезный результат;
- неизвестные ошибки нельзя маскировать под `pending` или `ok`.

При изменении Action contract обновить `gpt/ACTIONS_CATALOG.md`, `gpt/INSTRUCTIONS.md` и профильный `knowledge/` файл.

## 7. Деньги и качество данных

- Не складывать RUB, USD, EUR и другие валюты без подтверждённого FX-источника.
- Денежные расчёты выполнять через `Decimal` или безопасную эквивалентную логику.
- Не двойно учитывать комиссии, child operations, nested commissions или embedded trades.
- Не объявлять данные полными при `complete=false`, `status=partial` или `pagination.truncated=true`.
- Брокерский отчёт считать окончательным бухгалтерским источником при расхождении с оперативным API, но только после подтверждённой загрузки всех страниц.

## 8. Брокерский отчёт T-Invest

Для `getBrokerReportReconciliation`:

- `days` находится в диапазоне `1..31`;
- первый вызов с `wait_seconds=0` и без `task_id` должен вернуть `pending` и непустой `task_id`;
- повторный вызов использует тот же `task_id`;
- код T-Invest `30058` означает, что задача ещё не завершена;
- только `30058` и эквивалентные сообщения ожидания можно переводить в `pending`;
- прочие исключения должны оставаться ошибками;
- пока отчёт не готов, `complete=false`.

Подробности: `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`.

## 9. Тестирование

Каждое изменение должно иметь тесты. Минимум:

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Для новой возможности добавить:

- unit-тест happy path;
- тест частичного сбоя;
- тест защиты от двойного счёта, если есть денежная агрегация;
- endpoint/OpenAPI тест;
- Regression Shield тест;
- тест отсутствия торговых методов.

Тесты не должны обращаться к реальному T-Invest API и не должны использовать реальные секреты.

## 10. Git workflow

- Не писать новые функции прямо в `main`.
- Создать отдельную ветку.
- Сделать небольшие логические commits.
- Открыть Pull Request по `.github/pull_request_template.md`.
- Перед merge проверить head SHA, review threads и CI.
- Для релизов предпочтителен squash merge.
- После merge проверить production по `docs/operations/DEPLOYMENT_RUNBOOK.md`.

## 11. Обновление проектной памяти

После значимого изменения обновить:

- `CHANGELOG.md`;
- `README.md`, если изменился запуск, структура или release;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`, если изменились цели, компоненты или приоритеты;
- профильный файл `knowledge/NN_*`, если изменилось поведение Action;
- `gpt/`, если изменилось поведение Custom GPT или Action contract;
- `docs/inventory/PROJECT_ASSETS.md`, если изменились внешние компоненты;
- `.github/copilot-instructions.md`, если изменились обязательные правила AI.

Проектная память в GitHub должна оставаться обезличенной, проверяемой и пригодной для продолжения работы из любого нового чата.

## 12. Внешние компоненты

GitHub не заменяет:

- Render Dashboard для секретов и deploy state;
- GPT Editor для публикации, модели и Bearer key;
- T-Invest для реальных данных;
- исходный frontend-проект, пока он не найден и не зарегистрирован.

Не придумывать отсутствующий frontend repository и не создавать дубликат существующего сайта.
