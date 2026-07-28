# GitHub Copilot Instructions — Omni-CIO

Перед изменениями прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `docs/README.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. профильный файл `knowledge/`;
6. `gpt/` для Custom GPT;
7. `knowledge/12_TELEGRAM_COMPANION.txt` и Telegram runbook для Telegram-задач.

Обязательные правила:

- Сохраняй строго read-only архитектуру.
- Не добавляй создание, отправку, замену или отмену заявок.
- Сохраняй `trading_methods=false`.
- Gateway Actions только GET и Bearer-protected.
- Telegram может иметь только входящий POST webhook; к Gateway он обращается только GET-запросами.
- Не помещай в код, тесты, документацию или логи T-Invest token, Gateway key, Telegram token, webhook secret, реальные user IDs, полный номер счёта или реальные отчёты.
- Gateway entrypoint — `app:app`.
- Telegram entrypoint — `telegram_bot.app:app`.
- Gateway и Telegram являются отдельными Render services.
- Telegram webhook должен проверять `X-Telegram-Bot-Api-Secret-Token`.
- Telegram принимает только private chat и allowlisted users.
- Не логируй raw Telegram updates.
- Telegram не меняет финансовые значения Gateway и повторно маскирует account ID.
- Денежные суммы считай отдельно по валютам без скрытого FX.
- Не допускай двойного учёта top-level payment, nested commission, child operations или embedded trades.
- Не маскируй неизвестные исключения под `pending`.

Для брокерского отчёта:

- `days=1..31`;
- первый вызов без `task_id` и с `wait_seconds=0` возвращает `pending` и настоящий ID;
- повторный вызов использует тот же ID;
- T-Invest `30058` означает `pending`;
- до готовности `complete=false`.

Для Telegram:

- использовать официальный Bot API через HTTPS;
- auto setup выполняет `getMe`, `setMyCommands`, `setWebhook`;
- bootstrap failure отражается degraded health, но не раскрывает секреты;
- команды не управляют GitHub, Render, ключами или торговлей;
- report task in-memory является только удобством, task ID остаётся в ответе;
- normal command output должен быть краткой безопасной сводкой, а не полным JSON;
- friendly formatter не пересчитывает деньги, не смешивает валюты и не улучшает status/complete;
- длинные сообщения делятся ниже лимита Telegram;
- retry допустим только для того же GET-запроса при временной сетевой ошибке или HTTP 408/425/429/5xx;
- HTTP 401/403, validation errors и mutating requests не повторять;
- после исчерпания retry возвращать ошибку, а не `ok`;
- тесты используют fake clients и не выходят в интернет.

Проверки:

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation telegram_bot tests scripts
python -m pytest -q
```

Работай через отдельную ветку и PR. Обновляй changelog, master context, профильный knowledge, inventory и runbook.
