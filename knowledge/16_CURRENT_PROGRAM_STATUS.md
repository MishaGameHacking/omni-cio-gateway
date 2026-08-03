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
- exact-head Regression Shield #989 green.

### WP1 — Natural Language CIO Router: COMPLETE

- issue #182 / PR #184;
- merged to `main` as `7f6772889837ba632dc40c893d080a35b5f902ff`;
- exact-head Regression Shield #1002 fully green;
- deterministic Russian routing, exact-action isolation and fail-closed execution ambiguity accepted;
- router remains internal/read-only and hard-codes `execution_authorized=false`.

Architecture: `docs/architecture/V9_NATURAL_LANGUAGE_CIO_ROUTER.md`.

### WP2 — Investment Policy Statement Engine: COMPLETE

- issue #186 / PR #187;
- merged to `main` as `75c9ae078309f32d1519b76cbedd89a221b62bf0`;
- exact-head Regression Shield #1014 fully green;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- versioned owner IPS is separate from non-personalized `ConservativeRiskPolicyV1`;
- objective, horizon, explicit liquidity reserve, risk willingness/capacity and maximum drawdown are explicit;
- position/group/sector/currency concentration limits are deterministic;
- allowed/prohibited markets and instrument classes cannot conflict;
- material deny constraints require owner provenance/confirmation;
- system safe defaults cannot impersonate owner policy;
- bond permission requires both rating floor and named rating scale;
- annual review/effective/superseded states fail closed;
- deterministic SHA-256 policy reference binds future immutable plans;
- incomplete/invalid/unconfirmed policy blocks personal sizing;
- margin, short, withdrawal, transfer and autonomous real execution remain `Literal[False]`.

Architecture: `docs/architecture/V9_INVESTMENT_POLICY_STATEMENT.md`.

### WP3 — Market Universe Engine: IN PROGRESS

Tracking: issue #188 / draft PR #189.  
Branch: `v9/wp3-market-universe`.  
Architecture: `docs/architecture/V9_MARKET_UNIVERSE_ENGINE.md`.

Current implementation builds a reproducible broker-grounded universe from T-Invest:

- `Shares`, `Bonds`, `Etfs` only;
- `INSTRUMENT_STATUS_BASE` for the API-tradable base list;
- UID / position UID / FIGI / ISIN / ticker+class_code identity evidence;
- deterministic exact-duplicate removal and stable-alias conflict detection;
- API buy/sell, IIS, qualified-investor, missing-test, TCA, OTC, liquidity and real-exchange evidence;
- account eligibility refresh without retaining `user_id` or full account ID;
- fail-closed quality for incomplete sources, invalid rows, identity conflicts or unknown account eligibility;
- deterministic source-order-invariant SHA-256 content fingerprint;
- six-hour validated catalog cache while account eligibility stays fresh;
- repository guard explicitly forbids `FindInstrument` enumeration and trading/Sandbox mutation surfaces in the WP3 runtime.

WP3 adds no public route, OpenAPI Action or GPT Editor change. It is not complete until exact-head Regression Shield is green and the package is squash-merged.

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

WP1–WP3 add no withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management.

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
