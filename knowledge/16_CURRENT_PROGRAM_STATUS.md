# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**. The protected production release **v8.6.1 is 100% complete and protected** while the owner-approved v9 program continues. The applied Custom GPT remains v8.6.1 until WP15.

Production invariants:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- stable Render entrypoint: `app:app`;
- production read-only, Sandbox and Real contours remain separated;
- real BUY/SELL v1 remains owner-confirmed, immutable, idempotent and broker-reconciled;
- durable real journal remains Upstash Redis over HTTPS;
- `REAL_TRADING_ENABLED=false` remains the master real-money rollback;
- v9 development does not alter the applied Custom GPT before WP15 and does not grant broader real-money authority implicitly.

Protected v8.6.1 release commit: `baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`.

## Canonical v9 program

Roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Tracking epic: #176.

Development continues with the earliest dependency-ready incomplete work package. No duplicate bot, second Gateway, separate frontend, competing scheduler or parallel execution stack is permitted.

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
| WP10 Portfolio Optimizer & Capital Scaling | COMPLETE | #205 / #206 | `f7392977...`, exact-head #1105 |
| WP11 Immutable Portfolio Plan Protocol | COMPLETE | #207 / #208 | `7c3006d332041ec352f0c2eab8c7cb70e4c1a6af`, exact-head #1114 |
| WP12 Safe Plan Execution Engine | COMPLETE | #209 / #211 | `8f247fd3b966c16eb08fdfeed080010bdcbedde9`, exact-head #1160 on `e7022b89...` |
| WP13 Portfolio Watchtower | IN PROGRESS — FINAL EXACT-HEAD GATE | #212 / draft #213 | implementation/source sync complete on `v9/wp13-portfolio-watchtower`; final Regression Shield + security + zero review threads + squash merge required |
| WP14 Decision Journal / Evaluation & Learning Loop | PENDING | #214 | implementation starts only after WP13 merge |
| WP15 Custom GPT v9 Configuration & Recovery | PENDING | — | applied GPT remains v8.6.1 until then |

## WP12 completion evidence

WP12 is complete and squash-merged to `main` as `8f247fd3b966c16eb08fdfeed080010bdcbedde9` after exact-head Regression Shield #1160 on `e7022b89e4d212ecdd7ac72e0ff9e88170c4e724` with zero unresolved review threads.

Safe Plan Execution:

- executes only an exact owner-approved immutable WP11 plan;
- reuses the protected v8.6.1 real-order primitive instead of adding a second broker stack;
- supports deterministic staged LIMIT execution, partial-fill state and durable CAS/idempotency;
- revalidates portfolio/risk/strategy/optimizer/market/instrument state before progression;
- ambiguous possible-submit halts and reconciles without a second submit;
- preserves own-funds BUY, own-position SELL, RUB share/ETF and LIMIT/CURRENCY/DAY boundaries;
- adds no transfer, withdrawal, margin, short, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real execution.

## WP13 — Portfolio Watchtower

Tracking: issue #212 / draft PR #213.  
Branch: `v9/wp13-portfolio-watchtower`.  
Dependency base: WP12 merge `8f247fd3b966c16eb08fdfeed080010bdcbedde9`.

Implemented architecture:

- versioned Watchtower input/state/alert/evaluation contracts;
- deterministic reducer over canonical WP6 Credit, WP8 Portfolio Risk and market evidence rather than duplicate analytics;
- material rating downgrade/watch, active default, corporate event, liquidity, concentration, policy drift and data-quality signals;
- severity, semantic fingerprints and transport-delivery deduplication;
- no notification when no material alert is emitted;
- replay-safe duplicate QStash delivery handling;
- durable Watchtower state with separate Upstash namespace, HMAC-authenticated state envelopes and compare-and-swap updates;
- strict HTTPS-only Upstash REST client and fail-closed durable-state behavior;
- QStash schedule client with one canonical custom schedule ID, bounded retries, callbacks/failure callbacks and body redaction;
- exact raw-body + exact-destination QStash signature verification with current/next signing-key rotation;
- hidden internal POST routes excluded from GPT Actions OpenAPI;
- feature flag defaults disabled and canonical evidence provider installation is explicit/fail-closed;
- schedule reconciliation CLI and operations/recovery runbook;
- permanent repository boundary guard and mypy coverage.

Hard WP13 safety invariants:

- `execution_authorized=false`;
- `trading_methods=false`;
- no broker write token/client in Watchtower runtime;
- no autonomous recurring real-money execution;
- no transfer/withdrawal/margin/short authority;
- monitoring may request review/recommendation or a future proposed immutable plan, but cannot authorize or submit a real order;
- applied Custom GPT remains v8.6.1.

Acceptance/security coverage includes:

- clean initial baseline and silent no-change behavior;
- initial critical default alert;
- rating/default/corporate/liquidity/concentration/policy/data-quality signals;
- semantic dedup and condition recurrence after recovery;
- duplicate delivery replay safety;
- deterministic/canonical alert and evaluation hashing;
- in-memory and durable Upstash state semantics;
- stale-writer/CAS conflict, wrong-secret/tamper and storage-failure tests;
- QStash current/next key signature verification, body/URL mismatch rejection, bounded retries and observable schedule state;
- signed hidden runtime routes and callback acknowledgements;
- single `app:app` Gateway registration while Watchtower routes remain absent from GPT OpenAPI;
- disabled-by-default and missing-provider fail-closed behavior;
- repository guard preventing broker/Sandbox mutation authority inside WP13.

WP13 is **not complete** until the source-synced branch head passes the full exact-head Regression Shield and security jobs, review threads remain zero and PR #213 is squash-merged.

## WP14 dependency

Tracking issue: #214.

WP14 starts from `main` only after WP13 squash merge. Canonical scope is Decision Journal, Evaluation & Learning Loop: immutable decision/evidence/policy/plan/execution/outcome records; expected-vs-realized evaluation without hindsight rewriting; NO_ACTION and policy-objective benchmarks; quality metrics; sanitized synthetic/fake-broker offline replay datasets; and no self-modifying production rules without reviewed code/config changes.

## Canonical production configuration

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- Render: Free;
- entrypoint: `app:app`;
- production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.

GitHub remains canonical for code/config/recovery reference but does not automatically synchronize GPT Editor, Render secrets, QStash or Upstash environment values.

## Real-money boundary remains unchanged

Production read-only uses `TINVEST_TOKEN`. Sandbox uses `TINVEST_SANDBOX_TOKEN`. Real v1 uses the dedicated `TINVEST_TRADING_TOKEN` and remains limited to:

`fresh facts → immutable proposal/plan → exact owner confirmation in a new user turn → one submit/idempotency → broker reconciliation`.

Neither WP13 nor planned WP14 adds withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring real execution or token management.

**Production release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete and protected while v9 development continues.**
