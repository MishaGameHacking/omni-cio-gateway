# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-03

Этот файл хранит короткую долговременную память **одного проекта**: личного Custom GPT Omni-CIO и его Gateway для T-Invest.

## 1. Поддерживаемый продукт

Единственный пользовательский интерфейс:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Production GPT Editor payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Архитектура:

```text
Custom GPT → Omni-CIO Gateway (`app:app`, Render Free)
                    │
                    ├→ TINVEST_TOKEN → production read-only
                    ├→ TINVEST_SANDBOX_TOKEN → optional T-Invest Sandbox
                    ├→ TINVEST_TRADING_TOKEN → confirmed real LIMIT BUY/SELL
                    └→ Upstash Redis Free → durable real-execution journal
```

GitHub хранит backend-код и эталон GPT configuration. Render запускает Gateway. GPT Editor хранит фактически применённые Instructions/Knowledge/Bearer configuration и не синхронизируется с GitHub автоматически.

## 2. Protected production baseline

**Omni-CIO v8.6.1 real BUY/SELL v1 полностью released и owner-accepted.**

Protected release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

Accepted real-money lifecycle:

`prepare → exact owner confirmation → single broker submit → broker state → confirmed fill → portfolio/operations reconciliation → safe replay with no second submit`.

Observed first real acceptance:

- SBER BUY, 1 lot / 1 share;
- LIMIT order accepted by T-Invest;
- broker reconciled `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot executed at 280.55 RUB;
- executed commission 0.84 RUB;
- real portfolio reconciled to SBER = 1 share / 1 lot;
- operations reconciled purchase and separate commission;
- exact confirmation replay did not call `executeRealTrade` again and did not create a second broker order.

**Release state: v8.6.1 = 100% complete.**

## 3. Active v9 program

Owner-approved second-major-release program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Status: **OWNER-APPROVED / PROGRAM LOCKED**.

Until its Definition of Done is complete:

- do not start a competing roadmap, duplicate bot, second Gateway, separate frontend or unrelated execution surface;
- allowed work is a listed v9 package, blocking defect repair, security/dependency maintenance or preservation of stable v8.6.1;
- v8.6.1 must remain recoverable and operational throughout development;
- no v9 capability may be represented as implemented before code, tests, CI and required acceptance prove it.

Protected baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Tracking epic: GitHub issue #176.

## 4. Current production configuration

- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Recommended model: Thinking 5.6.
- User timezone: Europe/Moscow / MSK.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.
- Real durable journal: external Upstash Redis over HTTPS.
- `REAL_TRADING_ENABLED=false` remains master rollback state.

Exact status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 5. Gateway capability contours

### Production read-only

Capabilities include:

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

Current production portfolio-management routing:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

### Optional Sandbox

Uses only `TINVEST_SANDBOX_TOKEN` and fixed Sandbox host.

Sandbox remains virtual-only:

- `sandbox=true`;
- `real_money=false`;
- own-funds/own-position preflight;
- exact short-lived confirmation;
- idempotent submit;
- isolated virtual order state/cancel behavior.

### Real execution v1

Conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real v1 remains deliberately narrow:

- BUY/SELL only;
- supported cash share/ETF only;
- RUB;
- LIMIT/CURRENCY/DAY only;
- own funds / own position only;
- exact short-lived owner confirmation in a separate turn;
- fresh trusted market/order book;
- hard per-order/daily limits;
- UUID idempotency;
- no automatic retry after possible submit;
- broker reconciliation required.

## 6. Absolute execution safety boundary

Always preserve:

- `TINVEST_TOKEN` remains read-only;
- separate account-scoped full-access non-transfer `TINVEST_TRADING_TOKEN` for real execution;
- read-only, Sandbox and Real remain isolated;
- immutable proposal before real submit;
- explicit exact owner confirmation in a new message;
- `PostOrder` at most once per proposal/request UUID;
- ambiguous possible-submit → unknown/do-not-resubmit, reconciliation only;
- `submitted` is never called `filled` without broker proof;
- own-funds BUY and own-position SELL;
- margin/short disabled;
- stale/incomplete/contradictory market blocks execution;
- durable journal outage/tamper fails closed;
- account IDs are masked;
- secrets never enter GitHub, Knowledge or user-visible output.

Not part of current real release:

- withdrawal/transfer of money;
- securities transfer;
- MARKET/BESTPRICE real execution;
- margin/short;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder/PostOrderAsync;
- autonomous recurring real-money execution;
- token management through GPT.

Future v9 work must not weaken these boundaries without a separately approved threat model and release.

## 7. Durable real-execution state

Production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Properties:

- works from Render Free over HTTPS;
- survives Render sleep/deploy/restart;
- HMAC-authenticated metadata/proposal/day-counter state;
- atomic transition/daily-cap reservation;
- no memory fallback on outage;
- secret values are not stored inside proposals.

SQLite remains compatibility/test only.

## 8. GPT behavior baseline

For ordinary `УПРАВЛЯЙ ПОРТФЕЛЕМ` in production v8.6.1:

1. `getPortfolioSnapshot`;
2. if successful `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. analysis.

This is analysis, not trade authorization.

Exact-action requests remain isolated: `вызови только X` means no other Actions.

Normal real order lifecycle remains:

1. obtain current broker/market facts;
2. verify real readiness;
3. `prepareRealTrade`;
4. show REAL MONEY proposal, masked account, exact terms, preview, expiry and phrase;
5. stop;
6. owner sends exact phrase in a new message;
7. only then `executeRealTrade`;
8. broker-state reconciliation;
9. portfolio/operations reconciliation after confirmed execution.

## 9. v9 target behavior

The v9 program evolves the same product toward:

- natural-language intent routing without Action-name knowledge;
- versioned Investment Policy Statement;
- full broker-available market-universe ingestion;
- deterministic candidate funnel;
- evidence/research engine;
- credit/rating/default engine 2.0;
- Fund X-Ray;
- portfolio risk engine 2.0;
- meta-strategy selection;
- portfolio optimizer and capital scaling;
- immutable multi-leg portfolio plans;
- confirmed plan execution;
- read-only Watchtower;
- durable decision journal/evaluation loop;
- final Custom GPT v9 configuration and full GitHub recovery.

Critical financial constraints and calculations belong in deterministic Gateway code. The model interprets intent, synthesizes evidence and explains decisions; it must not bypass server policy.

## 10. Market / sizing rules

- last price != guaranteed execution price;
- fresh order-book/trading status required for real proposal;
- stale/partial market blocks real execution;
- `withdraw_limits` != automatic buying budget;
- technical affordability != personal sizing;
- BUY sizing uses own funds, SELL sizing own position;
- margin capacity is ignored for authorization;
- larger capital must be handled by risk/liquidity/participation/staged-execution logic, not by simply raising one hard cap.

## 11. Evidence / credit direction

Important claims should prioritize official/primary evidence. Rating logic must distinguish issuer, issue and guarantor and preserve agency/scale/date/outlook rather than average incompatible ratings.

v9 must use deterministic identity and evidence provenance before strong portfolio recommendations.

## 12. Secrets

Render/external systems only:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — Sandbox only;
- `TINVEST_TRADING_TOKEN` — real execution only, non-transfer;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer;
- `UPSTASH_REDIS_REST_URL` — journal endpoint;
- `UPSTASH_REDIS_REST_TOKEN` — journal secret.

Never commit values or expose them in GPT responses, issues, PRs or Knowledge.

## 13. Runtime dependency warning

Current `app.py` still depends on `app_v371.py`, `app_v360.py` and wrapper/core files. Do not delete them as legacy without a separate compatibility refactor and full Regression Shield.

## 14. Canonical files

- `README.md` — product/runtime overview.
- `AGENTS.md` — engineering rules.
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` — long-lived project context.
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` — current state.
- `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` — locked v9 roadmap.
- `docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md` — protected baseline/migration contract.
- `gpt/SETUP_INDEX.md` — recovery entry.
- `gpt/CONFIGURATION.md` — GPT registry.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` — production Instructions.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` — engineering reference.
- `gpt/knowledge/` — canonical production Knowledge.
- `gpt/ACTIONS_CATALOG.md` — Action catalog.
- `gpt/SECRETS_AND_RENDER.md` — external secret boundary.
- `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` — accepted real release evidence.

## 15. Git workflow

Significant changes:

`branch → PR → exact-head Regression Shield/security → review → squash merge → external acceptance when required`.

Do not bypass CI for broker-write or durable-state changes.

## 16. Current readiness

- read-only production: accepted;
- Sandbox: accepted;
- real BUY/SELL v1: accepted and release-complete;
- v8.6.1 protected baseline: active;
- v9 program: active/locked, under development;
- user-facing GPT remains v8.6.1 until WP15 is completed and owner-accepted.
