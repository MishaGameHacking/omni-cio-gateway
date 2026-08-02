# Omni-CIO security policy

Omni-CIO работает с финансовыми данными. Production read-only, Sandbox и conditional real execution являются отдельными контурами с разными credentials и независимыми kill switches.

Реальный write-контур существует в коде только как узкий default-off release: он не публикуется при `REAL_TRADING_ENABLED=false` и не считается готовым/авторизованным без durable journal, dedicated trading token, server limits и owner acceptance.

## Секреты и приватные данные

Никогда не публиковать в GitHub Issues, Pull Requests, source files или документации значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization/Bearer headers;
- полный broker account ID;
- реальные приватные broker reports/positions/operations;
- Render/GPT/Upstash credentials;
- private keys/certificates.

Использовать только безопасные placeholders и маскированные идентификаторы.

## Production credential isolation

### Read-only

`TINVEST_TOKEN`:

- остаётся read-only;
- никогда не повышается до full-access ради real execution;
- real-trading package не использует его как fallback.

### Sandbox

`TINVEST_SANDBOX_TOKEN`:

- Sandbox only;
- fixed Sandbox host;
- virtual money only.

### Real execution

`TINVEST_TRADING_TOKEN`:

- separate account-scoped full-access token;
- **без transfer access**;
- только для narrow `omni_cio.real_trading` OrdersService allowlist;
- не хранится в durable journal;
- не возвращается GPT/user.

## Критические production runtime-инварианты

- `app:app` — стабильный production entrypoint.
- Secrets поступают через environment variables.
- Account identifiers маскируются перед user-facing output.
- Ошибки очищаются от sensitive payload before exposure.
- Purchase/sale-capacity analytics не создаёт заявок.
- Withdrawal/transfer/securities-transfer surface отсутствует.
- Real MARKET/BESTPRICE execution отсутствует.
- Margin/short, stop order, replace, async submit и autonomous recurring execution отсутствуют в real v1.
- `REAL_TRADING_ENABLED=false` — default/rollback state; real Actions отсутствуют из OpenAPI.
- Real flag сам по себе не достаточен: invalid token/policy/durable journal fail closed.
- Реальный submit возможен только после separate proposal и exact short-lived owner confirmation в новом user turn.
- `submitted` никогда не считается `filled` без broker execution status.
- ambiguous possible-submit state никогда не auto-retry-ится.

## T-Invest Sandbox boundary

Sandbox execution может быть зарегистрирован только при `SANDBOX_TRADING_ENABLED=true`.

Защитные требования:

- outbound host жёстко фиксирован на `sandbox-invest-public-api.tbank.ru`;
- используется отдельный `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TOKEN` не передаётся sandbox-клиенту;
- sandbox responses явно маркируются `sandbox=true` и `real_money=false`;
- поддерживаются только allowlisted Sandbox methods;
- transfer/withdrawal и production real account mutation не входят в sandbox package;
- `confirmMarginTrade=false`;
- BUY sizing сверяется только с own-funds limits;
- SELL sizing сверяется только с own-position limits;
- proposal не является submit;
- подтверждение HMAC-bound к параметрам, имеет короткий TTL и не меняет заявку;
- broker limits повторно проверяются непосредственно перед submit;
- request `orderId` — UUID/idempotency key;
- повтор execution после успешного submit не создаёт вторую заявку;
- timeout/5xx после possible submit никогда не приводит к automatic retry;
- закрытие/пополнение/отмена Sandbox требуют явных подтверждений;
- sandbox account ID маскируется.

Sandbox in-memory proposal state намеренно инвалидируется restart-ом. Это относится только к виртуальному contour.

## Real execution v1 boundary

Conditional real Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- consequential `executeRealTrade`;
- `getRealOrderState`.

Real v1 разрешает только:

- BUY/SELL;
- supported cash share/ETF;
- RUB;
- LIMIT / CURRENCY / DAY;
- own-funds BUY;
- own-position SELL;
- exact price step;
- fresh trusted order book;
- small configurable per-order/daily caps below immutable code ceilings.

Prepare/execute separation:

1. server resolves/binds exactly one trading account to read-only account;
2. fresh market + instrument identity checked;
3. `GetMaxLots` / `GetOrderPrice` preflight;
4. durable immutable proposal created;
5. user receives exact phrase and submit stops;
6. exact phrase must arrive in a new user turn;
7. account/market/financial preflight repeats;
8. durable atomic daily reservation occurs **before** broker `PostOrder`;
9. submit occurs once using UUID idempotency key;
10. broker state is reconciled by request UUID.

Wrong/expired confirmation, changed preflight, insufficient own funds/position, account mismatch, stale market, hard-limit failure, durable-journal error or integrity failure all fail closed before submit.

## Free durable real-execution journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS *.upstash.io endpoint>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

This allows the Render service to remain on the Free plan without relying on its ephemeral filesystem.

Security requirements:

- Upstash URL must be HTTPS and `*.upstash.io`;
- REST token stays only in Render Environment;
- `trust_env=false`, redirects disabled;
- no fallback to process memory if Upstash is unavailable;
- journal metadata is HMAC-authenticated;
- each proposal envelope is revision/HMAC-authenticated;
- each Moscow-day notional counter is revision/HMAC-authenticated;
- authenticated proposal-count metadata is checked against stored proposal count;
- `integrity_check()` recomputes expected counted proposal totals and compares signed day counters;
- Redis Lua is limited to exact compare-and-swap updates for atomic journal state/daily-cap reservation;
- broker/Gateway/Upstash tokens are not stored inside proposal data;
- tamper/missing/corrupt state blocks readiness/submission.

SQLite durable journal remains an explicit compatibility/test backend only. It is not the selected production path for the current zero-cost deployment.

## Ambiguous broker submit

Network timeout/connection break/5xx after `PostOrder` may mean the request crossed the broker boundary.

Required behavior:

- proposal becomes `unknown` / `unknown_do_not_resubmit`;
- its daily notional remains reserved;
- automatic second `PostOrder` is forbidden;
- reconciliation uses the original request UUID and `GetOrderState` / `ORDER_ID_TYPE_REQUEST`;
- unresolved ambiguity is owner-visible and blocks automatic continuation.

A definitive broker rejection becomes `failed` and releases the reserved daily notional atomically.

## Custom GPT boundary

Canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.

- OpenAPI импортируется только из production Gateway.
- Authentication: API Key → Bearer с `GATEWAY_API_KEY`.
- Broker/Upstash tokens не передаются в GPT Editor.
- Default real flag OFF keeps all Real Trading Actions absent.
- Sandbox mutation Actions publish only after Sandbox enable.
- Real mutation Actions publish only after real enable + valid static readiness.
- Consequential UI никогда не заменяет server-side exact-confirmation gate.
- Ordinary portfolio-management request не является торговым подтверждением.
- Apps не используются одновременно с Actions.
- GitHub не синхронизирует GPT Editor/Render/Upstash автоматически.

## Data integrity

- Не смешивать валюты без verified FX + timestamp.
- Для денег использовать exact decimal logic.
- Partial/truncated/stale/contradictory data fail closed.
- Не double-count commissions/child operations/embedded trades.
- last price не выдавать за гарантированную executable price.
- при отсутствии fresh market data exact real proposal блокируется.
- Sandbox fill не является доказательством production fill/price behavior.
- Durable-journal availability/integrity не заменяет broker state; после submit всегда нужна broker reconciliation.

## Dependency and CI security

- Runtime/dev dependencies pinned и hash-locked.
- Lock files не редактируются вручную.
- External GitHub Actions pinned full commit SHA.
- Regression Shield проверяет compile, lint, formatting, types, contracts, tests, coverage, dependency audit, SAST and secret scan.
- Merge gates не используют broad `continue-on-error` для security/contract checks.
- Tests real/Sandbox execution use fake/mock transports; CI не отправляет broker orders и не использует live secrets.

## Перед merge real-execution/storage release

Подтвердить:

- stable `app:app`;
- default-off baseline OpenAPI unchanged;
- `TINVEST_TOKEN` no fallback in real package;
- dedicated production order host/method allowlist;
- no transfer/withdraw/cancel/replace/market/margin surface in real v1;
- wrong/expired confirmation cannot submit;
- own-funds/own-position failures block submit;
- preflight repeats immediately before submit;
- duplicate execution produces one broker submit total;
- ambiguous submission produces no retry;
- account IDs/secrets redacted;
- durable journal survives simulated restart;
- journal tamper is detected;
- daily cap is atomic under concurrency;
- Upstash backend rejects non-HTTPS/non-Upstash hosts;
- missing Upstash credentials publish no real mutation surface;
- no live network calls in CI;
- exact-head Regression Shield + dependency/SAST/secret security green.

## External owner acceptance before first real order

Green CI is insufficient. Before first real submit:

1. deploy default-off on existing Render Free service;
2. configure permanent Upstash Free database credentials in Render only;
3. configure separate account-scoped non-transfer T-Invest trading token;
4. configure small limits;
5. enable real contour intentionally;
6. `getRealTradingStatus` → ready, masked account, `journal_backend=upstash`;
7. read-only/Sandbox regression smoke;
8. wrong phrase rejection;
9. expiry rejection;
10. hard-cap rejection;
11. stale-market rejection;
12. over-position SELL rejection;
13. restart Render and verify durable journal survives;
14. rollback drill `REAL_TRADING_ENABLED=false` removes real Actions;
15. only after these checks may owner explicitly authorize the first controlled real LIMIT order.

Full procedure: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## Сообщение об уязвимости

Не прикладывать реальные secrets или financial payloads. Указать:

- затронутый commit/release;
- endpoint/module;
- шаги воспроизведения на фиктивных данных;
- ожидаемое и фактическое поведение;
- влияние;
- безопасный вариант исправления.
