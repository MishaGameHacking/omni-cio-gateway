# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**. The protected production release remains **v8.6.1** until WP15.

Current production invariants:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- stable entrypoint: `app:app`;
- production read-only, Sandbox and Real contours remain separated;
- real BUY/SELL v1 is owner-accepted and release-complete;
- durable real journal: Upstash Redis over HTTPS;
- `REAL_TRADING_ENABLED=false` remains the master rollback;
- v9 work does not grant broader execution authority before the relevant exit gates.

Protected v8.6.1 release commit: `baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`.

## Canonical v9 program

Roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Tracking epic: #176.

Development always continues with the earliest dependency-ready incomplete work package. No duplicate bot, second Gateway, separate frontend or competing roadmap is permitted by the program lock.

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
| WP9 Meta-Strategy Selector | COMPLETE | #203 / #204 | `f758fd73...`, exact-head #1088 |
| WP10 Portfolio Optimizer & Capital Scaling | COMPLETE | #205 / #206 | `f7392977...`, exact-head #1105 on `2ff38f96...` |
| WP11 Immutable Portfolio Plan Protocol | IN PROGRESS — FINAL GATE | #207 / draft #208 | branch `v9/wp11-immutable-portfolio-plan`; code/test head `9f410f88...` passed Regression Shield #1111 before final status/changelog sync |
| WP12 Safe Plan Execution Engine | PENDING | — | starts only after WP11 squash merge |
| WP13 Portfolio Watchtower | PENDING | — | — |
| WP14 Decision Journal / Evaluation | PENDING | — | — |
| WP15 Custom GPT v9 Configuration & Recovery | PENDING | — | applied GPT remains v8.6.1 until then |

## WP10 completion evidence

WP10 is complete:

- issue #205 / PR #206;
- squash-merged to `main` as `f73929771bcae4058c3c83b3d0632b8d66b8d05f`;
- final tested head `2ff38f962718e58ec9c12e0e89fd2605310592cc`;
- exact-head Regression Shield #1105 fully green;
- deterministic whole-lot optimizer bound to exact WP2/WP8/WP9/portfolio state;
- owner reserve preserved after settlement/НКД/fees;
- clean execution price separated from full economic valuation;
- fresh market/friction evidence required;
- large orders bounded by spread/depth/turnover/staging rules;
- complete hypothetical target revalidated through WP8;
- no broker-write authority; `trading_methods=false`.

Architecture: `docs/architecture/V9_PORTFOLIO_OPTIMIZER.md`.

## WP11 — current implementation package

Tracking: issue #207 / draft PR #208.  
Branch: `v9/wp11-immutable-portfolio-plan`.  
Architecture:

- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN.md`;
- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN_THREAT_MODEL.md`;
- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN_DATA_CONTRACT.md`.

WP11 compiles the exact upstream decision state into one frozen, versioned `PORTFOLIO_PLAN` and remains internal/read-only.

Current implementation includes:

- exact portfolio snapshot + recomputed WP2 policy fingerprint/reference + current WP8 + WP9 + WP10 + target WP8 bindings;
- full Pydantic re-validation of supplied upstream objects before cross-binding, so `model_copy` mutations cannot bypass validators by carrying a recalculated SHA;
- canonical recomputation of WP8/WP9/WP10 hashes;
- exact deterministic WP10 target rows and ordered BUY/SELL/NO_ACTION legs;
- plan totals reconciled to target rows, cash, embedded optimizer legs and WP8 before/after states;
- clean execution price, bond НКД, settlement notional, commissions, estimated tax and signed cash deltas preserved separately;
- build-time fail-closed freshness checks for market, friction and FX evidence;
- BUY requires current account eligibility; SELL does not incorrectly require buy eligibility for an already-held position;
- explicit validity window and complete hard-cancellation condition set;
- review-time market, friction and FX freshness plus clean-price/НКД/spread/turnover/depth/FX drift checks;
- extreme measured drift remains representable above 10,000 bps instead of overflowing a bounded tolerance type;
- any material mutation changes the canonical plan SHA;
- actionable owner challenge is derived from the exact plan SHA: `ПОДТВЕРЖДАЮ ПЛАН <PLAN_SHA_PREFIX>`;
- plan is revalidated before review; stale-hash plan mutation fails closed;
- valid review may expose the exact challenge but still hard-codes `execution_authorized=false` and `trading_methods=false`;
- no broker token/client/journal/order/submit/cancel/replace authority in WP11;
- dedicated `scripts/check_plan_boundary.py` plus boundary tests permanently guard the package;
- `omni_cio/plans` and the boundary guard are included in mypy scope.

Acceptance coverage includes:

- full WP2 → WP8 → WP9 → WP10 → WP11 actionable chain;
- full explicit `NO_ACTION` chain;
- immutable/hash mutation sensitivity and source-order invariance;
- valid fresh review and challenge binding;
- pre-valid and expired review;
- portfolio/policy/risk/strategy/optimizer/target-risk mutation cancellation;
- stale/future and missing evidence;
- clean-price and extreme-price drift;
- bond НКД drift;
- spread/turnover/depth deterioration;
- friction mutation;
- BUY eligibility cancellation and SELL non-buy-eligibility semantics;
- FX value/freshness drift;
- unknown-leg observation rejection;
- `model_copy` tamper rejection;
- repository authority boundary.

The code/test head `9f410f88e31fa161fcd713b9636ab7f460a6f5d6` passed security, Ruff, format, mypy, `app:app`, read-only release contract and full Regression Shield #1111. This documentation sync changes the branch SHA, therefore WP11 remains **IN PROGRESS** until the new final exact-head Regression Shield is fully green, PR review threads are clear and PR #208 is squash-merged.

## Next dependency after WP11

After WP11 squash merge, continue with **WP12 — Safe Plan Execution Engine**.

WP12 must reuse—not replace—the proven v8.6.1 single-order safety lifecycle as fallback and add execution only for an exact owner-approved immutable WP11 plan. Every leg must be revalidated immediately before submit for current market, spread, liquidity, price step, own funds/own position and risk. Remaining legs halt on drift or ambiguity. Large orders use staged LIMIT execution with partial-fill state and deterministic broker reconciliation. No recurring autonomous real-money execution, transfer, withdrawal, margin or short is allowed.

## Canonical production configuration

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- Render: Free;
- entrypoint: `app:app`;
- production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.

GitHub remains canonical for code/config/recovery reference but does not automatically synchronize GPT Editor, Render secrets or Upstash.

## Broker/execution safety remains unchanged

Production read-only uses only `TINVEST_TOKEN`. Sandbox uses `TINVEST_SANDBOX_TOKEN`. Real v1 uses the dedicated `TINVEST_TRADING_TOKEN` and remains limited to the accepted narrow lifecycle:

`fresh facts → immutable proposal → exact owner confirmation in a new user turn → one submit/idempotency → broker reconciliation`.

WP1–WP11 do not add withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management.

## v8.6.1 owner acceptance evidence

Owner Phase 4 on 2026-08-03 proved one explicitly authorized SBER LIMIT BUY with exactly one submit, broker-confirmed fill, portfolio/operations reconciliation and idempotent confirmation replay with no second submit.

**Production release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete and protected while v9 development continues.**
