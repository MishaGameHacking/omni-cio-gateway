# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-05

## Executive state

Omni-CIO remains **one Custom GPT + one production Render Gateway**.

- Applied external GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.
- UI: `Omni-CIO API | Управляющий и аналитик v9.0.0`.
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
- Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.
- Stable Gateway entrypoint: `app:app`.
- Production Gateway: `https://omni-cio-gateway.onrender.com`.
- Production OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- Completed tracking epic: #176.
- WP15 acceptance: #216.

The protected v8.6.1 rollback release remains available in GitHub. Its real BUY/SELL v1 acceptance remains **100% complete**.

Canonical recovery invariant remains: **idempotent replay verified with no second submit**.

## Program completion

| WP | State | Evidence |
|---|---|---|
| WP0 Baseline freeze | COMPLETE | #178 / PR #181 / #989 |
| WP1 Natural Language CIO Router | COMPLETE | #182 / PR #184 / #1002 |
| WP2 Investment Policy Statement | COMPLETE | #186 / PR #187 / #1014 |
| WP3 Market Universe Engine | COMPLETE | #188 / PR #189 / #1019 |
| WP4 Deterministic Candidate Funnel | COMPLETE | #190 / PR #191 / #1035 |
| WP5 Research & Evidence Engine | COMPLETE | #193 / PR #194 / #1043 |
| WP6 Credit, Rating & Default 2.0 | COMPLETE | #195 / PR #196 / #1057 |
| WP7 Fund X-Ray Engine | COMPLETE | #197 / PR #198 / #1064 |
| WP8 Portfolio Risk Engine 2.0 | COMPLETE | #199 / PR #201 / #1078 |
| WP9 Meta-Strategy Selector | COMPLETE | #203 / PR #204 / #1088 |
| WP10 Portfolio Optimizer & Capital Scaling | COMPLETE | #205 / PR #206 / #1105 |
| WP11 Immutable Portfolio Plan Protocol | COMPLETE | #207 / PR #208 / #1114 |
| WP12 Safe Plan Execution Engine | COMPLETE | #209 / PR #211 / #1160 |
| WP13 Portfolio Watchtower | COMPLETE | #212 / PR #213 / #1199 |
| WP14 Decision Journal / Evaluation | COMPLETE | #214 / PR #215 / #1231 |
| WP15 Custom GPT v9 Configuration & Recovery | COMPLETE | #216 / PR #223 / #1241 + owner acceptance |

WP15 repository target was squash-merged as `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` after exact-head Regression Shield #1241 on `578ffad5362df3182f8a23937ab4ca19de5c0b78`, with quality/full pytest/coverage, dependency audit, SAST, secret scan and zero unresolved review threads.

Owner acceptance then confirmed on the **existing** GPT:

- v9.0.0 name/description/starters/Instructions applied;
- exact 10-file Knowledge manifest applied once each;
- production OpenAPI refreshed;
- external API Key → Bearer authentication works without recording the secret value;
- Actions work after `Update`;
- `gatewayHealth` exact-action isolation passed;
- portfolio/cash/analytics read-only routing passed;
- SBER advisory request did not prepare or submit a real order;
- Watchtower/journal explanation did not fabricate server execution;
- real readiness check called only `getRealTradingStatus` and did not call prepare/execute;
- no real trade was submitted during configuration acceptance;
- recovery documentation and protected v8.6.1 rollback assets remain present.

Issues #176 and #216 are closed completed.

## Runtime / safety boundary

Always preserve:

- one GPT and one production Gateway;
- stable `app:app` entrypoint;
- production read-only broker credential never used as real-execution fallback;
- Sandbox remains virtual and isolated;
- real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- prepare and execute never collapse into one authorization turn;
- ambiguous possible-submit → reconciliation only, no automatic retry;
- submitted != filled without broker proof;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, stop/replace/async, token management or autonomous recurring real-money execution under the current reviewed surface;
- account identity remains masked in user-facing output;
- secret values/private broker payloads never enter GitHub or GPT Knowledge.

Master real rollback: `REAL_TRADING_ENABLED=false`.

Watchtower rollback: `WATCHTOWER_ENABLED=false`.

## Applied v9 Actions state

The effective production `/openapi.json` is the runtime authority.

Baseline read-only portfolio routing remains:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Conditional Sandbox and Real operations may also be present when their server feature/readiness gates are enabled. Reviewed real operationIds remain:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Internal v9 router/policy/universe/research/credit/fund/risk/strategy/optimizer/plan/Watchtower/journal modules are **not automatically GPT Actions**. The GPT may claim server execution only when actual Action/evidence proves it.

## Canonical recovery files

- setup/recovery entry: `gpt/SETUP_INDEX.md`;
- applied v9 registry: `gpt/CONFIGURATION.md`;
- applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Actions: `gpt/ACTIONS_CATALOG.md`;
- external secret roles: `gpt/SECRETS_AND_RENDER.md`;
- full Preview/rollback procedure: `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

## Maintenance mode

The v9 feature program is complete. Current work is controlled maintenance only:

- dependency updates remain proposals until exact-head Regression Shield/security passes;
- incompatible toolchain updates are held narrowly and documented rather than forcing CI green;
- stale generated/bootstrap artifacts are removed only through reviewed cleanup PRs;
- no maintenance change may broaden GPT or broker authority implicitly.

**Current state: Omni-CIO v9.0.0 is fully implemented, merged, externally applied to the existing GPT and owner-accepted. The repository is in controlled maintenance mode.**
