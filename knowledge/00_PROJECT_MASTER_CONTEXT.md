# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-03

Этот файл хранит короткую долговременную память **одного проекта**: личного Custom GPT Omni-CIO и его Gateway для T-Invest.

## 1. Поддерживаемый продукт

Единственный пользовательский интерфейс:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Canonical GPT Editor behavior payload: **v8.6.1 Compact**.

Full engineering reference: **v8.6.0**.

Архитектура:

```text
Custom GPT → Omni-CIO Gateway (`app:app`, Render Free)
                    │
                    ├→ TINVEST_TOKEN → production read-only
                    ├→ TINVEST_SANDBOX_TOKEN → optional T-Invest Sandbox
                    ├→ TINVEST_TRADING_TOKEN → optional confirmed real LIMIT BUY/SELL
                    └→ Upstash Redis Free → durable real-execution journal
```

GitHub хранит backend-код и эталон GPT configuration. Render запускает Gateway. GPT Editor хранит фактически применённые Instructions/Knowledge/Bearer configuration и не синхронизируется с GitHub автоматически.

## 2. Current production baseline

- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Historical Sandbox fallback: v8.5.0.
- Historical read-only fallback: v8.4.1.
- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Recommended model: Thinking 5.6.
- User timezone: Europe/Moscow / MSK.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- With Sandbox and Real disabled: exactly 14 baseline GET Actions.
- Sandbox enable adds 8 isolated virtual-only Actions.
- Valid Real enable adds at most 4 narrow real Actions.
- `REAL_TRADING_ENABLED=false` remains master rollback state.

Owner Phase 3 + kill-switch drill completed on 2026-08-03. Real contour recovered to `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok` after rollback.

Exact status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 3. Gateway capability contours

### Production read-only

- health / connection;
- portfolio snapshot and enriched positions;
- instrument search;
- instrument/portfolio market snapshots;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview;
- operations history/analytics/reconciliation;
- broker-report reconciliation;
- final decision review.

### Optional Sandbox

- status/account/funding;
- virtual portfolio;
- BUY/SELL proposal + own-funds/own-position preflight;
- exact short-lived confirmation;
- confirmed virtual submit with idempotency protection;
- order-state verification;
- confirmed Sandbox cancellation.

### Optional real execution v1

Conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real v1:

- BUY/SELL only;
- supported cash share/ETF only;
- RUB;
- LIMIT/CURRENCY/DAY only;
- own funds / own position only;
- exact short-lived owner confirmation in a separate turn;
- fresh trusted order book;
- hard per-order/daily limits;
- UUID idempotency;
- no automatic retry after possible submit;
- broker reconciliation required.

## 4. Absolute safety boundary

Never implement/publish in first real release:

- withdrawal/transfer of money;
- securities transfer;
- MARKET/BESTPRICE real execution;
- margin/short;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder/PostOrderAsync;
- autonomous recurring execution;
- token management through GPT;
- real cancellation before its own later reviewed sub-release.

Always:

- keep `TINVEST_TOKEN` read-only;
- use separate account-scoped full-access **non-transfer** `TINVEST_TRADING_TOKEN`;
- mask user-facing account ID;
- fail closed on stale/incomplete/contradictory data;
- use exact decimal money logic;
- never call `submitted` a fill without broker proof;
- never automatically resubmit ambiguous broker requests.

## 5. Durable real-execution state

Production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Render Free has no free Persistent Disk, so production durability is external Upstash Redis over HTTPS.

Journal safety:

- server-selected backend only;
- HTTPS `*.upstash.io` restriction;
- HMAC-authenticated metadata/proposal envelopes/day counters;
- atomic Redis Lua compare-and-swap for proposal transition + daily cap;
- no fallback to memory when storage is unavailable;
- no broker/Gateway/Upstash token stored in proposal data;
- restart/deploy/sleep preserves real proposal/request UUID state.

SQLite remains compatibility/test only.

## 6. GPT behavior

For `УПРАВЛЯЙ ПОРТФЕЛЕМ`:

1. `getPortfolioSnapshot`;
2. on success `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. analysis.

This is analysis, not trade authorization.

Real execution requires separate explicit real BUY/SELL intent. Normal flow:

1. current broker/market facts;
2. `getRealTradingStatus` ready;
3. `prepareRealTrade`;
4. show REAL MONEY proposal, masked account, exact parameters, amount/commission, expiry and phrase;
5. stop — no submit;
6. owner sends exact phrase in a new message;
7. only then `executeRealTrade`;
8. immediately `getRealOrderState`;
9. after broker-confirmed fill, reconcile real portfolio/cash/operations.

Wrong/expired phrase must never be repaired or substituted by GPT.

Exact-action requests remain isolated.

## 7. Owner Phase 3 acceptance status

Completed on 2026-08-03 with zero real submit.

Verified live:

- permanent Upstash configuration;
- dedicated trading credential separated from read-only token;
- saved GPT v8.6.1 + 10 Knowledge files + refreshed OpenAPI;
- `getRealTradingStatus` ready, durable journal true, `journal_integrity=ok`;
- technical proposal creation without submit;
- expiry rejection;
- wrong confirmation rejection;
- own-funds guard without margin fallback;
- read-only exact-action isolation;
- kill switch to `trading_methods=false`;
- recovery back to ready with proposal rows preserved.

Hard cap, stale market, SELL-over-position, replay and ambiguous-submit remain covered by merged fake-client/regression tests. Do not force unsafe live conditions merely to duplicate code-level evidence.

## 8. Market / sizing rules

- last price != guaranteed execution price;
- fresh order-book/trading status required for real proposal;
- stale/partial market blocks real execution;
- `withdraw_limits` != automatic buying budget;
- technical affordability != personal sizing;
- Sandbox/Real BUY use own-funds limit, SELL own-position limit;
- margin capacity is ignored for authorization.

## 9. Secrets

Render only:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — Sandbox only;
- `TINVEST_TRADING_TOKEN` — real execution only, non-transfer;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer;
- `UPSTASH_REDIS_REST_URL` — real journal endpoint;
- `UPSTASH_REDIS_REST_TOKEN` — real journal secret.

Never commit values or expose them in GPT responses, issues, PRs or Knowledge.

## 10. Runtime dependency warning

Current `app.py` still depends on `app_v371.py`, `app_v360.py` and wrapper/core files. Do not delete them as legacy without a separate compatibility refactor and full Regression Shield.

## 11. Canonical files

- `README.md` — product/runtime overview.
- `AGENTS.md` — engineering rules.
- `SECURITY.md` — security boundary.
- `gpt/SETUP_INDEX.md` — setup/recovery entry.
- `gpt/CONFIGURATION.md` — GPT UI/config registry.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` — GPT Editor Instructions.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` — full engineering reference.
- `gpt/knowledge/` — canonical 10 Knowledge files.
- `gpt/ACTIONS_CATALOG.md` — conditional Action catalog.
- `gpt/SECRETS_AND_RENDER.md` — secret/free-infrastructure boundary.
- `docs/operations/SANDBOX_TRADING_RUNBOOK.md` — Sandbox acceptance.
- `docs/architecture/REAL_TRADING_V1.md` — real architecture.
- `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md` — durable journal.
- `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` — staged owner release.
- `docs/master-plan/` — original development specification.

## 12. Git workflow

Significant change:

`branch → PR → exact-head Regression Shield/security → review → squash merge → external acceptance`

Do not bypass CI for broker-write or durable-state code.

## 13. Current readiness

Read-only production: accepted.

Sandbox: accepted with `real_money=false`.

Real execution engineering + infrastructure + owner Phase 3 + rollback/recovery: accepted.

**Only remaining release gate:** Phase 4 first controlled real order, which requires a new explicit owner instruction at execution time, followed by broker state, portfolio/operations reconciliation and safe idempotent replay with no second submit.