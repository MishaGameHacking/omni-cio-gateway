# GitHub Copilot Instructions — Omni-CIO

Перед изменениями прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `docs/README.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. профильный файл `knowledge/`;
6. `gpt/` для Custom GPT;
7. `knowledge/12_TELEGRAM_RETIREMENT.txt` и removal runbook для проверки
   завершённой миграции.

Обязательные правила:

- Сохраняй строго read-only архитектуру.
- Не добавляй создание, отправку, замену или отмену заявок.
- Сохраняй `trading_methods=false`.
- Gateway Actions только GET и Bearer-protected.
- Telegram runtime, Blueprint, environment configuration, imports и
  OpenAPI routes отсутствуют. Не восстанавливай их без нового ADR,
  threat model и решения владельца.
- Не помещай в код, тесты, документацию или логи T-Invest token,
  Gateway key, действующие или отозванные Telegram credentials, полный
  номер счёта или реальные отчёты.
- Gateway entrypoint — `app:app`.
- Денежные суммы считай отдельно по валютам без скрытого FX.
- Не допускай двойного учёта top-level payment, nested commission, child operations или embedded trades.
- Не маскируй неизвестные исключения под `pending`.

Для брокерского отчёта:

- `days=1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий ID;
- повторный вызов использует тот же ID;
- T-Invest `30058` означает `pending`;
- до готовности `complete=false`.

Проверки:

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Работай через отдельную ветку и PR. Обновляй changelog, master context, профильный knowledge, inventory и runbook.
