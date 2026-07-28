# Индекс файлов проекта

## Runtime

| Файл | Назначение |
|---|---|
| `app.py` | Актуальный gateway release wrapper, OpenAPI additions и `app:app` |
| `app_v371.py` | Архивный совместимый wrapper purchase-capacity release line |
| `app_v360.py` | Базовый legacy wrapper cash-liquidity release line |
| `main.py` | Историческое ядро gateway, auth, базовые routes и helpers |
| `portfolio_market.py` | Portfolio Market Snapshot |
| `portfolio_analytics.py` | Portfolio Analytics Core |
| `cash_liquidity.py` | Cash & Liquidity Diagnostics |
| `purchase_capacity.py` | Purchase Capacity Preview |
| `purchase_capacity_integrity.py` | Арифметика, комиссии и integrity checks |
| `sdk_order_compat.py` | Совместимость read-only SDK расчётных вызовов |
| `operations_analytics.py` | Operations Analytics & Cash Flow Reconciliation |
| `broker_report_reconciliation/` | Generate/Get official report, pagination и reconciliation |

## Конфигурация

| Файл | Назначение |
|---|---|
| `render.yaml` | Gateway Render contract |
| `requirements.in` | Human-edited production constraints |
| `requirements.txt` | Полностью pinned production lock с SHA-256 hashes |
| `requirements-dev.in` | Human-edited development constraints |
| `requirements-dev.txt` | Полностью pinned development lock с SHA-256 hashes |
| `pyproject.toml` | Ruff, mypy, pytest/coverage и Bandit baseline |
| `.env.example` | Имена Gateway-переменных без секретных значений |
| `.gitignore` | Защита от секретов и артефактов |
| `.editorconfig` | Единые правила форматирования |

## Tests

| Файл | Область |
|---|---|
| `tests/test_regression_shield.py` | Gateway OpenAPI, auth, read-only и entrypoint |
| `tests/test_portfolio_market_snapshot.py` | Рыночная оценка портфеля |
| `tests/test_portfolio_analytics.py` | Структура и концентрация |
| `tests/test_cash_liquidity.py` | Деньги и лимиты |
| `tests/test_purchase_capacity.py` | Purchase preview |
| `tests/test_purchase_capacity_integrity.py` | Арифметическая целостность |
| `tests/test_sdk_order_compat.py` | SDK request compatibility |
| `tests/test_operations_analytics.py` | Операции и cash-flow reconciliation |
| `tests/test_broker_report_reconciliation.py` | Брокерский отчёт и сверка |
| `tests/test_broker_report_async_integrity.py` | `task_id`, `pending`, T-Invest 30058 |
| `tests/test_no_telegram_runtime.py` | Запрет Telegram runtime, config, imports и OpenAPI routes |
| `tests/test_ci_security_baseline.py` | Hash locks, Action SHA pins и secret-report policy |

## Project memory

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила работы |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Полный контекст и roadmap |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market и buying-power semantics |
| `knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt` | Operations semantics |
| `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt` | Broker-report async semantics |
| `knowledge/12_TELEGRAM_RETIREMENT.txt` | Решение о выводе Telegram из эксплуатации |
| `knowledge/14_CI_SECURITY_BASELINE.txt` | Воспроизводимый CI, quality/security gates и debt register |
| `gpt/` | Восстановление Custom GPT |
| `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md` | Одноразовая внешняя очистка Telegram после merge |
| `docs/` | Архитектура, inventory и runbooks |

## GitHub automation

| Файл | Назначение |
|---|---|
| `.github/workflows/regression-shield.yml` | Blocking quality, contracts, coverage и security CI |
| `.github/dependabot.yml` | Еженедельные pip и GitHub Actions updates |
| `.github/CODEOWNERS` | Ответственный за области |
| `.github/pull_request_template.md` | Definition of Done для PR |
| `.github/ISSUE_TEMPLATE/` | Безопасные формы задач |
| `.github/copilot-instructions.md` | Канонические правила Copilot |

## Repository checks

| Файл | Назначение |
|---|---|
| `scripts/check_repository_layout.py` | Layout, retired Telegram и broker-write guard |
| `scripts/check_ci_security_baseline.py` | Dependency hashes, Action pins, gates и secret report |

## Правило актуальности

При добавлении, переименовании или удалении ключевого файла обновите этот индекс в том же Pull Request. `scripts/check_repository_layout.py` контролирует обязательный набор.
