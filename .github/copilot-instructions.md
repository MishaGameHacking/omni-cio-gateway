# GitHub Copilot Instructions — Omni-CIO Gateway

Перед изменениями прочитай `AGENTS.md`, `README.md` и `knowledge/00_PROJECT_MASTER_CONTEXT.md`.

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

Для `getBrokerReportReconciliation`:

- `days` только `1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий непустой `task_id`;
- повторный вызов использует тот же `task_id`;
- T-Invest `30058` означает `pending`;
- прочие ошибки остаются ошибками;
- до готовности отчёта `complete=false`.

Каждое изменение сопровождай тестами:

```bash
python -m compileall .
python -m pytest -q
```

Для новых Action или денежных расчётов добавляй unit, endpoint/OpenAPI и Regression Shield тесты. Тесты не должны обращаться к реальному API.

Работай через отдельную ветку и Pull Request. В PR указывай: что изменено, безопасность, выполненные тесты и production-проверку после merge.
