# Changelog

Краткая история заметных изменений Omni-CIO. Подробная инженерная последовательность остаётся в Git commits, issues и PR; этот файл фиксирует release/program milestones и текущий maintenance state без дублирования архитектурных документов.

> **Правило чтения истории.** Закрытые issues, merged PR и старые комментарии являются историческими снимками состояния на момент работы. Они не определяют текущий applied state. Для текущего состояния использовать `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md`, `gpt/CONFIGURATION.md` и accepted `main`.

## [Unreleased]

### Controlled maintenance

- Omni-CIO v9.0.0 уже полностью реализован, merged и owner-accepted на **существующем** Custom GPT.
- Текущий режим репозитория: **controlled maintenance** — dependency/security updates, compatibility fixes, documentation/recovery hygiene и owner-approved future programs.
- Maintenance changes проходят `branch → focused change/tests → exact-head Regression Shield/security → zero unresolved review threads → squash merge`.
- Изменения applied GPT configuration или reviewed Action contract дополнительно требуют owner Preview/`Update` на том же GPT; обычная backend/doc maintenance не означает автоматическое изменение GPT Editor.
- Protected rollback v8.6.1 сохраняется только как проверенный recovery baseline и не является текущей applied-версией.

## [2026-08-05] Omni-CIO v9.0.0 — fully implemented and owner-accepted

Canonical completed program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

Current applied UI: `Omni-CIO API | Управляющий и аналитик v9.0.0`.

### Program completion

WP0–WP15 завершены. Канонический completion/status index: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

- WP0 Baseline freeze — PR #181 / Regression Shield #989;
- WP1 Natural Language CIO Router — PR #184 / merge `7f677288...` / #1002;
- WP2 Investment Policy Statement Engine — PR #187 / merge `75c9ae07...` / #1014;
- WP3 Market Universe Engine — PR #189 / merge `5ae81aa9...` / #1019;
- WP4 Deterministic Candidate Funnel — PR #191 / merge `3946fc9a...` / #1035;
- WP5 Research & Evidence Engine — PR #194 / merge `f8f0bb95...` / #1043;
- WP6 Credit, Rating & Default Engine 2.0 — PR #196 / merge `64316008...` / #1057;
- WP7 Fund X-Ray Engine — PR #198 / merge `15505272...` / #1064;
- WP8 Portfolio Risk Engine 2.0 — PR #201 / merge `24e027f1...` / #1078;
- WP9 Meta-Strategy Selector — PR #204 / merge `f758fd73...` / #1088;
- WP10 Portfolio Optimizer & Capital Scaling — PR #206 / merge `f7392977...` / #1105;
- WP11 Immutable Portfolio Plan Protocol — PR #208 / merge `7c3006d3...` / #1114;
- WP12 Safe Plan Execution Engine — PR #211 / merge `8f247fd3...` / #1160;
- WP13 Portfolio Watchtower — PR #213 / merge `251a528a...` / #1199;
- WP14 Decision Journal, Evaluation & Learning Loop — PR #215 / merge `507b7f53...` / #1231;
- WP15 Custom GPT v9 Configuration & Recovery — PR #223 / merge `b9e4fabc...` / #1241 + owner acceptance in #216.

Epic #176 and WP15 issue #216 are closed completed. The existing GPT was upgraded in place rather than duplicated.

### Owner acceptance

Owner evidence on 2026-08-05 confirmed:

- v9.0.0 Name/Description/starters/Instructions applied to the existing GPT;
- exact 10-file Knowledge set applied once each;
- production OpenAPI and external Bearer authentication work after `Update`;
- exact `gatewayHealth` isolation;
- portfolio/cash/analytics read-only routing;
- SBER advisory request did not prepare or execute a real order;
- Watchtower/journal explanation did not fabricate server execution;
- real-readiness smoke invoked only `getRealTradingStatus`, without prepare/execute;
- no new live order was submitted during v9 configuration acceptance;
- recovery path and protected v8.6.1 rollback remain available.

### Runtime and safety state

- one existing Custom GPT + one production Gateway;
- stable Render entrypoint `app:app`;
- production read-only credential remains isolated from Sandbox and Real execution;
- effective production `/openapi.json` is the GPT Action authority;
- internal v9 engines are not automatically GPT Actions;
- Real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- no transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real-money execution under the reviewed surface;
- master Real rollback remains `REAL_TRADING_ENABLED=false`;
- Watchtower rollback remains `WATCHTOWER_ENABLED=false`.

## [2026-08-03] Omni-CIO v8.6.1 — historical protected rollback baseline

This section is **historical release evidence**, not the current applied GPT configuration.

- Protected Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Historical UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Production OpenAPI exposed the accepted read-only, Sandbox and conditional Real Trading contours.
- Durable real journal used Upstash Redis over HTTPS; the dedicated `TINVEST_TRADING_TOKEN` remained separate from read-only `TINVEST_TOKEN`.
- Owner Phase 3 acceptance verified readiness, expiry/mismatch rejection, own-funds guard, exact-action isolation and kill-switch rollback with zero real submit.
- Owner Phase 4 acceptance authorized exactly one controlled SBER LIMIT BUY and verified broker/portfolio/operations reconciliation.
- Canonical protected recovery invariant: **idempotent replay verified with no second submit**.
- Real BUY/SELL v1 Definition of Done was completed and remains the protected execution primitive/fallback used by later v9 plan execution.

### Real-money execution v1 engineering

- Issue #164 tracked the staged real BUY/SELL release.
- PRs #168/#169/#170 established durable proposal state, conditional Real Actions and Upstash journal hardening.
- Real v1 remained limited to supported cash share/ETF, RUB, BUY/SELL, LIMIT/CURRENCY/DAY, own-funds/own-position.
- Margin/short, MARKET/BESTPRICE, derivatives/currencies, stop automation, ReplaceOrder, transfer/withdrawal and autonomous execution remained outside the reviewed surface.
- Immutable/HMAC-bound proposal + exact owner confirmation + repeated preflight + UUID idempotency + broker reconciliation remained mandatory.
- Possible-submit ambiguity was `unknown/do-not-resubmit`; `submitted` was never treated as `filled` without broker proof.

### T-Invest Sandbox execution

- PR #160 added the isolated optional Sandbox contour; PR #162 fixed verified TLS/CA transport.
- `TINVEST_SANDBOX_TOKEN` never replaced `TINVEST_TOKEN`.
- Sandbox remained virtual (`real_money=false`) and required proposal → exact confirmation → submit, repeated limits, UUID idempotency and ambiguous-submit no-retry.

## [2026-08-02] Custom GPT v8.4.1 acceptance — historical

- PR #146 made portfolio-management routing tool-first.
- `УПРАВЛЯЙ ПОРТФЕЛЕМ` required `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics` before analysis.
- Exact-action requests remained isolated.
- Production Knowledge set contained exactly 10 files.
- This release has been superseded by the owner-accepted v9.0.0 configuration.

## [2026-08-01] Gateway v3.10.0 baseline

- Read-only Gateway baseline stabilized at 14 GET Actions.
- Added private read-only `getFinalDecisionReview` contract.
- Preserved Bearer protection, masked account output and `app:app`.
- Portfolio, market, liquidity, operations, purchase-capacity and broker-report workflows were covered by Regression Shield.
- Security baseline used pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## Historical note

Full engineering history is available in Git commits/issues/PRs. Historical descriptions may intentionally mention the then-current version or an unfinished WP. Do not use those historical statements as current instructions. Current authority is accepted `main` plus `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md`, `gpt/CONFIGURATION.md` and the effective production OpenAPI where runtime Action authority is relevant.
