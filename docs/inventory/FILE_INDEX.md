# Индекс файлов проекта

## Runtime

| Файл | Назначение |
|---|---|
| `app.py` | Актуальный release wrapper, OpenAPI additions и `app:app` |
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
| `render.yaml` | Render build/start/health contract |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Test dependencies |
| `.env.example` | Имена переменных без секретных значений |
| `.gitignore` | Защита от случайного коммита секретов и артефактов |
| `.editorconfig` | Единые правила форматирования файлов |

## Tests

| Файл | Область |
|---|---|
| `tests/test_regression_shield.py` | OpenAPI, auth, read-only и entrypoint |
| `tests/test_portfolio_market_snapshot.py` | Рыночная оценка портфеля |
| `tests/test_portfolio_analytics.py` | Структура и концентрация |
| `tests/test_cash_liquidity.py` | Деньги и лимиты |
| `tests/test_purchase_capacity.py` | Purchase preview |
| `tests/test_purchase_capacity_integrity.py` | Арифметическая целостность |
| `tests/test_sdk_order_compat.py` | SDK request compatibility |
| `tests/test_operations_analytics.py` | Операции и cash-flow reconciliation |
| `tests/test_broker_report_reconciliation.py` | Брокерский отчёт и сверка |
| `tests/test_broker_report_async_integrity.py` | `task_id`, `pending`, T-Invest 30058 |

## Project memory

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила работы |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Полный контекст и roadmap |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market и buying-power semantics |
| `knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt` | Operations semantics |
| `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt` | Broker-report async semantics |
| `gpt/` | Восстановление Custom GPT |
| `docs/` | Архитектура, inventory и runbooks |

## GitHub automation

| Файл | Назначение |
|---|---|
| `.github/workflows/regression-shield.yml` | Постоянный CI |
| `.github/CODEOWNERS` | Ответственный за области |
| `.github/pull_request_template.md` | Definition of Done для PR |
| `.github/ISSUE_TEMPLATE/` | Безопасные формы задач |
| `.github/copilot-instructions.md` | Канонические правила Copilot |

## Правило актуальности

При добавлении, переименовании или удалении ключевого файла обновите этот индекс в том же Pull Request. Автоматическая проверка `scripts/check_repository_layout.py` контролирует наличие обязательного набора.
