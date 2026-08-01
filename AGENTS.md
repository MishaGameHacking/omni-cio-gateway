# AGENTS.md — Omni-CIO Project Rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, работающего с репозиторием.

## 1. Сначала восстановить контекст

Перед изменением кода:

1. Прочитать `README.md`.
2. Прочитать `docs/README.md`.
3. Прочитать `docs/master-plan/README.md`.
4. Прочитать текущий порядок исполнения `docs/master-plan/OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md`.
5. Прочитать исходную стратегическую спецификацию `docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`.
6. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
7. Прочитать `knowledge/16_CURRENT_PROGRAM_STATUS.md` для фактического активного этапа.
8. Прочитать `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если задача касается Custom GPT.
9. Прочитать профильный файл из `knowledge/`.
10. Проверить current `main`, открытые PR, Issues, review threads, последние merges и GitHub Actions.
11. При работе с Custom GPT проверить фактический GPT Editor и Preview evidence либо явно отметить, что они недоступны.
12. Не считать будущую цель master plan реализованной без кода, тестов и acceptance.
13. Не считать старую переписку источником истины, если она расходится с фактическим состоянием.

До завершения GPT-only audit запрещено начинать новые функциональные пакеты, кроме явно необходимой compatibility/CI работы и синхронизации канонического плана.

## 2. Зафиксированный продукт и scope

Единственный пользовательский продукт — существующий Custom GPT Omni-CIO внутри ChatGPT.

Без отдельного нового решения владельца запрещено:

- создавать или развивать отдельный сайт/web-кабинет;
- создавать мобильное приложение;
- создавать отдельный чат-интерфейс;
- создавать дубликат Custom GPT;
- создавать собственную AI-модель или отдельный reasoning server;
- возвращать Telegram-бота как второй интерфейс.

Gateway является минимальным защищённым data layer для GPT Actions, а не пользовательским web-продуктом.

Старые roadmap-пункты о frontend, web cabinet, SberInvestments HTML cabinet и обязательной внешней production RAG не продолжаются автоматически. В GPT-only audit они должны быть классифицированы как conflict, reusable capability, optional future package, deprecated/orphaned или доказанная часть end-to-end цепочки.

## 3. Неприкосновенный read-only режим

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
- Regression Shield отклоняет торговые operationId и mutating gateway routes;
- Telegram runtime выведен из эксплуатации и не должен появляться в Gateway, OpenAPI или deployment configuration;
- `app:app` остаётся стабильным entrypoint;
- Shadow/Paper/Preview/Confirm-before-trade не разрешают execution без отдельной admission program и owner decision.

## 4. Секреты и персональные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` или `OMNI_GATEWAY_API_KEY`;
- Telegram tokens, webhook secrets и user IDs;
- полный номер брокерского счёта;
- реальные брокерские отчёты, операции и позиции;
- Authorization headers;
- секреты Render или GPT Editor.

Допустимы только имена переменных и безопасные placeholders. Счёт в ответах должен быть маскирован.

Когда требуется секрет, дать владельцу короткую UI-инструкцию и не просить само значение.

## 5. Стабильность runtime и деплоя

- Gateway entrypoint: `app:app`.
- Поддерживается только Gateway Render service из `render.yaml`.
- `telegram_bot/`, `render.telegram.yaml` и `/telegram/webhook` выведены из эксплуатации и не должны возвращаться без отдельного ADR и решения владельца.
- Перенос root runtime-модулей выполняется только отдельным refactor PR.
- Import/startup не должен выполнять сеть без отдельного явного проекта и тестов.
- CI не заменяет внешнюю Render/Gateway/GPT acceptance.

## 6. Структура репозитория

- Gateway runtime и wrappers — в корне;
- versioned domain packages — в `omni_cio/` и профильных модулях;
- доменные правила — в `knowledge/`;
- Custom GPT — в `gpt/`;
- master plans — в `docs/master-plan/`;
- архитектура, runbooks, audits и inventory — в `docs/`;
- проверки — в `scripts/`;
- постоянный CI и templates — в `.github/`.

Одноразовые release-patcher workflow нельзя оставлять в `main`.
Dependency lock-файлы нельзя редактировать вручную. Внешние GitHub Actions должны быть закреплены полным commit SHA.

Каждый ключевой runtime-файл должен иметь consumer/test или явный статус compatibility/deprecated/roadmap.

## 7. GPT Instructions, Knowledge и Actions

- Критический workflow, routing, priorities и stop conditions находятся в Instructions.
- Knowledge используется для справочных методик и личной стратегии, а не для скрытого порядка действий.
- Один Action имеет одно строгое назначение.
- Не допускается generic broker forwarding через `method/name/payload`.
- OpenAPI описывает только фактическое поведение.
- GPT использует Apps или Actions, но не оба режима одновременно, если официальная платформа не изменилась.
- Actions и Knowledge проверяются в Preview перед Update существующего GPT.
- Не создавать новый GPT вместо обновления существующего.

Для каждого Action:

- уникальный стабильный `operationId`;
- Bearer-защита через `GATEWAY_API_KEY`;
- явные `properties` у object schema;
- `status`, `version`, `retrieved_at`, masked account, `quality`, `complete`, `component_errors`, `warnings`, где применимо;
- typed failure states;
- неизвестные ошибки нельзя маскировать под `pending` или `ok`;
- execution, withdrawal, transfer и token-management отсутствуют при `trading_methods=false`.

При изменении Action contract обновить `gpt/`, OpenAPI и профильный `knowledge/` файл.

## 8. Выведенный из эксплуатации Telegram runtime

- Не добавлять package `telegram_bot/`.
- Не добавлять `render.telegram.yaml`.
- Не публиковать `/telegram/webhook`.
- Не возвращать Telegram-specific переменные в `.env.example`, `render.yaml` или dependency files.
- История решения хранится в `knowledge/12_TELEGRAM_RETIREMENT.txt`.
- Ручная очистка внешнего сервиса выполняется по `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`.
- В текущем релизе допустима только подготовка безопасного Telegram draft для ручной публикации.

## 9. Деньги и качество данных

- Не складывать валюты без подтверждённого FX и timestamp.
- Денежные расчёты выполнять через `Decimal` или безопасную эквивалентную логику.
- Не двойно учитывать комиссии, child operations, nested commissions или embedded trades.
- Не объявлять данные полными при `complete=false`, `status=partial`, stale/inconsistent state или `pagination.truncated=true`.
- Проверять UID, lot, currency, quote, trading status, pagination, open orders и account scope.
- Недостаточные данные должны приводить к abstain/missing-data, а не к оценке из воздуха.
- Одна новость, rating или technical pattern не является доказанным торговым сигналом.

## 10. Брокерский отчёт T-Invest

Для `getBrokerReportReconciliation`:

- `days=1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий `task_id`;
- повторный вызов использует тот же `task_id`;
- T-Invest `30058` означает `pending`;
- прочие ошибки остаются ошибками;
- до готовности отчёта `complete=false`.

## 11. Тестирование

Минимум:

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
```

Дополнительно обязательны contract, integration, property, fuzz, security и failure tests по затронутому scope.

Обязателен тест, подтверждающий отсутствие Telegram runtime, Blueprint, active env configuration, imports и OpenAPI routes.

Тесты не должны обращаться к реальным Render или T-Invest API.

Custom GPT изменения требуют отдельной Preview matrix: intent routing, minimal Action call, warnings/timestamps, abstain on stale/partial, no invented fields, prompt-injection resistance и mobile readability.

## 12. Git workflow

- Работать в отдельной ветке от свежего `main`.
- Один логический scope — один PR.
- Не смешивать dependency upgrade, architecture migration и новую функцию.
- Делать логические commits.
- Открывать draft PR по шаблону.
- В PR фиксировать exact base/head, contracts, risks, tests и rollback.
- Проверять head SHA, review threads, CI и artifacts.
- Для релизов использовать squash merge.
- Не merge при red, conflict, unresolved review или queued без evidence.
- После merge проверять каждый затронутый production service отдельно.
- Старый зелёный check не является доказательством после изменения `main`.

## 13. Обновление проектной памяти

После значимого изменения обновить по затронутому scope:

- `CHANGELOG.md`;
- `README.md`;
- `docs/master-plan/README.md` и канонический master-plan index;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- профильный `knowledge/NN_*`;
- `gpt/`, если меняется Custom GPT;
- `docs/inventory/PROJECT_ASSETS.md`;
- deployment/acceptance runbook;
- issue #27;
- `.github/copilot-instructions.md`, если меняются обязательные AI-правила.

Исходные PDF не переписывать. Новую версию добавлять отдельным файлом с checksum и migration note.

## 14. Внешние компоненты и owner-only evidence

GitHub не заменяет:

- Render Dashboard для secret/deploy state;
- GPT Editor для публикации, capabilities и Bearer key;
- T-Invest для реальных приватных данных;
- Preview UI, если его нельзя проверить инструментами.

Не просить пользователя делать то, что можно выполнить через код или GitHub. Просить только owner-only действия без передачи секретов.

## 15. Формат отчёта после этапа

1. Что найдено.
2. Что изменено.
3. Что реально проверено.
4. Что осталось.
5. Риски.
6. GitHub: branch/base/head/PR/Actions/artifact/review/merge decision.
7. GPT Editor: sync/schema/Knowledge/Preview state.
8. Действие пользователя: только необходимое owner-only действие.
9. Следующий один логический этап.
