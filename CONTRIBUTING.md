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
- Lock-файлы не редактируются вручную; production и CI используют
  `--require-hashes`.
- Внешние GitHub Actions закрепляются полным 40-символьным commit SHA.

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
python -m pip install --require-hashes -r requirements-dev.txt
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
python -m pip_audit --require-hashes --disable-pip --strict \
  --vulnerability-service osv \
  --progress-spinner off -r requirements.txt
python -m bandit -c pyproject.toml -r . -ll -ii -q
```

Secret scan запускается точной командой из Regression Shield. При
обновлении dependency constraints регенерируйте оба lock-файла через
pip-tools 7.6.0 и проверяйте diff версий и hashes.

## Требования к Pull Request

PR должен объяснять:

- что изменено;
- какие источники данных затронуты;
- как сохранён read-only режим;
- какие тесты выполнены;
- что проверить после merge и деплоя;
- какие документы обновлены.
- изменились ли `.in` constraints, lock-файлы, Action SHAs или
  зафиксированные quality/security baselines.
