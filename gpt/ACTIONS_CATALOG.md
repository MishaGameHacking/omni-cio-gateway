# Каталог GPT Actions

Текущий backend release: **v3.9.1**. Production schema импортируется из `/openapi.json` активного Render service.

Все пользовательские Actions защищены Bearer key и работают только на чтение.

| operationId | HTTP | Path | Назначение |
|---|---:|---|---|
| `gatewayHealth` | GET | `/health` | Версия, build, capabilities, Regression Shield |
| `getConnection` | GET | `/connection` | Проверка T-Invest подключения и маскированного счёта |
| `getPortfolioSnapshot` | GET | `/snapshot` | Базовый снимок портфеля и денежных остатков |
| `getEnrichedPortfolioSnapshot` | GET | `/snapshot/enriched` | Снимок с UID, FIGI, ISIN, ticker и identity checks |
| `findInstrument` | GET | `/instruments/search` | Умный поиск справочного инструмента |
| `getOperationsHistory` | GET | `/operations` | Сырая read-only история операций |
| `getMarketSnapshot` | GET | `/market/snapshot` | Цена, стакан, статус торгов и источники одного инструмента |
| `getPortfolioMarketSnapshot` | GET | `/portfolio/market-snapshot` | Рыночная оценка всего портфеля по валютам |
| `getPortfolioAnalytics` | GET | `/portfolio/analytics` | Структура, доли, концентрация и качество оценки |
| `getCashLiquiditySnapshot` | GET | `/portfolio/cash-liquidity` | Сопоставление позиций и лимитов вывода |
| `getPurchaseCapacityPreview` | GET | `/portfolio/purchase-capacity` | Предварительный read-only расчёт суммы и доступности покупки |
| `getOperationsAnalytics` | GET | `/operations/analytics` | Категории операций, денежные потоки и reconciliation |
| `getBrokerReportReconciliation` | GET | `/operations/broker-report-reconciliation` | Асинхронный официальный отчёт и сверка с операциями |

## Правила вызовов

- Когда пользователь пишет «вызови только X», нельзя вызывать другие Actions.
- `gatewayHealth` не подтверждает T-Invest token — для этого нужен `getConnection`.
- `getOperationsHistory` и `getOperationsAnalytics` не являются взаимозаменяемыми.
- `getPurchaseCapacityPreview` не создаёт заявку и не гарантирует исполнение.
- `getBrokerReportReconciliation` принимает `days=1..31`.
- Первый вызов отчёта без `task_id` возвращает `pending` и `task_id`; повторный вызов использует тот же ID.

## Стабильность контракта

Нельзя без migration plan менять:

- `operationId`;
- публичные paths;
- тип HTTP-метода;
- Bearer authentication;
- ключевые поля `status`, `version`, `retrieved_at`, `quality`, `complete`, `component_errors`, `warnings`, `trading_methods`.

## Обновление GPT Editor

1. Дождаться production deploy.
2. Проверить `/health`.
3. Импортировать актуальный `/openapi.json`.
4. Установить Authentication → API Key → Bearer.
5. Ввести секретный `GATEWAY_API_KEY` вручную.
6. Убедиться, что список действий совпадает с таблицей.
7. Выполнить один целевой тест и проверить, что другие методы не вызывались.
