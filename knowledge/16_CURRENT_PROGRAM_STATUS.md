# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**. The protected production release remains **v8.6.1** until WP15.

Production invariants:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- stable Render entrypoint: `app:app`;
- production read-only, Sandbox and Real contours remain separated;
- real BUY/SELL v1 is owner-accepted and release-complete;
- durable real journal: Upstash Redis over HTTPS;
- `REAL_TRADING_ENABLED=false` remains the master real-money rollback;
- v9 development does not alter the applied Custom GPT before WP15 and never grants broader real-money authority implicitly.

Protected v8.6.1 release commit: `baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`.

## Canonical v9 program

Roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Tracking epic: #176.

Development always continues with the earliest dependency-ready incomplete work package. No duplicate bot, second Gateway, separate frontend or competing roadmap is permitted.

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
| WP11 Immutable Portfolio Plan Protocol | COMPLETE | #207 / #208 | squash merge `7c3006d332041ec352f0c2eab8c7cb70e4c1a6af`; exact-head Regression Shield #1114 on `b97a6241...` |
| WP12 Safe Plan Execution Engine | IN PROGRESS — FINAL GATE | #209 / draft #211 | implementation, architecture, threat/data contracts and acceptance tests complete on `v9/wp12-safe-plan-execution`; final exact-head Regression Shield + zero review threads + squash merge still required |
| WP13 Portfolio Watchtower | PENDING | — | starts only after WP12 merge |
| WP14 Decision Journal / Evaluation | PENDING | — | — |
| WP15 Custom GPT v9 Configuration & Recovery | PENDING | — | applied GPT remains v8.6.1 until then |

## WP11 completion evidence

WP11 is complete and merged:

- issue #207 / PR #208;
- squash-merged to `main` as `7c3006d332041ec352f0c2eab8c7cb70e4c1a6af`;
- final tested head `b97a62412fe8accf8ebec528a63d8ad0b5087154`;
- exact-head Regression Shield #1114 fully green;
- exact immutable `PORTFOLIO_PLAN` binds portfolio + WP2 + WP8 + WP9 + WP10 + target WP8 state;
- deterministic ordered BUY/SELL/NO_ACTION legs, full cash/friction/НКД/tax semantics and material-drift cancellation;
- exact owner challenge derived from plan SHA;
- `execution_authorized=false` and `trading_methods=false` remain hard WP11 invariants;
- no broker-write authority exists in WP11.

Architecture:

- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN.md`;
- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN_THREAT_MODEL.md`;
- `docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN_DATA_CONTRACT.md`.

## WP12 — Safe Plan Execution Engine

Tracking: issue #209 / draft PR #211.  
Branch: `v9/wp12-safe-plan-execution`.

Architecture:

- `docs/architecture/V9_SAFE_PLAN_EXECUTION.md`;
- `docs/architecture/V9_SAFE_PLAN_EXECUTION_THREAT_MODEL.md`;
- `docs/architecture/V9_SAFE_PLAN_EXECUTION_DATA_CONTRACT.md`.

Implemented safety boundary:

- exact canonical WP11 plan SHA and exact owner approval challenge are required;
- approval records authorization for the exact plan but never submits by itself;
- WP12 reuses the accepted v8.6.1 `RealTradingServiceV1` proposal/preflight/idempotency/reconciliation primitive instead of adding a second broker stack;
- every stage revalidates portfolio progress, cash, policy/risk/strategy/optimizer/target-risk identity, broker instrument identity/lot size, fresh quote, price step, spread, turnover, depth and plan drift;
- the existing v8.6.1 own-funds/own-position `GetMaxLots`, per-order cap and atomic daily cap remain authoritative and are repeated immediately before submit;
- only `LIMIT / CURRENCY / DAY`, RUB, share/ETF, own-funds BUY and own-position SELL remain inside the proven real-money surface;
- deterministic execution journal uses compare-and-swap revisioning; production requires durable Upstash storage;
- broker NEW/PARTIAL remains active and is never resubmitted;
- terminal fills require independent read-only portfolio/cash reconciliation before progression;
- partial terminal fill returns only the remainder to the following Moscow day;
- ambiguous possible-submit halts all remaining plan work and permits only original request-id reconciliation; replay cannot duplicate `PostOrder`;
- plan expiry blocks new prepare/submit but never suppresses reconciliation of a request that may already have reached the broker;
- current WP8/WP9/WP10/target-risk SHA drift after approval fails closed;
- before first confirmed fill, the portfolio snapshot and current-risk SHA must still equal the exact WP11 starting state;
- WP11 validity now spans the exact WP10 `required_execution_days` horizon while retaining the short final-day validity tail;
- WP12 schedules multi-leg plans by tranche (`stage_index`) and then exact leg sequence, so portfolio staging remains synchronized;
- a given immutable instrument may submit at most one staged slice per Moscow calendar day;
- a tighter real-order cap may reduce slice size only when all required stages still fit inside immutable plan expiry; otherwise preparation fails with `PLAN_EXECUTION_PLAN_HORIZON_TOO_SHORT` instead of extending authorization or raising the cap.

Permanent guards and acceptance coverage include:

- `scripts/check_plan_execution_boundary.py` repository authority check;
- mypy scope for the execution package and boundary guard;
- full fake-client lifecycle: approval, one submit, partial fill, terminal reconciliation and completed replay;
- already-submitted proposal replay with zero duplicate submits;
- ambiguous-submit reconciliation-only recovery;
- instrument and upstream SHA drift fail-closed tests;
- plan-expiry/new-submit vs prior-submit reconciliation semantics;
- deterministic WP10 two-day staging and same-instrument Moscow-day cadence;
- hard-cap horizon-stretch rejection;
- durable Upstash restart/CAS/stale-writer/tamper/wrong-secret tests;
- broker reconciliation normalization and malformed-state rejection;
- explicit NO_ACTION no-session behavior;
- durable journal required by default;
- hard-coded prohibition of transfer/withdrawal, margin, short, MARKET/BESTPRICE, stop/replace/async submit and autonomous recurring execution.

WP12 is **not complete** until the final branch head passes the full exact-head Regression Shield, review threads are zero and PR #211 is squash-merged. No GPT Editor change and no real-cap increase is part of this development gate.

## Next dependency after WP12

After WP12 squash merge, continue with **WP13 — Portfolio Watchtower** from the canonical master plan. WP13 must be monitoring/read-only by default and must not create a recurring autonomous real-money executor.

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

WP12 orchestrates that same proven primitive for an exact owner-approved WP11 plan; it does not add withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring real execution or token management.

## v8.6.1 owner acceptance evidence

Owner Phase 4 on 2026-08-03 proved one explicitly authorized SBER LIMIT BUY with exactly one submit, broker-confirmed fill and portfolio/operations reconciliation. Canonical recovery invariant: **idempotent replay verified with no second submit**.

**Production release state: Omni-CIO v8.6.1 real BUY/SELL v1 — complete and protected while v9 development continues.**
