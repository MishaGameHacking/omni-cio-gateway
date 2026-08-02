# Каталог Omni-CIO GPT Actions

Accepted backend baseline: **v3.10.0** до merge Sandbox release.

Gateway:

`https://omni-cio-gateway.onrender.com`

Schema:

`https://omni-cio-gateway.onrender.com/openapi.json`

`gatewayHealth` публичный; остальные Actions используют Bearer `GATEWAY_API_KEY`.

## Baseline real-money-safe surface

При `SANDBOX_TRADING_ENABLED=false` опубликованы ровно 14 GET Actions:

| operationId | HTTP | Path | Назначение |
|---|---:|---|---|
| `gatewayHealth` | GET | `/health` | Версия, build, capabilities, real-money read-only contract |
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

Baseline invariants:

- реальный `TINVEST_TOKEN` read-only;
- real order create/submit/replace/cancel/stop-order/withdraw/transfer отсутствуют;
- `trading_methods=false` относится к реальному broker contour;
- `getPurchaseCapacityPreview` не создаёт заявку;
- `getFinalDecisionReview` не подтверждает execution.

## Conditional Sandbox surface

Только при `SANDBOX_TRADING_ENABLED=true` Gateway дополнительно регистрирует 8 Actions, жёстко привязанных к T-Invest Sandbox и отдельному `TINVEST_SANDBOX_TOKEN`:

| operationId | HTTP | Path | Consequential | Назначение |
|---|---:|---|---:|---|
| `getSandboxTradingStatus` | GET | `/sandbox/status` | no | Проверить Sandbox token/host/accounts |
| `openSandboxAccount` | POST | `/sandbox/account/open` | yes | Открыть виртуальный Sandbox account после explicit confirmation |
| `fundSandboxAccount` | POST | `/sandbox/account/fund` | yes | Добавить виртуальные RUB после explicit confirmation |
| `getSandboxPortfolio` | GET | `/sandbox/portfolio` | no | Sandbox portfolio + positions |
| `prepareSandboxTrade` | POST | `/sandbox/trade/prepare` | no submit | Зафиксировать BUY/SELL proposal, preflight, TTL и confirmation phrase |
| `executeSandboxTrade` | POST | `/sandbox/trade/execute` | yes | Отправить только ранее подготовленный неизменяемый proposal после exact confirmation |
| `getSandboxOrderState` | GET | `/sandbox/order/status` | no | Проверить broker state по UUID request id |
| `cancelSandboxOrder` | POST | `/sandbox/order/cancel` | yes | Отменить только Sandbox order после explicit confirmation |

Sandbox responses обязаны различать контуры:

- `sandbox=true`;
- `real_money=false`;
- `sandbox_trading_methods=true`;
- `real_trading_methods=false`.

## Sandbox execution contract

`prepareSandboxTrade`:

- ничего не отправляет на биржу;
- требует точный instrument id, BUY/SELL, lots, MARKET/LIMIT, rationale;
- BUY проверяет own-funds max lots;
- SELL проверяет own-position max lots;
- limit order получает preliminary `GetSandboxOrderPrice`;
- создаёт UUID `order_id` для idempotency;
- возвращает short-lived HMAC-bound `confirmation_phrase`.

`executeSandboxTrade`:

- принимает только `proposal_id` + exact `confirmation_phrase`;
- не принимает instrument/side/quantity/price повторно, поэтому подтверждённые параметры нельзя подменить;
- повторно проверяет broker max-lots непосредственно перед submit;
- отправляет только `SandboxService/PostSandboxOrder`;
- `confirmMarginTrade=false`;
- успешный повтор того же proposal возвращается как idempotent replay без второго broker submit;
- timeout/5xx после потенциального submit → `unknown_do_not_resubmit`; автоматического retry нет.

`getSandboxOrderState` использует `ORDER_ID_TYPE_REQUEST` для reconciliation по клиентскому UUID.

`cancelSandboxOrder` также использует request id и отдельную confirmation phrase.

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
- response models имеют explicit object properties;
- Sandbox mutation Actions помечаются `x-openai-isConsequential: true`, но server-side confirmation остаётся обязательным и не полагается только на UI approval.

## Contract stability

Без migration plan не менять:

- существующие baseline `operationId`/paths;
- Bearer authentication;
- real-money read-only semantics;
- Sandbox host/token separation;
- Sandbox two-phase confirmation;
- UUID idempotency и no-auto-resubmit rule.

## GPT Editor update

При выключенном Sandbox повторный OpenAPI import должен по-прежнему показать 14 baseline GET Actions.

Для Sandbox acceptance:

1. merge/deploy Sandbox release;
2. добавить отдельный `TINVEST_SANDBOX_TOKEN` в Render;
3. `SANDBOX_TRADING_ENABLED=true`;
4. healthy redeploy;
5. проверить `/sandbox/status`;
6. повторно импортировать `/openapi.json`;
7. Authentication → API Key → Bearer, существующий `GATEWAY_API_KEY`;
8. проверить 14 baseline + 8 Sandbox Actions;
9. убедиться, что real-money mutation Actions отсутствуют;
10. применить `CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`;
11. выполнить `docs/operations/SANDBOX_TRADING_RUNBOOK.md`;
12. только после acceptance нажать `Update`.
