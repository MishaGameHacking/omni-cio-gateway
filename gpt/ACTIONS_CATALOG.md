# Каталог Omni-CIO GPT Actions

Backend release: **v3.10.0**.

Production Gateway:

`https://omni-cio-gateway.onrender.com`

Production schema:

`https://omni-cio-gateway.onrender.com/openapi.json`

Все пользовательские операции работают только на чтение. `gatewayHealth` публичный; остальные используют Bearer `GATEWAY_API_KEY`.

| operationId | HTTP | Path | Назначение |
|---|---:|---|---|
| `gatewayHealth` | GET | `/health` | Версия, build, capabilities, read-only contract |
| `getConnection` | GET | `/connection` | T-Invest connection и masked account |
| `getPortfolioSnapshot` | GET | `/snapshot` | Базовый портфель и cash |
| `getEnrichedPortfolioSnapshot` | GET | `/snapshot/enriched` | Позиции + UID/FIGI/ISIN/ticker/identity checks |
| `findInstrument` | GET | `/instruments/search` | Поиск инструмента |
| `getOperationsHistory` | GET | `/operations` | Сырая read-only история операций |
| `getMarketSnapshot` | GET | `/market/snapshot` | Цена, order book, trading status одного инструмента |
| `getPortfolioMarketSnapshot` | GET | `/portfolio/market-snapshot` | Рыночная оценка портфеля |
| `getPortfolioAnalytics` | GET | `/portfolio/analytics` | Структура, доли, концентрация, quality |
| `getCashLiquiditySnapshot` | GET | `/portfolio/cash-liquidity` | Cash/liquidity/withdraw-limit diagnostics |
| `getPurchaseCapacityPreview` | GET | `/portfolio/purchase-capacity` | Read-only technical purchase capacity |
| `getOperationsAnalytics` | GET | `/operations/analytics` | Категории операций, cash flow, reconciliation |
| `getBrokerReportReconciliation` | GET | `/operations/broker-report-reconciliation` | Async official T-Invest report reconciliation |
| `getFinalDecisionReview` | GET | `/decision/final-review` | Read-only retrieval of an already prepared reviewed decision source |

## Инварианты

- Ровно 14 GET operations.
- Никаких order create/submit/replace/cancel/stop-order/withdraw/transfer operations.
- `trading_methods=false`.
- `gatewayHealth` не подтверждает broker connection; для этого `getConnection`.
- `getPurchaseCapacityPreview` не создаёт заявку и не превращает technical capacity в recommendation.
- `getFinalDecisionReview` не создаёт новую рекомендацию и не подтверждает execution.

## Broker report

`getBrokerReportReconciliation`:

- `days=1..31`;
- первый async вызов без `task_id`;
- T-Invest `30058` = report pending;
- повторная проверка использует тот же returned `task_id`;
- complete only when `complete=true`.

## GPT Actions OpenAPI compatibility

- одна Bearer security scheme: `ApiKeyAuth`;
- `gatewayHealth` остаётся public;
- остальные protected operations ссылаются на `ApiKeyAuth`;
- служебные correlation headers не публикуются как обязательные GPT Action parameters;
- response contracts сохраняют user-safe masked/read-only fields.

## Contract stability

Без migration plan не менять:

- `operationId`;
- paths;
- HTTP method type;
- Bearer authentication;
- ключевые `status/version/retrieved_at/quality/complete/component_errors/warnings/trading_methods` semantics.

## GPT Editor update

Повторный OpenAPI import нужен, когда реально изменился Action/OpenAPI contract.

После такого изменения:

1. deploy Gateway;
2. проверить production `/health`;
3. импортировать production `/openapi.json`;
4. Authentication → API Key → Bearer;
5. вручную ввести `GATEWAY_API_KEY`;
6. убедиться, что видны ровно 14 GET operations;
7. Preview smoke tests;
8. `Update`.
