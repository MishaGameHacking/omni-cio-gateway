# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

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

## Work-package evidence

| WP | State | Issue / PR | Merge / CI evidence |
|---|---|---|---|
| WP0 Baseline freeze | COMPLETE | #178 / #181 | `4fd3993b...`, Regression Shield #989 |
| WP1 Natural Language CIO Router | COMPLETE | #182 / #184 | `7f677288...`, #1002 |
| WP2 Investment Policy Statement | COMPLETE | #186 / #187 | `75c9ae07...`, #1014 |
| WP3 Market Universe Engine | COMPLETE | #188 / #189 | `5ae81aa9...`, #1019 |
| WP4 Deterministic Candidate Funnel | COMPLETE | #190 / #191 | `3946fc9a...`, #1035 |
| WP5 Research & Evidence Engine | COMPLETE | #193 / #194 | `f8f0bb95...`, #1043 |
| WP6 Credit, Rating & Default 2.0 | COMPLETE | #195 / #196 | `64316008...`, #1057 |
| WP7 Fund X-Ray Engine | COMPLETE | #197 / #198 | `15505272...`, #1064 |
| WP8 Portfolio Risk Engine 2.0 | COMPLETE | #199 / #201 | `24e027f1...`, #1078 |
| WP9 Meta-Strategy Selector | COMPLETE | #203 / #204 | `f758fd73...`, exact-head #1088 on `d95d56a9...` |
| WP10 Portfolio Optimizer & Capital Scaling | IN PROGRESS | #205 / draft #206 | branch `v9/wp10-portfolio-optimizer` |
| WP11 Immutable Portfolio Plan Protocol | PENDING | — | starts only after WP10 merge |
| WP12 Safe Plan Execution Engine | PENDING | — | — |
| WP13 Portfolio Watchtower | PENDING | — | — |
| WP14 Decision Journal / Evaluation | PENDING | — | — |
| WP15 Custom GPT v9 Configuration & Recovery | PENDING | — | applied GPT stays v8.6.1 until then |

Detailed accepted behavior for completed packages remains in their versioned architecture documents and Git/PR history. This status file is the current operational index, not a duplicate of every architecture specification.

## WP9 completion evidence

WP9 — Meta-Strategy Selector is complete:

- issue #203 / PR #204;
- squash-merged to `main` as `f758fd7325e5d3e6602fa441cc65f8cd3e10c2c3`;
- final tested head `d95d56a967aa822a22a2f8bbdec95748ad9734f7`;
- exact-head Regression Shield #1088 fully green;
- unresolved review threads/reviews/comments = 0 at merge gate;
- exact portfolio + WP2 policy + current WP8 risk binding;
- bounded five-regime comparison including `NO_ACTION`;
- risk willingness/capacity/horizon/WP8 state constrain strategy before ranking;
- fresh cost/tax provenance required;
- no expected-return or macro-regime forecast input;
- deterministic selection fingerprint and review/cancellation conditions;
- `omni_cio/strategy` internal/read-only with `trading_methods=false`.

Architecture: `docs/architecture/V9_META_STRATEGY_SELECTOR.md`.

## WP10 — current implementation package

Tracking: issue #205 / draft PR #206.  
Branch: `v9/wp10-portfolio-optimizer`.  
Architecture: `docs/architecture/V9_PORTFOLIO_OPTIMIZER.md`.

WP10 converts the exact WP9 strategy into deterministic lot-executable portfolio targets and then revalidates the complete hypothetical target through WP8.

Current implementation includes:

- exact portfolio snapshot + recomputed WP2 IPS fingerprint/reference + current WP8 assessment + WP9 selection binding;
- current WP8 baseline must have no proposed trades and identical before/after states;
- every current `RiskPositionV1` must bind exactly to an optimizer asset row;
- fixed reviewable WP9 regime component budgets with no expected-return/alpha input;
- WP9 `FORBIDDEN` / `ALLOWED` / `REQUIRED` component semantics preserved;
- owner liquidity reserve can only increase cash allocation;
- max-position policy applied before lot conversion;
- whole-lot deterministic sizing and explicit minimum meaningful-position rules;
- maximum target-position count and stable-key tie-breaks for small capital;
- clean execution-price evidence separated from full economic valuation;
- market evidence carries timestamp, source SHA-256, spread, turnover, top-of-book depth and clean price;
- bond market evidence carries НКД per lot; missing НКД blocks the trade instead of becoming zero;
- bond full value reconciles as `clean price + НКД / lot_size`;
- clean gross notional, НКД, settlement notional, commission, estimated SELL tax and signed cash delta are distinct leg fields;
- BUY cash is `-(settlement + commission)` and SELL cash is `settlement - commission - estimated tax`;
- large-capital sizing is bounded by average-turnover participation, top-of-book participation and maximum staging days;
- oversized trades are scaled to safe whole-lot capacity rather than declared fully executable;
- every leg records required execution days and `partial_fill_aware=true` without creating any order;
- cash is recomputed after settlement/НКД/fees and BUYs are reduced before the owner reserve can be spent;
- account-ineligible/unknown BUY exposure fails closed;
- stale/future market or friction evidence, wide spread and mutated price binding fail closed;
- deterministic trade IDs use sanitized stable key + SHA suffix; multi-leg ordering is canonical by full trade ID;
- CURRENT / TARGET / NO_ACTION scenarios are explicit and contain no return forecast;
- every changed target position becomes a real `ProposedTradeRiskEffectV1` and is passed into WP8;
- WP8 target must be decision-ready and policy-compliant, and its before-state must exactly equal the supplied current WP8 after-state;
- optimizer and target fingerprints are deterministic/source-order invariant;
- dedicated optimizer boundary guard forbids broker mutation/token surfaces and forecast/execution-authority fields;
- `omni_cio/optimizer` is in mypy scope and remains internal/read-only with `trading_methods=false`.

Acceptance coverage includes:

- normal lot-executable rebalance;
- source-order invariance;
- large-capacity scaling and staged execution;
- reserve-after-fees protection;
- missing/stale market evidence;
- missing friction evidence;
- missing bond НКД evidence;
- market-price binding mutation;
- WP8 target policy breach;
- same-version IPS mutation;
- small-cap microposition elimination;
- trade-ID collision-shaped multi-leg ordering;
- non-zero bond НКД settlement arithmetic.

WP10 is **not complete** until the final exact-head Regression Shield after all code/documentation changes is fully green, review threads are zero and PR #206 is squash-merged. Checks from an older SHA are evidence only; they are not the merge gate.

## Next dependency after WP10

Only after WP10 is squash-merged, continue with **WP11 — Immutable Portfolio Plan Protocol**.

WP11 must bind the exact portfolio, IPS, evidence, market, WP8 risk, WP9 strategy and WP10 optimizer result into a versioned immutable `PORTFOLIO_PLAN`; preserve ordered BUY/SELL/NO_ACTION legs, expected settlement/fees/cash/target weights/risk before-after, validity/drift/cancellation conditions, and a final read-only review. Any mutation must invalidate prior approval and plan replay must not duplicate orders.

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

WP1–WP10 add no withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management.

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
