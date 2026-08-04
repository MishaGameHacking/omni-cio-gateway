# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**. The protected applied GPT release remains **v8.6.1** until WP15 is merged and then explicitly applied to the existing GPT in Preview. The owner-approved v9 program has completed WP0–WP13; WP14 is in its final exact-head delivery gate; WP15 is the only remaining package after WP14.

Protected baseline release state: **Omni-CIO v8.6.1 real BUY/SELL v1 = 100% complete and protected.**

Production invariants:

- current applied UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- current applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- stable Render entrypoint: `app:app`;
- one production Gateway only;
- production read-only, Sandbox and Real contours remain separated;
- real BUY/SELL remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- canonical recovery invariant: **idempotent replay verified with no second submit**;
- durable real execution state remains Upstash Redis over HTTPS;
- `REAL_TRADING_ENABLED=false` remains the master real-money rollback;
- v9 research/monitoring/evaluation does not implicitly broaden broker-write authority;
- no duplicate GPT, second Gateway, separate frontend, competing scheduler or second broker stack.

Protected v8.6.1 release commit: `baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`.

## Canonical v9 program

Roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Tracking epic: #176.

Dependency order remains WP13 → WP14 → WP15. WP14 started strictly from the WP13 merge on `main`; WP15 must start strictly from the eventual WP14 squash merge.

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
| WP9 Meta-Strategy Selector | COMPLETE | #203 / #204 | `f758fd73...`, #1088 |
| WP10 Portfolio Optimizer & Capital Scaling | COMPLETE | #205 / #206 | `f7392977...`, #1105 |
| WP11 Immutable Portfolio Plan Protocol | COMPLETE | #207 / #208 | `7c3006d332041ec352f0c2eab8c7cb70e4c1a6af`, #1114 |
| WP12 Safe Plan Execution Engine | COMPLETE | #209 / #211 | `8f247fd3b966c16eb08fdfeed080010bdcbedde9`, #1160 |
| WP13 Portfolio Watchtower | COMPLETE | #212 / #213 | `251a528aebd6a2ecf0617828c43d39e14a38d69e`, exact-head #1199 on `91198ab4...`, zero review threads |
| WP14 Decision Journal / Evaluation & Learning Loop | IN PROGRESS — FINAL EXACT-HEAD GATE | #214 / draft #215 | implementation + production recorder + docs/source sync complete on `v9/wp14-decision-journal-evaluation`; final exact-head Regression Shield/security + zero threads + squash merge required |
| WP15 Custom GPT v9 Configuration & Recovery | PENDING | #216 | start only from WP14 merge; current applied GPT remains v8.6.1 |

## WP13 completion evidence

WP13 is complete and squash-merged to `main` as `251a528aebd6a2ecf0617828c43d39e14a38d69e` after exact-head Regression Shield #1199 on `91198ab471f5666d06e90b44ce1a85e60ea406b8`, with quality/full pytest/coverage and security SUCCESS and zero unresolved review threads.

Portfolio Watchtower provides deterministic scheduled read-only monitoring, material alerting/deduplication, replay-safe QStash delivery, HMAC/CAS Upstash state, signed hidden scheduler/callback routes, disabled-by-default/fail-closed installation and recovery tooling. It has no broker write token/client and cannot authorize or submit a real trade.

## WP14 — Decision Journal, Evaluation & Learning Loop

Tracking: #214 / draft PR #215.  
Branch: `v9/wp14-decision-journal-evaluation`.  
Dependency base: WP13 merge `251a528aebd6a2ecf0617828c43d39e14a38d69e`.

Implemented architecture:

- strict immutable `DecisionJournalRecordV1`, `DecisionOutcomeRecordV1`, `DecisionEvaluationRecordV1` and replay/regression contracts;
- canonical SHA-bound decision identity and separate append-only outcome/evaluation identity;
- production recorder binding canonical `DecisionSetV1` → exact WP8 portfolio-risk assessment → optional exact WP11 plan → optional exact WP12 execution session;
- cross-WP policy/portfolio/risk/strategy/optimizer/plan/execution mismatches fail closed;
- executed lots cannot be journaled as executed without owner-approved WP12 state;
- deterministic realized-period result net of external flows;
- evidence-bound `NO_ACTION` and policy-objective benchmarks; unavailable counterfactuals remain explicitly unavailable;
- data-completeness, research-coverage, concentration, cash-weight and execution-quality metrics;
- append-only in-memory journal and separate durable Upstash namespace using reviewed HTTPS transport, row/meta HMAC and atomic CAS semantics;
- sanitized synthetic/fake-broker replay datasets and deterministic regression comparison for MODEL/PROMPT/RULES/CONFIG candidates;
- candidate changes may become review-ready only; WP14 cannot self-modify or deploy production prompts/rules/policy/config;
- permanent repository boundary guard scans the full WP14 runtime and rejects real-trading/Sandbox broker mutation authority;
- dependency lock verification remains strict/hash-bound and now constrains both runtime and dev re-compiles to the reviewed lock state to avoid extra-index resolver drift.

Hard WP14 invariants:

- historical expectations are immutable;
- outcomes/evaluations are separate records;
- no fabricated counterfactual precision;
- `execution_authorized=false` and `trading_methods=false` in WP14 contracts;
- no broker token/client, order submit/cancel/replace, transfer, withdrawal, margin, short or autonomous real-money execution in the journal/evaluation package;
- no full account identifier, raw private broker payload or secret in replay datasets;
- applied Custom GPT remains v8.6.1 until WP15.

WP14 is **not complete** until the final branch head passes the full exact-head Regression Shield and security jobs, review threads remain zero and PR #215 is squash-merged.

## WP15 dependency and target

Tracking: #216.

After WP14 merges, WP15 upgrades the **existing** Omni-CIO GPT rather than creating another bot. Required GitHub deliverables are compact v9 Instructions, canonical Knowledge manifest, Russian conversation starters, reviewed production Actions/OpenAPI catalog, version-consistency CI, full recovery/secret-boundary runbook and owner Preview acceptance checklist/restoration demonstration.

The current applied GPT is not modified before WP15 passes its own repository gate.

## Canonical current production configuration

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- setup/recovery index: `gpt/SETUP_INDEX.md`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- Render entrypoint: `app:app`;
- production Knowledge: current v8.6.1 set from `gpt/CONFIGURATION.md` until WP15 changes are merged and explicitly applied.

GitHub is canonical for code/config/recovery reference but does not automatically synchronize the GPT Editor, Render secrets, QStash or Upstash environment values.

## Real-money boundary remains unchanged

Production read-only uses `TINVEST_TOKEN`. Sandbox uses `TINVEST_SANDBOX_TOKEN`. Real execution uses the separate `TINVEST_TRADING_TOKEN` and remains bounded by:

`fresh facts → immutable proposal/plan → exact owner confirmation in a new user turn → one idempotent submit → broker reconciliation`.

WP13/WP14 add no withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring real execution or token management.

**Current release state: applied Omni-CIO v8.6.1 remains protected while WP14 closes and WP15 is prepared.**
