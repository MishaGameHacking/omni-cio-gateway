# Omni-CIO — Secrets, persistent storage and Render boundary

Этот файл хранит только архитектуру и **имена** переменных. Значения secrets никогда не записываются в GitHub.

## Production service

Единственный поддерживаемый Render Web Service:

`omni-cio-gateway`

Base URL: `https://omni-cio-gateway.onrender.com`

Entrypoint: `app:app`

Не создавать отдельный trading service. Read-only, Sandbox и conditional real execution живут в одном Gateway, но используют разные broker credentials и разные server-side switches.

## Three credential contours

### 1. Production read-only

`TINVEST_TOKEN`

- существующий production read-only token;
- не повышать права;
- не заменять full-access token-ом;
- real execution package не использует его как fallback.

### 2. Sandbox

`TINVEST_SANDBOX_TOKEN`

- отдельный Sandbox token;
- работает только через T-Invest Sandbox;
- виртуальные деньги only.

### 3. Real execution

`TINVEST_TRADING_TOKEN`

- отдельный **account-scoped full-access trading token**;
- scope должен соответствовать одному intended broker account;
- **не transfer-access**;
- используется только `omni_cio.real_trading`;
- не заменяет `TINVEST_TOKEN`;
- token value не возвращается пользователю и не сохраняется в execution journal.

## Gateway secret

`GATEWAY_API_KEY`

Одно secret value используется:

- Render Environment: `GATEWAY_API_KEY`;
- GPT Action Authentication: API Key → Bearer.

T-Invest tokens в GPT Editor не вводятся.

## TLS

`SSL_TBANK_VERIFY=True`

TLS verification не отключать. Sandbox и real REST clients используют общий verified T-Bank CA helper и fail closed, если обязательный CA material недоступен.

## Sandbox environment

```text
TINVEST_TOKEN=<existing read-only production token>
TINVEST_SANDBOX_TOKEN=<separate Sandbox token>
GATEWAY_API_KEY=<existing Gateway secret>
SANDBOX_TRADING_ENABLED=true|false
SANDBOX_CONFIRMATION_TTL_SECONDS=120
SSL_TBANK_VERIFY=True
```

Rollback Sandbox:

`SANDBOX_TRADING_ENABLED=false` → redeploy/restart → Sandbox routes absent.

## Real execution environment

До owner acceptance keep:

```text
REAL_TRADING_ENABLED=false
```

Перед controlled enable required:

```text
TINVEST_TOKEN=<UNCHANGED read-only token>
TINVEST_TRADING_TOKEN=<separate account-scoped full-access non-transfer token>
GATEWAY_API_KEY=<existing Gateway secret>
REAL_TRADING_ENABLED=false
REAL_TRADING_MAX_ORDER_RUB=<small positive owner-approved cap>
REAL_TRADING_MAX_DAILY_RUB=<small positive owner-approved cap>
REAL_TRADING_CONFIRMATION_TTL_SECONDS=120
REAL_TRADING_MARKET_MAX_AGE_SECONDS=15
SSL_TBANK_VERIFY=True
```

Code ceilings exist above Render-configured caps; configuration cannot raise v1 beyond the reviewed code ceiling.

## Durable storage gate

Real execution cannot use process memory or ordinary Render ephemeral filesystem.

Existing `omni-cio-gateway` service must have a **Render persistent disk** mounted at:

`/var/data`

Production journal path is fixed by code:

`/var/data/omni-cio-real-trading.sqlite3`

The GPT cannot choose this path.

If `/var/data` is absent, token missing, limits invalid, schema unsupported or journal integrity fails:

- real execution is not ready;
- mutation routes are not published when static initialization fails;
- no real broker order should be submitted.

Journal properties:

- SQLite WAL;
- `synchronous=FULL`;
- atomic `BEGIN IMMEDIATE` daily reservation;
- HMAC-authenticated rows derived from Gateway secret;
- proposal/request UUID/state/confirmation evidence/daily accounting only;
- no broker token/Authorization header.

Details: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.

## Real kill switch

`REAL_TRADING_ENABLED`

- absent/false → all Real Trading Actions absent from OpenAPI;
- true + incomplete static config → status-only fail-closed surface;
- true + valid static config → narrow real surface can register.

Kill switch does **not** authorize a trade. Every order still needs fresh proposal + exact owner confirmation in a new message.

Rollback begins with:

```text
REAL_TRADING_ENABLED=false
```

then redeploy/restart and re-import OpenAPI in GPT Editor if the Action surface changed.

## Real hard-limit variables

`REAL_TRADING_MAX_ORDER_RUB`

- mandatory before real publish;
- positive finite decimal;
- must be below/equal immutable code ceiling.

`REAL_TRADING_MAX_DAILY_RUB`

- mandatory before real publish;
- positive finite decimal;
- must be >= per-order cap;
- must be below/equal immutable code ceiling.

`REAL_TRADING_CONFIRMATION_TTL_SECONDS`

- default 120;
- accepted range 30..600.

`REAL_TRADING_MARKET_MAX_AGE_SECONDS`

- default 15;
- accepted range 1..60;
- freshness uses trusted order-book timestamp.

## Correct connection topology

```text
Custom GPT
  │ Authorization: Bearer <GATEWAY_API_KEY>
  ▼
Omni-CIO Gateway / Render
  ├── <TINVEST_TOKEN> ──────────────► Production T-Invest / read-only
  ├── <TINVEST_SANDBOX_TOKEN> ─────► T-Invest Sandbox / virtual only
  └── <TINVEST_TRADING_TOKEN> ─────► Production T-Invest / confirmed LIMIT BUY/SELL only
                 │
                 └── durable proposal journal → /var/data
```

## Rotation

### Read-only token

Update only `TINVEST_TOKEN`, then read-only smoke. Trading/Sandbox tokens unchanged.

### Sandbox token

Disable Sandbox → update `TINVEST_SANDBOX_TOKEN` → redeploy → enable → status + virtual smoke.

### Real trading token

1. set `REAL_TRADING_ENABLED=false`;
2. revoke/replace only `TINVEST_TRADING_TOKEN`;
3. keep `TINVEST_TOKEN` unchanged;
4. redeploy;
5. controlled status/account-binding acceptance before re-enable.

### Gateway key

If `GATEWAY_API_KEY` changes, also update GPT Action Bearer. Because the execution journal integrity key is derived from this secret, do **not** casually rotate it while retaining an existing real execution journal. Follow a dedicated migration/retention procedure or archive/reinitialize the journal only when no unresolved real proposals/orders remain.

## Never store in GitHub / Knowledge / Instructions / user responses

- values of `TINVEST_TOKEN`;
- values of `TINVEST_SANDBOX_TOKEN`;
- values of `TINVEST_TRADING_TOKEN`;
- values of `GATEWAY_API_KEY`;
- Authorization headers;
- full broker account IDs;
- private positions/operations as configuration;
- Render secret exports.

## Release order

Real-money owner configuration is allowed only after engineering Phases 0–2 are merged and exact-head Regression Shield/security checks are green.

Then follow exactly:

`docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`

GitHub changes do not configure Render or GPT Editor automatically.