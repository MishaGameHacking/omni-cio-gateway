# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current production release remains **v8.6.1**:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- read-only analytics: accepted;
- isolated T-Invest Sandbox: accepted;
- real BUY/SELL v1: owner-accepted and release-complete;
- durable journal: Upstash Redis over HTTPS;
- Render: Free;
- stable entrypoint: `app:app`;
- idempotent replay verified with no second submit;
- applied GPT remains v8.6.1 until WP15.

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

## Active v9 program

Canonical owner-approved/program-locked roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Tracking epic: #176.

Development follows the earliest dependency-ready incomplete package. Stable v8.6.1 remains recoverable and its real-execution safety contract cannot be weakened by v9 feature work.

## Work-package progress

### WP0 — Baseline freeze and recovery correctness: COMPLETE

- issue #178 / PR #181;
- merged to `main` as `4fd3993bdb56162bb730dca25e3ada7046e560cc`;
- exact-head Regression Shield #989 green;
- protected v8.6.1 baseline, GPT recovery consistency, exact Knowledge registry and v9 program lock are machine-checked.

### WP1 — Natural Language CIO Router: COMPLETE

- issue #182 / PR #184;
- merged to `main` as `7f6772889837ba632dc40c893d080a35b5f902ff`;
- exact-head Regression Shield #1002 green for quality/contracts/coverage and dependency/SAST/secret security;
- unresolved review threads = 0.

Accepted behavior:

- deterministic Russian routing without Action-name knowledge;
- exact Action invocation locks scope and is never expanded;
- conversational Action-name mention does not invoke it;
- advisory `стоит ли купить/продать` is not execution;
- bare BUY/SELL requires an explicit real/Sandbox contour;
- real/Sandbox and BUY/SELL ambiguity fail closed;
- common Russian portfolio/diversification typos are normalized;
- explicit plan review beats rebalance keywords;
- raw user free text is not retained in route state;
- every route hard-codes `execution_authorized=false`;
- no `app.py`, OpenAPI, broker or GPT Editor change.

Architecture: `docs/architecture/V9_NATURAL_LANGUAGE_CIO_ROUTER.md`.

### WP2 — Investment Policy Statement Engine: IN PROGRESS

Tracking: issue #186.  
Branch: `v9/wp2-investment-policy-statement`.  
Architecture: `docs/architecture/V9_INVESTMENT_POLICY_STATEMENT.md`.

Current WP2 implementation adds:

- versioned `InvestmentPolicyStatementV1` owner-policy contract;
- objective, horizon, explicit liquidity reserve, risk willingness, risk capacity and maximum drawdown;
- position/group/sector/currency concentration limits;
- allowed/prohibited markets and instrument classes;
- bond credit-quality floor + rating scale;
- tax/account review state and rebalance band;
- per-field provenance and owner-confirmation state;
- deterministic annual-review/effective/supersession gates;
- deterministic policy SHA-256 reference for later immutable plans;
- incomplete-policy blockers for personal sizing;
- `Literal[False]` protections for margin, short sales, withdrawals, transfers and autonomous real execution.

WP2 deliberately does **not** replace `ConservativeRiskPolicyV1`. The existing conservative policy remains a non-personalized safety baseline. No reserve, risk tolerance, capacity or personal sizing value is inferred from age, current holdings or technical affordability.

WP2 is not complete until tests, ruff, mypy and exact-head Regression Shield pass and the package is squash-merged.

## Canonical production configuration

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- Render plan: Free;
- entrypoint: `app:app`;
- production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.

GitHub remains canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash.

## Broker/execution safety remains unchanged

Production read-only uses only `TINVEST_TOKEN`.

Sandbox uses only `TINVEST_SANDBOX_TOKEN` and remains `real_money=false`.

Real v1 uses only dedicated `TINVEST_TRADING_TOKEN` and remains limited to the accepted narrow flow:

`fresh facts → immutable proposal → exact owner confirmation in a new user turn → one submit/idempotency → broker reconciliation`.

No withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management is added by WP1/WP2.

`REAL_TRADING_ENABLED=false` remains the master rollback state.

## v8.6.1 owner acceptance evidence

Phase 4 completed 2026-08-03 with one explicitly authorized controlled real SBER LIMIT BUY:

- exactly one submit;
- broker reconciled `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot executed at 280.55 RUB;
- commission 0.84 RUB;
- portfolio and operations reconciled;
- idempotent replay verified with no second submit.

**Production release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**
