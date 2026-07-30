# GitHub Copilot Instructions — Omni-CIO

Перед изменениями прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `docs/README.md`;
4. `docs/master-plan/README.md` и текстовую копию master plan;
5. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
6. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
7. профильный файл `knowledge/`;
8. `gpt/` для Custom GPT;
9. retirement profile/runbook только для проверки завершённой миграции.
Обязательные правила:

- Сохраняй строго read-only архитектуру.
- Будущие торговые цели master plan не включают trading и не отменяют текущие запреты.
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
- Не редактируй generated lock-файлы вручную; dependencies меняются
  через `.in` и pip-tools.
- External GitHub Actions должны использовать full commit SHA.

Для брокерского отчёта:

- `days=1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий ID;
- повторный вызов использует тот же ID;
- T-Invest `30058` означает `pending`;
- до готовности `complete=false`.

Проверки:

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

Работай через отдельную ветку и PR. Обновляй changelog, master context, профильный knowledge, inventory и runbook.
