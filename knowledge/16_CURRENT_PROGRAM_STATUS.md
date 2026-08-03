# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current production release:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- production read-only analytics: accepted;
- isolated T-Invest Sandbox: accepted;
- real-money BUY/SELL v1: accepted and released;
- durable real journal: Upstash Redis over HTTPS;
- Render remains on Free plan;
- stable entrypoint: `app:app`;
- real BUY/SELL v1 Definition of Done is **100% complete**;
- `idempotent replay verified with no second submit`.

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

## Active v9 program

Canonical owner-approved/program-locked roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Tracking epic: GitHub issue #176.

Protected baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Development follows WP0 → WP15. Stable v8.6.1 remains recoverable and its real-execution safety contract may not be weakened by v9 feature work.

## Work-package progress

### WP0 — Baseline freeze and recovery correctness: COMPLETE

Merged to `main` via PR #181 as commit:

`4fd3993bdb56162bb730dca25e3ada7046e560cc`

Accepted evidence:

- protected v8.6.1 release commit pinned;
- GPT recovery/configuration drift reconciled;
- exact 10-file Knowledge registry enforced;
- active v9 program lock enforced;
- `AGENTS.md` requires the earliest dependency-ready incomplete work package;
- deterministic GPT recovery consistency checker and tests added;
- repository-layout guard recognizes read-only + Sandbox + confirmed Real v1;
- no runtime broker/OpenAPI/secret change;
- exact-head Regression Shield run #989: quality/contracts/coverage = success, dependency/SAST/secret security = success.

### WP1 — Natural Language CIO Router: IN PROGRESS

Tracking: GitHub issue #182.  
Architecture: `docs/architecture/V9_NATURAL_LANGUAGE_CIO_ROUTER.md`.

Current implementation branch adds an internal deterministic router for:

- exact-action diagnostics;
- portfolio analysis and management;
- risk review;
- issuer/instrument research;
- free-cash allocation;
- plan review;
- execution intent/confirmation classification;
- monitoring intent;
- fail-closed unknown/ambiguous intent.

Safety properties of the WP1 contract:

- pure classifier, no I/O;
- no public route and no OpenAPI change;
- no GPT Editor change;
- raw user text is not returned in routing state;
- advisory `стоит ли купить` is distinct from imperative execution;
- exact Action names lock scope and are never expanded;
- bare BUY/SELL does not silently become a real trade;
- real/Sandbox and BUY/SELL ambiguity requests clarification;
- confirmation phrases are classified but not server-validated;
- every route hard-codes `execution_authorized=false`;
- current v8.6.1 proposal/TTL/HMAC/idempotency/preflight gates remain authoritative.

WP1 is not complete until its exact-head Regression Shield is green and the package is squash-merged.

No user-facing v9 configuration is active yet. Applied GPT remains v8.6.1 until WP15.

## Canonical production configuration

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.

GitHub is canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash state.

## Broker contours

### Production read-only

`TINVEST_TOKEN` remains read-only and separate from execution credentials.

Current portfolio-management baseline remains:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

### Sandbox

Uses only `TINVEST_SANDBOX_TOKEN` and its isolated Sandbox contour. Sandbox remains `real_money=false`.

### Real execution v1

Uses only separate account-scoped `TINVEST_TRADING_TOKEN` without transfer access.

Published conditional Actions remain:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Current safety contract remains BUY/SELL, supported cash share/ETF, RUB, LIMIT/CURRENCY/DAY, own funds/own position, fresh trusted market, immutable proposal, exact short-lived owner confirmation in a new user turn, UUID idempotency, durable journal and broker reconciliation.

`submitted` never means `filled` without broker proof. Ambiguous possible-submit remains unknown/do-not-resubmit.

Not published: withdrawal/transfer, securities transfer, MARKET/BESTPRICE, margin/short, derivatives/currency execution, stop orders, ReplaceOrder, async submit, autonomous recurring real-money execution or token management through GPT.

## Durable journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Outage/tamper remains fail-closed with no process-memory fallback.

## Owner acceptance evidence for v8.6.1

Owner Phase 3 and kill-switch recovery completed on 2026-08-03.

Owner Phase 4 then completed with explicit authorization for one controlled real SBER LIMIT BUY:

- exactly one broker submit;
- broker reconciled `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot executed at 280.55 RUB;
- executed commission 0.84 RUB;
- real portfolio reconciled to SBER = 1 share / 1 lot;
- operations reconciled purchase + commission;
- confirmation replay did not invoke `executeRealTrade` again;
- no second broker submit or second purchase.

## Current safety state

- v8.6.1 production baseline remains active;
- real execution remains explicit-confirmation only;
- account output masked;
- `REAL_TRADING_ENABLED=false` remains the master rollback action;
- v9 development does not authorize broader live execution.

## v9 sequence after WP1

Next dependency-ready package after WP1 is WP2 — Investment Policy Statement Engine, followed by universe, deterministic candidate funnel, research/credit/fund engines, risk/strategy/optimizer, immutable plans, safe plan execution, Watchtower, evaluation journal and final GPT v9 recovery/configuration.

**Release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**
