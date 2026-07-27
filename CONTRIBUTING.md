# Вклад в Omni-CIO Gateway

## Перед началом

1. Прочитайте `AGENTS.md`.
2. Прочитайте `README.md` и `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
3. Откройте профильный документ в `knowledge/`.
4. Проверьте `main`, открытые Pull Request и Regression Shield.

## Неприкосновенные правила

- Только read-only пользовательские endpoints.
- `trading_methods=false`.
- Нельзя добавлять создание, отправку, замену или отмену заявок.
- Render entrypoint остаётся `app:app`.
- Нельзя сохранять токены, API-ключи, полные номера счетов и реальные брокерские отчёты.
- Валюты рассчитываются отдельно без неявного FX.

## Рабочий процесс

1. Создайте ветку от актуального `main`.
2. Сделайте одно логическое изменение.
3. Добавьте или обновите тесты.
4. Обновите документацию и project memory.
5. Откройте Pull Request по шаблону.
6. Дождитесь Regression Shield.
7. Для релизных веток используйте squash merge.

## Минимальные проверки

```bash
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests
python -m pytest -q
python scripts/check_repository_layout.py
```

## Требования к Pull Request

PR должен объяснять:

- что изменено;
- какие источники данных затронуты;
- как сохранён read-only режим;
- какие тесты выполнены;
- что проверить после merge и деплоя;
- какие документы обновлены.
