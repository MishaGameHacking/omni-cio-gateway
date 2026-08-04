# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная инженерная последовательность остаётся в Git/PR history; этот файл фиксирует release/program milestones и не дублирует архитектурные документы целиком.

## [Unreleased]

### Omni-CIO v9 Portfolio Autopilot — program development

Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`. Стабильный v8.6.1 остаётся защищённым production baseline до WP15.

Завершённые work packages:

- WP0 Baseline freeze — PR #181, Regression Shield #989;
- WP1 Natural Language CIO Router — PR #184, merge `7f677288...`, #1002;
- WP2 Investment Policy Statement Engine — PR #187, merge `75c9ae07...`, #1014;
- WP3 Market Universe Engine — PR #189, merge `5ae81aa9...`, #1019;
- WP4 Deterministic Candidate Funnel — PR #191, merge `3946fc9a...`, #1035;
- WP5 Research & Evidence Engine — PR #194, merge `f8f0bb95...`, #1043;
- WP6 Credit, Rating & Default Engine 2.0 — PR #196, merge `64316008...`, #1057;
- WP7 Fund X-Ray Engine — PR #198, merge `15505272...`, #1064;
- WP8 Portfolio Risk Engine 2.0 — PR #201, merge `24e027f1...`, #1078;
- WP9 Meta-Strategy Selector — PR #204, merge `f758fd73...`, exact-head #1088;
- WP10 Portfolio Optimizer & Capital Scaling — PR #206, squash merge `f73929771bcae4058c3c83b3d0632b8d66b8d05f`, exact-head Regression Shield #1105 on `2ff38f962718e58ec9c12e0e89fd2605310592cc`.

### WP11 — Immutable Portfolio Plan Protocol — final merge gate

Tracking: issue #207 / draft PR #208 / branch `v9/wp11-immutable-portfolio-plan`.

Implemented:

- frozen/versioned `PORTFOLIO_PLAN` contract with deterministic canonical SHA-256;
- exact portfolio + WP2 policy + current WP8 + WP9 + WP10 + target WP8 bindings;
- full re-validation of upstream Pydantic payloads and recomputation of WP8/WP9/WP10 hashes to catch stale-hash and recalculated-hash `model_copy` tampering;
- exact deterministic WP10 target rows and ordered BUY/SELL/NO_ACTION legs;
- clean execution price, bond НКД, settlement notional, commission, estimated SELL tax, cash delta and current/target cash preserved separately;
- plan arithmetic reconciled to embedded optimizer legs, target rows and WP8 before/after states;
- build-time freshness gates for market, friction and FX evidence;
- BUY eligibility required only for BUY; an already-held SELL is not falsely blocked by loss of buy eligibility;
- explicit validity window and complete hard-cancellation code set;
- review-time market/friction/FX freshness plus clean-price/НКД/spread/turnover/depth/FX drift gates;
- extreme measured drift can exceed 10,000 bps without contract overflow while bounded tolerances still cancel the plan;
- any material plan mutation changes the exact plan SHA and therefore changes the plan-specific approval challenge;
- actionable challenge is `ПОДТВЕРЖДАЮ ПЛАН <PLAN_SHA_PREFIX>` and is exposed only by a valid review;
- review remains read-only with `execution_authorized=false` and `trading_methods=false`;
- no broker client/token/journal/order submit/cancel/replace authority, no public route/OpenAPI/GPT Editor change;
- dedicated immutable-plan repository boundary guard plus mypy scope;
- architecture, threat-model and data-contract documents.

Acceptance coverage includes the real WP2→WP8→WP9→WP10→WP11 actionable chain, full NO_ACTION chain, source-order invariance, immutable hash/challenge mutation sensitivity, stale/missing/future evidence, pre-valid/expired review, clean-price and bond-НКД drift, liquidity/spread deterioration, friction change, BUY/SELL eligibility semantics, FX drift/freshness, unknown observation rejection and model-copy tamper rejection.

The code/test head `9f410f88e31fa161fcd713b9636ab7f460a6f5d6` passed security, Ruff, format, mypy, `app:app`, the read-only GPT Actions contract and full Regression Shield #1111. Status/changelog synchronization changes the PR head, so WP11 remains in final merge gate until the new exact-head Regression Shield and review-thread checks are green and PR #208 is squash-merged.

Next dependency after merge: **WP12 — Safe Plan Execution Engine**, reusing the proven v8.6.1 single-order protocol rather than creating a second execution stack.

Applied Custom GPT remains v8.6.1 until WP15; current v9 development is not authorization for broader real-money execution.

### Omni-CIO v8.6.1 — released / owner accepted

- GPT Editor uses `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`; full v8.6.0 remains engineering reference.
- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Production OpenAPI exposes accepted read-only, Sandbox and conditional Real Trading surfaces.
- Durable real journal uses Upstash Redis over HTTPS; Render remains Free.
- Dedicated `TINVEST_TRADING_TOKEN` is separate from read-only `TINVEST_TOKEN`.
- Owner Phase 3 acceptance on 2026-08-03 verified readiness, expiry/mismatch rejection, own-funds guard, exact-action isolation and kill-switch rollback with zero real submit.
- Owner Phase 4 acceptance on 2026-08-03 authorized exactly one controlled SBER LIMIT BUY:
  - one broker submit;
  - `EXECUTION_REPORT_STATUS_FILL`;
  - 1/1 lot at 280.55 RUB;
  - commission 0.84 RUB;
  - portfolio/operations reconciliation;
  - exact confirmation replay returned existing state and created no second submit.
- Real BUY/SELL v1 Definition of Done is complete.

### Real-money execution v1 engineering

- Issue #164 tracks the accepted staged real BUY/SELL release.
- PRs #168/#169/#170 established durable proposal state, conditional real Actions, full behavior reference and Upstash Redis journal.
- Real v1 remains limited to supported cash share/ETF, RUB, BUY/SELL, LIMIT/CURRENCY/DAY, own-funds/own-position.
- Margin/short, MARKET/BESTPRICE, derivatives/currencies, stop automation, ReplaceOrder, transfer/withdrawal and autonomous execution remain absent.
- Immutable/HMAC-bound proposal + exact owner confirmation + repeated preflight + UUID idempotency + broker reconciliation remain mandatory.
- Possible-submit ambiguity is `unknown/do-not-resubmit`; `submitted` is never treated as `filled` without broker proof.
- Missing/unreachable/tampered durable storage publishes no usable real mutation path and never falls back to ephemeral memory.

### T-Invest Sandbox execution

- PR #160 added the isolated optional Sandbox contour; PR #162 fixed verified TLS/CA transport.
- `TINVEST_SANDBOX_TOKEN` never replaces `TINVEST_TOKEN`.
- `SANDBOX_TRADING_ENABLED=false` preserves production baseline surface.
- Sandbox proposal → exact confirmation → submit with repeated limits, UUID idempotency and ambiguous-submit no-retry.
- Margin confirmation, withdrawal/transfer, auto-replace and stop automation remain absent.
- Owner Preview acceptance on 2026-08-02 covered account/funding/portfolio, BUY/SELL, rejection, replay, LIMIT state/cancel and reconciliation.
- Sandbox responses remain `real_money=false`.

### Repository state

- Repository is consolidated around one product: Omni-CIO Custom GPT + Gateway.
- `gpt/SETUP_INDEX.md` is the setup/recovery entry point.
- Current GPT Editor behavior is v8.6.1 Compact; v8.6.0 is full reference.
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` is the canonical program-status index.
- Runtime dependencies `app_v371.py`, `app_v360.py` and `main.py` remain intentionally because current `app.py` still imports them.

## [2026-08-02] Custom GPT v8.4.1 acceptance

- PR #146 made portfolio-management routing tool-first.
- `УПРАВЛЯЙ ПОРТФЕЛЕМ` requires `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics` before analysis.
- Exact-action requests remain isolated.
- Recommended model was fixed as Thinking 5.6.
- Canonical endpoint: `https://omni-cio-gateway.onrender.com`.
- User-visible timezone: Europe/Moscow / MSK.
- Market gate blocks exact personalized sizing without fresh best ask / market readiness.
- Production Knowledge set: exactly 10 files.

## [2026-08-01] Gateway v3.10.0 baseline

- Read-only Gateway surface stabilized at 14 GET Actions.
- Added private read-only `getFinalDecisionReview` contract.
- Preserved Bearer protection, masked account output and `app:app`.
- Portfolio, market, liquidity, operations, purchase-capacity and broker-report workflows are covered by Regression Shield.
- Security baseline uses pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## Historical note

Full engineering history is available in Git commits/issues/PRs. Old versions are not current configuration instructions and must not replace `main`, `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` or `gpt/SETUP_INDEX.md`.
