# Каталог Omni-CIO GPT Actions

Gateway: `https://omni-cio-gateway.onrender.com`

Schema: `https://omni-cio-gateway.onrender.com/openapi.json`

`gatewayHealth` публичный; остальные Actions используют Bearer `GATEWAY_API_KEY`.

## 1. Базовый production read-only surface

Когда `SANDBOX_TRADING_ENABLED=false` и `REAL_TRADING_ENABLED=false`, опубликованы ровно 14 GET Actions:

| operationId | HTTP | Path | Назначение |
|---|---:|---|---|
| `gatewayHealth` | GET | `/health` | Health/build/capabilities базового gateway |
| `getConnection` | GET | `/connection` | T-Invest connection + masked account |
| `getPortfolioSnapshot` | GET | `/snapshot` | Портфель и cash |
| `getEnrichedPortfolioSnapshot` | GET | `/snapshot/enriched` | Позиции + UID/FIGI/ISIN/ticker/identity |
| `findInstrument` | GET | `/instruments/search` | Поиск инструмента |
| `getOperationsHistory` | GET | `/operations` | Read-only история операций |
| `getMarketSnapshot` | GET | `/market/snapshot` | Instrument reference, order book, trading status |
| `getPortfolioMarketSnapshot` | GET | `/portfolio/market-snapshot` | Рыночная оценка портфеля |
| `getPortfolioAnalytics` | GET | `/portfolio/analytics` | Структура, доли, концентрация, quality |
| `getCashLiquiditySnapshot` | GET | `/portfolio/cash-liquidity` | Cash/liquidity diagnostics |
| `getPurchaseCapacityPreview` | GET | `/portfolio/purchase-capacity` | Read-only technical purchase capacity |
| `getOperationsAnalytics` | GET | `/operations/analytics` | Cash flow/categories/reconciliation |
| `getBrokerReportReconciliation` | GET | `/operations/broker-report-reconciliation` | Async official broker-report reconciliation |
| `getFinalDecisionReview` | GET | `/decision/final-review` | Read-only reviewed decision source |

Invariant: `TINVEST_TOKEN` остаётся отдельным production **read-only** credential и никогда не используется `omni_cio.real_trading` как fallback.

## 2. Conditional Sandbox surface

Только при `SANDBOX_TRADING_ENABLED=true` дополнительно публикуются 8 Sandbox Actions с отдельным `TINVEST_SANDBOX_TOKEN`:

| operationId | HTTP | Path | Consequential | Назначение |
|---|---:|---|---:|---|
| `getSandboxTradingStatus` | GET | `/sandbox/status` | no | Sandbox readiness/accounts |
| `openSandboxAccount` | POST | `/sandbox/account/open` | yes | Открыть виртуальный Sandbox account после exact confirmation |
| `fundSandboxAccount` | POST | `/sandbox/account/fund` | yes | Пополнить только виртуальными RUB после exact confirmation |
| `getSandboxPortfolio` | GET | `/sandbox/portfolio` | no | Виртуальный portfolio/positions |
| `prepareSandboxTrade` | POST | `/sandbox/trade/prepare` | no submit | Sandbox proposal + preflight + TTL + phrase |
| `executeSandboxTrade` | POST | `/sandbox/trade/execute` | yes | Submit неизменяемого Sandbox proposal после exact phrase |
| `getSandboxOrderState` | GET | `/sandbox/order/status` | no | Reconciliation по request UUID |
| `cancelSandboxOrder` | POST | `/sandbox/order/cancel` | yes | Отмена только Sandbox order после отдельного confirmation |

Sandbox responses должны явно показывать `sandbox=true`, `real_money=false`.

## 3. Conditional REAL EXECUTION surface

Real-money Actions регистрируются только при `REAL_TRADING_ENABLED=true`.

Дополнительная fail-closed граница: если dedicated token, hard limits или durable journal не готовы, Gateway публикует только безопасный readiness endpoint `getRealTradingStatus`; mutation Actions остаются отсутствующими.

При полностью готовом real contour публикуются только эти 4 Actions:

| operationId | HTTP | Path | Consequential | Назначение |
|---|---:|---|---:|---|
| `getRealTradingStatus` | GET | `/real-trading/status` | no | Readiness, account binding, limits, durable journal integrity |
| `prepareRealTrade` | POST | `/real-trading/trade/prepare` | no submit | Создать immutable real LIMIT proposal и exact short-lived phrase |
| `executeRealTrade` | POST | `/real-trading/trade/execute` | **yes** | Submit ровно одного ранее подготовленного proposal после exact owner phrase |
| `getRealOrderState` | GET | `/real-trading/order/state` | no | Broker reconciliation по исходному request UUID |

### Real v1 hard contract

- отдельный `TINVEST_TRADING_TOKEN`, account-scoped full-access **без transfer access**;
- existing `TINVEST_TOKEN` остаётся read-only и не заменяется;
- ровно один open account видим trading token и должен совпасть с read-only account;
- user-facing account только masked;
- только BUY/SELL cash securities v1: `share`/`etf`, RUB;
- только `LIMIT / CURRENCY / DAY`;
- `confirmMarginTrade=false` hard-coded;
- BUY — только own-funds `buyMaxLots`; SELL — только own-position `sellMaxLots`;
- per-order и daily server caps + immutable code ceilings;
- свежий trusted `getMarketSnapshot`, где freshness основана на `order_book.time`;
- price must match `min_price_increment`;
- `prepareRealTrade` ничего не отправляет брокеру;
- `executeRealTrade` принимает только `proposal_id` + exact `confirmation_phrase`;
- proposal и confirmation short-lived/HMAC-bound;
- непосредственно перед `PostOrder` повторяются account, market и financial preflight;
- UUID request id — idempotency key;
- duplicate confirmation не создаёт второй broker submit;
- timeout/network/5xx после возможного submit → `unknown_do_not_resubmit`; автоматического retry нет;
- `getRealOrderState` использует `ORDER_ID_TYPE_REQUEST`;
- `submitted` не означает `filled`; fill подтверждается только broker execution status;
- durable SQLite journal находится на persistent disk и хранит proposal state, request UUID, daily reservation и confirmation evidence hash;
- broker token/Authorization header в journal не сохраняются.

### Запрещено в real v1

Ни source code, ни OpenAPI не должны публиковать real:

- withdrawal / transfer денег;
- securities transfer;
- token creation/rotation;
- MARKET/BESTPRICE execution;
- margin/short;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder/PostOrderAsync;
- autonomous recurring execution;
- `cancelRealOrder` — отдельная более поздняя sub-release, не входит в первый real-submit milestone.

## 4. Возможные Action surfaces

| Sandbox | Real flag/static readiness | Ожидаемый surface |
|---|---|---|
| OFF | OFF | 14 baseline GET |
| ON | OFF | 14 baseline + 8 Sandbox |
| OFF/ON | Real flag ON, static config invalid | baseline (+ Sandbox if ON) + `getRealTradingStatus` only |
| OFF | Real ready | 14 baseline + 4 Real |
| ON | Real ready | 14 baseline + 8 Sandbox + 4 Real |

`getRealTradingStatus` является авторитетным readiness endpoint для real execution. Базовые legacy health/read-only flags не должны использоваться как разрешение на реальную сделку.

## 5. GPT Actions compatibility

- одна Bearer security scheme: `ApiKeyAuth`;
- `gatewayHealth` public;
- protected operations используют `ApiKeyAuth`;
- response objects имеют explicit properties;
- `executeRealTrade` помечен `x-openai-isConsequential: true`;
- Sandbox mutation Actions также consequential, где применимо;
- consequential UI никогда не заменяет server-side exact-confirmation gate.

## 6. GPT Editor после real enable

После намеренного owner enable/deploy:

1. проверить `getRealTradingStatus` вне сделки;
2. импортировать заново production `/openapi.json`;
3. Authentication оставить API Key → Bearer с тем же `GATEWAY_API_KEY`;
4. сверить operationId с таблицами выше;
5. применить целиком `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
6. выполнить Phase 3 negative Preview acceptance из `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`;
7. только после negative acceptance и rollback drill переходить к первой минимальной real LIMIT order по отдельному явному разрешению владельца.

GitHub не обновляет GPT Editor автоматически.