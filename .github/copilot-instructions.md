# GitHub Copilot Instructions — Omni-CIO Gateway

Перед изменениями прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `docs/README.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. профильный файл `knowledge/`;
6. `gpt/INSTRUCTIONS.md` и `gpt/ACTIONS_CATALOG.md`, если меняется Custom GPT.

Обязательные правила:

- Сохраняй строго read-only архитектуру.
- Не добавляй создание, отправку, замену или отмену заявок.
- Сохраняй `trading_methods=false`.
- Публичные Action endpoints должны быть только `GET` и защищены Bearer-ключом.
- Не помещай в код, тесты, документацию или логи `TINVEST_TOKEN`, `GATEWAY_API_KEY`, полный номер счёта или реальные данные брокерского отчёта.
- Стабильный Render entrypoint — `app:app`.
- Согласовывай версию runtime, `/health`, OpenAPI и Regression Shield.
- Для GPT Actions используй уникальные `operationId` и явные `properties` во всех object schemas.
- Денежные суммы считай отдельно по валютам. Не выполняй скрытую FX-конвертацию.
- Не допускай двойного учёта top-level payment, nested commission, child operations или embedded trades.
- При частичном сбое возвращай безопасный частичный результат с `status=partial`, `complete=false`, `component_errors` и `warnings`.
- Не маскируй неизвестные исключения под `pending`.

Структура:

- runtime остаётся в корне до отдельного compatibility refactor;
- предметные правила — `knowledge/`;
- Custom GPT — `gpt/`;
- архитектура и runbooks — `docs/`;
- постоянный CI и templates — `.github/`;
- одноразовые workflow после релиза удаляются из `main`.

Для `getBrokerReportReconciliation`:

- `days` только `1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий непустой `task_id`;
- повторный вызов использует тот же `task_id`;
- T-Invest `30058` означает `pending`;
- прочие ошибки остаются ошибками;
- до готовности отчёта `complete=false`.

Каждое изменение сопровождай тестами:

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Для новых Action или денежных расчётов добавляй unit, endpoint/OpenAPI и Regression Shield тесты. Тесты не должны обращаться к реальному API.

Работай через отдельную ветку и Pull Request по `.github/pull_request_template.md`. Обновляй `CHANGELOG.md`, project memory, профильный knowledge-файл и `gpt/`, если меняется Action contract.
