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
- WP9 Meta-Strategy Selector — PR #204, squash merge `f758fd7325e5d3e6602fa441cc65f8cd3e10c2c3`, exact-head Regression Shield #1088 on `d95d56a967aa822a22a2f8bbdec95748ad9734f7`.

WP9 accepted behavior includes exact portfolio/WP2/WP8 binding, bounded five-regime selection with `NO_ACTION`, pre-ranking owner-risk caps, fresh cost/tax provenance, deterministic review/cancellation conditions, no expected-return or macro-regime forecast input, canonical SHA-256 and a pure internal strategy runtime with `trading_methods=false`.

### WP10 — Portfolio Optimizer & Capital Scaling — active

Tracking: issue #205 / draft PR #206 / branch `v9/wp10-portfolio-optimizer`.

Implemented in the current WP10 branch:

- exact binding to portfolio snapshot, recomputed WP2 IPS fingerprint/reference, exact current WP8 risk and exact WP9 selection;
- deterministic fixed component budgets per bounded WP9 regime; no alpha/expected-return optimizer;
- owner reserve and max-position limits before lot conversion;
- small-capital minimum meaningful-position and whole-lot rules;
- large-capital spread, turnover participation, top-of-book participation, maximum staging days and partial-fill-aware metadata;
- clean execution price separated from full economic valuation;
- market price itself is part of structured market evidence with timestamp/source SHA-256;
- bonds keep clean price and НКД separate; missing НКД blocks a trade instead of assuming zero;
- bond full value reconciles to clean price + НКД/lot-size, preserving the project-wide full-value convention;
- leg arithmetic keeps clean gross, accrued interest, settlement notional, commission, estimated SELL tax and signed cash delta separate;
- owner reserve is rechecked after settlement/НКД/fees; BUYs are reduced deterministically before reserve can be spent;
- account-ineligible/unknown BUYs fail closed;
- stale/future market/friction evidence, price-binding mismatch, wide spread and zero safe capacity fail closed;
- deterministic trade IDs include a stable SHA suffix and multi-leg output is canonical by full trade ID;
- CURRENT / TARGET / NO_ACTION scenarios contain no return forecast;
- every changed target position is converted to a real WP8 hypothetical trade effect and revalidated through the WP8 risk engine;
- target risk must be decision-ready, policy-compliant and based on the exact supplied current-risk baseline;
- optimizer runtime remains internal/read-only, broker-mutation surfaces are repository-guarded, and `trading_methods=false` is contract-enforced.

WP10 acceptance coverage includes normal rebalancing, source-order invariance, large-capacity scaling/staging, reserve-after-fees, missing/stale evidence, price-binding mutation, missing bond НКД, WP8 target policy breach, same-version IPS mutation, small-cap micropositions, collision-shaped trade-ID ordering and non-zero bond accrued-interest settlement.

WP10 is not complete until the **final exact-head** Regression Shield after all code/documentation changes is green, review threads are zero and PR #206 is squash-merged.

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
