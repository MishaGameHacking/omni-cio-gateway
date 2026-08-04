# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**.

- Protected applied GPT: **v8.6.1** until WP15 owner Preview + `Update` are completed.
- Repository target GPT: **v9.0.0**.
- Target UI: `Omni-CIO API | Управляющий и аналитик v9.0.0`.
- Target Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
- Target Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.
- Stable Gateway entrypoint: `app:app`.
- Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- Tracking epic: #176.

Protected baseline release state remains **Omni-CIO v8.6.1 real BUY/SELL v1 = 100% complete and protected**.

Canonical recovery invariant remains: **idempotent replay verified with no second submit**.

## Work-package evidence

| WP | State | Issue / PR | Merge / CI evidence |
|---|---|---|---|
| WP0 Baseline freeze | COMPLETE | #178 / #181 | `4fd3993b...`, #989 |
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
| WP13 Portfolio Watchtower | COMPLETE | #212 / #213 | `251a528aebd6a2ecf0617828c43d39e14a38d69e`, #1199 |
| WP14 Decision Journal / Evaluation | COMPLETE | #214 / #215 | `507b7f53e3ab924f0d484e348528c23b79ffce9d`; exact-head #1231 on `56488ddd...`; Windows smoke #65; zero threads |
| WP15 Custom GPT v9 Configuration & Recovery | IN PROGRESS | #216 | branch `v9/wp15-custom-gpt-configuration-recovery` starts strictly from WP14 merge `507b7f53...`; repository config target v9.0.0 under development |

## WP14 completion evidence

WP14 was squash-merged into `main` as `507b7f53e3ab924f0d484e348528c23b79ffce9d` after exact-head Regression Shield #1231 on `56488dddb8a07d0da1cc880e15cb2650e2c6f174`.

The exact head passed:

- reproducible dependency-lock checks;
- repository/security policy;
- compile, Ruff, formatting and mypy;
- stable `app:app` and read-only GPT Action contract;
- full pytest/coverage;
- dependency audit, SAST and secret scan;
- Windows smoke #65;
- zero unresolved review threads.

Decision journal/evaluation remains append-only, evidence-bound, non-self-modifying and without broker-write authority.

## WP15 — current work

Tracking: issue #216.  
Branch: `v9/wp15-custom-gpt-configuration-recovery`.  
Dependency base: WP14 merge `507b7f53e3ab924f0d484e348528c23b79ffce9d`.

Repository target configuration already includes/in development:

- compact v9 Instructions within editor-size guard;
- canonical v9 Knowledge manifest;
- Russian human-language conversation starters;
- reviewed Actions/OpenAPI policy that never invents internal engine operationIds;
- upgrade-in-place architecture and threat model;
- recovery/runbook covering existing GPT, Actions, external authentication roles, Render/Upstash/QStash boundaries and rollback;
- version/recovery consistency CI guard;
- owner Preview acceptance checklist.

Hard WP15 boundary:

- update the **existing** GPT; do not create a duplicate;
- GitHub target readiness does not equal applied external acceptance;
- internal v9 engines are not claimed as GPT Actions unless operationIds exist in effective `/openapi.json`;
- Apps remain OFF while custom Actions are used;
- broker/storage/scheduler secret values remain external;
- real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- no transfer/withdrawal, margin/short, MARKET/BESTPRICE, autonomous recurring real execution or token management is added by configuration.

WP15 repository work is not complete until its exact-head Regression Shield/security is green, review threads are zero and its PR is squash-merged.

The **program** is not complete until the owner then applies the merged target to the existing GPT in ChatGPT web, passes Preview acceptance/restoration demonstration, selects `Update`, and records acceptance evidence.

## Canonical target/recovery files

- target registry: `gpt/CONFIGURATION.md`;
- setup index: `gpt/SETUP_INDEX.md`;
- target Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Actions: `gpt/ACTIONS_CATALOG.md`;
- external secret roles: `gpt/SECRETS_AND_RENDER.md`;
- full upgrade/Preview/rollback: `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- WP15 architecture: `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md`;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

Gateway remains `https://omni-cio-gateway.onrender.com` with production OpenAPI at `https://omni-cio-gateway.onrender.com/openapi.json`.

## Applied-vs-target rule

Until owner Preview/Update evidence is recorded:

- applied GPT = v8.6.1;
- repository target = v9.0.0.

Never infer applied v9 merely because the GitHub branch/PR has v9 files.

**Current state: WP14 complete; WP15 is the final active package; protected v8.6.1 remains recoverable and safe while v9.0.0 target configuration is completed.**
